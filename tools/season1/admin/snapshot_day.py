"""Generalized day snapshot for haha.meme Season 1 (any dayIndex).

Same pipeline as snapshot-day1.py, parameterized by dayIndex and the
day-boundary timestamp (UTC 00:00 = Beijing 08:00):
  1. Find snapshot block B = last block with timestamp <= boundary_ts.
  2. Wait until head >= B + 15 (15 confirmations).
  3. Replay PointsChanged logs from the indexer DB up to B.
  4. Compute the Merkle root + canonical manifest (tools.season1.merkle).
  5. Run root_publish_precheck(head, B).
  6. Write manifest-day{dayIndex}.json + report-day{dayIndex}.json.

Does NOT call setDayRoot and does NOT open any switch. The caller
(publish_root / daily_ops) decides whether to sign, and only when
precheck.ok is true and remainingBlocks > 0.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, "/opt/haha-season1")
sys.path.insert(0, "/opt/haha-indexer")

import psycopg2
from indexer.common import RpcClient, get_config
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
from tools.season1.mainnet import MODULE

POINTS_DEPLOY_BLOCK = 134834780
# topic0 of HahaPoints.PointsChanged(bytes32,address,int256,uint256,bytes32).
# keccak256("PointsChanged(bytes32,address,int256,uint256,bytes32)") — verified
# against src/HahaPoints.sol. Only this event carries (aiId, newBalance);
# other events from the same contract (Earned, EarnerUpdated, SpenderUpdated,
# SpenderBudgetUpdated) reuse topics[1]/data[32:64] for other fields, and
# replaying them produced 3 fake snapshot entries on day 20781 (aiIds
# "ACTIVATE", "REVIEW_RECEIVE" and the module address, with huge fake
# balances). Filter by topic0 so only PointsChanged is replayed.
POINTS_CHANGED_TOPIC = "0x64914efa3ac0dbc26f5227c1431c633c06a6cc9c6fe7f4020a3f67067e8853ca"
CONFIRMATIONS = 15
OUTDIR_BASE = "/opt/haha-season1/day-snapshots"
MAX_WAIT_SECONDS = 600


def rpc_block(rpc, number):
    return rpc.call("eth_getBlockByNumber", [hex(number), False])


def find_snapshot_block(rpc, boundary_ts):
    """Last block with timestamp <= boundary_ts (binary search)."""
    head = int(rpc.call("eth_blockNumber", []), 16)
    head_blk = rpc_block(rpc, head)
    if int(head_blk["timestamp"], 16) <= boundary_ts:
        return {"number": head, "hash": head_blk["hash"],
                "timestamp": int(head_blk["timestamp"], 16)}
    lo, hi = 0, head
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        blk = rpc_block(rpc, mid)
        if int(blk["timestamp"], 16) <= boundary_ts:
            lo = mid
        else:
            hi = mid
    blk = rpc_block(rpc, lo)
    return {"number": lo, "hash": blk["hash"], "timestamp": int(blk["timestamp"], 16)}


def fetch_points_logs(conn, snapshot_block):
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
        if len(topics) < 2:
            continue
        # Only PointsChanged carries (aiId, newBalance). Other events from
        # the Points contract must not be replayed as balance changes.
        t0 = topics[0]
        t0_hex = t0.lower() if isinstance(t0, str) else "0x" + bytes(t0).hex().lower()
        if t0_hex != POINTS_CHANGED_TOPIC:
            continue
        t1 = topics[1]
        ai_id = t1 if isinstance(t1, str) and t1.startswith("0x") else "0x" + bytes(t1).hex()
        raw = bytes(data)
        new_balance = int.from_bytes(raw[32:64], "big")
        logs.append({"block": block, "logIndex": log_index, "aiId": ai_id, "newBalance": new_balance})
    return logs


def fetch_orders(conn):
    cur = conn.cursor()
    cur.execute("SELECT ai_id, status FROM season1_orders")
    return [{"aiId": "0x" + row[0].hex(), "status": row[1]} for row in cur.fetchall()]


def fetch_previously_qualified(conn, day_index):
    """aiIds that were in a previous day's snapshot entries (day_index < today).

    These are the "expired" aiIds: they qualified on an earlier day but have
    no order (they did not apply). They are excluded from primary selection
    on this day; they only fill randomly when the fresh pool is short of
    DAILY_MAX. The caller (eligible_entries) still drops anyone with a
    blocking order, so this set is intersected with the live pool there.
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT ai_id FROM season1_entries WHERE day_index < %s",
        (int(day_index),))
    return ["0x" + row[0].hex() for row in cur.fetchall()]


def store_entries(conn, day_index, entries, proofs):
    """Insert/update the eligible entries + Merkle proofs for one day.

    Idempotent: re-running a snapshot for the same day replaces the rows.
    """
    cur = conn.cursor()
    for row in entries:
        ai = row["aiId"]
        proof = proofs.get(ai, [])
        cur.execute(
            "INSERT INTO season1_entries (day_index, ai_id, balance, tier, proof)"
            " VALUES (%s, %s, %s, %s, %s::jsonb)"
            " ON CONFLICT (day_index, ai_id) DO UPDATE SET"
            " balance = EXCLUDED.balance, tier = EXCLUDED.tier, proof = EXCLUDED.proof",
            (int(day_index), bytes.fromhex(ai[2:]), int(row["balance"]),
             int(row["tier"]), json.dumps(proof)),
        )
    conn.commit()


def run_snapshot(day_index, boundary_ts, outdir=None):
    """Run the full snapshot for one day. Returns the report dict."""
    outdir = outdir or os.path.join(OUTDIR_BASE, "day%d" % day_index)
    started = time.time()
    cfg = get_config()
    rpc = RpcClient(cfg["rpc_urls"])
    conn = psycopg2.connect(cfg["database_url"])
    try:
        snapshot = None
        while time.time() - started < MAX_WAIT_SECONDS:
            try:
                snapshot = find_snapshot_block(rpc, boundary_ts)
                break
            except RuntimeError:
                time.sleep(3)
        if snapshot is None:
            return {"ok": False, "error": "snapshot block not found within timeout"}
        head = None
        while time.time() - started < MAX_WAIT_SECONDS:
            head = int(rpc.call("eth_blockNumber", []), 16)
            if snapshot_ready(head, snapshot["number"], CONFIRMATIONS):
                break
            time.sleep(3)
        if head is None or not snapshot_ready(head, snapshot["number"], CONFIRMATIONS):
            return {"ok": False, "error": "15 confirmations not reached within timeout",
                    "snapshotBlock": snapshot["number"], "head": head}
        points_logs = fetch_points_logs(conn, snapshot["number"])
        orders = fetch_orders(conn)
        previously_qualified = fetch_previously_qualified(conn, day_index)
        balances = replay_balances(points_logs, snapshot["number"])
        # v2 rotation rule: the random fill is seeded by the snapshot block
        # hash (public, on-chain), so anyone can reproduce the draw.
        random_seed = snapshot["hash"]
        entries, reserved, remaining, stats = eligible_entries(
            balances, orders,
            previously_qualified=previously_qualified,
            random_seed=random_seed)
        root, proofs = merkle_root_and_proofs(entries)
        headers = [{"number": snapshot["number"], "timestamp": snapshot["timestamp"], "hash": snapshot["hash"]}]
        locked = lock_snapshot_block(headers, boundary_ts)
        body, _raw, digest = canonical_manifest(
            day_index, boundary_ts, locked, MODULE, entries, root, reserved, remaining,
            stats=stats, random_seed=random_seed)
        body["manifestHash"] = digest
        precheck = root_publish_precheck(head, snapshot["number"], CONFIRMATIONS)
        os.makedirs(outdir, exist_ok=True)
        with open(os.path.join(outdir, "manifest-day%d.json" % day_index), "w", encoding="utf-8") as f:
            json.dump(body, f, separators=(",", ":"))
            f.write("\n")
        # Store entries + proofs in the DB so the indexer can serve the
        # proof (GET /v1/season1/proof/{aiId}) and eligibility. The proof
        # comes from the same tree that produced this root, so it matches
        # the manifest by construction.
        store_entries(conn, day_index, entries, proofs)
        report = {
            "ok": bool(precheck["ok"]),
            "dayIndex": day_index,
            "boundaryTs": boundary_ts,
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
            "freshCount": stats["freshCount"],
            "expiredCount": stats["expiredCount"],
            "randomFilled": stats["randomFilled"],
            "randomSeed": random_seed,
            "previouslyQualified": len(previously_qualified),
            "pointsLogsReplayed": len(points_logs),
            "ordersExcluded": len(orders),
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "outdir": outdir,
        }
        with open(os.path.join(outdir, "report-day%d.json" % day_index), "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        return report
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", type=int, required=True)
    ap.add_argument("--boundary-ts", type=int, required=True)
    ap.add_argument("--outdir", default=None)
    args = ap.parse_args()
    report = run_snapshot(args.day, args.boundary_ts, args.outdir)
    print(json.dumps(report, indent=2))
    sys.exit(0 if report.get("ok") else 2)
