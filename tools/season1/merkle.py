"""Snapshot lock, points replay, eligibility, and the production Merkle tree.

Algorithm version `haha-season1-merkle-v2` (from day 20782, 2026-11-25).
v2 adds the rotation rule: an aiId that was in a previous day's snapshot but
did not apply is EXCLUDED from primary selection; the slot goes to the next
aiId behind it with balance >= PRICE. If the fresh pool is short of
DAILY_MAX, the excluded aiIds fill the remaining slots by a deterministic
random draw seeded by the snapshot block hash (public, reproducible).
The tree itself is unchanged: 3-leaf proof already passed the deployed
OpenZeppelin `MerkleProof.verify`. Do not switch it to hashing an odd node
with itself.

Leaf, in entry order. Production entries are sorted by raw aiId bytes ascending
before this function runs:

    inner = keccak256(abi.encode(bytes32 aiId, uint256 balance, uint8 tier))
    leaf  = keccak256(inner)

Pair: sort the two 32-byte nodes as raw bytes, then
keccak256(abi.encodePacked(smaller, larger)).

Odd node: carry that node up unchanged. Do not pair it with itself.
One leaf: the root is that leaf. Empty: root is 32 zero bytes.
"""

ALGORITHM_VERSION = "haha-season1-merkle-v2"
BLOCKHASH_DEPTH = 256

import json
import random

from tools.season1.constants import (
    CANDIDATE_NAMES,
    DAILY_MAX,
    EXCLUDED_ORDER_STATUSES,
    POINTS,
    PRICE,
    SEASON_ID,
    SNAPSHOT_CONFIRMATIONS,
)
from tools.season1.hashutil import commutative_keccak, hex32, keccak256, leaf_hash


def lock_snapshot_block(headers, boundary_ts):
    """headers: iterable of {number:int, timestamp:int, hash:str} on the current chain.

    Returns the header with the greatest number whose timestamp is <= boundary_ts.
    Confirmation depth is not consulted here.
    """
    chosen = None
    for header in headers:
        if int(header["timestamp"]) <= int(boundary_ts):
            if chosen is None or int(header["number"]) > int(chosen["number"]):
                chosen = header
    return chosen


def snapshot_ready(head_number, snapshot_number, confirmations=SNAPSHOT_CONFIRMATIONS):
    """True only when that exact block has `confirmations` blocks after it."""
    return int(head_number) >= int(snapshot_number) + int(confirmations)


def root_publish_precheck(head_number, snapshot_number, confirmations=SNAPSHOT_CONFIRMATIONS):
    """Whether the merged contract will accept setDayRoot for this snapshot.

    HahaSeason1 rejects when block.number >= snapshotBlock + 256 (StaleSnapshot).
    That is one block stricter than the EVM rule, where blockhash(head-256) can
    still be non-zero and blockhash(head-257) is zero. This check follows the
    contract so a root is not offered when the transaction would revert.
    remainingBlocks is a block count, not a clock time. It does not select an
    earlier snapshot and it does not move the season dates.
    """
    head = int(head_number)
    snap = int(snapshot_number)
    remaining = snap + BLOCKHASH_DEPTH - head
    ready = snapshot_ready(head, snap, confirmations)
    if snap >= head:
        return {"ok": False, "reason": "snapshot-not-past", "remainingBlocks": remaining, "confirmationsReady": ready}
    if not ready:
        return {"ok": False, "reason": "confirmations", "remainingBlocks": remaining, "confirmationsReady": False}
    if remaining <= 0:
        return {"ok": False, "reason": "blockhash-expired", "remainingBlocks": remaining, "confirmationsReady": True}
    return {"ok": True, "reason": None, "remainingBlocks": remaining, "confirmationsReady": True}


def replay_balances(points_logs, snapshot_block):
    """Last newBalance at or before snapshot_block. Drop aiId zero.

    points_logs items: {block:int, logIndex:int, aiId:str, newBalance:int}.
    A log after the snapshot does not change the result.
    """
    ordered = sorted(points_logs, key=lambda row: (int(row["block"]), int(row["logIndex"])))
    balances = {}
    for row in ordered:
        if int(row["block"]) > int(snapshot_block):
            continue
        ai = hex32(row["aiId"])
        if int(ai, 16) == 0:
            continue
        balances[ai] = int(row["newBalance"])
    return balances


def eligible_entries(balances, orders, previously_qualified=None, random_seed=None):
    """Eligibility with the v2 rotation rule (from day 20782).

    orders: iterable of {aiId, status}. Pending, Fulfilled, and CreditOpen are out.
    previously_qualified: iterable of aiIds that were in a previous day's
        snapshot entries but have no order (they qualified before and did not
        apply). They are EXCLUDED from primary selection; the slot goes to the
        next aiId behind them with balance >= PRICE. Priority is the fresh
        pool. If the fresh selection is short of DAILY_MAX, the excluded aiIds
        fill the remaining slots by a deterministic random draw.
    random_seed: seed for the deterministic random fill. The snapshot script
        passes the snapshot block hash, so anyone can reproduce the draw.
        When None, no random fill happens (fresh-only).

    Returns (entries, reserved_count, remaining_slots, stats) where stats is
    {"freshCount", "expiredCount", "randomFilled"} for the manifest/report.
    """
    blocked = set()
    for order in orders:
        if order["status"] in EXCLUDED_ORDER_STATUSES:
            blocked.add(hex32(order["aiId"]))
    expired_ids = set()
    if previously_qualified:
        expired_ids = {hex32(ai) for ai in previously_qualified}
    fresh_pool = []
    expired_pool = []
    for ai, balance in balances.items():
        if balance < PRICE or ai in blocked:
            continue
        row = {"aiId": ai, "balance": int(balance)}
        if ai in expired_ids:
            expired_pool.append(row)
        else:
            fresh_pool.append(row)
    fresh_pool.sort(key=lambda row: (-row["balance"], row["aiId"]))
    expired_pool.sort(key=lambda row: (-row["balance"], row["aiId"]))
    stats = {
        "freshCount": len(fresh_pool),
        "expiredCount": len(expired_pool),
        "randomFilled": 0,
    }
    if not fresh_pool and not expired_pool:
        return [], 0, 0, stats
    # Primary selection: fresh pool only, original cutoff logic.
    entries = []
    reserved = 0
    remaining = 0
    if len(fresh_pool) <= DAILY_MAX:
        for row in fresh_pool:
            row["tier"] = 0
        entries = list(fresh_pool)
        reserved = len(entries)
        remaining = 0
    else:
        cutoff = fresh_pool[DAILY_MAX - 1]["balance"]
        r = [row for row in fresh_pool if row["balance"] > cutoff]
        b = [row for row in fresh_pool if row["balance"] == cutoff]
        for row in r:
            row["tier"] = 0
        for row in b:
            row["tier"] = 1
        entries = r + b
        reserved = len(r)
        remaining = DAILY_MAX - len(r)
    # Random fill: if the fresh selection is short of DAILY_MAX, draw from
    # the expired pool (deterministic seed) up to DAILY_MAX total entries.
    # The expired pool is already in a deterministic order, so the draw is
    # reproducible from the seed alone.
    if len(entries) < DAILY_MAX and expired_pool and random_seed is not None:
        need = DAILY_MAX - len(entries)
        rng = random.Random(random_seed)
        k = min(need, len(expired_pool))
        picked = rng.sample(expired_pool, k)
        for row in picked:
            row["tier"] = 0
        entries = entries + picked
        stats["randomFilled"] = k
        reserved = len([row for row in entries if row["tier"] == 0])
        remaining = 0
    entries.sort(key=lambda row: bytes.fromhex(row["aiId"][2:]))
    return entries, reserved, remaining, stats


def merkle_root_and_proofs(entries):
    leaves = [leaf_hash(row["aiId"], row["balance"], row["tier"]) for row in entries]
    if not leaves:
        return "0x" + "00" * 32, {}
    layers = [leaves]
    while len(layers[-1]) > 1:
        level = layers[-1]
        nxt = []
        i = 0
        while i < len(level):
            if i + 1 == len(level):
                nxt.append(level[i])
                break
            nxt.append(commutative_keccak(level[i], level[i + 1]))
            i += 2
        layers.append(nxt)
    proofs = {}
    for index, leaf in enumerate(leaves):
        proof = []
        cursor = index
        for level in layers[:-1]:
            sibling = cursor ^ 1
            if sibling < len(level):
                proof.append("0x" + level[sibling].hex())
            cursor //= 2
        proofs[entries[index]["aiId"]] = proof
    return "0x" + layers[-1][0].hex(), proofs


def verify_proof(leaf: bytes, proof, root: str) -> bool:
    computed = leaf
    for sibling in proof:
        computed = commutative_keccak(computed, bytes.fromhex(sibling[2:]))
    return "0x" + computed.hex() == root


def canonical_manifest(day_index, boundary_ts, snapshot, module, entries, root, reserved, remaining, stats=None, random_seed=None):
    body = {
        "seasonId": SEASON_ID,
        "algorithmVersion": ALGORITHM_VERSION,
        "dayIndex": int(day_index),
        "boundaryTs": int(boundary_ts),
        "snapshotBlock": int(snapshot["number"]) if snapshot else 0,
        "snapshotBlockHash": snapshot["hash"] if snapshot else "0x" + "00" * 32,
        "points": POINTS,
        "module": module or "0x" + "00" * 32,
        "reservedCount": reserved,
        "remainingSlots": remaining,
        "freshCount": int((stats or {}).get("freshCount", 0)),
        "expiredCount": int((stats or {}).get("expiredCount", 0)),
        "randomFilled": int((stats or {}).get("randomFilled", 0)),
        "randomSeed": random_seed if random_seed is not None else None,
        "root": root,
        "entries": [
            {"aiId": row["aiId"], "balance": str(row["balance"]), "tier": row["tier"]}
            for row in sorted(entries, key=lambda row: bytes.fromhex(row["aiId"][2:]))
        ],
    }
    raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return body, raw, "0x" + keccak256(raw).hex()


def roots_match(admin_root, recomputed_root) -> bool:
    return (admin_root or "").lower() == (recomputed_root or "").lower() and admin_root not in (None, "")


def candidate_count():
    """1552 labels across two suffixes. This is not a count of unminted names."""
    return CANDIDATE_NAMES
