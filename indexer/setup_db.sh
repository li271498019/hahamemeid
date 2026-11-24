#!/bin/bash
# haha-indexer one-time DB setup. FRESH INSTALL ONLY.
#
# Creates role haha + databases haha_indexer / haha_indexer_test, and
# writes /etc/haha/indexer.env and /etc/haha/indexer-test.env (0600).
# The generated password is only ever written into those two files
# (never into a command line, never into a log).
#
# DANGER: with --reset this script DESTROYS the existing databases
# (pg_terminate_backend + DROP DATABASE) and rewrites the env files.
# Re-running it on a production machine wipes the indexed data; recovery
# is a full resync from block 134834631. NEVER run it casually.
#
#   (no flag)   fresh install only. If either database already exists,
#               the script refuses and exits. Use --reset to rebuild.
#   --reset     rebuild both databases. Requires an interactive terminal
#               and TWO confirmations: type `yes`, then type the database
#               name `haha_indexer`. A timestamped pg_dump backup is
#               taken first into /var/backups/haha-indexer/ (latest 3
#               kept per database); if the backup fails, nothing is
#               dropped.
#   --dry-run   print what would be done, change nothing.
#   --help, -h  print this help.
#
# Run as root on the server.
set -euo pipefail

BACKUP_DIR=/var/backups/haha-indexer
DEFAULT_RPC="https://bsc-dataseed.binance.org,https://bsc-dataseed1.defibit.io,https://bsc.publicnode.com"

usage() {
    sed -n '2,30p' "$0"
}

RESET=0
DRY_RUN=0
for arg in "$@"; do
    case "$arg" in
        --reset)   RESET=1 ;;
        --dry-run) DRY_RUN=1 ;;
        --help|-h) usage; exit 0 ;;
        *) echo "unknown argument: $arg" >&2; usage >&2; exit 2 ;;
    esac
done

db_exists() {
    # $1 = database name; prints 1 if it exists, 0 otherwise.
    sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$1'" | grep -q 1
}

existing_rpc() {
    # $1 = env file; prints its BSC_RPC_URLS value, or nothing if absent.
    if [ -f "$1" ]; then
        grep -E '^BSC_RPC_URLS=' "$1" | tail -n 1 | cut -d= -f2-
    fi
}

MAIN_EXISTS=0
TEST_EXISTS=0
db_exists haha_indexer && MAIN_EXISTS=1 || true
db_exists haha_indexer_test && TEST_EXISTS=1 || true

if [ "$DRY_RUN" = 1 ]; then
    if { [ "$MAIN_EXISTS" = 1 ] || [ "$TEST_EXISTS" = 1 ]; } && [ "$RESET" = 0 ]; then
        echo "DRY-RUN: databases already exist; the script would REFUSE (use --reset to rebuild)."
        exit 0
    fi
    if [ "$RESET" = 1 ]; then
        echo "DRY-RUN: would take pg_dump backups of haha_indexer + haha_indexer_test to $BACKUP_DIR (latest 3 kept),"
        echo "DRY-RUN: then terminate backends, DROP + CREATE both databases, rotate the haha role password,"
        echo "DRY-RUN: and rewrite /etc/haha/indexer.env + /etc/haha/indexer-test.env (0600, keeping any existing BSC_RPC_URLS)."
    else
        echo "DRY-RUN: would create role haha (if missing), CREATE DATABASE haha_indexer + haha_indexer_test OWNER haha,"
        echo "DRY-RUN: and write /etc/haha/indexer.env + /etc/haha/indexer-test.env (0600) with a fresh random password."
    fi
    echo "DRY-RUN: nothing was changed."
    exit 0
fi

# Default: refuse to re-run when a database already exists.
if { [ "$MAIN_EXISTS" = 1 ] || [ "$TEST_EXISTS" = 1 ]; } && [ "$RESET" = 0 ]; then
    echo "REFUSING: database haha_indexer and/or haha_indexer_test already exists." >&2
    echo "This script is for fresh installs only. To rebuild, run with --reset" >&2
    echo "(interactive terminal, two confirmations, backup taken first)." >&2
    exit 1
fi

if [ "$RESET" = 1 ]; then
    # --reset needs a real interactive terminal and two confirmations.
    if [ ! -t 0 ]; then
        echo "REFUSING: --reset needs an interactive terminal." >&2
        exit 1
    fi
    printf 'You are about to DESTROY and rebuild haha_indexer + haha_indexer_test.\n'
    printf 'Type yes to confirm: '
    read -r ans || exit 1
    if [ "$ans" != "yes" ]; then
        echo "Aborted: confirmation was not 'yes'." >&2
        exit 1
    fi
    printf 'Type the database name to confirm (haha_indexer): '
    read -r name || exit 1
    if [ "$name" != "haha_indexer" ]; then
        echo "Aborted: database name did not match." >&2
        exit 1
    fi
    # Backup first; a failed backup stops everything.
    mkdir -p "$BACKUP_DIR"
    chown postgres:postgres "$BACKUP_DIR"
    chmod 0700 "$BACKUP_DIR"
    TS=$(date +%Y%m%d-%H%M%S)
    for db in haha_indexer haha_indexer_test; do
        if ! sudo -u postgres pg_dump -Fc -d "$db" -f "$BACKUP_DIR/$db-$TS.dump"; then
            echo "Backup of $db failed; aborting, nothing was dropped." >&2
            exit 1
        fi
        # Keep only the latest 3 backups per database.
        ls -t "$BACKUP_DIR"/"$db"-*.dump 2>/dev/null | tail -n +4 | xargs -r rm -f
    done
    echo "Backups written to $BACKUP_DIR (latest 3 kept per database)."
fi

PW=$(openssl rand -hex 24)

# Set the role password via stdin, never on a command line (ps would show it).
if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='haha'" | grep -q 1; then
    printf "ALTER USER haha WITH PASSWORD '%s';\n" "$PW" | sudo -u postgres psql -v ON_ERROR_STOP=1 -q
else
    printf "CREATE USER haha WITH PASSWORD '%s';\n" "$PW" | sudo -u postgres psql -v ON_ERROR_STOP=1 -q
fi

if [ "$RESET" = 1 ]; then
    sudo -u postgres psql -v ON_ERROR_STOP=1 -q <<'SQL'
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname IN ('haha_indexer','haha_indexer_test') AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS haha_indexer;
DROP DATABASE IF EXISTS haha_indexer_test;
CREATE DATABASE haha_indexer OWNER haha;
CREATE DATABASE haha_indexer_test OWNER haha;
SQL
else
    sudo -u postgres psql -v ON_ERROR_STOP=1 -q <<'SQL'
CREATE DATABASE haha_indexer OWNER haha;
CREATE DATABASE haha_indexer_test OWNER haha;
SQL
fi

# Rewrite the env files, keeping any existing BSC_RPC_URLS; only a fresh
# install gets the default 3 public nodes.
RPC_MAIN=$(existing_rpc /etc/haha/indexer.env)
[ -n "$RPC_MAIN" ] || RPC_MAIN="$DEFAULT_RPC"
RPC_TEST=$(existing_rpc /etc/haha/indexer-test.env)
[ -n "$RPC_TEST" ] || RPC_TEST="$DEFAULT_RPC"
printf 'DATABASE_URL=postgresql://haha:%s@127.0.0.1:5432/haha_indexer\nBSC_RPC_URLS=%s\n' "$PW" "$RPC_MAIN" > /etc/haha/indexer.env
printf 'DATABASE_URL=postgresql://haha:%s@127.0.0.1:5432/haha_indexer_test\nBSC_RPC_URLS=%s\n' "$PW" "$RPC_TEST" > /etc/haha/indexer-test.env
chown haha:haha /etc/haha/indexer.env /etc/haha/indexer-test.env
chmod 0600 /etc/haha/indexer.env /etc/haha/indexer-test.env
echo SETUP_DONE
