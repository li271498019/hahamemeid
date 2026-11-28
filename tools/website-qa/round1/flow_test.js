// Local flow test: mints/market pages against the live chain, with SIMULATED market listings
// (no real listing exists yet): #1 valid at 0.05 BNB, #2 invalid at 0.2 BNB. Prints the copied agent commands.
const { chromium } = require("/workspace/hai/tools/node_modules/playwright-core");
const OUT = "/workspace/haha-dog-site/previews/";
const MKT = "0xd7f5502bd7a52e17959bf4b7f1180f6e3611fd49";
const enc = (n) => BigInt(n).toString(16).padStart(64, "0");
(async () => {
  const b = await chromium.launch({ executablePath: "/usr/bin/google-chrome", args: ["--no-sandbox"] });
  const real = await (await fetch("https://bsc-dataseed.binance.org", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "eth_call", params: [{ to: "0x26f88A5db4925e9aFa35B1096FdD6DBa09f056c6", data: "0x6352211e" + enc(1) }, "latest"] }) })).json();
  if (!real.result) throw new Error(JSON.stringify(real)); const owner1 = "0x" + real.result.slice(26);
  for (const lang of ["zh", "en"]) {
    for (const [dev, vp, mobile] of [["desktop", { width: 1440, height: 900 }, false], ["mobile", { width: 390, height: 844 }, true]]) {
      const ctx = await b.newContext({ viewport: vp, deviceScaleFactor: mobile ? 2 : 1, isMobile: mobile, hasTouch: mobile, permissions: ["clipboard-read", "clipboard-write"] });
      await ctx.addInitScript(l => { localStorage.setItem("haha.lang", l); }, lang);
      const p = await ctx.newPage(), errs = [];
      p.on("pageerror", e => errs.push(String(e)));
      p.on("console", m => { if (m.type() === "error" && !/404/.test(m.text())) errs.push(m.text()); });
      await p.route("https://bsc-dataseed.binance.org/**", async route => {
        const body = JSON.parse(route.request().postData());
        const one = (c) => {
          const to = (c.params[0].to || "").toLowerCase(), d = c.params[0].data;
          if (to === MKT && d.startsWith("0xde74e57b")) {
            const id = parseInt(d.slice(10), 16);
            if (id === 1) return "0x" + owner1.slice(2).padStart(64, "0") + enc(50000000000000000n) + enc(0);
            if (id === 2) return "0x" + owner1.slice(2).padStart(64, "0") + enc(200000000000000000n) + enc(0);
            return "0x" + "0".repeat(192);
          }
          if (to === MKT && d.startsWith("0xf577a500")) return "0x" + enc(parseInt(d.slice(10), 16) === 1 ? 1 : 0);
          if (to === MKT && d.startsWith("0x0964c95b")) return "0x" + enc(123000000000000000n);
          return null;
        };
        const mock = Array.isArray(body) ? body.map(c => one(c)) : [one(body)];
        if (mock.every(x => x === null)) return route.continue();
        if (mock.some(x => x === null)) { // mixed: fetch real for the rest
          const r = await fetch("https://bsc-dataseed.binance.org", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) }); const j = await r.json();
          const arr = Array.isArray(j) ? j : [j];
          return route.fulfill({ json: Array.isArray(body) ? arr.map((x, i) => mock[i] ? { jsonrpc: "2.0", id: x.id, result: mock[i] } : x) : (mock[0] ? { jsonrpc: "2.0", id: body.id, result: mock[0] } : j), headers: { "access-control-allow-origin": "*" } });
        }
        route.fulfill({ json: Array.isArray(body) ? body.map((c, i) => ({ jsonrpc: "2.0", id: c.id, result: mock[i] })) : { jsonrpc: "2.0", id: body.id, result: mock[0] }, headers: { "access-control-allow-origin": "*" } });
      });
      const clip = () => p.evaluate(() => navigator.clipboard.readText());
      // market, dog tab
      await p.goto("http://127.0.0.1:18095/market.html#dog", { waitUntil: "networkidle" });
      await p.waitForSelector("#dog-grid .dog-card", { timeout: 20000 });
      await p.fill("#mk-dog-addr", owner1); await p.click("#dog-mine-form button");
      await p.waitForSelector("#dog-mine .dog-card", { timeout: 20000 }); await p.waitForTimeout(800);
      await p.evaluate(() => scrollTo(0, 0)); await p.waitForTimeout(300);
      await p.screenshot({ path: `${OUT}market-dog-${dev}-${lang}.png`, fullPage: true });
      if (lang === "zh" && dev === "desktop") {
        const log = {};
        await p.click("[data-dbuy]"); log.buy = await clip();
        await p.fill("#dog-mine .dog-card:not(.invalid) .price-input", "0.3");
        const mine = await p.$$("#dog-mine .dog-card");
        for (const c of mine) { const t = await c.$("[data-dlist]"); if (t) { await c.fill(".price-input", "0.3"); await t.click(); log.list = await clip(); break; } }
        await p.click("#dog-mine [data-dreprice]"); log.reprice = await clip();   // no price typed: should refuse
        await p.fill("#dog-mine .dog-card:has([data-dreprice]) .price-input", "0.07"); await p.click("#dog-mine [data-dreprice]"); log.repriceOk = await clip();
        await p.click("#dog-mine [data-dcancel]"); log.cancel = await clip();
        await p.click("#dog-grid [data-dclear]"); log.clear = await clip();
        await p.click("[data-dwithdraw]"); log.withdraw = await clip();
        require("fs").writeFileSync(OUT + "agent-commands-market-zh.json", JSON.stringify(log, null, 2));
      }
      // mint page
      await p.goto("http://127.0.0.1:18095/mint.html?id=1", { waitUntil: "networkidle" });
      await p.waitForSelector("#view-table tr", { timeout: 20000 });
      await p.fill("#quota-addr", owner1); await p.click("#quota-form button");
      await p.waitForFunction(() => /额度|Quota|没有|holds/.test(document.getElementById("quota-out").textContent), null, { timeout: 20000 });
      const quota = await p.textContent("#quota-out");
      await p.click("#view-chain"); await p.waitForFunction(() => /ok|bad/.test(document.getElementById("view-verdict").className), null, { timeout: 30000 });
      const verdict = await p.textContent("#view-verdict");
      if (lang === "zh" && dev === "desktop") {
        const log = {};
        await p.click('[data-dog-mint="1"]'); log.mint1 = await clip();
        await p.click('[data-dog-mint="2"]'); log.mint2 = await clip();
        await p.fill("#reroll-id", "1"); await p.click("#reroll-form button"); log.reroll = await clip();
        require("fs").writeFileSync(OUT + "agent-commands-mint-zh.json", JSON.stringify(log, null, 2));
      }
      if (lang === "en" && dev === "desktop") {
        const log = {};
        await p.click('[data-dog-mint="2"]'); log.mint2 = await clip();
        await p.fill("#reroll-id", "1"); await p.click("#reroll-form button"); log.reroll = await clip();
        require("fs").writeFileSync(OUT + "agent-commands-mint-en.json", JSON.stringify(log, null, 2));
      }
      await p.waitForTimeout(500);
      await p.evaluate(() => scrollTo(0, 0)); await p.waitForTimeout(300);
      await p.screenshot({ path: `${OUT}mint-${dev}-${lang}.png`, fullPage: true });
      console.log(lang, dev, "| quota:", quota, "| tokenURI:", verdict, "| errors:", JSON.stringify(errs));
      await ctx.close();
    }
  }
  await b.close();
})();
