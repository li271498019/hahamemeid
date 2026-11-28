-- Haha Dog stalled flag (2026-11-28).
--
-- A dog whose seed hash is permanently unrecoverable (target block beyond the
-- EIP-2935 window and no Snapshot stored) is status 3 on-chain and needs a
-- free reroll. resolve_seeds() marks such dogs so the API can return
-- "stalled" instead of the vague "check". The flag is reset whenever the dog
-- is re-committed (reroll) or gets a seed.
ALTER TABLE dogs ADD COLUMN IF NOT EXISTS stalled BOOLEAN NOT NULL DEFAULT FALSE;
