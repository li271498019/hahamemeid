// Compare the in-browser model with the deployed HahaDogRenderer.svgOf(seed) on BSC (read-only).
const fs = require("fs");
const M = require("../site/js/haha-ai-model.js");
const D = __dirname + "/../site/ai-model/";
const W = JSON.parse(fs.readFileSync(D + "weights-int8.json"));
const TPL = JSON.parse(fs.readFileSync(D + "trait-templates.json"));
const RPC = process.env.RPC || "https://bsc-dataseed.binance.org";
const RENDERER = "0xCA760D9D3E76DcDC7AC6bcc55D53346b8a2c107E";
const DOG = "0x26f88A5db4925e9aFa35B1096FdD6DBa09f056c6";
async function call(to, data, gas) {
  const p = { to, data }; if (gas) p.gas = "0x" + gas.toString(16);
  const r = await fetch(RPC, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "eth_call", params: [p, "latest"] }) });
  const j = await r.json(); if (j.error) throw new Error(JSON.stringify(j.error)); return j.result;
}
function decStr(hex) { const b = Buffer.from(hex.slice(2), "hex"); const len = Number(BigInt("0x" + b.subarray(32, 64).toString("hex"))); return b.subarray(64, 64 + len).toString("utf8"); }
(async () => {
  const seeds = process.argv.slice(2);
  const sel = "0x" + (process.env.SEL || "");
  for (const s of seeds) {
    const t0 = Date.now();
    const data = "0x" + process.env.SVGOF + s.replace(/^0x/, "");
    const out = decStr(await call(RENDERER, data, 30000000));
    const local = M.svgFor(M.traits(W, TPL, M.fromHex(s)));
    console.log(s.slice(0, 12), "chain", out.length, "local", local.length, out === local ? "IDENTICAL" : "DIFF", Date.now() - t0, "ms");
  }
})();
