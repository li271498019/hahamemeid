"""Haha Dog derived tables: HahaDog (ERC-721) and HahaDogMarket events.

apply_dog_event() is called from syncer.apply_log for logs emitted by the two
Haha Dog contracts, inside the batch transaction. Everything here is a pure
function of the logs in block order, so handle_reorg() can truncate the dog_*
tables and replay raw_logs. resolve_seeds() runs after a batch, outside it.
"""

from common import CONFIRMATIONS, CONTRACTS, keccak256

SEED_DELAY = 4            # HahaDog.SEED_DELAY
LIVE_HASH_WINDOW = 250    # a node always has the hash this close to head
MAX_BLOCK_FETCH = 30      # RPC block fetches per resolve pass

DOG_TABLES = ("dogs", "dog_snapshots", "dog_listings", "dog_trades", "dog_withdrawals")


def h2b(s):
    return bytes.fromhex(s[2:]) if s.startswith("0x") else bytes.fromhex(s)


def seed_of(block_hash, token_id, rerolls):
    """keccak256(abi.encode(bytes32 hash, uint256 tokenId, uint256 rerolls))."""
    return keccak256(bytes(block_hash)
                     + int(token_id).to_bytes(32, "big")
                     + int(rerolls).to_bytes(32, "big"))


def apply_dog_event(cur, addr, event, p, meta):
    bn, bt, txh, _txi, li = meta
    if addr == CONTRACTS["dog"]:
        if event == "Transfer":
            if p["from"] == "0x" + "00" * 20:
                # Mint. Committed comes first in the same tx, so the row may exist.
                cur.execute(
                    "INSERT INTO dogs (token_id, owner, mint_block, mint_time, mint_tx,"
                    " commit_block, commit_time, rerolls) VALUES (%s, %s, %s, %s, %s, %s, %s, 0)"
                    " ON CONFLICT (token_id) DO UPDATE SET owner = EXCLUDED.owner,"
                    " mint_block = EXCLUDED.mint_block, mint_time = EXCLUDED.mint_time,"
                    " mint_tx = EXCLUDED.mint_tx",
                    (p["tokenId"], h2b(p["to"]), bn, bt, txh, bn, bt))
            else:
                cur.execute("UPDATE dogs SET owner = %s WHERE token_id = %s",
                            (h2b(p["to"]), p["tokenId"]))
        elif event == "Committed":
            cur.execute(
                "INSERT INTO dogs (token_id, commit_block, commit_time, rerolls)"
                " VALUES (%s, %s, %s, %s) ON CONFLICT (token_id) DO UPDATE SET"
                " commit_block = EXCLUDED.commit_block, commit_time = EXCLUDED.commit_time,"
                " rerolls = EXCLUDED.rerolls, seed = NULL, seed_block = NULL",
                (p["tokenId"], p["commitBlock"], bt, p["rerolls"]))
        elif event == "Snapshot":
            cur.execute(
                "INSERT INTO dog_snapshots (block_number, block_hash) VALUES (%s, %s)"
                " ON CONFLICT (block_number) DO NOTHING",
                (p["blockNumber"], h2b(p["blockHash"])))
    elif addr == CONTRACTS["dogmarket"]:
        if event == "Listed":
            cur.execute(
                "INSERT INTO dog_listings (token_id, seller, price_wei, rerolls, listed_block,"
                " listed_time, tx_hash, log_index) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
                " ON CONFLICT (token_id) DO UPDATE SET seller = EXCLUDED.seller,"
                " price_wei = EXCLUDED.price_wei, rerolls = EXCLUDED.rerolls,"
                " listed_block = EXCLUDED.listed_block, listed_time = EXCLUDED.listed_time,"
                " tx_hash = EXCLUDED.tx_hash, log_index = EXCLUDED.log_index",
                (p["tokenId"], h2b(p["seller"]), p["price"], p["rerolls"], bn, bt, txh, li))
        elif event == "PriceUpdated":
            # The contract keeps the listing's rerolls and seller; only the price moves.
            cur.execute("UPDATE dog_listings SET price_wei = %s WHERE token_id = %s",
                        (p["newPrice"], p["tokenId"]))
        elif event in ("Cancelled", "StaleCleared", "Sold"):
            cur.execute("DELETE FROM dog_listings WHERE token_id = %s", (p["tokenId"],))
            if event == "Sold":
                cur.execute(
                    "INSERT INTO dog_trades (token_id, seller, buyer, price_wei, fee_wei,"
                    " proceeds_wei, block_number, block_time, tx_hash, log_index)"
                    " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                    " ON CONFLICT (tx_hash, log_index) DO NOTHING",
                    (p["tokenId"], h2b(p["seller"]), h2b(p["buyer"]), p["price"], p["fee"],
                     p["proceeds"], bn, bt, txh, li))
        elif event == "Withdrawn":
            cur.execute(
                "INSERT INTO dog_withdrawals (account, amount_wei, block_number, block_time,"
                " tx_hash, log_index) VALUES (%s, %s, %s, %s, %s, %s)"
                " ON CONFLICT (tx_hash, log_index) DO NOTHING",
                (h2b(p["account"]), p["amount"], bn, bt, txh, li))


def resolve_seeds(conn, rpc, safe_block, log=lambda *a: None):
    """Fill dogs.seed for dogs whose target block (commit+4) is behind the safe
    block. Hash source: a stored Snapshot event, else the node while the target
    is within LIVE_HASH_WINDOW of head (the contract can read it too). Older
    targets with no Snapshot stay NULL and the API reports status "check", so
    clients ask the chain (the contract may still have the hash via EIP-2935).
    Never raises: a failed RPC just leaves the dog pending until the next pass."""
    fetched = 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT token_id, commit_block, rerolls FROM dogs"
                " WHERE seed IS NULL AND commit_block + %s < %s"
                " ORDER BY commit_block LIMIT 500", (SEED_DELAY, safe_block))
            pending = cur.fetchall()
            if not pending:
                conn.rollback()
                return 0
            targets = sorted({c + SEED_DELAY for _t, c, _r in pending})
            try:
                head = rpc.block_number()   # the contract's "live" window is relative to the real head
            except Exception:  # noqa: BLE001
                head = safe_block + CONFIRMATIONS
            cur.execute("SELECT block_number, block_hash FROM dog_snapshots"
                        " WHERE block_number = ANY(%s)", (targets,))
            hashes = {b: bytes(h) for b, h in cur.fetchall()}
            for tb in targets:
                if tb in hashes or head - tb > LIVE_HASH_WINDOW or fetched >= MAX_BLOCK_FETCH:
                    continue
                fetched += 1
                blk = rpc.get_block(tb)
                if blk and blk.get("hash"):
                    hashes[tb] = h2b(blk["hash"])
            done = 0
            for token_id, commit_block, rerolls in pending:
                h = hashes.get(commit_block + SEED_DELAY)
                if h is None:
                    continue
                cur.execute("UPDATE dogs SET seed = %s, seed_block = %s"
                            " WHERE token_id = %s AND commit_block = %s AND rerolls = %s"
                            " AND seed IS NULL",
                            (seed_of(h, token_id, rerolls), safe_block, token_id, commit_block, rerolls))
                done += cur.rowcount
        conn.commit()
        return done
    except Exception as e:  # noqa: BLE001 - best effort, retried next pass
        conn.rollback()
        log("dog seed pass skipped:", repr(e))
        return 0
