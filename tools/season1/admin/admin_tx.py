"""Send admin transactions from the server key. Never logs a private key.

The admin key lives in /etc/haha/admin-signer.env (0600, root) as
ADMIN_PRIVATE_KEY=0x... . This module refuses to sign unless the key
derives to the verified admin address (0x083A...76Ef7) and the file is
not group- or world-readable. It never prints or writes the key itself.

Transactions are legacy (type 0) BSC transactions, signed locally with
eth_account and broadcast with eth_sendRawTransaction through the
indexer's RpcClient (same endpoints the indexer uses). Every send is
preceded by an eth_call simulation where the target supports it, and
every receipt is checked for status == 1 and the expected event topic.
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, "/opt/haha-season1")
sys.path.insert(0, "/opt/haha-indexer")

from eth_account import Account
from eth_abi import encode as abi_encode

from indexer.common import RpcClient, get_config
from tools.season1.constants import ADMIN
from tools.season1.mainnet import CHAIN_ID
from tools.season1.hashutil import keccak256
from tools.season1.signer_env import load_matching_key

ADMIN_ENV = "/etc/haha/admin-signer.env"
ADMIN_KEY_NAME = "ADMIN_PRIVATE_KEY"

# Gas price is fixed at exactly 1 gwei (1_000_000_000 wei) for every admin tx.
# Note: L asked for "1 wei", but 1 wei is below BSC validators' minimum
# gas price (1 gwei) and would never be mined -- the tx would sit in the
# mempool forever and the season would not open. 1 gwei is the lowest
# price that actually gets included, and the cost is negligible
# (~0.0001 BNB for a setDayRoot). Do not lower this without confirming
# with L that they accept the tx may never be mined.
GAS_PRICE_WEI = 1_000_000_000          # 1 gwei, fixed
GAS_BUFFER_NUM = 5                     # estimate * 5/4
GAS_BUFFER_DEN = 4
RECEIPT_TIMEOUT_S = 180
RECEIPT_POLL_S = 3
# Retry: one attempt waits this long for mining before the tx is treated
# as stuck/dropped and re-sent. BSC mines ~every 3s; 1 gwei is normally
# included within a few blocks, so 45s is generous.
RETRY_RECEIPT_TIMEOUT_S = 45
RETRY_PAUSE_S = 5
# A confirmed revert (status 0) is retried this many times in case it was
# a transient state race; a deterministic logic revert will fail again and
# is then raised instead of looping forever.
RETRY_MAX_REVERTS = 3


class AdminTxError(Exception):
    pass


def load_admin_key():
    """Return (key, address). Refuses unless the key matches ADMIN."""
    key = load_matching_key(ADMIN_ENV, ADMIN)
    address = Account.from_key(key).address
    if address.lower() != ADMIN.lower():
        raise AdminTxError("admin key does not derive to the admin address")
    return key, address


def selector(sig: str) -> bytes:
    return keccak256(sig.encode())[:4]


def encode_call(sig: str, types, values) -> str:
    data = selector(sig) + abi_encode(types, values)
    return "0x" + data.hex()


def _rpc():
    cfg = get_config()
    return RpcClient(cfg["rpc_urls"])


def eth_call(rpc, to, data, block="latest", from_address=None):
    """Read-only call. from_address matters: admin-only functions
    (setDayRoot, setTaskPack, adminMint, attestFulfillment) revert unless
    the caller is the admin, so simulations of those MUST pass the admin
    address here, or they will always (wrongly) look like a revert."""
    call_obj = {"to": to, "data": data}
    if from_address:
        call_obj["from"] = from_address
    params = [call_obj, block]
    return rpc.call("eth_call", params)


def get_nonce(rpc, address):
    return int(rpc.call("eth_getTransactionCount", [address, "pending"]), 16)


def get_gas_price(rpc):
    """Fixed 1 gwei. The network price is ignored on purpose: the admin
    txs must stay at the cheapest price that still gets mined."""
    return GAS_PRICE_WEI


def estimate_gas(rpc, tx):
    try:
        gas = int(rpc.call("eth_estimateGas", [tx]), 16)
    except Exception as exc:
        raise AdminTxError("gas estimation failed: %s" % exc) from exc
    gas = gas * GAS_BUFFER_NUM // GAS_BUFFER_DEN
    return max(gas, 100_000)


def send_transaction(rpc, key, address, to, data, value=0, gas_limit=None):
    """Build, sign, broadcast one legacy tx. Returns the tx hash (hex str)."""
    nonce = get_nonce(rpc, address)
    gas_price = get_gas_price(rpc)
    base = {"from": address, "to": to, "data": data, "value": hex(value)}
    if gas_limit is None:
        gas_limit = estimate_gas(rpc, base)
    tx = {
        "to": to,
        "value": value,
        "data": bytes.fromhex(data[2:]) if data.startswith("0x") else bytes.fromhex(data),
        "gas": gas_limit,
        "gasPrice": gas_price,
        "nonce": nonce,
        "chainId": CHAIN_ID,
    }
    signed = Account.sign_transaction(tx, key)
    raw = "0x" + signed.raw_transaction.hex()
    tx_hash = rpc.call("eth_sendRawTransaction", [raw])
    return tx_hash


def wait_receipt(rpc, tx_hash, timeout=RECEIPT_TIMEOUT_S):
    started = time.time()
    while time.time() - started < timeout:
        receipt = rpc.call("eth_getTransactionReceipt", [tx_hash])
        if receipt is not None:
            return receipt
        time.sleep(RECEIPT_POLL_S)
    raise AdminTxError("no receipt for %s within %ss" % (tx_hash, timeout))


def check_receipt(receipt, expect_topics=None):
    """status must be 1; every expected event topic must appear in the logs."""
    if receipt is None:
        raise AdminTxError("no receipt")
    status = receipt.get("status")
    if status not in ("0x1", 1):
        raise AdminTxError("transaction reverted (status %s)" % status)
    if expect_topics:
        topics = set()
        for log in receipt.get("logs", []):
            if log.get("topics"):
                topics.add(log["topics"][0].lower())
        for topic in expect_topics:
            if topic.lower() not in topics:
                raise AdminTxError("expected event topic %s missing from receipt" % topic)
    return receipt


def send_and_confirm(key, address, to, data, value=0, expect_topics=None, gas_limit=None):
    """One signed tx + receipt + event check. Returns (tx_hash, receipt)."""
    rpc = _rpc()
    tx_hash = send_transaction(rpc, key, address, to, data, value=value, gas_limit=gas_limit)
    receipt = wait_receipt(rpc, tx_hash)
    check_receipt(receipt, expect_topics)
    return tx_hash, receipt


def send_with_retry(key, address, to, data, value=0, expect_topics=None,
                    gas_limit=None, deadline=None):
    """Send until confirmed successful or the deadline passes.

    Returns (tx_hash, receipt, attempts). Once a tx is confirmed
    successful it is never re-sent. Retries cover: the tx not being mined
    in time (stuck/dropped at 1 gwei, or an RPC hiccup), a transient RPC
    failure, and a revert that looks like a state race (retried at most
    RETRY_MAX_REVERTS times -- a deterministic logic revert is raised
    instead of looping forever). If the deadline passes first, raises
    AdminTxError with the last error so the caller can report it.
    """
    rpc = _rpc()
    attempts = 0
    reverts = 0
    last_error = "no attempt yet"
    while True:
        if deadline is not None and time.time() >= deadline:
            raise AdminTxError(
                "retry deadline reached after %d attempt(s); last error: %s"
                % (attempts, last_error))
        attempts += 1
        # 1. Simulate first: a logic revert is caught before broadcasting.
        #    The simulation must run as the admin, or admin-only functions
        #    will revert on authorization even when the real tx would pass.
        try:
            eth_call(rpc, to, data, "latest", from_address=address)
        except Exception as exc:
            last_error = "simulation failed: %s" % exc
            reverts += 1
            if reverts >= RETRY_MAX_REVERTS:
                raise AdminTxError(
                    "call keeps failing simulation after %d attempt(s): %s"
                    % (attempts, last_error))
            time.sleep(RETRY_PAUSE_S)
            continue
        # 2. Broadcast.
        try:
            tx_hash = send_transaction(rpc, key, address, to, data,
                                       value=value, gas_limit=gas_limit)
        except Exception as exc:
            last_error = "broadcast failed: %s" % exc
            time.sleep(RETRY_PAUSE_S)
            continue
        # 3. Wait for mining.
        try:
            receipt = wait_receipt(rpc, tx_hash, timeout=RETRY_RECEIPT_TIMEOUT_S)
            check_receipt(receipt, expect_topics)
            return tx_hash, receipt, attempts
        except AdminTxError as exc:
            last_error = str(exc)
            if "reverted" in last_error or "status" in last_error:
                reverts += 1
                if reverts >= RETRY_MAX_REVERTS:
                    raise AdminTxError(
                        "transaction keeps reverting after %d attempt(s): %s"
                        % (attempts, last_error))
                time.sleep(RETRY_PAUSE_S)
                continue
            # No receipt in time: it may have been mined but the lookup
            # missed it, or it is stuck/dropped. Re-check once.
            try:
                receipt = rpc.call("eth_getTransactionReceipt", [tx_hash])
            except Exception:
                receipt = None
            if receipt is not None:
                try:
                    check_receipt(receipt, expect_topics)
                    return tx_hash, receipt, attempts
                except AdminTxError as exc2:
                    last_error = str(exc2)
                    reverts += 1
                    if reverts >= RETRY_MAX_REVERTS:
                        raise AdminTxError(
                            "transaction keeps reverting after %d attempt(s): %s"
                            % (attempts, last_error))
                    time.sleep(RETRY_PAUSE_S)
                    continue
            # Still unmined: loop and re-send. The fresh nonce read will be
            # the same nonce while the old tx is pending, so the new tx
            # replaces it in the mempool.
            time.sleep(RETRY_PAUSE_S)
            continue
