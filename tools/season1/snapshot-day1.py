#!/usr/bin/env python3
"""First-day snapshot for haha.meme Season 1 (dayIndex 20781).

Runs at the 2026-11-24 08:00 Beijing day boundary. It:
  1. Finds the snapshot block B = last block with timestamp <= 1795478400.
  2. Waits until head >= B + 15 (15 confirmations).
  3. Replays PointsChanged logs from the indexer DB up to B.
  4. Computes the Merkle root + canonical manifest (tools.season1.merkle).
  5. Runs root_publish_precheck(head, B).
  6. Writes the manifest + report to /opt/haha-season1/day1-snapshot/.

It does NOT call setDayRoot and does NOT open any switch. L signs setDayRoot
with the admin wallet after reading this report. The setDayRoot transaction
must be mined while block.number < B + 256 (StaleSnapshot). If the precheck
is not ok, or remainingBlocks <= 0, do NOT sign; do NOT fall back to an
earlier snapshot block.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, "/opt/haha-season1")
sys.path.insert(0, "/opt/haha-indexer")

import psycopg2
from indexer.common import RpcClient, get_config, load_env
from tools.season1.merkle import (
    canonical_manifest,
    eligible_entries,
    lock_snapshot_block,
    merkle_root_and_proofs,
    replay_balances,
    root_publish_precheck,
    snapshot_ready,
)
from tools.season1.constants import POINTS

BOUNDARY_TS = 1795478400
DAY_INDEX = 20781
MODULE = "0x4B8a35bFe18750c2058fd01e7159728adD345C00"
POINTS_DEPLOY_BLOCK = 134834780
CONFIRMATIONS = 15
OUTDIR = "/opt/haha-season1/day1-snapshot"
MAX_WAIT_SECONDS = 600  # 10 minutes of polling; still inside the 256-block window


def rpc_block(rpc, number):
    return rpc.call("eth_getBlockByNumber", [hex(number), False])


def find_snapshot_block(rpc):
    """Return the last block with timestamp <= BOUNDARY_TS (binary search).

    BSC block timestamps are non-decreasing, so a binary search over
    [0, head] finds the boundary block in ~27 RPC calls. No linear walk-back.
    """
    head = int(rpc.call("eth_blockNumber", []), 16)
    # If even the head is at or before the boundary, the snapshot is the head.
    head_blk = rpc_block(rpc, head)
    if int(head_blk["timestamp"], 16) <= BOUNDARY_TS:
        return {"number": head, "hash": head_blk["hash"],
                "timestamp": int(head_blk["timestamp"], 16)}
    lo, hi = 0, head
    # Invariant: block(lo).timestamp <= boundary < block(hi).timestamp.
    # lo starts at 0 (genesis timestamp 0 <= boundary); hi is the head.
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        blk = rpc_block(rpc, mid)
        if int(blk["timestamp"], 16) <= BOUNDARY_TS:
            lo = mid
        else:
            hi = mid
    blk = rpc_block(rpc, lo)
    return {"number": lo, "hash": blk["hash"], "timestamp": int(blk["timestamp"], 16)}


def fetch_points_logs(conn, snapshot_block):
    """PointsChanged logs (block, logIndex, aiId, newBalance) up to snapshot_block."""
    cur = conn.cursor()
    cur.execute(
        "SELECT block_number, log_index, topics, data FROM raw_logs "
        "WHERE address = %s AND block_number <= %s "
        "ORDER BY block_number, log_index",
        (bytes.fromhex(POINTS[2:]), snapshot_block),
    )
    rows = cur.fetchall()
    logs = []
    for block, log_index, topics, data in rows:
        # topics come back from psycopg2 as a JSON list of hex strings
        # ("0x..."); topics[1] = aiId; data word 1 = newBalance.
        if len(topics) < 2:
            continue
        t1 = topics[1]
        ai_id = t1 if isinstance(t1, str) and t1.startswith("0x") else "0x" + bytes(t1).hex()
        # data is bytea -> bytes: word0 = delta (int256), word1 = newBalance (uint256).
        raw = bytes(data)
        new_balance = int.from_bytes(raw[32:64], "big")
        logs.append({"block": block, "logIndex": log_index, "aiId": ai_id, "newBalance": new_balance})
    return logs


def fetch_orders(conn):
    cur = conn.cursor()
    cur.execute("SELECT ai_id, status FROM season1_orders")
    return [{"aiId": "0x" + row[0].hex(), "status": row[1]} for row in cur.fetchall()]


def main():
    started = time.time()
    cfg = get_config()
    rpc = RpcClient(cfg["rpc_urls"])
    conn = psycopg2.connect(cfg["database_url"])
    try:
        # 1. Find the snapshot block (poll until the chain passes the boundary).
        snapshot = None
        while time.time() - started < MAX_WAIT_SECONDS:
            try:
                snapshot = find_snapshot_block(rpc)
                break
            except RuntimeError:
                time.sleep(3)
        if snapshot is None:
            print(json.dumps({"ok": False, "error": "snapshot block not found within timeout"}))
            return 2
        # 2. Wait for 15 confirmations.
        head = None
        while time.time() - started < MAX_WAIT_SECONDS:
            head_hex = rpc.call("eth_blockNumber", [])
            head = int(head_hex, 16)
            if snapshot_ready(head, snapshot["number"], CONFIRMATIONS):
                break
            time.sleep(3)
        if head is None or not snapshot_ready(head, snapshot["number"], CONFIRMATIONS):
            print(json.dumps({"ok": False, "error": "15 confirmations not reached within timeout",
                              "snapshotBlock": snapshot["number"], "head": head}))
            return 2
        # 3. Replay balances + eligibility + root.
        points_logs = fetch_points_logs(conn, snapshot["number"])
        orders = fetch_orders(conn)
        balances = replay_balances(points_logs, snapshot["number"])
        entries, reserved, remaining = eligible_entries(balances, orders)
        root, _proofs = merkle_root_and_proofs(entries)
        headers = [{"number": snapshot["number"], "timestamp": snapshot["timestamp"], "hash": snapshot["hash"]}]
        locked = lock_snapshot_block(headers, BOUNDARY_TS)
        body, _raw, digest = canonical_manifest(
            DAY_INDEX, BOUNDARY_TS, locked, MODULE, entries, root, reserved, remaining)
        body["manifestHash"] = digest
        # 4. Precheck.
        precheck = root_publish_precheck(head, snapshot["number"], CONFIRMATIONS)
        # 5. Write outputs.
        os.makedirs(OUTDIR, exist_ok=True)
        with open(os.path.join(OUTDIR, "manifest-day20781.json"), "w", encoding="utf-8") as f:
            json.dump(body, f, separators=(",", ":"))
            f.write("\n")
        report = {
            "ok": bool(precheck["ok"]),
            "dayIndex": DAY_INDEX,
            "boundaryTs": BOUNDARY_TS,
            "snapshotBlock": snapshot["number"],
            "snapshotBlockHash": snapshot["hash"],
            "snapshotTimestamp": snapshot["timestamp"],
            "head": head,
            "confirmations": CONFIRMATIONS,
            "precheck": precheck,
            "root": root,
            "manifestHash": digest,
            "reservedCount": reserved,
            "remainingSlots": remaining,
            "entryCount": len(entries),
            "pointsLogsReplayed": len(points_logs),
            "ordersExcluded": len(orders),
            "generatedAt": datetime.now(timezone.utc).isoformat(),
        }
        with open(os.path.join(OUTDIR, "report-day20781.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(json.dumps(report, indent=2))
        return 0 if precheck["ok"] else 2
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
