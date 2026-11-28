// node shot2.js <path> <outPrefix> [--addr 0x..] [--ai name] [--lang zh] [--wait 3500] [--click sel] [--only desktop|mobile] [--full] [--el sel] [--port 18096]
const { chromium } = require("/workspace/hai/tools/node_modules/playwright-core");
const a = process.argv.slice(2), page = a[0], prefix = a[1], o = {};
for (let i = 2; i < a.length; i++) { if (a[i].startsWith("--")) { const k = a[i].slice(2); o[k] = (a[i + 1] && !a[i + 1].startsWith("--")) ? a[++i] : true; } }
(async () => {
  const b = await chromium.launch({ executablePath: "/usr/bin/google-chrome", args: ["--no-sandbox"] });
  const lang = o.lang || "zh";
  for (const [name, vp, mobile] of [["desktop", { width: 1440, height: 900 }, false], ["mobile", { width: 390, height: 844 }, true]]) {
    if (o.only && o.only !== name) continue;
    const ctx = await b.newContext({ viewport: vp, deviceScaleFactor: mobile ? 2 : 1, isMobile: mobile, hasTouch: mobile, locale: lang === "zh" ? "zh-CN" : "en-US" });
    await ctx.addInitScript(([l, ai, addr]) => {
      try { localStorage.setItem("haha.lang", l); if (ai) localStorage.setItem("haha.session.v1", JSON.stringify(addr ? { ai, address: addr } : { ai })); } catch (e) {}
    }, [lang, o.ai || "", o.addr || ""]);
    const p = await ctx.newPage(), errs = [], reqs = [];
    p.on("pageerror", e => errs.push(String(e)));
    p.on("console", m => { if (m.type() === "error") errs.push(m.text()); });
    p.on("request", r => { const u = new URL(r.url()); if (u.pathname.startsWith("/api") || u.pathname.startsWith("/rpc")) reqs.push(u.pathname); });
    await p.goto("" + (o.base || ("http://127.0.0.1:" + (o.port || 18096))) + page, { waitUntil: "networkidle" });
    await p.waitForTimeout(Number(o.wait || 3500));
    if (o.click) { await p.click(o.click).catch(e => errs.push("click " + e.message)); await p.waitForTimeout(Number(o.wait || 3500)); }
    const sum = {}; reqs.forEach(r => { const k = r.replace(/\/[^/]*$/, "/…").slice(0, 40); sum[r] = (sum[r] || 0) + 1; });
    console.log(name, lang, "overflowX:", await p.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), "errors:", JSON.stringify(errs), "requests:", JSON.stringify(sum));
    const out = `${prefix}-${name}-${lang}.png`;
    if (o.el) { const el = await p.$(o.el); await el.scrollIntoViewIfNeeded(); await el.screenshot({ path: out }); }
    else await p.screenshot({ path: out, fullPage: o.full !== "false" });
    await ctx.close();
  }
  await b.close();
})();
