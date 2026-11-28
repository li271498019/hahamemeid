#!/usr/bin/env python3
"""Haha Dog snapshot keeper (python port of haha-dog/keeper/keeper.sh).

Same behaviour as keeper.sh: when HahaDog.processQueue(MAX_STEPS) would advance
queueHead, send that tx so due target block hashes get stored (permissionless call).

Differences from keeper.sh (security / ops only):
  * no `cast` / Foundry dependency; uses eth_account from the existing venv
  * the private key is NEVER put on a command line (cast --private-key is visible in `ps`);
    it is read from a systemd credential file and only lives in process memory
  * RPC URLs are read from a credential file; they are never logged (they embed API keys)
  * nonce / replacement errors are handled by re-simulating on the next loop
Logs only: start, tx hash + gas, errors (rate limited), 6-hourly heartbeat.
"""
import json, os, re, signal, sys, time, urllib.request
from eth_account import Account
from eth_utils import keccak

DOG = os.environ.get("HAHA_DOG_ADDRESS", "0x26f88A5db4925e9aFa35B1096FdD6DBa09f056c6")
EXPECT = os.environ.get("KEEPER_EXPECT_ADDRESS", "0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7").lower()
MAX_STEPS = int(os.environ.get("MAX_STEPS", "100"))
INTERVAL = float(os.environ.get("INTERVAL", "4"))
CRED = os.environ.get("CREDENTIALS_DIRECTORY", "")
KEY_FILE = os.environ.get("KEEPER_KEY_FILE", os.path.join(CRED, "admin-signer.env"))
RPC_FILE = os.environ.get("KEEPER_RPC_FILE", os.path.join(CRED, "indexer.env"))
CHAIN_ID = 56
MIN_GAS_PRICE = 100_000_000  # 0.1 gwei floor (BSC min is 0.05)
LOW_BALANCE = 2 * 10**15      # 0.002 BNB
STOP = False


def log(msg):
    print(time.strftime("%F %T", time.gmtime()) + "Z " + msg, flush=True)


_last_err = {}
def err(kind, e):
    # never log str(e): urllib errors may contain the RPC URL (with key)
    now = time.time()
    if now - _last_err.get(kind, 0) > 300:
        _last_err[kind] = now
        log(f"warn {kind}: {type(e).__name__}")


def load_key():
    for line in open(KEY_FILE, encoding="utf-8").read().splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        v = line.split("=", 1)[1].strip().strip("\"'").lower()
        v = v[2:] if v.startswith("0x") else v
        if re.fullmatch(r"[0-9a-f]{64}", v):
            if Account.from_key("0x" + v).address.lower() == EXPECT:
                return "0x" + v
    raise SystemExit("no key matching expected keeper address")


def load_rpcs():
    for line in open(RPC_FILE, encoding="utf-8").read().splitlines():
        if line.startswith("BSC_RPC_URLS="):
            return [u.strip() for u in line.split("=", 1)[1].split(",") if u.strip().startswith("http")]
    raise SystemExit("no BSC_RPC_URLS")


RPCS = []
def rpc(method, params, urls=None):
    last = None
    for u in (urls or RPCS):
        try:
            req = urllib.request.Request(u, json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
                                         {"content-type": "application/json", "user-agent": "haha-dog-keeper/1"})
            r = json.load(urllib.request.urlopen(req, timeout=8))
            if "error" in r:
                last = RuntimeError(str(r["error"].get("message", "rpc error"))[:80])
                if method == "eth_sendRawTransaction":
                    raise last  # do not blast a rejected tx at every node
                continue
            return r["result"]
        except RuntimeError:
            raise
        except Exception as e:
            last = e
    raise last or RuntimeError("no rpc")


def sel(sig):
    return "0x" + keccak(text=sig)[:4].hex()


def call(to, data, frm=None):
    p = {"to": to, "data": data}
    if frm:
        p["from"] = frm
    return rpc("eth_call", [p, "latest"])


def word(n):
    return n.to_bytes(32, "big").hex()


def main():
    global RPCS, STOP
    signal.signal(signal.SIGTERM, lambda *a: globals().update(STOP=True))
    signal.signal(signal.SIGINT, lambda *a: globals().update(STOP=True))
    key = load_key()
    RPCS = load_rpcs()
    me = Account.from_key(key).address
    log(f"keeper start addr={me} dog={DOG} interval={INTERVAL}s max_steps={MAX_STEPS} rpcs={len(RPCS)}")
    s_head, s_len, s_pq = sel("queueHead()"), sel("queueLength()"), sel("processQueue(uint256)")
    pq_data = s_pq + word(MAX_STEPS)
    last_beat = time.time()
    sent_total = 0
    while not STOP:
        try:
            head = int(call(DOG, s_head), 16)
            qlen = int(call(DOG, s_len), 16)
            if head < qlen:
                nxt = int(call(DOG, pq_data, me), 16)
                if nxt != head:
                    send(key, me, pq_data, head, nxt)
                    sent_total += 1
        except Exception as e:
            err("loop", e)
        if time.time() - last_beat > 6 * 3600:
            last_beat = time.time()
            try:
                bal = int(rpc("eth_getBalance", [me, "latest"]), 16)
                log(f"heartbeat balance_bnb={bal/1e18:.6f} txs={sent_total}")
            except Exception as e:
                err("heartbeat", e)
        for _ in range(int(INTERVAL * 10)):
            if STOP:
                break
            time.sleep(0.1)
    log("keeper stop")


def send(key, me, data, head, nxt):
    nonce = int(rpc("eth_getTransactionCount", [me, "pending"]), 16)
    gp = max(int(rpc("eth_gasPrice", []), 16) * 2, MIN_GAS_PRICE)
    tx = {"to": DOG, "from": me, "data": data}
    gas = int(rpc("eth_estimateGas", [tx]), 16)
    gas = min(int(gas * 1.3) + 20000, 3_000_000)
    bal = int(rpc("eth_getBalance", [me, "latest"]), 16)
    if bal < LOW_BALANCE:
        log(f"warn low balance {bal/1e18:.6f} BNB")
    signed = Account.sign_transaction({"to": DOG, "value": 0, "data": data, "gas": gas, "gasPrice": gp,
                                       "nonce": nonce, "chainId": CHAIN_ID}, key)
    raw = "0x" + signed.raw_transaction.hex().removeprefix("0x")
    try:
        txh = rpc("eth_sendRawTransaction", [raw])
    except RuntimeError as e:
        # nonce too low / already known / replacement underpriced (e.g. 08:00 daily ops tx): retry next loop
        log(f"send rejected: {e}")
        time.sleep(1.5)
        return
    log(f"sent queue {head}->{nxt} nonce={nonce} tx={txh}")
    for _ in range(40):
        time.sleep(1)
        try:
            rc = rpc("eth_getTransactionReceipt", [txh])
        except Exception:
            continue
        if rc:
            used = int(rc["gasUsed"], 16)
            price = int(rc.get("effectiveGasPrice", hex(gp)), 16)
            log(f"mined status={int(rc['status'],16)} block={int(rc['blockNumber'],16)} gas={used} fee_bnb={used*price/1e18:.8f} tx={txh}")
            return
    log(f"warn receipt timeout tx={txh}")


if __name__ == "__main__":
    main()
