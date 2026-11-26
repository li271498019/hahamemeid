"""Publish a day's task pack hash on-chain (setTaskPack) with the admin key.

Gates:
  1. The task pack file exists and its hash matches the given hash.
  2. If taskPack(dayIndex) already equals the hash, skip (idempotent).
  3. If a different hash is already set and verifiedCount(dayIndex) > 0,
     refuse (the pack is frozen once anyone has claimed that day).
  4. An eth_call simulation of setTaskPack (from the admin) does not revert.

On success the receipt must contain the TaskPackSet topic.
"""

import json
import sys

sys.path.insert(0, "/opt/haha-season1")
sys.path.insert(0, "/opt/haha-indexer")
sys.path.insert(0, "/opt/haha-season1/admin")

from admin_tx import (
    AdminTxError, encode_call, eth_call, load_admin_key, send_with_retry, _rpc,
)
from tools.season1.hashutil import keccak256
from tools.season1.mainnet import MODULE

TASK_PACK_SET_TOPIC = "0x" + keccak256(b"TaskPackSet(uint64,bytes32)").hex()
SET_TASK_PACK_SIG = "setTaskPack(uint64,bytes32)"
TASK_PACK_SEL = keccak256(b"taskPack(uint64)")[:4].hex()
VERIFIED_COUNT_SEL = keccak256(b"verifiedCount(uint64)")[:4].hex()


def _read_u256(rpc, to, selector_hex, arg):
    data = "0x" + selector_hex + ("%064x" % int(arg))
    raw = rpc.call("eth_call", [{"to": to, "data": data}, "latest"])
    if not raw or raw == "0x":
        return None
    return int(raw, 16)


def _read_bytes32(rpc, to, selector_hex, arg):
    data = "0x" + selector_hex + ("%064x" % int(arg))
    raw = rpc.call("eth_call", [{"to": to, "data": data}, "latest"])
    if not raw or raw == "0x":
        return None
    return "0x" + raw[2:].rjust(64, "0")[-64:]


def publish_taskpack(day_index, task_pack_hash, taskpack_file=None, deadline=None):
    """Publish a day's task pack hash. Retries until confirmed or the deadline."""
    if taskpack_file:
        with open(taskpack_file, "rb") as f:
            raw = f.read()
        file_hash = "0x" + keccak256(raw).hex()
        if file_hash.lower() != task_pack_hash.lower():
            raise AdminTxError(
                "task pack file hash %s does not match given hash %s"
                % (file_hash, task_pack_hash))
    day_index = int(day_index)
    rpc = _rpc()
    current = _read_bytes32(rpc, MODULE, TASK_PACK_SEL, day_index)
    if current and current.lower() == task_pack_hash.lower():
        return {"ok": True, "skipped": True,
                "reason": "taskPack already set to this hash", "dayIndex": day_index}
    if current and current != "0x" + "00" * 32:
        claimed = _read_u256(rpc, MODULE, VERIFIED_COUNT_SEL, day_index)
        if claimed and claimed > 0:
            raise AdminTxError(
                "taskPack for day %d is frozen (%d already verified); refusing to overwrite"
                % (day_index, claimed))
    key, address = load_admin_key()
    data = encode_call(
        SET_TASK_PACK_SIG,
        ["uint64", "bytes32"],
        [day_index, bytes.fromhex(task_pack_hash[2:])],
    )
    # The simulation must run as the admin, or setTaskPack reverts on auth.
    try:
        eth_call(rpc, MODULE, data, "latest", from_address=address)
    except Exception as exc:
        raise AdminTxError("setTaskPack simulation reverted: %s" % exc) from exc
    tx_hash, receipt, attempts = send_with_retry(
        key, address, MODULE, data, expect_topics=[TASK_PACK_SET_TOPIC],
        deadline=deadline)
    return {
        "ok": True,
        "dayIndex": day_index,
        "taskPackHash": task_pack_hash,
        "txHash": tx_hash,
        "attempts": attempts,
        "blockNumber": int(receipt.get("blockNumber", "0x0"), 16),
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", type=int, required=True)
    ap.add_argument("--hash", required=True)
    ap.add_argument("--file", default=None)
    ap.add_argument("--deadline", type=float, default=None,
                    help="Unix timestamp; stop retrying after this time")
    args = ap.parse_args()
    try:
        result = publish_taskpack(args.day, args.hash, args.file, deadline=args.deadline)
    except AdminTxError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        sys.exit(2)
    print(json.dumps(result, indent=2))
    sys.exit(0)
