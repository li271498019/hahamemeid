"""Generate the daily task pack (canonical JSON) for one dayIndex.

The task pack proves the displayed score of ONE agent at the day's
snapshot block. It is published only after that block reaches 15
confirmations, and every day gets one even with no new events.

Agent choice (deterministic, auditable): among all agents, pick the one
with the highest rating count at the snapshot block; ties break to the
lowest agentId. If no agent has any rating, pick the lowest agentId
(expectCount/expectSum are then "0"/"0" -- still a valid check).

Expected values come from the chain at the fixed block:
  getScore(agentId) -> (count, sum)   [HahaReputation]
  generationOf(agentId) -> generation  [HahaAgentIdentity]
The Rated events in the indexer DB are recounted per rater (last record
wins, via checker.last_rating_per_rater) as a cross-check; a mismatch
is logged as a warning and the chain values win.

Output: canonical JSON (keys sorted, no extra whitespace, UTF-8) at
/opt/haha-season1/day-taskpacks/taskpack-day{dayIndex}.json, and
taskPackHash = keccak256(file bytes). Returns a result dict.
"""

import json
import os
import sys

sys.path.insert(0, "/opt/haha-season1")
sys.path.insert(0, "/opt/haha-indexer")

import psycopg2
from indexer.common import RpcClient, get_config
from tools.season1.checker import last_rating_per_rater, task_pack_hash
from tools.season1.hashutil import keccak256
from tools.season1.mainnet import MODULE

REPUTATION = "0xf1A41B30d0c03fE178D3d76CBE6044E9D5Ce1800"
IDENTITY = "0x54A70BF81B288d41013D7b57c2Db0922f1E1a4d4"
OUTDIR = "/opt/haha-season1/day-taskpacks"


def _encode_call(selector_hex, arg):
    return "0x" + selector_hex + ("%064x" % int(arg))


def get_score_at(rpc, agent_id, block):
    data = _encode_call("0e1af57b", agent_id)
    raw = rpc.call("eth_call", [{"to": REPUTATION, "data": data}, hex(block)])
    if not raw or raw == "0x":
        raise ValueError("getScore returned nothing for agent %s" % agent_id)
    b = bytes.fromhex(raw[2:])
    return int.from_bytes(b[0:32], "big"), int.from_bytes(b[32:64], "big")


def generation_at(rpc, agent_id, block):
    data = _encode_call("e0bb12da", agent_id)
    raw = rpc.call("eth_call", [{"to": IDENTITY, "data": data}, hex(block)])
    if not raw or raw == "0x":
        raise ValueError("generationOf returned nothing for agent %s" % agent_id)
    return int.from_bytes(bytes.fromhex(raw[2:])[0:32], "big")


def pick_agent(conn, rpc, snapshot_block):
    """Return (agent_id, name, count, sum, generation, recount_count, recount_sum)."""
    cur = conn.cursor()
    cur.execute(
        "SELECT a.agent_id, n.full_name FROM agents a "
        "JOIN names n ON n.token_id = a.name_token_id ORDER BY a.agent_id"
    )
    agents = cur.fetchall()
    if not agents:
        raise ValueError("no agents in the indexer")
    # Recount Rated events at the snapshot block, per rater last-record.
    cur.execute(
        "SELECT agent_id, rater_ai_id, stars, block_number, log_index FROM reviews "
        "WHERE block_number <= %s",
        (snapshot_block,),
    )
    events = [{
        "agentId": int(r[0]), "raterAiId": "0x" + bytes(r[1]).hex(),
        "stars": int(r[2]), "block": int(r[3]), "logIndex": int(r[4]),
    } for r in cur.fetchall()]
    recount = last_rating_per_rater(events)
    best = None
    for agent_id, full_name in agents:
        bucket = recount.get(int(agent_id), {"count": 0, "sum": 0})
        key = (int(bucket["count"]), -int(agent_id))
        if best is None or key > best[0]:
            best = (key, int(agent_id), full_name, bucket)
    _key, agent_id, full_name, bucket = best
    count, total = get_score_at(rpc, agent_id, snapshot_block)
    generation = generation_at(rpc, agent_id, snapshot_block)
    return {
        "agentId": agent_id, "name": full_name,
        "count": count, "sum": total, "generation": generation,
        "recountCount": int(bucket["count"]), "recountSum": int(bucket["sum"]),
    }


def generate_taskpack(day_index, snapshot_block, snapshot_hash, outdir=None):
    outdir = outdir or OUTDIR
    cfg = get_config()
    rpc = RpcClient(cfg["rpc_urls"])
    conn = psycopg2.connect(cfg["database_url"])
    try:
        pick = pick_agent(conn, rpc, snapshot_block)
    finally:
        conn.close()
    warnings = []
    if pick["count"] != pick["recountCount"] or pick["sum"] != pick["recountSum"]:
        warnings.append(
            "getScore(%d) at block %d is count=%d sum=%d but Rated recount is "
            "count=%d sum=%d; chain values used"
            % (pick["agentId"], snapshot_block, pick["count"], pick["sum"],
               pick["recountCount"], pick["recountSum"]))
    body = {
        "seasonId": 1,
        "dayIndex": day_index,
        "blockNumber": snapshot_block,
        "blockHash": snapshot_hash,
        "checks": [{
            "id": "score",
            "agentId": str(pick["agentId"]),
            "generation": str(pick["generation"]),
            "name": pick["name"],
            "expectCount": str(pick["count"]),
            "expectSum": str(pick["sum"]),
        }],
    }
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "taskpack-day%d.json" % day_index)
    raw = json.dumps(body, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    with open(path, "wb") as f:
        f.write(raw)
    digest = task_pack_hash(body)
    # task_pack_hash re-serializes the same way; assert it matches the file bytes.
    file_hash = "0x" + keccak256(raw).hex()
    assert digest == file_hash, "task pack hash mismatch"
    return {
        "ok": True,
        "dayIndex": day_index,
        "snapshotBlock": snapshot_block,
        "snapshotBlockHash": snapshot_hash,
        "path": path,
        "taskPackHash": digest,
        "agentId": pick["agentId"],
        "agentName": pick["name"],
        "generation": pick["generation"],
        "expectCount": str(pick["count"]),
        "expectSum": str(pick["sum"]),
        "warnings": warnings,
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", type=int, required=True)
    ap.add_argument("--snapshot-block", type=int, required=True)
    ap.add_argument("--snapshot-hash", required=True)
    ap.add_argument("--outdir", default=None)
    args = ap.parse_args()
    result = generate_taskpack(args.day, args.snapshot_block, args.snapshot_hash, args.outdir)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0)
