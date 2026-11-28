#!/bin/bash
# Server-side setup for haha-agent-chat. Run as root.
# Generates the Bearer key, wires DB credentials from indexer.env,
# creates tables, installs the systemd unit. Secrets are never printed.
set -euo pipefail

APP=/opt/haha-agent-chat
ENV_FILE=/etc/haha/agent-chat.env
IMG_DIR=/var/www/haha.meme/agent-images

echo "== 1. ownership + npm install =="
chown -R haha:haha "$APP"
cd "$APP"
sudo -u haha npm ci --omit=dev --no-audit --no-fund 2>&1 | tail -2
node --check server.js && node --check persona.js && echo "syntax OK"

echo "== 2. create tables =="
sudo -u haha psql -d haha_indexer -v ON_ERROR_STOP=1 -f "$APP/schema.sql"

echo "== 3. image dir =="
mkdir -p "$IMG_DIR"
chown haha:haha "$IMG_DIR"
chmod 755 "$IMG_DIR"

echo "== 4. env file (Bearer key + DB creds) =="
# Read DATABASE_URL from the indexer env (0600, root-only) without printing it.
# Format: postgres://user:password@host:port/database
set -a
# shellcheck disable=SC1091
source /etc/haha/indexer.env
set +a
DB_URL="${DATABASE_URL:-}"
[ -n "$DB_URL" ] || { echo "FATAL: DATABASE_URL not found in indexer.env"; exit 1; }
# Parse without echoing: strip scheme, split user:pass@host:port/db.
REST="${DB_URL#*://}"
USERPASS="${REST%%@*}"
HOSTPORT_DB="${REST#*@}"
PGUSER="${USERPASS%%:*}"
PGPASSWORD="${USERPASS#*:}"
HOSTPORT="${HOSTPORT_DB%%/*}"
PGDATABASE="${HOSTPORT_DB#*/}"
PGHOST="${HOSTPORT%%:*}"
PGPORT="${HOSTPORT#*:}"
[ "$PGHOST" = "$HOSTPORT" ] && PGPORT=5432
[ -n "$PGPASSWORD" ] || { echo "FATAL: could not parse DATABASE_URL"; exit 1; }

# Generate the Bearer key (32 bytes, crypto RNG, base64url). Never printed.
CHANNEL_API_KEY=$(node -e "console.log(require('crypto').randomBytes(32).toString('base64url'))")

# Write the env file (0600, root). No secret is echoed anywhere.
umask 077
cat > "$ENV_FILE" <<EOF
CHANNEL_API_KEY=$CHANNEL_API_KEY
PGHOST=$PGHOST
PGPORT=$PGPORT
PGDATABASE=$PGDATABASE
PGUSER=$PGUSER
PGPASSWORD=$PGPASSWORD
INDEXER_API_BASE=http://127.0.0.1:8787
IMAGE_DIR=$IMG_DIR
PUBLIC_BASE_URL=https://haha.meme/agent-chat
EOF
chmod 600 "$ENV_FILE"
chown root:root "$ENV_FILE"
echo "env file written: $ENV_FILE (0600, key length ${#CHANNEL_API_KEY} chars)"

echo "== 5. systemd unit =="
cp "$APP/haha-agent-chat.service" /etc/systemd/system/haha-agent-chat.service
systemctl daemon-reload
systemctl enable haha-agent-chat.service
systemctl restart haha-agent-chat.service
sleep 3
systemctl status haha-agent-chat.service --no-pager | head -12
echo "== 6. listening? =="
(ss -ltnp 2>/dev/null || netstat -ltnp 2>/dev/null) | grep 8899 || echo "port 8899 NOT listening"
echo "== 7. health (local) =="
curl -s -m 5 http://127.0.0.1:8899/health; echo
echo "SETUP DONE"
