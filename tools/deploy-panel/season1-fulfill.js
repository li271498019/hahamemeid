// Season1 铸造发放面板逻辑（既定订单 adminMint，逐笔签名）。
// 复用 tools/season1/ops.py 的 adminMint calldata 编码与日志核对规则，用 JS 重写。
// 不新增空投规则，不提供「全部签名」，管理员私钥不进本文件、不进服务器。
const ethers = window.ethers;

const CHAIN_MAINNET = 56;
const CHAIN_TESTNET = 97;

const ADDRS = {
  admin: "0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7",
  season1: "0x4B8a35bFe18750c2058fd01e7159728adD345C00",
  registrar: "0x43426E37a31AafDaba851858e34B81DC300650F8",
};

const ADMIN_MINT_SELECTOR = "0x65f5a090"; // keccak256("adminMint(string,uint8,address)")[:4]

// 与 HahaNamehash 一致
const HAHA_NODE = "0xaa5a3a58f7c8841455eecaa0c6a6a0b40ace5681fbb31361a0d45b168179128f";
const MEME_NODE = "0x74df4ab2564a9f9bb6d4b6b77bf4fc02ac80f07bd9e1776d3967578b3fc36be4";

const state = {
  chainId: null,
  mode: "mainnet",
  provider: null,
  signer: null,
  address: null,
  walletType: null,
  season1Abi: null,
  registrarAbi: null,
  currentOrder: null, // { orderId, aiId, applicant, recipient, tld, label, dayIndex, status, tier }
  simulateResult: null,
  fulfillState: {}, // orderId -> { status, mintTx, error, ... }
};

function b32FromLabel(label) {
  return ethers.keccak256(ethers.toUtf8Bytes(label));
}

function tldNode(tld) {
  return tld === 0 ? HAHA_NODE : tld === 1 ? MEME_NODE : null;
}

// tokenId = keccak256(abi.encodePacked(tldNode, labelhash))，与 HahaNamehash.namehash 一致
function namehash(label, tld) {
  const parent = tldNode(tld);
  if (!parent) throw new Error("tld 非法");
  const labelHash = b32FromLabel(label);
  return ethers.keccak256(ethers.concat([parent, labelHash]));
}

// adminMint calldata，与 ops.py 的 admin_mint_calldata 完全一致
function adminMintCalldata(label, tld, recipient) {
  const iface = new ethers.Interface(["function adminMint(string,uint8,address)"]);
  const data = iface.encodeFunctionData("adminMint", [label, tld, recipient]);
  if (data.slice(0, 10) !== ADMIN_MINT_SELECTOR) {
    throw new Error("adminMint selector 与部署的 Registrar 不一致，停止");
  }
  return data;
}

function shorten(a) { return a ? a.slice(0, 10) + "…" + a.slice(-6) : ""; }

async function init() {
  try {
    const [s1Res, artRes] = await Promise.all([
      fetch("public/season1/HahaSeason1.abi.json"),
      fetch("public/artifacts.json"),
    ]);
    state.season1Abi = await s1Res.json();
    state.registrarAbi = (await artRes.json()).artifacts.HahaRegistrar.abi;
  } catch (e) {
    document.body.insertAdjacentHTML("afterbegin", `<div style="background:#7c2d12;color:#fed7aa;padding:12px 20px;">初始化失败：${e.message}。请先跑 node export-season1.mjs。</div>`);
    return;
  }

  document.getElementById("p-admin").textContent = ADDRS.admin;
  document.getElementById("p-season1").textContent = ADDRS.season1;
  document.getElementById("p-registrar").textContent = ADDRS.registrar;

  bindEvents();
  loadFulfillState();
  renderFulfillList();
  await restore();
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
  document.getElementById("btn-load-order").addEventListener("click", loadOrder);
  document.getElementById("btn-simulate").addEventListener("click", simulateMint);
  document.getElementById("btn-mint").addEventListener("click", signAndMint);
  document.getElementById("btn-verify-receipt").addEventListener("click", verifyReceipt);
  document.getElementById("btn-attest").addEventListener("click", attestFulfillment);
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
    onNetworkChanged();
  } catch (e) {
    alert(`连接 ${name} 失败：` + (e.shortMessage || e.message));
  }
}

function targetChainId() { return state.mode === "mainnet" ? CHAIN_MAINNET : CHAIN_TESTNET; }

function setMode(mode) {
  state.mode = mode;
  document.getElementById("btn-mainnet").classList.toggle("btn-primary", mode === "mainnet");
  document.getElementById("btn-testnet").classList.toggle("btn-primary", mode === "testnet");
  loadFulfillState();
  renderFulfillList();
}

function onNetworkChanged() {
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
// 发放状态持久化（按 chainId 隔离）
// ---------------------------------------------------------------------------

function storageKey() { return `haha-season1-fulfill-${targetChainId()}`; }
function loadFulfillState() {
  state.fulfillState = JSON.parse(localStorage.getItem(storageKey()) || "{}");
}
function saveFulfillState() { localStorage.setItem(storageKey(), JSON.stringify(state.fulfillState)); }

// ---------------------------------------------------------------------------
// 读订单 + 核对
// ---------------------------------------------------------------------------

function setResult(text, ok) {
  const el = document.getElementById("fulfill-result");
  el.textContent = text;
  el.className = "sr-result " + (ok ? "ok" : "err");
}

function setOrderDetail(text, ok) {
  const el = document.getElementById("order-detail");
  el.textContent = text;
  el.className = "sr-result " + (ok ? "ok" : "err");
}

async function loadOrder() {
  if (!requireConnected()) return;
  const orderId = document.getElementById("order-id").value.trim();
  if (!/^\d+$/.test(orderId)) { setOrderDetail("orderId 需为数字", false); return; }
  try {
    const s1 = new ethers.Contract(ADDRS.season1, state.season1Abi, state.provider);
    const o = await s1.order(orderId);
    // Order: aiId, applicant, recipient, tld, label, dayIndex, createdAt, status, tier
    if (Number(o[7]) === 0) { // status == None
      setOrderDetail(`orderId ${orderId} 不存在（status=None）。`, false);
      state.currentOrder = null;
      return;
    }
    const statusNames = { 1: "Pending", 2: "Fulfilled", 3: "CreditOpen", 4: "AccidentRefunded", 5: "AccidentClosed" };
    // Order: aiId(0), applicant(1), recipient(2), tld(3), label(4), dayIndex(5), createdAt(6), status(7), tier(8)
    const order = {
      orderId,
      aiId: o[0], applicant: o[1], recipient: o[2], tld: Number(o[3]), label: o[4],
      dayIndex: Number(o[5]), status: Number(o[7]), tier: Number(o[8]),
    };
    state.currentOrder = order;
    const tokenId = namehash(order.label, order.tld);

    // 查重：isMinted(namehash)
    const reg = new ethers.Contract(ADDRS.registrar, state.registrarAbi, state.provider);
    const minted = await reg.isMinted(tokenId);

    const lines = [
      `orderId: ${orderId}`,
      `label: ${order.label}${order.tld === 0 ? ".haha" : ".meme"}`,
      `recipient（原收件人）: ${order.recipient}`,
      `status: ${statusNames[order.status] || order.status}`,
      `tokenId(namehash): ${tokenId}`,
      `isMinted: ${minted ? "✅ 已铸造（NameTaken，停止）" : "未铸造（可发放）"}`,
    ];
    const ok = !minted && order.status === 1;
    setOrderDetail(lines.join("\n"), ok);
    if (!ok) {
      if (order.status !== 1) setResult(`订单状态为 ${statusNames[order.status]}，不是 Pending，停止发放。`, false);
    }
  } catch (e) {
    setOrderDetail("读订单失败：" + (e.shortMessage || e.message), false);
  }
}

function requireConnected() {
  if (!state.address) { setResult("请先连接钱包", false); return false; }
  if (state.chainId !== targetChainId()) { setResult("网络不符", false); return false; }
  if (state.address.toLowerCase() !== ADDRS.admin.toLowerCase()) {
    setResult("需管理员钱包 " + ADDRS.admin + "（当前 " + (state.address || "未连接") + "）", false);
    return false;
  }
  return true;
}

// 检查在途交易：该 orderId 是否已有 pending/broadcast 未确认的 mintTx
function inFlightTx(orderId) {
  const st = state.fulfillState[orderId];
  return st && (st.status === "sent" || st.status === "pending") && st.mintTx;
}

// ---------------------------------------------------------------------------
// ① 模拟 adminMint（eth_call，不广播）
// ---------------------------------------------------------------------------

async function simulateMint() {
  if (!requireConnected()) return;
  const order = state.currentOrder;
  if (!order) { setResult("请先读订单（orderId）", false); return; }
  if (order.status !== 1) { setResult("订单不是 Pending，不能发放", false); return; }
  try {
    const data = adminMintCalldata(order.label, order.tld, order.recipient);
    // eth_call 模拟
    const raw = await state.provider.call({ to: ADDRS.registrar, data, from: ADDRS.admin });
    // 模拟成功（没有 revert 即成功；返回值无意义，adminMint 无返回）
    state.simulateResult = { data, ok: true };
    setResult(
      `✅ 模拟成功（eth_call 未 revert）：adminMint(${order.label}, ${order.tld}, ${order.recipient})\n` +
      `calldata: ${data}\n可点「② 签名并广播」。`,
      true
    );
  } catch (e) {
    state.simulateResult = { ok: false };
    const msg = e.shortMessage || e.message || String(e);
    setResult(`❌ 模拟 revert，不广播：${msg}`, false);
  }
}

// ---------------------------------------------------------------------------
// ② 签名并广播（逐笔，单名字）
// ---------------------------------------------------------------------------

async function signAndMint() {
  if (!requireConnected()) return;
  const order = state.currentOrder;
  if (!order) { setResult("请先读订单", false); return; }
  if (order.status !== 1) { setResult("订单不是 Pending，不能发放", false); return; }
  if (inFlightTx(order.orderId)) {
    setResult(`该 orderId 已有在途交易 ${shorten(state.fulfillState[order.orderId].mintTx)}，请先「③ 核对回执」，不重复发放。`, false);
    return;
  }
  // 已在链上铸造则拒绝
  try {
    const tokenId = namehash(order.label, order.tld);
    const reg = new ethers.Contract(ADDRS.registrar, state.registrarAbi, state.provider);
    const minted = await reg.isMinted(tokenId);
    if (minted) { setResult("名字已铸造（NameTaken），停止发放，不重复铸造。", false); return; }
  } catch (e) { setResult("查重失败，停止：" + (e.shortMessage || e.message), false); return; }

  let data;
  try {
    data = state.simulateResult?.data || adminMintCalldata(order.label, order.tld, order.recipient);
  } catch (e) { setResult(e.message, false); return; }

  try {
    const tx = await state.signer.sendTransaction({ to: ADDRS.registrar, data });
    state.fulfillState[order.orderId] = { status: "sent", mintTx: tx.hash, label: order.label, tld: order.tld, recipient: order.recipient };
    saveFulfillState();
    renderFulfillList();
    setResult(`已广播 adminMint，tx: ${tx.hash}，等待确认…（状态：已广播未收据）`, true);
    const receipt = await tx.wait();
    await handleMintReceipt(order, receipt);
  } catch (e) {
    const msg = e.shortMessage || e.message || String(e);
    if (msg.includes("user rejected") || msg.includes("denied")) {
      setResult("已取消签名，未广播。该名字可稍后再签名。", false);
      return;
    }
    state.fulfillState[order.orderId] = { status: "failed", error: msg, label: order.label, tld: order.tld, recipient: order.recipient };
    saveFulfillState();
    renderFulfillList();
    setResult("广播失败：" + msg, false);
  }
}

// 核对铸造事件：NameMinted(tokenId, owner==recipient, label, tld, reservedMint=true) + Transfer(from=0, to==recipient, tokenId)
function checkMintLogs(order, receipt) {
  const tokenId = namehash(order.label, order.tld);
  const iface = new ethers.Interface(state.registrarAbi);
  let minted = false, transferred = false;
  for (const log of receipt.logs) {
    try {
      const parsed = iface.parseLog(log);
      if (!parsed) continue;
      if (parsed.name === "NameMinted") {
        const args = parsed.args;
        // NameMinted(uint256 tokenId, address owner, uint8 tld, bytes32 aiId, string label, bool reservedMint)
        if (args.tokenId.toString() === tokenId &&
            args.owner.toLowerCase() === order.recipient.toLowerCase() &&
            args.label === order.label &&
            Number(args.tld) === order.tld &&
            args.reservedMint === true) {
          minted = true;
        }
      } else if (parsed.name === "Transfer") {
        const args = parsed.args;
        // Transfer(address from, address to, uint256 tokenId)
        if (args.from === ethers.ZeroAddress &&
            args.to.toLowerCase() === order.recipient.toLowerCase() &&
            args.tokenId.toString() === tokenId) {
          transferred = true;
        }
      }
    } catch {}
  }
  return { minted, transferred, matched: minted && transferred };
}

async function handleMintReceipt(order, receipt) {
  if (receipt.status === 1) {
    const check = checkMintLogs(order, receipt);
    if (check.matched) {
      state.fulfillState[order.orderId] = {
        status: "confirmed", mintTx: receipt.hash, blockNumber: receipt.blockNumber,
        logCheck: "matched", label: order.label, tld: order.tld, recipient: order.recipient,
      };
      setResult(`✅ 铸造已确认并核对：NameMinted + Transfer 均匹配（tokenId=${namehash(order.label, order.tld)}，owner=${shorten(order.recipient)}）。\n可点「④ 见证发放」。`, true);
    } else {
      state.fulfillState[order.orderId] = {
        status: "confirmed", mintTx: receipt.hash, blockNumber: receipt.blockNumber,
        logCheck: "mismatch", label: order.label, tld: order.tld, recipient: order.recipient,
      };
      setResult(`⚠️ 交易成功但日志核对异常（mismatch：NameMinted=${check.minted}，Transfer=${check.transferred}）。不要标已发放，通知 L 核对签名参数。`, false);
    }
  } else {
    state.fulfillState[order.orderId] = { status: "failed", error: "交易 revert", mintTx: receipt.hash, label: order.label, tld: order.tld, recipient: order.recipient };
    setResult("❌ 交易 revert，未发放。", false);
  }
  saveFulfillState();
  renderFulfillList();
}

// ---------------------------------------------------------------------------
// ③ 核对回执（刷新后补查 / 替换交易处理）
// ---------------------------------------------------------------------------

async function verifyReceipt() {
  if (!requireConnected()) return;
  const order = state.currentOrder;
  if (!order) { setResult("请先读订单", false); return; }
  const st = state.fulfillState[order.orderId];
  if (!st || !st.mintTx) { setResult("该 orderId 无已广播交易，请先「② 签名并广播」。", false); return; }
  try {
    const receipt = await state.provider.getTransactionReceipt(st.mintTx);
    if (!receipt) {
      setResult(`交易 ${shorten(st.mintTx)} 尚未上链（pending）。稍后再试；若用同 nonce 替换过 gas，请以最新收据为准，旧哈希标 dropped。`, false);
      return;
    }
    await handleMintReceipt(order, receipt);
  } catch (e) {
    setResult("核对失败：" + (e.shortMessage || e.message), false);
  }
}

// ---------------------------------------------------------------------------
// ④ 见证发放 attestFulfillment(orderId, mintTxHash)
// ---------------------------------------------------------------------------

async function attestFulfillment() {
  if (!requireConnected()) return;
  const order = state.currentOrder;
  if (!order) { setResult("请先读订单", false); return; }
  const st = state.fulfillState[order.orderId];
  if (!st || st.logCheck !== "matched") {
    setResult("仅日志核对 matched 后才可见证发放（attestFulfillment）。当前未匹配，不调用。", false);
    return;
  }
  try {
    const s1 = new ethers.Contract(ADDRS.season1, state.season1Abi, state.signer);
    const tx = await s1.attestFulfillment(order.orderId, st.mintTx);
    setResult(`已发送 attestFulfillment(${order.orderId}, ${shorten(st.mintTx)})，tx: ${tx.hash}，等待确认…`, true);
    const receipt = await tx.wait();
    setResult(
      receipt.status === 1 ? "✅ 已见证发放，链上订单状态 Fulfilled。" : "❌ attestFulfillment revert",
      receipt.status === 1
    );
  } catch (e) {
    const msg = e.shortMessage || e.message || String(e);
    if (msg.includes("user rejected") || msg.includes("denied")) { setResult("已取消签名", false); return; }
    setResult("见证失败：" + msg, false);
  }
}

// ---------------------------------------------------------------------------
// 发放列表渲染
// ---------------------------------------------------------------------------

function renderFulfillList() {
  const el = document.getElementById("fulfill-list");
  el.innerHTML = "";
  const entries = Object.entries(state.fulfillState);
  if (entries.length === 0) {
    el.innerHTML = '<div class="step pending"><div class="name" style="color:var(--muted)">本批暂无发放记录。</div></div>';
    return;
  }
  for (const [orderId, st] of entries) {
    const statusText = { sent: "已广播", pending: "pending", confirmed: "已确认", failed: "失败" }[st.status] || st.status;
    const logCheckText = st.logCheck === "matched" ? " · 日志已核对" : st.logCheck === "mismatch" ? " · 日志异常" : "";
    const div = document.createElement("div");
    div.className = `step ${st.status || "pending"}`;
    div.innerHTML = `
      <div class="name">order ${orderId} · ${st.label}${st.tld === 0 ? ".haha" : ".meme"} · ${shorten(st.recipient)}</div>
      <div class="status">${statusText}${logCheckText}</div>
      <div class="detail">${st.mintTx ? "tx: " + shorten(st.mintTx) : ""}</div>
    `;
    el.appendChild(div);
  }
}

// ---------------------------------------------------------------------------
// 导入导出
// ---------------------------------------------------------------------------

function exportState() {
  const data = { chainId: targetChainId(), fulfillState: state.fulfillState };
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `season1-fulfill-state-${targetChainId()}.json`;
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
      state.fulfillState = data.fulfillState || {};
      saveFulfillState();
      renderFulfillList();
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
}

window.addEventListener("error", (e) => alert("页面脚本出错：" + (e.message || e.error)));
window.addEventListener("unhandledrejection", (e) => alert("异步出错：" + (e.reason?.shortMessage || e.reason?.message || e.reason)));

init();
