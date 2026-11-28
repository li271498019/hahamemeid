-- Haha Dog approval indexing (2026-11-28).
--
-- HahaDog emits ERC-721 Approval / ApprovalForAll, which the syncer did not
-- decode. /v1/dog/listings could then only guess whether a listing is still
-- buyable ("seller still holds it, not rerolled") and missed the case where
-- the seller revoked the market's approval. These tables make the listing's
-- buyable flag exact. They are derived from raw_logs like the other dog_*
-- tables, so they belong in handle_reorg's TRUNCATE list and in DOG_TABLES.
CREATE TABLE IF NOT EXISTS dog_approvals (
    token_id NUMERIC PRIMARY KEY,
    approved BYTEA NOT NULL
);
CREATE TABLE IF NOT EXISTS dog_operators (
    owner    BYTEA NOT NULL,
    operator BYTEA NOT NULL,
    approved BOOLEAN NOT NULL,
    PRIMARY KEY (owner, operator)
);
ALTER TABLE dog_approvals OWNER TO haha;
ALTER TABLE dog_operators OWNER TO haha;
