"""Unit tests for the pure parts of dog_store (no DB, no network).
Run from /opt/haha-indexer:  python3 -m unittest tests.test_dog_store -v"""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import common
from dog_store import seed_of, h2b


class TestDogStore(unittest.TestCase):
    def test_seed_formula_is_abi_encode_of_three_words(self):
        h = bytes.fromhex("11" * 32)
        want = common.keccak256(h + (7).to_bytes(32, "big") + (2).to_bytes(32, "big"))
        self.assertEqual(seed_of(h, 7, 2), want)
        self.assertNotEqual(seed_of(h, 7, 2), seed_of(h, 7, 3))   # reroll changes the seed
        self.assertNotEqual(seed_of(h, 7, 2), seed_of(h, 8, 2))

    def test_event_defs_registered(self):
        for key, name in ((common.CONTRACTS["dog"], "Committed"), (common.CONTRACTS["dogmarket"], "Sold")):
            self.assertTrue(any(a == key and n == name for (a, _t), (n, _p) in common.EVENTS.items()))
        self.assertIn(common.CONTRACTS["dog"], common.log_addresses())
        self.assertIn(common.CONTRACTS["dogmarket"], common.log_addresses())

    def test_decode_committed_and_sold(self):
        t0 = common.topic0("Committed(uint256,uint256,uint256)")
        data = (3).to_bytes(32, "big") + (136153344).to_bytes(32, "big")
        name, p = common.decode_log(common.CONTRACTS["dog"], [t0, "0x" + (5).to_bytes(32, "big").hex()], data)
        self.assertEqual((name, p["tokenId"], p["rerolls"], p["commitBlock"]), ("Committed", 5, 3, 136153344))
        t1 = common.topic0("Sold(uint256,address,address,uint256,uint256,uint256)")
        a = lambda x: "0x" + bytes(12).hex() + x * 20
        topics = [t1, "0x" + (9).to_bytes(32, "big").hex(), a("aa"), a("bb")]
        data = (10**18).to_bytes(32, "big") + (10**16).to_bytes(32, "big") + (99 * 10**16).to_bytes(32, "big")
        name, p = common.decode_log(common.CONTRACTS["dogmarket"], topics, data)
        self.assertEqual((name, p["tokenId"], p["price"], p["fee"], p["proceeds"]), ("Sold", 9, 10**18, 10**16, 99 * 10**16))
        self.assertEqual(p["seller"], "0x" + "aa" * 20)


if __name__ == "__main__":
    unittest.main()
