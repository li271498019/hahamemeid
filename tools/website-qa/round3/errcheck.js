const { chromium } = require("/workspace/hai/tools/node_modules/playwright-core");
(async () => {
  const base = process.argv[2], b = await chromium.launch({ executablePath: "/usr/bin/google-chrome", args: ["--no-sandbox"] });
  for (const pg of ["/", "/ai.html", "/how.html", "/mint.html", "/market.html#dog", "/scan.html", "/api.html", "/erc8004.html", "/earn.html", "/skill.md", "/llms.txt"]) {
    const ctx = await b.newContext({ reducedMotion: "reduce" }), p = await ctx.newPage(), errs = [];
    p.on("pageerror", e => errs.push(String(e)));
    p.on("console", m => { if (m.type() === "error") errs.push(m.text().slice(0, 120)); });
    p.on("requestfailed", r => errs.push("failed " + r.url().slice(0, 80)));
    const resp = await p.goto(base + pg, { waitUntil: "networkidle" }); await p.waitForTimeout(1500);
    const info = await p.evaluate(() => ({ repoLinks: [...document.querySelectorAll('a[href*="hahamemeid"]')].length, soon: /即将公开|going public soon/i.test(document.body.innerText), wait: document.querySelectorAll(".dog-wait img").length, src: [...document.querySelectorAll(".dog-wait source")].length }));
    console.log(pg, resp.status(), JSON.stringify(info), JSON.stringify(errs.filter(e => !/404/.test(e))));
    await ctx.close();
  }
  await b.close();
})();
