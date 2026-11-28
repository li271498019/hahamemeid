# Indexer plan: HahaDog + HahaDogMarket (NOT deployed; server untouched)

Patch: `indexer/indexer-haha-dog.patch` (against live /opt/haha-indexer). Dry-run applies cleanly to the base copy.

## What it adds
- `schema.sql` + `migrations/007_haha_dog.sql` (idempotent): `dogs`, `dog_snapshots`, `dog_listings`, `dog_trades`, `dog_withdrawals`. The syncer runs schema.sql on start, so the migration is only needed if the API is deployed first.
- `common.py`: HahaDog + HahaDogMarket in `log_addresses()` and event ABIs (Transfer, Committed, Snapshot, Listed/PriceChanged/Cancelled/Cleared/Sold/Withdrawn); `DOG_START_BLOCK`.
- `dog_store.py`: derives the dog_* tables as a pure function of raw_logs in block order (so reorg replay = truncate + rebuild). Seeds: `keccak(abi.encode(hash(commitBlock+4), tokenId, rerolls))`, resolved once the block is in the live-hash window (head via `block_number()`).
- `syncer.py`: applies dog events, resolves seeds each loop, reorg handling includes dog tables.
- `dog_backfill.py`: one-time backfill from deploy block (136153154) to checkpoint; rebuilds dog_* in one transaction; refuses to commit if the checkpoint moved.
- `api.py`: `GET /v1/dog/stats`, `/v1/dog/tokens` (+`/{id}`), `/v1/dog/owners/{address}/tokens`, `/v1/dog/listings`, `/v1/dog/trades`, `/v1/dog/activity`. Stale listings (seller != current owner, or rerolled since listing) are flagged and excluded from floor/count. Documented in api.html §24 and skill.md §17.7.
- Site already consumes these with chain fallback (mint cards, market stats/list, scan Haha Dog panel); with the indexer down, those pages fall back to direct chain reads.

## Deploy order (needs your go + the server)
1. Back up DB (`pg_dump`) and `/opt/haha-indexer`.
2. Copy new code to `/opt/haha-indexer`; do NOT restart.
3. `systemctl stop haha-indexer` (checkpoint frozen).
4. `python3 dog_backfill.py --dry-run` (range + log counts), then `python3 dog_backfill.py`. Re-runnable.
5. `systemctl start haha-indexer && systemctl restart haha-api`.
6. Verify: `curl /api/v1/dog/stats` vs chain (`totalSupply`, market listings count); `/v1/dog/owners/<addr>/tokens` for a known holder; compare `dogs.rerolls`/owner with `ownerOf`/`rerollsOf` for a sample.
7. Deploy the site patch AFTER the API is up (site falls back to chain if not, so order is not breaking).
Rollback: restore code, restart; the new tables are additive and can stay or be dropped.

## Test evidence (local scratch Postgres, live BSC)
- Unit: `tests/test_dog_store.py` 3 OK. Synthetic API test `tests/dog_api_synthetic.py` (incl. stale-listing exclusion, owner tokens with `withdrawn`).
- `tests/dog_e2e.py`: backfill -> forward sync with the real `Syncer` -> forced reorg rebuild -> compare with chain; identical dumps before/after rebuild.
- Bug found and fixed during testing: `h_dog_owner_tokens` KeyError(0) with RealDictCursor (500).

## Known issues / follow-ups
- **Pre-existing (not ours, for C):** `handle_reorg` `TRUNCATE` fails on an FK from `season1_finding_reports` to `season1_findings`. A real reorg would crash the syncer. In tests I dropped the FK in the scratch DB. Fix: `TRUNCATE ... CASCADE` or drop the FK.
- Approvals are not indexed (market `getApproved` read from chain when needed).
- Seed status "check" appears if a seed can't be computed in time (hash window expired); scan shows it as "check", not an error.
- MCP tools for dog data (agents reading dogs via MCP) not done; follow-up.
- Public RPCs reject the multi-address `getLogs` filter (13+ addresses); Ankr should accept it (verify with probe step 1 `getLogs` rows).
