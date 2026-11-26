"""Fail closed unless chain, module, signer, and a live validator read all agree."""

import json
import urllib.request

from eth_account import Account

from tools.season1.eip712 import SignRejected, require_live_validator
from tools.season1.mainnet import CHAIN_ID, DAILY_SIGNER, MODULE
from tools.season1.signer_env import load_matching_key


def authorize(env, eth_call, module, signer):
    """Return (key, module, chain_id) or raise SignRejected. Does not sign."""
    if env.get("SEASON1_SIGNING") != "on":
        raise SignRejected("signing disabled")
    try:
        chain_id = int(env.get("SEASON1_CHAIN_ID", str(CHAIN_ID)))
    except ValueError as exc:
        raise SignRejected("chain") from exc
    if chain_id != CHAIN_ID:
        raise SignRejected("chain must be 56")
    got_module = (env.get("SEASON1_MODULE") or "").strip()
    if got_module.lower() != module.lower():
        raise SignRejected("module is not the verified season1 address")
    # L4: the signing key comes ONLY from the SEASON1_SIGNER_ENV file
    # (0600, root; load_matching_key enforces the permissions and that
    # the key derives to the expected signer). The old plaintext
    # environment-variable fallback is deleted: it bypassed the
    # file-permission check and was visible to any process of the same
    # user via /proc/<pid>/environ.
    if env.get("SEASON1_SIGNER_ENV"):
        key = load_matching_key(env["SEASON1_SIGNER_ENV"], signer)
    else:
        raise SignRejected("no signing key configured: SEASON1_SIGNER_ENV is required")
    try:
        address = Account.from_key(key).address
    except Exception as exc:
        raise SignRejected("signer key is not usable") from exc
    if address.lower() != signer.lower():
        raise SignRejected("signer address mismatch")
    require_live_validator(eth_call, got_module, address)
    return key, got_module, chain_id


def production_targets():
    return MODULE, DAILY_SIGNER


def eth_call_factory(urls):
    """Build an eth_call(module, data) closure. URLs are not included in errors."""
    usable = [u.strip() for u in urls if u and u.strip()]
    if not usable:
        raise SignRejected("no RPC configured")

    def eth_call(module, data):
        body = json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "eth_call",
            "params": [{"to": module, "data": data}, "latest"],
        }).encode()
        last = None
        for url in usable:
            req = urllib.request.Request(
                url, data=body, headers={"content-type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=20) as res:
                    payload = json.loads(res.read().decode())
            except Exception as exc:
                last = exc
                continue
            if payload.get("error"):
                last = payload["error"]
                continue
            if "result" not in payload:
                last = "empty"
                continue
            return payload["result"]
        raise SignRejected("chain read failed") from (last if isinstance(last, Exception) else None)

    return eth_call
