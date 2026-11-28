// node shotrange.js <path> <outPrefix> <startSel> <endSel> [lang] [port]
const { chromium } = require("/workspace/hai/tools/node_modules/playwright-core");
const [pg, prefix, a, b, lang = "zh", port = "18096"] = process.argv.slice(2);
(async () => {
  const br = await chromium.launch({ executablePath: "/usr/bin/google-chrome", args: ["--no-sandbox"] });
  for (const [name, vp, mobile] of [["desktop", { width: 1440, height: 900 }, false], ["mobile", { width: 390, height: 844 }, true]]) {
    const ctx = await br.newContext({ viewport: vp, deviceScaleFactor: mobile ? 2 : 1, isMobile: mobile, hasTouch: mobile, locale: lang === "zh" ? "zh-CN" : "en-US" });
    await ctx.addInitScript(l => { try { localStorage.setItem("haha.lang", l); } catch (e) {} }, lang);
    const p = await ctx.newPage(); await p.goto("http://127.0.0.1:" + port + pg, { waitUntil: "networkidle" }); await p.waitForTimeout(2500);
    await p.addStyleTag({ content: "header{position:static !important}" });
    const box = await p.evaluate(([a, b]) => { const A = document.querySelector(a).getBoundingClientRect(), B = document.querySelector(b).getBoundingClientRect(); const sy = scrollY; return { x: 0, y: A.top + sy - 10, w: innerWidth, h: B.bottom - A.top + 20 }; }, [a, b]);
    await p.screenshot({ path: `${prefix}-${name}-${lang}.png`, fullPage: true, clip: { x: 0, y: box.y, width: box.w, height: Math.min(box.h, 6000) } });
    await ctx.close();
  }
  await br.close();
})();
