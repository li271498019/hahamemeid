"""Haha Dog one-time backfill.

The syncer only reads forward from its checkpoint, so once HahaDog and
HahaDogMarket are added to log_addresses() it would miss everything between
DOG_START_BLOCK and the checkpoint. This script fetches those logs, stores them
in raw_logs/blocks and rebuilds the dog_* tables from ALL dog logs in raw_logs.

Order of operations on the server (see INDEXER-PLAN.md):
  1. deploy the new code, do NOT restart yet
  2. systemctl stop haha-indexer           (checkpoint is now frozen)
  3. python3 dog_backfill.py --dry-run     (shows the range and log counts)
  4. python3 dog_backfill.py               (does it)
  5. systemctl start haha-indexer; systemctl restart haha-api

Safe to run again: raw_logs inserts are ON CONFLICT DO NOTHING and the dog_*
tables are rebuilt from scratch in one transaction. It refuses to commit if the
checkpoint moved while it ran (the syncer was still running).

Usage: python3 dog_backfill.py [--env /etc/haha/indexer.env] [--dry-run]
"""

import argparse
import datetime
import os
import sys

import psycopg2
import psycopg2.extras

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (CHAIN_ID, DOG_ADDRESSES, DOG_START_BLOCK, MAX_RANGE, MIN_RANGE,
                    RpcClient, RpcError, decode_log, get_config)
from dog_store import DOG_TABLES, apply_dog_event, h2b, resolve_seeds


def log(*a):
    print(datetime.datetime.now(datetime.timezone.utc).isoformat(), "[dog-backfill]", *a, flush=True)


def fetch_logs(rpc, start, end):
    out, rng, nxt = [], MAX_RANGE, start
    while nxt <= end:
        to = min(nxt + rng - 1, end)
        try:
            part = rpc.get_logs(nxt, to, DOG_ADDRESSES)
        except RpcError as e:
            if e.range_too_large and rng > MIN_RANGE:
                rng = max(MIN_RANGE, rng // 2)
                log("range too large, halving to", rng)
                continue
            raise
        out.extend(l for l in part if not l.get("removed"))
        nxt = to + 1
        rng = min(MAX_RANGE, rng + 250)
    out.sort(key=lambda l: (int(l["blockNumber"], 16), int(l["transactionIndex"], 16),
                            int(l["logIndex"], 16)))
    return out


def checkpoint(cur):
    cur.execute("SELECT safe_block FROM checkpoint WHERE id = 1")
    row = cur.fetchone()
    return row[0] if row else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    cfg = get_config(args.env)
    if not cfg["database_url"] or not cfg["rpc_urls"]:
        log("FATAL: DATABASE_URL / BSC_RPC_URLS missing in", cfg["env_path"])
        return 2
    rpc = RpcClient(cfg["rpc_urls"])
    conn = psycopg2.connect(cfg["database_url"])
    conn.autocommit = False
    with conn.cursor() as cur:
        start_cp = checkpoint(cur)
    conn.rollback()
    if start_cp is None:
        log("FATAL: no checkpoint yet; start the syncer once first")
        return 2
    if start_cp < DOG_START_BLOCK:
        log("checkpoint", start_cp, "is before the dog start block; nothing to backfill,"
            " the syncer will see the dog logs itself")
        return 0
    log("range", DOG_START_BLOCK, "..", start_cp)
    logs = fetch_logs(rpc, DOG_START_BLOCK, start_cp)
    log("fetched", len(logs), "dog logs")
    if args.dry_run:
        return 0
    want = sorted({int(l["blockNumber"], 16) for l in logs})
    headers = {bn: rpc.get_block(bn) for bn in want}
    with conn.cursor() as cur:
        # Block the syncer's raw_logs inserts while we rebuild, and re-check the checkpoint.
        cur.execute("LOCK TABLE raw_logs IN SHARE ROW EXCLUSIVE MODE")
        if checkpoint(cur) != start_cp:
            conn.rollback()
            log("ABORT: checkpoint moved; stop haha-indexer first and run again")
            return 3
        # Ensure the dog tables exist (first run after deploy): schema.sql is
        # idempotent (CREATE TABLE IF NOT EXISTS), so this is safe to repeat.
        # Without it the TRUNCATE below fails with relation "dogs" does not exist.
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")) as f:
            cur.execute(f.read())
        for bn, h in headers.items():
            cur.execute("SELECT hash FROM blocks WHERE block_number = %s", (bn,))
            row = cur.fetchone()
            if row is not None and bytes(row[0]) != h2b(h["hash"]):
                conn.rollback()
                log("ABORT: stored block", bn, "has a different hash (reorg?)")
                return 3
            cur.execute("INSERT INTO blocks (block_number, hash, parent_hash) VALUES (%s, %s, %s)"
                        " ON CONFLICT (block_number) DO NOTHING",
                        (bn, h2b(h["hash"]), h2b(h["parentHash"])))
        for l in logs:
            bn = int(l["blockNumber"], 16)
            bt = datetime.datetime.fromtimestamp(int(headers[bn]["timestamp"], 16), datetime.timezone.utc)
            cur.execute(
                "INSERT INTO raw_logs (chain_id, block_number, block_hash, block_time, tx_hash,"
                " tx_index, log_index, address, topic0, topics, data)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                " ON CONFLICT (chain_id, block_number, tx_index, log_index) DO NOTHING",
                (CHAIN_ID, bn, h2b(l["blockHash"]), bt, h2b(l["transactionHash"]),
                 int(l["transactionIndex"], 16), int(l["logIndex"], 16), h2b(l["address"]),
                 h2b(l["topics"][0]), psycopg2.extras.Json([t.lower() for t in l["topics"]]),
                 h2b(l["data"])))
        for t in DOG_TABLES:
            cur.execute("TRUNCATE %s" % t)
        cur.execute(
            "SELECT block_number, block_time, tx_hash, tx_index, log_index, address, topics, data"
            " FROM raw_logs WHERE address = ANY(%s) ORDER BY block_number, tx_index, log_index",
            ([h2b(a) for a in DOG_ADDRESSES],))
        rows = cur.fetchall()
        for bn, bt, txh, txi, li, addr, topics, data in rows:
            a = "0x" + bytes(addr).hex()
            event, p = decode_log(a, topics, bytes(data))
            if event is not None:
                apply_dog_event(cur, a, event, p, (bn, bt, bytes(txh), txi, li))
    conn.commit()
    log("rebuilt dog tables from", len(rows), "raw logs")
    n = resolve_seeds(conn, rpc, start_cp, log)
    log("seeds resolved:", n)
    with conn.cursor() as cur:
        cur.execute("SELECT (SELECT COUNT(*) FROM dogs), (SELECT COUNT(*) FROM dog_listings),"
                    " (SELECT COUNT(*) FROM dog_trades), (SELECT COUNT(*) FROM dog_snapshots)")
        log("dogs / listings / trades / snapshots:", cur.fetchone())
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
