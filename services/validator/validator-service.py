#!/usr/bin/env python3
"""haha.meme G13 验证者服务（Validation Registry，v1）。

按已冻结计划 ~/workspace/erc8004-g13-validation-registry-plan.md §6.2 写。

- 轮询 HahaValidation 合约的 ValidationRequest / ValidationDisputed 事件，
  每 30 秒查一次；收到请求后立即检查并提交 validationResponse。
- v1 唯一验证者 = 合约管理员（链上 validator()），服务用服务器上已有的
  管理员密钥签名：/etc/haha/admin-signer.env（0600，root），第一季自动化
  在用，不另写密钥。密钥值绝不写入日志、文件或聊天。
- 只做两类验证（计划 §3）：接口可达（endpoint-reachable）与身份真实性
  （identity-verified）。争议（ValidationDisputed）触发重新检查并提交新结果。
- BSC RPC 用服务器已配置的 /etc/haha/indexer.env 的 BSC_RPC_URLS
  （与索引器同一组），不直连公开节点；复用索引器的 RpcClient。
- 交易：legacy（type 0），gas 固定 1 gwei，与第一季自动化一致
  （admin_tx.py 的 GAS_PRICE_WEI）。nonce 冲突重试最多 3 次，
  间隔 1s / 2s / 4s；合约 revert 不重试，只记日志。
- 日志：/opt/haha-validation/validator.log；进度：/opt/haha-validation/state.json。
- systemd 服务 haha-validator.service（见同目录单元文件）。

环境变量（仅用于测试 / 运维覆盖；服务器默认不设）：
  VALIDATOR_RPC_URLS   逗号分隔的 BSC RPC 地址（默认读 /etc/haha/indexer.env）
  VALIDATOR_ADMIN_ENV  管理员密钥文件（默认 /etc/haha/admin-signer.env）
  VALIDATOR_STATE_DIR  日志与 state.json 所在目录（默认 /opt/haha-validation）
  VALIDATOR_POLL_INTERVAL 轮询间隔秒（默认 30）
  VALIDATOR_ONCE=1     只轮询一轮后退出（测试用）
  VALIDATOR_IPFS_GATEWAY  ipfs:// 网关（默认 https://ipfs.io/ipfs/)
  VALIDATOR_CHAIN_ID   链 ID（默认 56，BSC 主网）
  VALIDATOR_DEPLOY_BLOCK  首次轮询起始块（默认 135619015，测试用 0）
"""

import base64
import json
import logging
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# 服务器上的现成模块（第一季自动化同款）：索引器 RpcClient 与密钥加载。
# 本地测试环境没有这些路径时，用本文件内的同语义后备实现。
# ---------------------------------------------------------------------------
sys.path.insert(0, "/opt/haha-season1")
sys.path.insert(0, "/opt/haha-indexer")

try:
    from indexer.common import RpcClient as _ServerRpcClient
    from indexer.common import get_config as _server_get_config
    HAVE_SERVER_RPC = True
except Exception:  # 本地测试：无服务器代码
    _ServerRpcClient = None
    _server_get_config = None
    HAVE_SERVER_RPC = False

try:
    from tools.season1.signer_env import load_matching_key as _server_load_key
    HAVE_SERVER_KEYLOADER = True
except Exception:
    _server_load_key = None
    HAVE_SERVER_KEYLOADER = False

try:
    from eth_account import Account
    from eth_account.messages import encode_defunct, encode_typed_data
    from eth_abi import encode as abi_encode
    from eth_utils import keccak, to_checksum_address
except ImportError as exc:  # pragma: no cover
    raise SystemExit("validator-service needs eth_account + eth_abi: %s" % exc)

# ---------------------------------------------------------------------------
# 常量（已核对：主网部署回执 + 合约源码 HahaValidation.sol）
# ---------------------------------------------------------------------------
VALIDATION_ADDRESS = os.environ.get(
    "VALIDATOR_VALIDATION_ADDRESS", "0xAF9d2D3b6717469B21464baA12B022817841952b")
IDENTITY_ADDRESS = os.environ.get(
    "VALIDATOR_IDENTITY_ADDRESS", "0x54A70BF81B288d41013D7b57c2Db0922f1E1a4d4")
DEPLOY_BLOCK = int(os.environ.get("VALIDATOR_DEPLOY_BLOCK", "135619015"))  # HahaValidation 部署块
CHAIN_ID = int(os.environ.get("VALIDATOR_CHAIN_ID", "56"))
POLL_INTERVAL = int(os.environ.get("VALIDATOR_POLL_INTERVAL", "30"))
DOC_TIMEOUT_S = 10                # 请求文档 / 注册文件 / endpoint 超时
DOC_MAX_BYTES = 64 * 1024         # 请求文档上限 64KB（计划 §6.2）
GAS_PRICE_WEI = 1_000_000_000     # 1 gwei，固定（与 admin_tx.py 一致）
GAS_LIMIT = 500_000               # validationResponse 上限，实测约 10 万，留足余量
RECEIPT_TIMEOUT_S = 120
RECEIPT_POLL_S = 3
NONCE_RETRY_MAX = 3               # nonce 冲突最多重试 3 次
NONCE_RETRY_DELAYS = (1, 2, 4)    # 间隔 1s / 2s / 4s（计划 §6.2）
IPFS_GATEWAY = os.environ.get("VALIDATOR_IPFS_GATEWAY", "https://ipfs.io/ipfs/")
ADMIN_ENV = os.environ.get("VALIDATOR_ADMIN_ENV", "/etc/haha/admin-signer.env")
STATE_DIR = Path(os.environ.get("VALIDATOR_STATE_DIR", "/opt/haha-validation"))
LOG_FILE = STATE_DIR / "validator.log"
STATE_FILE = STATE_DIR / "state.json"

# 事件 topic0（keccak256，与 HahaValidation.sol 事件签名逐字对齐，
# 已用 eth_utils 独立验算，见 tests/t10_report.md）。
TOPIC_REQUEST = "0x530436c3634a98e1e626b0898be2f1e9980cc1bd2a78c07a0aba52d0a48a5059"
TOPIC_DISPUTED = "0xe3d32c9b1e490818f4656d2753e75fede5d1b74df812d64ccab705df76583a72"
# 函数 selector（keccak256 前 4 字节，已独立验算）。
SEL_VALIDATION_RESPONSE = "3d659a96"   # validationResponse(bytes32,uint8,string,bytes32,string)
SEL_VALIDATOR = "3a5381b5"             # validator()
SEL_GET_IDENTITY_REGISTRY = "bc4d861b"  # getIdentityRegistry()
SEL_TOKEN_URI = "c87b56dd"             # tokenURI(uint256)
SEL_OWNER_OF = "6352211e"              # ownerOf(uint256)

NONCE_ERROR_HINTS = ("nonce too low", "already used", "replacement underpriced",
                     "nonce has already been used", "invalid nonce")

# EIP-712 身份挑战（计划 §3.2 修订：BAW 只支持 EIP-712，服务同时认 EIP-191 与
# EIP-712）。Domain 固定：name HahaValidation，version 1，chainId 56，
# verifyingContract 主网 HahaValidation 地址；主类型 IdentityChallenge，
# 字段 agentId (uint256)、requestHash (bytes32)。verifyingContract 固定为
# 主网地址，不跟 VALIDATOR_VALIDATION_ADDRESS 走（测试在 anvil 上跑时，
# 签名与恢复用的 domain 仍是主网地址，与生产一致）。
EIP712_CHAIN_ID = int(os.environ.get("VALIDATOR_EIP712_CHAIN_ID", "56"))
EIP712_VERIFYING_CONTRACT = os.environ.get(
    "VALIDATOR_EIP712_CONTRACT", "0xAF9d2D3b6717469B21464baA12B022817841952b")
EIP712_DOMAIN = {
    "name": "HahaValidation",
    "version": "1",
    "chainId": EIP712_CHAIN_ID,
    "verifyingContract": EIP712_VERIFYING_CONTRACT,
}
EIP712_TYPES = {
    "EIP712Domain": [
        {"name": "name", "type": "string"},
        {"name": "version", "type": "string"},
        {"name": "chainId", "type": "uint256"},
        {"name": "verifyingContract", "type": "address"},
    ],
    "IdentityChallenge": [
        {"name": "agentId", "type": "uint256"},
        {"name": "requestHash", "type": "bytes32"},
    ],
}

# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------
log = logging.getLogger("haha-validator")


def setup_logging():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    handler_file = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
    handler_out = logging.StreamHandler(sys.stdout)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s",
                            datefmt="%Y-%m-%dT%H:%M:%S%z")
    handler_file.setFormatter(fmt)
    handler_out.setFormatter(fmt)
    log.setLevel(logging.INFO)
    log.addHandler(handler_file)
    log.addHandler(handler_out)


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# RPC（优先用索引器 RpcClient；本地测试用同语义的最小实现）
# ---------------------------------------------------------------------------
def _load_rpc_urls():
    override = os.environ.get("VALIDATOR_RPC_URLS", "").strip()
    if override:
        return [u.strip() for u in override.split(",") if u.strip()]
    if HAVE_SERVER_RPC:
        return _server_get_config()["rpc_urls"]
    env_path = os.environ.get("INDEXER_ENV", "/etc/haha/indexer.env")
    urls = []
    try:
        for line in Path(env_path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("BSC_RPC_URLS="):
                urls = [u.strip() for u in line.split("=", 1)[1].split(",") if u.strip()]
    except OSError:
        pass
    return urls or ["https://bsc-dataseed.binance.org"]


class _FallbackRpcClient:
    """最小 JSON-RPC 客户端：多节点轮换 + 指数退避（与 indexer RpcClient 同模式）。"""

    def __init__(self, urls, timeout=30):
        self.urls = urls
        self.timeout = timeout
        self.idx = 0
        self._id = 0

    @property
    def url(self):
        return self.urls[self.idx]

    @property
    def log_url(self):
        # 只记 scheme + host，绝不把 URL 里可能带的 API key 记进日志。
        try:
            from urllib.parse import urlparse
            p = urlparse(self.url)
            return "%s://%s" % (p.scheme, p.hostname or "?")
        except Exception:
            return "rpc"

    def call(self, method, params):
        last_err = None
        for _ in range(3 * len(self.urls)):
            self._id += 1
            body = json.dumps({"jsonrpc": "2.0", "id": self._id,
                               "method": method, "params": params}).encode()
            req = urllib.request.Request(
                self.url, data=body,
                headers={"Content-Type": "application/json",
                         "User-Agent": "haha-validator/1.0"})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    payload = json.loads(resp.read().decode())
            except Exception as exc:
                last_err = exc
                self.idx = (self.idx + 1) % len(self.urls)
                time.sleep(1)
                continue
            if "error" in payload:
                raise RuntimeError("rpc %s failed: %s" % (method, payload["error"]))
            return payload.get("result")
        raise RuntimeError("rpc %s failed on all endpoints: %s" % (method, last_err))


def make_rpc():
    urls = _load_rpc_urls()
    if HAVE_SERVER_RPC:
        return _ServerRpcClient(urls)
    return _FallbackRpcClient(urls)


# ---------------------------------------------------------------------------
# eth_call 编解码（只用 eth_abi / 手工解码，不依赖 web3）
# ---------------------------------------------------------------------------
def _decode_address(word_hex):
    raw = bytes.fromhex(word_hex[2:] if word_hex.startswith("0x") else word_hex)
    return "0x" + raw[-20:].hex()


def _decode_string(hexdata):
    raw = bytes.fromhex(hexdata[2:] if hexdata.startswith("0x") else hexdata)
    if len(raw) < 64:
        raise ValueError("short string return data")
    length = int.from_bytes(raw[32:64], "big")
    return raw[64:64 + length].decode("utf-8")


def eth_call(rpc, to, data, block="latest"):
    result = rpc.call("eth_call", [{"to": to, "data": data}, block])
    if result is None:
        raise RuntimeError("eth_call returned null for %s" % to)
    return result


def chain_validator(rpc):
    return _decode_address(eth_call(rpc, VALIDATION_ADDRESS, "0x" + SEL_VALIDATOR))


def chain_identity_registry(rpc):
    return _decode_address(
        eth_call(rpc, VALIDATION_ADDRESS, "0x" + SEL_GET_IDENTITY_REGISTRY))


def chain_agent_uri(rpc, identity, agent_id):
    data = "0x" + SEL_TOKEN_URI + agent_id.to_bytes(32, "big").hex()
    return _decode_string(eth_call(rpc, identity, data))


def chain_agent_owner(rpc, identity, agent_id):
    data = "0x" + SEL_OWNER_OF + agent_id.to_bytes(32, "big").hex()
    return _decode_address(eth_call(rpc, identity, data))


def request_hash(validator_address, agent_id, request_uri):
    """计划 §3.4：keccak256(abi.encodePacked(validatorAddress, agentId, requestURI))。"""
    packed = (bytes.fromhex(validator_address[2:])
              + agent_id.to_bytes(32, "big")
              + request_uri.encode("utf-8"))
    return "0x" + keccak(packed).hex()


# ---------------------------------------------------------------------------
# 密钥（只读 /etc/haha/admin-signer.env；值绝不记日志）
# ---------------------------------------------------------------------------
def load_admin_key(expected_address):
    """返回 (key, address)。密钥须派生出 expected_address（链上当前验证者），
    否则拒绝——这是发交易前的最后一道门。"""
    if HAVE_SERVER_KEYLOADER:
        key = _server_load_key(ADMIN_ENV, expected_address)
    else:
        key = _load_matching_key_fallback(ADMIN_ENV, expected_address)
    address = Account.from_key(key).address
    if address.lower() != expected_address.lower():
        raise RuntimeError("admin key does not derive to the current validator")
    return key, address


def _load_matching_key_fallback(path, expected_address):
    """与 tools.season1.signer_env.load_matching_key 同语义的后备实现
    （文件须存在、须为 0600 且仅 root 可读、只取派生地址匹配的那一把）。"""
    file = Path(path)
    if not file.is_file():
        raise RuntimeError("signer env file is missing: %s" % path)
    if file.stat().st_mode & 0o077:
        raise RuntimeError("signer env must not be readable by group or others")
    found = []
    for line in file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        value = line.split("=", 1)[1].strip().strip('"').strip("'").lower()
        if value.startswith("0x"):
            value = value[2:]
        if len(value) == 64 and all(c in "0123456789abcdef" for c in value):
            key = "0x" + value
            try:
                if Account.from_key(key).address.lower() == expected_address.lower():
                    found.append(key)
            except Exception:
                continue
    if len(set(found)) != 1:
        raise RuntimeError("signer env has no single key for the expected address")
    return found[0]


# ---------------------------------------------------------------------------
# HTTP 拉取（请求文档 / 注册文件 / endpoint）
# ---------------------------------------------------------------------------
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """3xx 不跟随跳转：3xx 响应本身即证明服务存在（计划 §3.1）。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _http_opener():
    return urllib.request.build_opener(_NoRedirect())


def resolve_doc_url(uri):
    """只接受 https:// 与 ipfs://（经网关）；其余 scheme 拒绝。"""
    if uri.startswith("https://"):
        return uri
    if uri.startswith("ipfs://"):
        rest = uri[len("ipfs://"):]
        return IPFS_GATEWAY.rstrip("/") + "/" + rest
    return None


def fetch_url(url, timeout=DOC_TIMEOUT_S, max_bytes=DOC_MAX_BYTES):
    """返回 (body_bytes, error_str)。error_str 为 None 表示成功。
    超过 max_bytes / 超时 / 连接失败都返回错误，不抛异常。"""
    req = urllib.request.Request(url, headers={"User-Agent": "haha-validator/1.0"})
    try:
        with _http_opener().open(req, timeout=timeout) as resp:
            length = resp.headers.get("Content-Length")
            if length is not None and int(length) > max_bytes:
                return None, "文档超过 64KB 上限（Content-Length %s 字节）" % length
            body = resp.read(max_bytes + 1)
    except urllib.error.HTTPError as exc:
        # HTTP 状态码本身是有效响应（如注册文件 404），调用方按状态码处理。
        return None, "HTTP %s" % exc.code
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as exc:
        return None, "拉取失败：%s" % exc
    if len(body) > max_bytes:
        return None, "文档超过 64KB 上限（实际多于 %d 字节）" % max_bytes
    return body, None


def fetch_json_doc(uri):
    """拉请求文档 / 注册文件。返回 (doc_dict_or_None, error_str)。"""
    url = resolve_doc_url(uri)
    if url is None:
        return None, "不支持的 URI scheme（只接受 https:// 与 ipfs://）：%s" % uri.split("://", 1)[0]
    body, err = fetch_url(url)
    if err is not None:
        return None, "请求文档无法读取（%s）：%s" % (uri, err)
    try:
        doc = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        return None, "请求文档 JSON 无效：%s" % exc
    if not isinstance(doc, dict):
        return None, "请求文档不是 JSON 对象"
    return doc, None


# ---------------------------------------------------------------------------
# 两类验证（计划 §3）
# ---------------------------------------------------------------------------
def check_endpoint_reachable(doc, agent_id, rpc, identity):
    """返回 (score, evidence_dict)。先核对 endpoint 在注册文件里，再 GET/POST。"""
    endpoint = doc.get("endpoint")
    if not endpoint or not isinstance(endpoint, str):
        return 0, {"reason": "请求文档缺 endpoint 字段"}
    try:
        agent_uri = chain_agent_uri(rpc, identity, agent_id)
    except Exception as exc:
        return 0, {"reason": "读 agent 注册文件失败：%s" % exc, "endpoint": endpoint}
    reg, err = fetch_json_doc(agent_uri)
    if err is not None:
        return 0, {"reason": "注册文件无法读取：%s" % err, "endpoint": endpoint}
    endpoints = []
    for svc in reg.get("services", []) or []:
        if isinstance(svc, dict) and isinstance(svc.get("endpoint"), str):
            endpoints.append(svc["endpoint"])
    if endpoint not in endpoints:
        return 0, {"reason": "endpoint 未在注册文件中",
                   "endpoint": endpoint, "registeredEndpoints": endpoints}
    # GET，超时 10 秒；405 改 POST 空 JSON。
    method, status, elapsed_ms = _probe_endpoint(endpoint, "GET")
    if status == 405:
        method, status, elapsed_ms = _probe_endpoint(endpoint, "POST")
    if status is None:
        return 0, {"method": method, "endpoint": endpoint,
                   "reason": "连接失败/超时/DNS 失败", "checkedAt": now_iso()}
    if 200 <= status < 400 or status in (401, 403):
        score = 100
    else:
        score = 0
    return score, {"method": method, "endpoint": endpoint, "httpStatus": status,
                   "responseMs": elapsed_ms, "checkedAt": now_iso()}


def _probe_endpoint(endpoint, method):
    """返回 (method, http_status_or_None, elapsed_ms)。3xx 不跟随跳转。"""
    body = b"{}" if method == "POST" else None
    headers = {"User-Agent": "haha-validator/1.0"}
    if method == "POST":
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(endpoint, data=body, headers=headers, method=method)
    started = time.monotonic()
    try:
        with _http_opener().open(req, timeout=DOC_TIMEOUT_S) as resp:
            return method, resp.status, int((time.monotonic() - started) * 1000)
    except urllib.error.HTTPError as exc:
        return method, exc.code, int((time.monotonic() - started) * 1000)
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError):
        return method, None, int((time.monotonic() - started) * 1000)


def _recover_eip191(req_hash, sig_bytes):
    """EIP-191 个人签名：签 requestHash 的 32 字节原始值。"""
    return Account.recover_message(
        encode_defunct(primitive=bytes.fromhex(req_hash[2:])),
        signature=sig_bytes)


def _recover_eip712(agent_id, req_hash, sig_bytes):
    """EIP-712 身份挑战：IdentityChallenge{agentId, requestHash}，
    domain HahaValidation/1/56/主网合约地址（计划 §3.2 修订）。"""
    msg = {
        "types": EIP712_TYPES,
        "domain": EIP712_DOMAIN,
        "primaryType": "IdentityChallenge",
        "message": {
            "agentId": agent_id,
            "requestHash": bytes.fromhex(req_hash[2:]),
        },
    }
    return Account.recover_message(
        encode_typed_data(full_message=msg), signature=sig_bytes)


def check_identity_verified(doc, agent_id, rpc, identity, req_hash):
    """返回 (score, evidence_dict)。
    先试 EIP-191（签 requestHash 的 32 字节原始值）；恢复地址与 ownerOf
    不匹配时再试 EIP-712（IdentityChallenge，计划 §3.2 修订——BAW 只支持
    EIP-712）。任一匹配 → 100，否则 0。文档可带可选 signatureType 字段
    （"eip191"/"eip712"），有则优先试对应的方式，没有则两种都试。"""
    signature = doc.get("signature")
    if not signature or not isinstance(signature, str):
        return 0, {"reason": "请求文档缺 signature 字段"}
    try:
        owner = chain_agent_owner(rpc, identity, agent_id)
    except Exception as exc:
        return 0, {"reason": "读 agent 主人失败：%s" % exc}
    try:
        sig_bytes = bytes.fromhex(signature[2:] if signature.startswith("0x") else signature)
        if len(sig_bytes) != 65:
            raise ValueError("签名长度不是 65 字节")
    except Exception as exc:
        return 0, {"reason": "签名无效：%s" % exc, "owner": owner}
    sig_type = doc.get("signatureType")
    if sig_type == "eip712":
        attempts = ["eip712", "eip191"]
    else:  # "eip191" 或未指定：先 EIP-191，再 EIP-712
        attempts = ["eip191", "eip712"]
    tried = []
    for method in attempts:
        try:
            if method == "eip191":
                recovered = _recover_eip191(req_hash, sig_bytes)
            else:
                recovered = _recover_eip712(agent_id, req_hash, sig_bytes)
        except Exception as exc:
            tried.append({"method": method, "error": str(exc)})
            continue
        tried.append({"method": method, "recoveredAddress": recovered})
        if recovered.lower() == owner.lower():
            evidence = {"signature": signature, "signatureType": method,
                        "recoveredAddress": recovered, "ownerAddress": owner,
                        "match": True, "checkedAt": now_iso()}
            return 100, evidence
    last = tried[-1] if tried else {}
    evidence = {"signature": signature,
                "signatureType": sig_type if isinstance(sig_type, str) else None,
                "recoveredAddress": last.get("recoveredAddress"),
                "ownerAddress": owner, "match": False,
                "attempts": tried, "checkedAt": now_iso()}
    return 0, evidence


def run_check(doc, agent_id, rpc, identity, req_hash):
    """按请求文档 type 分派。返回 (score, tag, evidence_dict)。"""
    doc_type = doc.get("type")
    if doc_type == "endpoint-reachable":
        score, evidence = check_endpoint_reachable(doc, agent_id, rpc, identity)
        return score, "endpoint-reachable", evidence
    if doc_type == "identity-verified":
        score, evidence = check_identity_verified(doc, agent_id, rpc, identity, req_hash)
        return score, "identity-verified", evidence
    return 0, "", {"reason": "请求文档缺 type 字段或 type 未知：%r" % (doc_type,)}


# ---------------------------------------------------------------------------
# 证据（计划 §3.1/§3.2）
# v1 无证据托管服务（计划 §3.4 G4）：证据记录本身以 data: URI 形式
# 放在 responseURI 里（自包含、可直接打开），responseHash 为该记录的 keccak256。
# ---------------------------------------------------------------------------
def make_evidence(req_hash, agent_id, doc_type, score, evidence):
    record = {"requestHash": req_hash, "agentId": agent_id, "type": doc_type,
              "score": score, "checkedAt": now_iso(), "evidence": evidence}
    raw = json.dumps(record, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    response_hash = "0x" + keccak(raw).hex()
    response_uri = ("data:application/json;base64,"
                    + base64.b64encode(raw).decode("ascii"))
    return response_uri, response_hash


# ---------------------------------------------------------------------------
# 发 validationResponse（计划 §6.2：每次发前核对链上验证者；nonce 重试 3 次）
# ---------------------------------------------------------------------------
def submit_response(rpc, req_hash, score, response_uri, response_hash, tag):
    """发交易并等回执。返回 tx_hash。合约 revert 不重试；nonce 冲突重试最多 3 次。"""
    validator = chain_validator(rpc)
    key, address = load_admin_key(validator)
    if address.lower() != validator.lower():
        raise RuntimeError("签名密钥地址与链上验证者不一致，停发")
    data = "0x" + SEL_VALIDATION_RESPONSE + abi_encode(
        ["bytes32", "uint8", "string", "bytes32", "string"],
        [bytes.fromhex(req_hash[2:]), score, response_uri,
         bytes.fromhex(response_hash[2:]), tag]).hex()
    # 先 eth_call 模拟：逻辑 revert 在广播前就发现，不重试、不花 gas。
    try:
        rpc.call("eth_call", [{"from": address, "to": VALIDATION_ADDRESS,
                               "data": data}, "latest"])
    except Exception as exc:
        raise RuntimeError("validationResponse 模拟失败（合约会 revert，不重试）：%s" % exc)
    last_err = None
    for attempt in range(NONCE_RETRY_MAX + 1):
        nonce = int(rpc.call("eth_getTransactionCount", [address, "pending"]), 16)
        tx = {"to": to_checksum_address(VALIDATION_ADDRESS), "value": 0,
              "data": bytes.fromhex(data[2:]), "gas": GAS_LIMIT,
              "gasPrice": GAS_PRICE_WEI, "nonce": nonce, "chainId": CHAIN_ID}
        signed = Account.sign_transaction(tx, key)
        try:
            tx_hash = rpc.call("eth_sendRawTransaction",
                               ["0x" + signed.raw_transaction.hex()])
        except Exception as exc:
            last_err = exc
            if _is_nonce_error(str(exc)) and attempt < NONCE_RETRY_MAX:
                log.warning("requestHash %s 广播遇 nonce 冲突（第 %d 次），%ss 后重试：%s",
                            req_hash, attempt + 1, NONCE_RETRY_DELAYS[attempt], exc)
                time.sleep(NONCE_RETRY_DELAYS[attempt])
                continue
            raise RuntimeError("广播失败：%s" % exc)
        receipt = _wait_receipt(rpc, tx_hash)
        if receipt is None:
            last_err = RuntimeError("no receipt for %s" % tx_hash)
            if attempt < NONCE_RETRY_MAX:
                log.warning("requestHash %s 交易 %s 未确认，%ss 后重发",
                            req_hash, tx_hash, NONCE_RETRY_DELAYS[attempt])
                time.sleep(NONCE_RETRY_DELAYS[attempt])
                continue
            raise last_err
        status = receipt.get("status")
        if status not in ("0x1", 1):
            raise RuntimeError("交易已确认但 revert（status %s），不重试：%s" % (status, tx_hash))
        return tx_hash
    raise RuntimeError("nonce 冲突重试 %d 次后仍失败：%s" % (NONCE_RETRY_MAX, last_err))


def _is_nonce_error(msg):
    lowered = msg.lower()
    return any(hint in lowered for hint in NONCE_ERROR_HINTS)


def _wait_receipt(rpc, tx_hash, timeout=RECEIPT_TIMEOUT_S):
    started = time.time()
    while time.time() - started < timeout:
        try:
            receipt = rpc.call("eth_getTransactionReceipt", [tx_hash])
        except Exception:
            receipt = None
        if receipt is not None:
            return receipt
        time.sleep(RECEIPT_POLL_S)
    return None


# ---------------------------------------------------------------------------
# 事件轮询与进度持久化
# ---------------------------------------------------------------------------
def load_state():
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        last_block = int(state.get("last_processed_block", DEPLOY_BLOCK - 1))
        last_log = int(state.get("last_log_index", -1))
        return last_block, last_log
    except (OSError, ValueError, TypeError):
        return DEPLOY_BLOCK - 1, -1


def save_state(last_block, last_log):
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps({"last_processed_block": last_block,
                               "last_log_index": last_log,
                               "updated_at": now_iso()}, indent=2),
                   encoding="utf-8")
    tmp.replace(STATE_FILE)


def _decode_request_log(log_entry):
    topics = log_entry.get("topics", [])
    validator_address = _decode_address(topics[1])
    agent_id = int(topics[2], 16)
    req_hash = topics[3]
    request_uri = _decode_string(log_entry.get("data", "0x"))
    return validator_address, agent_id, request_uri, req_hash


def _decode_disputed_log(log_entry):
    topics = log_entry.get("topics", [])
    return topics[1], _decode_address(topics[2])  # requestHash, disputer


def fetch_new_events(rpc, from_block, to_block):
    """拉取两个事件，按 (blockNumber, logIndex) 排序返回。"""
    events = []
    for topic in (TOPIC_REQUEST, TOPIC_DISPUTED):
        try:
            logs = rpc.call("eth_getLogs", [{
                "fromBlock": hex(from_block), "toBlock": hex(to_block),
                "address": VALIDATION_ADDRESS, "topics": [topic]}]) or []
        except Exception as exc:
            log.warning("eth_getLogs %s 失败：%s", topic[:10], exc)
            continue
        for entry in logs:
            events.append((int(entry["blockNumber"], 16),
                           int(entry["logIndex"], 16), topic, entry))
    events.sort(key=lambda e: (e[0], e[1]))
    return events


def handle_request(rpc, identity, validator_address, agent_id, request_uri, req_hash):
    """处理一次 ValidationRequest：核对验证者与 requestHash，检查，提交结果。"""
    current_validator = chain_validator(rpc)
    if validator_address.lower() != current_validator.lower():
        log.info("忽略请求 %s：validatorAddress %s 不是当前验证者 %s",
                 req_hash, validator_address, current_validator)
        return None
    expected = request_hash(validator_address, agent_id, request_uri)
    if expected.lower() != req_hash.lower():
        log.warning("忽略请求 %s：requestHash 与 §3.4 公式不符（期望 %s）",
                    req_hash, expected)
        return None
    doc, err = fetch_json_doc(request_uri)
    if err is not None:
        score, tag, evidence = 0, "", {"reason": err}
        doc_type = ""
    else:
        score, tag, evidence = run_check(doc, agent_id, rpc, identity, req_hash)
        doc_type = doc.get("type", "")
    response_uri, response_hash = make_evidence(req_hash, agent_id, doc_type, score, evidence)
    tx_hash = submit_response(rpc, req_hash, score, response_uri, response_hash, tag)
    log.info("请求 %s agentId=%s type=%s score=%s tag=%s tx=%s",
             req_hash, agent_id, doc_type, score, tag, tx_hash)
    return tx_hash


def handle_disputed(rpc, identity, req_hash, disputer):
    """处理 ValidationDisputed：重新检查并提交新结果（计划 §5：复核）。"""
    log.info("收到争议 %s（争议人 %s），重新检查", req_hash, disputer)
    # 争议事件本身不带 requestURI：从链上 getValidationStatus 取不到 URI，
    # 故从本服务已处理过的请求记录里找；找不到则记日志（该请求不是本服务
    # 处理的，无法复核——v1 不从索引器反查）。
    known = _known_requests()
    info = known.get(req_hash.lower())
    if info is None:
        log.warning("争议 %s 无本服务处理记录，无法复核（可能服务重启前未处理）", req_hash)
        return None
    tx_hash = handle_request(rpc, identity, info["validator_address"],
                             info["agent_id"], info["request_uri"], req_hash)
    log.info("争议复核 %s 完成 tx=%s", req_hash, tx_hash)
    return tx_hash


def _known_requests_path():
    return STATE_DIR / "requests.json"


def _known_requests():
    try:
        return json.loads(_known_requests_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _remember_request(req_hash, validator_address, agent_id, request_uri):
    path = _known_requests_path()
    try:
        known = _known_requests()
    except Exception:
        known = {}
    known[req_hash.lower()] = {"validator_address": validator_address,
                               "agent_id": agent_id, "request_uri": request_uri}
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(known, indent=2), encoding="utf-8")
    tmp.replace(path)


def poll_once(rpc):
    """轮询一轮：处理新事件，推进 state。返回处理的事件数。"""
    identity = chain_identity_registry(rpc)
    if identity.lower() != IDENTITY_ADDRESS.lower():
        log.warning("链上 identity 注册表 %s 与预期 %s 不一致，仍按链上地址工作",
                    identity, IDENTITY_ADDRESS)
    last_block, last_log = load_state()
    latest = int(rpc.call("eth_blockNumber", []), 16)
    from_block = last_block
    if from_block < DEPLOY_BLOCK:
        from_block = DEPLOY_BLOCK
    if from_block > latest:
        return 0
    events = fetch_new_events(rpc, from_block, latest)
    pending = [(b, l, t, e) for (b, l, t, e) in events
               if not (b == last_block and l <= last_log)]
    if not pending:
        # 区间内无新事件才推进水位；有未处理事件时绝不推进，
        # 否则失败事件会被永久跳过。
        if latest > last_block:
            save_state(latest, -1)
        return 0
    handled = 0
    cur_block, cur_log = last_block, last_log
    for block_no, log_idx, topic, entry in pending:
        if block_no == last_block and log_idx <= last_log:
            continue
        try:
            if topic == TOPIC_REQUEST:
                validator_address, agent_id, request_uri, req_hash = \
                    _decode_request_log(entry)
                _remember_request(req_hash, validator_address, agent_id, request_uri)
                handle_request(rpc, identity, validator_address, agent_id,
                               request_uri, req_hash)
            else:
                req_hash, disputer = _decode_disputed_log(entry)
                handle_disputed(rpc, identity, req_hash, disputer)
        except Exception as exc:
            # 单个请求失败不卡住整轮；已处理的前缀先落盘，未处理事件下轮重试。
            log.error("处理事件 %s（块 %s log %s）失败，下轮重试：%s",
                      entry.get("transactionHash"), block_no, log_idx, exc)
            if handled:
                save_state(cur_block, cur_log)
            break
        cur_block, cur_log = block_no, log_idx
        handled += 1
    if handled:
        save_state(cur_block, cur_log)
    return handled


def main():
    setup_logging()
    log.info("haha-validator 启动：合约 %s，部署块 %s，轮询间隔 %ss，RPC %s",
             VALIDATION_ADDRESS, DEPLOY_BLOCK, POLL_INTERVAL,
             _load_rpc_urls()[0].split("/")[2] if _load_rpc_urls() else "?")
    rpc = make_rpc()
    once = os.environ.get("VALIDATOR_ONCE") == "1"
    while True:
        try:
            handled = poll_once(rpc)
            if handled:
                log.info("本轮处理 %d 个事件", handled)
        except Exception as exc:
            # 轮询本身失败（如 RPC 全挂）：记日志，等下一轮；systemd 只在
            # 进程退出时重启，循环内不退出，避免短 RestartSec 无限重启。
            log.error("轮询失败：%s", exc)
        if once:
            break
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()

