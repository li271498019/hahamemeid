// haha-meme-mcp: read-only MCP server for haha.meme indexer data.
// Transport: Streamable HTTP, STATEFUL sessions.
// Each client session gets its own transport + server, kept in a map
// keyed by the MCP session id (standard hosted-MCP pattern).
// The server only answers read queries against the public indexer API;
// it never signs, never trades, never moves funds.
//
// Usage stats (v1.1.0): every session is tracked (IP, client, tool calls)
// and persisted to a daily-stats JSON file, so daily active users (DAU =
// distinct client IPs per UTC day) survive restarts. Aggregates are served
// at GET /stats (public, no raw IPs); the file stays on the server.
//
// Run:  HAHA_API_BASE=http://127.0.0.1:8787 PORT=3333 node dist/index.js
// Env:   HAHA_API_BASE (default https://haha.meme/api)
//        HOST (default 127.0.0.1), PORT (default 3333)
//        HAHA_MCP_STATS_FILE (default data/daily-stats.json under cwd)

import http from "node:http";
import { randomUUID } from "node:crypto";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { TOOLS } from "./tools.js";
import {
  StatsStore,
  summarizeSession,
  type SessionInfo,
} from "./stats.js";

export const SERVICE = "haha-meme-mcp";
export const VERSION = "1.1.0";

const STATS_FILE =
  process.env.HAHA_MCP_STATS_FILE ?? "data/daily-stats.json";
const stats = new StatsStore(STATS_FILE);

// Idle-session expiry: the client SDK's close() does NOT send a DELETE, so a
// client that just disconnects never tells the server. Without expiry the
// "online" count would only grow. A session idle longer than this is dropped
// (a client that comes back re-initializes as a new session; DAU is by IP,
// so a reconnect from the same IP does not inflate it).
const SESSION_IDLE_MS = Number(
  process.env.HAHA_MCP_SESSION_IDLE_MS ?? 30 * 60 * 1000,
);

function buildServer(onToolCall: (tool: string) => void): McpServer {
  const server = new McpServer({ name: SERVICE, version: VERSION });
  for (const t of TOOLS) {
    server.registerTool(
      t.name,
      { description: t.description, inputSchema: t.inputSchema },
      async (args: Record<string, unknown>) => {
        onToolCall(t.name);
        try {
          const data = await t.run(args ?? {});
          const text = typeof data === "string" ? data : JSON.stringify(data);
          return { content: [{ type: "text" as const, text }] };
        } catch (e) {
          const msg = e instanceof Error ? e.message : String(e);
          return {
            content: [{ type: "text" as const, text: `Error: ${msg}` }],
            isError: true,
          };
        }
      },
    );
  }
  return server;
}

async function readJsonBody(req: http.IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = [];
  for await (const chunk of req) chunks.push(chunk as Buffer);
  if (chunks.length === 0) return undefined;
  const raw = Buffer.concat(chunks).toString("utf-8");
  if (!raw.trim()) return undefined;
  return JSON.parse(raw);
}

// Client IP: nginx sets X-Real-IP (Cloudflare real-IP is configured, so it
// is the true client IP, not the edge IP). Fall back to X-Forwarded-For.
function clientIp(req: http.IncomingMessage): string {
  const real = req.headers["x-real-ip"];
  if (typeof real === "string" && real) return real;
  const fwd = req.headers["x-forwarded-for"];
  if (typeof fwd === "string" && fwd) return fwd.split(",")[0].trim();
  if (Array.isArray(fwd) && fwd.length) return fwd[0].split(",")[0].trim();
  return req.socket.remoteAddress ?? "unknown";
}

// One transport + server per client session, plus its usage info.
// `closed` is set by onclose so the post-request fallback never re-adds a
// session that was just terminated (e.g. by a client DELETE).
interface SessionEntry {
  transport: StreamableHTTPServerTransport;
  info: SessionInfo;
  closed: boolean;
}
const sessions = new Map<string, SessionEntry>();

// Drop sessions idle longer than SESSION_IDLE_MS. Runs every 60 s.
function startSessionSweeper(): void {
  const timer = setInterval(() => {
    const now = Date.now();
    for (const [id, entry] of sessions) {
      const idleMs = now - new Date(entry.info.lastSeenAt).getTime();
      if (idleMs > SESSION_IDLE_MS) {
        sessions.delete(id);
        try {
          void entry.transport.close();
        } catch {
          // Already closed; nothing to clean up.
        }
        console.error(
          `[${SERVICE}] session expired id=${id.slice(0, 8)} idle=${Math.round(idleMs / 1000)}s requests=${entry.info.requests} toolCalls=${entry.info.toolCalls}`,
        );
      }
    }
  }, 60 * 1000);
  timer.unref();
}

function getSessionId(req: http.IncomingMessage): string | undefined {
  const v = req.headers["mcp-session-id"];
  return Array.isArray(v) ? v[0] : v;
}

async function handleMcp(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
  const sessionId = getSessionId(req);
  let entry = sessionId ? sessions.get(sessionId) : undefined;
  let transport = entry?.transport;

  if (!transport) {
    if (req.method !== "POST") {
      // GET/DELETE need an established session.
      res.writeHead(404, { "content-type": "application/json" });
      res.end(JSON.stringify({ error: "session_not_found" }));
      return;
    }
    // New session (initialize request): fresh transport + server.
    // Pre-generate the session id so the info object knows it from the start.
    const sid = randomUUID();
    const now = new Date().toISOString();
    const info: SessionInfo = {
      id: sid,
      createdAt: now,
      lastSeenAt: now,
      ip: clientIp(req),
      userAgent:
        typeof req.headers["user-agent"] === "string"
          ? req.headers["user-agent"]
          : "",
      requests: 0,
      toolCalls: 0,
      tools: {},
    };
    const newEntry: SessionEntry = {
      transport: null as unknown as StreamableHTTPServerTransport,
      info,
      closed: false,
    };
    transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: () => sid,
      onsessioninitialized: (id) => {
        if (!sessions.has(id)) sessions.set(id, newEntry);
      },
    });
    newEntry.transport = transport;
    transport.onclose = () => {
      const id = transport!.sessionId ?? sid;
      newEntry.closed = true;
      const e = sessions.get(id);
      if (e) {
        sessions.delete(id);
        const dur = Math.round(
          (Date.now() - new Date(e.info.createdAt).getTime()) / 1000,
        );
        console.error(
          `[${SERVICE}] session close id=${id.slice(0, 8)} duration=${dur}s requests=${e.info.requests} toolCalls=${e.info.toolCalls}`,
        );
      }
    };
    const server = buildServer((tool) => {
      info.toolCalls += 1;
      info.tools[tool] = (info.tools[tool] ?? 0) + 1;
      info.lastSeenAt = new Date().toISOString();
      stats.recordToolCall(info, tool);
    });
    await server.connect(transport);
    sessions.set(sid, newEntry);
    stats.recordSessionOpen(info);
    console.error(
      `[${SERVICE}] session open id=${sid.slice(0, 8)} ip=${info.ip} client=${(info.userAgent || "unknown").slice(0, 80)}`,
    );
    entry = newEntry;
  }

  // Count this request against the session.
  entry!.info.requests += 1;
  entry!.info.lastSeenAt = new Date().toISOString();
  stats.recordRequest(entry!.info);

  let body: unknown;
  if (req.method === "POST") body = await readJsonBody(req);
  await transport.handleRequest(req, res, body);

  // Fallback: if the session id was assigned but onsessioninitialized
  // did not fire (ordering), store it now. Never re-add a session that
  // this request just closed (e.g. a client DELETE).
  const sid = transport.sessionId;
  if (sid && !sessions.has(sid) && !entry!.closed) {
    sessions.set(sid, entry!);
  }
}

function statsPayload(): Record<string, unknown> {
  return {
    ok: true,
    service: SERVICE,
    version: VERSION,
    now: new Date().toISOString(),
    // A session counts as online while it has been seen within the idle
    // timeout; idle sessions are swept every 60 s.
    sessionIdleMs: SESSION_IDLE_MS,
    online: {
      sessions: sessions.size,
      list: [...sessions.values()].map((e) => summarizeSession(e.info)),
    },
    today: stats.today(),
    history: stats.history(),
  };
}

async function main(): Promise<void> {
  const host = process.env.HOST ?? "127.0.0.1";
  const port = Number(process.env.PORT ?? 3333);
  startSessionSweeper();

  const httpServer = http.createServer(async (req, res) => {
    try {
      const url = new URL(req.url ?? "/", `http://${req.headers.host ?? "127.0.0.1"}`);
      if (url.pathname === "/mcp") {
        await handleMcp(req, res);
        return;
      }
      if (req.method === "GET" && (url.pathname === "/health" || url.pathname === "/mcp/health")) {
        // /mcp/health: nginx proxies the full /mcp prefix through, so the
        // public health URL arrives as /mcp/health. Accept both.
        res.writeHead(200, { "content-type": "application/json" });
        res.end(
          JSON.stringify({
            ok: true,
            service: SERVICE,
            version: VERSION,
            tools: TOOLS.length,
            sessions: sessions.size,
          }),
        );
        return;
      }
      if (req.method === "GET" && (url.pathname === "/stats" || url.pathname === "/mcp/stats")) {
        // Public usage stats: online sessions, today's DAU, history.
        // Aggregates only — no raw IPs or full session ids.
        res.writeHead(200, { "content-type": "application/json" });
        res.end(JSON.stringify(statsPayload()));
        return;
      }
      res.writeHead(404, { "content-type": "application/json" });
      res.end(JSON.stringify({ error: "not_found" }));
    } catch (e) {
      console.error(`[${SERVICE}] request error:`, e instanceof Error ? e.message : e);
      if (!res.headersSent) {
        res.writeHead(500, { "content-type": "application/json" });
      }
      res.end(JSON.stringify({ error: "internal", message: e instanceof Error ? e.message : String(e) }));
    }
  });

  httpServer.listen(port, host, () => {
    console.error(`[${SERVICE}] v${VERSION} listening on ${host}:${port} (POST/GET/DELETE /mcp, GET /health, GET /stats, ${TOOLS.length} tools)`);
  });
}

main().catch((e) => {
  console.error(`[${SERVICE}] fatal:`, e);
  process.exit(1);
});
