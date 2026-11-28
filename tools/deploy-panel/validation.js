// HahaValidation 部署面板逻辑（G13 验证注册表）。
// 单合约部署：构造参数固定 admin + identity。部署后读链核对，支持一键开源。

const ethers = window.ethers;

const CHAIN_MAINNET = 56;
const CHAIN_TESTNET = 97;

// 固定构造参数（与 validation-registry-plan.md §2.1/§4.1 一致，不可改）
const ADMIN = "0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7"; // = HahaRegistrar 的 admin
const IDENTITY = "0x54A70BF81B288d41013D7b57c2Db0922f1E1a4d4"; // = HahaAgentIdentity
const DISPUTE_WINDOW_SECONDS = 3 * 86400; // 3 days

const state = {
  chainId: null,
  mode: "mainnet",
  provider: null,
  signer: null,
  address: null,
  walletType: null,
  abi: null,
  bytecode: null,
  commit: null,
  deployedAddr: null,
  stepState: {}, // { status, txHash, blockNumber, error }
  verified: null, // { status, link, reason }
  verifyKey: "",
  selfCheck: [],
};

// ---------------------------------------------------------------------------
// 初始化
// ---------------------------------------------------------------------------
async function init() {
  try {
    const [abiRes, bcRes] = await Promise.all([
      fetch("public/validation/HahaValidation.abi.json"),
      fetch("public/validation/HahaValidation.bytecode.json"),
    ]);
    if (!abiRes.ok || !bcRes.ok) throw new Error("加载产物失败");
    state.abi = await abiRes.json();
    const bc = await bcRes.json();
    state.bytecode = bc.bytecode;
    try {
      const git = await (await fetch("public/validation/handoff.json")).json();
      state.commit = git.specCommit;
    } catch {
      state.commit = "—";
    }
  } catch (e) {
    console.error("初始化失败:", e);
    document.body.insertAdjacentHTML(
      "afterbegin",
      '<div style="background:#7c2d12;color:#fed7aa;padding:12px 20px;">面板初始化失败：' +
        (e.message || e) +
        "。请确认是在 <code>npm run deploy-panel</code> 启动后访问。</div>"
    );
    return;
  }

  document.getElementById("meta-commit").textContent = "commit: " + state.commit;
  document.getElementById("p-admin").textContent = ADMIN;
  document.getElementById("p-identity").textContent = IDENTITY;

  bindEvents();
  renderFixedParams();
  renderSteps();
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
  document.getElementById("btn-verify").addEventListener("click", verifyOne);
  document.getElementById("btn-selfcheck").addEventListener("click", runSelfCheck);
  document.getElementById("btn-receipt-copy").addEventListener("click", () => copyReceipt("json"));
  document.getElementById("btn-receipt-md").addEventListener("click", () => copyReceipt("md"));
  document.getElementById("btn-receipt-download").addEventListener("click", downloadReceipt);

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
function injectedProvider(type) {
  if (type === "okx") return window.okxwallet || null;
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
  loadStepState();
  renderFixedParams();
  renderSteps();
}

function renderFixedParams() {
  document.getElementById("p-chain").textContent = targetChainId();
}

// ---------------------------------------------------------------------------
// 步骤状态（localStorage，按 chainId 隔离）
// ---------------------------------------------------------------------------
function storageKey() {
  return `haha-validation-deploy-${targetChainId()}`;
}

function loadStepState() {
  const raw = localStorage.getItem(storageKey());
  state.stepState = raw ? JSON.parse(raw) : {};
  state.deployedAddr = state.stepState.contractAddress || null;
}

function saveStepState() {
  localStorage.setItem(storageKey(), JSON.stringify(state.stepState));
}

// ---------------------------------------------------------------------------
// 步骤渲染
// ---------------------------------------------------------------------------
function renderSteps() {
  const el = document.getElementById("steps");
  el.innerHTML = "";

  const status = state.stepState.status || "pending";
  const div = document.createElement("div");
  div.className = `step ${status}`;

  const idx = document.createElement("div");
  idx.className = "idx";
  idx.textContent = "1";
  div.appendChild(idx);

  const name = document.createElement("div");
  name.className = "name";
  name.innerHTML = `部署 HahaValidation<br><span class="sub">HahaValidation</span>`;
  div.appendChild(name);

  const statusEl = document.createElement("div");
  statusEl.className = "status " + statusClass(status);
  statusEl.textContent = statusText(status);
  div.appendChild(statusEl);

  const detail = document.createElement("div");
  detail.className = "detail";
  let d = "";
  if (state.stepState.txHash) d += "tx: " + shorten(state.stepState.txHash) + " ";
  if (state.stepState.contractAddress) d += "addr: " + shorten(state.stepState.contractAddress) + " ";
  if (state.stepState.blockNumber) d += "block: " + state.stepState.blockNumber + " ";
  if (state.stepState.error) d += "err: " + state.stepState.error;
  detail.textContent = d;
  div.appendChild(detail);

  const actions = document.createElement("div");
  actions.className = "actions";
  const btn = document.createElement("button");
  btn.className = "btn btn-primary";
  if (status === "pending") btn.textContent = "执行部署";
  else if (status === "failed") btn.textContent = "重试";
  else if (status === "sent") btn.textContent = "查询确认";
  else btn.textContent = "已完成";

  const reason = cannotReason(status);
  if (reason) {
    btn.classList.add("disabled");
    btn.title = reason;
  }
  btn.addEventListener("click", () => executeDeploy(status, reason));
  actions.appendChild(btn);
  div.appendChild(actions);

  el.appendChild(div);

  // 自检/回执按钮
  const confirmed = status === "confirmed";
  document.getElementById("btn-selfcheck").disabled = !confirmed;
  document.getElementById("btn-receipt-copy").disabled = !confirmed;
  document.getElementById("btn-receipt-md").disabled = !confirmed;
  document.getElementById("btn-receipt-download").disabled = !confirmed;
}

function cannotReason(status) {
  if (!window.ethereum && !window.okxwallet) return "未检测到 MetaMask / OKX 钱包，请先安装并解锁";
  if (!state.address) return "请先点右上角「连接 MetaMask」或「连接 OKX」";
  if (state.chainId !== targetChainId()) {
    return "网络不符：当前 " + state.chainId + "，需要 " + targetChainId() + "，请点「一键切换」";
  }
  if (status !== "pending" && status !== "failed" && status !== "sent") return "该步骤已完成";
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
// 编码构造参数 + 部署
// ---------------------------------------------------------------------------
function encodeCreationCode() {
  // constructor(address admin_, address identity_)
  const coder = ethers.AbiCoder.defaultAbiCoder();
  const argsHex = coder.encode(["address", "address"], [ADMIN, IDENTITY]).slice(2);
  return state.bytecode + argsHex;
}

async function executeDeploy(status, reason) {
  if (reason) {
    alert(reason);
    return;
  }

  try {
    if (status === "sent") {
      await confirmSent();
      return;
    }

    // 防重复部署：查链上是否已部署过（localStorage 里的地址）
    if (state.deployedAddr) {
      const code = await state.provider.getCode(state.deployedAddr);
      if (code && code !== "0x") {
        state.stepState = { ...state.stepState, status: "confirmed" };
        saveStepState();
        renderSteps();
        refreshOverview();
        return;
      }
    }

    const bytecode = encodeCreationCode();
    const tx = await state.signer.sendTransaction({ data: bytecode });
    state.stepState = { ...state.stepState, status: "sent", txHash: tx.hash, error: "" };
    saveStepState();
    renderSteps();

    const receipt = await tx.wait();
    await handleReceipt(receipt);
  } catch (e) {
    console.error("部署失败:", e);
    const msg = e.shortMessage || e.message || String(e);
    if (msg.includes("user rejected") || msg.includes("denied")) {
      alert("已取消签名。");
      renderSteps();
      return;
    }
    alert("部署失败：" + msg);
    state.stepState = { ...state.stepState, status: "failed", error: msg };
    saveStepState();
    renderSteps();
  }
}

async function handleReceipt(receipt) {
  if (receipt.status === 1) {
    state.stepState = {
      status: "confirmed",
      txHash: receipt.hash,
      blockNumber: receipt.blockNumber,
      contractAddress: receipt.contractAddress,
      error: "",
    };
    state.deployedAddr = receipt.contractAddress;
  } else {
    state.stepState = { ...state.stepState, status: "failed", error: "交易 revert" };
  }
  saveStepState();
  renderSteps();
  refreshOverview();
}

async function confirmSent() {
  if (!state.stepState.txHash) return;
  const receipt = await state.provider.getTransactionReceipt(state.stepState.txHash);
  if (!receipt) {
    alert("交易尚未被包含进区块，稍后再试。");
    return;
  }
  await handleReceipt(receipt);
}

// ---------------------------------------------------------------------------
// 链上状态总览
// ---------------------------------------------------------------------------
async function refreshOverview() {
  const el = document.getElementById("overview");
  if (!state.provider || !state.deployedAddr) {
    el.innerHTML = '<p class="hint">连接钱包并部署后，这里实时读链显示合约状态。</p>';
    return;
  }
  try {
    const iface = new ethers.Interface(state.abi);
    const read = async (name, args = []) => {
      const data = iface.encodeFunctionData(name, args);
      const raw = await state.provider.call({ to: state.deployedAddr, data });
      return iface.decodeFunctionResult(name, raw);
    };

    const admin = (await read("admin"))[0];
    const identity = (await read("getIdentityRegistry"))[0];
    const validator = (await read("validator"))[0];
    const window = (await read("DISPUTE_WINDOW"))[0];

    const rows = [
      ["admin", admin, admin.toLowerCase() === ADMIN.toLowerCase()],
      ["identity", identity, identity.toLowerCase() === IDENTITY.toLowerCase()],
      ["validator", validator, validator.toLowerCase() === ADMIN.toLowerCase()],
      ["DISPUTE_WINDOW", window.toString() + " 秒（3 天）", Number(window) === DISPUTE_WINDOW_SECONDS],
    ];

    el.innerHTML = "";
    for (const [k, v, ok] of rows) {
      const row = document.createElement("div");
      row.className = "item " + (ok ? "pass" : "fail");
      row.textContent = (ok ? "✓ " : "✗ ") + k + " = " + v;
      el.appendChild(row);
    }
  } catch (e) {
    el.innerHTML = '<div class="item fail">✗ 读链失败: ' + (e.shortMessage || e.message) + "</div>";
  }
}

// ---------------------------------------------------------------------------
// 部署后自检
// ---------------------------------------------------------------------------
async function runSelfCheck() {
  const el = document.getElementById("selfcheck");
  el.innerHTML = "";
  state.selfCheck = [];

  const add = (name, ok, detail) => {
    state.selfCheck.push({ name, ok, detail });
    const div = document.createElement("div");
    div.className = "item " + (ok ? "pass" : "fail");
    div.textContent = (ok ? "✓ " : "✗ ") + name + (detail ? " — " + detail : "");
    el.appendChild(div);
  };

  if (!state.deployedAddr) {
    add("未部署", false, "请先部署合约");
    return;
  }

  const iface = new ethers.Interface(state.abi);
  const read = async (name, args = []) => {
    const data = iface.encodeFunctionData(name, args);
    const raw = await state.provider.call({ to: state.deployedAddr, data });
    return iface.decodeFunctionResult(name, raw);
  };

  // 1. admin 正确
  const admin = (await read("admin"))[0];
  add("admin == 0x083A…6Ef7", admin.toLowerCase() === ADMIN.toLowerCase(), admin);

  // 2. identity 正确
  const identity = (await read("getIdentityRegistry"))[0];
  add("identity == HahaAgentIdentity", identity.toLowerCase() === IDENTITY.toLowerCase(), identity);

  // 3. validator 初始 = admin
  const validator = (await read("validator"))[0];
  add("validator 初始 == admin", validator.toLowerCase() === ADMIN.toLowerCase(), validator);

  // 4. DISPUTE_WINDOW = 3 天
  const win = (await read("DISPUTE_WINDOW"))[0];
  add("DISPUTE_WINDOW == 3 天", Number(win) === DISPUTE_WINDOW_SECONDS, win.toString() + " 秒");

  // 5. 部署钱包（非 admin）调 setValidator 失败
  if (state.address.toLowerCase() !== ADMIN.toLowerCase()) {
    const setVal = iface.encodeFunctionData("setValidator", [state.address]);
    const r = await tryCall(state.deployedAddr, setVal);
    add("非 admin 调 setValidator 失败", !r.ok, r.ok ? "竟然成功" : "已拒绝");
  } else {
    add("部署者即 admin（权限检查跳过）", true, "admin 天然拥有 setValidator 权限");
  }
}

async function tryCall(to, data) {
  try {
    await state.provider.call({ to, data, from: state.address });
    return { ok: true };
  } catch (e) {
    return { ok: false, reason: e.shortMessage || e.message };
  }
}

// ---------------------------------------------------------------------------
// 开源验证（Etherscan V2 统一 API，走本地 /api/bscscan 代理）
// ---------------------------------------------------------------------------
function explorerWeb() {
  return targetChainId() === CHAIN_MAINNET ? "https://bscscan.com" : "https://testnet.bscscan.com";
}

async function verifyOne() {
  if (!state.verifyKey) {
    alert("请先输入 Etherscan API Key。");
    return;
  }
  if (!state.deployedAddr) {
    alert("请先部署合约。");
    return;
  }

  // 读预生成的 standard-input
  let sourceCode;
  try {
    sourceCode = await (await fetch("public/verify/HahaValidation.json")).text();
  } catch (e) {
    state.verified = { status: "失败", reason: "缺少 standard-input，请先跑 node generate-standard-input.mjs" };
    renderVerify();
    return;
  }

  state.verified = { status: "验证中" };
  renderVerify();

  try {
    const payload = {
      chainid: targetChainId(),
      apikey: state.verifyKey,
      form: {
        module: "contract",
        action: "verifysourcecode",
        contractaddress: state.deployedAddr,
        sourceCode,
        codeformat: "solidity-standard-json-input",
        contractname: "src/HahaValidation.sol:HahaValidation",
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
      state.verified = { status: "已验证", link: `${explorerWeb()}/address/${state.deployedAddr}#code` };
    } else {
      state.verified = { status: "失败", reason: json.result };
    }
  } catch (e) {
    state.verified = { status: "失败", reason: e.message };
  }
  renderVerify();
}

function renderVerify() {
  const el = document.getElementById("verify-results");
  if (!el) return;
  el.classList.remove("hidden");
  el.textContent = state.verified
    ? `HahaValidation: ${state.verified.status}${state.verified.reason ? "（" + state.verified.reason + "）" : ""}${state.verified.link ? " " + state.verified.link : ""}`
    : "";
}

// ---------------------------------------------------------------------------
// 回执
// ---------------------------------------------------------------------------
function buildReceipt() {
  return {
    network: targetChainId() === CHAIN_MAINNET ? "BSC Mainnet" : "BSC Testnet",
    chainId: targetChainId(),
    commit: state.commit,
    compiler: { version: "0.8.28+commit.7893614a", optimizerRuns: 200, viaIr: true },
    deployer: state.address,
    admin: ADMIN,
    identity: IDENTITY,
    contracts: [
      {
        name: "HahaValidation",
        address: state.stepState.contractAddress || "",
        txHash: state.stepState.txHash || "",
        blockNumber: state.stepState.blockNumber || "",
        verifyStatus: state.verified?.status || "未验证",
        verifyLink: state.verified?.link || "",
      },
    ],
    selfCheck: state.selfCheck || [],
  };
}

function receiptMarkdown(r) {
  const lines = [];
  lines.push(`# HahaValidation 部署记录`);
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
  lines.push(`## 构造参数`);
  lines.push(``);
  lines.push(`- admin: ${r.admin}`);
  lines.push(`- identity: ${r.identity}`);
  lines.push(``);
  lines.push(`## 部署后自检`);
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
// 导出/导入进度
// ---------------------------------------------------------------------------
function exportState() {
  const data = {
    chainId: targetChainId(),
    commit: state.commit,
    exportedAt: new Date().toISOString(),
    stepState: state.stepState,
  };
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `validation-deploy-state-${targetChainId()}.json`;
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
      state.stepState = data.stepState || {};
      state.deployedAddr = state.stepState.contractAddress || null;
      saveStepState();
      renderSteps();
      refreshOverview();
      alert("进度已导入。");
    } catch (err) {
      alert("导入失败: " + err.message);
    }
  };
  reader.readAsText(file);
}

// ---------------------------------------------------------------------------
// 恢复
// ---------------------------------------------------------------------------
async function restore() {
  loadStepState();
  const candidates = state.walletType === "okx" ? ["okx", "metamask"] : ["metamask", "okx"];
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
  renderSteps();
  if (state.deployedAddr && state.provider) refreshOverview();
}

// ---------------------------------------------------------------------------
// 全局错误兜底
// ---------------------------------------------------------------------------
window.addEventListener("error", (e) => {
  console.error("全局错误:", e.error || e.message);
  alert("页面脚本出错：" + (e.message || e.error));
});
window.addEventListener("unhandledrejection", (e) => {
  console.error("未处理的 Promise 拒绝:", e.reason);
  alert("异步操作出错：" + (e.reason?.shortMessage || e.reason?.message || e.reason));
});

init();
