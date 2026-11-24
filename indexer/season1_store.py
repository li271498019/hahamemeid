"""Apply season-1 logs. The module address is injected; nothing here is a deployed address."""

from common import keccak256, topic0

from season1_merkle import recompute_day_root

HAHA_NODE = bytes.fromhex("aa5a3a58f7c8841455eecaa0c6a6a0b40ace5681fbb31361a0d45b168179128f")
MEME_NODE = bytes.fromhex("74df4ab2564a9f9bb6d4b6b77bf4fc02ac80f07bd9e1776d3967578b3fc36be4")

# name, signature, [(field, type, indexed)]
EVENT_DEFS = [
    ("DayRootSet", "DayRootSet(uint64,bytes32,uint64,bytes32,uint16,uint16)", [
        ("dayIndex", "uint64", True), ("merkleRoot", "bytes32", False),
        ("snapshotBlock", "uint64", False), ("snapshotBlockHash", "bytes32", False),
        ("reservedCount", "uint16", False), ("remainingSlots", "uint16", False),
    ]),
    ("Redeemed", "Redeemed(uint256,bytes32,address,address,uint8,string,uint64,uint8,uint256,bytes32)", [
        ("orderId", "uint256", True), ("aiId", "bytes32", True), ("applicant", "address", True),
        ("recipient", "address", False), ("tld", "uint8", False), ("label", "string", False),
        ("dayIndex", "uint64", False), ("tier", "uint8", False), ("price", "uint256", False),
        ("root", "bytes32", False),
    ]),
    ("FulfillmentAttested", "FulfillmentAttested(uint256,uint256,address,bytes32)", [
        ("orderId", "uint256", True), ("tokenId", "uint256", True), ("recipient", "address", True),
        ("mintTxHash", "bytes32", False),
    ]),
    ("Verified", "Verified(bytes32,uint64,uint256,uint64,uint8,bytes32,uint256)", [
        ("aiId", "bytes32", True), ("dayIndex", "uint64", True), ("agentId", "uint256", True),
        ("generation", "uint64", False), ("verdict", "uint8", False),
        ("taskPackHash", "bytes32", False), ("points", "uint256", False),
    ]),
    ("FindingCommitted", "FindingCommitted(bytes32,bytes32,address,bytes32)", [
        ("commitHash", "bytes32", True), ("aiId", "bytes32", True), ("committer", "address", True),
        ("reportEvidenceHash", "bytes32", False),
    ]),
    ("CanonicalAssigned", "CanonicalAssigned(bytes32,bytes32)", [
        ("reportEvidenceHash", "bytes32", True), ("canonicalRootCauseId", "bytes32", True),
    ]),
    ("FindingPaid", "FindingPaid(bytes32,bytes32,bytes32,address,uint256)", [
        ("canonicalRootCauseId", "bytes32", True), ("reportEvidenceHash", "bytes32", True),
        ("aiId", "bytes32", True), ("recipient", "address", False), ("points", "uint256", False),
    ]),
    ("TaskPackSet", "TaskPackSet(uint64,bytes32)", [
        ("dayIndex", "uint64", True), ("taskPackHash", "bytes32", False),
    ]),
    ("AccidentDeclared", "AccidentDeclared(uint256,bytes32,address,bytes32)", [
        ("orderId", "uint256", True), ("aiId", "bytes32", True), ("applicant", "address", True),
        ("evidenceHash", "bytes32", False),
    ]),
    ("AccidentRefunded", "AccidentRefunded(uint256,bytes32,uint256)", [
        ("orderId", "uint256", True), ("aiId", "bytes32", True), ("amount", "uint256", False),
    ]),
    ("AccidentCompensationDeferred", "AccidentCompensationDeferred(uint256,bytes32)", [
        ("orderId", "uint256", True), ("aiId", "bytes32", True),
    ]),
    ("AccidentCompensated", "AccidentCompensated(uint256,bytes32,uint256)", [
        ("orderId", "uint256", True), ("aiId", "bytes32", True), ("amount", "uint256", False),
    ]),
    ("ValidatorSet", "ValidatorSet(address,bool)", [
        ("account", "address", True), ("allowed", "bool", False),
    ]),
    ("RewardSignerSet", "RewardSignerSet(address)", [
        ("account", "address", True),
    ]),
]

DERIVED_TABLES = (
    "season1_days", "season1_orders", "season1_verifications",
    "season1_findings", "season1_task_packs", "season1_entries",
    "season1_validators", "season1_reward_signer",
)


def h2b(value):
    if isinstance(value, bytes):
        return value
    return bytes.fromhex(value[2:] if value.startswith("0x") else value)


def token_id(label, tld):
    parent = HAHA_NODE if int(tld) == 0 else MEME_NODE
    return int.from_bytes(keccak256(parent + keccak256(label.encode())), "big")


def bind_module(module, events):
    if not module:
        return
    module = module.lower()
    for name, sig, params in EVENT_DEFS:
        events[(module, topic0(sig))] = (name, params)


def bind_from_env(events):
    from common import season1_module
    bind_module(season1_module(), events)


def apply_season1_event(cur, event, p, meta):
    if event not in {row[0] for row in EVENT_DEFS}:
        return
    bn, _bt, txh, txi, li = meta
    if event == "DayRootSet":
        cur.execute(
            "INSERT INTO season1_days (day_index, merkle_root, snapshot_block,"
            " snapshot_block_hash, reserved_count, remaining_slots, opened,"
            " updated_block, updated_tx, updated_log)"
            " VALUES (%s,%s,%s,%s,%s,%s,true,%s,%s,%s)"
            " ON CONFLICT (day_index) DO UPDATE SET merkle_root = EXCLUDED.merkle_root,"
            " snapshot_block = EXCLUDED.snapshot_block,"
            " snapshot_block_hash = EXCLUDED.snapshot_block_hash,"
            " reserved_count = EXCLUDED.reserved_count,"
            " remaining_slots = EXCLUDED.remaining_slots,"
            " updated_block = EXCLUDED.updated_block,"
            " updated_tx = EXCLUDED.updated_tx, updated_log = EXCLUDED.updated_log"
            " WHERE (SELECT count(*) FROM season1_orders WHERE day_index = EXCLUDED.day_index) = 0",
            (p["dayIndex"], h2b(p["merkleRoot"]), p["snapshotBlock"], h2b(p["snapshotBlockHash"]),
             p["reservedCount"], p["remainingSlots"], bn, txh, li))
        # Recompute the day root from the snapshot entries and store it, so the
        # days API can report rootMatch. Entries are written by snapshot_day.py
        # before setDayRoot is sent, so they are normally already here. If the
        # snapshot has not landed yet, skip (the API recomputes on the fly).
        try:
            _root = recompute_day_root(cur, p["dayIndex"])
        except Exception:
            _root = None
        if _root is not None:
            cur.execute(
                "UPDATE season1_days SET recomputed_root = %s WHERE day_index = %s",
                (_root, p["dayIndex"]))
    elif event == "Redeemed":
        cur.execute(
            "INSERT INTO season1_orders (order_id, ai_id, applicant, recipient, label, tld,"
            " tier, day_index, price, root, status, token_id, block_number, tx_hash, tx_index, log_index)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'Pending',%s,%s,%s,%s,%s)"
            " ON CONFLICT (order_id) DO NOTHING",
            (p["orderId"], h2b(p["aiId"]), h2b(p["applicant"]), h2b(p["recipient"]),
             p["label"], p["tld"], p["tier"], p["dayIndex"], p["price"], h2b(p["root"]),
             token_id(p["label"], p["tld"]), bn, txh, txi, li))
    elif event == "FulfillmentAttested":
        cur.execute(
            "UPDATE season1_orders SET status = 'Fulfilled', mint_tx = %s, token_id = %s"
            " WHERE order_id = %s AND status = 'Pending'",
            (h2b(p["mintTxHash"]), p["tokenId"], p["orderId"]))
    elif event == "Verified":
        cur.execute(
            "INSERT INTO season1_verifications (ai_id, day_index, agent_id, generation,"
            " verdict, task_pack_hash, points, block_number, tx_hash, log_index)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (h2b(p["aiId"]), p["dayIndex"], p["agentId"], p["generation"], p["verdict"],
             h2b(p["taskPackHash"]), p["points"], bn, txh, li))
    elif event == "TaskPackSet":
        cur.execute(
            "INSERT INTO season1_task_packs (day_index, task_pack_hash, block_number)"
            " VALUES (%s,%s,%s) ON CONFLICT (day_index) DO UPDATE"
            " SET task_pack_hash = EXCLUDED.task_pack_hash, block_number = EXCLUDED.block_number"
            " WHERE NOT EXISTS (SELECT 1 FROM season1_verifications v WHERE v.day_index = EXCLUDED.day_index)",
            (p["dayIndex"], h2b(p["taskPackHash"]), bn))
    elif event == "FindingCommitted":
        cur.execute(
            "INSERT INTO season1_findings (report_evidence_hash, commit_hash, ai_id, committer,"
            " commit_block, tx_index, log_index, block_number)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (report_evidence_hash) DO NOTHING",
            (h2b(p["reportEvidenceHash"]), h2b(p["commitHash"]), h2b(p["aiId"]),
             h2b(p["committer"]), bn, txi, li, bn))
    elif event == "CanonicalAssigned":
        cur.execute(
            "UPDATE season1_findings SET canonical_id = %s WHERE report_evidence_hash = %s AND NOT paid",
            (h2b(p["canonicalRootCauseId"]), h2b(p["reportEvidenceHash"])))
    elif event == "FindingPaid":
        cur.execute(
            "UPDATE season1_findings SET paid = true WHERE report_evidence_hash = %s AND NOT paid",
            (h2b(p["reportEvidenceHash"]),))
    elif event == "AccidentDeclared":
        cur.execute(
            "UPDATE season1_orders SET status = 'CreditOpen', evidence_hash = %s"
            " WHERE order_id = %s AND status = 'Pending' AND ai_id = %s AND applicant = %s",
            (h2b(p["evidenceHash"]), p["orderId"], h2b(p["aiId"]), h2b(p["applicant"])))
    elif event == "AccidentRefunded":
        cur.execute(
            "UPDATE season1_orders SET status = 'AccidentRefunded', refunded = true"
            " WHERE order_id = %s AND status IN ('Pending', 'CreditOpen') AND ai_id = %s",
            (p["orderId"], h2b(p["aiId"])))
    elif event == "AccidentCompensated":
        cur.execute(
            "UPDATE season1_orders SET status = 'AccidentClosed', compensated = true"
            " WHERE order_id = %s AND NOT compensated AND ai_id = %s",
            (p["orderId"], h2b(p["aiId"])))
    elif event == "ValidatorSet":
        cur.execute(
            "INSERT INTO season1_validators (account, allowed, block_number, log_index)"
            " VALUES (%s, %s, %s, %s)"
            " ON CONFLICT (account) DO UPDATE SET allowed = EXCLUDED.allowed,"
            " block_number = EXCLUDED.block_number, log_index = EXCLUDED.log_index"
            " WHERE (season1_validators.block_number, season1_validators.log_index)"
            " <= (EXCLUDED.block_number, EXCLUDED.log_index)",
            (h2b(p["account"]), bool(p["allowed"]), bn, li))
    elif event == "RewardSignerSet":
        cur.execute(
            "INSERT INTO season1_reward_signer (id, account, block_number, log_index)"
            " VALUES (1, %s, %s, %s)"
            " ON CONFLICT (id) DO UPDATE SET account = EXCLUDED.account,"
            " block_number = EXCLUDED.block_number, log_index = EXCLUDED.log_index"
            " WHERE (season1_reward_signer.block_number, season1_reward_signer.log_index)"
            " <= (EXCLUDED.block_number, EXCLUDED.log_index)",
            (h2b(p["account"]), bn, li))
