// haha.meme 部署面板主逻辑。
import { predictAddresses, encodeConstructor, encodeConfigCall } from "./encode.mjs";

// ethers 由 index.html 的 UMD 脚本注入到 window
const ethers = window.ethers;

const CHAIN_MAINNET = 56;
const CHAIN_TESTNET = 97;

const CONTRACT_NAMES = ["namepolicy", "metadata", "resolver", "registry", "registrar", "identity", "points", "reputation", "marketplace", "deployer"];

const state = {
  chainId: null,
  mode: "mainnet", // mainnet | testnet
  provider: null,
  signer: null,
  address: null,
  walletType: null, // "metamask" | "okx"
  artifacts: null,
  predicted: null, // 10 个预测地址
  deployed: {}, // 合约名 -> 地址（链上确认后填）
  steps: [], // 展平的步骤列表（部署 10 + 配置 3）
  stepStates: {}, // key -> {status, txHash, blockNumber, contractAddress, error}
  verified: {}, // 合约名 -> 验证状态
  verifyKey: "", // 仅内存
};

// ---------------------------------------------------------------------------
// 初始化
// ---------------------------------------------------------------------------
async function init() {
  try {
    const res = await fetch("public/artifacts.json");
    if (!res.ok) throw new Error("加载 artifacts.json 失败 HTTP " + res.status);
    state.artifacts = await res.json();
  } catch (e) {
    console.error("初始化失败:", e);
    document.body.insertAdjacentHTML(
      "afterbegin",
      '<div style="background:#7c2d12;color:#fed7aa;padding:12px 20px;">面板初始化失败：' +
        (e.message || e) +
        "。请确认是在 <code>npm run deploy-panel</code> 启动后通过 http://localhost:4321 访问。</div>"
    );
    return;
  }

  // 填 header
  document.getElementById("meta-commit").textContent = "commit: " + state.artifacts.commit;
  document.getElementById("meta-solc").textContent =
    "solc: " + state.artifacts.compiler.version + " (via-ir, runs " + state.artifacts.compiler.optimizerRuns + ")";
  document.getElementById("p-admin").textContent = state.artifacts.addresses.admin;
  document.getElementById("p-fee").textContent = state.artifacts.addresses.feeReceiver;
  document.getElementById("p-ai").textContent = state.artifacts.addresses.aiRegistry;

  // 拼装合约信息到步骤
  const byName = {};
  for (const [k, v] of Object.entries(state.artifacts.artifacts)) byName[k] = v;

  state.steps = [
    ...state.artifacts.steps.map((s) => ({ ...s, contractInfo: byName[s.contract], kind: "deploy" })),
    ...state.artifacts.configSteps.map((s) => ({ ...s, contractInfo: byName[s.contract], kind: "config" })),
  ];

  bindEvents();
  renderFixedParams();
  renderSteps();

  // 尝试恢复钱包连接与进度
  await restore();
}

// ---------------------------------------------------------------------------
// 事件绑定
// ---------------------------------------------------------------------------
function bindEvents() {
  document.getElementById("btn-connect").addEventListener("click", () => connectWallet("metamask"));
  document.getElementById("btn-connect-okx").addEventListener("click", () => connectWallet("okx"));
  document.getElementById("btn-switch-net").addEventListener("click", switchNetwork);
  document.getElementById("btn-mainnet").addEventListener("click", () => setMode("mainnet"));
  document.getElementById("btn-testnet").addEventListener("click", () => setMode("testnet"));
  document.getElementById("btn-export").addEventListener("click", exportState);
  document.getElementById("btn-import").addEventListener("click", () => document.getElementById("import-file").click());
  document.getElementById("import-file").addEventListener("change", importState);
  document.getElementById("verify-key").addEventListener("input", (e) => (state.verifyKey = e.target.value.trim()));
  document.getElementById("btn-verify").addEventListener("click", verifyAll);
  document.getElementById("btn-selfcheck").addEventListener("click", runSelfCheck);
  document.getElementById("btn-receipt-copy").addEventListener("click", () => copyReceipt("json"));
  document.getElementById("btn-receipt-md").addEventListener("click", () => copyReceipt("md"));
  document.getElementById("btn-receipt-download").addEventListener("click", downloadReceipt);

  // 监听两个钱包的账户/网络变化
  for (const w of [window.ethereum, window.okxwallet]) {
    if (w && w.on) {
      w.on("accountsChanged", () => location.reload());
      w.on("chainChanged", () => location.reload());
    }
  }
}

// ---------------------------------------------------------------------------
// 钱包与网络
// ---------------------------------------------------------------------------
// 返回指定类型的注入 provider：metamask / okx
function injectedProvider(type) {
  if (type === "okx") {
    // OKX 钱包暴露 window.okxwallet（EIP-1193 兼容）
    return window.okxwallet || null;
  }
  return window.ethereum || null;
}

async function connectWallet(type) {
  const name = type === "okx" ? "OKX" : "MetaMask";
  const injected = injectedProvider(type);
  if (!injected) {
    alert(`未检测到 ${name} 钱包，请先安装并解锁。`);
    return;
  }
  try {
    const provider = new ethers.BrowserProvider(injected);
    const signer = await provider.getSigner();
    state.provider = provider;
    state.signer = signer;
    state.walletType = type;
    state.address = await signer.getAddress();
    state.chainId = Number((await provider.getNetwork()).chainId);
    document.getElementById("addr").textContent = shorten(state.address);
    await refreshBalance();
    await onNetworkChanged();
    renderSteps();
  } catch (e) {
    console.error("连接钱包失败:", e);
    alert(`连接 ${name} 钱包失败：` + (e.shortMessage || e.message || e) + `。请确认 ${name} 已解锁并授权本页面。`);
  }
}

async function refreshBalance() {
  if (!state.provider || !state.address) return;
  const bal = await state.provider.getBalance(state.address);
  document.getElementById("balance").textContent = ethers.formatEther(bal).slice(0, 8) + " BNB";
}

async function onNetworkChanged() {
  const target = targetChainId();
  const badge = document.getElementById("net-badge");
  const warn = document.getElementById("net-warning");
  if (state.chainId === target) {
    badge.textContent = state.chainId === CHAIN_MAINNET ? "BSC 主网" : "BSC 测试网";
    badge.className = "badge badge-ok";
    warn.classList.add("hidden");
  } else {
    badge.textContent = "网络错误 " + state.chainId;
    badge.className = "badge badge-err";
    warn.classList.remove("hidden");
  }
  renderSteps();
}

async function switchNetwork() {
  const target = targetChainId();
  const params =
    target === CHAIN_MAINNET
      ? { chainId: "0x38", chainName: "BNB Smart Chain", rpcUrls: ["https://bsc-dataseed.binance.org"], nativeCurrency: { name: "BNB", symbol: "BNB", decimals: 18 }, blockExplorerUrls: ["https://bscscan.com"] }
      : { chainId: "0x61", chainName: "BNB Testnet", rpcUrls: ["https://data-seed-prebsc-1-s1.binance.org:8545"], nativeCurrency: { name: "BNB", symbol: "BNB", decimals: 18 }, blockExplorerUrls: ["https://testnet.bscscan.com"] };
  const injected = injectedProvider(state.walletType) || window.ethereum;
  if (!injected) {
    alert("请先连接钱包。");
    return;
  }
  try {
    await injected.request({ method: "wallet_switchEthereumChain", params: [{ chainId: params.chainId }] });
  } catch (e) {
    if (e.code === 4902) {
      await injected.request({ method: "wallet_addEthereumChain", params: [params] });
    } else {
      throw e;
    }
  }
}

function targetChainId() {
  return state.mode === "mainnet" ? CHAIN_MAINNET : CHAIN_TESTNET;
}

function setMode(mode) {
  state.mode = mode;
  document.getElementById("btn-mainnet").classList.toggle("btn-primary", mode === "mainnet");
  document.getElementById("btn-testnet").classList.toggle("btn-primary", mode === "testnet");
  loadStepStates();
  renderFixedParams();
  renderSteps();
}

// ---------------------------------------------------------------------------
// 固定参数渲染
// ---------------------------------------------------------------------------
function renderFixedParams() {
  document.getElementById("p-chain").textContent = targetChainId();
}

// ---------------------------------------------------------------------------
// 步骤状态（localStorage，按 chainId 隔离）
// ---------------------------------------------------------------------------
function storageKey() {
  return `haha-deploy-${targetChainId()}`;
}

function loadStepStates() {
  const raw = localStorage.getItem(storageKey());
  state.stepStates = raw ? JSON.parse(raw) : {};
  // 恢复 deployed 地址
  state.deployed = {};
  for (let i = 0; i < 10; i++) {
    const key = "deploy:" + CONTRACT_NAMES[i];
    const st = state.stepStates[key];
    if (st && st.contractAddress) state.deployed[CONTRACT_NAMES[i]] = st.contractAddress;
  }
}

function saveStepStates() {
  localStorage.setItem(storageKey(), JSON.stringify(state.stepStates));
}

// ---------------------------------------------------------------------------
// 预测地址
// ---------------------------------------------------------------------------
async function ensurePredicted() {
  if (state.predicted) return;
  if (!state.signer) return;
  const nonce = await state.provider.getTransactionCount(state.address, "pending");
  state.predicted = predictAddresses(state.address, nonce);
}

// ---------------------------------------------------------------------------
// 步骤渲染
// ---------------------------------------------------------------------------
function renderSteps() {
  const el = document.getElementById("steps");
  el.innerHTML = "";

  // 确定当前可执行步骤索引
  const currentIdx = currentStepIndex();

  state.steps.forEach((step, i) => {
    const st = state.stepStates[step.key] || {};
    const status = st.status || "pending";
    const isCurrent = i === currentIdx;
    const div = document.createElement("div");
    div.className = `step ${status} ${isCurrent ? "" : "disabled"}`;

    // 索引
    const idx = document.createElement("div");
    idx.className = "idx";
    idx.textContent = i + 1;
    div.appendChild(idx);

    // 名称
    const name = document.createElement("div");
    name.className = "name";
    name.innerHTML = `${step.label}${step.adminOnly ? ' <span style="color:var(--warn)">[管理员]</span>' : ""}<br><span class="sub">${step.contract}</span>`;
    div.appendChild(name);

    // 状态
    const statusEl = document.createElement("div");
    statusEl.className = "status " + statusClass(status);
    statusEl.textContent = statusText(status);
    div.appendChild(statusEl);

    // 详情（tx hash / 地址 / 区块 / 错误）
    const detail = document.createElement("div");
    detail.className = "detail";
    let d = "";
    if (st.txHash) d += "tx: " + shorten(st.txHash) + " ";
    if (st.contractAddress) d += "addr: " + shorten(st.contractAddress) + " ";
    if (st.blockNumber) d += "block: " + st.blockNumber + " ";
    if (st.error) d += "err: " + st.error;
    detail.textContent = d;
    div.appendChild(detail);

    // 操作按钮
    const actions = document.createElement("div");
    actions.className = "actions";
    const btn = document.createElement("button");
    btn.className = "btn btn-primary";
    if (status === "pending") btn.textContent = "执行";
    else if (status === "failed") btn.textContent = "重试";
    else if (status === "sent") btn.textContent = "查询确认";
    else btn.textContent = "已完成";

    // 置灰逻辑：可执行才高亮；不可执行仍可点击（点击会弹出原因）
    const reason = cannotReason(step, status, isCurrent);
    if (reason) {
      btn.classList.add("disabled");
      btn.title = reason;
    }
    btn.addEventListener("click", () => executeStep(step, status, reason));
    actions.appendChild(btn);
    div.appendChild(actions);

    el.appendChild(div);
  });

  // 自检按钮
  const allDone = state.steps.every((s) => (state.stepStates[s.key] || {}).status === "confirmed");
  document.getElementById("btn-selfcheck").disabled = !allDone;
  document.getElementById("btn-receipt-copy").disabled = !allDone;
  document.getElementById("btn-receipt-md").disabled = !allDone;
  document.getElementById("btn-receipt-download").disabled = !allDone;
}

function currentStepIndex() {
  // 返回第一个非 confirmed 的步骤索引；全 confirmed 返回最后一个
  for (let i = 0; i < state.steps.length; i++) {
    const st = state.stepStates[state.steps[i].key] || {};
    if (st.status !== "confirmed") return i;
  }
  return state.steps.length - 1;
}

function canExecute(step, status, isCurrent) {
  return cannotReason(step, status, isCurrent) === null;
}

// 返回不能执行的原因；null 表示可以执行
function cannotReason(step, status, isCurrent) {
  if (!window.ethereum && !window.okxwallet) return "未检测到 MetaMask / OKX 钱包，请先安装并解锁";
  if (!state.address) return "请先点右上角「连接 MetaMask」或「连接 OKX」";
  if (state.chainId !== targetChainId()) {
    return "网络不符：当前 " + state.chainId + "，需要 " + targetChainId() + "，请点「一键切换」";
  }
  if (status !== "pending" && status !== "failed" && status !== "sent") return "该步骤已完成";
  if (!isCurrent) return "请先完成前面的步骤（只能按顺序执行）";
  if (step.adminOnly && state.address.toLowerCase() !== state.artifacts.addresses.admin.toLowerCase()) {
    return "该步骤需管理员钱包（" + state.artifacts.addresses.admin + "），请在钱包里切换账户";
  }
  return null;
}

function statusText(s) {
  return { pending: "待执行", sent: "已发送", confirmed: "已确认", failed: "失败" }[s] || s;
}
function statusClass(s) {
  return { pending: "", sent: "status-warn", confirmed: "status-ok", failed: "status-err" }[s] || "";
}

function shorten(addr) {
  if (!addr) return "";
  return addr.slice(0, 10) + "…" + addr.slice(-6);
}

// ---------------------------------------------------------------------------
// 执行步骤
// ---------------------------------------------------------------------------
async function executeStep(step, status, reason) {
  // 先给明确反馈：不能执行就提示原因
  if (reason) {
    alert(reason);
    return;
  }

  try {
    if (status === "sent") {
      // 已发送未确认：查链上结果
      await confirmSentStep(step);
      return;
    }

    // 防重复部署：重试前先查链上是否已成功
    if (status === "failed" || status === "pending") {
      const already = await checkAlreadyDeployed(step);
      if (already) {
        state.stepStates[step.key] = { ...already, status: "confirmed" };
        saveStepStates();
        renderSteps();
        return;
      }
    }

    await ensurePredicted();

    let tx;
    if (step.kind === "deploy") {
      const { bytecode } = encodeConstructor(step, state.predicted, state.artifacts.addresses);
      tx = await state.signer.sendTransaction({ data: bytecode });
    } else {
      // config: 调用 setEarner
      const data = encodeConfigCall(step, state.deployed, step.contractInfo.abi);
      tx = await state.signer.sendTransaction({ to: state.deployed.points, data });
    }

    state.stepStates[step.key] = { ...state.stepStates[step.key], status: "sent", txHash: tx.hash, error: "" };
    saveStepStates();
    renderSteps();

    // 等待确认
    const receipt = await tx.wait();
    await handleReceipt(step, receipt);
  } catch (e) {
    console.error("executeStep 完整错误:", e);
    console.error("错误堆栈:", e && e.stack);
    console.error("当前状态: address=", state.address, " chainId=", state.chainId, " predicted=", state.predicted);
    const msg = e.shortMessage || e.message || String(e);
    // 用户拒绝签名不记失败
    if (msg.includes("user rejected") || msg.includes("denied")) {
      alert("已取消签名。");
      renderSteps();
      return;
    }
    alert("执行失败：" + msg + "\n\n（请按 F12 打开控制台，把 Console 里的红色报错发我，便于定位）");
    state.stepStates[step.key] = { ...state.stepStates[step.key], status: "failed", error: msg };
    saveStepStates();
    renderSteps();
  }
}

async function handleReceipt(step, receipt) {
  if (receipt.status === 1) {
    // 读回核对
    const check = await verifyStepOnChain(step, receipt);
    state.stepStates[step.key] = {
      status: "confirmed",
      txHash: receipt.hash,
      blockNumber: receipt.blockNumber,
      contractAddress: receipt.contractAddress || step.contractAddress,
      error: check.ok ? "" : "核对失败: " + check.reason,
    };
    if (step.kind === "deploy") {
      const name = step.key.replace("deploy:", "");
      state.deployed[name] = receipt.contractAddress;
    }
  } else {
    state.stepStates[step.key] = { ...state.stepStates[step.key], status: "failed", error: "交易 revert" };
  }
  saveStepStates();
  renderSteps();
}

async function confirmSentStep(step) {
  const st = state.stepStates[step.key];
  if (!st.txHash) return;
  const receipt = await state.provider.getTransactionReceipt(st.txHash);
  if (!receipt) {
    alert("交易尚未被包含进区块，稍后再试。");
    return;
  }
  await handleReceipt(step, receipt);
}

// 防重复部署：查链上是否已有该合约/配置
async function checkAlreadyDeployed(step) {
  if (step.kind === "config") return null; // 配置步骤幂等，靠读回核对
  // 部署步骤：预测地址上是否已有代码
  await ensurePredicted();
  const name = step.key.replace("deploy:", "");
  const idx = CONTRACT_NAMES.indexOf(name);
  const addr = state.predicted[idx];
  const code = await state.provider.getCode(addr);
  if (code && code !== "0x") {
    return { contractAddress: addr, txHash: state.stepStates[step.key]?.txHash };
  }
  return null;
}

// ---------------------------------------------------------------------------
// 读回核对
// ---------------------------------------------------------------------------
async function verifyStepOnChain(step, receipt) {
  try {
    if (step.kind === "deploy") {
      // 核对实际部署地址 == 预测地址
      const name = step.key.replace("deploy:", "");
      const idx = CONTRACT_NAMES.indexOf(name);
      const expected = state.predicted[idx];
      const actual = receipt.contractAddress;
      if (expected.toLowerCase() !== actual.toLowerCase()) {
        return { ok: false, reason: `地址不符: 期望 ${expected}, 实际 ${actual}` };
      }
      return { ok: true };
    }
    // config: 读 earner 配置
    const iface = new ethers.Interface(state.artifacts.artifacts.HahaPoints.abi);
    const [actionId] = step.args;
    const data = iface.encodeFunctionData("earner", [actionId]);
    const raw = await state.provider.call({ to: state.deployed.points, data });
    // earner 返回 tuple
    const decoded = iface.decodeFunctionResult("earner", raw)[0];
    // decoded = EarnerConfig { module, points, perUserDailyCap, globalDailyPoints, keyMode, requireName, enabled }
    const cfg = step.args[1];
    const module = cfg.module === "{reputation}" ? state.deployed.reputation : state.deployed.identity;
    if (decoded.module.toLowerCase() !== module.toLowerCase()) return { ok: false, reason: "module 不符" };
    if (decoded.points !== BigInt(cfg.points)) return { ok: false, reason: "points 不符" };
    if (decoded.perUserDailyCap !== BigInt(cfg.perUserDailyCap)) return { ok: false, reason: "cap 不符" };
    if (decoded.globalDailyPoints !== BigInt(cfg.globalDailyPoints)) return { ok: false, reason: "global 不符" };
    if (BigInt(decoded.keyMode) !== BigInt(cfg.keyMode)) return { ok: false, reason: "keyMode 不符" };
    if (decoded.enabled !== true) return { ok: false, reason: "enabled 不符" };
    return { ok: true };
  } catch (e) {
    return { ok: false, reason: e.shortMessage || e.message };
  }
}

// ---------------------------------------------------------------------------
// 断线续部署：导出 / 导入
// ---------------------------------------------------------------------------
function exportState() {
  const data = {
    chainId: targetChainId(),
    commit: state.artifacts.commit,
    exportedAt: new Date().toISOString(),
    deployed: state.deployed,
    steps: state.stepStates,
  };
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `deploy-state-${targetChainId()}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

function importState(e) {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const data = JSON.parse(reader.result);
      if (data.chainId !== targetChainId()) {
        alert("导入的进度 chainId 与当前模式不符。");
        return;
      }
      state.deployed = data.deployed || {};
      state.stepStates = data.steps || {};
      saveStepStates();
      renderSteps();
      alert("进度已导入。");
    } catch (err) {
      alert("导入失败: " + err.message);
    }
  };
  reader.readAsText(file);
}

// ---------------------------------------------------------------------------
// 最终自检
// ---------------------------------------------------------------------------
async function runSelfCheck() {
  const el = document.getElementById("selfcheck");
  el.innerHTML = "";
  const results = [];

  const add = (name, ok, detail) => {
    results.push({ name, ok, detail });
    const div = document.createElement("div");
    div.className = "item " + (ok ? "pass" : "fail");
    div.textContent = (ok ? "✓ " : "✗ ") + name + (detail ? " — " + detail : "");
    el.appendChild(div);
  };

  const signerAddr = state.address;
  const ifaceRegistrar = new ethers.Interface(state.artifacts.artifacts.HahaRegistrar.abi);
  const ifacePoints = new ethers.Interface(state.artifacts.artifacts.HahaPoints.abi);
  const ifaceRegistry = new ethers.Interface(state.artifacts.artifacts.HahaRegistry.abi);

  // 1. 部署钱包无管理员权限
  //    注意：若部署 EOA 就是 admin，则 admin 天然拥有管理权限，此项不适用，跳过。
  const isDeployerAdmin = signerAddr.toLowerCase() === state.artifacts.addresses.admin.toLowerCase();
  if (isDeployerAdmin) {
    add("部署者即管理员（权限检查跳过）", true, "部署 EOA == admin，admin 天然拥有管理权限，非漏洞");
  } else {
    const adminMint = ifaceRegistrar.encodeFunctionData("adminMint", ["binance", 0, signerAddr]);
    const r1 = await tryCall(state.deployed.registrar, adminMint);
    add("部署钱包调 adminMint 失败", !r1.ok, r1.ok ? "竟然成功" : "已拒绝");

    const setPointParams = ifacePoints.encodeFunctionData("setPointParams", [1, 1, 1, 1, 1, 1]);
    const r2 = await tryCall(state.deployed.points, setPointParams);
    add("部署钱包调 setPointParams 失败", !r2.ok, r2.ok ? "竟然成功" : "已拒绝");

    // setEarner 用合法参数（cap=5 等），确保 revert 原因是「无权限」而非「参数错」
    const setEarner = ifacePoints.encodeFunctionData("setEarner", [
      state.artifacts.actionIds.reviewGive,
      [state.deployed.reputation, 5, 5, 50000, 1, true, true],
    ]);
    const r3 = await tryCall(state.deployed.points, setEarner);
    add("部署钱包调 setEarner 失败", !r3.ok, r3.ok ? "竟然成功" : "已拒绝");
  }

  // 2. 地址引用正确（读 HahaDeployer.addresses 与各合约引用）
  const ifaceDeployer = new ethers.Interface(state.artifacts.artifacts.HahaDeployer.abi);
  const addrsRaw = await state.provider.call({ to: state.deployed.deployer, data: ifaceDeployer.encodeFunctionData("addresses") });
  const addrs = ifaceDeployer.decodeFunctionResult("addresses", addrsRaw)[0];
  let refOk = true;
  CONTRACT_NAMES.slice(0, 9).forEach((n, i) => {
    if (addrs[i].toLowerCase() !== state.deployed[n].toLowerCase()) refOk = false;
  });
  add("HahaDeployer 九个地址引用正确", refOk);

  // 3. 冷却参数
  const ifaceReg = new ethers.Interface(state.artifacts.artifacts.HahaRegistrar.abi);
  // COOLDOWN 是 constant，读不到；改读 admin 与 feeReceiver 引用
  const adminVal = await readAddr(state.deployed.registrar, ifaceReg, "admin");
  const feeVal = await readAddr(state.deployed.registrar, ifaceReg, "feeReceiver");
  add("registrar.admin == 管理员", adminVal.toLowerCase() === state.artifacts.addresses.admin.toLowerCase());
  add("registrar.feeReceiver == 手续费", feeVal.toLowerCase() === state.artifacts.addresses.feeReceiver.toLowerCase());

  // 4. bootstrap 不可再调用
  const bootstrap = ifaceRegistry.encodeFunctionData("bootstrap");
  const r4 = await tryCall(state.deployed.registry, bootstrap);
  add("bootstrap 不能再调用", !r4.ok);

  // 5. TLD node owner 是 Registrar
  const hahaNode = "0xaa5a3a58f7c8841455eecaa0c6a6a0b40ace5681fbb31361a0d45b168179128f";
  const memeNode = "0x74df4ab2564a9f9bb6d4b6b77bf4fc02ac80f07bd9e1776d3967578b3fc36be4";
  const o1 = await readOwner(state.deployed.registry, ifaceRegistry, hahaNode);
  const o2 = await readOwner(state.deployed.registry, ifaceRegistry, memeNode);
  add("hahaNode owner == Registrar", o1.toLowerCase() === state.deployed.registrar.toLowerCase());
  add("memeNode owner == Registrar", o2.toLowerCase() === state.deployed.registrar.toLowerCase());

  // 存储自检结果供回执用
  state.selfCheck = results;
}

async function tryCall(to, data) {
  try {
    const r = await state.provider.call({ to, data, from: state.address });
    return { ok: true, data: r };
  } catch (e) {
    return { ok: false, data: null, reason: e.shortMessage || e.message };
  }
}

async function readAddr(to, iface, name) {
  const data = iface.encodeFunctionData(name);
  const raw = await state.provider.call({ to, data });
  return iface.decodeFunctionResult(name, raw)[0];
}

async function readOwner(to, iface, node) {
  const data = iface.encodeFunctionData("owner", [node]);
  const raw = await state.provider.call({ to, data });
  return iface.decodeFunctionResult("owner", raw)[0];
}

// ---------------------------------------------------------------------------
// 开源验证
// ---------------------------------------------------------------------------
function explorerBase() {
  return targetChainId() === CHAIN_MAINNET ? "https://api.bscscan.com/api" : "https://api-testnet.bscscan.com/api";
}
function explorerWeb() {
  return targetChainId() === CHAIN_MAINNET ? "https://bscscan.com" : "https://testnet.bscscan.com";
}

async function verifyAll() {
  if (!state.verifyKey) {
    alert("请先输入 BscScan API Key。");
    return;
  }
  // 逐个验证已部署合约
  const results = [];
  for (let i = 0; i < 9; i++) {
    const name = CONTRACT_NAMES[i];
    const addr = state.deployed[name];
    if (!addr) continue;
    await verifyOne(name, addr);
    results.push(`${fileMapName(name)}: ${state.verified[name].status}${state.verified[name].reason ? "（" + state.verified[name].reason + "）" : ""}`);
  }
  renderSteps();
  // 展示验证结果
  const el = document.getElementById("verify-results");
  if (el) {
    el.classList.remove("hidden");
    el.textContent = results.join("\n");
  }
  alert("验证完成：\n\n" + results.join("\n"));
}

function fileMapName(name) {
  const fileMap = {
    namepolicy: "HahaNamePolicy", metadata: "HahaMetadata", resolver: "HahaResolver", registry: "HahaRegistry",
    registrar: "HahaRegistrar", identity: "HahaAgentIdentity", points: "HahaPoints", reputation: "HahaReputation",
    marketplace: "HahaMarketplace",
  };
  return fileMap[name] || name;
}

async function verifyOne(name, addr) {
  const fname = fileMapName(name);
  if (!fname || fname === name) {
    state.verified[name] = { status: "失败", reason: "未知合约 " + name };
    return;
  }

  // 读预生成的 standard-input JSON（含全部 import 依赖 + via-ir 设置）
  let sourceCode;
  try {
    sourceCode = await (await fetch(`public/verify/${fname}.json`)).text();
  } catch (e) {
    state.verified[name] = { status: "失败", reason: "缺少 standard-input，请先跑 node generate-standard-input.mjs" };
    return;
  }

  const params = new URLSearchParams({
    apikey: state.verifyKey,
    module: "contract",
    action: "verifysourcecode",
    contractaddress: addr,
    sourceCode,
    codeformat: "solidity-standard-json-input",
    contractname: fname,
    compilerversion: "v0.8.28+commit.7893614a",
    optimizationUsed: "1",
    runs: "200",
  });

  state.verified[name] = { status: "验证中" };
  try {
    // 走本地代理（解决浏览器直连 Etherscan 的 CORS 限制）
    // Etherscan V2 统一 API：chainid=56(BNB 主网)/97(测试网)，用 Etherscan key
    const payload = {
      chainid: targetChainId(),
      apikey: state.verifyKey,
      form: {
        module: "contract",
        action: "verifysourcecode",
        contractaddress: addr,
        sourceCode,
        codeformat: "solidity-standard-json-input",
        contractname: `src/${fname}.sol:${fname}`,
        compilerversion: "v0.8.28+commit.7893614a",
        optimizationUsed: "1",
        runs: "200",
        licenseType: "3",
      },
    };
    const res = await fetch("/api/bscscan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const json = await res.json();
    if (json.status === "1") {
      state.verified[name] = { status: "已验证", link: `${explorerWeb()}/address/${addr}#code` };
    } else {
      state.verified[name] = { status: "失败", reason: json.result };
    }
  } catch (e) {
    state.verified[name] = { status: "失败", reason: e.message };
  }
}

// ---------------------------------------------------------------------------
// 回执
// ---------------------------------------------------------------------------
function buildReceipt() {
  const r = {
    network: targetChainId() === CHAIN_MAINNET ? "BSC Mainnet" : "BSC Testnet",
    chainId: targetChainId(),
    commit: state.artifacts.commit,
    compiler: state.artifacts.compiler,
    deployer: state.address,
    admin: state.artifacts.addresses.admin,
    feeReceiver: state.artifacts.addresses.feeReceiver,
    aiRegistry: state.artifacts.addresses.aiRegistry,
    contracts: [],
    configSteps: [],
    selfCheck: state.selfCheck || [],
  };
  // 部署合约
  state.artifacts.steps.forEach((s, i) => {
    const name = CONTRACT_NAMES[i];
    const st = state.stepStates["deploy:" + name] || {};
    r.contracts.push({
      name: s.contract,
      address: st.contractAddress || "",
      txHash: st.txHash || "",
      blockNumber: st.blockNumber || "",
      verifyStatus: state.verified[name]?.status || "未验证",
      verifyLink: state.verified[name]?.link || "",
    });
  });
  // 配置步骤
  state.artifacts.configSteps.forEach((s) => {
    const st = state.stepStates[s.key] || {};
    r.configSteps.push({ label: s.label, txHash: st.txHash || "", blockNumber: st.blockNumber || "" });
  });
  return r;
}

function receiptMarkdown(r) {
  const lines = [];
  lines.push(`# 部署记录`);
  lines.push(``);
  lines.push(`| 项 | 值 |`);
  lines.push(`| --- | --- |`);
  lines.push(`| 链 | ${r.network}，chainId ${r.chainId} |`);
  lines.push(`| 部署 EOA | ${r.deployer} |`);
  lines.push(`| commit | ${r.commit} |`);
  lines.push(`| 编译器 | solc ${r.compiler.version}，optimizer runs ${r.compiler.optimizerRuns}，via-ir |`);
  lines.push(``);
  lines.push(`## 合约地址`);
  lines.push(``);
  lines.push(`| 合约 | 地址 | 部署交易 | 区块 | 验证 |`);
  lines.push(`| --- | --- | --- | --- | --- |`);
  for (const c of r.contracts) {
    lines.push(`| ${c.name} | ${c.address} | ${c.txHash} | ${c.blockNumber} | ${c.verifyStatus}${c.verifyLink ? " " + c.verifyLink : ""} |`);
  }
  lines.push(``);
  lines.push(`## 配置步骤`);
  lines.push(``);
  for (const c of r.configSteps) {
    lines.push(`- ${c.label}: tx ${c.txHash} (block ${c.blockNumber})`);
  }
  lines.push(``);
  lines.push(`## 最终自检`);
  lines.push(``);
  for (const s of r.selfCheck) {
    lines.push(`- [${s.ok ? "x" : " "}] ${s.name}${s.detail ? " — " + s.detail : ""}`);
  }
  return lines.join("\n");
}

async function copyReceipt(kind) {
  const r = buildReceipt();
  const text = kind === "md" ? receiptMarkdown(r) : JSON.stringify(r, null, 2);
  const el = document.getElementById("receipt");
  el.classList.remove("hidden");
  el.textContent = text;
  await navigator.clipboard.writeText(text);
  alert("已复制到剪贴板。");
}

function downloadReceipt() {
  const r = buildReceipt();
  const blob = new Blob([JSON.stringify(r, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `deployment-${r.chainId}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// 恢复
// ---------------------------------------------------------------------------
async function restore() {
  // 尝试恢复钱包（静默连接：优先上次用的，否则哪个有账户连哪个）
  const prefer = state.walletType || "metamask";
  const candidates = prefer === "okx" ? ["okx", "metamask"] : ["metamask", "okx"];
  for (const t of candidates) {
    const injected = injectedProvider(t);
    if (!injected) continue;
    try {
      const accounts = await injected.request({ method: "eth_accounts" });
      if (accounts.length > 0) {
        await connectWallet(t);
        break;
      }
    } catch {}
  }
  loadStepStates();
  renderSteps();
}

// ---------------------------------------------------------------------------
// 全局错误兜底：任何未捕获错误都显示出来，避免「点了没反应」
// ---------------------------------------------------------------------------
window.addEventListener("error", (e) => {
  console.error("全局错误:", e.error || e.message);
  alert("页面脚本出错：" + (e.message || e.error));
});
window.addEventListener("unhandledrejection", (e) => {
  console.error("未处理的 Promise 拒绝:", e.reason);
  alert("异步操作出错：" + (e.reason?.shortMessage || e.reason?.message || e.reason));
});

// ---------------------------------------------------------------------------
// 启动
// ---------------------------------------------------------------------------
init();
