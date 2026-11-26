#!/bin/bash
# Deploy haha-meme-mcp to the Vultr server.
# Idempotent: safe to re-run. Run as root on the server.
# Source is rsynced in by the caller (see deploy-mcp.sh wrapper) or
# already present in /opt/haha-mcp.
set -euo pipefail
# 用法：先 export SERVER_IP=<你的服务器 IP>（不要把真实 IP 写进仓库）
SERVER_IP="${SERVER_IP:-}"

APP=/opt/haha-mcp
UNIT=/etc/systemd/system/haha-mcp.service
NGINX_SITE=/etc/nginx/sites-enabled/haha.meme
RATE_LIMIT=/etc/nginx/conf.d/rate-limit.conf

echo "== 1. app dir =="
mkdir -p "$APP"
# Recursive: rsync lands as root; haha must own every file (npm reads/writes
# package-lock.json, node_modules, dist).
chown -R haha:haha "$APP"
# Stats dir (v1.1.0): daily-stats.json lives here; haha must be able to write.
mkdir -p "$APP/data"
chown haha:haha "$APP/data"
chmod 750 "$APP/data"

echo "== 2. npm install + build (as haha) =="
cd "$APP"
sudo -u haha npm install --no-audit --no-fund
sudo -u haha npm run build
echo "node version: $(node --version)"

echo "== 3. systemd unit =="
cat > "$UNIT" <<'EOF'
[Unit]
Description=haha.meme MCP server (read-only indexer API)
After=network-online.target haha-api.service
Wants=network-online.target

[Service]
Type=simple
User=haha
Group=haha
WorkingDirectory=/opt/haha-mcp
Environment=HAHA_API_BASE=http://127.0.0.1:8787
Environment=HOST=127.0.0.1
Environment=PORT=3333
Environment=NODE_ENV=production
ExecStart=/usr/bin/node /opt/haha-mcp/dist/index.js
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable haha-mcp
systemctl restart haha-mcp
sleep 2
systemctl status haha-mcp --no-pager | head -6
curl -fsS http://127.0.0.1:3333/health && echo " <- local /health OK"

echo "== 4. nginx rate-limit zone =="
if ! grep -q 'zone=mcp:' "$RATE_LIMIT"; then
  printf 'limit_req_zone $binary_remote_addr zone=mcp:10m rate=120r/m;\n' >> "$RATE_LIMIT"
  echo "added mcp zone"
else
  echo "mcp zone already present"
fi

echo "== 5. nginx location /mcp =="
if ! grep -q 'location /mcp' "$NGINX_SITE"; then
  python3 - "$NGINX_SITE" <<'PYEOF'
import sys
path = sys.argv[1]
block = '''  location /mcp {
    # MCP Server (2026-11-26, C): Streamable HTTP, hosted. SSE responses must
    # not be buffered; sessions are stateful (mcp-session-id).
    limit_req zone=mcp burst=20 nodelay;
    limit_req_status 429;
    limit_req_log_level warn;
    limit_conn conn 20;
    client_max_body_size 256k;
    add_header Retry-After 60 always;
    include /etc/nginx/snippets/security-headers-haha.conf;
    proxy_pass http://127.0.0.1:3333;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_buffering off;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
  }

'''
with open(path) as f:
    text = f.read()
anchor = "  location / {\n"
assert anchor in text, "anchor 'location / {' not found"
assert "location /mcp" not in text, "location /mcp already present"
text = text.replace(anchor, block + anchor, 1)
with open(path, "w") as f:
    f.write(text)
print("inserted location /mcp")
PYEOF
else
  echo "location /mcp already present"
fi

echo "== 6. nginx test + reload =="
nginx -t
systemctl reload nginx
echo "nginx reloaded"

echo "== 7. verify public endpoint =="
sleep 1
curl -fsS https://haha.meme/mcp/health && echo " <- public /mcp/health OK"
curl -fsS https://haha.meme/mcp/stats | head -c 400 && echo "" && echo " <- public /mcp/stats OK"
echo "DEPLOY DONE"
