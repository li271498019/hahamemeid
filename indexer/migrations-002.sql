-- Safe to run on a live V1 database. Adds a lookup index only.
-- Supports GET /v1/reviews/latest ordering by most recent first.
-- Does not rewrite rows, drop columns, or touch the checkpoint.

CREATE INDEX IF NOT EXISTS reviews_latest ON reviews (block_time DESC, block_number DESC, tx_hash DESC, log_index DESC);
