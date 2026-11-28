"""In-memory season log replay. The SQL applier uses the same status names.

Replaying a prefix of the log twice does not create a second order or a second review.
MintConfirmed is ignored. FulfillmentAttested alone does not mean the name was minted.
"""

from tools.season1.hashutil import hex32


def replay(logs):
    orders = {}
    days = {}
    verifications = {}
    findings = {}
    reviews = {}
    task_packs = {}
    validators = {}
    reward_signer = {}
    for log in logs:
        event = log["event"]
        if event == "MintConfirmed":
            continue
        if event == "Rated":
            reviews[(log["agentId"], log["raterAiId"])] = {
                "stars": log["stars"],
                "review": log["review"],
                "block": log["block"],
            }
        elif event == "DayRootSet":
            days[int(log["dayIndex"])] = {
                "merkleRoot": log["merkleRoot"],
                "snapshotBlock": int(log["snapshotBlock"]),
                "snapshotBlockHash": log["snapshotBlockHash"],
                "reservedCount": int(log["reservedCount"]),
                "remainingSlots": int(log["remainingSlots"]),
                "opened": True,
                "block": log["block"],
            }
        elif event == "Redeemed":
            oid = str(log["orderId"])
            if oid in orders:
                continue
            orders[oid] = {
                "orderId": oid,
                "aiId": hex32(log["aiId"]),
                "applicant": log["applicant"],
                "recipient": log["recipient"],
                "label": log["label"],
                "tld": int(log["tld"]),
                "tier": "Reserved" if int(log["tier"]) == 0 else "Boundary",
                "status": "Pending",
                "mintTx": None,
                "tokenId": str(log["tokenId"]),
                "dayIndex": int(log["dayIndex"]),
                "block": log["block"],
                "txIndex": log["txIndex"],
                "logIndex": log["logIndex"],
            }
        elif event == "FulfillmentAttested":
            order = orders.get(str(log["orderId"]))
            if order and order["status"] == "Pending":
                order["status"] = "Fulfilled"
                order["mintTx"] = log["mintTxHash"]
                order["tokenId"] = str(log["tokenId"])
        elif event == "Verified":
            key = (hex32(log["aiId"]), int(log["dayIndex"]))
            if key in verifications:
                continue
            verifications[key] = {
                "points": int(log["points"]),
                "verdict": "Match" if int(log["verdict"]) == 0 else "Discrepancy",
                "taskPackHash": log["taskPackHash"],
            }
        elif event == "TaskPackSet":
            task_packs[int(log["dayIndex"])] = log["taskPackHash"]
        elif event == "FindingCommitted":
            h = hex32(log["reportEvidenceHash"])
            findings.setdefault(h, {"withheld": False, "canonicalAssigned": False, "canonicalPaid": False})
            findings[h].update({
                "reportEvidenceHash": h,
                "commitBlock": int(log["block"]),
                "txIndex": int(log["txIndex"]),
                "logIndex": int(log["logIndex"]),
                "aiId": hex32(log["aiId"]),
            })
        elif event == "CanonicalAssigned":
            h = hex32(log["reportEvidenceHash"])
            findings.setdefault(h, {"withheld": False, "canonicalPaid": False})
            findings[h]["canonicalAssigned"] = True
            findings[h]["canonicalId"] = hex32(log["canonicalRootCauseId"])
        elif event == "FindingPaid":
            h = hex32(log["reportEvidenceHash"])
            findings.setdefault(h, {"withheld": False, "canonicalAssigned": True})
            if not findings[h].get("canonicalPaid"):
                findings[h]["canonicalPaid"] = True
        elif event == "AccidentDeclared":
            order = orders.get(str(log["orderId"]))
            if order and order["status"] == "Pending":
                order["evidenceHash"] = log["evidenceHash"]
                order["status"] = "CreditOpen"
                # applicant and aiId stay on the original order
        elif event == "AccidentRefunded":
            order = orders.get(str(log["orderId"]))
            if order and order["status"] in ("Pending", "CreditOpen"):
                order["status"] = "AccidentRefunded"
                order["refunded"] = True
        elif event == "AccidentCompensationDeferred":
            order = orders.get(str(log["orderId"]))
            if order:
                order["deferred"] = True
        elif event == "AccidentCompensated":
            order = orders.get(str(log["orderId"]))
            if order and not order.get("compensated"):
                order["compensated"] = True
                order["status"] = "AccidentClosed"
        elif event == "ValidatorSet":
            validators[log["account"].lower()] = bool(log["allowed"])
        elif event == "RewardSignerSet":
            reward_signer["account"] = log["account"].lower()
    return {
        "orders": orders,
        "days": days,
        "verifications": verifications,
        "findings": findings,
        "reviews": reviews,
        "taskPacks": task_packs,
        "validators": validators,
        "rewardSigner": reward_signer,
    }


def drop_after(logs, block):
    return [log for log in logs if int(log["block"]) <= int(block)]
