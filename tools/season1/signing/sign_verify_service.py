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
Response (4xx/5xx): {"error": "<generic code>"} — one of:
  "invalid_request"   (400: bad shape, bad Content-Type/Origin, bad field
                       format or value, outside season, bad deadline)
  "not_eligible"      (403: shape is fine but the day's chain/task-pack
                       checks fail — wrong taskPackHash, agent not in
                       today's pack, nonce mismatch, already verified,
                       or outside the signing window)
  "too_many_attempts" (429: the 5-per-day aiId quota is used up, or one
                       client IP has failed too many times recently)
  "internal"          (500: server-side failure, e.g. signer/chain read)
The detail behind a rejection is only written to the server log
("[sign-verify] rejected ..."), never returned to the client, so the
endpoint cannot be used as an oracle to probe one check at a time.

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
     (eip712.sign_verify enforces these; the local window/verdict/
     generation checks run before counting, see below).
Rate limit: at most 5 signature attempts per aiId per day (in memory).
The count is only incremented AFTER every chain/task-pack check has
passed, immediately before signing — a request that fails any check
does not consume quota, so garbage requests can no longer drain
someone's daily allowance (S3). Separately, failures are also counted
per client IP: an IP with too many failures in a short window gets
429 for that IP only, without locking any aiId.
NOTE on the IP counter: this service sits behind nginx, which
currently does NOT forward X-Forwarded-For / X-Real-IP for the
sign-verify location, so every proxied request arrives as 127.0.0.1
and the per-IP limit stays inactive for proxied traffic until nginx
adds `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`
to that location. The counter is keyed on that header when present
and deliberately skipped for loopback addresses, so it can never
lock out all proxied users at once.
Residual risk (S3): anyone who can build 5 fully valid requests
(aiId, nonce and taskPackHash are all public chain data) can still
drain a victim's 5-per-day quota. Fully closing that needs the
requester to authenticate (a design decision, out of scope here).
A signature for an already-consumed nonce is useless, so the cap only
stops spam, it does not stop a legitimate retry.
"""

import json
import os
import re
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

# S3: cross-site simple requests (fetch with text/plain, no preflight)
# must not reach the signing path.
ALLOWED_ORIGIN = "https://haha.meme"

# L3: aiId / taskPackHash are 0x + 64 hex chars, nothing else.
HEX32_RE = re.compile(r"0x[0-9a-fA-F]{64}")

# L8: generic client-facing error codes. The detail stays server-side.
ERR_INVALID = "invalid_request"
ERR_NOT_ELIGIBLE = "not_eligible"
ERR_TOO_MANY = "too_many_attempts"
ERR_INTERNAL = "internal"

# selector helpers (computed from the contract source, not memory)
TASKPACK_SEL = "07a68cfc"   # taskPack(uint64)
NONCES_SEL = "9e317f12"     # nonces(bytes32)
VERIFIED_SEL = "d7aa727c"   # verified(bytes32,uint64)

_attempts = {}
_attempts_lock = threading.Lock()

# S3: per-IP failure counting (failures only, never successes).
# An IP that fails a lot in a short window is limited by IP; the aiId
# quota is untouched by this counter.
IP_FAIL_WINDOW_SECONDS = 60
IP_FAIL_THRESHOLD = 20
_ip_failures = {}
_ip_failures_lock = threading.Lock()


def _pad32(hexstr):
    return hexstr.lower().replace("0x", "").rjust(64, "0")


def _rpc_u64(rpc, selector, args_hex):
    data = "0x" + selector + args_hex
    out = rpc.call("eth_call", [{"to": MODULE, "data": data}, "latest"])
    return out


def _onchain_taskpack(rpc, day):
    out = _rpc_u64(rpc, TASKPACK_SEL, day.to_bytes(32, "big").hex())
    return "0x" + bytes.fromhex(out[2:]).hex()


def _onchain_nonce(rpc, ai_id):
    out = _rpc_u64(rpc, NONCES_SEL, _pad32(ai_id))
    return int(out, 16)


def _onchain_verified(rpc, ai_id, day):
    args = _pad32(ai_id) + day.to_bytes(32, "big").hex()
    out = _rpc_u64(rpc, VERIFIED_SEL, args)
    return int(out, 16) == 1


def _taskpack_checks(day):
    path = os.path.join(TASKPACK_DIR, "taskpack-day%d.json" % day)
    with open(path, "r", encoding="utf-8") as f:
        pack = json.load(f)
    return pack.get("checks", [])


def _client_ip(handler):
    """Best-effort client IP. Trusts X-Forwarded-For only because this
    service listens on 127.0.0.1 and nginx is its only client; see the
    module docstring — until nginx forwards the header this returns
    the loopback address and the per-IP limiter stays inactive."""
    xff = handler.headers.get("X-Forwarded-For")
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first
    xri = handler.headers.get("X-Real-IP")
    if xri and xri.strip():
        return xri.strip()
    return handler.client_address[0]


def _is_loopback(ip):
    return ip in ("127.0.0.1", "::1") or ip.startswith("127.")


def _record_ip_failure(ip):
    """Count one failed request for this IP. Loopback is skipped: with
    no forwarded header every proxied request looks like 127.0.0.1,
    and counting it would let one attacker lock out all users."""
    if _is_loopback(ip):
        return
    now = time.time()
    with _ip_failures_lock:
        stamps = [t for t in _ip_failures.get(ip, []) if now - t < IP_FAIL_WINDOW_SECONDS]
        stamps.append(now)
        _ip_failures[ip] = stamps


def _ip_limited(ip):
    if _is_loopback(ip):
        return False
    now = time.time()
    with _ip_failures_lock:
        stamps = [t for t in _ip_failures.get(ip, []) if now - t < IP_FAIL_WINDOW_SECONDS]
        _ip_failures[ip] = stamps
        return len(stamps) >= IP_FAIL_THRESHOLD


def _public_code(exc):
    """Map a SignRejected to its generic client-facing code. The detail
    after the 'code: ' prefix is for the server log only."""
    msg = str(exc)
    for code in (ERR_INVALID, ERR_NOT_ELIGIBLE, ERR_TOO_MANY, ERR_INTERNAL):
        if msg == code or msg.startswith(code + ":"):
            return code
    return ERR_INTERNAL


def _status_for_code(code):
    return {
        ERR_INVALID: 400,
        ERR_NOT_ELIGIBLE: 403,
        ERR_TOO_MANY: 429,
        ERR_INTERNAL: 500,
    }[code]


def _strict_int(value):
    """L3: JSON numbers must be real integers. bool is not int here
    (type(True) is bool), and floats such as 20781.9 are rejected
    instead of being silently truncated by int()."""
    if type(value) is not int:
        raise SignRejected(ERR_INVALID + ": bad field type")
    return value


def _validate_and_sign(body, env):
    """Return (status, payload). Raises SignRejected for a bad request,
    with a 'code: detail' message; do_POST maps it to the generic code
    and logs the detail server-side."""
    # --- shape ---
    required = ["seasonId", "dayIndex", "aiId", "agentId", "generation",
                "taskPackHash", "verdict", "nonce", "deadline"]
    for key in required:
        if key not in body:
            raise SignRejected(ERR_INVALID + ": missing field: " + key)
    day = _strict_int(body["dayIndex"])
    agent_id = _strict_int(body["agentId"])
    generation = _strict_int(body["generation"])
    verdict = _strict_int(body["verdict"])
    nonce = _strict_int(body["nonce"])
    deadline = _strict_int(body["deadline"])
    season = _strict_int(body["seasonId"])
    # L3: aiId / taskPackHash must be 0x + 64 hex chars. Anything else
    # is rejected here and never reaches eth_call (no more RPC 500s
    # for malformed input).
    if not isinstance(body["aiId"], str) or not HEX32_RE.fullmatch(body["aiId"]):
        raise SignRejected(ERR_INVALID + ": bad aiId")
    if not isinstance(body["taskPackHash"], str) or not HEX32_RE.fullmatch(body["taskPackHash"]):
        raise SignRejected(ERR_INVALID + ": bad taskPackHash")
    ai_id = body["aiId"].lower()
    task_hash = body["taskPackHash"].lower()
    if season != SEASON_ID:
        raise SignRejected(ERR_INVALID + ": season")
    if day < FIRST_DAY or day > LAST_DAY:
        raise SignRejected(ERR_INVALID + ": outside season")
    if deadline != (day + 1) * 86400:
        raise SignRejected(ERR_INVALID + ": deadline must be the end of that UTC day")
    # Local window/verdict/generation checks run BEFORE counting, so a
    # request that fails them never consumes quota. These mirror
    # eip712.sign_verify._check_window; sign_verify re-checks them at
    # sign time.
    if verdict not in (0, 1):
        raise SignRejected(ERR_INVALID + ": verdict")
    if generation < 1:
        raise SignRejected(ERR_INVALID + ": generation")
    now = int(time.time())
    if now < day * 86400 or now >= (day + 1) * 86400:
        raise SignRejected(ERR_NOT_ELIGIBLE + ": verification is only signed inside that UTC day")
    if now < START_TS or now >= END_TS:
        raise SignRejected(ERR_NOT_ELIGIBLE + ": outside the 15-day window; no makeup")

    # --- chain + task pack (all before any counting) ---
    rpc = RpcClient(get_config()["rpc_urls"])
    if _onchain_taskpack(rpc, day) != task_hash:
        raise SignRejected(ERR_NOT_ELIGIBLE + ": taskPackHash does not match the chain")
    try:
        checks = _taskpack_checks(day)
    except FileNotFoundError:
        raise SignRejected(ERR_NOT_ELIGIBLE + ": task pack not published yet")
    if not any(str(c.get("agentId")) == str(agent_id) and
               str(c.get("generation")) == str(generation) for c in checks):
        raise SignRejected(ERR_NOT_ELIGIBLE + ": agentId/generation not in today's task pack")
    if _onchain_nonce(rpc, ai_id) != nonce:
        raise SignRejected(ERR_NOT_ELIGIBLE + ": nonce mismatch; fetch the current nonce first")
    if _onchain_verified(rpc, ai_id, day):
        raise SignRejected(ERR_NOT_ELIGIBLE + ": already verified today")

    # --- rate limit (per aiId per day), S3: only now, after every
    # check has passed and the request is about to be signed. ---
    key = (ai_id, day)
    with _attempts_lock:
        n = _attempts.get(key, 0) + 1
        _attempts[key] = n
    if n > MAX_ATTEMPTS_PER_AI_PER_DAY:
        raise SignRejected(ERR_TOO_MANY + ": too many attempts today")

    # --- authorize + sign (window checks live inside sign_verify) ---
    # Failures here are server-side (signer revoked, chain read
    # failed), not the requester's fault: report as internal.
    try:
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
    except SignRejected as exc:
        raise SignRejected(ERR_INTERNAL + ": " + str(exc))
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

    def _reject(self, code, detail_for_log=None):
        """Send the generic code; the detail goes to the server log only."""
        if detail_for_log is not None:
            sys.stderr.write("[sign-verify] rejected: %s\n" % detail_for_log)
        self._send(_status_for_code(code), {"error": code})

    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"ok": True, "signingEnabled": os.environ.get("SEASON1_SIGNING") == "on"})
        else:
            self._send(404, {"error": "not_found"})

    def do_POST(self):
        if self.path != "/v1/season1/sign-verify":
            self._send(404, {"error": "not_found"})
            return
        client_ip = _client_ip(self)
        # S3: per-IP failure limit — only this IP is slowed, no aiId
        # is locked by it.
        if _ip_limited(client_ip):
            sys.stderr.write("[sign-verify] ip-limited ip=%s\n" % client_ip)
            self._send(429, {"error": ERR_TOO_MANY})
            return
        # S3: Origin/Referer must be haha.meme when present. Missing
        # headers are allowed (server-side and agent callers send none).
        origin = self.headers.get("Origin")
        if origin is not None and origin.strip() != ALLOWED_ORIGIN:
            _record_ip_failure(client_ip)
            # S3 asks for 403 here (cross-site request refused);
            # the code stays invalid_request so agents can tell it
            # apart from not_eligible / too_many_attempts.
            sys.stderr.write("[sign-verify] rejected: bad Origin: %s\n" % origin)
            self._send(403, {"error": ERR_INVALID})
            return
        referer = self.headers.get("Referer")
        if referer is not None and not (
                referer == ALLOWED_ORIGIN or referer.startswith(ALLOWED_ORIGIN + "/")):
            _record_ip_failure(client_ip)
            sys.stderr.write("[sign-verify] rejected: bad Referer: %s\n" % referer)
            self._send(403, {"error": ERR_INVALID})
            return
        # S3: only real JSON posts are accepted. A cross-site simple
        # request (Content-Type: text/plain) never reaches validation.
        content_type = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if content_type != "application/json":
            _record_ip_failure(client_ip)
            self._reject(ERR_INVALID, "bad Content-Type: %s" % content_type)
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > 4096:
                _record_ip_failure(client_ip)
                self._reject(ERR_INVALID, "bad body length: %s" % length)
                return
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(body, dict):
                raise SignRejected(ERR_INVALID + ": bad body")
        except (ValueError, SignRejected) as exc:
            _record_ip_failure(client_ip)
            self._reject(ERR_INVALID, "bad body: %s" % exc)
            return
        try:
            status, payload = _validate_and_sign(body, os.environ)
        except SignRejected as exc:
            # L8: keep the existing rejected log line (detail stays
            # server-side); the client only gets the generic code.
            sys.stderr.write("[sign-verify] rejected aiId=%s day=%s: %s\n" % (
                body.get("aiId"), body.get("dayIndex"), str(exc)))
            _record_ip_failure(client_ip)
            code = _public_code(exc)
            self._send(_status_for_code(code), {"error": code})
            return
        except Exception as exc:
            sys.stderr.write("[sign-verify] error: %s\n" % str(exc))
            self._send(500, {"error": ERR_INTERNAL})
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
