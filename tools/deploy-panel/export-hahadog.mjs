#!/usr/bin/env node
// 导出 Haha Dog 4 个合约的 ABI + bytecode（供部署面板 dog.html 使用）。
// 顺序：HahaDogModel -> HahaDogRenderer -> HahaDog -> HahaDogMarket
// 用法：node tools/deploy-panel/export-hahadog.mjs
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { execSync } from "node:child_process";
import { ethers } from "ethers";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..", "..");

const CONTRACTS = [
  {
    name: "HahaDogModel",
    source: "src/hahadog/HahaDogModel.sol:HahaDogModel",
    ctorTypes: [], // 无构造参数
    hasConstructorArgs: false,
  },
  {
    name: "HahaDogRenderer",
    source: "src/hahadog/HahaDogRenderer.sol:HahaDogRenderer",
    ctorTypes: ["address"], // model
    hasConstructorArgs: true,
  },
  {
    name: "HahaDog",
    source: "src/hahadog/HahaDog.sol:HahaDog",
    ctorTypes: ["address", "address", "address", "address", "address"], // renderer, aiRegistry, registrar, feeReceiver, blockHistory
    hasConstructorArgs: true,
  },
  {
    name: "HahaDogMarket",
    source: "src/hahadog/HahaDogMarket.sol:HahaDogMarket",
    ctorTypes: ["address", "address"], // dog, feeReceiver
    hasConstructorArgs: true,
  },
];

function eventSignature(item) {
  const inputs = item.inputs.map((i) => i.type).join(",");
  return `${item.name}(${inputs})`;
}

const specCommit = (() => {
  try {
    return execSync("git rev-parse --short HEAD", { cwd: ROOT }).toString().trim();
  } catch {
    return "unknown";
  }
})();

const outDir = join(__dirname, "public", "dog");
mkdirSync(outDir, { recursive: true });

const manifest = {
  kind: "haha-dog-handoff",
  specCommit,
  compiler: "0.8.28",
  viaIr: true,
  optimizerRuns: 200,
  evmVersion: "cancun",
  contracts: [],
  // 默认构造参数（BSC 主网，与 DEPLOY.md 一致，可被环境变量覆盖）
  defaults: {
    aiRegistry: "0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F",
    registrar: "0x43426E37a31AafDaba851858e34B81DC300650F8",
    feeReceiver: "0x57A76124bC919F7509bEb54924E8448258De90df",
    blockHistory: "0x0000F90827F1C53a10cb7A02335B175320002935",
  },
  // 两个哈希（DEPLOY.md §5 公布值）：
  // - weightsFileHash：模型权重文件 haha-dog/model/weights-int8.json 原始字节的 keccak256（离线文件哈希）
  // - modelDataHash：链上 HahaDogModel.MODEL_DATA_HASH() = keccak256(Wt.DATA)（链上数据哈希）
  weightsFileHash: "0x1d2239644b5273c4f1925c489d32900a564262bce6597f94a929489cfbe58078",
  modelDataHash: "0x72f92c628a64bc0d5652d285c6789fa0f84cb462d328604cf3dcff224704f8da",
};

for (const c of CONTRACTS) {
  const artifact = JSON.parse(
    readFileSync(join(ROOT, "out", `${c.name}.sol`, `${c.name}.json`), "utf8")
  );
  const abi = artifact.abi;
  const creationBytecode = artifact.bytecode.object; // 带 0x 前缀
  const deployedBytecode = artifact.deployedBytecode.object.replace(/^0x/, "");

  // 收集事件（用于 handoff 记录 + topic0 核对）
  const events = [];
  for (const item of abi) {
    if (item.type === "event") {
      const sig = eventSignature(item);
      events.push({ name: item.name, signature: sig, topic0: ethers.id(sig) });
    }
  }

  // 写 ABI 和 bytecode
  writeFileSync(join(outDir, `${c.name}.abi.json`), JSON.stringify(abi, null, 2));
  writeFileSync(
    join(outDir, `${c.name}.bytecode.json`),
    JSON.stringify({ bytecode: creationBytecode }, null, 2)
  );

  const entry = {
    name: c.name,
    source: c.source,
    ctorTypes: c.ctorTypes,
    hasConstructorArgs: c.hasConstructorArgs,
    bytecodeBytes: Math.floor(deployedBytecode.length / 2),
    abiPath: `tools/deploy-panel/public/dog/${c.name}.abi.json`,
    bytecodePath: `tools/deploy-panel/public/dog/${c.name}.bytecode.json`,
    events,
  };
  manifest.contracts.push(entry);

  console.log(`  ${c.name}: 运行时 ${entry.bytecodeBytes} bytes, ${events.length} 个事件`);
}

writeFileSync(join(outDir, "handoff.json"), JSON.stringify(manifest, null, 2));

console.log("已导出 4 个合约 ABI + bytecode -> public/dog/");
console.log("  事件 topic0 清单:");
for (const c of manifest.contracts) {
  for (const e of c.events) {
    console.log(`    [${c.name}] ${e.name}  ${e.topic0}`);
  }
}
