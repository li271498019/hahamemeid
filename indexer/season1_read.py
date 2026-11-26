"""Read models for the season-1 GET routes. No writes and no RPC."""

from common import decode_log

from season1_merkle import recompute_day_root


def hx(value):
    if value is None:
        return None
    return "0x" + bytes(value).hex()


def day_row(cur, day_index):
    cur.execute(
        "SELECT merkle_root, snapshot_block, snapshot_block_hash, reserved_count,"
        " remaining_slots, opened, recomputed_root, confirmations_seen"
        " FROM season1_days WHERE day_index = %s",
        (day_index,))
    row = cur.fetchone()
    if row is None:
        return None
    root, snap, snap_hash, reserved, remaining, opened, recomputed, seen = row
    if recomputed is None:
        # Safety net: the syncer writes recomputed_root when DayRootSet lands,
        # but if the snapshot entries arrived after it, recompute here instead.
        try:
            recomputed = recompute_day_root(cur, day_index)
        except Exception:
            recomputed = None
    # confirmations_seen is live: the checkpoint is the indexer's safe head.
    try:
        cur.execute("SELECT safe_block FROM checkpoint WHERE id = 1")
        _head = cur.fetchone()
        seen = max(0, int(_head[0]) - int(snap)) if _head and _head[0] is not None else int(seen or 0)
    except Exception:
        seen = int(seen or 0)
    cur.execute(
        "SELECT tier, count(*) FROM season1_orders"
        " WHERE day_index = %s AND status IN ('Pending','Fulfilled')"
        " GROUP BY tier",
        (day_index,))
    filled = {tier: count for tier, count in cur.fetchall()}
    match = recomputed is not None and bytes(recomputed) == bytes(root)
    return {
        "dayIndex": int(day_index),
        "merkleRoot": hx(root),
        "recomputedRoot": hx(recomputed),
        "rootMatch": bool(match),
        "snapshotBlock": int(snap),
        "snapshotBlockHash": hx(snap_hash),
        "confirmationsRequired": 15,
        "confirmationsSeen": int(seen or 0),
        "reservedCount": int(reserved),
        "remainingSlots": int(remaining),
        "reservedFilled": int(filled.get(0, 0)),
        "boundaryFilled": int(filled.get(1, 0)),
        "opened": bool(opened),
    }


def eligibility_row(cur, ai_id, day_index):
    cur.execute(
        "SELECT status FROM season1_orders WHERE day_index = %s AND ai_id = %s"
        " ORDER BY order_id DESC LIMIT 1",
        (day_index, ai_id))
    order = cur.fetchone()
    cur.execute(
        "SELECT balance, tier FROM season1_entries WHERE day_index = %s AND ai_id = %s",
        (day_index, ai_id))
    entry = cur.fetchone()
    cur.execute("SELECT balance FROM points WHERE ai_id = %s", (ai_id,))
    now = cur.fetchone()
    balance_now = None if now is None else str(now[0])
    if order and order[0] in ("Pending", "CreditOpen"):
        status, reason = "excluded", "pending"
    elif order and order[0] == "Fulfilled":
        status, reason = "excluded", "fulfilled"
    elif entry is None:
        status, reason = "excluded", "below-cutoff"
    elif int(entry[1]) == 0:
        status, reason = "reserved", None
    else:
        status, reason = "boundary", None
    return {
        "status": status,
        "reason": reason,
        "balance": None if entry is None else str(entry[0]),
        "balanceNow": balance_now,
    }


def proof_row(cur, ai_id, day_index):
    """Merkle proof for one eligible .ai on one day.

    The proof is stored by snapshot_day.py alongside the entry, computed
    from the same tree that produced the day root. Returns None when this
    .ai has no entry that day (not eligible).
    """
    cur.execute(
        "SELECT balance, tier, proof FROM season1_entries"
        " WHERE day_index = %s AND ai_id = %s",
        (day_index, ai_id))
    entry = cur.fetchone()
    if entry is None:
        return None
    cur.execute(
        "SELECT merkle_root FROM season1_days WHERE day_index = %s",
        (day_index,))
    day = cur.fetchone()
    return {
        "aiId": hx(ai_id),
        "dayIndex": int(day_index),
        "balance": str(entry[0]),
        "tier": int(entry[1]),
        "root": hx(day[0]) if day else None,
        "proof": entry[2] if entry[2] is not None else [],
    }


def tx_logs(cur, tx_hash):
    cur.execute(
        "SELECT address, topics, data FROM raw_logs WHERE tx_hash = %s",
        (tx_hash,))
    found = []
    for addr, topics, data in cur.fetchall():
        event, params = decode_log("0x" + bytes(addr).hex(), topics, bytes(data))
        if event:
            params = dict(params)
            params["event"] = event
            params["txHash"] = hx(tx_hash)
            found.append(params)
    return found


def log_check(order, logs):
    if not order.get("mintTx"):
        return "not-minted"
    if not logs:
        return "unknown"
    token_id = int(order["tokenId"])
    recipient = order["recipient"].lower()
    minted = transferred = False
    for log in logs:
        if log.get("event") == "NameMinted" and int(log["tokenId"]) == token_id \
                and log["owner"].lower() == recipient and log["label"] == order["label"] \
                and int(log["tld"]) == int(order["tld"]) and log["reservedMint"] is True:
            minted = True
        if log.get("event") == "Transfer" and log["from"].lower() == "0x" + "00" * 20 \
                and log["to"].lower() == recipient and int(log["tokenId"]) == token_id:
            transferred = True
    return "matched" if minted and transferred else "mismatch"


def order_dict(row, logs=None):
    (oid, ai, applicant, recipient, label, tld, tier, status, mint_tx, token_id) = row
    body = {
        "orderId": str(oid),
        "aiId": hx(ai),
        "applicant": hx(applicant),
        "recipient": hx(recipient),
        "label": label,
        "tld": int(tld),
        "tier": "Reserved" if int(tier) == 0 else "Boundary",
        "status": status,
        "mintTx": hx(mint_tx),
        "tokenId": None if token_id is None else str(token_id),
    }
    body["logCheck"] = log_check(body, logs)
    return body


def _with_logs(cur, row):
    mint_tx = row[8]
    logs = tx_logs(cur, mint_tx) if mint_tx is not None else None
    return order_dict(row, logs)


def orders_for_day(cur, day_index, limit):
    cur.execute(
        "SELECT order_id, ai_id, applicant, recipient, label, tld, tier, status,"
        " mint_tx, token_id FROM season1_orders WHERE day_index = %s ORDER BY order_id"
        " LIMIT %s",
        (day_index, limit))
    return [_with_logs(cur, row) for row in cur.fetchall()]


def order_by_id(cur, order_id):
    cur.execute(
        "SELECT order_id, ai_id, applicant, recipient, label, tld, tier, status,"
        " mint_tx, token_id FROM season1_orders WHERE order_id = %s",
        (order_id,))
    row = cur.fetchone()
    return None if row is None else _with_logs(cur, row)


def leaderboard_rows(cur, day_index, limit):
    """Per-person season leaderboard for one day (the daily ranking).

    One row per Merkle entry, in the same scope as the day's selection
    (reservedCount): real entrants first, ranked by snapshot balance
    DESC (ai_id ASC breaks ties), mirroring /v1/leaderboard/points
    ({rank, aiId, handle, name, balance}), then the invalid snapshot
    leaves (if any) unranked at the end.

    An entry is valid iff its aiId exists in `points`. The known dirty
    leaves have aiIds that are ASCII reason strings ("ACTIVATE",
    "REVIEW_RECEIVE") or the module address itself: they come from
    non-PointsChanged config events the snapshot replay mistook for
    PointsChanged (it never checked topic0), and they never appear in
    `points`, so valid=false and rank=null. Their fake balance is the
    raw Merkle leaf value; callers should not display it as points.

    Each row also carries the person's application and issuance for
    that day (LEFT JOIN season1_orders): the domain they applied for,
    the applyFor tx hash (the application hash), the points spent
    (-200, the order price) and its tx hash (the spend happens inside
    the applyFor tx, so spendTx == applyTx), whether the name was
    issued, and the adminMint tx hash when it was.
    """
    cur.execute(
        "SELECT e.ai_id, p.ai_id AS in_points, p.handle, e.balance, e.tier,"
        " (SELECT n.full_name FROM names n WHERE n.mint_ai_id = e.ai_id"
        " ORDER BY n.mint_block ASC, n.token_id ASC LIMIT 1) AS first_name,"
        " o.label, o.tld, o.status, o.tx_hash, o.mint_tx, o.price"
        " FROM season1_entries e"
        " LEFT JOIN points p ON p.ai_id = e.ai_id"
        " LEFT JOIN season1_orders o ON o.day_index = e.day_index AND o.ai_id = e.ai_id"
        " WHERE e.day_index = %s"
        " ORDER BY (p.ai_id IS NULL), e.balance DESC, e.ai_id ASC"
        " LIMIT %s",
        (day_index, limit))
    out = []
    rank = 0
    for row in cur.fetchall():
        (ai, in_points, handle, balance, tier, first_name, label, tld,
         status, tx_hash, mint_tx, price) = row
        valid = in_points is not None
        if valid:
            rank += 1
        applied = label is not None
        out.append({
            "rank": int(rank) if valid else None,
            "valid": bool(valid),
            "aiId": hx(ai),
            "handle": handle,
            "name": first_name,
            # I4: a dirty leaf (valid=false) carries a fake balance from
            # the raw Merkle leaf value — report null so no consumer
            # mistakes it for real points. rank stays null as before.
            "balance": str(int(balance)) if valid else None,
            "tier": "Reserved" if int(tier) == 0 else "Boundary",
            "appliedName": (label + (".meme" if int(tld) == 1 else ".haha")) if applied else None,
            "applyTx": hx(tx_hash) if applied else None,
            "pointsSpent": -int(price) if applied else None,
            "spendTx": hx(tx_hash) if applied else None,
            "status": status if applied else None,
            "issued": bool(applied and status == "Fulfilled"),
            "mintTx": hx(mint_tx) if (applied and mint_tx is not None) else None,
        })
    return out


def verify_row(cur, ai_id, day_index):
    cur.execute(
        "SELECT task_pack_hash FROM season1_task_packs WHERE day_index = %s",
        (day_index,))
    pack = cur.fetchone()
    cur.execute(
        "SELECT verdict, task_pack_hash, points FROM season1_verifications"
        " WHERE ai_id = %s AND day_index = %s",
        (ai_id, day_index))
    row = cur.fetchone()
    if row is None:
        return {
            "claimed": False,
            "taskPackHash": None if pack is None else hx(pack[0]),
            "verdict": None,
            "points": 0,
        }
    return {
        "claimed": True,
        "taskPackHash": hx(row[1]),
        "verdict": "Match" if int(row[0]) == 0 else "Discrepancy",
        "points": int(row[2]),
    }


def finding_row(cur, digest, withheld_hashes):
    cur.execute(
        "SELECT commit_block, tx_index, log_index, canonical_id, paid, withheld"
        " FROM season1_findings WHERE report_evidence_hash = %s",
        (digest,))
    row = cur.fetchone()
    if row is None:
        return None
    withheld = bool(row[5]) or hx(digest) in withheld_hashes
    if withheld:
        return {"withheld": True}
    return {
        "withheld": False,
        "commitBlock": None if row[0] is None else int(row[0]),
        "txIndex": None if row[1] is None else int(row[1]),
        "logIndex": None if row[2] is None else int(row[2]),
        "canonicalAssigned": row[3] is not None,
        "canonicalPaid": bool(row[4]),
    }


def findings_rows(cur):
    """All season-1 findings, earliest commit first.

    One row per FindingCommitted, ordered by (commitBlock, txIndex,
    logIndex) — the on-chain order, which is also the priority order
    when two findings share a root cause. The submitter is resolved
    to their .ai handle (from `points`) and first minted name (from
    `names`), mirroring leaderboard_rows; the website displays only
    the .ai handle. commitTime is NOT here (this module does no RPC);
    the api handler enriches it from the block header.
    """
    cur.execute(
        "SELECT f.report_evidence_hash, f.commit_hash, f.ai_id,"
        " p.handle,"
        " (SELECT n.full_name FROM names n WHERE n.mint_ai_id = f.ai_id"
        " ORDER BY n.mint_block ASC, n.token_id ASC LIMIT 1) AS first_name,"
        " f.commit_block, f.tx_index, f.log_index,"
        " f.canonical_id, f.paid,"
        " r.report_id, r.title, r.content"
        " FROM season1_findings f"
        " LEFT JOIN points p ON p.ai_id = f.ai_id"
        " LEFT JOIN season1_finding_reports r"
        " ON r.report_evidence_hash = f.report_evidence_hash"
        " ORDER BY f.commit_block ASC, f.tx_index ASC, f.log_index ASC"
    )
    out = []
    for row in cur.fetchall():
        (digest, commit_hash, ai, handle, first_name, block, txi, li,
         canonical_id, paid, report_id, report_title, report_content) = row
        out.append({
            "reportEvidenceHash": hx(digest),
            "commitHash": hx(commit_hash),
            "aiId": hx(ai),
            "handle": handle,
            "name": first_name,
            "commitBlock": int(block),
            "commitTime": None,  # enriched by the api handler via RPC
            "commitTx": None,  # enriched by the api handler via RPC
            "txIndex": int(txi) if txi is not None else None,
            "logIndex": int(li) if li is not None else None,
            "canonicalAssigned": canonical_id is not None,
            "canonicalPaid": bool(paid),
            "reportId": report_id,
            "reportTitle": report_title,
            "reportContent": report_content,
        })
    return out
