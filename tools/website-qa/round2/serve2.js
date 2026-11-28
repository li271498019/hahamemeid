// Round 2 preview server. Static site, /rpc/ and /rpc-bsc/ -> official BSC node, /api/* -> API_PORT (local indexer API on the scratch DB)
// or, with API=none, a 404; with API=mock, MOCK_FILE (json map path -> body) is served.
const http = require("http"), fs = require("fs"), path = require("path");
const root = process.env.ROOT, port = Number(process.env.PORT || 18096), apiMode = process.env.API || "proxy", apiPort = Number(process.env.API_PORT || 18787);
const mock = process.env.MOCK_FILE ? JSON.parse(fs.readFileSync(process.env.MOCK_FILE, "utf8")) : {};
const types = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".txt": "text/plain; charset=utf-8", ".md": "text/markdown; charset=utf-8", ".xml": "application/xml" };
http.createServer(async (req, res) => {
  const u = new URL(req.url, "http://x");
  if (u.pathname.startsWith("/rpc")) {
    const chunks = []; for await (const c of req) chunks.push(c);
    if (process.env.MOCK_VALID) {
      try {
        const body = JSON.parse(Buffer.concat(chunks).toString()), arr = Array.isArray(body) ? body : [body];
        if (arr.every(x => x.method === "eth_call" && String(x.params[0].data).startsWith("0xf577a500"))) {
          const out = arr.map(x => ({ jsonrpc: "2.0", id: x.id, result: "0x" + "0".repeat(63) + "1" }));
          res.writeHead(200, { "content-type": "application/json" }); return res.end(JSON.stringify(Array.isArray(body) ? out : out[0]));
        }
      } catch (e) {}
    }
    const r = await fetch("https://bsc-dataseed.binance.org", { method: "POST", headers: { "content-type": "application/json" }, body: Buffer.concat(chunks) }).catch(() => null);
    res.writeHead(r ? r.status : 502, { "content-type": "application/json" }); return res.end(r ? await r.text() : "{}");
  }
  if (u.pathname.startsWith("/api/")) {
    const sub = u.pathname.slice(4) + u.search;
    if (apiMode === "none") { res.writeHead(404, { "content-type": "application/json" }); return res.end("{}"); }
    if (apiMode === "mock") {
      const k = Object.keys(mock).find(k => sub.startsWith(k));
      if (!k) { res.writeHead(404, { "content-type": "application/json" }); return res.end("{}"); }
      res.writeHead(200, { "content-type": "application/json" }); return res.end(JSON.stringify(mock[k]));
    }
    const r = await fetch("http://127.0.0.1:" + apiPort + sub).catch(() => null);
    res.writeHead(r ? r.status : 502, { "content-type": "application/json" }); return res.end(r ? await r.text() : "{}");
  }
  let p = decodeURIComponent(u.pathname); if (p === "/") p = "/index.html";
  let f = path.join(root, p); if (!fs.existsSync(f) && fs.existsSync(f + ".html")) f += ".html";
  if (!f.startsWith(root) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end("not found"); }
  res.writeHead(200, { "content-type": types[path.extname(f)] || "application/octet-stream", "cache-control": "no-store" }); fs.createReadStream(f).pipe(res);
}).listen(port, "127.0.0.1", () => console.log("listening", port));
