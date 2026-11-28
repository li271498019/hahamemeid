#!/usr/bin/env python3
"""Read-only probe of the RPC endpoints the indexer uses. Run ON THE SERVER:
    python3 ankr_probe.py
Reads BSC_RPC_URLS from /etc/haha/indexer.env inside the process and prints only
labels (ankr#1, ankr#2, dataseed), HTTP status, timing and sizes. It never prints
a URL or key. Only eth_blockNumber / eth_call / eth_getLogs / eth_getBlockByNumber."""
import json, re, ssl, sys, time, urllib.request, urllib.error
from urllib.parse import urlparse

ENV = "/etc/haha/indexer.env"
DOG = "0x26f88A5db4925e9aFa35B1096FdD6DBa09f056c6"
RENDERER = "0xCA760D9D3E76DcDC7AC6bcc55D53346b8a2c107E"
MODEL = "0x3277990797Ed8B15B3674ee0C557011F5a1eCCC9"
MARKET = "0xD7F5502Bd7a52E17959bF4b7F1180f6e3611fd49"
SEED = "e30d88c427b9041ce20e2d496c4620ca140cb216a2096eca4f6a0d0cc7af999e"
DATASEED = "https://bsc-dataseed.binance.org"


def endpoints():
    env = {}
    for l in open(ENV):
        if "=" in l and not l.lstrip().startswith("#"):
            k, v = l.strip().split("=", 1)
            env[k] = v.strip().strip('"').strip("'")
    urls = [u.strip() for u in env.get("BSC_RPC_URLS", "").split(",") if u.strip()]
    ankr = [u for u in urls if "ankr" in (urlparse(u).hostname or "")]
    out = [("ankr#%d" % (i + 1), u) for i, u in enumerate(ankr)]
    out.append(("dataseed", DATASEED))
    return out


def scrub(s, urls):
    s = str(s)
    for u in urls:
        s = s.replace(u, "<url>")
        p = urlparse(u).path.strip("/").split("/")
        for seg in p:
            if len(seg) > 8:
                s = s.replace(seg, "<key>")
    return re.sub(r"https?://\S+", "<url>", s)[:160]


def post(url, body, urls, timeout=20):
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "User-Agent": "haha-probe/1"})
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, int((time.time() - t) * 1000), len(raw), json.loads(raw), None
    except urllib.error.HTTPError as e:
        return e.code, int((time.time() - t) * 1000), 0, None, scrub(e.read()[:200], urls)
    except Exception as e:
        return 0, int((time.time() - t) * 1000), 0, None, scrub(e, urls)


def pad(h): return h.rjust(64, "0")


def main():
    eps = endpoints()
    urls = [u for _, u in eps]
    print("endpoints:", [n for n, _ in eps])
    cases = []
    cases.append(("eth_blockNumber", {"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []}))
    cases.append(("totalSupply (plain call)", {"jsonrpc": "2.0", "id": 1, "method": "eth_call", "params": [{"to": DOG, "data": "0x18160ddd"}, "latest"]}))
    cases.append(("svgOf(seed) ~2.3M gas, gas=30M", {"jsonrpc": "2.0", "id": 1, "method": "eth_call", "params": [{"to": RENDERER, "data": "0xb951bff3" + SEED, "gas": hex(30000000)}, "latest"]}))
    cases.append(("svgOf(seed) no gas field", {"jsonrpc": "2.0", "id": 1, "method": "eth_call", "params": [{"to": RENDERER, "data": "0xb951bff3" + SEED}, "latest"]}))
    cases.append(("tokenURI(1) ~4.5M gas, gas=30M", {"jsonrpc": "2.0", "id": 1, "method": "eth_call", "params": [{"to": DOG, "data": "0xc87b56dd" + pad("1"), "gas": hex(30000000)}, "latest"]}))
    cases.append(("tokenURI(1) no gas field", {"jsonrpc": "2.0", "id": 1, "method": "eth_call", "params": [{"to": DOG, "data": "0xc87b56dd" + pad("1")}, "latest"]}))
    cases.append(("modelData() gas=30M", {"jsonrpc": "2.0", "id": 1, "method": "eth_call", "params": [{"to": MODEL, "data": "0xbd0a9d4e", "gas": hex(30000000)}, "latest"]}))
    cases.append(("batch 60 x dogOf", [{"jsonrpc": "2.0", "id": i + 1, "method": "eth_call", "params": [{"to": DOG, "data": "0x2f403afd" + pad(format(i % 5 + 1, "x"))}, "latest"]} for i in range(60)]))
    cases.append(("batch 100 x ownerOf", [{"jsonrpc": "2.0", "id": i + 1, "method": "eth_call", "params": [{"to": DOG, "data": "0x6352211e" + pad(format(i % 5 + 1, "x"))}, "latest"]} for i in range(100)]))
    cases.append(("batch 200 x ownerOf", [{"jsonrpc": "2.0", "id": i + 1, "method": "eth_call", "params": [{"to": DOG, "data": "0x6352211e" + pad(format(i % 5 + 1, "x"))}, "latest"]} for i in range(200)]))
    for label, url in eps:
        print("\n==", label)
        st, ms, n, j, err = post(url, cases[0][1], urls)
        head = int(j["result"], 16) if j and "result" in j else None
        print("%-34s http=%s %dms bytes=%d %s" % (cases[0][0], st, ms, n, err or ("head ok" if head else "no result")))
        for name, body in cases[1:]:
            st, ms, n, j, err = post(url, body, urls)
            note = err or ""
            if j is not None:
                one = j[0] if isinstance(j, list) else j
                if isinstance(j, list):
                    errs = sum(1 for x in j if "error" in x)
                    note = "items=%d errors=%d" % (len(j), errs)
                    if errs:
                        note += " first_err=" + scrub(next(x for x in j if "error" in x)["error"], urls)
                elif "error" in one:
                    note = "rpc_error " + scrub(one["error"], urls)
                else:
                    r = one.get("result", "")
                    note = "result_chars=%d" % len(r)
            print("%-34s http=%s %dms bytes=%d %s" % (name, st, ms, n, note))
        # eth_getLogs windows over the dog contracts
        if head:
            for span in (2000, 5000, 20000, 100000):
                body = {"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs", "params": [{"fromBlock": hex(head - span), "toBlock": hex(head), "address": [DOG, MARKET]}]}
                st, ms, n, j, err = post(url, body, urls, 30)
                note = err or ("rpc_error " + scrub(j["error"], urls) if j and "error" in j else "logs=%d" % len((j or {}).get("result", [])))
                print("%-34s http=%s %dms bytes=%d %s" % ("getLogs span=%d" % span, st, ms, n, note))
        # burst: 30 sequential eth_blockNumber as fast as possible
        codes = {}
        t = time.time()
        for _ in range(30):
            st = post(url, cases[0][1], urls, 10)[0]
            codes[st] = codes.get(st, 0) + 1
        print("burst 30 sequential blockNumber: %s in %.1fs" % (codes, time.time() - t))
        # 8 parallel heavy tokenURI (browser gallery-ish)
        import threading
        res = []
        def w():
            res.append(post(url, cases[4][1], urls, 30)[:2])
        ts = [threading.Thread(target=w) for _ in range(8)]
        t = time.time(); [x.start() for x in ts]; [x.join() for x in ts]
        print("8 parallel tokenURI: codes=%s max=%dms wall=%.1fs" % (sorted(set(r[0] for r in res)), max(r[1] for r in res), time.time() - t))


if __name__ == "__main__":
    main()
