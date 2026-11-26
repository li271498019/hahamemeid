"""Load the daily signer from C's existing env file. Never prints or writes a key."""

from pathlib import Path

from eth_account import Account

from tools.season1.eip712 import SignRejected


def _normalize_key(value):
    raw = value.strip().lower()
    if raw.startswith("0x"):
        raw = raw[2:]
    if len(raw) == 64 and all(ch in "0123456789abcdef" for ch in raw):
        return "0x" + raw
    return None


def load_matching_key(path, expected_address):
    """Return the one key in `path` whose address is `expected_address`.

    The file must already exist and must not be group- or world-readable.
    This function does not create, overwrite, or echo the file.
    """
    file = Path(path)
    if not file.is_file():
        raise SignRejected("signer env file is missing")
    if file.stat().st_mode & 0o077:
        raise SignRejected("signer env must not be readable by group or others")
    try:
        text = file.read_text(encoding="utf-8")
    except OSError as exc:
        raise SignRejected("signer env is not readable") from exc
    found = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        _name, value = line.split("=", 1)
        key = _normalize_key(value.strip().strip('"').strip("'"))
        if key is None:
            continue
        try:
            address = Account.from_key(key).address
        except Exception:
            continue
        if address.lower() == expected_address.lower():
            found.append(key)
    unique = list(dict.fromkeys(found))
    if len(unique) != 1:
        raise SignRejected("signer env has no single key for the expected address")
    return unique[0]
