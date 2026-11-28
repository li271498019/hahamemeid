#!/usr/bin/env node
// 向 BscScan 提交 HahaSeason1 开源验证（solidity-standard-json-input 模式）。
// 用法：BSCSCAN_API_KEY=<key> node tools/deploy-panel/verify-hs1.mjs
// 走 HTTP_PROXY/HTTPS_PROXY 环境变量（若已设置）。
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

const ADDRESS = "0x4B8a35bFe18750c2058fd01e7159728adD345C00";
const CONTRACT_NAME = "src/HahaSeason1.sol:HahaSeason1";
const COMPILER = "v0.8.28+commit.7893614a";

const apiKey = process.env.BSCSCAN_API_KEY || process.env.ETHERSCAN_API_KEY || "";
if (!apiKey) {
  console.error("缺少 API key：请设置 BSCSCAN_API_KEY（或 ETHERSCAN_API_KEY）环境变量。");
  process.exit(1);
}

const standardInput = readFileSync(join(__dirname, "public", "verify", "HahaSeason1.json"), "utf8");

// BscScan 已迁移到 Etherscan V2 统一 API：一个 endpoint + chainid 参数跨链（56=BNB 主网）。
// 验证成功后源码显示在 bscscan.com。
const chainId = process.env.CHAIN_ID || "56";
const params = new URLSearchParams({
  apikey: apiKey,
  module: "contract",
  action: "verifysourcecode",
  contractaddress: ADDRESS,
  sourceCode: standardInput,
  codeformat: "solidity-standard-json-input",
  contractname: CONTRACT_NAME,
  compilerversion: COMPILER,
  optimizationUsed: "1",
  runs: "200",
  licenseType: "3", // MIT
});

const endpoint = process.env.BSCSCAN_ENDPOINT || `https://api.etherscan.io/v2/api?chainid=${chainId}`;

try {
  const res = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: params.toString(),
  });
  const text = await res.text();
  let json;
  try { json = JSON.parse(text); } catch { json = { raw: text }; }

  if (json.status === "1" || json.message === "OK") {
    console.log("✅ 验证提交成功：", json.result || json.message);
    console.log("查看：https://bscscan.com/address/" + ADDRESS + "#code");
  } else {
    console.log("❌ 验证失败：", json.result || json.message || text);
  }
} catch (e) {
  console.error("请求失败：", e.message);
  process.exit(1);
}
