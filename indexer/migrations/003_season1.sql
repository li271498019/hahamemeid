-- Season 1 derived tables. Keys are chain ids. Safe on a live V1 database:
-- creates missing tables only, does not rewrite reviews, names, or checkpoint.

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
