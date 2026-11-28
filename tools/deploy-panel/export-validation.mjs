#!/usr/bin/env node
// 导出 HahaValidation 的 ABI 和 bytecode（供部署面板使用）。
// 用法：node tools/deploy-panel/export-validation.mjs
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { execSync } from "node:child_process";
import { ethers } from "ethers";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..", "..");

const artifact = JSON.parse(
  readFileSync(join(ROOT, "out", "HahaValidation.sol", "HahaValidation.json"), "utf8")
);
const abi = artifact.abi;

function eventSignature(item) {
  const inputs = item.inputs.map((i) => i.type).join(",");
  return `${item.name}(${inputs})`;
}
function topic0(sig) {
  return ethers.id(sig);
}

// 3 个事件（含 indexed）
const VALIDATION_EVENTS = ["ValidationRequest", "ValidationResponse", "ValidationDisputed"];

const events = [];
for (const item of abi) {
  if (item.type === "event" && VALIDATION_EVENTS.includes(item.name)) {
    const sig = eventSignature(item);
    events.push({ name: item.name, signature: sig, topic0: topic0(sig) });
  }
}

const specCommit = (() => {
  try {
    return execSync("git rev-parse --short HEAD", { cwd: ROOT }).toString().trim();
  } catch {
    return "unknown";
  }
})();

const creationBytecode = artifact.bytecode.object; // 带 0x 前缀
const deployedBytecode = artifact.deployedBytecode.object.replace(/^0x/, "");

const outDir = join(__dirname, "public", "validation");
mkdirSync(outDir, { recursive: true });

writeFileSync(join(outDir, "HahaValidation.abi.json"), JSON.stringify(abi, null, 2));
writeFileSync(join(outDir, "HahaValidation.bytecode.json"), JSON.stringify({ bytecode: creationBytecode }, null, 2));

const handoff = {
  kind: "validation-handoff",
  specCommit,
  compiler: "0.8.28",
  viaIr: true,
  bytecodeBytes: Math.floor(deployedBytecode.length / 2),
  abiPath: "tools/deploy-panel/public/validation/HahaValidation.abi.json",
  events,
  // 构造参数：admin + identity（v1 固定，见 validation-registry-plan.md §2.1/§4.1）
  constructor: {
    admin: "0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7", // = HahaRegistrar 的 admin
    identity: "0x54A70BF81B288d41013D7b57c2Db0922f1E1a4d4", // = HahaAgentIdentity
  },
};
writeFileSync(join(outDir, "handoff.json"), JSON.stringify(handoff, null, 2));

console.log("已导出 ABI 和 bytecode -> public/validation/");
console.log("  事件数:", events.length);
console.log("  运行时字节码:", handoff.bytecodeBytes, "bytes");
console.log("  事件清单:");
for (const e of events) {
  console.log(`    ${e.name}  ${e.topic0}`);
}
