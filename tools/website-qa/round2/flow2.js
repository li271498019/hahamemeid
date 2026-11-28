const { chromium } = require("/workspace/hai/tools/node_modules/playwright-core");
(async () => {
  const b = await chromium.launch({ executablePath: "/usr/bin/google-chrome", args: ["--no-sandbox"] });
  const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, permissions: ["clipboard-read", "clipboard-write"], locale: "zh-CN" });
  await ctx.addInitScript(() => { try { localStorage.setItem("haha.lang", "zh"); } catch (e) {} });
  const p = await ctx.newPage(), errs = [];
  p.on("pageerror", e => errs.push(String(e)));
  await p.goto("http://127.0.0.1:18096/mint.html", { waitUntil: "networkidle" });
  await p.waitForTimeout(2500);
  const out = {};
  out.loggedOut = await p.$eval("#mine-grid", e => e.innerText.replace(/\s+/g, " "));
  out.refreshHidden = await p.$eval("#mine-refresh", e => e.hidden);
  // log in the way the page does, then the address resolves
  await p.evaluate(() => { HahaSession.login("tester"); });
  await p.waitForTimeout(800);
  out.loggedInNoAddr = await p.$eval("#mine-grid", e => e.innerText.replace(/\s+/g, " "));
  await p.evaluate(() => { HahaSession.setAddress("0xccfaa6a7dbc37957c262bbf262765d2283d1c3b3"); });
  await p.waitForSelector("[data-reroll]", { timeout: 15000 });
  out.cards = await p.$$eval("#mine-grid .dog-card", els => els.map(e => e.innerText.replace(/\s+/g, " ")));
  await p.click('[data-reroll="9"]');
  await p.waitForTimeout(500);
  out.clip = (await p.evaluate(() => navigator.clipboard.readText())).slice(0, 400);
  out.toast = await p.$eval("#toast", e => e.innerText).catch(() => "");
  // card art opens the viewer
  await p.click('#mine-grid [data-view="8"]'); await p.waitForTimeout(2500);
  out.viewer = await p.$eval("#view-table", e => e.innerText.replace(/\s+/g, " ").slice(0, 120));
  // logout
  await p.evaluate(() => { HahaSession.logout(); }); await p.waitForTimeout(500);
  out.afterLogout = await p.$eval("#mine-grid", e => e.innerText.replace(/\s+/g, " "));
  out.errors = errs;
  console.log(JSON.stringify(out, null, 1));
  await b.close();
})();
