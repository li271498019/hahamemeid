#!/usr/bin/env node
// 生成 Etherscan V2 验证用的 standard-input JSON（每个主合约一份）。
// 递归收集 import 依赖，sources key 使用 import 语句能匹配的逻辑路径：
//   - remapping import "@openzeppelin/contracts/..." -> sources key 保留 "@openzeppelin/contracts/..."
//   - 相对 import "./..." / "../..." -> 相对当前逻辑路径解析
// 与 foundry.toml 的 solc 设置一致（via-ir, optimizer 200, cancun）。
//
// 用法：node tools/deploy-panel/generate-standard-input.mjs

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join, resolve, normalize, posix } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..", "..");

// remappings（与 foundry.toml 一致）: import 前缀 -> 实际文件路径（相对 ROOT）
const REMAPPINGS = [
  ["@openzeppelin/contracts/", "lib/openzeppelin-contracts/contracts/"],
  ["forge-std/", "lib/forge-std/src/"],
];

const MAIN_CONTRACTS = [
  "HahaNamePolicy", "HahaMetadata", "HahaResolver", "HahaRegistry", "HahaRegistrar",
  "HahaAgentIdentity", "HahaPoints", "HahaReputation", "HahaMarketplace", "HahaDeployer",
  "HahaValidation",
];

// Haha Dog 4 个合约（src/hahadog/ 目录，逻辑路径不同）
const HAHA_DOG_CONTRACTS = [
  "hahadog/HahaDogModel", "hahadog/HahaDogRenderer", "hahadog/HahaDog", "hahadog/HahaDogMarket",
];

// 逻辑路径 -> 绝对路径。返回 null 表示找不到。
function logicalToAbsolute(logicalPath) {
  // remapping 前缀
  for (const [prefix, target] of REMAPPINGS) {
    if (logicalPath.startsWith(prefix)) {
      return resolve(ROOT, target, logicalPath.slice(prefix.length));
    }
  }
  // 其余（src/... 或 lib/...）直接相对 ROOT
  return resolve(ROOT, logicalPath);
}

// 从逻辑路径解析 import 到新的逻辑路径。
// import 相对路径时相对当前逻辑路径的目录；remapping 时直接用前缀。
function resolveImportLogical(fromLogical, importPath) {
  if (importPath.startsWith(".")) {
    // 相对路径：normalize 掉 ./ 和 ../
    const base = posix.dirname(fromLogical);
    return posix.normalize(posix.join(base, importPath));
  }
  // remapping 或裸路径，直接返回（保持原样）
  return importPath;
}

function collectImports(entryLogical, sources, visited) {
  if (visited.has(entryLogical)) return;
  visited.add(entryLogical);

  const abs = logicalToAbsolute(entryLogical);
  let content;
  try {
    content = readFileSync(abs, "utf8");
  } catch {
    console.warn("  跳过缺失文件:", entryLogical, "->", abs);
    return;
  }

  sources[entryLogical] = { content };

  const importRe = /import\s+(?:\{[^}]*\}\s+from\s+)?["']([^"']+)["']/g;
  let m;
  while ((m = importRe.exec(content)) !== null) {
    const depLogical = resolveImportLogical(entryLogical, m[1]);
    if (!visited.has(depLogical)) {
      collectImports(depLogical, sources, visited);
    }
  }
}

function buildStandardInput(contractName) {
  const sources = {};
  const visited = new Set();
  collectImports("src/" + contractName + ".sol", sources, visited);

  return {
    language: "Solidity",
    sources,
    settings: {
      optimizer: { enabled: true, runs: 200 },
      viaIR: true,
      evmVersion: "cancun",
      outputSelection: { "*": { "*": ["abi", "evm.bytecode"] } },
      // metadata.bytecodeHash 与部署一致：foundry 默认 ipfs
      metadata: { bytecodeHash: "ipfs" },
    },
  };
}

function main() {
  const outDir = join(__dirname, "public", "verify");
  mkdirSync(outDir, { recursive: true });

  for (const name of MAIN_CONTRACTS) {
    const input = buildStandardInput(name);
    const file = join(outDir, `${name}.json`);
    writeFileSync(file, JSON.stringify(input));
    console.log(`  ${name}.json  -> ${Object.keys(input.sources).length} 个源文件`);
  }
  for (const name of HAHA_DOG_CONTRACTS) {
    const input = buildStandardInput(name);
    const file = join(outDir, `${name.replace(/\//g, "_")}.json`);
    writeFileSync(file, JSON.stringify(input));
    console.log(`  ${name}.json  -> ${Object.keys(input.sources).length} 个源文件`);
  }
  console.log("standard-input 生成完成 -> public/verify/");
}

main();
