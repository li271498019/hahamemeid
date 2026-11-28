-- Haha Dog (2026-11-28): derived tables for HahaDog (ERC-721) and HahaDogMarket.
-- Idempotent. Also appended to schema.sql, which the syncer runs on start, so
-- the migration only needs applying by hand when the API is deployed first.
-- All uint256 values NUMERIC; addresses and hashes BYTEA.

CREATE TABLE IF NOT EXISTS dogs (
    token_id      NUMERIC PRIMARY KEY,
    owner         BYTEA,                   -- latest Transfer.to
    mint_block    BIGINT,
    mint_time     TIMESTAMPTZ,
    mint_tx       BYTEA,
    commit_block  BIGINT NOT NULL,         -- latest Committed.commitBlock
    commit_time   TIMESTAMPTZ NOT NULL,
    rerolls       INT NOT NULL DEFAULT 0,  -- latest Committed.rerolls
    seed          BYTEA,                   -- keccak256(abi.encode(hash(commit+4), tokenId, rerolls)); NULL until known
    seed_block    BIGINT                   -- block at which the seed became known (informational)
);
CREATE INDEX IF NOT EXISTS dogs_owner ON dogs (owner, token_id);
CREATE INDEX IF NOT EXISTS dogs_pending_seed ON dogs (commit_block) WHERE seed IS NULL;

CREATE TABLE IF NOT EXISTS dog_snapshots (
    block_number BIGINT PRIMARY KEY,
    block_hash   BYTEA NOT NULL
);

CREATE TABLE IF NOT EXISTS dog_listings (
    token_id     NUMERIC PRIMARY KEY,
    seller       BYTEA NOT NULL,
    price_wei    NUMERIC NOT NULL,
    rerolls      INT NOT NULL,             -- rerolls at listing time (market's own check)
    listed_block BIGINT NOT NULL,
    listed_time  TIMESTAMPTZ NOT NULL,
    tx_hash      BYTEA NOT NULL,
    log_index    INT NOT NULL
);
CREATE INDEX IF NOT EXISTS dog_listings_price ON dog_listings (price_wei, token_id);

CREATE TABLE IF NOT EXISTS dog_trades (
    token_id      NUMERIC NOT NULL,
    seller        BYTEA NOT NULL,
    buyer         BYTEA NOT NULL,
    price_wei     NUMERIC NOT NULL,
    fee_wei       NUMERIC NOT NULL,
    proceeds_wei  NUMERIC NOT NULL,
    block_number  BIGINT NOT NULL,
    block_time    TIMESTAMPTZ NOT NULL,
    tx_hash       BYTEA NOT NULL,
    log_index     INT NOT NULL,
    PRIMARY KEY (tx_hash, log_index)
);
CREATE INDEX IF NOT EXISTS dog_trades_time ON dog_trades (block_number DESC, log_index DESC);
CREATE INDEX IF NOT EXISTS dog_trades_token ON dog_trades (token_id, block_number DESC);

CREATE TABLE IF NOT EXISTS dog_withdrawals (
    account      BYTEA NOT NULL,
    amount_wei   NUMERIC NOT NULL,
    block_number BIGINT NOT NULL,
    block_time   TIMESTAMPTZ NOT NULL,
    tx_hash      BYTEA NOT NULL,
    log_index    INT NOT NULL,
    PRIMARY KEY (tx_hash, log_index)
);
