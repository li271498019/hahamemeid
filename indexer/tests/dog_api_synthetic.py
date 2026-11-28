"""Synthetic market/reroll/transfer events -> dog_* tables -> /v1/dog/* API.
Needs a scratch Postgres that already holds the real dog data (run tests/dog_e2e.py first).
    python3 tests/dog_api_synthetic.py --env FILE
It appends fake logs at block numbers above the checkpoint into raw_logs of the SCRATCH db."""
import datetime, json, os, subprocess, sys, time, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import psycopg2, psycopg2.extras
import common
from common import CONTRACTS, topic0, get_config
from dog_store import apply_dog_event

env = sys.argv[sys.argv.index("--env") + 1] if "--env" in sys.argv else None
cfg = get_config(env)
conn = psycopg2.connect(cfg["database_url"]); cur = conn.cursor()
cur.execute("SELECT safe_block FROM checkpoint WHERE id = 1"); cp = cur.fetchone()[0]
cur.execute("SELECT token_id, encode(owner,'hex') FROM dogs ORDER BY token_id LIMIT 6")
own = {int(t): o for t, o in cur.fetchall()}
conn.rollback()

w = lambda n: int(n).to_bytes(32, "big")
a32 = lambda hx: bytes(12) + bytes.fromhex(hx)
def log(addr, sig, topics, data, block, idx, tx):
    t0 = bytes.fromhex(topic0(sig)[2:])
    return dict(addr=addr, t0=t0, topics=[t0] + topics, data=data, block=block, idx=idx, tx=bytes.fromhex(("%064x" % tx)))
D, M = CONTRACTS["dog"], CONTRACTS["dogmarket"]
BNB = 10 ** 18
buyer = "ab" * 20
now = datetime.datetime.now(datetime.timezone.utc)
b = cp - 100  # inside the already-synced range so the API's safe block covers it
L = [
    log(M, "Listed(uint256,address,uint256,uint256)", [w(1), a32(own[1])], w(BNB // 2) + w(0), b + 1, 0, 101),
    log(M, "Listed(uint256,address,uint256,uint256)", [w(2), a32(own[2])], w(BNB // 5) + w(0), b + 2, 0, 102),
    log(M, "PriceUpdated(uint256,address,uint256,uint256)", [w(2), a32(own[2])], w(BNB // 5) + w(BNB // 4), b + 3, 0, 103),
    log(M, "Sold(uint256,address,address,uint256,uint256,uint256)", [w(1), a32(own[1]), a32(buyer)], w(BNB // 2) + w(BNB // 200) + w(BNB // 2 - BNB // 200), b + 4, 0, 104),
    log(D, "Transfer(address,address,uint256)", [a32(own[1]), a32(buyer), w(1)], b"", b + 4, 1, 104),
    log(M, "Withdrawn(address,uint256)", [a32(own[1])], w(BNB // 2 - BNB // 200), b + 5, 0, 105),
    log(M, "Listed(uint256,address,uint256,uint256)", [w(3), a32(own[3])], w(BNB) + w(0), b + 6, 0, 106),
    log(D, "Committed(uint256,uint256,uint256)", [w(3)], w(1) + w(b + 7), b + 7, 0, 107),       # reroll -> listing 3 stale
    log(M, "Listed(uint256,address,uint256,uint256)", [w(4), a32(own[4])], w(3 * BNB) + w(0), b + 8, 0, 108),
    log(M, "Cancelled(uint256,address)", [w(4), a32(own[4])], b"", b + 9, 0, 109),
]
rows = 0
for l in L:
    topics = ["0x" + t.hex() for t in l["topics"]]
    event, p = common.decode_log(l["addr"], topics, l["data"])
    assert event, l
    cur.execute("INSERT INTO raw_logs (chain_id, block_number, block_hash, block_time, tx_hash, tx_index, log_index, address, topic0, topics, data)"
                " VALUES (56,%s,%s,%s,%s,0,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (l["block"], bytes(32), now, l["tx"], l["idx"], bytes.fromhex(l["addr"][2:]), l["t0"], psycopg2.extras.Json(topics), l["data"]))
    apply_dog_event(cur, l["addr"], event, p, (l["block"], now, l["tx"], 0, l["idx"]))
    rows += 1
conn.commit()
print("applied", rows, "synthetic logs")

port = 18787
api = subprocess.Popen([sys.executable, os.path.join(ROOT, "api.py")] + (["--env", env] if env else []) + ["--port", str(port)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
time.sleep(2)
def get(path):
    return json.loads(urllib.request.urlopen("http://127.0.0.1:%d%s" % (port, path), timeout=10).read())
bad = []
def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name + (" " + str(extra) if extra and not ok else ""))
    if not ok: bad.append(name)
try:
    s = get("/v1/dog/stats")
    check("stats minted/holders/market (stale listing not counted)", s["minted"] == 19 and s["market"]["listings"] == 1 and s["market"]["sales"] == 1
          and s["market"]["floorPriceWei"] == str(BNB // 4) and s["market"]["latestTradePriceWei"] == str(BNB // 2)
          and s["market"]["volumeWei"] == str(BNB // 2) and s["market"]["feesWei"] == str(BNB // 200) and s["rerolls"] == 1, s)
    ls = get("/v1/dog/listings")
    check("listings sorted by price (token 2 at 0.25, token 3 at 1.0)", [x["tokenId"] for x in ls["items"]] == ["2", "3"], ls)
    check("listing 3 stale after reroll, listing 2 not", {x["tokenId"]: x["stale"] for x in ls["items"]} == {"2": False, "3": True}, ls)
    check("listing carries dog fields (owner, status, rerolls)", all(k in ls["items"][0] for k in ("owner", "status", "rerolls", "seed", "priceWei", "seller")))
    ls2 = get("/v1/dog/listings?sort=price_desc&limit=1")
    check("price_desc + cursor", ls2["items"][0]["tokenId"] == "3" and ls2["nextCursor"] and get("/v1/dog/listings?sort=price_desc&limit=1&cursor=" + ls2["nextCursor"])["items"][0]["tokenId"] == "2")
    tr = get("/v1/dog/trades")
    check("trades: one sale, fee 1%", len(tr["items"]) == 1 and tr["items"][0]["feeWei"] == str(BNB // 200) and tr["items"][0]["buyer"] == "0x" + buyer, tr)
    t1 = get("/v1/dog/tokens/1")
    check("token 1 now owned by the buyer, no listing", t1["owner"] == "0x" + buyer and t1["listing"] is None and t1["minted"], t1)
    check("token 3 rerolls=1 and seed reset", get("/v1/dog/tokens/3")["rerolls"] == 1 and get("/v1/dog/tokens/3")["seed"] is None)
    check("unminted token -> minted:false", get("/v1/dog/tokens/9999")["minted"] is False)
    ot = get("/v1/dog/owners/0x" + buyer + "/tokens")
    check("owner tokens (buyer holds #1)", ot["count"] == 1 and ot["items"][0]["tokenId"] == "1", ot)
    ot1 = get("/v1/dog/owners/0x" + own[1] + "/tokens")
    check("seller withdrawn total", ot1["withdrawnWei"] == str(BNB // 2 - BNB // 200), ot1)
    tk = get("/v1/dog/tokens?limit=5")
    check("tokens page newest first", [x["tokenId"] for x in tk["items"]] == ["19", "18", "17", "16", "15"] and tk["nextCursor"], tk["items"][0])
    ac = get("/v1/dog/activity?limit=50")
    types = [x["type"] for x in ac["items"]]
    check("activity has sale, withdraw, list, price, cancel, reroll, transfer, mint", all(t in types for t in ("sale", "withdraw", "list", "price", "cancel", "reroll", "transfer", "mint")), types[:12])
    check("activity: no empty-commit noise (rerolls=0 Committed hidden)", types.count("reroll") == 1, types.count("reroll"))
    check("activity filter by tokenId=1", all(x["tokenId"] == "1" for x in get("/v1/dog/activity?tokenId=1")["items"]) and len(get("/v1/dog/activity?tokenId=1")["items"]) >= 3)
    check("activity filter type=sale", [x["type"] for x in get("/v1/dog/activity?type=sale")["items"]] == ["sale"])
    check("activity filter address=buyer", len(get("/v1/dog/activity?address=0x" + buyer)["items"]) >= 2)
    ev = get("/v1/events?contract=dog&limit=3")
    check("existing /v1/events works with contract=dog", len(ev["events"]) == 3 and ev["events"][0]["event"] in ("Committed", "Transfer", "Snapshot"), ev["events"][0])
    ev2 = get("/v1/events?contract=dogmarket&event=Sold")
    check("existing /v1/events works with contract=dogmarket&event=Sold", len(ev2["events"]) == 1)
    for bad_path in ("/v1/dog/tokens/0", "/v1/dog/tokens/abc", "/v1/dog/owners/0x12/tokens", "/v1/dog/activity?type=zzz", "/v1/dog/listings?sort=zzz"):
        try:
            urllib.request.urlopen("http://127.0.0.1:%d%s" % (port, bad_path), timeout=10); check("rejects " + bad_path, False)
        except urllib.error.HTTPError as e:
            check("rejects %s with %d" % (bad_path, e.code), e.code in (400, 404))
    hh = get("/health")
    check("/health still works", "safeBlock" in hh)
    st = get("/v1/stats")
    check("existing /v1/stats unchanged shape", "market" in st and "registered" in st)
finally:
    api.terminate()
print("RESULT", "OK" if not bad else "FAIL: %s" % bad)
sys.exit(1 if bad else 0)
