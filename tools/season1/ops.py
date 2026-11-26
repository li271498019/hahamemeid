"""One adminMint calldata per pending order. Does not sign, store a key, or broadcast."""

from eth_abi import encode

from tools.season1.constants import ADMIN_MINT_SELECTOR, PRICE, REGISTRAR
from tools.season1.hashutil import keccak256, namehash


class OpsStopped(Exception):
    pass


def admin_mint_calldata(label, tld, recipient):
    if not isinstance(label, str) or len(label) != 2 or not label.islower() or not label.isalnum():
        raise OpsStopped("label outside the two-character pool")
    if tld not in (0, 1):
        raise OpsStopped("tld")
    if not isinstance(recipient, str) or not recipient.startswith("0x") or len(recipient) != 42:
        raise OpsStopped("recipient")
    if label.isdigit() or label.isalpha():
        pass
    else:
        raise OpsStopped("mixed two-character labels are not in this pool")
    body = encode(["string", "uint8", "address"], [label, tld, recipient])
    selector = keccak256(b"adminMint(string,uint8,address)")[:4]
    if "0x" + selector.hex() != ADMIN_MINT_SELECTOR:
        raise OpsStopped("adminMint selector drifted from the deployed registrar")
    return "0x" + selector.hex() + body.hex()


def interpret_is_minted(result):
    """True: name exists. False: clean unminted. Anything else stops the row."""
    if result is True:
        return "name-taken"
    if result is False:
        return None
    raise OpsStopped("isMinted did not return a clean boolean; not unminted")


def log_check(order, tx_logs):
    """tx_logs are logs from the mint transaction. receipt.to is ignored."""
    if not order.get("mintTx"):
        return "not-minted"
    if tx_logs is None:
        return "unknown"
    token_id = int(order["tokenId"])
    recipient = order["recipient"].lower()
    minted = False
    transferred = False
    for log in tx_logs:
        if log.get("txHash", "").lower() != order["mintTx"].lower():
            continue
        if log.get("event") == "NameMinted":
            if (int(log["tokenId"]) == token_id and log["owner"].lower() == recipient
                    and log["label"] == order["label"] and int(log["tld"]) == int(order["tld"])
                    and log["reservedMint"] is True):
                minted = True
        if log.get("event") == "Transfer":
            if (log["from"].lower() == "0x" + "00" * 20 and log["to"].lower() == recipient
                    and int(log["tokenId"]) == token_id):
                transferred = True
    if minted and transferred:
        return "matched"
    return "mismatch"


def build_rows(orders, is_minted_fn, logs_for_tx):
    """One row, one transaction description. No batch field and no signature."""
    rows = []
    for order in orders:
        if order["status"] != "Pending":
            rows.append({**_public(order, logs_for_tx), "action": "skip", "reason": order["status"]})
            continue
        try:
            sim = interpret_is_minted(is_minted_fn(order))
        except OpsStopped as exc:
            rows.append({**_public(order, logs_for_tx), "action": "stop", "simError": "name-check-failed", "detail": str(exc)})
            continue
        if sim == "name-taken":
            rows.append({**_public(order, logs_for_tx), "action": "stop", "simError": "name-taken"})
            continue
        expected = namehash(order["label"], int(order["tld"]))
        if int(order["tokenId"]) != expected:
            rows.append({**_public(order, logs_for_tx), "action": "stop", "simError": "name-check-failed",
                         "detail": "tokenId is not the namehash"})
            continue
        data = admin_mint_calldata(order["label"], int(order["tld"]), order["recipient"])
        rows.append({
            **_public(order, logs_for_tx),
            "action": "sign-one",
            "to": REGISTRAR,
            "data": data,
            "value": "0",
            "simError": None,
            "price": PRICE,
        })
    return rows


def _public(order, logs_for_tx=None):
    logs = None
    if order.get("mintTx") and logs_for_tx is not None:
        logs = logs_for_tx(order)
    return {
        "orderId": str(order["orderId"]),
        "label": order["label"],
        "tld": int(order["tld"]),
        "recipient": order["recipient"],
        "logCheck": log_check(order, logs),
    }
