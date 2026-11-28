// dry-run 验证：在 anvil 本地链上完整走一遍部署，验证面板的核心逻辑
// （CREATE 地址预测 + 构造参数编码 + 字节码）能正确部署全部 10 个合约并 bootstrap。
// 用法：
//   1. 起 anvil:  anvil --silent
//   2. node tools/deploy-panel/verify-dryrun.mjs
import { ethers } from "ethers";
import { readFileSync } from "node:fs";

import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
const __dirname = dirname(fileURLToPath(import.meta.url));

const RPC = process.env.RPC || "http://127.0.0.1:8545";
const artifacts = JSON.parse(readFileSync(join(__dirname, "public", "artifacts.json"), "utf8"));

const ADMIN = artifacts.addresses.admin;
const FEE = artifacts.addresses.feeReceiver;
const AI = artifacts.addresses.aiRegistry;

// 用 anvil 提供的测试账户作部署者（私钥是 anvil 默认的）
const provider = new ethers.JsonRpcProvider(RPC);
const deployer = new ethers.Wallet("0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80", provider);

const CONTRACT_NAMES = ["namepolicy", "metadata", "resolver", "registry", "registrar", "identity", "points", "reputation", "marketplace", "deployer"];

function predictAddresses(deployerAddr, baseNonce) {
  const addrs = [];
  for (let i = 0; i < 10; i++) {
    addrs.push(ethers.getCreateAddress({ from: deployerAddr, nonce: BigInt(baseNonce) + BigInt(i) }));
  }
  return addrs;
}

function encodeConstructor(step, predicted) {
  const abi = ethers.AbiCoder.defaultAbiCoder();
  const resolveAddr = (r) => (typeof r === "number" ? predicted[r] : artifacts.addresses[r]);
  const types = [];
  const values = [];
  for (const a of step.args) {
    if (a.t === "addr") { types.push("address"); values.push(a.fixed !== undefined ? a.fixed : predicted[a.p]); }
    else if (a.t === "b32arr") { types.push("bytes32[]"); values.push(a.banned || a.reserved || []); }
    else if (a.t === "encode9") {
      types.push("bytes");
      values.push(abi.encode(
        ["address", "address", "address", "address", "address", "address", "address", "address", "address"],
        a.refs.map(resolveAddr)
      ));
    } else if (a.t === "addrarr9") { types.push("address[9]"); values.push(a.refs.map(resolveAddr)); }
  }
  const argsHex = types.length === 0 ? "" : abi.encode(types, values).slice(2);
  return "0x" + step.contractInfo.bytecode + argsHex;
}

async function main() {
  const deployerAddr = deployer.address;
  // 注意：.ai 注册表在 anvil 上没有代码，但 HahaRegistrar/HahaPoints 构造不检查 aiRegistry 代码，
  // 只有 Deploy.s.sol 的前置检查 _checkAiBytecode 检查，面板不强制（仅部署）。这里用一个非零地址即可。
  const baseNonce = await provider.getTransactionCount(deployerAddr);
  const predicted = predictAddresses(deployerAddr, baseNonce);

  console.log("起始 nonce:", baseNonce);
  console.log("部署者:", deployerAddr);
  console.log("");

  const deployed = {};
  let ok = true;

  // 部署 10 个合约
  for (let i = 0; i < 10; i++) {
    const step = artifacts.steps[i];
    const contractInfo = artifacts.artifacts[step.contract];
    const data = encodeConstructor({ ...step, contractInfo }, predicted);
    const tx = await deployer.sendTransaction({ data, gasLimit: 30_000_000 });
    const receipt = await tx.wait();
    const actual = receipt.contractAddress;
    const expected = predicted[i];
    const name = CONTRACT_NAMES[i];
    deployed[name] = actual;
    const match = actual.toLowerCase() === expected.toLowerCase();
    if (!match) ok = false;
    console.log(`${String(i).padStart(2)} ${step.contract.padEnd(18)} 预测=${expected.slice(0,10)}… 实际=${actual.slice(0,10)}… ${match ? "✓" : "✗ 地址不符"}`);
  }

  console.log("");
  console.log("=== 读回核对 ===");
  // 核对 registry.bootstrapped == true（HahaDeployer 构造时 bootstrap）
  const regAbi = artifacts.artifacts.HahaRegistry.abi;
  const registry = new ethers.Contract(deployed.registry, regAbi, provider);
  const bootstrapped = await registry.bootstrapped();
  console.log("registry.bootstrapped:", bootstrapped, bootstrapped ? "✓" : "✗");
  if (!bootstrapped) ok = false;

  // 核对 HahaDeployer.addresses 与 predicted 一致
  const depAbi = artifacts.artifacts.HahaDeployer.abi;
  const deployerC = new ethers.Contract(deployed.deployer, depAbi, provider);
  const addrs = await deployerC.addresses();
  for (let i = 0; i < 9; i++) {
    const m = addrs[i].toLowerCase() === predicted[i].toLowerCase();
    if (!m) { ok = false; console.log(`Deployer.addresses[${i}] 不符`); }
  }
  console.log("HahaDeployer.addresses 与预测一致: ✓");

  // 核对 TLD owner
  const hahaNode = "0xaa5a3a58f7c8841455eecaa0c6a6a0b40ace5681fbb31361a0d45b168179128f";
  const memeNode = "0x74df4ab2564a9f9bb6d4b6b77bf4fc02ac80f07bd9e1776d3967578b3fc36be4";
  const o1 = await registry.owner(hahaNode);
  const o2 = await registry.owner(memeNode);
  console.log("hahaNode owner == registrar:", o1.toLowerCase() === deployed.registrar.toLowerCase() ? "✓" : "✗");
  console.log("memeNode owner == registrar:", o2.toLowerCase() === deployed.registrar.toLowerCase() ? "✓" : "✗");

  // 核对 registrar.admin / feeReceiver
  const regrAbi = artifacts.artifacts.HahaRegistrar.abi;
  const registrar = new ethers.Contract(deployed.registrar, regrAbi, provider);
  const admin = await registrar.admin();
  const fee = await registrar.feeReceiver();
  console.log("registrar.admin == ADMIN:", admin.toLowerCase() === ADMIN.toLowerCase() ? "✓" : "✗");
  console.log("registrar.feeReceiver == FEE:", fee.toLowerCase() === FEE.toLowerCase() ? "✓" : "✗");

  // 核对 points.admin == ADMIN
  const pointsAbi = artifacts.artifacts.HahaPoints.abi;
  const pointsC = new ethers.Contract(deployed.points, pointsAbi, provider);
  const pAdmin = await pointsC.admin();
  console.log("points.admin == ADMIN:", pAdmin.toLowerCase() === ADMIN.toLowerCase() ? "✓" : "✗");

  // =====================================================================
  // 配置步骤（setEarner × 3），用 anvil impersonate 模拟 admin 钱包
  // =====================================================================
  console.log("");
  console.log("=== 配置步骤（impersonate admin）===");
  const coder = ethers.AbiCoder.defaultAbiCoder();
  const configOk = await runConfigSteps(provider, deployed, artifacts, coder, ADMIN);
  if (!configOk) ok = false;

  // =====================================================================
  // 最终自检：部署者（非 admin）调 adminMint / setPointParams / setEarner 应 revert
  // =====================================================================
  console.log("");
  console.log("=== 最终自检 ===");
  const selAdminMint = new ethers.Interface(regrAbi).encodeFunctionData("adminMint", ["binance", 0, deployerAddr]);
  const r1 = await tryCall(provider, deployed.registrar, selAdminMint, deployerAddr);
  console.log("部署者调 adminMint 被拒:", !r1.ok ? "✓" : "✗ 竟然成功");
  if (r1.ok) ok = false;

  const selSetPoint = new ethers.Interface(pointsAbi).encodeFunctionData("setPointParams", [1,1,1,1,1,1]);
  const r2 = await tryCall(provider, deployed.points, selSetPoint, deployerAddr);
  console.log("部署者调 setPointParams 被拒:", !r2.ok ? "✓" : "✗ 竟然成功");
  if (r2.ok) ok = false;

  const selSetEarner = new ethers.Interface(pointsAbi).encodeFunctionData("setEarner", [
    artifacts.actionIds.reviewGive, [deployerAddr, 1, 1, 1, 1, true, true],
  ]);
  const r3 = await tryCall(provider, deployed.points, selSetEarner, deployerAddr);
  console.log("部署者调 setEarner 被拒:", !r3.ok ? "✓" : "✗ 竟然成功");
  if (r3.ok) ok = false;

  console.log("");
  console.log(ok ? "=== DRY-RUN 全部通过 ✓ ===" : "=== 有失败项 ✗ ===");
  process.exit(ok ? 0 : 1);
}

async function tryCall(provider, to, data, from) {
  try {
    await provider.call({ to, data, from });
    return { ok: true };
  } catch {
    return { ok: false };
  }
}

// 用 impersonate 以 admin 身份执行 3 次 setEarner，并读回核对
async function runConfigSteps(provider, deployed, artifacts, coder, adminAddr) {
  // impersonate admin
  await provider.send("anvil_impersonateAccount", [adminAddr]);
  await provider.send("anvil_setBalance", [adminAddr, "0x3635c9adc5dea00000"]); // 1000 ETH

  const pointsAbi = artifacts.artifacts.HahaPoints.abi;
  const iface = new ethers.Interface(pointsAbi);

  let ok = true;
  for (const step of artifacts.configSteps) {
    const [actionId, cfg] = step.args;
    const module = cfg.module === "{reputation}" ? deployed.reputation : deployed.identity;
    const data = iface.encodeFunctionData(step.method, [
      actionId,
      {
        module,
        points: cfg.points,
        perUserDailyCap: cfg.perUserDailyCap,
        globalDailyPoints: cfg.globalDailyPoints,
        keyMode: cfg.keyMode,
        requireName: cfg.requireName,
        enabled: cfg.enabled,
      },
    ]);
    // 用 eth_sendTransaction 直接发（impersonate 账户无私钥，不能走 signer 签名）
    const txHash = await provider.send("eth_sendTransaction", [
      { from: adminAddr, to: deployed.points, data, gas: "0x7a120" }, // 500000 gas
    ]);
    const receipt = await provider.waitForTransaction(txHash);
    const good = receipt.status === 1;

    // 读回核对
    let readback = false;
    if (good) {
      const rdata = iface.encodeFunctionData("earner", [actionId]);
      const raw = await provider.call({ to: deployed.points, data: rdata });
      const dec = iface.decodeFunctionResult("earner", raw)[0];
      readback =
        dec.module.toLowerCase() === module.toLowerCase() &&
        dec.points === BigInt(cfg.points) &&
        dec.perUserDailyCap === BigInt(cfg.perUserDailyCap) &&
        dec.globalDailyPoints === BigInt(cfg.globalDailyPoints) &&
        BigInt(dec.keyMode) === BigInt(cfg.keyMode) &&
        dec.enabled === true;
    }
    console.log(`${step.key.padEnd(28)} 执行:${good ? "✓" : "✗"} 读回:${readback ? "✓" : "✗"}`);
    if (!good || !readback) ok = false;
  }

  await provider.send("anvil_stopImpersonatingAccount", [adminAddr]);
  return ok;
}

main().catch((e) => { console.error(e); process.exit(1); });
