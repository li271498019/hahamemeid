"""Merkle root recomputation for season-1 days.

Same algorithm as /opt/haha-season1/tools/season1/merkle.py
(haha-season1-merkle-v1), verified against the deployed OpenZeppelin
MerkleProof.verify:

    leaf = keccak256(keccak256(abi.encode(bytes32 aiId, uint256 balance, uint8 tier)))
    pair: sort the two 32-byte nodes as raw bytes, keccak256(smaller + larger)
    odd node: carried up unchanged, never paired with itself
    one leaf: root is that leaf. empty set: root is 32 zero bytes.

Entries are read from season1_entries ordered by ai_id bytes ascending.
"""

from common import keccak256


def _word_uint(n):
    return int(n).to_bytes(32, "big")


def leaf_hash(ai_id, balance, tier):
    """ai_id: 32-byte bytes (or hex str). balance/tier: int."""
    if isinstance(ai_id, str):
        ai = bytes.fromhex(ai_id[2:] if ai_id.startswith("0x") else ai_id)
    else:
        ai = bytes(ai_id)
    encoded = _word_uint(int.from_bytes(ai, "big")) + _word_uint(balance) + _word_uint(tier)
    return keccak256(keccak256(encoded))


def _commutative_keccak(a, b):
    return keccak256(a + b) if a < b else keccak256(b + a)


def merkle_root(entries):
    """entries: iterable of (ai_id bytes, balance int, tier int), sorted by ai_id.
    Returns the 32-byte root. Empty set -> 32 zero bytes."""
    leaves = [leaf_hash(ai, bal, tier) for ai, bal, tier in entries]
    if not leaves:
        return b"\x00" * 32
    level = leaves
    while len(level) > 1:
        nxt = []
        i = 0
        while i < len(level):
            if i + 1 == len(level):
                nxt.append(level[i])
                break
            nxt.append(_commutative_keccak(level[i], level[i + 1]))
            i += 2
        level = nxt
    return level[0]


def recompute_day_root(cur, day_index):
    """Read a day's entries and compute its Merkle root.

    Returns the 32-byte root, or None when the day has no entries yet
    (snapshot not written). Never raises on empty input.
    """
    cur.execute(
        "SELECT ai_id, balance, tier FROM season1_entries"
        " WHERE day_index = %s ORDER BY ai_id",
        (day_index,))
    rows = cur.fetchall()
    if not rows:
        return None
    entries = [(bytes(ai), int(bal), int(tier)) for ai, bal, tier in rows]
    return merkle_root(entries)
