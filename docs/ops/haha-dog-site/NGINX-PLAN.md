# Nginx plan: whole site prefers Ankr, with failover (NOT applied)

## What changes
`/rpc/` order becomes: Ankr key (one of two, 50/50) -> the other Ankr key -> official BSC dataseed.
Failover triggers: 401/402/403/429/500/502/503/504, connect/read timeouts. Nothing else changes for the browser (`window.HAHA_RPC_URL="/rpc/"`).
Keys live only in `/etc/nginx/haha-rpc-secrets.conf` (server only, root:root 0600). Nothing in the repo or in these files contains a key.

Files (all under `nginx/etc/`):
- `conf.d/haha-rpc.conf` (new, no secrets): dataseed upstream, `split_clients` key spread, `haha_rpc` log format.
- `haha-rpc-secrets.conf.example` -> real file on server: `upstream haha_rpc_ankr` + 3 maps (host, key1 path, key2 path).
- `snippets/haha-rpc-common.conf` (new): body cap 32k, Retry-After, security headers, keepalive (`http 1.1`, `Connection ""`), `proxy_ssl_server_name on`, `proxy_ssl_verify on`, Origin/Referer stripped, `recursive_error_pages on` (required for 3 hops), `proxy_next_upstream off`.
- `rpc-location.conf`: replaces the `location /rpc/` block; adds named locations `@haha_rpc_a/_b/_bsc` and `/rpc-bsc/` (direct dataseed, used by the browser's own 2nd try, because nginx can't see a JSON-RPC error inside HTTP 200).
- `sites-enabled-haha.meme.diff`: exact diff against the live `sites-enabled/haha.meme`.

Design points (each verified in local tests):
- `try_files /__rpc_none @haha_rpc_a` instead of `error_page` on `/rpc/`: `limit_req`/`limit_conn` run first, so a rate-limited client gets its 429 and cannot bypass the limit.
- Named locations don't allow a URI in `proxy_pass`, so it's the variable form (`proxy_pass https://upstream$path`), with explicit `Host` and `proxy_ssl_name` = real hostname (correct SNI + cert check).
- Named locations don't inherit `client_max_body_size`/headers, so those live in the common snippet.
- Timeouts: Ankr connect 2s / read 6s; dataseed connect 3s / read 8s. Worst case with two hung Ankr keys = 12s to the dataseed answer (tested). Keepalive 16 to Ankr, 8 to dataseed.
- `X-Rpc-Upstream: ankr-a|ankr-b|bsc` response header and `haha-rpc.log` (`up=` lists every stage tried) show who answered.

## Apply (on the server, when approved)
1. Back up: `cp -a /etc/nginx /root/nginx-backup-$(date +%F)`.
2. Create the secrets file WITHOUT echoing values: a small script reads the first two Ankr URLs from `BSC_RPC_URLS` in `/etc/haha/indexer.env`, writes `/etc/nginx/haha-rpc-secrets.conf` (template = the `.example`), `chmod 600`. Recommended: use two NEW Ankr keys dedicated to the site, not the indexer's (a flood on the site must not rate-limit the indexer).
3. Install `conf.d/haha-rpc.conf`, `snippets/haha-rpc-common.conf`; make sure `nginx.conf` includes `conf.d/*.conf` in `http {}` (or add the include).
4. Apply the diff to `sites-enabled/haha.meme`; `nginx -t` (do NOT paste `nginx -T`: it prints the keys).
5. `systemctl reload nginx` (no downtime). Rollback: restore backup, `nginx -t`, reload.

## Test plan (read-only; run on the server)
1. `python3 nginx/ankr_probe.py` BEFORE applying. Reads the keys inside the process, prints only labels (ankr#1/#2/dataseed), HTTP codes, timings, sizes. Covers: eth_blockNumber, plain call, heavy `svgOf(seed)` (~2.3M gas) and `tokenURI(1)` (~4.5M gas) with and without `gas=30M`, `modelData()`, 60/100/200-call batches, `eth_getLogs` windows 2k/5k/20k/100k blocks over the dog contracts, 30-call burst, 8 parallel tokenURI. Decision rule: if heavy `eth_call` or the 100-call batch fails on Ankr, failover still saves it, but we should know the rate of fallbacks.
   **Not run yet: the keys are only on the server and I did not touch the server. Local tests used a TLS fake Ankr/dataseed.**
2. After reload: `curl -s -D- -o /dev/null -X POST https://haha.meme/rpc/ -H 'content-type: application/json' -d '{"jsonrpc":"2.0","id":1,"method":"eth_blockNumber","params":[]}'` x20 -> `x-rpc-upstream: ankr-a|ankr-b`.
3. Heavy read via the site: `tokenURI(1)` and `svgOf(seed)` `eth_call` through `/rpc/` with curl (same bodies as the probe), 100-call batch, 8 parallel; expect 200 and `ankr-*`.
4. Watch `tail -f /var/log/nginx/haha-rpc.log` for 10 min: `up=` should be single `200`; occasional `429, 200` = fallback working. Alert if `bsc` appears often.
5. Failover drill (optional, off-peak): temporarily break key 1 in the secrets file, reload, expect `ankr-b` for everything; restore.

## Local test results (`nginx/test-results.txt`, nginx 1.24.0, fake TLS upstreams): 15 checks, 0 failed
Healthy -> only Ankr answers, both keys used (29/31). Host + SNI correct, key path correct, Origin/Referer stripped. Key1 429 -> all via key2. Both Ankr down -> dataseed. 403 from both -> dataseed. 100-call batch (21 KB) forwarded byte-identical at all 3 stages. Ankr hang -> dataseed after 12s. All three failing -> quick HTTP 500. JSON-RPC error in HTTP 200 passes through. `/rpc-bsc/` OK. >32k body -> 413 with no upstream hit. Rate limit still enforced (429s from nginx itself). Reproduce: `cd nginx/test && bash render.sh && python3 run_tests.py`.

## Whole-site audit (does all JS use /rpc/?)
- `js/config.js`: `HAHA_RPC_URL="/rpc/"`. `rpc.js`, `haha-dog.js`, the market/mint/scan JS use it.
- **Exception to decide:** `rpc.js` `fastUrls()` races `/rpc/` with 3 public nodes (dataseed, defibit, publicnode) on every call (1.8s timeout), and the fastest wins. So even with Ankr behind `/rpc/`, public nodes can answer and each lookup fires 4 requests. For "Ankr first", change to: `/rpc/` alone, then hedge to public nodes only after ~800 ms or on error. I did NOT change it (it's the live resilience behaviour for name lookups); it's a ~10-line change in `fastUrls()/raceCall`. Say if you want it.
- `haha-dog.js` order: `/rpc/` -> `/rpc-bsc/` -> publicnode (sequential).
- `eth_getLogs` is sent by the browser only as the Haha Dog market-stats fallback when the indexer is down. Note in the nginx comment for any future method whitelist.
