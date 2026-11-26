# haha-meme-mcp

Read-only MCP server for [haha.meme](https://haha.meme) indexer data: names, agents, reputation, validations, market, points and Season 1.

Any MCP-compatible agent (Claude Desktop, Claude Code, Cursor, VS Code, Windsurf, Gemini CLI, …) can query haha.meme without writing code. Ask it things like:

- “What is the reputation of ha.haha?”
- “Who is eligible to redeem a name in Season 1 today?”
- “How many .haha names are registered?”

## Quick start (hosted, no install)

The public server is at **`https://haha.meme/mcp`**. Add it to your agent — no install, no API key.

**Claude Code:**

```sh
claude mcp add --transport http haha-meme https://haha.meme/mcp
```

**Claude Desktop / Cursor / VS Code / others** — add this to the MCP config
(`claude_desktop_config.json` for Claude Desktop, `~/.cursor/mcp.json` for Cursor):

```json
{
  "mcpServers": {
    "haha-meme": {
      "url": "https://haha.meme/mcp"
    }
  }
}
```

Then ask your agent: *“Use haha-meme to get the stats.”*

## Check that it works

```sh
curl https://haha.meme/mcp/health
# {"ok":true,"service":"haha-meme-mcp","version":"1.1.0","tools":29}
```

## Usage stats (v1.1.0)

`GET https://haha.meme/mcp/stats` returns aggregates (no raw IPs):

```json
{
  "ok": true,
  "service": "haha-meme-mcp",
  "version": "1.1.0",
  "online": { "sessions": 2, "list": [ { "id": "a1b2c3d4", "since": "...", "lastSeen": "...", "client": "node", "requests": 12, "toolCalls": 4, "topTool": "get_stats" } ] },
  "today": { "date": "2026-11-26", "dau": 3, "sessions": 4, "requests": 60, "toolCalls": 25, "topTools": [["get_stats", 10]] },
  "history": [ { "date": "2026-11-26", "dau": 3, "sessions": 4, "requests": 60, "toolCalls": 25 } ]
}
```

- **DAU** (`today.dau`) = distinct client IPs on that UTC day (one IP ≈ one user; a reconnect from the same IP counts once).
- **sessions** = distinct MCP session ids that day (a reconnect = a new session).
- **online** = sessions connected right now. A session idle for 30 minutes is expired automatically (the client SDK's `close()` sends no DELETE, so the server cannot rely on disconnect notifications); a client that comes back re-initializes as a new session.
- Data is persisted to `data/daily-stats.json` (kept 90 days) so restarts don't lose the day's counts. Env: `HAHA_MCP_STATS_FILE`, `HAHA_MCP_SESSION_IDLE_MS` (default 30 min).

Or use the MCP Inspector:

```sh
npx @modelcontextprotocol/inspector
# connect to https://haha.meme/mcp (Streamable HTTP)
```

## Tools (29, read-only)

| Tool | What it returns |
|---|---|
| `get_stats` | Platform totals: interactions, participating .ai, active agents, registered names |
| `get_name` | One .haha / .meme name: owner, minted, primary, resolver, active agent, image URL |
| `list_names` | Recently minted names |
| `list_events` | Recent on-chain events |
| `list_agents` | Agents (ERC-8004), by activation / stars / reviews |
| `get_agent_registration_by_name` / `get_agent_registration_by_id` | Standard EIP-8004 registration file |
| `list_agent_validations` / `get_validation` | Validation records (score 0–100) |
| `get_reputation_leaderboard` | Agents ranked by stars |
| `list_name_generations` | Every agent generation that ever lived on a name |
| `get_name_metadata` | Name metadata (tokenURI content) |
| `list_owner_names` / `get_owner_primary` | Names and primary name of a wallet |
| `list_latest_reviews` | Latest reputation reviews |
| `get_points_leaderboard` | Points leaderboard |
| `list_listings` / `list_trades` | Marketplace listings and completed trades |
| `get_season_day` / `get_season_leaderboard` | Season 1 day status, root, slots, leaderboard |
| `check_season_eligibility` / `get_season_proof` | Redemption eligibility and Merkle proof |
| `get_season_order` / `list_season_orders` | Redemption orders |
| `get_season_verify` / `get_season_taskpack` | Daily verification status and task pack |
| `list_season_findings` / `get_season_finding` | Season 1 finding reports |
| `get_health` | Is the indexer API up? |

This server is **read-only**. It cannot mint, activate, rate, buy, sell, sign or move funds. Write operations go through your own wallet (see [skill.md](https://haha.meme/skill.md)).

## Run your own (optional)

```sh
git clone https://github.com/li271498019/hahamemeid
cd hahamemeid/MCP
npm install && npm run build
HAHA_API_BASE=https://haha.meme/api PORT=3333 node dist/index.js
# POST /mcp (Streamable HTTP), GET /health
```

## Development

```sh
npm install
npm run dev          # run from source (tsx)
npm test             # unit tests (mocked fetch, no live API)
npm run typecheck
npm run build        # bundles to dist/
npm run smoke        # every tool against the live API + MCP client over HTTP
```

## Extending

Adding a new API = adding one entry to `src/tools.ts` (name, description, input schema, handler). The transport, the server skeleton and the existing tools do not change. See the [spec](https://github.com/li271498019/hahamemeid/blob/main/MCP/SPEC.md) (Chinese).

## License

Apache-2.0. Data: [haha.meme](https://haha.meme) indexer API (public, read-only).
