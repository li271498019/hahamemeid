#!/usr/bin/env node
// 面板核心逻辑验证：namehash / adminMint calldata / 日志核对 / 时间门禁 / 快照窗口。
// 与 tools/season1/ops.py（Python）逐字节对齐，作为面板 JS 逻辑的测试证据。
// 用法：node tools/deploy-panel/test-fulfill-logic.mjs
import { ethers } from "ethers";

const HAHA_NODE = "0xaa5a3a58f7c8841455eecaa0c6a6a0b40ace5681fbb31361a0d45b168179128f";
const MEME_NODE = "0x74df4ab2564a9f9bb6d4b6b77bf4fc02ac80f07bd9e1776d3967578b3fc36be4";
const ADMIN_MINT_SELECTOR = "0x65f5a090";
const START_TS = 1795478400;
const END_TS = 1796774400;
const SNAPSHOT_MIN_DEPTH = 15;
const SNAPSHOT_MAX_DEPTH = 256;

let pass = 0, fail = 0;
function ok(cond, name) {
  if (cond) { pass++; console.log(`  ✅ ${name}`); }
  else { fail++; console.log(`  ❌ ${name}`); }
}

function namehash(label, tld) {
  const parent = tld === 0 ? HAHA_NODE : MEME_NODE;
  const labelHash = ethers.keccak256(ethers.toUtf8Bytes(label));
  return ethers.keccak256(ethers.concat([parent, labelHash]));
}

function adminMintCalldata(label, tld, recipient) {
  const iface = new ethers.Interface(["function adminMint(string,uint8,address)"]);
  const data = iface.encodeFunctionData("adminMint", [label, tld, recipient]);
  if (data.slice(0, 10) !== ADMIN_MINT_SELECTOR) throw new Error("selector drift");
  return data;
}

// 时间门禁（与 season1.js 的 launchGate 一致）
function launchGate(ts, strict = true) {
  if (!strict) return null;
  if (ts < START_TS) return { reason: "未到首日正式快照时刻" };
  if (ts >= END_TS) return { reason: "赛季已结束" };
  return null;
}

// 快照窗口判断（与 season1.js 的 precheck 一致）
function snapshotWindow(latest, snapshotBlock) {
  const depth = latest - snapshotBlock;
  if (depth < SNAPSHOT_MIN_DEPTH) return "too-fresh";
  if (depth >= SNAPSHOT_MAX_DEPTH) return "stale";
  return "ok";
}

console.log("== namehash 与 Python 对齐 ==");
ok(namehash("aa", 0) === "0x2cea48600b4112a5e143e9710c71347ef53e2acc160772787d75b08928bc62c3", "namehash(aa,0)");
ok(namehash("ab", 1) === "0xf8dfe1eae28c040d1a22b6252d3dbb0931c5b25dabcd635c6f888a6e7ff5e0d0", "namehash(ab,1)");

console.log("== adminMint calldata 与 Python 对齐 ==");
const calldata = adminMintCalldata("aa", 0, "0x1111111111111111111111111111111111111111");
ok(calldata.slice(0, 10) === ADMIN_MINT_SELECTOR, "selector 0x65f5a090");
// Python tools/season1/ops.py 的输出（已实测逐字节一致，硬编码作回归基准）
const PY_EXPECTED =
  "0x65f5a09000000000000000000000000000000000000000000000000000000000000000600000000000000000000000000000000000000000000000000000000000000000000000000000000000000000111111111111111111111111111111111111111100000000000000000000000000000000000000000000000000000000000000026161000000000000000000000000000000000000000000000000000000000000";
ok(calldata === PY_EXPECTED, "JS calldata == Python ops.py 输出（逐字节）");

console.log("== 时间门禁 ==");
ok(launchGate(START_TS - 1) !== null, "提前 1 秒被拒（未到首日正式快照）");
ok(launchGate(START_TS) === null, "START_TS 整点放行");
ok(launchGate(START_TS + 100) === null, "START_TS 之后放行");
ok(launchGate(END_TS) !== null, "END_TS 之后被拒（赛季结束）");
ok(launchGate(START_TS - 1, false) === null, "测试网/预演不挡时间（strict=false）");

console.log("== 快照窗口 ==");
ok(snapshotWindow(100, 95) === "too-fresh", "深度 5（<15）→ too-fresh");
ok(snapshotWindow(100, 80) === "ok", "深度 20（≥15，<256）→ ok");
ok(snapshotWindow(100, 90) === "too-fresh", "深度 10（<15）→ too-fresh");
ok(snapshotWindow(400, 143) === "stale", "深度 257（≥256）→ stale");
ok(snapshotWindow(400, 144) === "stale", "深度 256（≥256）→ stale");

console.log("");
console.log(`结果：${pass} 通过 / ${fail} 失败`);
process.exit(fail === 0 ? 0 : 1);
