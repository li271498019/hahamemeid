"""Unit tests for the season-1 off-chain tools. No network, no stored key, no mint."""

import json
import os
import unittest
from pathlib import Path

from eth_account import Account

from tools.season1.abi_adapter import load_adapter
from tools.season1.api_view import DAY_KEYS, ORDER_KEYS, day_view, eligibility_view, finding_view, order_view, verify_view
from tools.season1.checker import check_scores, last_rating_per_rater, registration_format, task_pack_hash, verdict_code
from tools.season1.constants import CANDIDATE_NAMES, END_TS, PRICE, SNAPSHOT_CONFIRMATIONS, START_TS, VERIFY_GLOBAL
from tools.season1.eip712 import SignRejected, finding_claim_window, recovered_in_allowed_set, sign_verify
from tools.season1.hashutil import namehash
from tools.season1.index_model import drop_after, replay
from tools.season1.merkle import (
    candidate_count,
    canonical_manifest,
    eligible_entries,
    lock_snapshot_block,
    merkle_root_and_proofs,
    replay_balances,
    roots_match,
    snapshot_ready,
    verify_proof,
)
from tools.season1.ops import OpsStopped, admin_mint_calldata, build_rows, interpret_is_minted, log_check

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "docs" / "season1" / "kickoff" / "fixtures"
AI = "0x" + "11" * 32
AI2 = "0x" + "22" * 32


def _ai(n):
    return "0x" + ("%064x" % n)


class MerkleTests(unittest.TestCase):
    def test_lock_does_not_fall_back(self):
        headers = [
            {"number": 10, "timestamp": 100, "hash": "0x" + "aa" * 32},
            {"number": 11, "timestamp": 200, "hash": "0x" + "bb" * 32},
            {"number": 12, "timestamp": 300, "hash": "0x" + "cc" * 32},
        ]
        locked = lock_snapshot_block(headers, 250)
        self.assertEqual(locked["number"], 11)
        self.assertFalse(snapshot_ready(20, 11, SNAPSHOT_CONFIRMATIONS))
        self.assertTrue(snapshot_ready(26, 11, SNAPSHOT_CONFIRMATIONS))
        # A deeper earlier block is not substituted when 11 is still too fresh.
        self.assertNotEqual(lock_snapshot_block(headers, 250)["number"], 10)

    def test_replay_ignores_later_points_and_zero_ai(self):
        logs = [
            {"block": 1, "logIndex": 0, "aiId": AI, "newBalance": 100},
            {"block": 2, "logIndex": 0, "aiId": AI, "newBalance": 250},
            {"block": 3, "logIndex": 0, "aiId": AI, "newBalance": 999},
            {"block": 2, "logIndex": 1, "aiId": "0x" + "00" * 32, "newBalance": 500},
        ]
        balances = replay_balances(logs, 2)
        self.assertEqual(balances[AI], 250)
        self.assertEqual(len(balances), 1)

    def test_boundary_ties_and_full_tie(self):
        balances = {_ai(i): 1000 for i in range(18)}
        for i in range(10):
            balances[_ai(100 + i)] = 200
        entries, reserved, remaining = eligible_entries(balances, [])
        self.assertEqual(reserved, 18)
        self.assertEqual(remaining, 2)
        self.assertEqual(sum(1 for row in entries if row["tier"] == 1), 10)
        tied = {_ai(i): 200 for i in range(25)}
        entries, reserved, remaining = eligible_entries(tied, [])
        self.assertEqual(reserved, 0)
        self.assertEqual(remaining, 20)
        self.assertEqual(len(entries), 25)

    def test_pending_and_low_balance_excluded(self):
        balances = {AI: 400, AI2: 199, _ai(3): 400}
        entries, _, _ = eligible_entries(balances, [{"aiId": AI, "status": "Pending"}])
        ids = {row["aiId"] for row in entries}
        self.assertNotIn(AI, ids)
        self.assertNotIn(AI2, ids)
        self.assertIn(_ai(3), ids)

    def test_root_stable_and_proof(self):
        balances = {_ai(i): 300 + i for i in range(4)}
        entries, _, _ = eligible_entries(balances, [])
        root_a, proofs = merkle_root_and_proofs(entries)
        root_b, _ = merkle_root_and_proofs(entries)
        self.assertEqual(root_a, root_b)
        for row in entries:
            self.assertTrue(verify_proof(
                __import__("tools.season1.hashutil", fromlist=["leaf_hash"]).leaf_hash(
                    row["aiId"], row["balance"], row["tier"]),
                proofs[row["aiId"]], root_a))
        body, raw, digest = canonical_manifest(20781, 1795478400, {"number": 5, "hash": "0x" + "ab" * 32},
                                                None, entries, root_a, 4, 0)
        self.assertEqual(json.loads(raw.decode()), body)
        self.assertTrue(digest.startswith("0x"))
        self.assertFalse(roots_match(root_a, "0x" + "ff" * 32))

    def test_candidates_are_not_stock(self):
        self.assertEqual(candidate_count(), 1552)
        self.assertEqual(CANDIDATE_NAMES, 1552)


class IndexTests(unittest.TestCase):
    def _redeem(self, block=5):
        return {"event": "Redeemed", "block": block, "txIndex": 1, "logIndex": 0,
                "orderId": 1, "aiId": AI, "applicant": "0x" + "22" * 20,
                "recipient": "0x" + "33" * 20, "label": "ab", "tld": 0, "tier": 0,
                "tokenId": 1, "dayIndex": 20781}

    def test_reorg_does_not_double_and_keeps_reviews(self):
        logs = [
            {"event": "Rated", "block": 4, "agentId": 1, "raterAiId": AI, "stars": 5, "review": "ok"},
            self._redeem(5),
            self._redeem(6),
        ]
        full = replay(logs)
        self.assertEqual(len(full["orders"]), 1)
        rolled = replay(drop_after(logs, 5))
        self.assertEqual(len(rolled["orders"]), 1)
        self.assertEqual(len(rolled["reviews"]), 1)
        again = replay(drop_after(logs, 5) + drop_after(logs, 5))
        self.assertEqual(len(again["orders"]), 1)
        self.assertEqual(len(again["reviews"]), 1)

    def test_mint_confirmed_ignored_and_fulfillment_needs_logs(self):
        logs = [self._redeem(), {"event": "MintConfirmed", "block": 6, "orderId": 1},
                {"event": "FulfillmentAttested", "block": 7, "orderId": 1,
                 "tokenId": namehash("ab", 0), "mintTxHash": "0x" + "dd" * 32}]
        state = replay(logs)
        order = state["orders"]["1"]
        self.assertEqual(order["status"], "Fulfilled")
        self.assertEqual(log_check(order, []), "mismatch")
        good = [{
            "event": "NameMinted", "txHash": order["mintTx"], "tokenId": order["tokenId"],
            "owner": order["recipient"], "label": "ab", "tld": 0, "reservedMint": True,
        }, {
            "event": "Transfer", "txHash": order["mintTx"], "tokenId": order["tokenId"],
            "from": "0x" + "00" * 20, "to": order["recipient"],
        }]
        # receipt.to is not consulted
        self.assertEqual(log_check({**order, "receiptTo": "0x" + "99" * 20}, good), "matched")

    def test_duplicate_verify_and_accident_keeps_claimant(self):
        logs = [
            {"event": "Verified", "block": 8, "aiId": AI, "dayIndex": 20781, "verdict": 0,
             "taskPackHash": "0x" + "ee" * 32, "points": 30},
            {"event": "Verified", "block": 9, "aiId": AI, "dayIndex": 20781, "verdict": 1,
             "taskPackHash": "0x" + "ee" * 32, "points": 30},
            self._redeem(),
            {"event": "AccidentDeclared", "block": 10, "orderId": 1, "evidenceHash": "0x" + "ab" * 32},
        ]
        state = replay(logs)
        self.assertEqual(len(state["verifications"]), 1)
        self.assertEqual(state["verifications"][(AI, 20781)]["verdict"], "Match")
        order = state["orders"]["1"]
        self.assertEqual(order["status"], "CreditOpen")
        self.assertEqual(order["applicant"], "0x" + "22" * 20)
        self.assertEqual(order["aiId"], AI)

    def test_zero_event_pack_and_edited_reviews(self):
        body = {"seasonId": 1, "dayIndex": 20781, "blockNumber": 1, "blockHash": "0x" + "00" * 32, "checks": []}
        self.assertEqual(task_pack_hash(body), task_pack_hash(body))
        ratings = [
            {"agentId": 1, "raterAiId": AI, "stars": 5, "block": 1, "logIndex": 0},
            {"agentId": 1, "raterAiId": AI, "stars": 4, "block": 2, "logIndex": 0},
        ]
        rolled = last_rating_per_rater(ratings)
        self.assertEqual(rolled[1], {"count": 1, "sum": 4})


class ApiShapeTests(unittest.TestCase):
    def test_fixture_keys(self):
        day = json.loads((FIXTURES / "day.json").read_text())
        shaped = day_view(day)
        self.assertEqual(set(shaped), set(DAY_KEYS))
        self.assertTrue(shaped["rootMatch"])
        mismatch = json.loads((FIXTURES / "day-mismatch.json").read_text())
        self.assertFalse(day_view(mismatch)["rootMatch"])
        order = json.loads((FIXTURES / "orders.json").read_text())["orders"][0]
        self.assertEqual(set(order_view(order)), set(ORDER_KEYS))
        bad = json.loads((FIXTURES / "order-log-mismatch.json").read_text())
        self.assertEqual(order_view(bad)["logCheck"], "mismatch")
        verify = json.loads((FIXTURES / "verify.json").read_text())
        for case in verify["cases"]:
            row = {"aiId": verify["aiId"], "dayIndex": verify["dayIndex"], **case}
            view = verify_view(row)
            self.assertEqual(view["points"], 30 if case["claimed"] else 0)
        finding = json.loads((FIXTURES / "finding.json").read_text())
        public = finding_view(finding["cases"][0], set())
        self.assertIn("commitBlock", public)
        hidden = finding_view(finding["cases"][1], set())
        self.assertEqual(set(hidden), {"reportEvidenceHash", "withheld"})
        self.assertNotIn("salt", hidden)
        elig = eligibility_view(AI, 20781, "excluded", "below-cutoff", 190, 190)
        self.assertEqual(elig["balance"], "190")
        self.assertEqual(VERIFY_GLOBAL, 100000)

    def test_adapter_is_mock_until_handoff(self):
        loaded = load_adapter("")
        self.assertFalse(loaded["deployed"])
        self.assertIsNone(loaded["mainnet_module"])
        names = {row["name"] for row in loaded["events"]}
        self.assertIn("FulfillmentAttested", names)
        self.assertNotIn("MintConfirmed", names)


class SignerAndOpsTests(unittest.TestCase):
    def test_sign_window_revoke_and_fail_closed(self):
        key = Account.create().key.hex()
        module = "0x" + "44" * 20
        message = {
            "seasonId": 1, "dayIndex": 20781, "aiId": AI, "agentId": 1, "generation": 1,
            "taskPackHash": "0x" + "ee" * 32, "verdict": 0, "nonce": 0,
            "deadline": (20781 + 1) * 86400,
        }
        now = START_TS + 10
        with self.assertRaises(SignRejected):
            sign_verify(None, message, 56, module, now)
        with self.assertRaises(SignRejected):
            sign_verify(key, message, 56, None, now)
        signed = sign_verify(key, message, 56, module, now, allowed_signers=[Account.from_key(key).address])
        self.assertTrue(signed["signature"].startswith("0x"))
        late = dict(message)
        with self.assertRaises(SignRejected):
            sign_verify(key, late, 56, module, END_TS + 1)
        self.assertFalse(recovered_in_allowed_set(key, []))
        published = END_TS - 3600
        self.assertTrue(finding_claim_window(END_TS - 3 * 86400, published, published + 86400 + 10))
        self.assertFalse(finding_claim_window(END_TS, END_TS + 10, END_TS + 90000))
        self.assertEqual(PRICE, 200)

    def test_ops_one_tx_and_closed_checks(self):
        token = namehash("ab", 0)
        order = {
            "orderId": 1, "status": "Pending", "label": "ab", "tld": 0,
            "recipient": "0x" + "33" * 20, "tokenId": token, "mintTx": None,
        }
        rows = build_rows([order], lambda _o: False, lambda _o: [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["action"], "sign-one")
        self.assertNotIn("batch", rows[0])
        self.assertTrue(rows[0]["data"].startswith("0x65f5a090"))
        stopped = build_rows([order], lambda _o: None, lambda _o: [])
        self.assertEqual(stopped[0]["simError"], "name-check-failed")
        taken = build_rows([order], lambda _o: True, lambda _o: [])
        self.assertEqual(taken[0]["simError"], "name-taken")
        with self.assertRaises(OpsStopped):
            interpret_is_minted("403")
        data = admin_mint_calldata("ab", 0, order["recipient"])
        self.assertNotEqual(data, admin_mint_calldata("ac", 0, order["recipient"]))
        self.assertEqual(check_scores({}, None, rpc_error=True), "unclear")
        self.assertEqual(verdict_code("discrepancy"), 1)
        self.assertEqual(registration_format({"type": "https://eips.ethereum.org/EIPS/eip-8004#registration-v1"}), "match")


class PageTests(unittest.TestCase):
    def test_apply_page_has_no_wallet(self):
        html = (ROOT / "web" / "site" / "season-apply.html").read_text()
        js = (ROOT / "web" / "site" / "js" / "season-apply.js").read_text()
        blob = html + js
        self.assertNotIn("ethereum", blob.lower())
        self.assertNotIn("privatekey", blob.lower().replace("_", ""))
        self.assertIn("200", js)
        # node evaluates the instruction gate
        script = js + "\nconsole.log(JSON.stringify({show: canShowInstruction({rootMatch:false, opened:true}), text: buildInstruction({label:'ab', tld:0, recipient:'0x" + "33"*20 + "'} )}));"
        import subprocess
        out = subprocess.check_output(["node", "-e", script], text=True)
        parsed = json.loads(out)
        self.assertFalse(parsed["show"])
        shown = subprocess.check_output(["node", "-e", js + "\nconsole.log(canShowInstruction({rootMatch:true, opened:true}) ? buildInstruction({label:'ab', tld:0, recipient:'0x" + "33"*20 + "'}) : '')"], text=True)
        self.assertIn("200", shown)
        self.assertIn("ab.haha", shown)


if __name__ == "__main__":
    unittest.main()
