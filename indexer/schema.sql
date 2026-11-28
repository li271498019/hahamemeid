-- haha.meme V1 indexer schema (Postgres 16).
-- Raw logs + checkpoint; derived tables only ever reflect blocks <= safe_block.
-- All uint256 values are NUMERIC (exact, arbitrary precision).
-- Addresses / hashes are BYTEA (20 / 32 bytes). JSON uses lowercase hex.

CREATE TABLE IF NOT EXISTS raw_logs (
    chain_id     SMALLINT NOT NULL,
    block_number BIGINT NOT NULL,
    block_hash   BYTEA NOT NULL,
    block_time   TIMESTAMPTZ NOT NULL,
    tx_hash      BYTEA NOT NULL,
    tx_index     INT NOT NULL,
    log_index    INT NOT NULL,
    address      BYTEA NOT NULL,
    topic0       BYTEA NOT NULL,
    topics       JSONB NOT NULL,
    data         BYTEA NOT NULL,
    PRIMARY KEY (chain_id, block_number, tx_index, log_index)
);
CREATE INDEX IF NOT EXISTS raw_logs_addr_block ON raw_logs (address, block_number);

CREATE TABLE IF NOT EXISTS blocks (
    block_number BIGINT PRIMARY KEY,
    hash         BYTEA NOT NULL,
    parent_hash  BYTEA NOT NULL
);

-- Single row (id = 1). Only updated in the same transaction as the
-- derived tables it covers. Restart resumes from safe_block + 1.
CREATE TABLE IF NOT EXISTS checkpoint (
    id         SMALLINT PRIMARY KEY,
    safe_block BIGINT NOT NULL,
    safe_hash  BYTEA NOT NULL
);

CREATE TABLE IF NOT EXISTS names (
    token_id     NUMERIC PRIMARY KEY,
    label        TEXT NOT NULL,
    tld          SMALLINT NOT NULL, -- 0 = .haha, 1 = .meme
    full_name    TEXT NOT NULL UNIQUE,
    owner        BYTEA NOT NULL,
    mint_ai_id   BYTEA NOT NULL,
    reserved_mint BOOLEAN NOT NULL,
    mint_block   BIGINT NOT NULL,
    mint_time    TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS names_owner ON names (owner);
CREATE INDEX IF NOT EXISTS names_label ON names (label);

CREATE TABLE IF NOT EXISTS listings (
    token_id    NUMERIC PRIMARY KEY,
    seller      BYTEA NOT NULL,
    price_wei   NUMERIC NOT NULL,
    listed_block BIGINT NOT NULL,
    listed_time TIMESTAMPTZ NOT NULL,
    tx_hash     BYTEA NOT NULL,
    log_index   INT NOT NULL
);
CREATE INDEX IF NOT EXISTS listings_price ON listings (price_wei);

CREATE TABLE IF NOT EXISTS trades (
    token_id    NUMERIC NOT NULL,
    seller      BYTEA NOT NULL,
    buyer       BYTEA NOT NULL,
    price_wei   NUMERIC NOT NULL,
    fee_wei     NUMERIC NOT NULL,
    proceeds_wei NUMERIC NOT NULL,
    block_number BIGINT NOT NULL,
    block_time  TIMESTAMPTZ NOT NULL,
    tx_hash     BYTEA NOT NULL,
    log_index   INT NOT NULL,
    PRIMARY KEY (tx_hash, log_index)
);
CREATE INDEX IF NOT EXISTS trades_block ON trades (block_number DESC);

CREATE TABLE IF NOT EXISTS agents (
    agent_id       NUMERIC PRIMARY KEY,
    name_token_id  NUMERIC NOT NULL,
    owner          BYTEA NOT NULL,
    operator_ai_id BYTEA NOT NULL,
    generation     INT NOT NULL,
    agent_uri      TEXT NOT NULL,
    active         BOOLEAN NOT NULL,
    activated_block BIGINT NOT NULL,
    activated_time TIMESTAMPTZ NOT NULL,
    reset_block    BIGINT,
    reset_time     TIMESTAMPTZ,
    stars_sum      NUMERIC NOT NULL DEFAULT 0,
    stars_count    BIGINT NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS agents_name_token ON agents (name_token_id, generation DESC);
CREATE INDEX IF NOT EXISTS agents_active ON agents (active, activated_block DESC);

CREATE TABLE IF NOT EXISTS reviews (
    agent_id     NUMERIC NOT NULL,
    rater_ai_id  BYTEA NOT NULL,
    rater        BYTEA NOT NULL,
    stars        SMALLINT NOT NULL,
    review       TEXT NOT NULL,
    edited       BOOLEAN NOT NULL,
    block_number BIGINT NOT NULL,
    block_time   TIMESTAMPTZ NOT NULL,
    tx_hash      BYTEA NOT NULL,
    log_index    INT NOT NULL,
    PRIMARY KEY (agent_id, rater_ai_id)
);
CREATE INDEX IF NOT EXISTS reviews_agent ON reviews (agent_id, block_number DESC);

CREATE TABLE IF NOT EXISTS points (
    ai_id         BYTEA PRIMARY KEY,
    balance       NUMERIC NOT NULL,
    last_user     BYTEA NOT NULL,
    last_reason   BYTEA NOT NULL,
    updated_block BIGINT NOT NULL,
    updated_time  TIMESTAMPTZ NOT NULL,
    handle        TEXT
);
CREATE INDEX IF NOT EXISTS points_balance ON points (balance DESC);

-- Internal: .ai handle cache (1h TTL). Never exposed directly; the API
-- only shows a handle whose keccak256 matches the ai_id.
CREATE TABLE IF NOT EXISTS handle_cache (
    user_address BYTEA PRIMARY KEY,
    handle       TEXT,
    fetched_at   TIMESTAMPTZ NOT NULL
);

-- Season 1. Same statements as migrations/003_season1.sql.
CREATE TABLE IF NOT EXISTS season1_days (
    day_index            BIGINT PRIMARY KEY,
    merkle_root          BYTEA NOT NULL,
    snapshot_block       BIGINT NOT NULL,
    snapshot_block_hash  BYTEA NOT NULL,
    reserved_count       INT NOT NULL,
    remaining_slots      INT NOT NULL,
    opened               BOOLEAN NOT NULL,
    recomputed_root      BYTEA,
    confirmations_seen   BIGINT,
    updated_block        BIGINT NOT NULL,
    updated_tx           BYTEA NOT NULL,
    updated_log          INT NOT NULL
);

CREATE TABLE IF NOT EXISTS season1_orders (
    order_id       NUMERIC PRIMARY KEY,
    ai_id          BYTEA NOT NULL,
    applicant      BYTEA NOT NULL,
    recipient      BYTEA NOT NULL,
    label          TEXT NOT NULL,
    tld            SMALLINT NOT NULL,
    tier           SMALLINT NOT NULL,
    day_index      BIGINT NOT NULL,
    price          NUMERIC NOT NULL,
    root           BYTEA NOT NULL,
    status         TEXT NOT NULL,
    mint_tx        BYTEA,
    token_id       NUMERIC,
    evidence_hash  BYTEA,
    refunded       BOOLEAN NOT NULL DEFAULT false,
    compensated    BOOLEAN NOT NULL DEFAULT false,
    block_number   BIGINT NOT NULL,
    tx_hash        BYTEA NOT NULL,
    tx_index       INT NOT NULL,
    log_index      INT NOT NULL
);
CREATE INDEX IF NOT EXISTS season1_orders_day ON season1_orders (day_index, order_id);

CREATE TABLE IF NOT EXISTS season1_verifications (
    ai_id           BYTEA NOT NULL,
    day_index       BIGINT NOT NULL,
    agent_id        NUMERIC NOT NULL,
    generation      INT NOT NULL,
    verdict         SMALLINT NOT NULL,
    task_pack_hash  BYTEA NOT NULL,
    points          INT NOT NULL,
    block_number    BIGINT NOT NULL,
    tx_hash         BYTEA NOT NULL,
    log_index       INT NOT NULL,
    PRIMARY KEY (ai_id, day_index)
);

CREATE TABLE IF NOT EXISTS season1_findings (
    report_evidence_hash BYTEA PRIMARY KEY,
    commit_hash          BYTEA,
    ai_id                BYTEA,
    committer            BYTEA,
    commit_block         BIGINT,
    tx_index             INT,
    log_index            INT,
    canonical_id         BYTEA,
    paid                 BOOLEAN NOT NULL DEFAULT false,
    withheld             BOOLEAN NOT NULL DEFAULT false,
    block_number         BIGINT NOT NULL
);

-- Report text a finding submitter published themselves (POST
-- /v1/season1/findings/{hash}/report). Verified server-side:
-- keccak256(content) must equal report_evidence_hash. Adoption/reason are
-- reviewer decisions and live elsewhere (findings.json on the website).
CREATE TABLE IF NOT EXISTS season1_finding_reports (
    report_evidence_hash BYTEA PRIMARY KEY,
    report_id            TEXT NOT NULL,
    title                TEXT NOT NULL,
    content              TEXT NOT NULL,
    published_at         BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS season1_task_packs (
    day_index       BIGINT PRIMARY KEY,
    task_pack_hash  BYTEA NOT NULL,
    block_number    BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS season1_entries (
    day_index  BIGINT NOT NULL,
    ai_id      BYTEA NOT NULL,
    balance    NUMERIC NOT NULL,
    tier       SMALLINT NOT NULL,
    PRIMARY KEY (day_index, ai_id)
);
ALTER TABLE season1_entries ADD COLUMN IF NOT EXISTS proof JSONB;

CREATE TABLE IF NOT EXISTS season1_validators (
    account      BYTEA PRIMARY KEY,
    allowed      BOOLEAN NOT NULL,
    block_number BIGINT NOT NULL,
    log_index    INT NOT NULL
);

CREATE TABLE IF NOT EXISTS season1_reward_signer (
    id           SMALLINT PRIMARY KEY,
    account      BYTEA,
    block_number BIGINT NOT NULL,
    log_index    INT NOT NULL
);

-- ===== Haha Dog (migrations/007_haha_dog.sql) =====
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
    seed_block    BIGINT,                  -- block at which the seed became known (informational)
    stalled       BOOLEAN NOT NULL DEFAULT FALSE -- on-chain status 3: hash unrecoverable, free reroll needed
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

-- Haha Dog approvals (2026-11-28): ERC-721 Approval / ApprovalForAll, so
-- /v1/dog/listings can tell whether a listing is actually buyable.
CREATE TABLE IF NOT EXISTS dog_approvals (
    token_id NUMERIC PRIMARY KEY,
    approved BYTEA NOT NULL
);
CREATE TABLE IF NOT EXISTS dog_operators (
    owner    BYTEA NOT NULL,
    operator BYTEA NOT NULL,
    approved BOOLEAN NOT NULL,
    PRIMARY KEY (owner, operator)
);;
