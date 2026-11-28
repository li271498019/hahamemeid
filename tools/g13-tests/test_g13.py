"""G13 T7/T8 unit checks, run on the server (has pycryptodome + psycopg2).
Tests the NEW /opt/haha-indexer/common.py + api.py in place.
No writes to the DB (read-only SELECTs only)."""
import importlib.util
import sys

sys.path.insert(0, "/opt/haha-indexer")
import common as new_common  # noqa: E402
from common import decode_log, topic0  # noqa: E402

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (" | " + str(detail) if detail else ""))


# 1. keccak sanity: well-known Transfer topic0
check("keccak sanity Transfer topic0",
      topic0("Transfer(address,address,uint256)") ==
      "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef")

# 2. validation topic0s present in EVENTS under the validation address
VAL = "0xaf9d2d3b6717469b21464baa12b022817841952b"
for sig in ("ValidationRequest(address,uint256,string,bytes32)",
            "ValidationResponse(address,uint256,bytes32,uint8,string,bytes32,string)",
            "ValidationDisputed(bytes32,address)"):
    t0 = topic0(sig)
    print("topic0", sig, "=", t0)
    check("EVENTS has " + sig.split("(")[0], (VAL, t0) in new_common.EVENTS)
check("_EVENT_DEFS grew by exactly 3", len(new_common._EVENT_DEFS) == 51,
      "now %d" % len(new_common._EVENT_DEFS))
check("validation in ALL_ADDRESSES/log_addresses",
      VAL in new_common.log_addresses())


def topic_addr(a):
    return "0x" + "00" * 12 + a[2:].lower()


def topic_u(n):
    return "0x" + n.to_bytes(32, "big").hex()


def enc_str_at(offset, s):
    b = s.encode()
    ln = len(b)
    pad = (-ln) % 32
    return offset.to_bytes(32, "big") + ln.to_bytes(32, "big") + b + b"\x00" * pad


ADMIN = "0x083a467259f12602e9053bbae2b3fd5b62976ef7"
REQ_HASH = "0x" + "ab" * 32
RESP_HASH = "0x" + "cd" * 32
AGENT_ID = 30

# 3a. ValidationRequest synthetic log
req_uri = "https://example.com/req-30.json"
data_req = enc_str_at(32, req_uri)
name, p = decode_log(VAL, [topic0("ValidationRequest(address,uint256,string,bytes32)"),
                           topic_addr(ADMIN), topic_u(AGENT_ID), REQ_HASH],
                     data_req)
check("decode ValidationRequest", name == "ValidationRequest" and
      p["validatorAddress"] == ADMIN.lower() and p["agentId"] == AGENT_ID and
      p["requestURI"] == req_uri and p["requestHash"] == REQ_HASH, p)

# 3b. ValidationResponse synthetic log
resp_uri = "https://example.com/resp-30.json"
tag = "endpoint-reachable"
resp_uri_off = 128
# tag data starts after the responseURI tail: len word + bytes + padding
tag_off = 128 + 32 + len(resp_uri.encode()) + ((-len(resp_uri.encode())) % 32)
# head: response word, respURI offset, responseHash word, tag offset
head = ((100).to_bytes(32, "big") + resp_uri_off.to_bytes(32, "big") +
        bytes.fromhex(RESP_HASH[2:]) + tag_off.to_bytes(32, "big"))
tail = (len(resp_uri.encode()).to_bytes(32, "big") + resp_uri.encode() +
        b"\x00" * ((-len(resp_uri.encode())) % 32) +
        len(tag.encode()).to_bytes(32, "big") + tag.encode() +
        b"\x00" * ((-len(tag.encode())) % 32))
data_resp = head + tail
name, p = decode_log(VAL, [topic0("ValidationResponse(address,uint256,bytes32,uint8,string,bytes32,string)"),
                           topic_addr(ADMIN), topic_u(AGENT_ID), REQ_HASH],
                     data_resp)
check("decode ValidationResponse", name == "ValidationResponse" and
      p["response"] == 100 and p["responseURI"] == resp_uri and
      p["responseHash"] == RESP_HASH and p["tag"] == tag and
      p["validatorAddress"] == ADMIN.lower() and p["agentId"] == AGENT_ID, p)

# 3c. ValidationDisputed synthetic log (no data)
name, p = decode_log(VAL, [topic0("ValidationDisputed(bytes32,address)"),
                           REQ_HASH, topic_addr("0x1111111111111111111111111111111111111111")],
                     b"")
check("decode ValidationDisputed", name == "ValidationDisputed" and
      p["requestHash"] == REQ_HASH and
      p["disputer"] == "0x1111111111111111111111111111111111111111", p)

# 4. Regression: same 200 latest raw_logs rows decode identically
#    under the backup (pre-G13) common.py and the new one.
from importlib.machinery import SourceFileLoader
bak = SourceFileLoader(
    "common_bak", "/opt/haha-indexer/common.py.bak-20261125-g13").load_module()
import psycopg2
from common import get_config
cfg = get_config()
conn = psycopg2.connect(cfg["database_url"])
conn.autocommit = True
with conn.cursor() as cur:
    cur.execute("SELECT address, topics, data FROM raw_logs"
                " ORDER BY block_number DESC, tx_index DESC, log_index DESC"
                " LIMIT 200")
    rows = cur.fetchall()
same, decoded = 0, 0
names_seen = set()
for addr, topics, data in rows:
    a_hex = "0x" + bytes(addr).hex()
    n1, p1 = bak.decode_log(a_hex, topics, bytes(data))
    n2, p2 = new_common.decode_log(a_hex, topics, bytes(data))
    if (n1, p1) == (n2, p2):
        same += 1
    if n2 is not None:
        decoded += 1
        names_seen.add(n2)
check("regression: 200 latest raw_logs decode identically old vs new",
      same == len(rows), "%d/%d identical, %d decoded" % (same, len(rows), decoded))
for want in ("NameMinted", "AgentActivated", "PointsChanged", "DayRootSet"):
    check("regression: %s still decodes" % want, want in names_seen)
# Rated is rare: the latest 200 rows happen to contain none. Check one
# Rated row directly by topic0 instead of relying on the sample.
with conn.cursor() as cur:
    cur.execute("SELECT address, topics, data FROM raw_logs WHERE topic0 = %s"
                " ORDER BY block_number DESC LIMIT 1",
                (bytes.fromhex(topic0(
                    "Rated(uint256,bytes32,address,uint8,string,bool)")[2:]),))
    rrow = cur.fetchone()
if rrow is not None:
    n2, _p2 = new_common.decode_log("0x" + bytes(rrow[0]).hex(),
                                    rrow[1], bytes(rrow[2]))
    check("regression: Rated still decodes", n2 == "Rated", n2)
else:
    check("regression: Rated still decodes (no Rated row in DB)", True,
          "no Rated event exists on-chain yet")
conn.close()

# 5. Dispute derivation unit tests (pure function, real api.py code)
import api as api_mod  # noqa: E402


def ev(event, **params):
    return {"event": event, "params": params, "blockNumber": 1,
            "blockTime": None, "txHash": b"\x00" * 32, "txIndex": 0,
            "logIndex": 0}


REQ = ev("ValidationRequest", validatorAddress=ADMIN.lower(), agentId=30,
         requestURI=req_uri, requestHash=REQ_HASH)
R100 = ev("ValidationResponse", validatorAddress=ADMIN.lower(), agentId=30,
          requestHash=REQ_HASH, response=100, responseURI=resp_uri,
          responseHash=RESP_HASH, tag=tag)
R0 = ev("ValidationResponse", validatorAddress=ADMIN.lower(), agentId=30,
        requestHash=REQ_HASH, response=0, responseURI=resp_uri,
        responseHash=RESP_HASH, tag=tag)
DISP = ev("ValidationDisputed", requestHash=REQ_HASH,
          disputer="0x1111111111111111111111111111111111111111")

cases = [
    ("not_disputed", [REQ, R100], ("not_disputed", 0, 100, 100)),
    ("disputed", [REQ, R100, DISP], ("disputed", 1, 100, 100)),
    ("upheld", [REQ, R100, DISP, R100], ("upheld", 1, 100, 100)),
    ("overturned", [REQ, R100, DISP, R0], ("overturned", 1, 100, 0)),
    ("overturned 0->100", [REQ, R0, DISP, R100], ("overturned", 1, 0, 100)),
    ("no response yet", [REQ], ("not_disputed", 0, None, None)),
    ("multi response pre-dispute", [REQ, R0, R100, DISP],
     ("disputed", 1, 100, 100)),
]
for label, events, want in cases:
    got = api_mod._validation_dispute_state(events)
    check("dispute state: " + label, got == want, "got %r want %r" % (got, want))

rec = api_mod._validation_record(REQ_HASH, [REQ, R100, DISP, R0])
check("record shape overturned", rec["disputeStatus"] == "overturned" and
      rec["originalResponse"] == 100 and rec["latestResponse"] == 0 and
      rec["response"] == 0 and rec["agentId"] == "30" and
      rec["tag"] == tag and rec["requestURI"] == req_uri, rec)

# 6. Handler direct calls against the real (still empty) validation data
api_mod._cfg = get_config()
out = api_mod.h_agent_validations("30")
check("handler h_agent_validations(30) empty 200-shape",
      out == {"agentId": "30", "validations": []}, out)
out = api_mod.h_agent_validations("999999999")
check("handler h_agent_validations(unknown) empty",
      out == {"agentId": "999999999", "validations": []}, out)
out = api_mod.h_agent_validations("abc")
check("handler h_agent_validations(non-numeric) empty",
      out == {"agentId": "abc", "validations": []}, out)
try:
    api_mod.h_validation_detail("0x" + "00" * 32)
    check("handler h_validation_detail(unknown) 404", False, "no raise")
except api_mod.ApiError as e:
    check("handler h_validation_detail(unknown) 404",
          e.status == 404 and e.body == {"error": "validation_not_found"}, e.body)
try:
    api_mod.h_validation_detail("not-a-hash")
    check("handler h_validation_detail(malformed) 404", False, "no raise")
except api_mod.ApiError as e:
    check("handler h_validation_detail(malformed) 404",
          e.status == 404 and e.body == {"error": "validation_not_found"}, e.body)

print("\n%d passed, %d failed" % (len(PASS), len(FAIL)))
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
