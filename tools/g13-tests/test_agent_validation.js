// T9: agent 页验证块测试（G13）。
// 用 jsdom 加载 agent.html 内联脚本 + i18n.js，mock 链上与 API。
// 检查：新 i18n 键中英双语都不空白；验证块渲染；验证者无 .ai 显示“管理员验证”；
// “请求验证”按钮 fail-closed（持有人显示、非持有人隐藏）；validationRequest 指令模板可填。
const fs = require("fs");
const path = require("path");
const { JSDOM } = require("jsdom");

const SITE = path.join(__dirname, "..", "repo", "web", "site");
const OWNER = "0xe40a0c726fd2f990713ade7380c89800f4e8ac49"; // ha.haha 持有人（L 的测试地址）
const OTHER = "0x1111111111111111111111111111111111111111";
const ADMIN = "0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7";

const VALIDATIONS = {
  agentId: "30",
  validations: [
    {
      requestHash: "0x" + "ab".repeat(32),
      agentId: "30",
      validatorAddress: ADMIN,
      requestURI: "https://example.com/req/1.json",
      requestedAt: "2026-11-25T08:00:00Z",
      response: 100,
      responseURI: "https://example.com/evidence/1.json",
      responseHash: "0x" + "cd".repeat(32),
      tag: "endpoint-reachable",
      lastUpdatedAt: "2026-11-25T08:05:00Z",
      disputeStatus: "not_disputed",
      disputeCount: 0,
      originalResponse: 100,
      latestResponse: 100,
    },
    {
      requestHash: "0x" + "12".repeat(32),
      agentId: "30",
      validatorAddress: ADMIN,
      requestURI: "https://example.com/req/2.json",
      requestedAt: "2026-11-25T09:00:00Z",
      response: 0,
      responseURI: "https://example.com/evidence/2.json",
      responseHash: "0x" + "34".repeat(32),
      tag: "identity-verified",
      lastUpdatedAt: "2026-11-25T09:05:00Z",
      disputeStatus: "upheld",
      disputeCount: 1,
      originalResponse: 0,
      latestResponse: 0,
    },
  ],
};

let pass = 0;
let fail = 0;
function check(name, ok, extra) {
  if (ok) { pass++; console.log("PASS " + name); }
  else { fail++; console.log("FAIL " + name + (extra ? " :: " + extra : "")); }
}

function buildDom(lang, sessionAddr) {
  const html = fs.readFileSync(path.join(SITE, "agent.html"), "utf-8");
  const inline = html.match(/<script>\n([\s\S]*?)<\/script>\n\n<script src="\/js\/rain\.js/) [1];
  const dom = new JSDOM(
    '<!DOCTYPE html><html lang="zh-Hans" data-lang="' + lang + '"><head></head>' +
    '<body><div class="wrap"><main><section class="page" id="root"></section></main></div>' +
    '<div id="toast" role="status"></div></body></html>',
    { url: "https://haha.meme/agent.html?name=ha.haha", runScripts: "outside-only", pretendToBeVisual: true }
  );
  const w = dom.window;
  // mock fetch: validations API + anything else -> empty ok
  w.fetch = function (url) {
    if (String(url).indexOf("/v1/agents/30/validations") !== -1) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(VALIDATIONS) });
    }
    return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) });
  };
  // mock chain + session + ui
  w.HahaRPC = {
    tokenIdOf: () => "0x" + "11".repeat(32),
    nodeOf: () => "0x" + "11".repeat(32),
    ownerOf: () => Promise.resolve(OWNER),
    agentOfName: () => Promise.resolve(30),
    getAgent: () => Promise.resolve({ active: true, generation: 1, uri: "https://haha.meme/" }),
    getScore: () => Promise.resolve({ count: 2, sum: 10 }),
    aiName: (addr) => Promise.resolve(null), // 无 .ai：验证者应显示“管理员验证”
  };
  w.HahaIndex = { generations: () => Promise.resolve({ generations: [] }) };
  w.hahaNft = () => "";
  const copied = [];
  w.HahaUI = {
    copyText: (t) => { copied.push(t); return Promise.resolve(true); },
    toast: () => {},
  };
  // load site scripts in order
  w.eval(fs.readFileSync(path.join(SITE, "js", "config.js"), "utf-8"));
  w.eval(fs.readFileSync(path.join(SITE, "js", "i18n.js"), "utf-8"));
  w.eval(fs.readFileSync(path.join(SITE, "js", "instructions.js"), "utf-8"));
  w.eval(fs.readFileSync(path.join(SITE, "js", "session.js"), "utf-8"));
  // set login session before agent inline script runs
  if (sessionAddr) {
    w.localStorage.setItem("haha.session.v1", JSON.stringify({ ai: "hahameme", address: sessionAddr }));
  }
  w.eval(inline);
  return { dom, w, copied };
}

async function tick(ms) { return new Promise((r) => setTimeout(r, ms || 50)); }

(async () => {
  // ---- 1. i18n 新键中英双语 ----
  const KEYS = [
    "agent.validation", "agent.validationNote", "agent.noValidations",
    "agent.requestValidation", "agent.validationAdmin",
    "agent.validationTagEndpoint", "agent.validationTagIdentity",
    "agent.validationValidator", "agent.validationTime",
    "agent.validationEvidence", "agent.validationPending",
    "agent.disputeNotDisputed", "agent.disputeDisputed",
    "agent.disputeUpheld", "agent.disputeOverturned",
  ];
  for (const lang of ["zh", "en"]) {
    const { w } = buildDom(lang, null);
    for (const k of KEYS) {
      const v = w.HahaI18n.t(k);
      check("i18n " + lang + " " + k + " non-empty", typeof v === "string" && v.length > 0, JSON.stringify(v));
    }
    // task 模板可填，不抛错
    let taskOk = false, taskText = "";
    try {
      taskText = w.HahaI18n.task("validationRequest", { name: "ha.haha", agentId: "30" });
      taskOk = taskText.indexOf("ha.haha") !== -1 && taskText.indexOf("0xAF9d2D3b6717469B21464baA12B022817841952b") !== -1
        && taskText.indexOf("0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7") !== -1
        && taskText.indexOf("keccak256(abi.encodePacked(validatorAddress, agentId, requestURI))") !== -1;
    } catch (e) { taskText = "THREW: " + e.message; }
    check("task.validationRequest fills (" + lang + ")", taskOk, taskText.slice(0, 120));
  }

  // ---- 2. 持有人登录：验证块渲染 + 请求按钮显示 ----
  {
    const { dom, w, copied } = buildDom("zh", OWNER);
    await tick(300);
    const root = dom.window.document.getElementById("root").innerHTML;
    check("zh 验证块标题显示", root.indexOf("验证") !== -1);
    check("zh 验证说明显示", root.indexOf("验证由 HahaValidation 提供") !== -1);
    check("zh 记录1 tag 接口可达", root.indexOf("接口可达") !== -1);
    check("zh 记录1 分数 100 / 100", root.indexOf("100 / 100") !== -1);
    check("zh 记录2 tag 身份真实性", root.indexOf("身份真实性") !== -1);
    check("zh 记录2 分数 0 / 100", root.indexOf("0 / 100") !== -1);
    check("zh 验证者无.ai 显示管理员验证", root.indexOf("管理员验证") !== -1);
    check("zh 争议状态 未争议", root.indexOf("未争议") !== -1);
    check("zh 争议状态 已复核-维持原判", root.indexOf("已复核-维持原判") !== -1);
    check("zh 证据链接显示", root.indexOf("https://example.com/evidence/1.json") !== -1);
    check("zh 请求验证按钮显示（持有人）", root.indexOf('id="request-validation"') !== -1);
    // 点请求验证按钮，复制出 validationRequest 指令
    const btn = dom.window.document.getElementById("request-validation");
    btn.click();
    await tick(100);
    check("点击请求验证复制出指令", copied.length === 1 && copied[0].indexOf("validationRequest") !== -1
      && copied[0].indexOf("HahaValidation") !== -1, copied[0] ? copied[0].slice(0, 100) : "nothing copied");
  }

  // ---- 3. 非持有人登录：请求按钮隐藏 ----
  {
    const { dom } = buildDom("zh", OTHER);
    await tick(300);
    const root = dom.window.document.getElementById("root").innerHTML;
    check("zh 请求验证按钮隐藏（非持有人）", root.indexOf('id="request-validation"') === -1);
    check("zh 验证块仍显示（非持有人）", root.indexOf("接口可达") !== -1);
  }

  // ---- 4. 未登录：请求按钮隐藏 ----
  {
    const { dom } = buildDom("zh", null);
    await tick(300);
    const root = dom.window.document.getElementById("root").innerHTML;
    check("zh 请求验证按钮隐藏（未登录）", root.indexOf('id="request-validation"') === -1);
  }

  // ---- 5. 英文：验证块渲染 ----
  {
    const { dom } = buildDom("en", OWNER);
    await tick(300);
    const root = dom.window.document.getElementById("root").innerHTML;
    check("en Validation heading", root.indexOf("Validation") !== -1);
    check("en Endpoint reachable", root.indexOf("Endpoint reachable") !== -1);
    check("en Identity verified", root.indexOf("Identity verified") !== -1);
    check("en Admin validation", root.indexOf("Admin validation") !== -1);
    check("en Reviewed — upheld", root.indexOf("Reviewed — upheld") !== -1);
  }

  // ---- 6. 空记录：显示暂无验证记录 ----
  {
    const html = fs.readFileSync(path.join(SITE, "agent.html"), "utf-8");
    const inline = html.match(/<script>\n([\s\S]*?)<\/script>\n\n<script src="\/js\/rain\.js/) [1];
    const dom = new JSDOM(
      '<!DOCTYPE html><html lang="zh-Hans" data-lang="zh"><head></head>' +
      '<body><div class="wrap"><main><section class="page" id="root"></section></main></div>' +
      '<div id="toast" role="status"></div></body></html>',
      { url: "https://haha.meme/agent.html?name=ha.haha", runScripts: "outside-only", pretendToBeVisual: true }
    );
    const w = dom.window;
    w.fetch = () => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ agentId: "30", validations: [] }) });
    w.HahaRPC = {
      tokenIdOf: () => "0x" + "11".repeat(32),
      ownerOf: () => Promise.resolve(OWNER),
      agentOfName: () => Promise.resolve(30),
      getAgent: () => Promise.resolve({ active: true, generation: 1, uri: "" }),
      getScore: () => Promise.resolve({ count: 0, sum: 0 }),
      aiName: () => Promise.resolve(null),
    };
    w.HahaIndex = { generations: () => Promise.resolve({ generations: [] }) };
    w.hahaNft = () => "";
    w.HahaUI = { copyText: () => Promise.resolve(true), toast: () => {} };
    w.eval(fs.readFileSync(path.join(SITE, "js", "config.js"), "utf-8"));
    w.eval(fs.readFileSync(path.join(SITE, "js", "i18n.js"), "utf-8"));
    w.eval(fs.readFileSync(path.join(SITE, "js", "instructions.js"), "utf-8"));
    w.eval(fs.readFileSync(path.join(SITE, "js", "session.js"), "utf-8"));
    w.eval(inline);
    await tick(300);
    const root = dom.window.document.getElementById("root").innerHTML;
    check("zh 空记录显示暂无验证记录", root.indexOf("暂无验证记录") !== -1);
  }

  console.log("\n" + pass + " passed, " + fail + " failed");
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error("TEST CRASH:", e); process.exit(2); });
