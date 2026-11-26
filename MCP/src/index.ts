// haha-meme-mcp: read-only MCP server for haha.meme indexer data.
// Transport: Streamable HTTP, STATEFUL sessions.
// Each client session gets its own transport + server, kept in a map
// keyed by the MCP session id (standard hosted-MCP pattern).
// The server only answers read queries against the public indexer API;
// it never signs, never trades, never moves funds.
//
// Run:  HAHA_API_BASE=http://127.0.0.1:8787 PORT=3333 node dist/index.js
// Env:   HAHA_API_BASE (default https://haha.meme/api)
//        HOST (default 127.0.0.1), PORT (default 3333)

import http from "node:http";
import { randomUUID } from "node:crypto";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { TOOLS } from "./tools.js";

export const SERVICE = "haha-meme-mcp";
export const VERSION = "1.0.0";

function buildServer(): McpServer {
  const server = new McpServer({ name: SERVICE, version: VERSION });
  for (const t of TOOLS) {
    server.registerTool(
      t.name,
      { description: t.description, inputSchema: t.inputSchema },
      async (args: Record<string, unknown>) => {
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

// One transport + server per client session.
const sessions = new Map<string, StreamableHTTPServerTransport>();

function getSessionId(req: http.IncomingMessage): string | undefined {
  const v = req.headers["mcp-session-id"];
  return Array.isArray(v) ? v[0] : v;
}

async function handleMcp(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
  const sessionId = getSessionId(req);
  let transport = sessionId ? sessions.get(sessionId) : undefined;

  if (!transport) {
    if (req.method !== "POST") {
      // GET/DELETE need an established session.
      res.writeHead(404, { "content-type": "application/json" });
      res.end(JSON.stringify({ error: "session_not_found" }));
      return;
    }
    // New session (initialize request): fresh transport + server.
    transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: () => randomUUID(),
      onsessioninitialized: (sid) => {
        sessions.set(sid, transport!);
      },
    });
    transport.onclose = () => {
      const sid = transport!.sessionId;
      if (sid) sessions.delete(sid);
    };
    const server = buildServer();
    await server.connect(transport);
  }

  let body: unknown;
  if (req.method === "POST") body = await readJsonBody(req);
  await transport.handleRequest(req, res, body);

  // Fallback: if the session id was assigned but onsessioninitialized
  // did not fire (ordering), store it now.
  const sid = transport.sessionId;
  if (sid && !sessions.has(sid)) sessions.set(sid, transport);
}

async function main(): Promise<void> {
  const host = process.env.HOST ?? "127.0.0.1";
  const port = Number(process.env.PORT ?? 3333);

  const httpServer = http.createServer(async (req, res) => {
    try {
      const url = new URL(req.url ?? "/", `http://${req.headers.host ?? "127.0.0.1"}`);
      if (url.pathname === "/mcp") {
        await handleMcp(req, res);
        return;
      }
      if (req.method === "GET" && url.pathname === "/health") {
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
    console.error(`[${SERVICE}] v${VERSION} listening on ${host}:${port} (POST/GET/DELETE /mcp, GET /health, ${TOOLS.length} tools)`);
  });
}

main().catch((e) => {
  console.error(`[${SERVICE}] fatal:`, e);
  process.exit(1);
});
