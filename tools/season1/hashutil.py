"""Keccak, ABI encode, and namehash. No network and no keys."""

from tools.season1.constants import HAHA_NODE, MEME_NODE

try:
    from Cryptodome.Hash import keccak as _keccak_mod
except ImportError:
    from Crypto.Hash import keccak as _keccak_mod


def keccak256(data: bytes) -> bytes:
    h = _keccak_mod.new(digest_bits=256)
    h.update(data)
    return h.digest()


def keccak_hex(data: bytes) -> str:
    return "0x" + keccak256(data).hex()


def hex32(value) -> str:
    if isinstance(value, str):
        raw = bytes.fromhex(value[2:] if value.startswith("0x") else value)
    else:
        raw = value
    if len(raw) != 32:
        raise ValueError("expected 32 bytes")
    return "0x" + raw.hex()


def word_uint(n: int) -> bytes:
    if n < 0 or n >= 1 << 256:
        raise ValueError("uint256 out of range")
    return n.to_bytes(32, "big")


def abi_encode_static(*words: bytes) -> bytes:
    return b"".join(words)


def leaf_hash(ai_id: str, balance: int, tier: int) -> bytes:
    """keccak256(keccak256(abi.encode(bytes32,uint256,uint8)))."""
    encoded = word_uint(int(ai_id, 16)) + word_uint(balance) + word_uint(tier)
    return keccak256(keccak256(encoded))


def commutative_keccak(a: bytes, b: bytes) -> bytes:
    return keccak256(a + b) if a < b else keccak256(b + a)


def namehash(label: str, tld: int) -> int:
    if tld == 0:
        parent = HAHA_NODE
    elif tld == 1:
        parent = MEME_NODE
    else:
        raise ValueError("tld")
    return int.from_bytes(keccak256(parent + keccak256(label.encode())), "big")
