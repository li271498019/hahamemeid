// Season1 部署授权面板逻辑。
const ethers = window.ethers;

const CHAIN_MAINNET = 56;
const CHAIN_TESTNET = 97;

const ADDRS = {
  admin: "0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7",
  points: "0xB2D023b8B5895835EFD71C1150BeAD7bD735DfAa",
  registrar: "0x43426E37a31AafDaba851858e34B81DC300650F8",
  identity: "0x54A70BF81B288d41013D7b57c2Db0922f1E1a4d4",
  aiRegistry: "0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F",
};

// 日奖签名钱包公钥（L 提供，只回传公钥、无私钥）。服务器离线签名钱包地址。
const VALIDATOR_PUBKEY = "0xbd02a475Cb374B1685e6BAae1CF1FbDc2deE5aaA";

const ACTION_VERIFY = "0x534541534f4e315f564552494659000000000000000000000000000000000000"; // SEASON1_VERIFY
const ACTION_FIND = "0x534541534f4e315f46494e440000000000000000000000000000000000000000"; // SEASON1_FIND
const ACTION_ACCIDENT = "0x534541534f4e315f4143434944454e5400000000000000000000000000000000"; // SEASON1_ACCIDENT

// 链上时间常量（与 HahaSeason1 完全一致，不可改）
const START_TS = 1795478400; // 2026-11-24T00:00:00Z = 北京时间 2026-11-24 08:00
const END_TS = 1796774400;   // 2026-12-09T00:00:00Z
const FIRST_DAY = 20781;
const LAST_DAY = 20795;      // 窗口 [20781, 20796)
const LAUNCH_EPOCH_MS = START_TS * 1000; // 首日正式快照最早时刻（北京 08:00）

const state = {
  chainId: null,
  mode: "mainnet",
  provider: null,
  signer: null,
  address: null,
  walletType: null,
  season1Abi: null,
  pointsAbi: null,
  bytecode: null,
  season1Addr: null,
  stepStates: {},
  steps: [],
  gatePassed: false,
};

function b32(s) {
  return "0x" + Array.from(new TextEncoder().encode(s)).map((b) => b.toString(16).padStart(2, "0")).join("").padEnd(64, "0");
}

async function init() {
  try {
    const [abiRes, bcRes, ptsRes] = await Promise.all([
      fetch("public/season1/HahaSeason1.abi.json"),
      fetch("public/season1/HahaSeason1.bytecode.json"),
      fetch("public/artifacts.json"),
    ]);
    state.season1Abi = await abiRes.json();
    state.bytecode = (await bcRes.json()).bytecode;
    state.pointsAbi = (await ptsRes.json()).artifacts.HahaPoints.abi;
  } catch (e) {
    document.body.insertAdjacentHTML("afterbegin", `<div style="background:#7c2d12;color:#fed7aa;padding:12px 20px;">初始化失败：${e.message}。请先跑 node export-season1.mjs。</div>`);
    return;
  }

  // 固定参数展示
  document.getElementById("p-admin").textContent = ADDRS.admin;
  document.getElementById("p-points").textContent = ADDRS.points;
  document.getElementById("p-registrar").textContent = ADDRS.registrar;
  document.getElementById("p-identity").textContent = ADDRS.identity;
  document.getElementById("p-ai").textContent = ADDRS.aiRegistry;

  // 预填日奖公钥（L 已提供，只公钥无私钥）
  state.validatorAddr = VALIDATOR_PUBKEY;
  const vInput = document.getElementById("validator-addr");
  if (vInput) vInput.value = VALIDATOR_PUBKEY;

  buildSteps();
  bindEvents();
  renderSteps();
  await restore();
  await refreshOverview();
  startClock();
}

function buildSteps() {
  state.steps = [
    { key: "deploy", label: "部署 HahaSeason1", kind: "deploy" },
    { key: "readback", label: "读回构造参数（只读核对）", kind: "readback" },
    { key: "setSpender", label: "setSpender(season1, true)", kind: "tx", target: "points" },
    { key: "setBudget", label: "setSpenderBudget(200, 4000)", kind: "tx", target: "points" },
    { key: "earnerVerify", label: "setEarner(SEASON1_VERIFY, 30/1/100000/PerDay)", kind: "tx", target: "points" },
    { key: "earnerFind", label: "setEarner(SEASON1_FIND, 100/5/10000/Lifetime)", kind: "tx", target: "points" },
    { key: "earnerAccident", label: "setEarner(SEASON1_ACCIDENT, 100/50/10000/Lifetime)", kind: "tx", target: "points" },
    { key: "setValidator", label: "setValidator（日奖公钥）", kind: "tx", target: "season1", needsValidator: true },
    { key: "setRewardSigner", label: "setRewardSigner(管理员)", kind: "tx", target: "season1" },
    { key: "redeemOpen", label: "打开 redeemOpen", kind: "tx", target: "season1", gated: true },
    { key: "rewardsOpen", label: "打开 rewardsOpen", kind: "tx", target: "season1", gated: true },
  ];
}

function bindEvents() {
  document.getElementById("btn-connect").addEventListener("click", () => connectWallet("metamask"));
  document.getElementById("btn-connect-okx").addEventListener("click", () => connectWallet("okx"));
  document.getElementById("btn-switch-net").addEventListener("click", switchNetwork);
  document.getElementById("btn-mainnet").addEventListener("click", () => setMode("mainnet"));
  document.getElementById("btn-testnet").addEventListener("click", () => setMode("testnet"));
  document.getElementById("btn-export").addEventListener("click", exportState);
  document.getElementById("btn-import").addEventListener("click", () => document.getElementById("import-file").click());
  document.getElementById("import-file").addEventListener("change", importState);
  document.getElementById("validator-addr").addEventListener("input", (e) => {
    state.validatorAddr = e.target.value.trim();
    renderSteps();
  });
  document.getElementById("btn-sr-precheck").addEventListener("click", precheckSetDayRoot);
  document.getElementById("btn-sr-submit").addEventListener("click", submitSetDayRoot);
  document.getElementById("gate-passed").addEventListener("change", (e) => {
    state.gatePassed = e.target.checked;
    renderSteps();
  });
  for (const w of [window.ethereum, window.okxwallet]) {
    if (w && w.on) {
      w.on("accountsChanged", () => location.reload());
      w.on("chainChanged", () => location.reload());
    }
  }
}

function injectedProvider(type) {
  return type === "okx" ? window.okxwallet || null : window.ethereum || null;
}

async function connectWallet(type) {
  const name = type === "okx" ? "OKX" : "MetaMask";
  const injected = injectedProvider(type);
  if (!injected) { alert(`未检测到 ${name} 钱包`); return; }
  try {
    const provider = new ethers.BrowserProvider(injected);
    const signer = await provider.getSigner();
    state.provider = provider;
    state.signer = signer;
    state.walletType = type;
    state.address = await signer.getAddress();
    state.chainId = Number((await provider.getNetwork()).chainId);
    document.getElementById("addr").textContent = shorten(state.address);
    const bal = await provider.getBalance(state.address);
    document.getElementById("balance").textContent = ethers.formatEther(bal).slice(0, 8) + " BNB";
    await onNetworkChanged();
    renderSteps();
  } catch (e) {
    alert(`连接 ${name} 失败：` + (e.shortMessage || e.message));
  }
}

function shorten(a) { return a ? a.slice(0, 10) + "…" + a.slice(-6) : ""; }

function targetChainId() { return state.mode === "mainnet" ? CHAIN_MAINNET : CHAIN_TESTNET; }

function setMode(mode) {
  state.mode = mode;
  document.getElementById("btn-mainnet").classList.toggle("btn-primary", mode === "mainnet");
  document.getElementById("btn-testnet").classList.toggle("btn-primary", mode === "testnet");
  loadStepStates();
  renderSteps();
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
}

async function switchNetwork() {
  const target = targetChainId();
  const params = target === CHAIN_MAINNET
    ? { chainId: "0x38", chainName: "BNB Smart Chain", rpcUrls: ["https://bsc-dataseed.binance.org"], nativeCurrency: { name: "BNB", symbol: "BNB", decimals: 18 }, blockExplorerUrls: ["https://bscscan.com"] }
    : { chainId: "0x61", chainName: "BNB Testnet", rpcUrls: ["https://data-seed-prebsc-1-s1.binance.org:8545"], nativeCurrency: { name: "BNB", symbol: "BNB", decimals: 18 }, blockExplorerUrls: ["https://testnet.bscscan.com"] };
  const injected = injectedProvider(state.walletType) || window.ethereum;
  if (!injected) { alert("请先连接钱包"); return; }
  try {
    await injected.request({ method: "wallet_switchEthereumChain", params: [{ chainId: params.chainId }] });
  } catch (e) {
    if (e.code === 4902) await injected.request({ method: "wallet_addEthereumChain", params: [params] });
    else throw e;
  }
}

// ---------------------------------------------------------------------------
// 步骤
// ---------------------------------------------------------------------------

function storageKey() { return `haha-season1-${targetChainId()}`; }
function loadStepStates() {
  state.stepStates = JSON.parse(localStorage.getItem(storageKey()) || "{}");
  state.season1Addr = state.stepStates.deploy?.contractAddress || null;
}
function saveStepStates() { localStorage.setItem(storageKey(), JSON.stringify(state.stepStates)); }

function currentStepIndex() {
  for (let i = 0; i < state.steps.length; i++) {
    const st = state.stepStates[state.steps[i].key] || {};
    if (st.status !== "confirmed") return i;
  }
  return state.steps.length - 1;
}

function cannotReason(step, status, isCurrent) {
  if (!state.address) return "请先连接钱包";
  if (state.chainId !== targetChainId()) return "网络不符";
  if (status !== "pending" && status !== "failed" && status !== "sent") return "已完成";
  if (!isCurrent) return "请先完成前面的步骤";
  if (step.gated && !state.gatePassed) return "开关步骤锁定：请先勾选上方「验收门已通过」（需 A 复算 root 一致 + 第一天 setDayRoot 已设）";
  if (step.needsValidator && !state.validatorAddr) return "请先填写日奖公钥地址";
  if (state.address.toLowerCase() !== ADDRS.admin.toLowerCase()) return "需管理员钱包 " + ADDRS.admin;
  return null;
}

function renderSteps() {
  const el = document.getElementById("steps");
  el.innerHTML = "";
  const currentIdx = currentStepIndex();

  state.steps.forEach((step, i) => {
    const st = state.stepStates[step.key] || {};
    const status = st.status || "pending";
    const isCurrent = i === currentIdx;
    const reason = cannotReason(step, status, isCurrent);

    const div = document.createElement("div");
    div.className = `step ${status} ${isCurrent ? "" : "disabled"}`;

    const idx = document.createElement("div");
    idx.className = "idx";
    idx.textContent = i + 1;
    div.appendChild(idx);

    const name = document.createElement("div");
    name.className = "name";
    name.textContent = step.label;
    div.appendChild(name);

    const statusEl = document.createElement("div");
    statusEl.className = "status";
    statusEl.textContent = { pending: "待执行", sent: "已发送", confirmed: "已确认", failed: "失败" }[status] || status;
    div.appendChild(statusEl);

    const detail = document.createElement("div");
    detail.className = "detail";
    detail.textContent = st.txHash ? "tx: " + shorten(st.txHash) : (st.contractAddress ? "addr: " + shorten(st.contractAddress) : "");
    div.appendChild(detail);

    const actions = document.createElement("div");
    actions.className = "actions";
    const btn = document.createElement("button");
    btn.className = "btn btn-primary";
    btn.textContent = status === "pending" ? "执行" : status === "failed" ? "重试" : status === "sent" ? "查询确认" : "已完成";
    if (reason) { btn.classList.add("disabled"); btn.title = reason; }
    btn.addEventListener("click", () => executeStep(step, status, reason));
    actions.appendChild(btn);
    div.appendChild(actions);

    el.appendChild(div);
  });
}

function stepData(step) {
  const coder = ethers.AbiCoder.defaultAbiCoder();
  if (step.kind === "deploy") {
    const args = coder.encode(
      ["address", "address", "address", "address", "address", "uint64"],
      [ADDRS.admin, ADDRS.points, ADDRS.registrar, ADDRS.identity, ADDRS.aiRegistry, 15]
    );
    return { to: null, data: state.bytecode + args.slice(2) };
  }
  if (step.kind === "readback") return null;

  if (step.target === "points") {
    const iface = new ethers.Interface(state.pointsAbi);
    if (step.key === "setSpender") {
      return { to: ADDRS.points, data: iface.encodeFunctionData("setSpender", [state.season1Addr, true]) };
    }
    if (step.key === "setBudget") {
      return { to: ADDRS.points, data: iface.encodeFunctionData("setSpenderBudget", [state.season1Addr, [200, 4000]]) };
    }
    if (step.key === "earnerVerify") {
      return { to: ADDRS.points, data: iface.encodeFunctionData("setEarner", [ACTION_VERIFY, [state.season1Addr, 30, 1, 100000, 1, true, true]]) };
    }
    if (step.key === "earnerFind") {
      return { to: ADDRS.points, data: iface.encodeFunctionData("setEarner", [ACTION_FIND, [state.season1Addr, 100, 5, 10000, 2, true, true]]) };
    }
    if (step.key === "earnerAccident") {
      return { to: ADDRS.points, data: iface.encodeFunctionData("setEarner", [ACTION_ACCIDENT, [state.season1Addr, 100, 50, 10000, 2, false, true]]) };
    }
  }

  if (step.target === "season1") {
    const iface = new ethers.Interface(state.season1Abi);
    if (step.key === "setValidator") {
      return { to: state.season1Addr, data: iface.encodeFunctionData("setValidator", [state.validatorAddr, true]) };
    }
    if (step.key === "setRewardSigner") {
      return { to: state.season1Addr, data: iface.encodeFunctionData("setRewardSigner", [ADDRS.admin]) };
    }
    if (step.key === "redeemOpen") {
      return { to: state.season1Addr, data: iface.encodeFunctionData("setRedeemOpen", [true]) };
    }
    if (step.key === "rewardsOpen") {
      return { to: state.season1Addr, data: iface.encodeFunctionData("setRewardsOpen", [true]) };
    }
  }
  throw new Error("unknown step " + step.key);
}

async function executeStep(step, status, reason) {
  if (reason) { alert(reason); return; }
  try {
    if (status === "sent") {
      const st = state.stepStates[step.key];
      const receipt = await state.provider.getTransactionReceipt(st.txHash);
      if (!receipt) { alert("尚未上链，稍后再试"); return; }
      await handleReceipt(step, receipt);
      return;
    }

    if (step.kind === "readback") {
      // 只读核对：读回 season1 的构造参数
      await doReadback(step);
      return;
    }

    const { to, data } = stepData(step);
    const tx = await state.signer.sendTransaction({ to: to || undefined, data });
    state.stepStates[step.key] = { status: "sent", txHash: tx.hash };
    saveStepStates();
    renderSteps();
    const receipt = await tx.wait();
    await handleReceipt(step, receipt);
  } catch (e) {
    const msg = e.shortMessage || e.message || String(e);
    if (msg.includes("user rejected") || msg.includes("denied")) { alert("已取消签名"); return; }
    console.error(e);
    alert("执行失败：" + msg);
    state.stepStates[step.key] = { status: "failed", error: msg };
    saveStepStates();
    renderSteps();
  }
}

async function handleReceipt(step, receipt) {
  if (receipt.status === 1) {
    state.stepStates[step.key] = {
      status: "confirmed",
      txHash: receipt.hash,
      blockNumber: receipt.blockNumber,
      contractAddress: receipt.contractAddress || null,
    };
    if (step.kind === "deploy") state.season1Addr = receipt.contractAddress;
  } else {
    state.stepStates[step.key] = { status: "failed", error: "交易 revert" };
  }
  saveStepStates();
  renderSteps();
}

async function doReadback(step) {
  if (!state.season1Addr) { alert("请先部署合约"); return; }
  const iface = new ethers.Interface(state.season1Abi);
  const checks = [];
  const names = ["admin", "points", "registrar", "identity", "aiRegistry"];
  for (const n of names) {
    const data = iface.encodeFunctionData(n);
    const raw = await state.provider.call({ to: state.season1Addr, data });
    const got = iface.decodeFunctionResult(n, raw)[0];
    checks.push(`${n}: ${got.toLowerCase() === ADDRS[n].toLowerCase() ? "✓" : "✗ 不一致"}`);
  }
  const conf = iface.encodeFunctionData("snapshotConfirmations");
  const raw = await state.provider.call({ to: state.season1Addr, data: conf });
  const got = iface.decodeFunctionResult("snapshotConfirmations", raw)[0];
  checks.push(`snapshotConfirmations: ${Number(got) === 15 ? "✓" : "✗"}`);

  state.stepStates[step.key] = { status: "confirmed" };
  saveStepStates();
  renderSteps();
  alert("构造参数核对：\n" + checks.join("\n"));
}

// ---------------------------------------------------------------------------
// 链上状态总览（只读）
// ---------------------------------------------------------------------------

async function refreshOverview() {
  const el = document.getElementById("overview");
  if (!el) return;
  if (!state.season1Addr) {
    el.innerHTML = '<div class="ov-item muted">尚未部署 HahaSeason1（完成第 1 步后自动读回）。</div>';
    return;
  }
  try {
    const iface = new ethers.Interface(state.season1Abi);
    const calls = ["redeemOpen", "rewardsOpen", "rewardSigner"];
    const results = {};
    for (const name of calls) {
      const data = iface.encodeFunctionData(name);
      const raw = await state.provider.call({ to: state.season1Addr, data });
      results[name] = iface.decodeFunctionResult(name, raw)[0];
    }

    // 当前链上 day（用于判断过去日界预演）
    const latestBlock = await state.provider.getBlock("latest");
    const chainDay = Math.floor(Number(latestBlock.timestamp) / 86400);

    // 第一天 dayMarket
    let dayRoot = null;
    try {
      const data = iface.encodeFunctionData("dayMarket", [FIRST_DAY]);
      const raw = await state.provider.call({ to: state.season1Addr, data });
      const m = iface.decodeFunctionResult("dayMarket", raw)[0];
      dayRoot = {
        merkleRoot: m[0], snapshotBlock: Number(m[1]), snapshotBlockHash: m[2],
        reservedCount: Number(m[3]), remainingSlots: Number(m[4]),
        reservedFilled: Number(m[6]), boundaryFilled: Number(m[5]), opened: m[7],
      };
    } catch {}

    const validatorAddr = VALIDATOR_PUBKEY;
    let validatorOn = false;
    try {
      const data = iface.encodeFunctionData("validators", [validatorAddr]);
      const raw = await state.provider.call({ to: state.season1Addr, data });
      validatorOn = iface.decodeFunctionResult("validators", raw)[0];
    } catch {}

    const items = [
      { k: "模块地址", v: state.season1Addr, mono: true },
      { k: "redeemOpen", v: results.redeemOpen ? "✅ 已打开" : "🔒 关闭", ok: results.redeemOpen },
      { k: "rewardsOpen", v: results.rewardsOpen ? "✅ 已打开" : "🔒 关闭", ok: results.rewardsOpen },
      { k: "rewardSigner", v: results.rewardSigner, mono: true },
      { k: "日奖验证人", v: validatorOn ? "✅ 已授权" : "❌ 未授权", ok: validatorOn },
      { k: "链上当前 day", v: String(chainDay) },
    ];
    if (dayRoot) {
      const rootSet = dayRoot.merkleRoot !== ethers.ZeroHash;
      items.push({ k: `day ${FIRST_DAY} root`, v: rootSet ? "已设置" : "未设置（全零）", ok: rootSet });
      if (rootSet) {
        items.push({ k: `day ${FIRST_DAY} 快照块`, v: String(dayRoot.snapshotBlock) });
        items.push({ k: "已占槽 (reserved/boundary)", v: `${dayRoot.reservedFilled}/${dayRoot.boundaryFilled}` });
      }
    }
    el.innerHTML = items.map((it) => {
      const cls = it.ok === undefined ? "" : it.ok ? "ok" : "warn";
      const val = it.mono ? `<span class="mono">${shorten(it.v)}</span>` : `<span class="${cls}">${it.v}</span>`;
      return `<div class="ov-item"><span class="ov-k">${it.k}</span>${val}</div>`;
    }).join("");
  } catch (e) {
    el.innerHTML = `<div class="ov-item muted">状态读回失败：${e.shortMessage || e.message}</div>`;
  }
}

// ---------------------------------------------------------------------------
// 时间门禁 + 倒计时
// ---------------------------------------------------------------------------

// 链上时间门禁：返回 null 表示允许；否则返回拒绝原因。
// 必须用链上 block.timestamp 判断，不能用本机时间。
// strict=true（主网）：block.timestamp < START_TS 或 >= END_TS 都拒绝。
// strict=false（测试网/预演）：不挡时间，但调用方仍需自行标识预演。
async function launchGate(strict = true) {
  const latestBlock = await state.provider.getBlock("latest");
  const ts = Number(latestBlock.timestamp);
  if (!strict) return null;
  if (ts < START_TS) {
    const remainMs = LAUNCH_EPOCH_MS - ts * 1000;
    return { reason: "未到首日正式快照时刻", remainMs, ts, blockNumber: latestBlock.number };
  }
  if (ts >= END_TS) {
    return { reason: "赛季已结束（END_TS 已过）", remainMs: 0, ts, blockNumber: latestBlock.number };
  }
  return null;
}

function fmtDuration(ms) {
  if (ms <= 0) return "0 秒";
  const s = Math.floor(ms / 1000);
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (d > 0) return `${d} 天 ${h} 小时 ${m} 分`;
  if (h > 0) return `${h} 小时 ${m} 分 ${sec} 秒`;
  if (m > 0) return `${m} 分 ${sec} 秒`;
  return `${sec} 秒`;
}

function renderCountdown() {
  const el = document.getElementById("launch-countdown");
  if (!el) return;
  if (!state.provider) {
    el.innerHTML = '<div class="ov-item muted">连接钱包后显示活动倒计时与快照窗口状态。</div>';
    return;
  }
  state.provider.getBlock("latest").then((block) => {
    const ts = Number(block.timestamp);
    const remainMs = LAUNCH_EPOCH_MS - ts * 1000;
    let html;
    if (ts < START_TS) {
      html = `<div class="cd-warn">⏳ 距首日正式快照（北京 2026-11-24 08:00）还有 <strong>${fmtDuration(remainMs)}</strong></div>`;
      html += `<div class="cd-sub">链上 block.timestamp = ${ts}（区块 #${block.number}）&lt; START_TS ${START_TS}。首日正式快照与发布交易被禁止。</div>`;
    } else if (ts >= END_TS) {
      html = `<div class="cd-warn">🏁 赛季已结束（END_TS 已过）。</div>`;
    } else {
      html = `<div class="cd-ok">✅ 已过首日正式快照时刻，可准备正式 setDayRoot（仍需满足快照窗口）。</div>`;
      html += `<div class="cd-sub">链上 block.timestamp = ${ts}（区块 #${block.number}）。活动剩余 <strong>${fmtDuration(END_TS * 1000 - ts * 1000)}</strong>。</div>`;
    }
    el.innerHTML = html;
  }).catch(() => {});
}

function startClock() {
  renderCountdown();
  setInterval(() => {
    renderCountdown();
    if (state.season1Addr) refreshOverview();
  }, 15000); // 每 15 秒刷新，避免频繁 RPC
}

const SNAPSHOT_MIN_DEPTH = 15; // 确认深度下限（块）
const SNAPSHOT_MAX_DEPTH = 256; // EVM 只能读最近 256 块的 blockhash；深度 >= 256 读不到

function srResult(text, ok) {
  const el = document.getElementById("sr-result");
  el.textContent = text;
  el.className = "sr-result " + (ok ? "ok" : "err");
}

async function readSrInput() {
  const dayIndex = Number(document.getElementById("sr-day").value);
  const snapshotBlock = Number(document.getElementById("sr-block").value);
  const merkleRoot = document.getElementById("sr-root").value.trim();
  const reservedCount = Number(document.getElementById("sr-reserved").value);
  const remainingSlots = Number(document.getElementById("sr-remaining").value);
  if (!state.season1Addr) { alert("请先完成第 1 步部署 HahaSeason1"); return null; }
  if (!dayIndex || !snapshotBlock || !merkleRoot) { srResult("请填齐 dayIndex、snapshotBlock、merkleRoot", false); return null; }
  if (!/^0x[0-9a-fA-F]{64}$/.test(merkleRoot)) { srResult("merkleRoot 需为 0x + 64 位 hex", false); return null; }
  return { dayIndex, snapshotBlock, merkleRoot, reservedCount, remainingSlots };
}

// 预检：只读，不发交易。返回窗口检查结果 + 快照块哈希（窗口内时）。
async function precheckSetDayRoot() {
  const inp = await readSrInput();
  if (!inp) return;
  try {
    // 0. 链上时间门禁（主网严格；测试网/预演不挡但会标识）
    const strict = state.mode === "mainnet";
    const gate = await launchGate(strict);
    if (gate) {
      srResult(
        `⛔ 拒绝：${gate.reason}（链上 block.timestamp=${gate.ts}，区块 #${gate.blockNumber}）。` +
        (gate.remainMs > 0 ? `\n还需等待 ${fmtDuration(gate.remainMs)}。` : "") +
        `\n首日正式快照不得提前生成，也不得用「过去日界」凑正式发布。`,
        false
      );
      return;
    }

    const latest = await state.provider.getBlockNumber();
    const depth = latest - inp.snapshotBlock;

    // 过去日界预演标识：dayIndex < 链上当前 day 时，标记为预演，不能用于正式发布
    const latestBlock = await state.provider.getBlock("latest");
    const chainDay = Math.floor(Number(latestBlock.timestamp) / 86400);
    const isRehearsal = inp.dayIndex < chainDay;
    const rehearsalTag = isRehearsal ? "【预演·过去日界，不可用于正式发布】" : "";

    if (inp.snapshotBlock <= 0 || depth < 0) {
      srResult(`❌ 拒绝：快照块 #${inp.snapshotBlock} 无效（不能是 0 或未来块）。${rehearsalTag}`, false);
      return;
    }
    if (depth < SNAPSHOT_MIN_DEPTH) {
      srResult(
        `❌ 拒绝：快照块 #${inp.snapshotBlock} 太新，深度 ${depth} 块 < ${SNAPSHOT_MIN_DEPTH} 块确认深度。` +
        `请等待更多块或换更早的快照块。\n不回退快照块、不自动顺延赛季。${rehearsalTag}`,
        false
      );
      return;
    }
    if (depth >= SNAPSHOT_MAX_DEPTH) {
      srResult(
        `❌ 拒绝：快照块 #${inp.snapshotBlock} 太老，深度 ${depth} 块 >= ${SNAPSHOT_MAX_DEPTH} 块，` +
        `blockhash 已不可读（EVM 只能读最近 256 块）。请换一个最近 ${SNAPSHOT_MAX_DEPTH - 1} 块内的快照块。\n不回退快照块、不自动顺延赛季。${rehearsalTag}`,
        false
      );
      return;
    }

    const block = await state.provider.getBlock(inp.snapshotBlock);
    state.srBlockHash = block.hash;
    state.srRehearsal = isRehearsal;
    srResult(
      `✅ 窗口内：快照块 #${inp.snapshotBlock}，深度 ${depth} 块（需 ${SNAPSHOT_MIN_DEPTH} ~ ${SNAPSHOT_MAX_DEPTH - 1} 块）。` +
      `\nblockhash = ${block.hash}。剩余有效块数 ${SNAPSHOT_MAX_DEPTH - 1 - depth}。可点「提交 setDayRoot」。` +
      (isRehearsal ? `\n⚠️ ${rehearsalTag}` : ""),
      true
    );
  } catch (e) {
    srResult("预检失败：" + (e.shortMessage || e.message), false);
  }
}

async function submitSetDayRoot() {
  const inp = await readSrInput();
  if (!inp) return;
  if (state.address?.toLowerCase() !== ADDRS.admin.toLowerCase()) {
    srResult("需管理员钱包 " + ADDRS.admin, false);
    return;
  }
  try {
    // 0. 签名前再次校验时间门禁（主网严格）
    const strict = state.mode === "mainnet";
    const gate = await launchGate(strict);
    if (gate) {
      srResult(`⛔ 拒绝：${gate.reason}（链上 block.timestamp=${gate.ts}）。首日正式快照不得提前发布。`, false);
      return;
    }

    // 提交前再预检一次（防窗口已过）
    const latest = await state.provider.getBlockNumber();
    const depth = latest - inp.snapshotBlock;
    if (depth < SNAPSHOT_MIN_DEPTH || depth >= SNAPSHOT_MAX_DEPTH) {
      srResult(`❌ 拒绝：快照块 #${inp.snapshotBlock} 深度 ${depth} 块，不在 ${SNAPSHOT_MIN_DEPTH}~${SNAPSHOT_MAX_DEPTH - 1} 窗口内。不回退快照块、不自动顺延赛季。`, false);
      return;
    }
    const block = await state.provider.getBlock(inp.snapshotBlock);

    // 过去日界预演：提交正式发布时拒绝预演 dayIndex（但允许在测试网明确预演）
    const latestBlock = await state.provider.getBlock("latest");
    const chainDay = Math.floor(Number(latestBlock.timestamp) / 86400);
    const isRehearsal = inp.dayIndex < chainDay;
    if (isRehearsal && state.mode === "mainnet") {
      srResult(
        `⛔ 拒绝正式发布：dayIndex ${inp.dayIndex} 是过去日界（链上当前 day ${chainDay}）。` +
        `过去日界只能预演，不能直接用于正式发布。请改用当前 day 的正式快照。`,
        false
      );
      return;
    }

    const iface = new ethers.Interface(state.season1Abi);
    const data = iface.encodeFunctionData("setDayRoot", [
      inp.dayIndex,
      inp.merkleRoot,
      inp.snapshotBlock,
      block.hash,
      inp.reservedCount,
      inp.remainingSlots,
    ]);
    const tx = await state.signer.sendTransaction({ to: state.season1Addr, data });
    srResult("已发送 setDayRoot，tx: " + tx.hash + "，等待确认…", true);
    const receipt = await tx.wait();
    srResult(
      receipt.status === 1
        ? `✅ setDayRoot 已确认：dayIndex=${inp.dayIndex} snapshotBlock=${inp.snapshotBlock} block=${receipt.blockNumber}${isRehearsal ? "（预演）" : ""}`
        : "❌ 交易 revert",
      receipt.status === 1
    );
    await refreshOverview();
  } catch (e) {
    const msg = e.shortMessage || e.message || String(e);
    if (msg.includes("user rejected") || msg.includes("denied")) { srResult("已取消签名", false); return; }
    srResult("提交失败：" + msg, false);
  }
}

function exportState() {
  const data = { chainId: targetChainId(), season1Addr: state.season1Addr, steps: state.stepStates };
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `season1-deploy-state-${targetChainId()}.json`;
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
      if (data.chainId !== targetChainId()) { alert("chainId 不符"); return; }
      state.season1Addr = data.season1Addr || null;
      state.stepStates = data.steps || {};
      saveStepStates();
      renderSteps();
    } catch (err) { alert("导入失败：" + err.message); }
  };
  reader.readAsText(file);
}

async function restore() {
  const candidates = state.walletType === "okx" ? ["okx", "metamask"] : ["metamask", "okx"];
  for (const t of candidates) {
    const injected = injectedProvider(t);
    if (!injected) continue;
    try {
      const accounts = await injected.request({ method: "eth_accounts" });
      if (accounts.length > 0) { await connectWallet(t); break; }
    } catch {}
  }
  loadStepStates();
  renderSteps();
}

window.addEventListener("error", (e) => alert("页面脚本出错：" + (e.message || e.error)));
window.addEventListener("unhandledrejection", (e) => alert("异步出错：" + (e.reason?.shortMessage || e.reason?.message || e.reason)));

init();
