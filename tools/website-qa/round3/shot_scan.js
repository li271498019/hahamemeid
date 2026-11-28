const { chromium } = require("/workspace/hai/tools/node_modules/playwright-core");
(async () => {
  const b = await chromium.launch({ executablePath: "/usr/bin/google-chrome", args: ["--no-sandbox"] });
  for (const [name, vp, mobile] of [["desktop", { width: 1440, height: 900 }, false], ["mobile", { width: 390, height: 844 }, true]]) {
    const ctx = await b.newContext({ viewport: vp, deviceScaleFactor: mobile ? 2 : 1, isMobile: mobile, locale: "zh-CN" });
    await ctx.addInitScript(() => { try { localStorage.setItem("haha.lang", "zh"); } catch (e) {} });
    const p = await ctx.newPage(), errs = [];
    p.on("pageerror", e => errs.push(String(e)));
    p.on("console", m => { if (m.type() === "error" && !/404/.test(m.text())) errs.push(m.text()); });
    await p.goto("http://127.0.0.1:18112/scan.html", { waitUntil: "networkidle" });
    for (const id of [18, 20, 17]) {
      await p.fill("#scan-search-input", "dog " + id); await p.press("#scan-search-input", "Enter"); await p.waitForTimeout(1500);
      const el = await p.$("#scan-search-result"); await el.scrollIntoViewIfNeeded();
      await el.screenshot({ path: `../previews/scan-dog${id}-${name}-zh.png` });
    }
    console.log(name, JSON.stringify(errs));
    await ctx.close();
  }
  await b.close();
})();
