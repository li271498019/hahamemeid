#!/bin/bash
# One-time DB setup for haha-indexer. Run as root on the server.
# Creates role haha + databases haha_indexer / haha_indexer_test,
# writes /etc/haha/indexer.env and indexer-test.env (0600).
# The generated password is only ever written into those two files.
set -euo pipefail
PW=$(openssl rand -hex 24)
export PW
if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='haha'" | grep -q 1; then
  sudo -u postgres psql -v ON_ERROR_STOP=1 -c "ALTER USER haha WITH PASSWORD '$PW'"
else
  sudo -u postgres psql -v ON_ERROR_STOP=1 -c "CREATE USER haha WITH PASSWORD '$PW'"
fi
sudo -u postgres psql -v ON_ERROR_STOP=1 <<'SQL'
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname IN ('haha_indexer','haha_indexer_test') AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS haha_indexer;
DROP DATABASE IF EXISTS haha_indexer_test;
CREATE DATABASE haha_indexer OWNER haha;
CREATE DATABASE haha_indexer_test OWNER haha;
SQL
printf 'DATABASE_URL=postgresql://haha:%s@127.0.0.1:5432/haha_indexer\nBSC_RPC_URLS=https://bsc-dataseed.binance.org,https://bsc-dataseed1.defibit.io,https://bsc.publicnode.com\n' "$PW" > /etc/haha/indexer.env
printf 'DATABASE_URL=postgresql://haha:%s@127.0.0.1:5432/haha_indexer_test\nBSC_RPC_URLS=https://bsc-dataseed.binance.org,https://bsc-dataseed1.defibit.io,https://bsc.publicnode.com\n' "$PW" > /etc/haha/indexer-test.env
chown haha:haha /etc/haha/indexer.env /etc/haha/indexer-test.env
chmod 0600 /etc/haha/indexer.env /etc/haha/indexer-test.env
echo SETUP_DONE
