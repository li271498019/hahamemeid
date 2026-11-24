"""haha.meme V1 indexer — sync loop.

Reads BSC logs from START_BLOCK, stores raw_logs + blocks, derives the
six V1 tables, and advances checkpoint(safe_block, safe_hash) in the same
transaction as the derived tables. Safe height = head - 3.

Reorgs: the checkpoint hash is verified against the chain every loop
iteration. On mismatch, walk back along blocks.parent_hash to the last
on-chain block N, delete raw_logs/blocks above N in one transaction,
rebuild all derived tables from the remaining raw logs, set checkpoint
to N, and resume.

Usage: python3 syncer.py [--env /etc/haha/indexer.env] [--once]
--once syncs to the current safe height and exits (handy for a first run).
"""

import argparse
import datetime
import hashlib
import os
import signal
import sys
import time

import psycopg2
import psycopg2.extras

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (AI_REGISTRY, ALL_ADDRESSES, CHAIN_ID, CONFIRMATIONS,
                    CONTRACTS, MAX_RANGE, MIN_RANGE, RpcClient, RpcError,
                    START_BLOCK, ZERO_ADDRESS, ZERO_BYTES32, decode_handleof_return,
                    decode_log, get_config, keccak256, topic0, _mask_url)

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
HANDLE_TTL = 3600  # seconds


def log(*args):
    print(datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "[syncer]", *args, flush=True)


def h2b(s):
    return bytes.fromhex(s[2:]) if s.startswith("0x") else bytes.fromhex(s)


def b2h(b):
    return "0x" + bytes(b).hex()


class HandleResolver:
    """Resolves .ai handles via handleOf(last_user), 1h in-process cache
    seeded from the handle_cache table. Verifies keccak256(handle) == aiId
    per PointsChanged row; on RPC failure returns None (API shows null)."""

    def __init__(self, rpc):
        self.rpc = rpc
        self.cache = {}  # user bytes -> (handle str|None, fetched_at epoch)

    def load_cache(self, cur):
        try:
            cur.execute("SELECT user_address, handle, fetched_at FROM handle_cache")
            now = time.time()
            for user, handle, fetched_at in cur.fetchall():
                age = now - fetched_at.timestamp()
                if age < HANDLE_TTL:
                    self.cache[bytes(user)] = (handle, fetched_at.timestamp())
        except Exception as e:
            log("handle_cache load skipped:", e)

    def _fetch(self, user_bytes):
        user_hex = "0x" + user_bytes.hex()
        data = topic0("handleOf(address)")[:10] + user_bytes.hex().rjust(64, "0")
        try:
            raw = self.rpc.eth_call(AI_REGISTRY, data)
        except RpcError as e:
            log("handleOf(%s) RPC failed: %s" % (user_hex, e))
            return None, False
        handle = decode_handleof_return(raw)
        return handle, True

    def resolve(self, user_bytes):
        """Return handle string, or None. Does NOT verify against aiId."""
        now = time.time()
        hit = self.cache.get(user_bytes)
        if hit is not None and now - hit[1] < HANDLE_TTL:
            return hit[0]
        handle, ok = self._fetch(user_bytes)
        if ok:
            self.cache[user_bytes] = (handle, now)
        return handle

    def persist(self, cur):
        now = datetime.datetime.now(datetime.timezone.utc)
        for user, (handle, _ts) in self.cache.items():
            cur.execute(
                "INSERT INTO handle_cache (user_address, handle, fetched_at)"
                " VALUES (%s, %s, %s) ON CONFLICT (user_address) DO UPDATE"
                " SET handle = EXCLUDED.handle, fetched_at = EXCLUDED.fetched_at",
                (user, handle, now))


def apply_log(cur, addr, event, p, meta, resolver):
    """Apply one decoded log to the derived tables. meta =
    (block_number, block_time, tx_hash_bytes, tx_index, log_index)."""
    bn, bt, txh, _txi, li = meta
    if event is None:
        return
    if event == "NameMinted":
        tld = p["tld"]
        full = p["label"] + (".haha" if tld == 0 else ".meme")
        cur.execute(
            "INSERT INTO names (token_id, label, tld, full_name, owner,"
            " mint_ai_id, reserved_mint, mint_block, mint_time)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (token_id) DO UPDATE SET label = EXCLUDED.label,"
            " tld = EXCLUDED.tld, full_name = EXCLUDED.full_name,"
            " owner = EXCLUDED.owner, mint_ai_id = EXCLUDED.mint_ai_id,"
            " reserved_mint = EXCLUDED.reserved_mint,"
            " mint_block = EXCLUDED.mint_block, mint_time = EXCLUDED.mint_time",
            (p["tokenId"], p["label"], tld, full, h2b(p["owner"]),
             h2b(p["aiId"]), p["reservedMint"], bn, bt))
    elif event == "Transfer" and addr == CONTRACTS["registrar"]:
        cur.execute("UPDATE names SET owner = %s WHERE token_id = %s",
                    (h2b(p["to"]), p["tokenId"]))
        cur.execute("DELETE FROM listings WHERE token_id = %s AND seller <> %s",
                    (p["tokenId"], h2b(p["to"])))
    elif event == "Transfer" and addr == CONTRACTS["identity"]:
        if p["to"] == ZERO_ADDRESS:
            cur.execute(
                "UPDATE agents SET active = false, reset_block = %s,"
                " reset_time = %s WHERE agent_id = %s",
                (bn, bt, p["tokenId"]))
    elif event == "AgentActivated":
        cur.execute(
            "INSERT INTO agents (agent_id, name_token_id, owner, operator_ai_id,"
            " generation, agent_uri, active, activated_block, activated_time,"
            " stars_sum, stars_count) VALUES (%s, %s, %s, %s, %s, %s, true,"
            " %s, %s, 0, 0) ON CONFLICT (agent_id) DO NOTHING",
            (p["agentId"], p["nameTokenId"], h2b(p["owner"]),
             h2b(p["operatorAiId"]), p["generation"], p["agentURI"], bn, bt))
    elif event == "URIUpdated":
        cur.execute("UPDATE agents SET agent_uri = %s WHERE agent_id = %s",
                    (p["newURI"], p["agentId"]))
    elif event == "AgentReset":
        cur.execute(
            "UPDATE agents SET active = false, reset_block = %s,"
            " reset_time = %s WHERE agent_id = %s",
            (bn, bt, p["agentId"]))
    elif event == "Rated":
        cur.execute("SELECT stars FROM reviews WHERE agent_id = %s AND rater_ai_id = %s",
                    (p["agentId"], h2b(p["aiId"])))
        old = cur.fetchone()
        cur.execute(
            "INSERT INTO reviews (agent_id, rater_ai_id, rater, stars, review,"
            " edited, block_number, block_time, tx_hash, log_index)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (agent_id, rater_ai_id) DO UPDATE SET stars = EXCLUDED.stars,"
            " review = EXCLUDED.review, edited = EXCLUDED.edited,"
            " block_number = EXCLUDED.block_number, block_time = EXCLUDED.block_time,"
            " tx_hash = EXCLUDED.tx_hash, log_index = EXCLUDED.log_index",
            (p["agentId"], h2b(p["aiId"]), h2b(p["rater"]), p["stars"],
             p["review"], p["edited"], bn, bt, txh, li))
        if old is None:
            cur.execute(
                "UPDATE agents SET stars_count = stars_count + 1,"
                " stars_sum = stars_sum + %s WHERE agent_id = %s",
                (p["stars"], p["agentId"]))
        else:
            cur.execute(
                "UPDATE agents SET stars_sum = stars_sum - %s + %s WHERE agent_id = %s",
                (old[0], p["stars"], p["agentId"]))
    elif event == "Listed":
        cur.execute("DELETE FROM listings WHERE token_id = %s", (p["tokenId"],))
        cur.execute(
            "INSERT INTO listings (token_id, seller, price_wei, listed_block,"
            " listed_time, tx_hash, log_index) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (p["tokenId"], h2b(p["seller"]), p["price"], bn, bt, txh, li))
    elif event == "PriceUpdated":
        cur.execute(
            "UPDATE listings SET price_wei = %s, listed_block = %s,"
            " listed_time = %s, tx_hash = %s, log_index = %s"
            " WHERE token_id = %s AND seller = %s",
            (p["newPrice"], bn, bt, txh, li, p["tokenId"], h2b(p["seller"])))
        if cur.rowcount == 0:
            cur.execute(
                "INSERT INTO listings (token_id, seller, price_wei, listed_block,"
                " listed_time, tx_hash, log_index) VALUES (%s, %s, %s, %s, %s, %s, %s)"
                " ON CONFLICT (token_id) DO NOTHING",
                (p["tokenId"], h2b(p["seller"]), p["newPrice"], bn, bt, txh, li))
    elif event in ("Cancelled", "Sold", "StaleCleared"):
        cur.execute("DELETE FROM listings WHERE token_id = %s", (p["tokenId"],))
        if event == "Sold":
            cur.execute(
                "INSERT INTO trades (token_id, seller, buyer, price_wei, fee_wei,"
                " proceeds_wei, block_number, block_time, tx_hash, log_index)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                " ON CONFLICT (tx_hash, log_index) DO NOTHING",
                (p["tokenId"], h2b(p["seller"]), h2b(p["buyer"]), p["price"],
                 p["fee"], p["proceeds"], bn, bt, txh, li))
    elif event == "PointsChanged":
        ai_id = h2b(p["aiId"])
        if ai_id == bytes(32):
            return
        handle = None
        got = resolver.resolve(h2b(p["user"]))
        if got is not None and keccak256(got.encode()) == ai_id:
            handle = got
        cur.execute(
            "INSERT INTO points (ai_id, balance, last_user, last_reason,"
            " updated_block, updated_time, handle)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (ai_id) DO UPDATE SET balance = EXCLUDED.balance,"
            " last_user = EXCLUDED.last_user, last_reason = EXCLUDED.last_reason,"
            " updated_block = EXCLUDED.updated_block,"
            " updated_time = EXCLUDED.updated_time, handle = COALESCE(EXCLUDED.handle, points.handle)",
            (ai_id, p["newBalance"], h2b(p["user"]), h2b(p["reason"]), bn, bt, handle))
    else:
        from season1_store import apply_season1_event
        apply_season1_event(cur, event, p, meta)


class Syncer:
    def __init__(self, cfg):
        self.cfg = cfg
        self.rpc = RpcClient(cfg["rpc_urls"])
        self.conn = psycopg2.connect(cfg["database_url"])
        self.conn.autocommit = False
        self.resolver = HandleResolver(self.rpc)
        from common import EVENTS
        from season1_store import bind_from_env
        bind_from_env(EVENTS)
        self.range_blocks = MAX_RANGE
        self.stop = False
        self._ensure_schema()

    def _ensure_schema(self):
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            sql = f.read()
        with self.conn.cursor() as cur:
            cur.execute(sql)
            self.resolver.load_cache(cur)
        self.conn.commit()

    def get_checkpoint(self):
        with self.conn.cursor() as cur:
            cur.execute("SELECT safe_block, safe_hash FROM checkpoint WHERE id = 1")
            row = cur.fetchone()
        if row is None:
            return None
        return row[0], bytes(row[1])

    def set_checkpoint(self, cur, block, block_hash):
        cur.execute(
            "INSERT INTO checkpoint (id, safe_block, safe_hash) VALUES (1, %s, %s)"
            " ON CONFLICT (id) DO UPDATE SET safe_block = EXCLUDED.safe_block,"
            " safe_hash = EXCLUDED.safe_hash",
            (block, block_hash))

    def chain_block(self, number):
        blk = self.rpc.get_block(number)
        if blk is None:
            raise RpcError("getBlockByNumber(%d) returned null" % number)
        return blk

    def check_reorg(self, safe_block, safe_hash):
        """True if the checkpoint block is still on-chain, False if it was
        reorged away, None if the RPC check itself failed (unknown).
        Compares the chain hash against BOTH checkpoint.safe_hash and the
        stored blocks.hash for safe_block: a test that tampers blocks.hash
        (spec acceptance 8) must also be caught, not only a real reorg
        (where both stored hashes disagree with the chain)."""
        if safe_block is None:
            return True
        try:
            blk = self.chain_block(safe_block)
        except RpcError as e:
            log("checkpoint check RPC failed (unknown, not a reorg):", e)
            return None
        chain_hash = h2b(blk["hash"])
        if chain_hash != safe_hash:
            return False
        with self.conn.cursor() as cur:
            cur.execute("SELECT hash FROM blocks WHERE block_number = %s",
                        (safe_block,))
            row = cur.fetchone()
        if row is not None and bytes(row[0]) != chain_hash:
            log("stored blocks.hash for safe_block disagrees with chain")
            return False
        return True

    def handle_reorg(self, safe_block):
        """Walk back to the last on-chain block N, then in ONE transaction
        delete raw_logs/blocks above N and rebuild derived tables."""
        log("REORG suspected at safe_block", safe_block, "- walking back")
        n = safe_block
        while True:
            blk = self.chain_block(n)
            with self.conn.cursor() as cur:
                cur.execute("SELECT hash FROM blocks WHERE block_number = %s", (n,))
                row = cur.fetchone()
            if row is not None and bytes(row[0]) == h2b(blk["hash"]):
                break
            if n <= START_BLOCK - 1:
                n = START_BLOCK - 1
                break
            n -= 1
        chain_hash = h2b(self.chain_block(n)["hash"])
        log("REORG: rolling back to block", n)
        # Pre-resolve handles for the surviving PointsChanged logs.
        with self.conn.cursor() as cur:
            # topics[2] is the indexed `user` of PointsChanged
            # (topics[0]=topic0, topics[1]=aiId, topics[2]=user, topics[3]=reason).
            cur.execute(
                "SELECT DISTINCT topics->2 FROM raw_logs WHERE block_number <= %s"
                " AND address = %s AND topic0 = %s",
                (n, h2b(CONTRACTS["points"]),
                 h2b(topic0("PointsChanged(bytes32,address,int256,uint256,bytes32)"))))
            users = [bytes.fromhex(t[2:])[12:] for (t,) in cur.fetchall()]
        for u in users:
            self.resolver.resolve(u)
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM raw_logs WHERE block_number > %s", (n,))
            cur.execute("DELETE FROM blocks WHERE block_number > %s", (n,))
            for t in ("names", "listings", "trades", "agents", "reviews", "points",
                      "season1_days", "season1_orders", "season1_verifications",
                      "season1_findings", "season1_task_packs", "season1_entries",
                      "season1_validators", "season1_reward_signer"):
                cur.execute("TRUNCATE %s" % t)
            cur.execute(
                "SELECT block_number, block_time, tx_hash, tx_index, log_index,"
                " address, topics, data FROM raw_logs ORDER BY block_number,"
                " tx_index, log_index")
            rows = cur.fetchall()
            for bn, bt, txh, txi, li, addr, topics, data in rows:
                event, p = decode_log(b2h(addr), topics, bytes(data))
                apply_log(cur, b2h(addr), event, p,
                          (bn, bt, bytes(txh), txi, li), self.resolver)
            self.resolver.persist(cur)
            self.set_checkpoint(cur, n, chain_hash)
        self.conn.commit()
        log("REORG: rolled back to", n, "; replayed", len(rows), "logs")
        return n

    def sync_batch(self, from_block, to_block):
        """Fetch + commit one batch [from_block, to_block]. Returns the
        block it actually committed to (== to_block), or raises RpcError."""
        logs = self.rpc.get_logs(from_block, to_block)
        logs = [l for l in logs if not l.get("removed")]
        logs.sort(key=lambda l: (int(l["blockNumber"], 16),
                                 int(l["transactionIndex"], 16),
                                 int(l["logIndex"], 16)))
        # Block headers we need: every block with logs, plus to_block.
        want = {int(l["blockNumber"], 16) for l in logs}
        want.add(to_block)
        headers = {}
        for bn in sorted(want):
            headers[bn] = self.chain_block(bn)
        # Pre-resolve .ai handles for PointsChanged in this batch.
        pc_topic = topic0("PointsChanged(bytes32,address,int256,uint256,bytes32)")
        users = set()
        for l in logs:
            if l["address"].lower() == CONTRACTS["points"] and \
                    l["topics"][0].lower() == pc_topic:
                users.add(bytes.fromhex(l["topics"][2][2:])[12:])
        for u in users:
            self.resolver.resolve(u)
        with self.conn.cursor() as cur:
            # Refuse to commit if a block we already stored changed hash.
            for bn, h in headers.items():
                cur.execute("SELECT hash FROM blocks WHERE block_number = %s", (bn,))
                row = cur.fetchone()
                if row is not None and bytes(row[0]) != h2b(h["hash"]):
                    raise RpcError("stored block %d hash changed; reorg?" % bn)
            for bn, h in headers.items():
                cur.execute(
                    "INSERT INTO blocks (block_number, hash, parent_hash)"
                    " VALUES (%s, %s, %s) ON CONFLICT (block_number) DO NOTHING",
                    (bn, h2b(h["hash"]), h2b(h["parentHash"])))
            for l in logs:
                bn = int(l["blockNumber"], 16)
                bt = datetime.datetime.fromtimestamp(
                    int(headers[bn]["timestamp"], 16), datetime.timezone.utc)
                cur.execute(
                    "INSERT INTO raw_logs (chain_id, block_number, block_hash,"
                    " block_time, tx_hash, tx_index, log_index, address, topic0,"
                    " topics, data) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,"
                    " %s, %s) ON CONFLICT (chain_id, block_number, tx_index,"
                    " log_index) DO NOTHING",
                    (CHAIN_ID, bn, h2b(l["blockHash"]), bt,
                     h2b(l["transactionHash"]), int(l["transactionIndex"], 16),
                     int(l["logIndex"], 16), h2b(l["address"]),
                     h2b(l["topics"][0]),
                     psycopg2.extras.Json([t.lower() for t in l["topics"]]),
                     h2b(l["data"])))
            for l in logs:
                bn = int(l["blockNumber"], 16)
                bt = datetime.datetime.fromtimestamp(
                    int(headers[bn]["timestamp"], 16), datetime.timezone.utc)
                event, p = decode_log(l["address"], l["topics"],
                                      h2b(l["data"]))
                apply_log(cur, l["address"].lower(), event, p,
                          (bn, bt, h2b(l["transactionHash"]),
                           int(l["transactionIndex"], 16),
                           int(l["logIndex"], 16)), self.resolver)
            self.resolver.persist(cur)
            self.set_checkpoint(cur, to_block, h2b(headers[to_block]["hash"]))
        self.conn.commit()
        return to_block

    def run_once(self):
        """Sync from the checkpoint up to the current safe height once."""
        cp = self.get_checkpoint()
        if cp is None:
            nxt = START_BLOCK
            safe_block, safe_hash = None, None
        else:
            safe_block, safe_hash = cp
            nxt = safe_block + 1
        if safe_block is not None:
            ok = self.check_reorg(safe_block, safe_hash)
            if ok is False:
                nxt = self.handle_reorg(safe_block) + 1
                cp = self.get_checkpoint()
                safe_block, safe_hash = cp
        head = self.rpc.block_number()
        safe_target = head - CONFIRMATIONS
        log("head", head, "safe_target", safe_target, "next", nxt)
        while nxt <= safe_target and not self.stop:
            to = min(nxt + self.range_blocks - 1, safe_target)
            try:
                self.sync_batch(nxt, to)
            except RpcError as e:
                if e.range_too_large:
                    self.range_blocks = max(MIN_RANGE, self.range_blocks // 2)
                    log("range too large, halving to", self.range_blocks)
                    continue
                log("batch failed:", e, "- retrying in 5s")
                time.sleep(5)
                continue
            except Exception as e:
                self.conn.rollback()
                log("batch failed (db?):", repr(e), "- retrying in 5s")
                time.sleep(5)
                continue
            log("synced to", to)
            self.range_blocks = min(MAX_RANGE, self.range_blocks + 250)
            nxt = to + 1
        return nxt - 1

    def run_forever(self):
        while not self.stop:
            try:
                self.run_once()
            except RpcError as e:
                log("sync error:", e, "- retrying in 5s")
                time.sleep(5)
                continue
            except Exception as e:
                self.conn.rollback()
                log("sync error:", repr(e), "- retrying in 5s")
                time.sleep(5)
                continue
            for _ in range(30):
                if self.stop:
                    break
                time.sleep(0.1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=None)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    cfg = get_config(args.env)
    if not cfg["database_url"]:
        log("FATAL: no DATABASE_URL in env", cfg["env_path"])
        sys.exit(2)
    syncer = Syncer(cfg)
    stop = {"flag": False}

    def _sig(signum, frame):
        log("signal", signum, "- stopping")
        syncer.stop = True
    signal.signal(signal.SIGTERM, _sig)
    signal.signal(signal.SIGINT, _sig)
    log("starting; rpc:", _mask_url(cfg["rpc_urls"][0]), "...")
    if args.once:
        syncer.run_once()
        log("once done")
    else:
        syncer.run_forever()
    syncer.conn.close()


if __name__ == "__main__":
    main()
