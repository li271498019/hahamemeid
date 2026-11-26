"""Publish a day's Merkle root on-chain (setDayRoot) with the admin key.

Gates (all must pass or nothing is sent):
  1. The snapshot report says precheck.ok is true.
  2. remainingBlocks > 0 (snapshot block + 256 not yet passed).
  3. The current head is still < snapshotBlock + 256 (re-checked live).
  4. No DayRootSet event exists yet for this dayIndex (idempotency: never
     publish the same day twice).
  5. An eth_call simulation of setDayRoot (from the admin) does not revert.

On success the receipt must contain the DayRootSet topic. Returns a
result dict with the tx hash. Never logs a private key.
"""

import json
import sys

sys.path.insert(0, "/opt/haha-season1")
sys.path.insert(0, "/opt/haha-indexer")
sys.path.insert(0, "/opt/haha-season1/admin")

from admin_tx import (
    AdminTxError, check_receipt, encode_call, eth_call, load_admin_key,
    send_with_retry, wait_receipt, _rpc,
)
from tools.season1.hashutil import keccak256
from tools.season1.mainnet import MODULE, DEPLOY_BLOCK

DAY_ROOT_SET_TOPIC = "0x" + keccak256(
    b"DayRootSet(uint64,bytes32,uint64,bytes32,uint16,uint16)").hex()
SET_DAY_ROOT_SIG = "setDayRoot(uint64,bytes32,uint64,bytes32,uint16,uint16)"


def day_root_already_set(rpc, day_index):
    """True if a DayRootSet event for this dayIndex is already on-chain."""
    topic_day = "0x" + day_index.to_bytes(32, "big").hex()
    logs = rpc.call("eth_getLogs", [{
        "fromBlock": hex(DEPLOY_BLOCK),
        "toBlock": "latest",
        "address": MODULE,
        "topics": [DAY_ROOT_SET_TOPIC, topic_day],
    }])
    return len(logs) > 0


def publish_root(report, deadline=None):
    """Send setDayRoot for the day described by a snapshot report dict.

    Retries until confirmed or the deadline (08:10 Beijing) passes.
    """
    if not report.get("ok") or not report.get("precheck", {}).get("ok"):
        raise AdminTxError("snapshot precheck is not ok; refusing to publish root")
    remaining = report.get("precheck", {}).get("remainingBlocks")
    if remaining is None or int(remaining) <= 0:
        raise AdminTxError("remainingBlocks <= 0; snapshot is stale, refusing to publish root")
    day_index = int(report["dayIndex"])
    snapshot_block = int(report["snapshotBlock"])
    root = report["root"]
    snapshot_hash = report["snapshotBlockHash"]
    reserved = int(report["reservedCount"])
    remaining_slots = int(report["remainingSlots"])

    key, address = load_admin_key()
    rpc = _rpc()

    # Live window re-check: head must still be < snapshotBlock + 256.
    head = int(rpc.call("eth_blockNumber", []), 16)
    if head >= snapshot_block + 256:
        raise AdminTxError(
            "head %d already >= snapshotBlock %d + 256; snapshot is stale"
            % (head, snapshot_block))

    # Idempotency: never publish the same day twice.
    if day_root_already_set(rpc, day_index):
        return {"ok": True, "skipped": True, "reason": "DayRootSet already on-chain",
                "dayIndex": day_index}

    data = encode_call(
        SET_DAY_ROOT_SIG,
        ["uint64", "bytes32", "uint64", "bytes32", "uint16", "uint16"],
        [day_index, bytes.fromhex(root[2:]), snapshot_block,
         bytes.fromhex(snapshot_hash[2:]), reserved, remaining_slots],
    )
    # Simulate once up front so a logic revert is reported immediately;
    # send_with_retry re-simulates before every attempt.
    # The simulation must run as the admin, or setDayRoot reverts on auth.
    try:
        eth_call(rpc, MODULE, data, "latest", from_address=address)
    except Exception as exc:
        raise AdminTxError("setDayRoot simulation reverted: %s" % exc) from exc

    tx_hash, receipt, attempts = send_with_retry(
        key, address, MODULE, data, expect_topics=[DAY_ROOT_SET_TOPIC],
        deadline=deadline)
    return {
        "ok": True,
        "dayIndex": day_index,
        "snapshotBlock": snapshot_block,
        "root": root,
        "txHash": tx_hash,
        "attempts": attempts,
        "blockNumber": int(receipt.get("blockNumber", "0x0"), 16),
        "headAtSend": head,
        "remainingBlocksAtSend": int(remaining),
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True, help="snapshot report JSON path")
    ap.add_argument("--deadline", type=float, default=None,
                    help="Unix timestamp; stop retrying after this time")
    args = ap.parse_args()
    with open(args.report, encoding="utf-8") as f:
        report = json.load(f)
    try:
        result = publish_root(report, deadline=args.deadline)
    except AdminTxError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        sys.exit(2)
    print(json.dumps(result, indent=2))
    sys.exit(0)
