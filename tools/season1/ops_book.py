"""Local book for one-by-one adminMint. The server never holds a key and never broadcasts."""

import json
from pathlib import Path

from eth_abi import decode as abi_decode

from tools.season1.constants import ADMIN, REGISTRAR
from tools.season1.hashutil import keccak256
from tools.season1.ops import admin_mint_calldata, interpret_is_minted, log_check

TRANSFER_TOPIC = "0x" + keccak256(b"Transfer(address,address,uint256)").hex()
MINT_TOPIC = "0x" + keccak256(b"NameMinted(uint256,address,uint8,bytes32,string,bool)").hex()


class OpsRefused(Exception):
    pass


def normalize_logs(logs, tx_hash):
    out = []
    for log in logs:
        if log.get("event"):
            row = dict(log)
            row["txHash"] = tx_hash
            out.append(row)
            continue
        topics = [str(t).lower() for t in log.get("topics") or []]
        if len(topics) >= 4 and topics[0] == TRANSFER_TOPIC:
            out.append({
                "event": "Transfer",
                "txHash": tx_hash,
                "from": "0x" + topics[1][-40:],
                "to": "0x" + topics[2][-40:],
                "tokenId": int(topics[3], 16),
            })
        elif len(topics) >= 3 and topics[0] == MINT_TOPIC:
            data = bytes.fromhex(log.get("data", "0x")[2:])
            tld, label, reserved = abi_decode(["uint8", "string", "bool"], data)
            out.append({
                "event": "NameMinted",
                "txHash": tx_hash,
                "tokenId": int(topics[1], 16),
                "owner": "0x" + topics[2][-40:],
                "label": label,
                "tld": tld,
                "reservedMint": reserved,
            })
    return out


class OpsBook:
    def __init__(self, orders, chain_id=56, admin=ADMIN, state_path=None, panel_dir=None, mint_check=None):
        self.chain_id = int(chain_id)
        self.admin = admin.lower()
        self.orders = {str(row["orderId"]): row for row in orders}
        self.state_path = Path(state_path) if state_path else None
        self.panel_dir = Path(panel_dir) if panel_dir else Path(__file__).resolve().parent / "ops_panel"
        self.mint_check = mint_check or (lambda _row: False)
        self.txs = {}
        if self.state_path and self.state_path.is_file():
            self.txs = json.loads(self.state_path.read_text())

    def save(self):
        if self.state_path:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps(self.txs, indent=2))

    def _order(self, order_id):
        row = self.orders.get(str(order_id))
        if row is None:
            raise OpsRefused("unknown-order")
        return row

    def prepare(self, order_id, chain_id, account, is_minted):
        row = self._order(order_id)
        if int(chain_id) != self.chain_id:
            raise OpsRefused("wrong-chain")
        if not account or account.lower() != self.admin:
            raise OpsRefused("wrong-admin")
        current = self.txs.get(str(order_id), {})
        if current.get("status") in ("pending", "confirmed"):
            raise OpsRefused("already-sent")
        try:
            sim = interpret_is_minted(self.mint_check(row) if is_minted is None else is_minted(row))
        except Exception as exc:
            raise OpsRefused("name-check-failed") from exc
        if sim == "name-taken":
            raise OpsRefused("name-taken")
        data = admin_mint_calldata(row["label"], int(row["tld"]), row["recipient"])
        return {
            "orderId": str(order_id),
            "to": REGISTRAR,
            "value": "0x0",
            "data": data,
            "chainId": hex(self.chain_id),
            "from": self.admin,
            "recipient": row["recipient"],
        }

    def note_submitted(self, order_id, tx_hash, nonce):
        row = self._order(order_id)
        current = self.txs.get(str(order_id), {})
        if current.get("status") == "confirmed":
            raise OpsRefused("already-confirmed")
        if current.get("status") == "pending" and current.get("hash") != tx_hash:
            current["status"] = "replaced"
        self.txs[str(order_id)] = {
            "status": "pending",
            "hash": tx_hash,
            "nonce": nonce,
            "recipient": row["recipient"],
            "replaced": current.get("hash") if current.get("status") == "replaced" else current.get("replaced"),
        }
        self.save()
        return self.txs[str(order_id)]

    def note_receipt(self, order_id, receipt, logs):
        current = self.txs.get(str(order_id))
        if not current or current.get("status") not in ("pending", "confirmed"):
            raise OpsRefused("no-pending")
        incoming = str(receipt.get("transactionHash") or "")
        if current.get("status") == "confirmed" and current.get("logCheck") == "matched":
            if incoming.lower() != str(current.get("hash") or "").lower():
                raise OpsRefused("historical-mint-kept")
            return current
        if receipt.get("status") not in (1, "0x1", True):
            current["status"] = "reverted"
            current["logCheck"] = "not-minted"
            self.save()
            return current
        order = dict(self._order(order_id))
        order["mintTx"] = receipt["transactionHash"]
        order["tokenId"] = order.get("tokenId")
        check = log_check(order, normalize_logs(logs or [], receipt["transactionHash"]))
        current["status"] = "confirmed" if check == "matched" else "log-mismatch"
        current["logCheck"] = check
        current["hash"] = receipt["transactionHash"]
        self.save()
        return current

    def drop_unconfirmed(self, order_id):
        """A reorg removed the receipt. Do not create a second success."""
        current = self.txs.get(str(order_id))
        if current and current.get("status") == "confirmed":
            current["status"] = "reorged"
            current["logCheck"] = "unknown"
            self.save()
        return current

    def accident_instruction(self, order_id):
        self._order(order_id)
        current = self.txs.get(str(order_id), {})
        if current.get("status") == "pending":
            return {"allowRefund": False, "reason": "local-pending", "needsAdmin": True}
        if current.get("status") == "confirmed" and current.get("logCheck") == "matched":
            return {"allowRefund": False, "reason": "already-minted", "needsAdmin": True}
        if current.get("status") == "reverted":
            return {"allowRefund": False, "reason": "local-reverted", "needsAdmin": True}
        if current.get("status") == "log-mismatch":
            return {"allowRefund": False, "reason": "log-mismatch", "needsAdmin": True}
        if current.get("status") == "reorged":
            return {"allowRefund": False, "reason": "reorged", "needsAdmin": True}
        return {
            "allowRefund": False,
            "reason": "external-unobserved",
            "needsAdmin": True,
        }
