"""Backfill HahaSeason1 logs without moving the global checkpoint.

The syncer only reads addresses in its allow-list, and only forward from
checkpoint. If SEASON1_MODULE was empty while the cursor passed the deploy
block, those logs were never stored. Replaying the whole checkpoint would
also replay Points logs and can overwrite a newer balance with an older one.
This tool inserts and applies only the module address, from the verified
deploy block through the current checkpoint, then commits. It does not
change checkpoint.

Run from the indexer directory after the code update, with the indexer
stopped:

    python3 season1_backfill.py

The deploy block and module below are the values verified on BSC. They are
duplicated in tools/season1/mainnet.py because this process does not import
that package on the server.
"""

import datetime
import json
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from common import CHAIN_ID, EVENTS, RpcClient, RpcError, decode_log, get_config
from season1_store import bind_module
from syncer import apply_log, h2b

MODULE = "0x4b8a35bfe18750c2058fd01e7159728add345c00"
DEPLOY_BLOCK = 135231506
DEPLOY_BLOCK_HASH = "0xd0c1080ee303a2bcbb74cf64308c8beba7f4287b0ec86ffeac80d7c1156bcfa6"
# Receipts re-read on BSC. The deploy receipt itself has zero logs.
ANCHORS = (
    {
        "event": "ValidatorSet",
        "txHash": "0x3c10db324213a5e21625d71b0eb04058bb1fb78af9bfa9bbf6a5f64f9f2ad743",
        "block": 135233318,
        "logIndex": 218,
        "topic0": "0x6b3b7d0d26ec99d080840dca1323c7147d1868adc66a4290afb8101d7908320d",
    },
    {
        "event": "RewardSignerSet",
        "txHash": "0x21880599387bb198ffc3dc7a32beb67536f7c4a82e815e10b5be1a07d466b80f",
        "block": 135233378,
        "logIndex": 251,
        "topic0": "0x073ffd8bf24fd95cb2eb5bab8db507b06961fbc31ed400a0f3c8fff8fb9045ba",
    },
)


def log_identity(row):
    return {
        "block": int(row["blockNumber"], 16),
        "txHash": str(row.get("transactionHash", "")).lower(),
        "logIndex": int(row["logIndex"], 16),
        "address": str(row.get("address", "")).lower(),
        "topic0": str((row.get("topics") or [""])[0]).lower(),
    }


def missing_anchors(logs, anchors=ANCHORS):
    """Return anchor events whose tx hash is absent. Empty means the minimum set is present."""
    found = {str(row.get("transactionHash", "")).lower() for row in logs}
    return [row["event"] for row in anchors if row["txHash"] not in found]


def plan(safe_block, deploy_block=DEPLOY_BLOCK):
    if safe_block is None:
        return {"action": "wait-for-sync", "reason": "no-checkpoint"}
    safe_block = int(safe_block)
    if safe_block < deploy_block:
        return {
            "action": "wait-for-sync",
            "reason": "cursor-before-deploy",
            "safeBlock": safe_block,
            "deployBlock": deploy_block,
        }
    return {
        "action": "backfill",
        "from": deploy_block,
        "to": safe_block,
    }


def apply_sql_files(cur):
    names = [
        "schema.sql",
        "migrations/003_season1.sql",
        "migrations/004_season1_signers.sql",
    ]
    applied = []
    for name in names:
        path = HERE / name
        if path.is_file():
            cur.execute(path.read_text(encoding="utf-8"))
            applied.append(name)
    return applied


def write_module_logs(cur, module, logs, headers):
    """Insert and apply one module's logs. Does not read or write checkpoint."""
    module = module.lower()
    bind_module(module, EVENTS)
    kept = []
    for row in logs:
        if row.get("removed"):
            continue
        if str(row.get("address", "")).lower() != module:
            continue
        kept.append(row)
    kept.sort(key=lambda row: (
        int(row["blockNumber"], 16),
        int(row["transactionIndex"], 16),
        int(row["logIndex"], 16),
    ))
    counts = {"ValidatorSet": 0, "RewardSignerSet": 0, "other": 0, "undecoded": 0}
    for row in kept:
        block = int(row["blockNumber"], 16)
        header = headers[block]
        if header["hash"].lower() != row["blockHash"].lower():
            raise RuntimeError("log block hash disagrees with the header")
        when = datetime.datetime.fromtimestamp(
            int(header["timestamp"], 16), datetime.timezone.utc)
        cur.execute(
            "INSERT INTO raw_logs (chain_id, block_number, block_hash,"
            " block_time, tx_hash, tx_index, log_index, address, topic0,"
            " topics, data) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,"
            " %s, %s) ON CONFLICT (chain_id, block_number, tx_index,"
            " log_index) DO NOTHING",
            (CHAIN_ID, block, h2b(row["blockHash"]), when,
             h2b(row["transactionHash"]), int(row["transactionIndex"], 16),
             int(row["logIndex"], 16), h2b(row["address"]),
             h2b(row["topics"][0]),
             psycopg2.extras.Json([topic.lower() for topic in row["topics"]]),
             h2b(row["data"])))
        event, params = decode_log(row["address"], row["topics"], h2b(row["data"]))
        if event is None:
            counts["undecoded"] += 1
            continue
        apply_log(cur, row["address"].lower(), event, params,
                  (block, when, h2b(row["transactionHash"]),
                   int(row["transactionIndex"], 16), int(row["logIndex"], 16)),
                  None)
        if event in ("ValidatorSet", "RewardSignerSet"):
            counts[event] += 1
        else:
            counts["other"] += 1
    return counts


def fetch_logs(rpc, module, start, end):
    size = 2000
    found = []
    cursor = start
    while cursor <= end:
        stop = min(cursor + size - 1, end)
        try:
            batch = rpc.call("eth_getLogs", [{
                "fromBlock": hex(cursor),
                "toBlock": hex(stop),
                "address": module,
            }])
        except RpcError as exc:
            if exc.range_too_large and size > 50:
                size = max(50, size // 2)
                continue
            raise
        found.extend(batch or [])
        cursor = stop + 1
    return found


def readback(cur):
    cur.execute("SELECT safe_block FROM checkpoint WHERE id = 1")
    checkpoint = cur.fetchone()
    cur.execute(
        "SELECT encode(account, 'hex'), allowed, block_number, log_index"
        " FROM season1_validators ORDER BY block_number, log_index")
    validators = [
        {"account": "0x" + account, "allowed": allowed, "block": block, "logIndex": index}
        for account, allowed, block, index in cur.fetchall()
    ]
    cur.execute(
        "SELECT encode(account, 'hex'), block_number, log_index"
        " FROM season1_reward_signer ORDER BY block_number, log_index")
    signers = [
        {"account": "0x" + account, "block": block, "logIndex": index}
        for account, block, index in cur.fetchall()
    ]
    cur.execute(
        "SELECT block_number, log_index, encode(tx_hash, 'hex'), encode(topic0, 'hex')"
        " FROM raw_logs WHERE address = %s ORDER BY block_number, log_index",
        (h2b(MODULE),))
    raw = [
        {"block": block, "logIndex": index, "txHash": "0x" + tx, "topic0": "0x" + topic}
        for block, index, tx, topic in cur.fetchall()
    ]
    counts = {}
    for table in (
        "season1_days", "season1_orders", "season1_verifications",
        "season1_findings", "season1_task_packs", "season1_entries",
    ):
        cur.execute("SELECT count(*) FROM %s" % table)
        counts[table] = cur.fetchone()[0]
    return {
        "checkpoint": None if checkpoint is None else int(checkpoint[0]),
        "validators": validators,
        "rewardSigners": signers,
        "moduleRawLogs": raw,
        "businessRowCounts": counts,
    }


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="Backfill season1 module logs without moving checkpoint")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    cfg = get_config()
    if not cfg["database_url"]:
        print(json.dumps({"ok": False, "error": "no DATABASE_URL"}))
        return 2
    rpc = RpcClient(cfg["rpc_urls"])
    conn = psycopg2.connect(cfg["database_url"])
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT safe_block FROM checkpoint WHERE id = 1")
            before = cur.fetchone()
            applied = apply_sql_files(cur)
        decision = plan(None if before is None else before[0])
        decision["sql"] = applied
        decision["checkpointBefore"] = None if before is None else int(before[0])
        if decision["action"] != "backfill":
            conn.rollback()
            print(json.dumps(decision))
            return 0
        header = rpc.get_block(DEPLOY_BLOCK)
        if header is None or header.get("hash", "").lower() != DEPLOY_BLOCK_HASH:
            print(json.dumps({"ok": False, "error": "deploy block hash mismatch"}))
            conn.rollback()
            return 2
        logs = fetch_logs(rpc, MODULE, decision["from"], decision["to"])
        identity = [log_identity(row) for row in logs if not row.get("removed")]
        absent = missing_anchors(logs)
        report = {
            **decision,
            "chainLogCount": len(identity),
            "chainLogs": identity,
            "anchors": list(ANCHORS),
            "missingAnchors": absent,
            "forwardCatchupIsNotHistory": True,
        }
        if absent:
            conn.rollback()
            print(json.dumps({"ok": False, "rolledBack": True, **report}))
            return 2
        if args.dry_run:
            conn.rollback()
            print(json.dumps({"ok": True, "dryRun": True, **report}))
            return 0
        wanted = {item["block"] for item in identity}
        headers = {DEPLOY_BLOCK: header}
        for number in sorted(wanted):
            headers[number] = rpc.get_block(number)
        with conn.cursor() as cur:
            counts = write_module_logs(cur, MODULE, logs, headers)
            after = readback(cur)
        if counts["ValidatorSet"] < 1 or counts["RewardSignerSet"] < 1 or counts["undecoded"]:
            conn.rollback()
            print(json.dumps({"ok": False, "rolledBack": True, **report, **counts}))
            return 2
        if after["checkpoint"] != decision["checkpointBefore"]:
            conn.rollback()
            print(json.dumps({"ok": False, "rolledBack": True, "error": "checkpoint changed", **after}))
            return 2
        conn.commit()
        print(json.dumps({"ok": True, "dryRun": False, **report, **counts, "database": after}))
        return 0
    except Exception as exc:
        conn.rollback()
        print(json.dumps({"ok": False, "error": exc.__class__.__name__}))
        return 2
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
