// 最小静态服务器 + BscScan 验证代理，零依赖，纯本地运行。
// 服务 tools/deploy-panel/ 目录（index.html 在根，public/ 放 artifacts.json）。
// /api/bscscan 代理验证请求到 BscScan API（服务器端无 CORS 限制）。
// 用法：node tools/deploy-panel/server.mjs [port]

import { createServer } from "node:http";
import { request as httpsRequest } from "node:https";
import { readFileSync, existsSync, statSync } from "node:fs";
import { join, normalize, dirname, extname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = normalize(join(__dirname, "..", "..")); // 仓库根
const PORT = Number(process.argv[2] || process.env.PORT || 4321);

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".sol": "text/plain; charset=utf-8",
  ".svg": "image/svg+xml",
};

// 把 URL 路径映射到本地文件。
function resolvePath(urlPath) {
  let p = decodeURIComponent(urlPath.split("?")[0]);
  if (p === "/") p = "/index.html";
  if (p === "/vendor/ethers.umd.min.js") {
    return normalize(join(__dirname, "node_modules", "ethers", "dist", "ethers.umd.min.js"));
  }
  if (p.startsWith("/src/")) {
    return normalize(join(ROOT, p));
  }
  return normalize(join(__dirname, p));
}

function serveFile(res, file) {
  const ext = extname(file).toLowerCase();
  res.writeHead(200, { "Content-Type": MIME[ext] || "application/octet-stream" });
  res.end(readFileSync(file));
}

function sendJson(res, code, obj) {
  res.writeHead(code, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(obj));
}

// 代理 Etherscan V2 验证请求。body: { chainid: 56|97, apikey: "...", form: {...} }
function proxyBscScan(req, res) {
  let body = "";
  req.on("data", (c) => (body += c));
  req.on("end", () => {
    let payload;
    try {
      payload = JSON.parse(body);
    } catch (e) {
      sendJson(res, 400, { status: "0", result: "无效请求体" });
      return;
    }

    const { chainid, apikey, form } = payload || {};
    // Etherscan V2 统一 API：一个 endpoint + chainid 参数跨链（56=BNB 主网, 97=BNB 测试网）
    const url = `https://api.etherscan.io/v2/api?chainid=${chainid || 56}&apikey=${encodeURIComponent(apikey || "")}`;

    const formBody = new URLSearchParams(form || {}).toString();

    const upstream = httpsRequest(
      url,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          "Content-Length": Buffer.byteLength(formBody),
        },
      },
      (upRes) => {
        let data = "";
        upRes.on("data", (c) => (data += c));
        upRes.on("end", () => {
          res.writeHead(upRes.statusCode || 200, { "Content-Type": "application/json; charset=utf-8" });
          res.end(data);
        });
      }
    );
    upstream.on("error", (e) => {
      sendJson(res, 502, { status: "0", result: "代理请求失败：" + e.message });
    });
    upstream.write(formBody);
    upstream.end();
  });
}

const server = createServer((req, res) => {
  const urlPath = req.url.split("?")[0];

  // BscScan 验证代理
  if (urlPath === "/api/bscscan" && req.method === "POST") {
    proxyBscScan(req, res);
    return;
  }

  // 静态文件
  const file = resolvePath(req.url);
  const allowedRoots = [__dirname, join(ROOT, "src"), join(__dirname, "node_modules", "ethers", "dist")];
  const isAllowed = allowedRoots.some((root) => normalize(file).startsWith(normalize(root)));

  if (!isAllowed || !existsSync(file) || !statSync(file).isFile()) {
    res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    res.end("404 Not Found: " + req.url);
    return;
  }
  serveFile(res, file);
});

server.listen(PORT, "127.0.0.1", () => {
  console.log("");
  console.log("  haha.meme 部署面板已启动（仅本地）");
  console.log(`  → http://localhost:${PORT}`);
  console.log("");
  console.log("  字节码来源: public/artifacts.json（commit 固定）");
  console.log("  验证代理:   POST /api/bscscan -> api.bscscan.com");
  console.log("  按 Ctrl+C 停止");
  console.log("");
});
