// Local preview server: static files from ../site, /rpc/ proxied to a public BSC node, /api/ returns 404.
const http = require("http"), fs = require("fs"), path = require("path");
const root = process.env.ROOT || path.join(__dirname, "../site"), port = Number(process.env.PORT || 18095);
const types = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".md": "text/markdown", ".txt": "text/plain", ".webmanifest": "application/json", ".ico": "image/x-icon", ".gif": "image/gif" };
http.createServer(async (req, res) => {
  const u = new URL(req.url, "http://x");
  if (u.pathname.startsWith("/rpc")) {
    const chunks = []; for await (const c of req) chunks.push(c);
    const r = await fetch("https://bsc-dataseed.binance.org", { method: "POST", headers: { "content-type": "application/json" }, body: Buffer.concat(chunks) }).catch(() => null);
    res.writeHead(r ? r.status : 502, { "content-type": "application/json" }); return res.end(r ? await r.text() : "{}");
  }
  if (u.pathname.startsWith("/api")) { res.writeHead(404, { "content-type": "application/json" }); return res.end("{}"); }
  let p = decodeURIComponent(u.pathname); if (p === "/") p = "/index.html";
  let f = path.join(root, p); if (!fs.existsSync(f) && fs.existsSync(f + ".html")) f += ".html";
  if (!f.startsWith(root) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end("not found"); }
  res.writeHead(200, { "content-type": types[path.extname(f)] || "application/octet-stream", "cache-control": "no-store" }); fs.createReadStream(f).pipe(res);
}).listen(port, "127.0.0.1", () => console.log("listening", port));
