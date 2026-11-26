#!/bin/bash
# Deploy the MCP direct-connect change (remove `claude mcp add`, add
# "请连接数据源接口：https://haha.meme/mcp" to the instruction shell + MCP blocks).
# skill.md v21. Idempotent: safe to re-run. Run as root on the server.
# The new release dir is created by cp -a from the CURRENT live release
# (never from an old release, never tar -C .).
# Changed files are rsynced in by the caller before running this script.
set -euo pipefail
# 用法：先 export SERVER_IP=<你的服务器 IP>（不要把真实 IP 写进仓库）
SERVER_IP="${SERVER_IP:-}"

EXPECTED_SKILL_SHA=cbf4d9657ce941c3dc0c37c6cec25c0c05fcd1df8bdc3b24f2b78cb772da0e9b
LIVE_LINK=/var/www/haha.meme
RELEASES=/var/www/releases

echo "== 1. current live release =="
CURRENT=$(readlink "$LIVE_LINK")
echo "live -> $CURRENT"
[ -n "$CURRENT" ] || { echo "FAIL: no live symlink"; exit 1; }

echo "== 2. new release dir from current live (cp -a) =="
if [ "${1:-}" != "" ]; then
  NEW="$1"
  [ -d "$NEW" ] || { echo "FAIL: given release dir $NEW does not exist"; exit 1; }
  echo "using given release dir $NEW"
else
  TS=$(date +%Y%m%d-%H%M%S)
  NEW="$RELEASES/$TS-mcp-direct-connect"
  if [ -d "$NEW" ]; then
    echo "release dir $NEW already exists, reusing (idempotent)"
  else
    cp -a "$CURRENT" "$NEW"
    echo "created $NEW from $CURRENT"
  fi
fi

echo "== 3. verify changed files are in the new release =="
for f in how.html api.html skill.md js/i18n.js js/instructions.js agent.html earn.html erc8004.html index.html market.html scan.html season-checklist.html season.html; do
  [ -f "$NEW/$f" ] || { echo "FAIL: $NEW/$f missing (rsync the 13 files first)"; exit 1; }
done
# instructions.js v12 in all 10 HTML files that load it
for f in how.html api.html agent.html earn.html erc8004.html index.html market.html scan.html season-checklist.html season.html; do
  grep -q 'instructions.js?v=12' "$NEW/$f" || { echo "FAIL: instructions v12 missing in $f"; exit 1; }
done
# i18n.js v64 in how/api
grep -q 'i18n.js?v=64' "$NEW/how.html" || { echo "FAIL: i18n v64 missing in how.html"; exit 1; }
grep -q 'i18n.js?v=64' "$NEW/api.html" || { echo "FAIL: i18n v64 missing in api.html"; exit 1; }
# MCP direct instruction present, claude mcp add gone
grep -q '请连接数据源接口：https://haha.meme/mcp' "$NEW/how.html" || { echo "FAIL: direct MCP instruction missing in how.html"; exit 1; }
grep -q '请连接数据源接口：https://haha.meme/mcp' "$NEW/api.html" || { echo "FAIL: direct MCP instruction missing in api.html"; exit 1; }
grep -q '请连接数据源接口：https://haha.meme/mcp' "$NEW/skill.md" || { echo "FAIL: direct MCP instruction missing in skill.md"; exit 1; }
grep -q '然后请连接数据源接口' "$NEW/js/instructions.js" || { echo "FAIL: MCP connect line missing in instructions.js"; exit 1; }
grep -q 'MCP_URL = "https://haha.meme/mcp"' "$NEW/js/instructions.js" || { echo "FAIL: MCP_URL missing in instructions.js"; exit 1; }
for f in how.html api.html skill.md js/instructions.js js/i18n.js; do
  if grep -q 'claude mcp add' "$NEW/$f"; then echo "FAIL: claude mcp add still in $f"; exit 1; fi
done
REL_SHA=$(sha256sum "$NEW/skill.md" | awk '{print $1}')
echo "skill.md sha256 release=$REL_SHA (expect $EXPECTED_SKILL_SHA)"
[ "$REL_SHA" = "$EXPECTED_SKILL_SHA" ] || { echo "FAIL: skill.md in release differs from expected v21 hash — refusing to flip"; exit 1; }
echo "all pre-flip checks passed"

echo "== 4. permissions (explicit, no --reference) =="
chown -R root:www-data "$NEW"
find "$NEW" -type d -exec chmod 755 {} +
find "$NEW" -type f -exec chmod 644 {} +

echo "== 5. flip symlink =="
ln -sfn "$NEW" "$LIVE_LINK"
echo "live -> $(readlink $LIVE_LINK)"

echo "== 6. verify live =="
# NOTE: never `curl | grep -q` under `set -o pipefail`: download to files first, then grep.
LIVE_SHA=$(sha256sum "$LIVE_LINK/skill.md" | awk '{print $1}')
echo "skill.md sha256 live=$LIVE_SHA (expect $EXPECTED_SKILL_SHA)"
[ "$LIVE_SHA" = "$EXPECTED_SKILL_SHA" ] || { echo "FAIL: live skill.md differs from expected v21 hash after flip"; exit 1; }
curl -fsS "https://haha.meme/how.html" -o /tmp/verify-how.html
curl -fsS "https://haha.meme/skill.md" -o /tmp/verify-skill.md
curl -fsS "https://haha.meme/js/instructions.js" -o /tmp/verify-instructions.js
grep -q 'version: 21' /tmp/verify-skill.md || { echo "FAIL: live skill.md is not v21"; exit 1; }
grep -q '请连接数据源接口：https://haha.meme/mcp' /tmp/verify-how.html || { echo "FAIL: live how.html has no direct MCP instruction"; exit 1; }
grep -q '请连接数据源接口：https://haha.meme/mcp' /tmp/verify-skill.md || { echo "FAIL: live skill.md has no direct MCP instruction"; exit 1; }
grep -q '然后请连接数据源接口' /tmp/verify-instructions.js || { echo "FAIL: live instructions.js has no MCP connect line"; exit 1; }
grep -q 'MCP_URL = "https://haha.meme/mcp"' /tmp/verify-instructions.js || { echo "FAIL: live instructions.js has no MCP_URL"; exit 1; }
if grep -q 'claude mcp add' /tmp/verify-how.html /tmp/verify-skill.md; then echo "FAIL: live still has claude mcp add"; exit 1; fi
echo "live checks passed"
echo "DEPLOY DONE: $NEW"
