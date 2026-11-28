"""Synthetic fixture test for the haha-indexer (TEST database only).

Builds a full lifecycle on haha_indexer_test using REAL block headers
(hashes/parent_hashes/timestamps from the chain, so the reorg walk-back
works), inserts synthetic raw_logs, replays the derived tables with the
syncer's own apply_log, and asserts the expected state.

Scenario (tokenId 1001 = abc.haha, 1002 = xyz.meme):
  mint abc + xyz, list abc 0.5 -> reprice 0.6, list xyz 1.0,
  activate agent 1 (abc, gen 1), rate 5 "nice", points +10/+5,
  re-rate 4 "ok" edited (count stays 1, sum 5 -> 4),
  transfer abc A -> D (listing must vanish, no clearStale),
  AgentReset + agent-NFT burn (agent 1 inactive),
  sell xyz B -> E for 1 BNB (fee 0.01, proceeds 0.99),
  activate agent 2 (abc, gen 2, new owner D), points +20,
  zero-aiId PointsChanged (must NOT enter the board),
  points +30 for E.
Expected: names abc->D, xyz->E; listings empty; trades 1 row;
agents: 1 inactive (sum 4, count 1), 2 active (gen 2, 0 stars);
reviews 1 row (4 stars, "ok", edited=true);
points: AA 10, CC 5, DD 20, EE 30, no zero-aiId row, handles NULL.

Run on the server: python3 fixture_test.py
Env: /etc/haha/indexer-test.env (DATABASE_URL + BSC_RPC_URLS).
Leaves the test DB in the fixture state for the API + reorg tests.
"""

import datetime
import os
import sys

import psycopg2
import psycopg2.extras

sys.path.insert(0, "/opt/haha-indexer")
from common import CONTRACTS, RpcClient, get_config, keccak256, topic0
from syncer import HandleResolver, apply_log

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

A = "0x" + "aa" * 20
B = "0x" + "bb" * 20
C = "0x" + "cc" * 20
D = "0x" + "dd" * 20
E = "0x" + "ee" * 20
F = "0x" + "ff" * 20
ZERO20 = "0x" + "00" * 20
AA = "0x" + "aa" * 32
BB = "0x" + "bb" * 32
CC = "0x" + "cc" * 32
DD = "0x" + "dd" * 32
EE = "0x" + "ee" * 32
ZERO32 = "0x" + "00" * 32
T1, T2 = 1001, 1002  # tokenIds: abc.haha, xyz.meme
BNB = 10 ** 18


def h2b(s):
    return bytes.fromhex(s[2:])


def w_uint(n):
    return n.to_bytes(32, "big")


def w_int(n):
    return n.to_bytes(32, "big", signed=True)


def w_addr(a):
    return bytes(12) + h2b(a)


def w_b32(b):
    return h2b(b) if isinstance(b, str) else b


def w_bool(v):
    return bytes(31) + (b"\x01" if v else b"\x00")


def encode_abi(params):
    """params: [(type, value)]. Returns data bytes."""
    head, tail = b"", b""
    dyn_offset = 32 * len(params)
    for typ, val in params:
        if typ == "string":
            head += w_uint(dyn_offset)
            raw = val.encode()
            tail += w_uint(len(raw)) + raw + bytes((-len(raw)) % 32)
            dyn_offset += 32 + len(raw) + (-len(raw)) % 32
        elif typ in ("uint256", "uint8", "uint64"):
            head += w_uint(val)
        elif typ == "int256":
            head += w_int(val)
        elif typ == "address":
            head += w_addr(val)
        elif typ == "bytes32":
            head += w_b32(val)
        elif typ == "bool":
            head += w_bool(val)
        else:
            raise ValueError(typ)
    return head + tail


def topic_word(typ, val):
    if typ == "address":
        return "0x" + w_addr(val).hex()
    if typ == "bytes32":
        return "0x" + w_b32(val).hex()
    if typ in ("uint256", "uint8", "uint64"):
        return "0x" + w_uint(val).hex()
    if typ == "bool":
        return "0x" + w_bool(val).hex()
    raise ValueError(typ)


class Builder:
    def __init__(self, headers):
        self.headers = headers  # block -> header dict
        self.logs = []          # (block, tx_index, log_index, addr, topics, data)
        self.tx_counter = 0

    def add(self, block, contract, sig, indexed, data_params, tx_index=0, log_index=0):
        topics = [topic0(sig)]
        for typ, val in indexed:
            topics.append(topic_word(typ, val))
        data = encode_abi(data_params)
        self.logs.append((block, tx_index, log_index, CONTRACTS[contract],
                          topics, data))

    def run(self, conn, resolver):
        cur = conn.cursor()
        cur.execute(open("/opt/haha-indexer/schema.sql").read())
        for t in ("raw_logs", "blocks", "checkpoint", "names", "listings",
                  "trades", "agents", "reviews", "points", "handle_cache",
                  "season1_days", "season1_orders", "season1_verifications",
                  "season1_findings", "season1_task_packs", "season1_entries",
                  "season1_validators", "season1_reward_signer"):
            cur.execute("SELECT to_regclass(%s)", (t,))
            if cur.fetchone()[0] is not None:
                cur.execute("TRUNCATE %s" % t)
        for bn in sorted(self.headers):
            h = self.headers[bn]
            cur.execute(
                "INSERT INTO blocks (block_number, hash, parent_hash) VALUES (%s, %s, %s)",
                (bn, h2b(h["hash"]), h2b(h["parentHash"])))
        for (bn, txi, li, addr, topics, data) in sorted(self.logs):
            h = self.headers[bn]
            bt = datetime.datetime.fromtimestamp(int(h["timestamp"], 16),
                                                 datetime.timezone.utc)
            txh = keccak256(("fixture-%d-%d-%d" % (bn, txi, li)).encode())
            cur.execute(
                "INSERT INTO raw_logs (chain_id, block_number, block_hash, block_time,"
                " tx_hash, tx_index, log_index, address, topic0, topics, data)"
                " VALUES (56, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (bn, h2b(h["hash"]), bt, txh, txi, li, h2b(addr),
                 h2b(topics[0]), psycopg2.extras.Json(topics), data))
        # replay derived tables in log order (same code path as reorg replay)
        from common import decode_log
        cur.execute("SELECT block_number, block_time, tx_hash, tx_index, log_index,"
                    " address, topics, data FROM raw_logs ORDER BY block_number,"
                    " tx_index, log_index")
        rows = cur.fetchall()
        for bn, bt, txh, txi, li, addr, topics, data in rows:
            event, p = decode_log("0x" + bytes(addr).hex(), topics, bytes(data))
            apply_log(cur, "0x" + bytes(addr).hex(), event, p,
                      (bn, bt, bytes(txh), txi, li), resolver)
        resolver.persist(cur)
        last = max(self.headers)
        cur.execute("INSERT INTO checkpoint (id, safe_block, safe_hash) VALUES (1, %s, %s)",
                    (last, h2b(self.headers[last]["hash"])))
        conn.commit()
        return len(rows)


def check(name, got, want):
    ok = got == want
    print(("PASS " if ok else "FAIL ") + name + ": got=%r want=%r" % (got, want))
    return ok


def main():
    cfg = get_config("/etc/haha/indexer-test.env")
    rpc = RpcClient(cfg["rpc_urls"])
    blocks = [134834631] + list(range(134834700, 134834717))
    headers = {}
    for bn in blocks:
        headers[bn] = rpc.get_block(bn)
    print("fetched %d real block headers" % len(headers))

    b = Builder(headers)
    b.add(134834631, "policy", "ListsFrozen(uint256,uint256)", [],
          [("uint256", 208), ("uint256", 61)])
    b.add(134834700, "registrar", "NameMinted(uint256,address,uint8,bytes32,string,bool)",
          [("uint256", T1), ("address", A), ("bytes32", AA)],
          [("uint8", 0), ("string", "abc"), ("bool", False)])
    b.add(134834701, "registrar", "NameMinted(uint256,address,uint8,bytes32,string,bool)",
          [("uint256", T2), ("address", B), ("bytes32", BB)],
          [("uint8", 1), ("string", "xyz"), ("bool", False)])
    b.add(134834702, "market", "Listed(uint256,address,uint256)",
          [("uint256", T1), ("address", A)], [("uint256", BNB // 2)])
    b.add(134834703, "market", "PriceUpdated(uint256,address,uint256,uint256)",
          [("uint256", T1), ("address", A)],
          [("uint256", BNB // 2), ("uint256", BNB * 6 // 10)])
    b.add(134834704, "market", "Listed(uint256,address,uint256)",
          [("uint256", T2), ("address", B)], [("uint256", BNB)])
    b.add(134834705, "identity", "AgentActivated(uint256,uint256,address,bytes32,uint64,string)",
          [("uint256", 1), ("uint256", T1), ("address", A)],
          [("bytes32", AA), ("uint64", 1), ("string", "https://example.com/agent.json")])
    b.add(134834706, "reputation", "Rated(uint256,bytes32,address,uint8,string,bool)",
          [("uint256", 1), ("bytes32", CC), ("address", C)],
          [("uint8", 5), ("string", "nice"), ("bool", False)])
    b.add(134834707, "points", "PointsChanged(bytes32,address,int256,uint256,bytes32)",
          [("bytes32", AA), ("address", A), ("bytes32", "0x" + (b"MINT" + bytes(28)).hex())],
          [("int256", 10), ("uint256", 10)])
    b.add(134834708, "points", "PointsChanged(bytes32,address,int256,uint256,bytes32)",
          [("bytes32", CC), ("address", C),
           ("bytes32", "0x" + (b"REVIEW_GIVE" + bytes(21)).hex())],
          [("int256", 5), ("uint256", 5)])
    b.add(134834709, "reputation", "Rated(uint256,bytes32,address,uint8,string,bool)",
          [("uint256", 1), ("bytes32", CC), ("address", C)],
          [("uint8", 4), ("string", "ok"), ("bool", True)])
    b.add(134834710, "registrar", "Transfer(address,address,uint256)",
          [("address", A), ("address", D), ("uint256", T1)], [])
    b.add(134834711, "identity", "AgentReset(uint256,uint256,address)",
          [("uint256", T1), ("uint256", 1), ("address", A)], [])
    b.add(134834711, "identity", "Transfer(address,address,uint256)",
          [("address", A), ("address", ZERO20), ("uint256", 1)], [],
          tx_index=0, log_index=1)
    b.add(134834712, "registrar", "Transfer(address,address,uint256)",
          [("address", B), ("address", E), ("uint256", T2)], [])
    b.add(134834712, "market", "Sold(uint256,address,address,uint256,uint256,uint256)",
          [("uint256", T2), ("address", B), ("address", E)],
          [("uint256", BNB), ("uint256", BNB // 100), ("uint256", BNB * 99 // 100)],
          tx_index=0, log_index=1)
    b.add(134834713, "identity", "AgentActivated(uint256,uint256,address,bytes32,uint64,string)",
          [("uint256", 2), ("uint256", T1), ("address", D)],
          [("bytes32", DD), ("uint64", 2), ("string", "https://example.com/agent2.json")])
    b.add(134834714, "points", "PointsChanged(bytes32,address,int256,uint256,bytes32)",
          [("bytes32", DD), ("address", D),
           ("bytes32", "0x" + (b"ACTIVATE" + bytes(24)).hex())],
          [("int256", 20), ("uint256", 20)])
    b.add(134834715, "points", "PointsChanged(bytes32,address,int256,uint256,bytes32)",
          [("bytes32", ZERO32), ("address", F),
           ("bytes32", "0x" + (b"CHECKIN" + bytes(25)).hex())],
          [("int256", 99), ("uint256", 99)])
    b.add(134834716, "points", "PointsChanged(bytes32,address,int256,uint256,bytes32)",
          [("bytes32", EE), ("address", E),
           ("bytes32", "0x" + (b"CHECKIN" + bytes(25)).hex())],
          [("int256", 30), ("uint256", 30)])

    conn = psycopg2.connect(cfg["database_url"])
    resolver = HandleResolver(rpc)
    n = b.run(conn, resolver)
    print("replayed %d logs" % n)

    cur = conn.cursor()
    ok = True
    cur.execute("SELECT count(*) FROM raw_logs")
    ok &= check("raw_logs", cur.fetchone()[0], 20)
    cur.execute("SELECT full_name, encode(owner,'hex') FROM names ORDER BY token_id")
    ok &= check("names", cur.fetchall(),
                [("abc.haha", "dd" * 20), ("xyz.meme", "ee" * 20)])
    cur.execute("SELECT count(*) FROM listings")
    ok &= check("listings empty", cur.fetchone()[0], 0)
    cur.execute("SELECT token_id, encode(seller,'hex'), encode(buyer,'hex'),"
                " price_wei, fee_wei, proceeds_wei FROM trades")
    ok &= check("trades", cur.fetchall(),
                [(1002, "bb" * 20, "ee" * 20, BNB, BNB // 100, BNB * 99 // 100)])
    cur.execute("SELECT agent_id, generation, active, stars_sum, stars_count"
                " FROM agents ORDER BY agent_id")
    ok &= check("agents", cur.fetchall(),
                [(1, 1, False, 4, 1), (2, 2, True, 0, 0)])
    cur.execute("SELECT agent_id, stars, review, edited FROM reviews")
    ok &= check("reviews", cur.fetchall(), [(1, 4, "ok", True)])
    cur.execute("SELECT encode(ai_id,'hex'), balance, handle FROM points ORDER BY balance DESC")
    ok &= check("points", cur.fetchall(),
                [("ee" * 32, 30, None), ("dd" * 32, 20, None),
                 ("aa" * 32, 10, None), ("cc" * 32, 5, None)])
    cur.execute("SELECT safe_block FROM checkpoint")
    ok &= check("checkpoint", cur.fetchone()[0], 134834716)
    print("ALL PASS" if ok else "SOME FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
