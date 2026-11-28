# haha-agent-chat

Channel service for the haha agent dialog (agent page `agent.html`).
Frozen spec v1.0: `~/workspace/haha-agent-channel-spec-frozen-v1.md` (889 lines).
The spec is the sole authority; no behaviour beyond it is implemented.

## Stack

Node.js (>=20) + `pg` + `js-sha3`. No web framework (built-in `http`).
Why Node: the server already runs Node 22 and the MCP service on the same
runtime; async I/O fits a high-concurrency queue service; only two small
dependencies are needed.

## Layout (server)

- Code: `/opt/haha-agent-chat/` (User `haha`), `server.js` + `persona.js`.
- Env (secrets): `/etc/haha/agent-chat.env` (0600, root). Holds
  `CHANNEL_API_KEY`, `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`,
  `PGPASSWORD`, `INDEXER_API_BASE`, `IMAGE_DIR`, `PUBLIC_BASE_URL`.
  The Bearer key is generated with a cryptographic RNG (32 bytes) and
  lives ONLY in that file. It never enters code, repo, chat or logs.
- systemd: `haha-agent-chat` (enabled, restart on failure).
- nginx: `location /agent-chat/` proxies to `127.0.0.1:8899`
  (prefix stripped by the trailing slash in `proxy_pass`).
- Images: `/var/www/haha.meme/agent-images/` (NOT served by nginx
  directly; only via `GET /images/{imageId}`).

## Endpoints (spec §5)

- `GET /health` — 200 `{"ok": true}` when Postgres is reachable, else 503.
- `POST /questions` — submit a question (`type` `chat`|`save`).
- `GET /questions/pending` — Bearer only; up to 50 queued questions.
- `POST /answers` — Bearer only; write an answer (+ memory / images).
- `GET /questions/{questionId}` — poll one question's status/answer.
- `GET /history/{agentId}?aiId=...` — chat history (owner-checked).
- `GET /images/{imageId}` — serve a stored image (3-day retention).

## Key numbers (frozen)

- Poll: agent 1s, website 1s. Target: seconds; hard timeout 60s.
- Submit limit: 1 per 5s per agent, no total cap.
- Image fetch: 60/min per IP. Image: max 1 per answer, base64 <= 20MB,
  png/jpeg only, stored 3 days. Chat history: 30 days.
- Burned agent (transfer/burn): memory + records deleted immediately.
  (Spec §14.5 still says "burned over 30 days ago" — stale text; §14.1
  and §10.4, both locked, say delete immediately. Immediate wins.)

## Identity (L 2026-11-27, locked)

The answering AI calls itself "haha agent" and addresses the user by the
user's REAL domain (.haha or .meme). The example domain from the spec is
NEVER hardcoded: `persona.js` uses `{name}` / `{agentId}` placeholders,
substituted with the real values when the `agent_memory` row is created,
and `server.js` contains no literal example domain (grep-verified).

## Owner verification (spec §8, fail-closed)

- `aiId` -> address: indexer `handle_cache` table (aiId is the keccak256
  of the handle WITHOUT the ".ai" suffix), cached in memory, refreshed
  every 10 min and on miss. No indexer HTTP endpoint exists for this.
- name -> owner: indexer read-only HTTP API `GET /v1/names/{name}`.
- Any failure -> 403 `not_owner`. Operator is not the owner -> 403.

## Cleanup

Built into the service (no separate cron):
- Timeout sweeper every 10s: mark `queued` questions older than 60s as
  `timeout` (plus lazy evaluation on read).
- Daily cleanup at 00:00 UTC: delete 30-day-old chat history and question
  rows, 3-day-old images (rows + files), and all records of burned agents.

## Deploy

1. `rsync -a` the project dir to `/opt/haha-agent-chat/` (no tar, no
   `rsync --delete` across multiple sources).
2. `npm ci --omit=dev` (or `npm install --omit=dev`) in `/opt/haha-agent-chat`.
3. Create tables: `sudo -u haha psql -d haha_indexer -f schema.sql`.
4. Write `/etc/haha/agent-chat.env` (0600, root) with the Bearer key and
   DB credentials. Generate the key with `node -e` + `crypto.randomBytes`.
5. Install the systemd unit, `systemctl daemon-reload`, enable + start.
6. Add the nginx `location /agent-chat/` block, `nginx -t`, reload.
7. Run `test-e2e.sh` (needs `CHANNEL_API_KEY` exported) and verify all
   steps pass.
