"""Fulfill one day's frozen batch (adminMint + attestFulfillment).

Per Pending order, in order, one transaction at a time:
  1. isMinted(tokenId) must return a clean False. True means the name is
     already taken: stop this order, notify L, never auto-swap or
     auto-refund. A failed/unclear read also stops the row; never broadcast
     on an unknown state.
  2. tokenId must equal namehash(label, tld).
  3. Build adminMint calldata (tools.season1.ops) and simulate it with
     eth_call from the admin. A revert stops the row.
  4. Send adminMint. The receipt must contain BOTH NameMinted (tokenId,
     owner == recipient, label, tld, reservedMint == true) AND Transfer
     (from == 0, to == recipient, same tokenId), checked with
     tools.season1.ops.log_check on the normalized receipt logs.
  5. Only on a "matched" log check, call attestFulfillment(orderId,
     mintTxHash) and verify the FulfillmentAttested topic.

A mismatched receipt is an anomaly: no attestation, no success mark,
notify L. The indexer owns the order-status writes; this script only
reads the DB and writes its own JSON report.
"""

import json
import sys

sys.path.insert(0, "/opt/haha-season1")
sys.path.insert(0, "/opt/haha-indexer")
sys.path.insert(0, "/opt/haha-season1/admin")

import psycopg2
from admin_tx import (
    AdminTxError, encode_call, eth_call, load_admin_key, send_with_retry, _rpc,
)
from indexer.common import get_config
from tools.season1.constants import REGISTRAR
from tools.season1.hashutil import keccak256, namehash
from tools.season1.mainnet import MODULE
from tools.season1.ops import admin_mint_calldata, interpret_is_minted, log_check, OpsStopped
from tools.season1.ops_book import normalize_logs

ATTEST_SIG = "attestFulfillment(uint256,bytes32)"
FULFILL_ATTESTED_TOPIC = "0x" + keccak256(
    b"FulfillmentAttested(uint256,uint256,address,bytes32)").hex()
IS_MINTED_SEL = keccak256(b"isMinted(bytes32)")[:4].hex()


def is_minted(rpc, token_id):
    data = "0x" + IS_MINTED_SEL + ("%064x" % int(token_id))
    raw = rpc.call("eth_call", [{"to": REGISTRAR, "data": data}, "latest"])
    if not raw or raw == "0x":
        return None
    return int(raw, 16) != 0


def fulfill_day(day_index, deadline=None):
    """Fulfill one day's frozen batch. Each tx retries until confirmed or the deadline."""
    cfg = get_config()
    rpc = _rpc()
    key, address = load_admin_key()
    conn = psycopg2.connect(cfg["database_url"])
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT order_id, recipient, label, tld, token_id, status "
            "FROM season1_orders WHERE day_index = %s AND status = 'Pending' "
            "ORDER BY order_id",
            (int(day_index),),
        )
        orders = [{
            "orderId": int(r[0]), "recipient": "0x" + bytes(r[1]).hex(),
            "label": r[2], "tld": int(r[3]), "tokenId": int(r[4]), "status": r[5],
        } for r in cur.fetchall()]
    finally:
        conn.close()

    results = []
    for order in orders:
        row = {"orderId": order["orderId"], "label": order["label"],
               "tld": order["tld"], "recipient": order["recipient"]}
        try:
            minted = is_minted(rpc, order["tokenId"])
            verdict = interpret_is_minted(minted)
            if verdict == "name-taken":
                row.update({"ok": False, "action": "stop", "reason": "name-taken"})
                results.append(row)
                continue
            if int(order["tokenId"]) != namehash(order["label"], order["tld"]):
                row.update({"ok": False, "action": "stop", "reason": "tokenId is not the namehash"})
                results.append(row)
                continue
            data = admin_mint_calldata(order["label"], order["tld"], order["recipient"])
            # Simulate before broadcasting, as the admin (or adminMint
            # reverts on auth even when the real tx would pass).
            try:
                eth_call(rpc, REGISTRAR, data, "latest", from_address=address)
            except Exception as exc:
                row.update({"ok": False, "action": "stop", "reason": "adminMint simulation reverted",
                            "detail": str(exc)})
                results.append(row)
                continue
            tx_hash, receipt, attempts = send_with_retry(
                key, address, REGISTRAR, data, deadline=deadline)
            logs = normalize_logs(receipt.get("logs", []), tx_hash)
            check = log_check({**order, "mintTx": tx_hash}, logs)
            row["mintTx"] = tx_hash
            row["mintAttempts"] = attempts
            row["logCheck"] = check
            if check != "matched":
                row.update({"ok": False, "action": "stop",
                            "reason": "receipt logs did not match (no attestation)"})
                results.append(row)
                continue
            mint_tx_bytes = bytes.fromhex(tx_hash[2:])
            attest_data = encode_call(
                ATTEST_SIG, ["uint256", "bytes32"], [order["orderId"], mint_tx_bytes])
            attest_hash, attest_receipt, attest_attempts = send_with_retry(
                key, address, MODULE, attest_data,
                expect_topics=[FULFILL_ATTESTED_TOPIC], deadline=deadline)
            row.update({"ok": True, "action": "fulfilled",
                        "attestTx": attest_hash,
                        "attestAttempts": attest_attempts,
                        "attestBlock": int(attest_receipt.get("blockNumber", "0x0"), 16)})
            results.append(row)
        except (AdminTxError, OpsStopped) as exc:
            row.update({"ok": False, "action": "stop", "reason": str(exc)})
            results.append(row)
    return {"ok": True, "dayIndex": int(day_index), "orders": results,
            "fulfilled": sum(1 for r in results if r.get("ok")),
            "stopped": sum(1 for r in results if not r.get("ok"))}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", type=int, required=True)
    ap.add_argument("--deadline", type=float, default=None,
                    help="Unix timestamp; stop retrying after this time")
    args = ap.parse_args()
    try:
        result = fulfill_day(args.day, deadline=args.deadline)
    except AdminTxError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        sys.exit(2)
    print(json.dumps(result, indent=2))
    sys.exit(0)
