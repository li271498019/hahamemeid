"""EIP-712 VerifyAuth. Signing refuses unless a module address and a key are supplied.

The key never comes from this module. Callers pass an in-memory test key or an
env value they already hold. This file does not generate or store a production key.
"""

from eth_account import Account
from eth_account.messages import encode_typed_data

from tools.season1.constants import END_TS, SEASON_ID, START_TS
from tools.season1.hashutil import keccak256

VERIFY_TYPES = {
    "VerifyAuth": [
        {"name": "seasonId", "type": "uint256"},
        {"name": "dayIndex", "type": "uint64"},
        {"name": "aiId", "type": "bytes32"},
        {"name": "agentId", "type": "uint256"},
        {"name": "generation", "type": "uint64"},
        {"name": "taskPackHash", "type": "bytes32"},
        {"name": "verdict", "type": "uint8"},
        {"name": "nonce", "type": "uint256"},
        {"name": "deadline", "type": "uint64"},
    ],
}


class SignRejected(Exception):
    pass


def domain(chain_id, module):
    if module is None or int(module, 16) == 0:
        raise SignRejected("module address is unset; fail closed")
    return {
        "name": "HahaSeason1",
        "version": "1",
        "chainId": int(chain_id),
        "verifyingContract": module,
    }


def _check_window(message, now):
    day = int(message["dayIndex"])
    deadline = int(message["deadline"])
    start = day * 86400
    end = (day + 1) * 86400
    if deadline != end:
        raise SignRejected("deadline must be the end of that UTC day")
    if now < start or now >= end:
        raise SignRejected("verification is only signed inside that UTC day")
    if now < START_TS or now >= END_TS:
        raise SignRejected("outside the 15-day window; no makeup")
    if int(message["seasonId"]) != SEASON_ID:
        raise SignRejected("season")
    if int(message["verdict"]) not in (0, 1):
        raise SignRejected("verdict")
    if int(message["generation"]) < 1:
        raise SignRejected("generation")


def sign_verify(private_key, message, chain_id, module, now, allowed_signers=None):
    if not private_key:
        raise SignRejected("no signing key configured")
    _check_window(message, now)
    account = Account.from_key(private_key)
    if allowed_signers is not None and account.address.lower() not in {a.lower() for a in allowed_signers}:
        raise SignRejected("signer has been removed")
    signable = encode_typed_data(
        full_message={
            "types": VERIFY_TYPES,
            "primaryType": "VerifyAuth",
            "domain": domain(chain_id, module),
            "message": message,
        }
    )
    signed = Account.sign_message(signable, private_key)
    return {
        "signer": account.address,
        "signature": "0x" + signed.signature.hex(),
        "domain": domain(chain_id, module),
    }


def require_live_validator(eth_call, module, signer):
    """Read validators(address) at sign time. No cache. A failed or empty read stays closed."""
    if not module or int(module, 16) == 0:
        raise SignRejected("module unset")
    if eth_call is None:
        raise SignRejected("no live chain read")
    selector = keccak256(b"validators(address)")[:4]
    data = "0x" + selector.hex() + signer.lower().replace("0x", "").rjust(64, "0")
    try:
        raw = eth_call(module, data)
    except Exception as exc:
        raise SignRejected("chain read failed") from exc
    if not raw or raw == "0x" or int(raw, 16) == 0:
        raise SignRejected("validator revoked or unreadable")


def recovered_in_allowed_set(private_key, allowed_signers):
    """A signature made earlier still recovers to the old key. Authorization is the current set."""
    account = Account.from_key(private_key)
    return account.address.lower() in {a.lower() for a in allowed_signers}


def finding_claim_window(committed_at, published_at, now):
    """Commit must be inside the season. The claim may be after END_TS."""
    if committed_at >= END_TS:
        return False
    if published_at is None:
        return False
    if published_at > committed_at + 7 * 86400:
        return False
    open_at = published_at + 86400
    close_at = open_at + 7 * 86400
    return open_at <= now < close_at
