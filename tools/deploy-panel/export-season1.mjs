#!/usr/bin/env node
// 导出 HahaSeason1 的 ABI 和 handoff.json（给 A 并行对接）。
// 用法：node tools/deploy-panel/export-season1.mjs
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { execSync } from "node:child_process";
import { ethers } from "ethers";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..", "..");

const artifact = JSON.parse(readFileSync(join(ROOT, "out", "HahaSeason1.sol", "HahaSeason1.json"), "utf8"));
const abi = artifact.abi;

// 事件签名 -> topic0（keccak256，用 ethers.id）
function eventSignature(item) {
  const inputs = item.inputs.map((i) => i.type).join(",");
  return `${item.name}(${inputs})`;
}
function topic0(sig) {
  return ethers.id(sig);
}

// 事件名（索引器只认这些，加上旧事件）
const SEASON_EVENTS = [
  "DayRootSet",
  "Redeemed",
  "FulfillmentAttested",
  "Verified",
  "FindingCommitted",
  "CanonicalAssigned",
  "FindingPaid",
  "ValidatorSet",
  "RewardSignerSet",
  "TaskPackSet",
  "AccidentDeclared",
  "AccidentRefunded",
  "AccidentCompensationDeferred",
  "AccidentCompensated",
];

const events = [];
for (const item of abi) {
  if (item.type === "event" && SEASON_EVENTS.includes(item.name)) {
    const sig = eventSignature(item);
    events.push({ name: item.name, signature: sig, topic0: topic0(sig) });
  }
}

// 确认没有 MintConfirmed
const hasMintConfirmed = abi.some((i) => i.type === "event" && i.name === "MintConfirmed");
if (hasMintConfirmed) {
  console.error("错误：ABI 里出现 MintConfirmed 事件，不应发出。");
  process.exit(1);
}

const specCommit = (() => {
  try {
    return execSync("git rev-parse --short HEAD", { cwd: ROOT }).toString().trim();
  } catch {
    return "unknown";
  }
})();

const deployedBytecode = artifact.deployedBytecode.object.replace(/^0x/, "");
const creationBytecode = artifact.bytecode.object; // 带 0x 前缀

const outDir = join(__dirname, "public", "season1");
mkdirSync(outDir, { recursive: true });

// ABI
writeFileSync(join(outDir, "HahaSeason1.abi.json"), JSON.stringify(abi, null, 2));

// creation bytecode（部署面板用）
writeFileSync(join(outDir, "HahaSeason1.bytecode.json"), JSON.stringify({ bytecode: creationBytecode }, null, 2));

// handoff.json
const handoff = {
  kind: "season1-handoff",
  specCommit,
  compiler: "0.8.28",
  viaIr: true,
  bytecodeBytes: Math.floor(deployedBytecode.length / 2),
  split: false,
  abiPath: "tools/deploy-panel/public/season1/HahaSeason1.abi.json",
  events,
  anvil: { chainId: 31337, module: null },
  mainnet: { chainId: 56, module: null },
};
writeFileSync(join(outDir, "handoff.json"), JSON.stringify(handoff, null, 2));

console.log("已导出 ABI 和 handoff.json -> public/season1/");
console.log("  事件数:", events.length);
console.log("  运行时字节码:", handoff.bytecodeBytes, "bytes");
console.log("  事件清单:");
for (const e of events) {
  console.log(`    ${e.name}  ${e.topic0}`);
}
