// Usage: node shot.js <page> <outPrefix> [zh|en] — desktop and mobile full-page shots + console errors.
const { chromium } = require("/workspace/hai/tools/node_modules/playwright-core");
(async () => {
  const [page, prefix, lang = "zh", wait = "2500", sel] = process.argv.slice(2);
  const b = await chromium.launch({ executablePath: "/usr/bin/google-chrome", args: ["--no-sandbox"] });
  for (const [name, vp, mobile] of [["desktop", { width: 1440, height: 900 }, false], ["mobile", { width: 390, height: 844 }, true]]) {
    const ctx = await b.newContext({ viewport: vp, deviceScaleFactor: mobile ? 2 : 1, isMobile: mobile, hasTouch: mobile, locale: lang === "zh" ? "zh-CN" : "en-US" });
    await ctx.addInitScript(l => { try { localStorage.setItem("haha.lang", l); } catch (e) {} }, lang);
    const p = await ctx.newPage(), errs = [];
    p.on("pageerror", e => errs.push(String(e)));
    p.on("console", m => { if (m.type() === "error") errs.push(m.text()); });
    await p.goto("http://127.0.0.1:18095" + page, { waitUntil: "networkidle" });
    await p.waitForTimeout(Number(wait));
    if (sel) { await p.click(sel).catch(e => errs.push("click " + e.message)); await p.waitForTimeout(Number(wait)); }
    console.log(name, lang, "overflowX:", await p.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), "errors:", JSON.stringify(errs));
    await p.screenshot({ path: `${prefix}-${name}-${lang}.png`, fullPage: true });
    await ctx.close();
  }
  await b.close();
})();
