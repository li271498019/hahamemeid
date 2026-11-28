"""Offline commands. They do not open a port, sign with a generated production key, or broadcast."""

import argparse
import json
import sys

from tools.season1.checker import check_scores
from tools.season1.eip712 import SignRejected, sign_verify
from tools.season1.merkle import (
    canonical_manifest,
    eligible_entries,
    lock_snapshot_block,
    merkle_root_and_proofs,
    replay_balances,
    snapshot_ready,
)
from tools.season1.ops import build_rows


def cmd_manifest(args):
    doc = json.load(sys.stdin)
    locked = lock_snapshot_block(doc["headers"], doc["boundaryTs"])
    if locked is None:
        raise SystemExit("no block at or before the boundary")
    if not snapshot_ready(doc["head"], locked["number"], doc.get("confirmations", 15)):
        raise SystemExit("snapshot block does not have 15 confirmations; not falling back")
    balances = replay_balances(doc["points"], locked["number"])
    entries, reserved, remaining, stats = eligible_entries(
        balances, doc.get("orders", []),
        previously_qualified=doc.get("previouslyQualified"),
        random_seed=doc.get("randomSeed"))
    root, _proofs = merkle_root_and_proofs(entries)
    body, _raw, digest = canonical_manifest(
        doc["dayIndex"], doc["boundaryTs"], locked, doc.get("module"),
        entries, root, reserved, remaining,
        stats=stats, random_seed=doc.get("randomSeed"))
    body["manifestHash"] = digest
    json.dump(body, sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")


def cmd_check(args):
    doc = json.load(sys.stdin)
    verdict = check_scores(doc.get("expect") or {}, doc.get("observed"), rpc_error=bool(doc.get("rpcError")))
    json.dump({"verdict": verdict, "points": 0}, sys.stdout)
    sys.stdout.write("\n")


def _rpc_urls(env, indexer_env):
    urls = [u.strip() for u in (env.get("SEASON1_RPC_URL") or env.get("BSC_RPC_URLS") or "").split(",") if u.strip()]
    if urls:
        return urls
    if not indexer_env:
        raise SignRejected("no RPC configured")
    from indexer.common import load_env
    loaded = load_env(indexer_env)
    urls = [u.strip() for u in (loaded.get("BSC_RPC_URLS") or "").split(",") if u.strip()]
    if not urls:
        raise SignRejected("no RPC configured")
    return urls


def _signing_env(base, signer_env):
    env = dict(base)
    if signer_env:
        env["SEASON1_SIGNER_ENV"] = signer_env
    return env


def cmd_sign(args):
    import os
    from tools.season1.mainnet import DAILY_SIGNER, MODULE
    from tools.season1.sign_gate import authorize, eth_call_factory
    message = json.load(sys.stdin)
    try:
        env = _signing_env(os.environ, args.signer_env)
        eth_call = eth_call_factory(_rpc_urls(env, args.indexer_env))
        key, module, chain_id = authorize(env, eth_call, MODULE, DAILY_SIGNER)
        signed = sign_verify(key, message, chain_id, module, int(message["now"]),
                             allowed_signers=[DAILY_SIGNER])
    except SignRejected as exc:
        raise SystemExit(str(exc))
    json.dump({"signer": signed["signer"], "signature": signed["signature"]}, sys.stdout)
    sys.stdout.write("\n")


def cmd_signer_check(args):
    import os
    from eth_account import Account
    from tools.season1.eip712 import require_live_validator
    from tools.season1.mainnet import DAILY_SIGNER, MODULE
    from tools.season1.sign_gate import eth_call_factory
    from tools.season1.signer_env import load_matching_key
    env = _signing_env(os.environ, args.signer_env)
    try:
        if not env.get("SEASON1_SIGNER_ENV"):
            raise SignRejected("signer env path is required")
        key = load_matching_key(env["SEASON1_SIGNER_ENV"], DAILY_SIGNER)
        address = Account.from_key(key).address
        module = (env.get("SEASON1_MODULE") or MODULE).strip()
        if module.lower() != MODULE.lower():
            raise SignRejected("module is not the verified season1 address")
        eth_call = eth_call_factory(_rpc_urls(env, args.indexer_env))
        require_live_validator(eth_call, module, address)
        body = {
            "address": address,
            "addressMatch": address.lower() == DAILY_SIGNER.lower(),
            "validator": True,
            "signingEnabled": env.get("SEASON1_SIGNING") == "on",
            "module": MODULE,
        }
    except SignRejected as exc:
        json.dump({"ok": False, "error": str(exc), "signingEnabled": os.environ.get("SEASON1_SIGNING") == "on"}, sys.stdout)
        sys.stdout.write("\n")
        raise SystemExit(1)
    json.dump(body, sys.stdout)
    sys.stdout.write("\n")


def cmd_ops(args):
    doc = json.load(sys.stdin)
    def minted(order):
        return doc.get("minted", {}).get(str(order["orderId"]), False)
    rows = build_rows(doc["orders"], minted, lambda _order: [])
    json.dump(rows, sys.stdout)
    sys.stdout.write("\n")


def cmd_ops_serve(args):
    from tools.season1.ops_book import OpsBook
    from tools.season1.ops_server import serve
    orders = json.load(open(args.orders, encoding="utf-8")) if args.orders else []
    book = OpsBook(orders, state_path=args.state)
    print("ops panel http://127.0.0.1:%s/  (localhost only, wallet signs)" % args.port)
    serve(book, args.port)


def main():
    parser = argparse.ArgumentParser(prog="python3 -m tools.season1")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("manifest")
    sub.add_parser("check")
    sign = sub.add_parser("sign")
    sign.add_argument("--signer-env", default="")
    sign.add_argument("--indexer-env", default="")
    check_signer = sub.add_parser("signer-check")
    check_signer.add_argument("--signer-env", default="")
    check_signer.add_argument("--indexer-env", default="")
    sub.add_parser("ops")
    panel = sub.add_parser("ops-serve")
    panel.add_argument("--orders", default="")
    panel.add_argument("--state", default="")
    panel.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    {"manifest": cmd_manifest, "check": cmd_check, "sign": cmd_sign,
     "signer-check": cmd_signer_check, "ops": cmd_ops,
     "ops-serve": cmd_ops_serve}[args.cmd](args)


if __name__ == "__main__":
    main()
