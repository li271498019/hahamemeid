-- Safe to run on a live V1 database. Adds lookup indexes only.
-- Does not rewrite rows, drop columns, or touch the checkpoint.
-- names.full_name is already UNIQUE. These two cover "my names" and label filters.

CREATE INDEX IF NOT EXISTS names_owner ON names (owner);
CREATE INDEX IF NOT EXISTS names_label ON names (label);
