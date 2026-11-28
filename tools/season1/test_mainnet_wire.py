"""Gates for the verified module and the server signer file. No production key."""

import json
import os
import stat
import subprocess
import sys
import unittest
from pathlib import Path

from eth_account import Account

from tools.season1.eip712 import SignRejected, sign_verify
from tools.season1.mainnet import (
    CHAIN_ID, DAILY_SIGNER, DEPLOY_BLOCK, DEPLOY_BLOCK_HASH, MODULE,
)
from tools.season1.sign_gate import authorize
from tools.season1.signer_env import load_matching_key

ROOT = Path(__file__).resolve().parents[2]
INDEXER = ROOT / "indexer"
sys.path.insert(0, str(INDEXER))
from season1_backfill import DEPLOY_BLOCK as BACKFILL_BLOCK  # noqa: E402
from season1_backfill import MODULE as BACKFILL_MODULE  # noqa: E402
from season1_backfill import missing_anchors, plan, write_module_logs  # noqa: E402


def _allow(_module, _data):
    return "0x" + "00" * 31 + "01"


class GateTests(unittest.TestCase):
    def test_constants_match_the_indexer_copy(self):
        self.assertEqual(MODULE.lower(), BACKFILL_MODULE)
        self.assertEqual(DEPLOY_BLOCK, BACKFILL_BLOCK)
        self.assertEqual(CHAIN_ID, 56)
        self.assertTrue(DEPLOY_BLOCK_HASH.startswith("0xd0c1080e"))

    def test_signing_stays_off_until_explicitly_enabled(self):
        key = Account.create().key.hex()
        address = Account.from_key(key).address
        env = {"SEASON1_SIGNER_KEY": key, "SEASON1_MODULE": MODULE, "SEASON1_CHAIN_ID": "56"}
        with self.assertRaises(SignRejected) as caught:
            authorize(env, _allow, MODULE, address)
        self.assertIn("disabled", str(caught.exception))
        self.assertNotIn(key.replace("0x", ""), str(caught.exception))

    def test_authorize_requires_chain_module_and_live_validator(self):
        account = Account.create()
        env = {
            "SEASON1_SIGNING": "on",
            "SEASON1_SIGNER_KEY": account.key.hex(),
            "SEASON1_MODULE": MODULE,
            "SEASON1_CHAIN_ID": "56",
        }
        with self.assertRaises(SignRejected):
            authorize(dict(env, SEASON1_CHAIN_ID="97"), _allow, MODULE, account.address)
        with self.assertRaises(SignRejected):
            authorize(dict(env, SEASON1_MODULE="0x" + "11" * 20), _allow, MODULE, account.address)
        with self.assertRaises(SignRejected):
            authorize(env, lambda *_: "0x" + "00" * 32, MODULE, account.address)
        with self.assertRaises(SignRejected):
            authorize(env, lambda *_: (_ for _ in ()).throw(RuntimeError("down")), MODULE, account.address)
        key, module, chain = authorize(env, _allow, MODULE, account.address)
        self.assertEqual(chain, 56)
        self.assertEqual(module.lower(), MODULE.lower())
        message = {
            "seasonId": 1, "dayIndex": 20781, "aiId": "0x" + "11" * 32, "agentId": 1,
            "generation": 1, "taskPackHash": "0x" + "ee" * 32, "verdict": 0, "nonce": 0,
            "deadline": (20781 + 1) * 86400,
        }
        signed = sign_verify(key, message, chain, module, 1795478400 + 10, allowed_signers=[account.address])
        self.assertTrue(signed["signature"].startswith("0x"))
        self.assertEqual(signed["domain"]["chainId"], 56)
        self.assertEqual(signed["domain"]["verifyingContract"].lower(), MODULE.lower())

    def test_env_file_matches_one_address_and_does_not_echo(self):
        account = Account.create()
        other = Account.create()
        path = Path("/tmp/season1-signer-test.env")
        path.write_text(
            "NOTE=not-a-key\nSIGNER_KEY=%s\nOTHER=%s\n" % (account.key.hex(), other.key.hex()),
            encoding="utf-8")
        path.chmod(0o600)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode) & 0o077, 0)
        loaded = load_matching_key(path, account.address)
        self.assertEqual(Account.from_key(loaded).address, account.address)
        path.chmod(0o640)
        with self.assertRaises(SignRejected) as caught:
            load_matching_key(path, account.address)
        self.assertNotIn(account.key.hex().replace("0x", ""), str(caught.exception))
        path.chmod(0o600)
        with self.assertRaises(SignRejected):
            load_matching_key(path, DAILY_SIGNER)

    def test_cli_refuses_without_a_file(self):
        env = os.environ.copy()
        env.pop("SEASON1_SIGNER_KEY", None)
        env.pop("SEASON1_SIGNING", None)
        proc = subprocess.run(
            [sys.executable, "-m", "tools.season1", "signer-check",
             "--signer-env", "/tmp/season1-signer-missing.env"],
            cwd=ROOT, env=env, text=True, capture_output=True, check=False)
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn("missing", proc.stdout)


class BackfillTests(unittest.TestCase):
    def test_known_receipts_are_required(self):
        self.assertEqual(missing_anchors([]), ["ValidatorSet", "RewardSignerSet"])
        present = [
            {"transactionHash": "0x3c10db324213a5e21625d71b0eb04058bb1fb78af9bfa9bbf6a5f64f9f2ad743"},
            {"transactionHash": "0x21880599387bb198ffc3dc7a32beb67536f7c4a82e815e10b5be1a07d466b80f"},
        ]
        self.assertEqual(missing_anchors(present), [])

    def test_plan_does_not_rewind_before_deploy(self):
        self.assertEqual(plan(None)["action"], "wait-for-sync")
        self.assertEqual(plan(DEPLOY_BLOCK - 1)["action"], "wait-for-sync")
        decision = plan(135236408)
        self.assertEqual(decision["action"], "backfill")
        self.assertEqual(decision["from"], DEPLOY_BLOCK)
        self.assertEqual(decision["to"], 135236408)

    def test_postgres_apply_keeps_checkpoint(self):
        import psycopg2
        from tools.season1.hashutil import keccak256
        try:
            conn = psycopg2.connect("postgresql://haha:haha@127.0.0.1/haha_audit")
        except Exception as exc:
            self.skipTest("local audit database is not available: %s" % exc)
        conn.autocommit = False
        module = "0x" + "44" * 20
        block = 900000111
        block_hash = "0x" + "ab" * 32
        signer = "0x" + "55" * 20
        topic0 = "0x" + keccak256(b"ValidatorSet(address,bool)").hex()
        topic1 = "0x" + signer[2:].rjust(64, "0")
        data = "0x" + (1).to_bytes(32, "big").hex()
        logs = [
            {
                "address": module, "blockNumber": hex(block), "blockHash": block_hash,
                "transactionHash": "0x" + "cd" * 32, "transactionIndex": "0x0",
                "logIndex": "0x0", "topics": [topic0, topic1], "data": data,
            },
            {
                "address": "0xb2d023b8b5895835efd71c1150bead7bd735dfaa",
                "blockNumber": hex(block), "blockHash": block_hash,
                "transactionHash": "0x" + "ce" * 32, "transactionIndex": "0x1",
                "logIndex": "0x1", "topics": [topic0, topic1], "data": data,
            },
        ]
        headers = {block: {"hash": block_hash, "timestamp": hex(1795000000)}}
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO checkpoint (id, safe_block, safe_hash) VALUES (1, %s, %s)"
                    " ON CONFLICT (id) DO UPDATE SET safe_block = checkpoint.safe_block",
                    (135236408, bytes.fromhex("11" * 32)))
                cur.execute("SELECT safe_block FROM checkpoint WHERE id = 1")
                before = cur.fetchone()[0]
                counts = write_module_logs(cur, module, logs, headers)
                cur.execute("SELECT safe_block FROM checkpoint WHERE id = 1")
                after = cur.fetchone()[0]
                cur.execute("SELECT allowed FROM season1_validators WHERE account = %s",
                            (bytes.fromhex(signer[2:]),))
                allowed = cur.fetchone()
            self.assertEqual(before, after)
            self.assertEqual(counts["ValidatorSet"], 1)
            self.assertEqual(allowed[0], True)
        finally:
            conn.rollback()
            conn.close()


if __name__ == "__main__":
    unittest.main()
