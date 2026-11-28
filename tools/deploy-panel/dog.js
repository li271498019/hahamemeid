// Haha Dog 部署面板逻辑。
// 4 合约按序部署：HahaDogModel -> HahaDogRenderer -> HahaDog -> HahaDogMarket。
// 构造参数可核对修改（aiRegistry/registrar/feeReceiver/blockHistory 从 handoff 默认值带出）。
// 每步显示 tx/地址/状态，前一步确认后才能下一步；断线续部署；一键开源（Etherscan V2）。

const ethers = window.ethers;

const CHAIN_MAINNET = 56;
const CHAIN_TESTNET = 97;

// 两个哈希（DEPLOY.md §5 公布值）：
// - weightsFileHash：权重文件 haha-dog/model/weights-int8.json 原始字节的 keccak256（离线文件哈希）
// - modelDataHash：链上 HahaDogModel.MODEL_DATA_HASH() = keccak256(Wt.DATA)（链上数据哈希）
const WEIGHTS_FILE_HASH = "0x1d2239644b5273c4f1925c489d32900a564262bce6597f94a929489cfbe58078";
const MODEL_DATA_HASH = "0x72f92c628a64bc0d5652d285c6789fa0f84cb462d328604cf3dcff224704f8da";

// 4 合约定义。ctorArgs(idx, ctx) 返回构造参数数组（前序合约地址从 ctx 取）。
const CONTRACTS = [
  { name: "HahaDogModel", source: "src/hahadog/HahaDogModel.sol:HahaDogModel", ctorTypes: [], args: () => [] },
  { name: "HahaDogRenderer", source: "src/hahadog/HahaDogRenderer.sol:HahaDogRenderer", ctorTypes: ["address"], args: (ctx) => [ctx.addr("HahaDogModel")] },
  { name: "HahaDog", source: "src/hahadog/HahaDog.sol:HahaDog", ctorTypes: ["address", "address", "address", "address", "address"], args: (ctx) => [ctx.addr("HahaDogRenderer"), ctx.param("aiRegistry"), ctx.param("registrar"), ctx.param("feeReceiver"), ctx.param("blockHistory")] },
  { name: "HahaDogMarket", source: "src/hahadog/HahaDogMarket.sol:HahaDogMarket", ctorTypes: ["address", "address"], args: (ctx) => [ctx.addr("HahaDog"), ctx.param("feeReceiver")] },
];

const state = {
  chainId: null,
  mode: "mainnet",
  provider: null,
  signer: null,
  address: null,
  walletType: null,
  commit: null,
  defaults: null, // handoff.json 默认参数
  stepState: {}, // { "HahaDogModel": {status, txHash, blockNumber, contractAddress, error}, ... }
  verified: {}, // { "HahaDogModel": {status, link, reason}, ... }
  verifyKey: "",
  selfCheck: [],
};

// ---------------------------------------------------------------------------
// 初始化
// ---------------------------------------------------------------------------
async function init() {
  try {
    const handoff = await (await fetch("public/dog/handoff.json")).json();
    state.commit = handoff.specCommit;
    state.defaults = handoff.defaults;
  } catch (e) {
    console.error("加载 handoff 失败:", e);
    document.body.insertAdjacentHTML(
      "afterbegin",
      '<div style="background:#7c2d12;color:#fed7aa;padding:12px 20px;">面板初始化失败：' +
        (e.message || e) +
        "。请确认是在 <code>npm run deploy-panel</code> 启动后访问，且已运行 <code>node export-hahadog.mjs</code>。</div>"
    );
    return;
  }

  document.getElementById("meta-commit").textContent = "commit: " + state.commit;

  // 构造参数输入框默认值
  document.getElementById("in-aiRegistry").value = state.defaults.aiRegistry;
  document.getElementById("in-registrar").value = state.defaults.registrar;
  document.getElementById("in-feeReceiver").value = state.defaults.feeReceiver;
  document.getElementById("in-blockHistory").value = state.defaults.blockHistory;

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
  document.getElementById("btn-verify").addEventListener("click", verifyAll);
  document.getElementById("btn-selfcheck").addEventListener("click", runSelfCheck);
  document.getElementById("btn-tokenuri").addEventListener("click", callTokenURI);
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
// 构造参数读取
// ---------------------------------------------------------------------------
function readParams() {
  return {
    aiRegistry: document.getElementById("in-aiRegistry").value.trim(),
    registrar: document.getElementById("in-registrar").value.trim(),
    feeReceiver: document.getElementById("in-feeReceiver").value.trim(),
    blockHistory: document.getElementById("in-blockHistory").value.trim(),
  };
}

function validateParams() {
  const p = readParams();
  const checks = [
    ["aiRegistry", p.aiRegistry, ethers.isAddress(p.aiRegistry)],
    ["registrar", p.registrar, ethers.isAddress(p.registrar)],
    ["feeReceiver", p.feeReceiver, ethers.isAddress(p.feeReceiver)],
  ];
  for (const [k, v, ok] of checks) {
    if (!ok) return `参数 ${k} 不是有效地址：${v}`;
  }
  // blockHistory 允许为空（合约允许 address(0)），但主网应填 EIP-2935
  if (p.blockHistory && !ethers.isAddress(p.blockHistory)) {
    return `参数 blockHistory 不是有效地址：${p.blockHistory}`;
  }
  return null;
}

// ---------------------------------------------------------------------------
// 步骤状态（localStorage，按 chainId 隔离）
// ---------------------------------------------------------------------------
function storageKey() {
  return `haha-dog-deploy-${targetChainId()}`;
}

function loadStepState() {
  const raw = localStorage.getItem(storageKey());
  state.stepState = raw ? JSON.parse(raw) : {};
}

function saveStepState() {
  localStorage.setItem(storageKey(), JSON.stringify(state.stepState));
}

function stepOf(name) {
  return state.stepState[name] || { status: "pending" };
}

// ---------------------------------------------------------------------------
// 步骤渲染
// ---------------------------------------------------------------------------
function renderSteps() {
  const el = document.getElementById("steps");
  el.innerHTML = "";

  const ctx = buildCtx();

  CONTRACTS.forEach((c, i) => {
    const st = stepOf(c.name);
    const status = st.status || "pending";

    const div = document.createElement("div");
    div.className = `step ${status}`;

    const idx = document.createElement("div");
    idx.className = "idx";
    idx.textContent = String(i + 1);
    div.appendChild(idx);

    const name = document.createElement("div");
    name.className = "name";
    const argsDesc = c.ctorTypes.length
      ? `<br><span class="sub">ctor(${c.ctorTypes.join(", ")})</span>`
      : `<br><span class="sub">无构造参数</span>`;
    name.innerHTML = `部署 ${c.name}${argsDesc}`;
    div.appendChild(name);

    const statusEl = document.createElement("div");
    statusEl.className = "status " + statusClass(status);
    statusEl.textContent = statusText(status);
    div.appendChild(statusEl);

    const detail = document.createElement("div");
    detail.className = "detail";
    let d = "";
    if (st.txHash) d += "tx: " + shorten(st.txHash) + " ";
    if (st.contractAddress) d += "addr: " + shorten(st.contractAddress) + " ";
    if (st.blockNumber) d += "block: " + st.blockNumber + " ";
    if (st.error) d += "err: " + st.error;
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

    const reason = cannotReason(c, status);
    if (reason) {
      btn.classList.add("disabled");
      btn.title = reason;
    }
    btn.addEventListener("click", () => executeDeploy(c, status, reason));
    actions.appendChild(btn);
    div.appendChild(actions);

    el.appendChild(div);
  });

  // 全部 confirmed 才启用自检/回执/tokenURI
  const allConfirmed = CONTRACTS.every((c) => stepOf(c.name).status === "confirmed");
  document.getElementById("btn-selfcheck").disabled = !allConfirmed;
  document.getElementById("btn-tokenuri").disabled = !allConfirmed;
  document.getElementById("btn-receipt-copy").disabled = !allConfirmed;
  document.getElementById("btn-receipt-md").disabled = !allConfirmed;
  document.getElementById("btn-receipt-download").disabled = !allConfirmed;
  document.getElementById("btn-verify").disabled = !allConfirmed;
}

// 构建构造参数上下文：前序合约地址 + 当前参数
function buildCtx() {
  const params = readParams();
  return {
    param: (k) => params[k],
    addr: (name) => {
      const s = stepOf(name);
      return s.contractAddress || "";
    },
  };
}

function cannotReason(c, status) {
  if (!window.ethereum && !window.okxwallet) return "未检测到 MetaMask / OKX 钱包，请先安装并解锁";
  if (!state.address) return "请先点右上角「连接 MetaMask」或「连接 OKX」";
  if (state.chainId !== targetChainId()) {
    return "网络不符：当前 " + state.chainId + "，需要 " + targetChainId() + "，请点「一键切换」";
  }
  if (status !== "pending" && status !== "failed" && status !== "sent") return "该步骤已完成";

  // 前序合约必须已确认
  const idx = CONTRACTS.findIndex((x) => x.name === c.name);
  for (let j = 0; j < idx; j++) {
    const prev = CONTRACTS[j];
    if (stepOf(prev.name).status !== "confirmed") {
      return `前序合约 ${prev.name} 尚未确认，不能部署 ${c.name}`;
    }
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
// 编码构造参数 + 部署
// ---------------------------------------------------------------------------
async function loadArtifact(name) {
  const [abiRes, bcRes] = await Promise.all([
    fetch(`public/dog/${name}.abi.json`),
    fetch(`public/dog/${name}.bytecode.json`),
  ]);
  if (!abiRes.ok || !bcRes.ok) throw new Error(`加载 ${name} 产物失败`);
  const abi = await abiRes.json();
  const bc = await bcRes.json();
  return { abi, bytecode: bc.bytecode };
}

function encodeCreationCode(bytecode, ctorTypes, args) {
  const coder = ethers.AbiCoder.defaultAbiCoder();
  const argsHex = ctorTypes.length ? coder.encode(ctorTypes, args).slice(2) : "";
  return bytecode + argsHex;
}

async function executeDeploy(c, status, reason) {
  if (reason) {
    alert(reason);
    return;
  }

  try {
    if (status === "sent") {
      await confirmSent(c);
      return;
    }

    // 防重复部署：查链上是否已部署过
    const existing = state.stepState[c.name]?.contractAddress;
    if (existing) {
      const code = await state.provider.getCode(existing);
      if (code && code !== "0x") {
        state.stepState[c.name] = { ...state.stepState[c.name], status: "confirmed" };
        saveStepState();
        renderSteps();
        refreshOverview();
        return;
      }
    }

    const { abi, bytecode } = await loadArtifact(c.name);
    const args = c.args(buildCtx());
    const data = encodeCreationCode(bytecode, c.ctorTypes, args);

    const tx = await state.signer.sendTransaction({ data });
    state.stepState[c.name] = { ...state.stepState[c.name], status: "sent", txHash: tx.hash, error: "" };
    saveStepState();
    renderSteps();

    const receipt = await tx.wait();
    await handleReceipt(c, receipt);
  } catch (e) {
    console.error("部署失败:", e);
    const msg = e.shortMessage || e.message || String(e);
    if (msg.includes("user rejected") || msg.includes("denied")) {
      alert("已取消签名。");
      renderSteps();
      return;
    }
    alert("部署失败：" + msg);
    state.stepState[c.name] = { ...state.stepState[c.name], status: "failed", error: msg };
    saveStepState();
    renderSteps();
  }
}

async function handleReceipt(c, receipt) {
  if (receipt.status === 1) {
    state.stepState[c.name] = {
      status: "confirmed",
      txHash: receipt.hash,
      blockNumber: receipt.blockNumber,
      contractAddress: receipt.contractAddress,
      error: "",
    };
  } else {
    state.stepState[c.name] = { ...state.stepState[c.name], status: "failed", error: "交易 revert" };
  }
  saveStepState();
  renderSteps();
  refreshOverview();
}

async function confirmSent(c) {
  const st = state.stepState[c.name];
  if (!st || !st.txHash) return;
  const receipt = await state.provider.getTransactionReceipt(st.txHash);
  if (!receipt) {
    alert("交易尚未被包含进区块，稍后再试。");
    return;
  }
  await handleReceipt(c, receipt);
}

// ---------------------------------------------------------------------------
// 链上状态总览
// ---------------------------------------------------------------------------
async function refreshOverview() {
  const el = document.getElementById("overview");
  if (!state.provider) {
    el.innerHTML = '<p class="hint">连接钱包后，这里实时读链显示 4 个合约状态。</p>';
    return;
  }
  const rows = [];
  for (const c of CONTRACTS) {
    const st = stepOf(c.name);
    if (st.contractAddress) {
      const code = await state.provider.getCode(st.contractAddress);
      const hasCode = code && code !== "0x";
      rows.push([c.name, st.contractAddress, hasCode && st.status === "confirmed"]);
    } else {
      rows.push([c.name, "未部署", false]);
    }
  }
  el.innerHTML = "";
  for (const [name, addr, ok] of rows) {
    const row = document.createElement("div");
    row.className = "item " + (ok ? "pass" : "fail");
    row.textContent = (ok ? "✓ " : "· ") + name + " = " + addr;
    el.appendChild(row);
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

  const dogAddr = stepOf("HahaDog").contractAddress;
  const modelAddr = stepOf("HahaDogModel").contractAddress;
  const rendererAddr = stepOf("HahaDogRenderer").contractAddress;
  const marketAddr = stepOf("HahaDogMarket").contractAddress;
  if (!dogAddr || !modelAddr || !rendererAddr || !marketAddr) {
    add("未部署完成", false, "请先部署全部 4 个合约");
    return;
  }

  // 读函数辅助
  const readOn = async (addr, abi, name, args = []) => {
    const iface = new ethers.Interface(abi);
    const data = iface.encodeFunctionData(name, args);
    const raw = await state.provider.call({ to: addr, data });
    return iface.decodeFunctionResult(name, raw);
  };

  try {
    const modelAbi = await (await fetch("public/dog/HahaDogModel.abi.json")).json();
    const rendererAbi = await (await fetch("public/dog/HahaDogRenderer.abi.json")).json();
    const dogAbi = await (await fetch("public/dog/HahaDog.abi.json")).json();
    const marketAbi = await (await fetch("public/dog/HahaDogMarket.abi.json")).json();

    // 1. 链上数据哈希核对：MODEL_DATA_HASH() == 公布值 0x72f92c...f8da
    const modelHash = (await readOn(modelAddr, modelAbi, "MODEL_DATA_HASH"))[0];
    add("MODEL_DATA_HASH() == 链上数据哈希 0x72f92c…f8da", modelHash.toLowerCase() === MODEL_DATA_HASH.toLowerCase(), modelHash);

    // 2. 链上数据哈希自洽：keccak256(modelData()) == MODEL_DATA_HASH（合约部署时已校验，这里复核）
    const modelData = (await readOn(modelAddr, modelAbi, "modelData"))[0];
    const computedDataHash = ethers.keccak256(modelData);
    add("keccak256(modelData()) == MODEL_DATA_HASH", computedDataHash.toLowerCase() === modelHash.toLowerCase(), computedDataHash);

    // 3. 权重文件哈希（离线核对，展示公布值，需用户本地 cast keccak 复核权重文件）
    add("权重文件哈希 = 0x1d2239…8078（离线核对）", true, "请用 cast keccak $(xxd -p haha-dog/model/weights-int8.json | tr -d '\\n' | sed 's/^/0x/') 复核本地文件");

    // 3. HahaDog.renderer == rendererAddr
    const dogRenderer = (await readOn(dogAddr, dogAbi, "renderer"))[0];
    add("HahaDog.renderer == Renderer", dogRenderer.toLowerCase() === rendererAddr.toLowerCase(), dogRenderer);

    // 4. HahaDog.blockHistory == EIP-2935
    const bh = (await readOn(dogAddr, dogAbi, "blockHistory"))[0];
    add("HahaDog.blockHistory == EIP-2935", bh.toLowerCase() === (state.defaults.blockHistory || "").toLowerCase(), bh);

    // 5. HahaDog.totalSupply == 0（初始）
    const supply = (await readOn(dogAddr, dogAbi, "totalSupply"))[0];
    add("HahaDog.totalSupply == 0", Number(supply) === 0, supply.toString());

    // 6. HahaDogMarket.feeBps == 100
    const feeBps = (await readOn(marketAddr, marketAbi, "feeBps"))[0];
    add("HahaDogMarket.feeBps == 100", Number(feeBps) === 100, feeBps.toString());

    // 7. HahaDogMarket.dog == dogAddr
    const marketDog = (await readOn(marketAddr, marketAbi, "dog"))[0];
    add("HahaDogMarket.dog == HahaDog", marketDog.toLowerCase() === dogAddr.toLowerCase(), marketDog);
  } catch (e) {
    add("自检异常", false, e.shortMessage || e.message);
  }
}

// ---------------------------------------------------------------------------
// tokenURI 出图验证
// ---------------------------------------------------------------------------
async function callTokenURI() {
  const el = document.getElementById("tokenuri-result");
  el.classList.remove("hidden");
  const dogAddr = stepOf("HahaDog").contractAddress;
  const rendererAddr = stepOf("HahaDogRenderer").contractAddress;
  if (!dogAddr || !rendererAddr) {
    el.textContent = "请先部署完成。";
    return;
  }

  const idInput = document.getElementById("tokenuri-id").value.trim();
  const dogAbi = await (await fetch("public/dog/HahaDog.abi.json")).json();
  const rendererAbi = await (await fetch("public/dog/HahaDogRenderer.abi.json")).json();
  const dogIface = new ethers.Interface(dogAbi);
  const rendererIface = new ethers.Interface(rendererAbi);

  el.textContent = "调用中…";

  try {
    // 三种情况：
    //   - 纯数字 -> tokenURI(tokenId)，返回完整 base64 JSON
    //   - 0x + 64 位 hex -> svgOf(seed)，按指定种子出图
    //   - 留空 -> svgOf(固定 seed 0x…01) 出图
    const isSeed = /^0x[0-9a-fA-F]{64}$/.test(idInput);
    const isTokenId = /^\d+$/.test(idInput);

    if (isTokenId) {
      const data = dogIface.encodeFunctionData("tokenURI", [idInput]);
      const raw = await state.provider.call({ to: dogAddr, data });
      const [uri] = dogIface.decodeFunctionResult("tokenURI", raw);
      let pretty = uri;
      if (uri.startsWith("data:application/json;base64,")) {
        const b64 = uri.split(",")[1];
        const jsonStr = atob(b64);
        pretty = JSON.stringify(JSON.parse(jsonStr), null, 2);
      }
      el.textContent = "tokenURI(" + idInput + ") =\n" + pretty;
    } else if (isSeed) {
      const data = rendererIface.encodeFunctionData("svgOf", [idInput]);
      const raw = await state.provider.call({ to: rendererAddr, data });
      const [svg] = rendererIface.decodeFunctionResult("svgOf", raw);
      el.textContent = "svgOf(seed=" + idInput + ") 出图成功，SVG 长度 " + svg.length + " 字符（预览前 200 字符）:\n" + svg.slice(0, 200) + "…";
    } else if (idInput === "") {
      const seed = "0x0000000000000000000000000000000000000000000000000000000000000001";
      const data = rendererIface.encodeFunctionData("svgOf", [seed]);
      const raw = await state.provider.call({ to: rendererAddr, data });
      const [svg] = rendererIface.decodeFunctionResult("svgOf", raw);
      el.textContent = "svgOf(seed=0x…01) 出图成功，SVG 长度 " + svg.length + " 字符（预览前 200 字符）:\n" + svg.slice(0, 200) + "…";
    } else {
      el.textContent = "输入格式：填 tokenId 用纯数字（如 1）；填 seed 用 0x 开头 64 位 hex（如 token #1 的 seed）；留空则用固定 seed 0x…01 调 svgOf。";
    }
  } catch (e) {
    el.textContent = "调用失败：" + (e.shortMessage || e.message || e);
  }
}

// ---------------------------------------------------------------------------
// 开源验证（Etherscan V2 统一 API，走本地 /api/bscscan 代理）
// ---------------------------------------------------------------------------
function explorerWeb() {
  return targetChainId() === CHAIN_MAINNET ? "https://bscscan.com" : "https://testnet.bscscan.com";
}

async function verifyAll() {
  if (!state.verifyKey) {
    alert("请先输入 Etherscan API Key。");
    return;
  }
  const allConfirmed = CONTRACTS.every((c) => stepOf(c.name).status === "confirmed");
  if (!allConfirmed) {
    alert("请先完成全部 4 个合约部署。");
    return;
  }

  const resultsEl = document.getElementById("verify-results");
  resultsEl.classList.remove("hidden");
  resultsEl.textContent = "验证中…";

  const lines = [];
  for (const c of CONTRACTS) {
    const addr = stepOf(c.name).contractAddress;
    state.verified[c.name] = { status: "验证中" };
    try {
      // 实际文件名：hahadog_HahaDogModel.json 等（generate-standard-input.mjs 生成）
      const stdInput = await (await fetch(`public/verify/hahadog_${c.name}.json`)).text();

      // 构造参数编码（供 verifysourcecode 用 constructorArguements）
      const ctorArgTypes = c.ctorTypes;
      let constructorArgsHex = "";
      if (ctorArgTypes.length) {
        const coder = ethers.AbiCoder.defaultAbiCoder();
        const args = c.args(buildCtx());
        constructorArgsHex = coder.encode(ctorArgTypes, args);
      }

      const payload = {
        chainid: targetChainId(),
        apikey: state.verifyKey,
        form: {
          module: "contract",
          action: "verifysourcecode",
          contractaddress: addr,
          sourceCode: stdInput,
          codeformat: "solidity-standard-json-input",
          contractname: c.source,
          compilerversion: "v0.8.28+commit.7893614a",
          optimizationUsed: "1",
          runs: "200",
          licenseType: "3",
          ...(constructorArgsHex ? { constructorArguements: constructorArgsHex.slice(2) } : {}),
        },
      };
      const res = await fetch("/api/bscscan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const json = await res.json();
      if (json.status === "1") {
        state.verified[c.name] = { status: "已验证", link: `${explorerWeb()}/address/${addr}#code` };
        lines.push(`✓ ${c.name}: 已验证 ${state.verified[c.name].link}`);
      } else {
        state.verified[c.name] = { status: "失败", reason: json.result };
        lines.push(`✗ ${c.name}: ${json.result}`);
      }
    } catch (e) {
      state.verified[c.name] = { status: "失败", reason: e.message };
      lines.push(`✗ ${c.name}: ${e.message}`);
    }
  }
  resultsEl.textContent = lines.join("\n");
}

// ---------------------------------------------------------------------------
// 回执
// ---------------------------------------------------------------------------
function buildReceipt() {
  const contracts = CONTRACTS.map((c) => {
    const st = stepOf(c.name);
    return {
      name: c.name,
      address: st.contractAddress || "",
      txHash: st.txHash || "",
      blockNumber: st.blockNumber || "",
      verifyStatus: state.verified[c.name]?.status || "未验证",
      verifyLink: state.verified[c.name]?.link || "",
    };
  });
  return {
    network: targetChainId() === CHAIN_MAINNET ? "BSC Mainnet" : "BSC Testnet",
    chainId: targetChainId(),
    commit: state.commit,
    compiler: { version: "0.8.28+commit.7893614a", optimizerRuns: 200, viaIr: true, evmVersion: "cancun" },
    deployer: state.address,
    params: readParams(),
    weightsFileHash: WEIGHTS_FILE_HASH,
    modelDataHash: MODEL_DATA_HASH,
    contracts,
    selfCheck: state.selfCheck || [],
  };
}

function receiptMarkdown(r) {
  const lines = [];
  lines.push(`# Haha Dog 部署记录`);
  lines.push(``);
  lines.push(`| 项 | 值 |`);
  lines.push(`| --- | --- |`);
  lines.push(`| 链 | ${r.network}，chainId ${r.chainId} |`);
  lines.push(`| 部署 EOA | ${r.deployer} |`);
  lines.push(`| commit | ${r.commit} |`);
  lines.push(`| 编译器 | solc ${r.compiler.version}，optimizer runs ${r.compiler.optimizerRuns}，via-ir，cancun |`);
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
  lines.push(`- aiRegistry: ${r.params.aiRegistry}`);
  lines.push(`- registrar: ${r.params.registrar}`);
  lines.push(`- feeReceiver: ${r.params.feeReceiver}`);
  lines.push(`- blockHistory: ${r.params.blockHistory}`);
  lines.push(``);
  lines.push(`## 哈希`);
  lines.push(``);
  lines.push(`- 权重文件 keccak256: ${r.weightsFileHash}（离线文件 haha-dog/model/weights-int8.json）`);
  lines.push(`- 链上数据哈希 MODEL_DATA_HASH(): ${r.modelDataHash}`);
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
  a.download = `haha-dog-deployment-${r.chainId}.json`;
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
    params: readParams(),
    stepState: state.stepState,
  };
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `haha-dog-deploy-state-${targetChainId()}.json`;
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
      if (data.params) {
        document.getElementById("in-aiRegistry").value = data.params.aiRegistry || "";
        document.getElementById("in-registrar").value = data.params.registrar || "";
        document.getElementById("in-feeReceiver").value = data.params.feeReceiver || "";
        document.getElementById("in-blockHistory").value = data.params.blockHistory || "";
      }
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
  if (state.provider) refreshOverview();
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
