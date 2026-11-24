"""Shared helpers for the haha.meme V1 indexer: env loading, BSC JSON-RPC
client (rate-limited, rotating, exponential backoff), keccak256, and
ABI log decoding. Pure stdlib + pycryptodome (Cryptodome or Crypto)."""

import json
import os
import time
import urllib.error
import urllib.request

try:
    from Cryptodome.Hash import keccak as _keccak_mod
except ImportError:  # local dev venvs install pycryptodome as Crypto
    from Crypto.Hash import keccak as _keccak_mod

CHAIN_ID = 56
START_BLOCK = 134834631
CONFIRMATIONS = 3  # B 的规格原定 15（防重组，约 45 秒）；老板 2026-11-21 要求更快，
# BSC 上 3 块以上的重组基本没发生过，改成 3（约 9 秒）。重组检测（checkpoint 哈希比对 + 出错重算）还在，改回去只需改这一行。
MAX_RANGE = 2000
MIN_RANGE = 50

CONTRACTS = {
    "policy": "0x1f260aa05334f76a6e1d6fbd416f4d07d6bf3d96",
    "metadata": "0x790b670d664ea0046b0f2d395c182add3c389ab4",
    "resolver": "0x85c2dbdfd81a14b958b360159e8710e6c15370d6",
    "registry": "0x712ca65e2f6f5436c846569949072c8941982987",
    "registrar": "0x43426e37a31aafdaba851858e34b81dc300650f8",
    "identity": "0x54a70bf81b288d41013d7b57c2db0922f1e1a4d4",
    "points": "0xb2d023b8b5895835efd71c1150bead7bd735dfaa",
    "reputation": "0xf1a41b30d0c03fe178d3d76cbe6044e9d5ce1800",
    "market": "0xc7294df776344a39726b4c1256faf0e728c99835",
    "deployer": "0x3c7bd1649ac03afb65e6e10f949f45d764b6b601",
}
AI_REGISTRY = "0x60b9262456de011f7d15a54cdd8c48baaa8b022f"
ALL_ADDRESSES = [CONTRACTS[k] for k in
                 ("policy", "metadata", "resolver", "registry", "registrar",
                  "identity", "points", "reputation", "market", "deployer")]

ZERO_ADDRESS = "0x" + "00" * 20
ZERO_BYTES32 = "0x" + "00" * 32


def season1_module():
    """Public module address from the environment. Unset or zero stays closed."""
    raw = os.environ.get("SEASON1_MODULE", "").strip().lower()
    if len(raw) == 42 and raw.startswith("0x"):
        try:
            if int(raw, 16) == 0:
                return None
        except ValueError:
            return None
        return raw
    return None


def log_addresses():
    addrs = list(ALL_ADDRESSES)
    module = season1_module()
    if module and module not in addrs:
        addrs.append(module)
    return addrs


def keccak256(data: bytes) -> bytes:
    h = _keccak_mod.new(digest_bits=256)
    h.update(data)
    return h.digest()


def topic0(sig: str) -> str:
    return "0x" + keccak256(sig.encode()).hex()


def load_env(path):
    """Load KEY=VALUE lines (no shell expansion). Returns dict."""
    env = {}
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def get_config(env_path=None):
    env_path = env_path or os.environ.get("INDEXER_ENV", "/etc/haha/indexer.env")
    env = load_env(env_path)
    database_url = env.get("DATABASE_URL") or os.environ.get("DATABASE_URL", "")
    rpc_urls = env.get("BSC_RPC_URLS") or os.environ.get("BSC_RPC_URLS", "")
    urls = [u.strip() for u in rpc_urls.split(",") if u.strip()]
    if not urls:
        urls = ["https://bsc-dataseed.binance.org"]
    return {"database_url": database_url, "rpc_urls": urls, "env_path": env_path}


class RpcError(Exception):
    def __init__(self, msg, retryable=True, range_too_large=False):
        super().__init__(msg)
        self.retryable = retryable
        self.range_too_large = range_too_large


def _mask_url(url):
    # Mask a possible API key in a URL for logging. Ankr-style keys live
    # in the last path segment; hide any long trailing segment so a key
    # never reaches stderr / the systemd journal.
    try:
        from urllib.parse import urlsplit, urlunsplit
        parts = [s for s in urlsplit(url).path.split("/") if s]
        if parts and len(parts[-1]) >= 16:
            parts[-1] = "***"
            q = urlsplit(url)
            return urlunsplit((q.scheme, q.netloc,
                               "/" + "/".join(parts), q.query, q.fragment))
    except Exception:
        pass
    return url


class RpcClient:
    """JSON-RPC client: <=5 req/s per endpoint, exponential backoff
    1s..60s on 429/timeout, rotate to the next endpoint after 3
    consecutive failures."""

    def __init__(self, urls, timeout=30):
        self.urls = urls
        self.timeout = timeout
        self.idx = 0
        self.consecutive_failures = 0
        self.backoff = 1.0
        self.last_call = {u: 0.0 for u in urls}
        self.last_error = None
        self._id = 0

    @property
    def url(self):
        return self.urls[self.idx]

    @property
    def log_url(self):
        # Current endpoint with any API key masked; safe for logs.
        return _mask_url(self.url)

    def _rotate(self):
        self.idx = (self.idx + 1) % len(self.urls)
        self.consecutive_failures = 0
        self.backoff = 1.0

    def _throttle(self):
        now = time.monotonic()
        wait = 0.21 - (now - self.last_call[self.url])
        if wait > 0:
            time.sleep(wait)
        self.last_call[self.url] = time.monotonic()

    def call(self, method, params):
        """One logical call; retries across endpoints with backoff.
        Raises RpcError if every endpoint fails. For eth_getLogs, rate
        limits / timeouts also flag range_too_large so the caller halves
        its range (spec: halve on limit or 'range too large')."""
        import sys as _sys
        attempts = 0
        max_attempts = 3 * len(self.urls)
        range_issue = False
        while attempts < max_attempts:
            attempts += 1
            self._throttle()
            self._id += 1
            body = json.dumps({"jsonrpc": "2.0", "id": self._id,
                               "method": method, "params": params}).encode()
            req = urllib.request.Request(
                self.url, data=body,
                headers={"Content-Type": "application/json",
                         "User-Agent": "haha-indexer/1.0"})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    payload = json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                if e.code in (429, 403, 500, 502, 503, 504):
                    if method == "eth_getLogs" and e.code in (429, 403):
                        range_issue = True
                    self._note_failure("HTTP %s from %s" % (e.code, self.log_url))
                    _sys.stderr.write("[rpc] %s %s -> HTTP %s (fail %d)\n"
                                      % (method, self.log_url, e.code,
                                         self.consecutive_failures))
                    time.sleep(self.backoff)
                    self.backoff = min(60.0, self.backoff * 2)
                    if self.consecutive_failures >= 3:
                        self._rotate()
                    continue
                raise RpcError("HTTP %s from %s" % (e.code, self.log_url))
            except Exception as e:  # timeout / connection error
                if method == "eth_getLogs":
                    range_issue = True
                self._note_failure("%s: %s" % (self.log_url, e))
                _sys.stderr.write("[rpc] %s %s -> %s (fail %d)\n"
                                  % (method, self.log_url, e,
                                     self.consecutive_failures))
                time.sleep(self.backoff)
                self.backoff = min(60.0, self.backoff * 2)
                if self.consecutive_failures >= 3:
                    self._rotate()
                continue
            if "error" in payload:
                msg = str(payload["error"].get("message", payload["error"]))
                low = msg.lower()
                if ("range" in low and "large" in low) or "too large" in low:
                    raise RpcError(msg, range_too_large=True)
                if "limit exceeded" in low:
                    if method == "eth_getLogs":
                        range_issue = True
                    self._note_failure("RPC error from %s: %s" % (self.log_url, msg))
                    _sys.stderr.write("[rpc] %s %s -> %s (fail %d)\n"
                                      % (method, self.log_url, msg,
                                         self.consecutive_failures))
                    time.sleep(self.backoff)
                    self.backoff = min(60.0, self.backoff * 2)
                    if self.consecutive_failures >= 3:
                        self._rotate()
                    continue
                self._note_failure("RPC error from %s: %s" % (self.log_url, msg))
                time.sleep(self.backoff)
                self.backoff = min(60.0, self.backoff * 2)
                if self.consecutive_failures >= 3:
                    self._rotate()
                continue
            self.consecutive_failures = 0
            self.backoff = 1.0
            self.last_error = None
            return payload.get("result")
        raise RpcError("all RPC endpoints failed; last: %s" % self.last_error,
                       range_too_large=range_issue)

    def _note_failure(self, msg):
        self.consecutive_failures += 1
        self.last_error = msg

    def block_number(self):
        return int(self.call("eth_blockNumber", []), 16)

    def get_logs(self, from_block, to_block):
        return self.call("eth_getLogs", [{
            "fromBlock": hex(from_block),
            "toBlock": hex(to_block),
            "address": log_addresses(),
        }])

    def get_block(self, number):
        return self.call("eth_getBlockByNumber", [hex(number), False])

    def eth_call(self, to, data, block="latest"):
        return self.call("eth_call", [{"to": to, "data": data}, block])


# ---------------------------------------------------------------- ABI decode

def _u(word):
    return int.from_bytes(word, "big")


def _addr(word):
    return "0x" + word[12:].hex()


def _b32(word):
    return "0x" + word.hex()


def _bool(word):
    return word[-1] != 0


def _str(data, slot_off):
    pos = _u(data[slot_off:slot_off + 32])
    ln = _u(data[pos:pos + 32])
    return data[pos + 32:pos + 32 + ln].decode("utf-8", "replace")


def _decode_word(typ, word):
    if typ == "address":
        return _addr(word)
    if typ == "bytes32":
        return _b32(word)
    if typ == "bool":
        return _bool(word)
    if typ in ("uint256", "uint8", "uint16", "uint64"):
        return _u(word)
    if typ == "int256":
        v = _u(word)
        return v - (1 << 256) if v >= (1 << 255) else v
    raise ValueError("unsupported static type %s" % typ)


# (event name, [(param name, solidity type, indexed)]) per contract.
# Canonical signatures are taken from src/ (main @ 756638f9); topic0 is
# computed at import so a typo fails loudly instead of silently missing logs.
_EVENT_DEFS = [
    ("registrar", "NameMinted(uint256,address,uint8,bytes32,string,bool)",
     [("tokenId", "uint256", True), ("owner", "address", True),
      ("tld", "uint8", False), ("aiId", "bytes32", True),
      ("label", "string", False), ("reservedMint", "bool", False)]),
    ("registrar", "Transfer(address,address,uint256)",
     [("from", "address", True), ("to", "address", True),
      ("tokenId", "uint256", True)]),
    ("registrar", "Approval(address,address,uint256)",
     [("owner", "address", True), ("approved", "address", True),
      ("tokenId", "uint256", True)]),
    ("registrar", "ApprovalForAll(address,address,bool)",
     [("owner", "address", True), ("operator", "address", True),
      ("approved", "bool", False)]),
    ("market", "Listed(uint256,address,uint256)",
     [("tokenId", "uint256", True), ("seller", "address", True),
      ("price", "uint256", False)]),
    ("market", "PriceUpdated(uint256,address,uint256,uint256)",
     [("tokenId", "uint256", True), ("seller", "address", True),
      ("oldPrice", "uint256", False), ("newPrice", "uint256", False)]),
    ("market", "Cancelled(uint256,address)",
     [("tokenId", "uint256", True), ("seller", "address", True)]),
    ("market", "StaleCleared(uint256,address,address)",
     [("tokenId", "uint256", True), ("seller", "address", True),
      ("currentOwner", "address", True)]),
    ("market", "Sold(uint256,address,address,uint256,uint256,uint256)",
     [("tokenId", "uint256", True), ("seller", "address", True),
      ("buyer", "address", True), ("price", "uint256", False),
      ("fee", "uint256", False), ("proceeds", "uint256", False)]),
    ("market", "Withdrawn(address,uint256)",
     [("account", "address", True), ("amount", "uint256", False)]),
    ("identity", "AgentActivated(uint256,uint256,address,bytes32,uint64,string)",
     [("agentId", "uint256", True), ("nameTokenId", "uint256", True),
      ("owner", "address", True), ("operatorAiId", "bytes32", False),
      ("generation", "uint64", False), ("agentURI", "string", False)]),
    ("identity", "URIUpdated(uint256,string,address)",
     [("agentId", "uint256", True), ("newURI", "string", False),
      ("updatedBy", "address", True)]),
    ("identity", "AgentReset(uint256,uint256,address)",
     [("nameTokenId", "uint256", True), ("agentId", "uint256", True),
      ("previousOwner", "address", True)]),
    ("identity", "AgentOperatorSet(uint256,address,bool)",
     [("agentId", "uint256", True), ("operator", "address", True),
      ("allowed", "bool", False)]),
    ("identity", "Transfer(address,address,uint256)",
     [("from", "address", True), ("to", "address", True),
      ("tokenId", "uint256", True)]),
    ("reputation", "Rated(uint256,bytes32,address,uint8,string,bool)",
     [("agentId", "uint256", True), ("aiId", "bytes32", True),
      ("rater", "address", True), ("stars", "uint8", False),
      ("review", "string", False), ("edited", "bool", False)]),
    ("points", "PointsChanged(bytes32,address,int256,uint256,bytes32)",
     [("aiId", "bytes32", True), ("user", "address", True),
      ("delta", "int256", False), ("newBalance", "uint256", False),
      ("reason", "bytes32", True)]),
    ("points", "Earned(bytes32,bytes32,address,uint256,bytes32,uint256)",
     [("actionId", "bytes32", True), ("aiId", "bytes32", True),
      ("user", "address", True), ("amount", "uint256", False),
      ("uniqueKey", "bytes32", False), ("newBalance", "uint256", False)]),
    ("points", "PointParamsUpdated(uint256,uint256,uint256,uint256,uint256,uint256)",
     [("checkInPoints", "uint256", False), ("mintReward", "uint256", False),
      ("followPoints", "uint256", False), ("retweetPoints", "uint256", False),
      ("likePoints", "uint256", False), ("commentPoints", "uint256", False)]),
    ("points", "SpenderUpdated(address,bool)",
     [("spender", "address", True), ("allowed", "bool", False)]),
    ("points", "EarnerUpdated(bytes32,address,uint256,uint64,uint256,uint8,bool,bool)",
     [("actionId", "bytes32", True), ("module", "address", True),
      ("points", "uint256", False), ("perUserDailyCap", "uint64", False),
      ("globalDailyPoints", "uint256", False), ("keyMode", "uint8", False),
      ("requireName", "bool", False), ("enabled", "bool", False)]),
    ("points", "SpenderBudgetUpdated(address,uint256,uint256)",
     [("spender", "address", True), ("perUserDailyPoints", "uint256", False),
      ("globalDailyPoints", "uint256", False)]),
    ("points", "RoundOpened(uint256,bytes32,bytes32,address,uint64)",
     [("sessionId", "uint256", True), ("gameId", "bytes32", True),
      ("aiId", "bytes32", True), ("player", "address", False),
      ("openDay", "uint64", False)]),
    ("points", "RoundClaimed(uint256,bytes32,bytes32,uint256)",
     [("sessionId", "uint256", True), ("gameId", "bytes32", True),
      ("aiId", "bytes32", True), ("amount", "uint256", False)]),
    ("points", "GameUpdated(bytes32,address,uint256,uint256,uint256,bool)",
     [("gameId", "bytes32", True), ("module", "address", True),
      ("maxScorePerRound", "uint256", False),
      ("perAiDailyPoints", "uint256", False),
      ("globalDailyPoints", "uint256", False), ("enabled", "bool", False)]),
    ("resolver", "AddrChanged(bytes32,address)",
     [("node", "bytes32", True), ("a", "address", False)]),
    ("resolver", "TextChanged(bytes32,string,string,string)",
     [("node", "bytes32", True), ("indexedKey", "string", True),
      ("key", "string", False), ("value", "string", False)]),
    ("resolver", "RecordsCleared(bytes32)",
     [("node", "bytes32", True)]),
    ("resolver", "PrimaryNameSet(address,bytes32,string)",
     [("user", "address", True), ("node", "bytes32", True),
      ("fullName", "string", False)]),
    ("resolver", "PrimaryNameCleared(address,bytes32)",
     [("user", "address", True), ("node", "bytes32", True)]),
    ("registry", "NewOwner(bytes32,bytes32,address)",
     [("node", "bytes32", True), ("label", "bytes32", True),
      ("owner", "address", False)]),
    ("registry", "NewResolver(bytes32,address)",
     [("node", "bytes32", True), ("resolver", "address", False)]),
    ("registry", "Transfer(bytes32,address)",
     [("node", "bytes32", True), ("owner", "address", False)]),
    ("policy", "ListsFrozen(uint256,uint256)",
     [("bannedCount", "uint256", False), ("reservedCount", "uint256", False)]),
]

# (contract key, topic0) -> (event name, params)
EVENTS = {}
for _contract, _sig, _params in _EVENT_DEFS:
    _name = _sig.split("(")[0]
    EVENTS[(CONTRACTS[_contract], topic0(_sig))] = (_name, _params)

# topic0 -> set of contract keys that emit it (Transfer exists twice)
TOPIC0_CONTRACTS = {}
for _contract, _sig, _params in _EVENT_DEFS:
    TOPIC0_CONTRACTS.setdefault(topic0(_sig), set()).add(_contract)

HANDLEOF_SELECTOR = topic0("handleOf(address)")[:10]  # 0x + 4 bytes


def decode_log(address, topics, data):
    """Decode one raw log. Returns (event_name, params dict) or (None, {}).
    topics: list of 0x hex strings (topics[0] = topic0). data: bytes."""
    key = (address.lower(), topics[0].lower() if topics else "")
    hit = EVENTS.get(key)
    if hit is None:
        return None, {}
    name, params = hit
    out = {}
    topic_idx = 1
    data_off = 0
    for pname, typ, indexed in params:
        if indexed:
            if typ == "string":
                # dynamic indexed param: topic is its keccak, not decodable
                out[pname] = None
            else:
                word = bytes.fromhex(topics[topic_idx][2:])
                out[pname] = _decode_word(typ, word)
            topic_idx += 1
        else:
            if typ == "string":
                out[pname] = _str(data, data_off)
            else:
                out[pname] = _decode_word(typ, data[data_off:data_off + 32])
            data_off += 32
    return name, out


def decode_handleof_return(hexdata):
    """Decode handleOf(address) -> string return data."""
    if not hexdata or hexdata == "0x":
        return None
    data = bytes.fromhex(hexdata[2:])
    if len(data) < 64:
        return None
    try:
        return _str(data, 0)
    except Exception:
        return None
