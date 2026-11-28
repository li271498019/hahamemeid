"""Round 2 tests. No mainnet and no production key."""

import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from eth_abi import encode

from tools.season1.abi_adapter import load_adapter
from tools.season1.constants import ADMIN
from tools.season1.eip712 import SignRejected, require_live_validator
from tools.season1.hashutil import keccak256, leaf_hash, namehash
from tools.season1.index_model import replay
from tools.season1.merkle import ALGORITHM_VERSION, merkle_root_and_proofs, root_publish_precheck, verify_proof
from tools.season1.ops_book import OpsBook, OpsRefused, normalize_logs
from tools.season1.ops_server import serve

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "docs" / "season1" / "kickoff" / "fixtures" / "merkle-v1.json"
RECIPIENT = "0x" + "33" * 20


class MerkleFixtureTests(unittest.TestCase):
    def test_fixture_matches_generator(self):
        doc = json.loads(FIXTURE.read_text())
        self.assertEqual(doc["algorithm"], ALGORITHM_VERSION)
        counts = [case["count"] for case in doc["cases"]]
        self.assertEqual(counts, [1, 2, 3, 5, 20])
        tiers = {entry["tier"] for case in doc["cases"] for entry in case["entries"]}
        self.assertEqual(tiers, {0, 1})
        for case in doc["cases"]:
            rows = [{"aiId": e["aiId"], "balance": int(e["balance"]), "tier": e["tier"]} for e in case["entries"]]
            root, proofs = merkle_root_and_proofs(rows)
            self.assertEqual(root, case["root"])
            for entry in case["entries"]:
                leaf = leaf_hash(entry["aiId"], int(entry["balance"]), entry["tier"])
                self.assertEqual("0x" + leaf.hex(), entry["leaf"])
                self.assertEqual(proofs[entry["aiId"]], entry["proof"])
                self.assertTrue(verify_proof(leaf, entry["proof"], case["root"]))

    def test_blockhash_window_does_not_slide(self):
        snap = 1000
        ok = root_publish_precheck(snap + 15, snap)
        self.assertTrue(ok["ok"])
        self.assertEqual(ok["remainingBlocks"], 256 - 15)
        still = root_publish_precheck(snap + 255, snap)
        self.assertTrue(still["ok"])
        self.assertEqual(still["remainingBlocks"], 1)
        exact = root_publish_precheck(snap + 256, snap)
        self.assertFalse(exact["ok"])
        self.assertEqual(exact["reason"], "blockhash-expired")
        self.assertEqual(exact["remainingBlocks"], 0)
        late = root_publish_precheck(snap + 257, snap)
        self.assertFalse(late["ok"])
        self.assertEqual(late["reason"], "blockhash-expired")
        self.assertLess(late["remainingBlocks"], 0)


class HandoffAndSignerTests(unittest.TestCase):
    def test_real_handoff_stays_closed(self):
        loaded = load_adapter()
        self.assertEqual(loaded["source"], "handoff")
        self.assertIsNone(loaded["mainnet_module"])
        self.assertFalse(loaded["deployed"])
        self.assertEqual(loaded["chainId"], 56)
        names = {row["name"] for row in loaded["events"]}
        self.assertIn("FulfillmentAttested", names)
        self.assertIn("ValidatorSet", names)
        self.assertNotIn("MintConfirmed", names)

    def test_live_read_is_not_cached(self):
        calls = []

        def eth_call(module, data):
            calls.append((module, data))
            return "0x" + "00" * 31 + "01"

        module = "0x" + "44" * 20
        signer = "0x" + "55" * 20
        require_live_validator(eth_call, module, signer)
        require_live_validator(eth_call, module, signer)
        self.assertEqual(len(calls), 2)
        with self.assertRaises(SignRejected):
            require_live_validator(lambda *_: "0x" + "00" * 32, module, signer)
        with self.assertRaises(SignRejected):
            require_live_validator(lambda *_: (_ for _ in ()).throw(RuntimeError("rpc")), module, signer)

    def test_reorg_restores_revocation(self):
        logs = [
            {"event": "ValidatorSet", "account": "0x" + "55" * 20, "allowed": True, "block": 1},
            {"event": "ValidatorSet", "account": "0x" + "55" * 20, "allowed": False, "block": 2},
            {"event": "RewardSignerSet", "account": "0x" + "66" * 20, "block": 2},
        ]
        self.assertFalse(replay(logs)["validators"]["0x" + "55" * 20])
        rolled = replay([row for row in logs if row["block"] <= 1])
        self.assertTrue(rolled["validators"]["0x" + "55" * 20])
        self.assertNotIn("account", rolled["rewardSigner"])


class OpsTests(unittest.TestCase):
    def _orders(self):
        return [
            {"orderId": "1", "label": "ab", "tld": 0, "recipient": RECIPIENT,
             "tokenId": namehash("ab", 0), "dayIndex": 20781},
            {"orderId": "2", "label": "ac", "tld": 0, "recipient": RECIPIENT,
             "tokenId": namehash("ac", 0), "dayIndex": 20781},
        ]

    def _logs(self, order, tx_hash):
        token = int(order["tokenId"])
        return [
            {"event": "NameMinted", "txHash": tx_hash, "tokenId": token, "owner": RECIPIENT,
             "label": order["label"], "tld": 0, "reservedMint": True},
            {"event": "Transfer", "txHash": tx_hash, "tokenId": token,
             "from": "0x" + "00" * 20, "to": RECIPIENT},
        ]

    def test_two_orders_restart_and_locks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            book = OpsBook(self._orders(), state_path=path)
            first = book.prepare("1", 56, ADMIN, lambda _r: False)
            self.assertNotIn("nonce", first)
            self.assertEqual(first["value"], "0x0")
            book.note_submitted("1", "0x" + "aa" * 32, None)
            with self.assertRaises(OpsRefused):
                book.prepare("1", 56, ADMIN, lambda _r: False)
            self.assertFalse(book.accident_instruction("1")["allowRefund"])
            self.assertEqual(book.accident_instruction("1")["reason"], "local-pending")
            book.note_receipt("1", {"status": 1, "transactionHash": "0x" + "aa" * 32},
                              self._logs(self._orders()[0], "0x" + "aa" * 32))
            self.assertEqual(book.txs["1"]["logCheck"], "matched")
            second = book.prepare("2", 56, ADMIN, lambda _r: False)
            self.assertNotEqual(second["data"], first["data"])
            with self.assertRaises(OpsRefused):
                book.prepare("2", 97, ADMIN, lambda _r: False)
            with self.assertRaises(OpsRefused):
                book.prepare("2", 56, "0x" + "99" * 20, lambda _r: False)
            with self.assertRaises(OpsRefused):
                book.prepare("9", 56, ADMIN, lambda _r: False)
            idle = book.accident_instruction("2")
            self.assertFalse(idle["allowRefund"])
            self.assertEqual(idle["reason"], "external-unobserved")
            reloaded = OpsBook(self._orders(), state_path=path)
            self.assertEqual(reloaded.txs["1"]["status"], "confirmed")
            reloaded.drop_unconfirmed("1")
            self.assertEqual(reloaded.txs["1"]["status"], "reorged")
            self.assertEqual(reloaded.accident_instruction("1")["reason"], "reorged")
            self.assertFalse(reloaded.accident_instruction("1")["allowRefund"])
            self.assertNotEqual(reloaded.txs["1"].get("logCheck"), "matched")

    def test_replacement_keeps_the_old_hash(self):
        book = OpsBook(self._orders())
        book.prepare("2", 56, ADMIN, lambda _r: False)
        book.note_submitted("2", "0x" + "bb" * 32, None)
        book.note_submitted("2", "0x" + "cc" * 32, None)
        self.assertEqual(book.txs["2"]["status"], "pending")
        self.assertEqual(book.txs["2"]["hash"], "0x" + "cc" * 32)
        self.assertEqual(book.txs["2"]["replaced"], "0x" + "bb" * 32)
        self.assertEqual(book.accident_instruction("2")["reason"], "local-pending")
        self.assertFalse(book.accident_instruction("2")["allowRefund"])

    def test_raw_mint_logs_survive_a_later_transfer(self):
        book = OpsBook(self._orders())
        order = self._orders()[0]
        book.prepare("1", 56, ADMIN, lambda _r: False)
        mint_hash = "0x" + "aa" * 32
        book.note_submitted("1", mint_hash, None)
        token = int(order["tokenId"])
        minted = "0x" + keccak256(b"NameMinted(uint256,address,uint8,bytes32,string,bool)").hex()
        transfer = "0x" + keccak256(b"Transfer(address,address,uint256)").hex()
        data = "0x" + encode(["uint8", "string", "bool"], [0, "ab", True]).hex()

        def pad_addr(value):
            return "0x" + value.lower().replace("0x", "").rjust(64, "0")

        raw = [
            {"topics": [minted, "0x" + token.to_bytes(32, "big").hex(), pad_addr(RECIPIENT), "0x" + "00" * 32], "data": data},
            {"topics": [transfer, "0x" + "00" * 32, pad_addr(RECIPIENT), "0x" + token.to_bytes(32, "big").hex()], "data": "0x"},
        ]
        book.note_receipt("1", {"status": "0x1", "transactionHash": mint_hash}, raw)
        self.assertEqual(book.txs["1"]["logCheck"], "matched")
        later = "0x" + "dd" * 32
        moved = [{
            "topics": [transfer, pad_addr(RECIPIENT), pad_addr("0x" + "44" * 20), "0x" + token.to_bytes(32, "big").hex()],
            "data": "0x",
        }]
        with self.assertRaises(OpsRefused):
            book.note_receipt("1", {"status": "0x1", "transactionHash": later}, moved)
        self.assertEqual(book.txs["1"]["status"], "confirmed")
        self.assertEqual(book.txs["1"]["hash"], mint_hash)
        self.assertEqual(book.txs["1"]["logCheck"], "matched")
        self.assertEqual(book.accident_instruction("1")["reason"], "already-minted")
        self.assertEqual(normalize_logs(raw, mint_hash)[0]["label"], "ab")

    def test_reverted_receipt_does_not_open_a_refund(self):
        book = OpsBook(self._orders())
        book.prepare("1", 56, ADMIN, lambda _r: False)
        book.note_submitted("1", "0x" + "ee" * 32, None)
        book.note_receipt("1", {"status": "0x0", "transactionHash": "0x" + "ee" * 32}, [])
        self.assertEqual(book.txs["1"]["status"], "reverted")
        self.assertFalse(book.accident_instruction("1")["allowRefund"])
        self.assertEqual(book.accident_instruction("1")["reason"], "local-reverted")

    def test_localhost_server(self):
        book = OpsBook(self._orders())
        thread = threading.Thread(target=serve, args=(book, 8766), daemon=True)
        thread.start()
        req = urllib.request.Request(
            "http://127.0.0.1:8766/api/prepare",
            data=json.dumps({"orderId": "1", "chainId": 56, "account": ADMIN}).encode(),
            headers={"content-type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=3) as res:
            body = json.loads(res.read())
        self.assertNotIn("nonce", body)
        self.assertTrue(body["data"].startswith("0x65f5a090"))


class PageGateTests(unittest.TestCase):
    def test_js_gate(self):
        import subprocess
        script = (ROOT / "tools/season1/ops_panel/app.js").read_text()
        node = script + """
const prepared = {from: OPS_ADMIN, to: '0x1', value: '0x0', data: '0xab', chainId: '0x38'};
if (canSend({chainId: 56, account: OPS_ADMIN, prepared, localStatus: 'idle'}) !== null) process.exit(1);
if (!canSend({chainId: 97, account: OPS_ADMIN, prepared, localStatus: 'idle'})) process.exit(2);
const tx = walletRequest(prepared);
if ('nonce' in tx) process.exit(3);
console.log('ok');
"""
        out = subprocess.check_output(["node", "-e", node], text=True)
        self.assertIn("ok", out)
        self.assertEqual(keccak256(b"adminMint(string,uint8,address)")[:4].hex(), "65f5a090")


if __name__ == "__main__":
    unittest.main()
