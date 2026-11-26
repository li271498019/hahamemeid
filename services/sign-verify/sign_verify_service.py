"""Minimal daily-verification signing service for haha.meme Season 1.

Listens on 127.0.0.1 only. The validator key never leaves this process:
it is read once from /etc/haha/season1-signer.env (0600, root) and only
used to sign a VerifyAuth that passed every check below. Nothing is
logged except the request outcome (no key, no signature in logs).

Endpoint: POST /v1/season1/sign-verify
Body (JSON): the VerifyAuth fields the agent wants signed:
  seasonId, dayIndex, aiId, agentId, generation, taskPackHash, verdict,
  nonce, deadline
Response (200): {"signer": "...", "signature": "0x...", "dayIndex": N, "aiId": "0x..."}
Response (4xx): {"error": "<short reason>"} — the agent should tell the
  user the reason in plain words, not retry blindly.

Checks (all fail-closed):
  1. SEASON1_SIGNING=on, module is the verified HahaSeason1 address, the
     key derives to the expected signer, and the signer is a live
     validator right now (sign_gate.authorize).
  2. dayIndex is inside the season (20781-20795).
  3. taskPackHash equals the on-chain taskPack(dayIndex).
  4. agentId + generation match one check in that day's task pack file.
  5. nonce equals the on-chain nonces(aiId).
  6. The .ai has not already verified that day (on-chain verified()).
  7. deadline is the end of that UTC day; now is inside that day and
     inside the 15-day season; verdict is 0 or 1; generation >= 1
     (eip712.sign_verify enforces these).
Rate limit: at most 5 signature attempts per aiId per day (in memory).
A signature for an already-consumed nonce is useless, so the cap only
stops spam, it does not stop a legitimate retry.
"""

import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, "/opt/haha-season1")
sys.path.insert(0, "/opt/haha-indexer")

from indexer.common import RpcClient, get_config
from tools.season1.eip712 import SignRejected, sign_verify
from tools.season1.mainnet import CHAIN_ID, DAILY_SIGNER, MODULE
from tools.season1.sign_gate import authorize, eth_call_factory
from tools.season1.constants import DAY_INDEX_END_EXCLUSIVE, DAY_INDEX_START, END_TS, SEASON_ID, START_TS

FIRST_DAY = DAY_INDEX_START
LAST_DAY = DAY_INDEX_END_EXCLUSIVE - 1

TASKPACK_DIR = "/opt/haha-season1/day-taskpacks"
PORT = 8788
MAX_ATTEMPTS_PER_AI_PER_DAY = 5

# selector helpers (computed from the contract source, not memory)
TASKPACK_SEL = "07a68cfc"   # taskPack(uint64)
NONCES_SEL = "9e317f12"     # nonces(bytes32)
VERIFIED_SEL = "d7aa727c"   # verified(bytes32,uint64)

_attempts = {}
_attempts_lock = threading.Lock()


def _pad32(hexstr):
    return hexstr.lower().replace("0x", "").rjust(64, "0")


def _rpc_u64(rpc, selector, args_hex):
    data = "0x" + selector + args_hex
    out = rpc.call("eth_call", [{"to": MODULE, "data": data}, "latest"])
    return out


def _onchain_taskpack(rpc, day):
    out = _rpc_u64(rpc, TASKPACK_SEL, day.to_bytes(8, "big").hex())
    return "0x" + bytes.fromhex(out[2:]).hex()


def _onchain_nonce(rpc, ai_id):
    out = _rpc_u64(rpc, NONCES_SEL, _pad32(ai_id))
    return int(out, 16)


def _onchain_verified(rpc, ai_id, day):
    args = _pad32(ai_id) + day.to_bytes(8, "big").hex()
    out = _rpc_u64(rpc, VERIFIED_SEL, args)
    return int(out, 16) == 1


def _taskpack_checks(day):
    path = os.path.join(TASKPACK_DIR, "taskpack-day%d.json" % day)
    with open(path, "r", encoding="utf-8") as f:
        pack = json.load(f)
    return pack.get("checks", [])


def _validate_and_sign(body, env):
    """Return (status, payload). Raises SignRejected for a bad request."""
    # --- shape ---
    required = ["seasonId", "dayIndex", "aiId", "agentId", "generation",
                "taskPackHash", "verdict", "nonce", "deadline"]
    for key in required:
        if key not in body:
            raise SignRejected("missing field: " + key)
    try:
        day = int(body["dayIndex"])
        agent_id = int(body["agentId"])
        generation = int(body["generation"])
        verdict = int(body["verdict"])
        nonce = int(body["nonce"])
        deadline = int(body["deadline"])
        season = int(body["seasonId"])
    except (TypeError, ValueError):
        raise SignRejected("bad field type")
    ai_id = str(body["aiId"]).lower()
    task_hash = str(body["taskPackHash"]).lower()
    if not ai_id.startswith("0x") or len(ai_id) != 66:
        raise SignRejected("bad aiId")
    if not task_hash.startswith("0x") or len(task_hash) != 66:
        raise SignRejected("bad taskPackHash")
    if season != SEASON_ID:
        raise SignRejected("season")
    if day < FIRST_DAY or day > LAST_DAY:
        raise SignRejected("outside season")
    if deadline != (day + 1) * 86400:
        raise SignRejected("deadline must be the end of that UTC day")

    # --- rate limit (per aiId per day) ---
    key = (ai_id, day)
    with _attempts_lock:
        n = _attempts.get(key, 0) + 1
        _attempts[key] = n
    if n > MAX_ATTEMPTS_PER_AI_PER_DAY:
        raise SignRejected("too many attempts today")

    # --- chain + task pack ---
    rpc = RpcClient(get_config()["rpc_urls"])
    if _onchain_taskpack(rpc, day) != task_hash:
        raise SignRejected("taskPackHash does not match the chain")
    try:
        checks = _taskpack_checks(day)
    except FileNotFoundError:
        raise SignRejected("task pack not published yet")
    if not any(str(c.get("agentId")) == str(agent_id) and
               str(c.get("generation")) == str(generation) for c in checks):
        raise SignRejected("agentId/generation not in today's task pack")
    if _onchain_nonce(rpc, ai_id) != nonce:
        raise SignRejected("nonce mismatch; fetch the current nonce first")
    if _onchain_verified(rpc, ai_id, day):
        raise SignRejected("already verified today")

    # --- authorize + sign (window checks live inside sign_verify) ---
    eth_call = eth_call_factory(get_config()["rpc_urls"])
    key, module, chain_id = authorize(env, eth_call, MODULE, DAILY_SIGNER)
    message = {
        "seasonId": season,
        "dayIndex": day,
        "aiId": ai_id,
        "agentId": agent_id,
        "generation": generation,
        "taskPackHash": task_hash,
        "verdict": verdict,
        "nonce": nonce,
        "deadline": deadline,
        "now": int(time.time()),
    }
    signed = sign_verify(key, message, chain_id, module, int(time.time()),
                         allowed_signers=[DAILY_SIGNER])
    return 200, {
        "signer": signed["signer"],
        "signature": signed["signature"],
        "dayIndex": day,
        "aiId": ai_id,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("[sign-verify] %s\n" % (fmt % args))

    def _send(self, status, payload):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"ok": True, "signingEnabled": os.environ.get("SEASON1_SIGNING") == "on"})
        else:
            self._send(404, {"error": "not_found"})

    def do_POST(self):
        if self.path != "/v1/season1/sign-verify":
            self._send(404, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > 4096:
                self._send(400, {"error": "bad body"})
                return
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(body, dict):
                raise SignRejected("bad body")
        except (ValueError, SignRejected):
            self._send(400, {"error": "bad body"})
            return
        try:
            status, payload = _validate_and_sign(body, os.environ)
        except SignRejected as exc:
            sys.stderr.write("[sign-verify] rejected aiId=%s day=%s: %s\n" % (
                body.get("aiId"), body.get("dayIndex"), str(exc)))
            self._send(403, {"error": str(exc)})
            return
        except Exception as exc:
            sys.stderr.write("[sign-verify] error: %s\n" % str(exc))
            self._send(500, {"error": "internal"})
            return
        self._send(status, payload)


def main():
    env = dict(os.environ)
    if env.get("SEASON1_SIGNING") != "on":
        sys.stderr.write("[sign-verify] refusing to start: SEASON1_SIGNING is not 'on'\n")
        return 2
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    sys.stderr.write("[sign-verify] listening on 127.0.0.1:%d\n" % PORT)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
