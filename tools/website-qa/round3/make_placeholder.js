/* Renders the Haha AI latent-morph animation from ai.html (same keyframes, same integer model) into raw frames.
 * Usage: node make_placeholder.js <site dir> <out dir>. Then python3 make_placeholder.py. */
var fs = require("fs"), path = require("path");
var site = process.argv[2], out = process.argv[3];
var M = require(path.join(site, "js/haha-ai-model.js"));
var W = JSON.parse(fs.readFileSync(path.join(site, "ai-model/weights-int8.json"), "utf8"));
var keys = [], STEPS = 14, HOLD = 10, per = STEPS + HOLD;
for (var i = 1; i <= 6; i++) keys.push(M.seedToZ(M.keccak256(M.utf8("Haha AI #" + i))));
function zAt(f) {
  var k = Math.floor(f / per), s = f % per, a = keys[k], b = keys[(k + 1) % keys.length];
  if (s < HOLD) return a.slice();
  var u = (s - HOLD) / STEPS;
  return a.map(function (v, j) { return Math.round(v + (b[j] - v) * u); });
}
fs.mkdirSync(out, { recursive: true });
var frames = [];
for (var f = 0; f < per * keys.length; f++) {
  var z = zAt(f), r = M.forward(W, z), im = M.compose(r.cells, r.picks, 1, 2), buf = Buffer.alloc(24 * 24 * 3), p = 0;
  for (var y = 0; y < 24; y++) for (var x = 0; x < 24; x++) { var c = im[y][x]; buf[p++] = c[0]; buf[p++] = c[1]; buf[p++] = c[2]; }
  fs.writeFileSync(path.join(out, "f" + String(f).padStart(3, "0") + ".rgb"), buf);
}
console.log("frames", per * keys.length);
