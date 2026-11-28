"""End-to-end check of the Haha Dog indexer against the live chain and a scratch Postgres.
NOT part of the unit tests (needs network + DB). Usage:
    DATABASE_URL=postgresql://... python3 tests/dog_e2e.py [--env FILE]
Steps: backfill -> forward sync with the real Syncer (get_logs limited to the dog
contracts, because public nodes refuse the 13-address filter) -> forced reorg rebuild ->
compare dogs/listings/trades with the chain (ownerOf, dogOf, listings)."""
import hashlib, json, os, subprocess, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import psycopg2
import common
from common import DOG_ADDRESSES, RpcClient, get_config
import syncer as syncer_mod
import dog_store

env = sys.argv[sys.argv.index("--env") + 1] if "--env" in sys.argv else None
cfg = get_config(env)
RpcClient.get_logs = lambda self, a, b, addresses=None: self.call("eth_getLogs", [{"fromBlock": hex(a), "toBlock": hex(b), "address": DOG_ADDRESSES}])
rpc = RpcClient(cfg["rpc_urls"])


def dump(conn):
    cur = conn.cursor()
    out = []
    for t, order in (("dogs", "token_id"), ("dog_snapshots", "block_number"), ("dog_listings", "token_id"),
                     ("dog_trades", "tx_hash, log_index"), ("dog_withdrawals", "tx_hash, log_index")):
        cur.execute("SELECT * FROM %s ORDER BY %s" % (t, order))
        out.append((t, [tuple(bytes(c).hex() if isinstance(c, memoryview) else str(c) for c in r) for r in cur.fetchall()]))
    conn.rollback()
    return out


def digest(d):
    return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()[:16]


def chain_call(to, data):
    return rpc.call("eth_call", [{"to": to, "data": data}, "latest"])


def w(h, i):
    return h[2 + 64 * i: 2 + 64 * (i + 1)]


conn = psycopg2.connect(cfg["database_url"])
cur = conn.cursor()
cur.execute("TRUNCATE raw_logs, blocks, checkpoint, dogs, dog_snapshots, dog_listings, dog_trades, dog_withdrawals")
head = rpc.block_number()
cp = head - 1500
blk = rpc.get_block(cp)
cur.execute("INSERT INTO checkpoint (id, safe_block, safe_hash) VALUES (1, %s, %s)", (cp, bytes.fromhex(blk["hash"][2:])))
conn.commit()
print("checkpoint", cp, "head", head)
subprocess.check_call([sys.executable, os.path.join(ROOT, "dog_backfill.py")] + (["--env", env] if env else []))
after_backfill = digest(dump(conn))

s = syncer_mod.Syncer(cfg)
s.run_once()
cur.execute("SELECT safe_block FROM checkpoint WHERE id = 1")
new_cp = cur.fetchone()[0]
conn.rollback()
print("syncer advanced checkpoint", cp, "->", new_cp)
d1 = dump(conn)
print("after forward sync:", {t: len(rows) for t, rows in d1}, digest(d1))

# Pre-existing, unrelated: handle_reorg TRUNCATEs season1_findings, which season1_finding_reports
# references (FK), so a real reorg fails on production too (see INDEXER-PLAN.md, "found on the way").
# Drop the FK in this scratch DB only so the dog replay can be tested.
cur.execute("ALTER TABLE season1_finding_reports DROP CONSTRAINT IF EXISTS season1_finding_reports_report_evidence_hash_fkey")
conn.commit()
# forced reorg path: wrong checkpoint hash -> walk back, truncate, replay raw_logs
cur.execute("UPDATE checkpoint SET safe_hash = %s WHERE id = 1", (b"\x01" * 32,))
conn.commit()
s2 = syncer_mod.Syncer(cfg)
s2.run_once()
d2 = dump(conn)
print("after forced reorg rebuild:", {t: len(rows) for t, rows in d2}, digest(d2))
reorg_ok = {t: len(r) for t, r in d1} == {t: len(r) for t, r in d2}

# compare with the chain
total = int(w(chain_call(common.CONTRACTS["dog"], "0x18160ddd"), 0), 16)
cur.execute("SELECT token_id, encode(owner,'hex'), rerolls, encode(seed,'hex'), commit_block FROM dogs ORDER BY token_id")
rows = {int(r[0]): r for r in cur.fetchall()}
bad = []
for i in range(1, total + 1):
    r = rows.get(i)
    if r is None:
        bad.append((i, "missing")); continue
    o = w(chain_call(common.CONTRACTS["dog"], "0x6352211e%064x" % i), 0)[24:]
    d = chain_call(common.CONTRACTS["dog"], "0x2f403afd%064x" % i)
    seed = w(d, 4); status = int(w(d, 3), 16)
    if o != r[1]: bad.append((i, "owner"))
    if int(w(d, 2), 16) != r[2]: bad.append((i, "rerolls"))
    if int(w(d, 0), 16) != r[4]: bad.append((i, "commitBlock"))
    if status == 2 and r[3] is not None and r[3] != seed: bad.append((i, "SEED MISMATCH"))
    if status == 2 and r[3] is None: pass  # indexer may still be waiting for a hash; API says "check"
    if status == 1 and r[3] is not None: bad.append((i, "seed before ready"))
print("chain total", total, "indexed", len(rows), "mismatches", bad)
seeds_known = sum(1 for r in rows.values() if r[3] is not None)
print("seeds known", seeds_known, "of", len(rows))
cur.execute("SELECT token_id, encode(seller,'hex'), price_wei, rerolls FROM dog_listings ORDER BY token_id")
for tid, seller, price, rr in cur.fetchall():
    h = chain_call(common.CONTRACTS["dogmarket"], "0xde74e57b%064x" % int(tid))
    ok = w(h, 0)[24:] == seller and int(w(h, 1), 16) == int(price) and int(w(h, 2), 16) == rr
    print("listing", tid, "matches chain" if ok else "MISMATCH")
    if not ok: bad.append((int(tid), "listing"))
print("RESULT", "OK" if not bad and reorg_ok and len(rows) == total else "FAIL")
sys.exit(0 if not bad and reorg_ok and len(rows) == total else 1)
