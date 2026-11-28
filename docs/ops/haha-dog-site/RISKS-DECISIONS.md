# Round 2 risks and decisions

Decisions for you:
1. **Races in `rpc.js`** (see NGINX-PLAN): to make the whole site truly Ankr-first, change `fastUrls()` to `/rpc/` then hedge. Not changed.
2. **Dedicated Ankr keys for the site** (recommended) vs reusing the indexer's two keys.
3. **Start time** is a fixed value: 2026-11-28 10:47 (UTC+8) = HahaDog deploy block 136153154. (The reroll/market "open" strings changed accordingly.)
4. skill.md version 23 (was 22). Bump again if more edits land before deploy.

Risks:
- Ankr keys: nginx `error.log` can print the upstream URL incl. key path on upstream errors (tested: yes). Mitigate: `error_log` mode 640, never share logs, `nginx -T` also prints keys. Consider `error_log ... crit` for the vhost.
- No JSON-RPC method whitelist (no Lua/NJS in this nginx); anyone can burn Ankr quota via /rpc/ within the 120r/m limit. Consider a monitor on Ankr usage.
- HTTP-200 JSON-RPC errors from Ankr (e.g. gas cap on heavy eth_call) are invisible to nginx; browser retries via `/rpc-bsc/` then publicnode. Ankr's heavy-call behavior is untested until the server probe runs.
- Ankr latency vs dataseed unknown; 2s/6s timeouts mean a degraded Ankr adds up to 12s to a request before dataseed answers (browser gives up earlier at its own timeouts and retries).
- Static DNS in nginx upstreams (resolved at start/reload); a provider IP change needs a reload.
- Indexer deploy needs a stop + backfill window; pre-existing reorg FK bug (see INDEXER-PLAN).
- BscScan verification of the four dog contracts could not be confirmed via API; copy says "look up on BscScan" instead of claiming verified.
- English nav may wrap on narrow widths (cosmetic).
- Market stats from chain fallback use `eth_getLogs` from the browser (only when the indexer is down).
