-- Signer rotation tables. Does not rewrite orders, reviews, or checkpoint.

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
