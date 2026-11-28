"""Unit tests for common._mask_url (L7).

Run on the server (system python3 has the indexer deps):
    python3 -m unittest discover -s tests -v
Or from /opt/haha-indexer:
    python3 -m unittest tests.test_mask_url -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import _mask_url


class TestMaskUrl(unittest.TestCase):
    def test_ankr_path_key_masked(self):
        url = "https://rpc.ankr.com/bsc/0123456789abcdef0123456789abcdef"
        self.assertEqual(_mask_url(url), "https://rpc.ankr.com/bsc/***")

    def test_apikey_query_dropped(self):
        # L7: the old mask kept the query string, so ?apikey=<key> leaked.
        url = "https://rpc.example.com/bsc?apikey=querytoken"
        self.assertEqual(_mask_url(url), "https://rpc.example.com/bsc")
        self.assertNotIn("querytoken", _mask_url(url))

    def test_apikey_query_with_other_params_dropped(self):
        url = "https://rpc.example.com/bsc?apikey=querytoken&x=1"
        self.assertEqual(_mask_url(url), "https://rpc.example.com/bsc")

    def test_userinfo_stripped(self):
        url = "https://querytoken@rpc.example.com/bsc"
        self.assertEqual(_mask_url(url), "https://rpc.example.com/bsc")
        self.assertNotIn("querytoken", _mask_url(url))

    def test_userinfo_and_long_tail_masked(self):
        url = "https://user:querytoken@rpc.example.com/v1/abcdef0123456789"
        self.assertEqual(_mask_url(url), "https://rpc.example.com/v1/***")

    def test_plain_url_unchanged(self):
        url = "https://bsc-dataseed.binance.org"
        self.assertEqual(_mask_url(url), url)

    def test_short_single_segment_kept(self):
        url = "https://rpc.example.com/short"
        self.assertEqual(_mask_url(url), url)

    def test_port_preserved(self):
        url = "https://rpc.example.com:8545/bsc/0123456789abcdef0123456789abcdef"
        self.assertEqual(
            _mask_url(url), "https://rpc.example.com:8545/bsc/***")


if __name__ == "__main__":
    unittest.main()
