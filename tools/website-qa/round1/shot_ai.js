// AI page: run both on-chain checks, then screenshot the generator and info panels (desktop + mobile, zh + en).
const { chromium } = require("/workspace/hai/tools/node_modules/playwright-core");
const OUT = "/workspace/haha-dog-site/previews/";
(async () => {
  const b = await chromium.launch({ executablePath: "/usr/bin/google-chrome", args: ["--no-sandbox"] });
  for (const lang of ["zh", "en"]) for (const [dev, vp, mobile] of [["desktop", { width: 1440, height: 900 }, false], ["mobile", { width: 390, height: 844 }, true]]) {
    const ctx = await b.newContext({ viewport: vp, deviceScaleFactor: mobile ? 2 : 1, isMobile: mobile, hasTouch: mobile });
    await ctx.addInitScript(l => localStorage.setItem("haha.lang", l), lang);
    const p = await ctx.newPage(), errs = [];
    p.on("pageerror", e => errs.push(String(e))); p.on("console", m => { if (m.type() === "error") errs.push(m.text()); });
    await p.goto("http://127.0.0.1:18095/ai.html?seed=0xe30d88c427b9041ce20e2d496c4620ca140cb216a2096eca4f6a0d0cc7af999e", { waitUntil: "networkidle" });
    await p.click("#chain-btn"); await p.waitForFunction(() => /ok|bad/.test(document.getElementById("chain-verdict").className), null, { timeout: 30000 });
    const v1 = await p.textContent("#chain-verdict");
    await p.click("#data-btn"); await p.waitForFunction(() => /ok|bad/.test(document.getElementById("data-verdict").className), null, { timeout: 30000 });
    await p.waitForTimeout(500);
    await p.addStyleTag({ content: ".nav, header.nav { position: static !important; }" });
    const gen = await p.$("#gen"), info = await p.$(".ai-info");
    await (await p.$("#gen")).screenshot({ path: `${OUT}ai-gen-chain-${dev}-${lang}.png` });
    await (await info.evaluateHandle(e => e.closest(".panel"))).asElement().screenshot({ path: `${OUT}ai-info-${dev}-${lang}.png` });
    console.log(lang, dev, v1.slice(0, 60), "errors:", JSON.stringify(errs));
    await ctx.close();
  }
  await b.close();
})();
