-- Season 1 redemption proof: store the Merkle proof per eligible entry so the
-- indexer can serve it to agents (GET /v1/season1/proof/{aiId}?day=).
-- The proof is computed once by snapshot_day.py from the same tree that
-- produced the day root, so it always matches the manifest.
ALTER TABLE season1_entries ADD COLUMN IF NOT EXISTS proof JSONB;
ALTER TABLE season1_entries OWNER TO haha;
