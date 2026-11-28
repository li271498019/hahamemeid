"""JSON shapes for the six read routes. fixture/note are sample metadata, not API fields."""

ORDER_KEYS = (
    "orderId", "aiId", "applicant", "recipient", "label", "tld", "tier",
    "status", "mintTx", "tokenId", "simError", "logCheck",
)
DAY_KEYS = (
    "dayIndex", "merkleRoot", "recomputedRoot", "rootMatch", "snapshotBlock",
    "snapshotBlockHash", "confirmationsRequired", "confirmationsSeen",
    "reservedCount", "remainingSlots", "reservedFilled", "boundaryFilled", "opened",
)


def day_view(row):
    return {key: row[key] for key in DAY_KEYS}


def eligibility_view(ai_id, day_index, status, reason, balance, balance_now):
    if status not in ("none", "reserved", "boundary", "excluded"):
        raise ValueError(status)
    if reason not in (None, "balance", "pending", "fulfilled", "below-cutoff"):
        raise ValueError(reason)
    return {
        "aiId": ai_id,
        "dayIndex": int(day_index),
        "status": status,
        "reason": reason,
        "balance": None if balance is None else str(balance),
        "balanceNow": None if balance_now is None else str(balance_now),
    }


def order_view(row):
    out = {key: row.get(key) for key in ORDER_KEYS}
    out["orderId"] = str(out["orderId"])
    out["tld"] = int(out["tld"])
    if out["tokenId"] is not None:
        out["tokenId"] = str(out["tokenId"])
    return out


def orders_view(rows):
    return {"dayIndex": rows["dayIndex"], "orders": [order_view(row) for row in rows["orders"]]}


def verify_view(row):
    out = {
        "aiId": row["aiId"],
        "dayIndex": int(row["dayIndex"]),
        "claimed": bool(row["claimed"]),
        "taskPackHash": row.get("taskPackHash"),
        "verdict": row.get("verdict"),
        "points": int(row["points"]),
    }
    if row.get("queue"):
        out["queue"] = row["queue"]
    if out["claimed"] and out["points"] != 30:
        raise ValueError("a paid verification is 30 points")
    if not out["claimed"] and out["points"] != 0:
        raise ValueError("an unpaid verification stores 0")
    return out


def finding_view(row, withheld_hashes):
    digest = row["reportEvidenceHash"]
    if row.get("withheld") or digest in withheld_hashes:
        return {"reportEvidenceHash": digest, "withheld": True}
    return {
        "reportEvidenceHash": digest,
        "withheld": False,
        "commitBlock": row.get("commitBlock"),
        "txIndex": row.get("txIndex"),
        "logIndex": row.get("logIndex"),
        "canonicalAssigned": bool(row.get("canonicalAssigned")),
        "canonicalPaid": bool(row.get("canonicalPaid")),
    }
