#!/usr/bin/env node
// 生成部署面板用的固化产物 artifacts.json。
// 字节码与 ABI 直接读 forge build 的 out/*.json，构造参数元数据写死在下面，
// 与 script/Deploy.s.sol 完全一致。名单哈希从 docs/contracts/*.hashes.txt 读取。
//
// 用法：node tools/deploy-panel/generate-artifacts.mjs
// 产出：tools/deploy-panel/public/artifacts.json

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..", "..");

// 固定地址（与 Deploy.s.sol 的 DEFAULT_* 一致）
const ADMIN = "0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7";
const FEE_RECEIVER = "0x57A76124bC919F7509bEb54924E8448258De90df";
const AI_REGISTRY = "0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F";

// 内置 actionId 常量（bytes32，字符串左对齐）
function b32(s) {
  return "0x" + Buffer.from(s, "utf8").toString("hex").padEnd(64, "0");
}

const ACTION_REVIEW_GIVE = b32("REVIEW_GIVE");
const ACTION_REVIEW_RECEIVE = b32("REVIEW_RECEIVE");
const ACTION_ACTIVATE = b32("ACTIVATE");

// KeyMode 枚举（HahaPoints.sol）
const KeyMode = { None: 0, PerDay: 1, Lifetime: 2 };

// 编译参数（foundry.toml）
const COMPILER = {
  version: "0.8.28",
  optimizer: true,
  optimizerRuns: 200,
  viaIR: true,
  evmVersion: "cancun",
};

const COMMIT = "70fe8e79"; // 面板固定的 commit（PR #6 合并到 main 的 merge commit）

// ---------------------------------------------------------------------------
// 1. 读取 forge 产物
// ---------------------------------------------------------------------------
function readArtifact(name) {
  const path = join(ROOT, "out", `${name}.sol`, `${name}.json`);
  return JSON.parse(readFileSync(path, "utf8"));
}

// 名单哈希：读 "word 0xhash" 每行，取 hash
function readHashes(rel) {
  const txt = readFileSync(join(ROOT, rel), "utf8");
  return txt
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.length > 0)
    .map((l) => l.split(/\s+/)[1]); // 取 0x... 部分
}

const banned = readHashes("docs/contracts/blacklist-v2.hashes.txt");
const reserved = readHashes("docs/contracts/reserved-names.hashes.txt");

// ---------------------------------------------------------------------------
// 2. 部署步骤定义
//
// 每步：contract 名称、bytecode、abi、构造参数编码方式。
// 参数分三类：
//   - {kind:"fixed", value}: 写死地址（admin/feeReceiver/aiRegistry）
//   - {kind:"predicted", index}: 引用预测地址数组中第 index 个（按部署顺序 0..9）
//   - {kind:"raw", data}: 已编码好的原始 calldata（用于 abi.encode 打包的 Registrar、NamePolicy）
//
// 部署顺序（Deploy.s.sol _deployAll，nonce 从链上读，相对基准 N 连续 +0..+9）：
//   N+0 policy, N+1 metadata, N+2 resolver, N+3 registry, N+4 registrar,
//   N+5 identity, N+6 points, N+7 reputation, N+8 marketplace, N+9 deployer
// ---------------------------------------------------------------------------

const contracts = [
  { name: "HahaNamePolicy", file: "HahaNamePolicy" },
  { name: "HahaMetadata", file: "HahaMetadata" },
  { name: "HahaResolver", file: "HahaResolver" },
  { name: "HahaRegistry", file: "HahaRegistry" },
  { name: "HahaRegistrar", file: "HahaRegistrar" },
  { name: "HahaAgentIdentity", file: "HahaAgentIdentity" },
  { name: "HahaPoints", file: "HahaPoints" },
  { name: "HahaReputation", file: "HahaReputation" },
  { name: "HahaMarketplace", file: "HahaMarketplace" },
  { name: "HahaDeployer", file: "HahaDeployer" },
];

const artifacts = {};
for (const c of contracts) {
  const a = readArtifact(c.file);
  artifacts[c.name] = {
    bytecode: a.bytecode.object.replace(/^0x/, ""), // creation code（去 0x 前缀的纯 hex）
    abi: a.abi,
  };
}

// ---------------------------------------------------------------------------
// 3. 部署步骤（含构造参数元数据），前端据此动态编码
// ---------------------------------------------------------------------------

// 构造参数用「占位」描述，前端拿到预测地址后填充。
// 用统一的描述结构：args 数组，每项是 {t:"addr", fixed:地址} 或 {t:"addr", p:预测索引} 或 {t:"b32arr", hashes:[...]}。
const steps = [
  {
    key: "deploy:namepolicy",
    label: "部署 HahaNamePolicy",
    contract: "HahaNamePolicy",
    kind: "deploy",
    adminOnly: false,
    args: [{ t: "b32arr", banned }, { t: "b32arr", reserved }],
  },
  {
    key: "deploy:metadata",
    label: "部署 HahaMetadata",
    contract: "HahaMetadata",
    kind: "deploy",
    adminOnly: false,
    args: [],
  },
  {
    key: "deploy:resolver",
    label: "部署 HahaResolver",
    contract: "HahaResolver",
    kind: "deploy",
    adminOnly: false,
    args: [{ t: "addr", p: 3 }, { t: "addr", p: 4 }], // registry, registrar
  },
  {
    key: "deploy:registry",
    label: "部署 HahaRegistry",
    contract: "HahaRegistry",
    kind: "deploy",
    adminOnly: false,
    args: [{ t: "addr", p: 4 }, { t: "addr", p: 9 }, { t: "addr", p: 2 }], // registrar, factory(deployer), resolver
  },
  {
    key: "deploy:registrar",
    label: "部署 HahaRegistrar",
    contract: "HahaRegistrar",
    kind: "deploy",
    adminOnly: false,
    // 构造参数是 abi.encode(9 addresses) 打包成 bytes，前端用 abi.encode 再包一层
    args: [{ t: "encode9", refs: [3, 2, 1, 6, 5, 0, "aiRegistry", "admin", "feeReceiver"] }],
  },
  {
    key: "deploy:identity",
    label: "部署 HahaAgentIdentity",
    contract: "HahaAgentIdentity",
    kind: "deploy",
    adminOnly: false,
    args: [{ t: "addr", p: 4 }, { t: "addr", p: 2 }, { t: "addr", p: 6 }, { t: "addr", fixed: AI_REGISTRY }], // registrar, resolver, points, aiRegistry
  },
  {
    key: "deploy:points",
    label: "部署 HahaPoints",
    contract: "HahaPoints",
    kind: "deploy",
    adminOnly: false,
    args: [{ t: "addr", p: 4 }, { t: "addr", fixed: AI_REGISTRY }, { t: "addr", fixed: ADMIN }], // registrar, aiRegistry, admin
  },
  {
    key: "deploy:reputation",
    label: "部署 HahaReputation",
    contract: "HahaReputation",
    kind: "deploy",
    adminOnly: false,
    args: [{ t: "addr", p: 5 }, { t: "addr", fixed: AI_REGISTRY }, { t: "addr", p: 6 }], // identity, aiRegistry, points
  },
  {
    key: "deploy:marketplace",
    label: "部署 HahaMarketplace",
    contract: "HahaMarketplace",
    kind: "deploy",
    adminOnly: false,
    args: [{ t: "addr", p: 4 }, { t: "addr", fixed: FEE_RECEIVER }], // registrar, feeReceiver
  },
  {
    key: "deploy:deployer",
    label: "部署 HahaDeployer（触发 bootstrap）",
    contract: "HahaDeployer",
    kind: "deploy",
    adminOnly: false,
    args: [
      { t: "addrarr9", refs: [0, 1, 2, 3, 4, 5, 6, 7, 8] },
      { t: "addr", fixed: ADMIN },
      { t: "addr", fixed: FEE_RECEIVER },
      { t: "addr", fixed: AI_REGISTRY },
    ],
  },
];

// ---------------------------------------------------------------------------
// 4. 部署后配置步骤（管理员钱包）
// ---------------------------------------------------------------------------
const configSteps = [
  {
    key: "config:earner-review-give",
    label: "setEarner：写评价 REVIEW_GIVE",
    contract: "HahaPoints",
    kind: "tx",
    adminOnly: true,
    method: "setEarner",
    args: [
      ACTION_REVIEW_GIVE,
      { module: "{reputation}", points: 5, perUserDailyCap: 5, globalDailyPoints: 50000, keyMode: KeyMode.PerDay, requireName: true, enabled: true },
    ],
  },
  {
    key: "config:earner-review-receive",
    label: "setEarner：收到评价 REVIEW_RECEIVE",
    contract: "HahaPoints",
    kind: "tx",
    adminOnly: true,
    method: "setEarner",
    args: [
      ACTION_REVIEW_RECEIVE,
      { module: "{reputation}", points: 5, perUserDailyCap: 5, globalDailyPoints: 50000, keyMode: KeyMode.PerDay, requireName: false, enabled: true },
    ],
  },
  {
    key: "config:earner-activate",
    label: "setEarner：激活 ACTIVATE",
    contract: "HahaPoints",
    kind: "tx",
    adminOnly: true,
    method: "setEarner",
    args: [
      ACTION_ACTIVATE,
      { module: "{identity}", points: 20, perUserDailyCap: 1, globalDailyPoints: 100000, keyMode: KeyMode.Lifetime, requireName: true, enabled: true },
    ],
  },
];

// ---------------------------------------------------------------------------
// 5. 输出
// ---------------------------------------------------------------------------
const out = {
  commit: COMMIT,
  compiler: COMPILER,
  addresses: { admin: ADMIN, feeReceiver: FEE_RECEIVER, aiRegistry: AI_REGISTRY },
  keyModes: KeyMode,
  actionIds: {
    reviewGive: ACTION_REVIEW_GIVE,
    reviewReceive: ACTION_REVIEW_RECEIVE,
    activate: ACTION_ACTIVATE,
  },
  artifacts,
  steps,
  configSteps,
};

const outPath = join(__dirname, "public", "artifacts.json");
mkdirSync(dirname(outPath), { recursive: true });
writeFileSync(outPath, JSON.stringify(out, null, 2));
console.log(`已生成 ${outPath}`);
console.log(`  合约数: ${contracts.length}`);
console.log(`  部署步骤: ${steps.length}`);
console.log(`  配置步骤: ${configSteps.length}`);
console.log(`  banned: ${banned.length}, reserved: ${reserved.length}`);
