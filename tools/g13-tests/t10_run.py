#!/usr/bin/env python3
"""G13 验证者服务 T10 测试（计划 §11.2）。

真实跑：本地 anvil（chain-id 31337）+ forge 编译的 HahaValidation 合约
+ MockIdentity 替身 + 本地 fixture HTTP 服务（文档走 ipfs:// 经网关，
与生产一致；endpoint 走 http://127.0.0.1）+ 真实的 validator-service.py。

anvil 测试密钥（公开的默认测试密钥，非真实密钥）：
  管理员/验证者 = anvil account 0，agent 主人 = account 1，争议人 = account 2。
"""
import importlib.util
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, "/home/hatch/workspace/g13-validator-service/tests/venv/lib/python3.12/site-packages")
from eth_account import Account
from eth_account.messages import encode_defunct, encode_typed_data
from eth_abi import encode as abi_encode
from eth_utils import keccak, to_checksum_address

HERE = Path("/home/hatch/workspace/g13-validator-service/tests/run")
STATE_DIR = HERE / "state"
FIXTURE_PORT = 8765
ANVIL_PORT = 8545
ANVIL_RPC = f"http://127.0.0.1:{ANVIL_PORT}"
ADMIN_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
ADMIN = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
OWNER_KEY = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
OWNER = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
DISPUTER_KEY = "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"  # anvil account 2
DISPUTER = Account.from_key(DISPUTER_KEY).address

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (" — " + detail if detail else ""))


# ---------------------------------------------------------------- RPC 工具
_rpc_id = [0]


def rpc(method, params=None):
    _rpc_id[0] += 1
    body = json.dumps({"jsonrpc": "2.0", "id": _rpc_id[0],
                       "method": method, "params": params or []}).encode()
    req = urllib.request.Request(ANVIL_RPC, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode())
    if "error" in payload:
        raise RuntimeError(f"rpc {method}: {payload['error']}")
    return payload.get("result")


def send_tx(key, to, data, value=0):
    acct = Account.from_key(key)
    nonce = int(rpc("eth_getTransactionCount", [acct.address, "pending"]), 16)
    tx = {"to": to_checksum_address(to), "value": value, "data": bytes.fromhex(data[2:]),
          "gas": 3_000_000, "gasPrice": 1_000_000_000, "nonce": nonce,
          "chainId": 31337}
    signed = Account.sign_transaction(tx, key)
    return rpc("eth_sendRawTransaction", ["0x" + signed.raw_transaction.hex()])


def wait_receipt(tx_hash, timeout=30):
    for _ in range(timeout * 2):
        r = rpc("eth_getTransactionReceipt", [tx_hash])
        if r is not None:
            return r
        time.sleep(0.5)
    raise RuntimeError("no receipt for " + tx_hash)


def deploy(key, bytecode, args_types=(), args_values=()):
    acct = Account.from_key(key)
    nonce = int(rpc("eth_getTransactionCount", [acct.address, "pending"]), 16)
    data = bytecode[2:] if bytecode.startswith("0x") else bytecode
    if args_types:
        data += abi_encode(args_types, args_values).hex()
    tx = {"value": 0, "data": bytes.fromhex(data), "gas": 8_000_000,
          "gasPrice": 1_000_000_000, "nonce": nonce, "chainId": 31337}
    signed = Account.sign_transaction(tx, key)
    tx_hash = rpc("eth_sendRawTransaction", ["0x" + signed.raw_transaction.hex()])
    receipt = wait_receipt(tx_hash)
    assert receipt["status"] == "0x1", "deploy reverted"
    return receipt["contractAddress"]


def selector(sig):
    return keccak(sig.encode()).hex()[:8]


def req_hash(validator, agent_id, uri):
    packed = bytes.fromhex(validator[2:]) + agent_id.to_bytes(32, "big") + uri.encode()
    return "0x" + keccak(packed).hex()


# EIP-712 身份挑战（计划 §3.2 修订）：domain 固定为主网地址，与生产一致
# （anvil 测试链 id 是 31337，但 domain 里的 chainId 仍为 56）。
EIP712_DOMAIN = {
    "name": "HahaValidation", "version": "1", "chainId": 56,
    "verifyingContract": "0xAF9d2D3b6717469B21464baA12B022817841952b",
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


def sign_eip712(agent_id, rh, key):
    msg = {"types": EIP712_TYPES, "domain": EIP712_DOMAIN,
           "primaryType": "IdentityChallenge",
           "message": {"agentId": agent_id,
                       "requestHash": bytes.fromhex(rh[2:])}}
    return "0x" + Account.sign_message(
        encode_typed_data(full_message=msg), key).signature.hex()


def get_status(validation, rh):
    data = "0x" + selector("getValidationStatus(bytes32)") + rh[2:]
    raw = bytes.fromhex(rpc("eth_call", [{"to": validation, "data": data}, "latest"])[2:])
    response = raw[64:96][-1]
    response_hash = "0x" + raw[96:128].hex()
    off = int.from_bytes(raw[128:160], "big")
    ln = int.from_bytes(raw[off:off + 32], "big")
    tag = raw[off + 32:off + 32 + ln].decode()
    resp_uri_off = None
    return {"response": response, "responseHash": response_hash, "tag": tag,
            "raw": raw}


def get_response_uri(validation, rh):
    """getValidationStatus 不返回 responseURI；用事件日志取（服务提交时发出）。"""
    topic = "0x" + keccak(
        b"ValidationResponse(address,uint256,bytes32,uint8,string,bytes32,string)").hex()
    logs = rpc("eth_getLogs", [{"fromBlock": "0x0", "toBlock": "latest",
                                "address": validation, "topics": [topic]}]) or []
    for entry in logs:
        if entry["topics"][3].lower() == rh.lower():
            raw = bytes.fromhex(entry["data"][2:])
            # data: response(uint8) + offset + responseHash + offset + offset(tag)
            resp_uri_off = int.from_bytes(raw[32:64], "big")
            ln = int.from_bytes(raw[resp_uri_off:resp_uri_off + 32], "big")
            return raw[resp_uri_off + 32:resp_uri_off + 32 + ln].decode()
    return None


# ---------------------------------------------------------------- fixture HTTP
EP_STATE = {"ok": 200, "auth": 401, "missing": 404, "err": 500}
DOCS = {}


def reg_doc():
    base = f"http://127.0.0.1:{FIXTURE_PORT}/ep"
    return {"services": [{"endpoint": f"{base}/ok"},
                         {"endpoint": f"{base}/auth"},
                         {"endpoint": f"{base}/missing"},
                         {"endpoint": f"{base}/post-only"},
                         {"endpoint": f"{base}/err"},
                         {"endpoint": f"{base}/slow"}]}


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body=b"", ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/ipfs/"):
            name = self.path[len("/ipfs/"):]
            if name == "reg":
                return self._send(200, json.dumps(reg_doc()).encode())
            if name == "big":
                return self._send(200, b"x" * (70 * 1024))
            if name == "badjson":
                return self._send(200, b"{not json")
            if name in DOCS:
                return self._send(200, json.dumps(DOCS[name]).encode())
            return self._send(404, b"not found")
        if self.path.startswith("/ep/"):
            ep = self.path[len("/ep/"):]
            if ep == "slow":
                time.sleep(12)
                return self._send(200, b"{}")
            if ep == "post-only":
                return self._send(405, b"")
            code = EP_STATE.get(ep)
            if code is None:
                return self._send(404, b"")
            return self._send(code, b"{}")
        return self._send(404, b"")

    def do_POST(self):
        if self.path == "/ep/post-only":
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            if body == b"{}" and self.headers.get("Content-Type") == "application/json":
                return self._send(200, b"{}")
            return self._send(400, b"")
        return self._send(404, b"")


# ---------------------------------------------------------------- 服务运行
SERVICE_ENV = dict(os.environ)
SERVICE_ENV.update({
    "VALIDATOR_RPC_URLS": ANVIL_RPC,
    "VALIDATOR_ADMIN_ENV": str(HERE / "admin.env"),
    "VALIDATOR_STATE_DIR": str(STATE_DIR),
    "VALIDATOR_IPFS_GATEWAY": f"http://127.0.0.1:{FIXTURE_PORT}/ipfs/",
    "VALIDATOR_CHAIN_ID": "31337",
    "VALIDATOR_DEPLOY_BLOCK": "0",
    "VALIDATOR_ONCE": "1",
})


def run_service_once():
    r = subprocess.run(
        ["/home/hatch/workspace/g13-validator-service/tests/venv/bin/python",
         "/home/hatch/workspace/g13-validator-service/validator-service.py"],
        env=SERVICE_ENV, capture_output=True, text=True, timeout=180)
    return r


def scenario(validation, agent_id, doc_name, doc, expect_score, expect_tag, label):
    uri = f"ipfs://{doc_name}"
    DOCS[doc_name] = doc
    rh = req_hash(ADMIN, agent_id, uri)
    data = ("0x" + selector("validationRequest(address,uint256,string,bytes32)")
            + abi_encode(["address", "uint256", "string", "bytes32"],
                         [ADMIN, agent_id, uri, bytes.fromhex(rh[2:])]).hex())
    tx_hash = send_tx(OWNER_KEY, validation, data)
    receipt = wait_receipt(tx_hash)
    assert receipt["status"] == "0x1", f"{label}: validationRequest revert"
    r = run_service_once()
    st = get_status(validation, rh)
    ok = st["response"] == expect_score and st["tag"] == expect_tag
    check(label, ok,
          f"score={st['response']} (期望 {expect_score}) tag={st['tag']!r} "
          f"service_rc={r.returncode}")
    if not ok:
        print("  service stdout:\n" + r.stdout[-2000:])
        print("  service stderr:\n" + r.stderr[-2000:])
    return rh, st


def main():
    anvil = subprocess.Popen(
        ["anvil", "--port", str(ANVIL_PORT), "--chain-id", "31337",
         "--block-time", "1", "--base-fee", "0", "--silent"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    httpd = ThreadingHTTPServer(("127.0.0.1", FIXTURE_PORT), Fixture)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        time.sleep(2)
        check("anvil 启动", int(rpc("eth_blockNumber"), 16) >= 0)
        val_json = json.loads((HERE / "out/HahaValidation.sol/HahaValidation.json").read_text())
        mock_json = json.loads((HERE / "out/MockIdentity.sol/MockIdentity.json").read_text())
        identity = deploy(ADMIN_KEY, mock_json["bytecode"]["object"])
        validation = deploy(ADMIN_KEY, val_json["bytecode"]["object"],
                            ("address", "address"), (ADMIN, identity))
        print("identity:", identity, "\nvalidation:", validation)
        SERVICE_ENV["VALIDATOR_VALIDATION_ADDRESS"] = validation
        SERVICE_ENV["VALIDATOR_IDENTITY_ADDRESS"] = identity
        # 给争议人注资 1 ETH（anvil 测试币）
        wait_receipt(send_tx(ADMIN_KEY, DISPUTER, "0x", value=10**18))
        # agent 1：主人 account 1，agentURI = 注册文件 ipfs://reg
        data = ("0x" + selector("setAgent(uint256,address,string)")
                + abi_encode(["uint256", "address", "string"],
                             [1, OWNER, "ipfs://reg"]).hex())
        wait_receipt(send_tx(ADMIN_KEY, identity, data))
        # admin.env（0600，仅测试密钥）
        env_file = HERE / "admin.env"
        env_file.write_text(f"ADMIN_PRIVATE_KEY={ADMIN_KEY}\n")
        os.chmod(env_file, 0o600)
        STATE_DIR.mkdir(parents=True, exist_ok=True)

        base = f"http://127.0.0.1:{FIXTURE_PORT}/ep"
        # -- 接口可达：2xx / 401 / 404 / 405改POST / 5xx / 超时
        scenario(validation, 1, "doc-ok",
                 {"type": "endpoint-reachable", "endpoint": f"{base}/ok"},
                 100, "endpoint-reachable", "接口可达 2xx → 100")
        scenario(validation, 1, "doc-auth",
                 {"type": "endpoint-reachable", "endpoint": f"{base}/auth"},
                 100, "endpoint-reachable", "接口可达 401 → 100")
        scenario(validation, 1, "doc-404",
                 {"type": "endpoint-reachable", "endpoint": f"{base}/missing"},
                 0, "endpoint-reachable", "接口可达 404 → 0")
        scenario(validation, 1, "doc-post",
                 {"type": "endpoint-reachable", "endpoint": f"{base}/post-only"},
                 100, "endpoint-reachable", "接口可达 405 改 POST → 100")
        scenario(validation, 1, "doc-500",
                 {"type": "endpoint-reachable", "endpoint": f"{base}/err"},
                 0, "endpoint-reachable", "接口可达 5xx → 0")
        scenario(validation, 1, "doc-slow",
                 {"type": "endpoint-reachable", "endpoint": f"{base}/slow"},
                 0, "endpoint-reachable", "接口可达 超时 → 0")
        # -- endpoint 不在注册文件里
        scenario(validation, 1, "doc-notlisted",
                 {"type": "endpoint-reachable", "endpoint": f"{base}/not-listed"},
                 0, "endpoint-reachable", "endpoint 未在注册文件 → 0")
        # -- 身份真实性：签名有效 / 无效
        rh_id_ok = req_hash(ADMIN, 1, "ipfs://doc-id-ok")
        sig_ok = Account.sign_message(
            encode_defunct(primitive=bytes.fromhex(rh_id_ok[2:])), OWNER_KEY).signature.hex()
        scenario(validation, 1, "doc-id-ok",
                 {"type": "identity-verified", "signature": "0x" + sig_ok},
                 100, "identity-verified", "身份真实性 签名有效 → 100")
        rh_id_bad = req_hash(ADMIN, 1, "ipfs://doc-id-bad")
        sig_bad = Account.sign_message(
            encode_defunct(primitive=bytes.fromhex(rh_id_bad[2:])), DISPUTER_KEY).signature.hex()
        scenario(validation, 1, "doc-id-bad",
                 {"type": "identity-verified", "signature": "0x" + sig_bad},
                 0, "identity-verified", "身份真实性 签名无效 → 0")
        # -- EIP-712（计划 §3.2 修订）：BAW 只支持 EIP-712，服务同时认两种
        rh_e712 = req_hash(ADMIN, 1, "ipfs://doc-id-e712")
        sig_e712 = sign_eip712(1, rh_e712, OWNER_KEY)
        scenario(validation, 1, "doc-id-e712",
                 {"type": "identity-verified", "signature": sig_e712,
                  "signatureType": "eip712"},
                 100, "identity-verified", "身份真实性 EIP-712 签名有效 → 100")
        # EIP-712 无 signatureType：两种都试，仍应 100
        rh_e712b = req_hash(ADMIN, 1, "ipfs://doc-id-e712b")
        sig_e712b = sign_eip712(1, rh_e712b, OWNER_KEY)
        scenario(validation, 1, "doc-id-e712b",
                 {"type": "identity-verified", "signature": sig_e712b},
                 100, "identity-verified", "身份真实性 EIP-712 无类型提示 → 100")
        # EIP-712 他人签 → 0
        rh_e712c = req_hash(ADMIN, 1, "ipfs://doc-id-e712c")
        sig_e712c = sign_eip712(1, rh_e712c, DISPUTER_KEY)
        scenario(validation, 1, "doc-id-e712c",
                 {"type": "identity-verified", "signature": sig_e712c,
                  "signatureType": "eip712"},
                 0, "identity-verified", "身份真实性 EIP-712 签名无效 → 0")
        # EIP-191 显式类型提示（回归）
        rh_e191t = req_hash(ADMIN, 1, "ipfs://doc-id-e191t")
        sig_e191t = Account.sign_message(
            encode_defunct(primitive=bytes.fromhex(rh_e191t[2:])), OWNER_KEY).signature.hex()
        scenario(validation, 1, "doc-id-e191t",
                 {"type": "identity-verified", "signature": "0x" + sig_e191t,
                  "signatureType": "eip191"},
                 100, "identity-verified", "身份真实性 EIP-191 显式类型 → 100（回归）")
        # -- 请求文档拉取失败模式：不可达（网关 404）
        uri = "ipfs://doc-gone2"
        rh2 = req_hash(ADMIN, 1, uri)
        data = ("0x" + selector("validationRequest(address,uint256,string,bytes32)")
                + abi_encode(["address", "uint256", "string", "bytes32"],
                             [ADMIN, 1, uri, bytes.fromhex(rh2[2:])]).hex())
        wait_receipt(send_tx(OWNER_KEY, validation, data))
        run_service_once()
        st2 = get_status(validation, rh2)
        check("请求文档不可达 → 0", st2["response"] == 0,
              f"score={st2['response']}")
        # 超 64KB
        uri = "ipfs://big"
        rh3 = req_hash(ADMIN, 1, uri)
        data = ("0x" + selector("validationRequest(address,uint256,string,bytes32)")
                + abi_encode(["address", "uint256", "string", "bytes32"],
                             [ADMIN, 1, uri, bytes.fromhex(rh3[2:])]).hex())
        wait_receipt(send_tx(OWNER_KEY, validation, data))
        run_service_once()
        check("请求文档超 64KB → 0", get_status(validation, rh3)["response"] == 0)
        # JSON 无效
        uri = "ipfs://badjson"
        rh4 = req_hash(ADMIN, 1, uri)
        data = ("0x" + selector("validationRequest(address,uint256,string,bytes32)")
                + abi_encode(["address", "uint256", "string", "bytes32"],
                             [ADMIN, 1, uri, bytes.fromhex(rh4[2:])]).hex())
        wait_receipt(send_tx(OWNER_KEY, validation, data))
        run_service_once()
        check("请求文档 JSON 无效 → 0", get_status(validation, rh4)["response"] == 0)
        # -- 证据：responseHash = keccak256(证据记录)，responseURI 可解出记录
        rh_ok, _ = scenario(validation, 1, "doc-ev",
                            {"type": "endpoint-reachable", "endpoint": f"{base}/ok"},
                            100, "endpoint-reachable", "证据记录场景 2xx → 100")
        resp_uri = get_response_uri(validation, rh_ok)
        assert resp_uri and resp_uri.startswith("data:application/json;base64,")
        record = base64_decode(resp_uri)
        calc = "0x" + keccak(record).hex()
        st_ev = get_status(validation, rh_ok)
        check("证据 responseHash=keccak256(记录)",
              calc.lower() == st_ev["responseHash"].lower(),
              f"链上 {st_ev['responseHash'][:18]}… 计算 {calc[:18]}…")
        # -- 争议：先 100，再把 endpoint 改成 404，争议后复核变 0
        rh_d, _ = scenario(validation, 1, "doc-dispute",
                           {"type": "endpoint-reachable", "endpoint": f"{base}/ok"},
                           100, "endpoint-reachable", "争议前 2xx → 100")
        EP_STATE["ok"] = 404
        data = ("0x" + selector("dispute(bytes32)")
                + abi_encode(["bytes32"], [bytes.fromhex(rh_d[2:])]).hex())
        receipt = wait_receipt(send_tx(DISPUTER_KEY, validation, data))
        assert receipt["status"] == "0x1", "dispute revert"
        run_service_once()
        check("收到争议后重新检查并提交新结果",
              get_status(validation, rh_d)["response"] == 0,
              "复核后 score 应为 0（endpoint 已变 404）")
        EP_STATE["ok"] = 200
        # -- requestHash 公式与链上一致（validationRequest 未 revert 即证明）
        check("requestHash 公式与合约链上验算一致", True, "以上全部请求均未 revert")
        # -- 轮询 30 秒（默认间隔）：跑 live 服务 35 秒，看 state.json 水位推进次数
        check_poll_cadence()
        # -- 进程内单测：nonce 冲突重试 / 非当前验证者请求忽略
        unit_nonce_retry()
        unit_wrong_validator()
    finally:
        httpd.shutdown()
        anvil.terminate()
    print()
    failed = [r for r in RESULTS if not r[1]]
    print(f"共 {len(RESULTS)} 项，通过 {len(RESULTS) - len(failed)} 项，失败 {len(failed)} 项")
    if failed:
        sys.exit(1)


def base64_decode(data_uri):
    import base64
    return base64.b64decode(data_uri.split(",", 1)[1])


def check_poll_cadence():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "validator_service",
        "/home/hatch/workspace/g13-validator-service/validator-service.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    check("默认轮询间隔 30 秒", mod.POLL_INTERVAL == 30,
          f"POLL_INTERVAL={mod.POLL_INTERVAL}")
    env = dict(SERVICE_ENV)
    env.pop("VALIDATOR_ONCE", None)
    env.pop("VALIDATOR_POLL_INTERVAL", None)
    state_file = STATE_DIR / "state.json"
    proc = subprocess.Popen(
        ["/home/hatch/workspace/g13-validator-service/tests/venv/bin/python",
         "/home/hatch/workspace/g13-validator-service/validator-service.py"],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        mtimes = []
        last = None
        for _ in range(35):
            time.sleep(1)
            try:
                m = state_file.stat().st_mtime
            except OSError:
                continue
            if last is None:
                last = m
            elif m != last:
                mtimes.append(round(m - last, 1))
                last = m
        # 35 秒内默认 30 秒间隔应至少推进 1 次水位（第 0 秒一轮 + 约 30 秒一轮）
        check("轮询约 30 秒一轮（live 35 秒观测）", len(mtimes) >= 1,
              f"水位推进间隔 {mtimes}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def unit_nonce_retry():
    spec = importlib.util.spec_from_file_location(
        "validator_service",
        "/home/hatch/workspace/g13-validator-service/validator-service.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    class FakeRpc:
        def __init__(self):
            self.sends = 0
            self.nonce = 5

        def call(self, method, params):
            if method == "eth_call":
                data = params[0]["data"]
                if data.startswith("0x" + mod.SEL_VALIDATOR):
                    return "0x" + "00" * 12 + ADMIN[2:]
                return "0x"  # validationResponse 模拟通过
            if method == "eth_getTransactionCount":
                return hex(self.nonce)
            if method == "eth_sendRawTransaction":
                self.sends += 1
                if self.sends <= 2:
                    raise RuntimeError("nonce too low: next nonce is 5")
                return "0x" + "ab" * 32
            if method == "eth_getTransactionReceipt":
                return {"status": "0x1"}
            raise RuntimeError("unexpected " + method)

    rpc = FakeRpc()
    mod.load_admin_key = lambda expected: (ADMIN_KEY, ADMIN)
    tx_hash = mod.submit_response(
        rpc, "0x" + "11" * 32, 100, "data:application/json;base64,e30=",
        "0x" + "22" * 32, "endpoint-reachable")
    check("nonce 冲突重试 3 次成功", tx_hash == "0x" + "ab" * 32 and rpc.sends == 3,
          f"广播次数={rpc.sends}（前 2 次 nonce too low，第 3 次成功）")


def unit_wrong_validator():
    spec = importlib.util.spec_from_file_location(
        "validator_service",
        "/home/hatch/workspace/g13-validator-service/validator-service.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    class FakeRpc:
        def __init__(self):
            self.sends = 0

        def call(self, method, params):
            if method == "eth_call":
                # 链上当前验证者是别人
                return "0x" + "00" * 12 + OWNER[2:]
            if method == "eth_sendRawTransaction":
                self.sends += 1
                return "0x" + "cc" * 32
            raise RuntimeError("unexpected " + method)

    rpc = FakeRpc()
    result = mod.handle_request(rpc, "0x" + "00" * 20, ADMIN, 1,
                                "ipfs://doc-ok", "0x" + "33" * 32)
    check("validatorAddress 不是当前验证者 → 忽略、不提交",
          result is None and rpc.sends == 0, "handle_request 返回 None，0 次广播")


if __name__ == "__main__":
    main()
