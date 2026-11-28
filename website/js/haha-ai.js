/* Haha AI page: live generation, latent morph, hash check and test vectors. */
(function () {
  "use strict";
  var M = window.HahaAIModel;
  var PUB_KECCAK = "0x1d2239644b5273c4f1925c489d32900a564262bce6597f94a929489cfbe58078";
  var PUB_SHA = "0x383d75587f6e6453dae603fd18cab79dc5f9f6cd7a4e60299451a363ea8cbbf2";
  var PUB_DATA = "0x72f92c628a64bc0d5652d285c6789fa0f84cb462d328604cf3dcff224704f8da";
  var D = window.HahaDog;
  var BASE = "/ai-model/";
  var W = null, TPL = null, current = null;

  function $(id) { return document.getElementById(id); }
  function T(k) { return window.HahaI18n ? HahaI18n.t(k) : k; }
  function F(k, vars) { return T(k).replace(/\{(\w+)\}/g, function (_, n) { return vars[n] == null ? "" : String(vars[n]); }); }
  function zh() { return !window.HahaI18n || HahaI18n.lang() === "zh"; }
  function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
  function toast(msg) { if (window.HahaUI && HahaUI.toast) HahaUI.toast(msg); }
  function copy(text) {
    var done = function () { toast(T("ai.copied")); };
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(done, function () {});
    else if (window.HahaUI && HahaUI.copyText) HahaUI.copyText(text).then(function (ok) { if (ok) done(); });
  }
  function getJSON(name) {
    return fetch(BASE + name, { cache: "force-cache" }).then(function (r) {
      if (!r.ok) throw new Error(name + " " + r.status);
      return r.json();
    });
  }
  var ready = Promise.all([getJSON("weights-int8.json"), getJSON("trait-templates.json")]).then(function (a) {
    W = a[0]; TPL = a[1];
  });

  $("pub-keccak").textContent = PUB_KECCAK;
  $("pub-sha").textContent = PUB_SHA;
  $("pub-data").textContent = PUB_DATA;
  /* The four deployed Haha Dog contracts, with BscScan links. */
  $("ai-contracts").innerHTML = [["HahaDogModel", "dogModel"], ["HahaDogRenderer", "dogRenderer"], ["HahaDog", "dog"], ["HahaDogMarket", "dogMarket"]].map(function (c) {
    var a = D.ADDR[c[1]];
    return '<div class="ai-contract"><b>' + c[0] + '</b> <code>' + a + '</code> <a href="' + D.bscscan(a) + '" target="_blank" rel="noopener noreferrer">BscScan</a></div>';
  }).join("");
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-copy-hash]");
    if (b) copy($(b.getAttribute("data-copy-hash")).textContent);
  });

  function randomSeed() {
    var b = new Uint8Array(32);
    crypto.getRandomValues(b);
    return b;
  }

  function parseSeed(text) {
    var s = String(text || "").trim();
    if (!s) return { seed: randomSeed(), src: "rand" };
    if (/^(0x)?[0-9a-fA-F]{64}$/.test(s)) return { seed: M.fromHex(s), src: "hex" };
    return { seed: M.keccak256(M.utf8(s)), src: "text", text: s };
  }

  function name(cat, i) {
    var en = M.NAMES[cat][i], z = M.NAMES_ZH[cat][i];
    return zh() ? z + " <small>" + esc(en) + "</small>" : esc(en);
  }

  function paintTraits() {
    if (!current) return;
    var t = current.t;
    var badge = $("tier-badge");
    badge.className = "ai-tier t" + t.tier;
    badge.textContent = zh() ? M.NAMES_ZH.tier[t.tier] + " · " + M.NAMES.tier[t.tier] : M.NAMES.tier[t.tier];
    $("tier-score").textContent = t.score;
    var rows = [
      ["ai.tHead", "head", t.head], ["ai.tEyes", "eyes", t.eyes], ["ai.tMouth", "mouth", t.mouth],
      ["ai.tNeck", "neck", t.neck], ["ai.tFur", "fur", t.picks[0]], ["ai.tCloth", "cloth", t.picks[1]],
      ["ai.tAcc", "acc", t.picks[2]], ["ai.tGlow", "glow", t.picks[3]], ["ai.tBg", "style", t.style],
      ["ai.tBgColor", "bgColor", t.color]
    ];
    $("trait-table").innerHTML = rows.map(function (r) {
      return "<tr><td>" + esc(T(r[0])) + "</td><td>" + name(r[1], r[2]) + "</td></tr>";
    }).join("");
    $("seed-out").textContent = "0x" + M.hex(current.seed);
    $("z-out").textContent = "[" + t.z.join(", ") + "]";
    $("gen-ms").textContent = F("ai.ms", { ms: current.ms.toFixed(1) });
    var p = current.parsed;
    $("seed-src").textContent = p.src === "text" ? F("ai.srcText", { text: p.text.length > 40 ? p.text.slice(0, 40) + "…" : p.text })
      : T(p.src === "hex" ? "ai.srcHex" : "ai.srcRand");
  }

  function generate(text) {
    return ready.then(function () {
      var parsed = parseSeed(text);
      var t0 = performance.now();
      var t = M.traits(W, TPL, parsed.seed);
      var svg = M.svgFor(t);
      var ms = performance.now() - t0;
      current = { seed: parsed.seed, parsed: parsed, t: t, svg: svg, ms: ms };
      $("chain-verdict").textContent = "";
      $("chain-verdict").className = "ai-verdict";
      $("dog-out").innerHTML = svg;
      paintTraits();
    }).catch(function () { $("seed-src").textContent = T("ai.loadFail"); });
  }

  $("seed-form").addEventListener("submit", function (e) { e.preventDefault(); generate($("seed-in").value); });
  $("seed-rand").addEventListener("click", function () {
    var s = "0x" + M.hex(randomSeed());
    $("seed-in").value = s;
    generate(s);
  });
  $("copy-seed").addEventListener("click", function () { if (current) copy("0x" + M.hex(current.seed)); });
  $("dl-svg").addEventListener("click", function () {
    if (!current) return;
    var url = URL.createObjectURL(new Blob([current.svg], { type: "image/svg+xml" }));
    var a = document.createElement("a");
    a.href = url;
    a.download = "haha-ai-" + M.hex(current.seed).slice(0, 12) + ".svg";
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  });

  function gallery() {
    ready.then(function () {
      var html = "";
      for (var i = 0; i < 12; i++) {
        var seed = randomSeed(), t = M.traits(W, TPL, seed), hx = "0x" + M.hex(seed);
        html += '<button type="button" data-seed="' + hx + '">' + M.svgFor(t)
          + '<span class="t' + t.tier + '">' + esc(zh() ? M.NAMES_ZH.tier[t.tier] : M.NAMES.tier[t.tier]) + " · " + t.score + "</span></button>";
      }
      $("gallery").innerHTML = html;
    });
  }
  $("more-btn").addEventListener("click", gallery);
  $("gallery").addEventListener("click", function (e) {
    var b = e.target.closest("[data-seed]");
    if (!b) return;
    $("seed-in").value = b.getAttribute("data-seed");
    generate(b.getAttribute("data-seed"));
    $("gen").scrollIntoView({ behavior: "smooth", block: "start" });
  });

  /* Latent morph: integer z codes interpolated between keyframe seeds. */
  function morph() {
    var cv = $("morph"), ctx = cv.getContext("2d"), img = ctx.createImageData(24, 24);
    var keys = [], STEPS = 14, HOLD = 10, frame = 0, timer = 0, visible = true;
    for (var i = 1; i <= 6; i++) keys.push(M.seedToZ(M.keccak256(M.utf8("Haha AI #" + i))));
    var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
    var per = STEPS + HOLD, total = per * keys.length;
    function zAt(f) {
      var k = Math.floor(f / per), s = f % per, a = keys[k], b = keys[(k + 1) % keys.length];
      if (s < HOLD) return a.slice();
      var u = (s - HOLD) / STEPS;
      return a.map(function (v, j) { return Math.round(v + (b[j] - v) * u); });
    }
    function draw() {
      var z = zAt(frame), r = M.forward(W, z), im = M.compose(r.cells, r.picks, 1, 2), p = 0;
      for (var y = 0; y < 24; y++) for (var x = 0; x < 24; x++) {
        var c = im[y][x];
        img.data[p++] = c[0]; img.data[p++] = c[1]; img.data[p++] = c[2]; img.data[p++] = 255;
      }
      ctx.putImageData(img, 0, 0);
      $("morph-z").textContent = "z = [" + z.join(", ") + "]";
    }
    function tick() {
      if (visible && !document.hidden) { draw(); frame = (frame + (reduce ? per : 1)) % total; }
      timer = setTimeout(tick, reduce ? 2000 : 90);
    }
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (en) { visible = en[0].isIntersecting; }).observe(cv);
    }
    tick();
  }

  /* On-chain check: HahaDogRenderer.svgOf(seed) at a high gas limit vs the in-browser model. */
  $("chain-btn").addEventListener("click", function () {
    if (!current) return;
    var btn = $("chain-btn"), v = $("chain-verdict"), mine = current;
    btn.disabled = true;
    v.className = "ai-verdict";
    v.textContent = T("ai.chainBusy");
    D.chainSvg("0x" + M.hex(mine.seed)).then(function (r) {
      var same = r.svg === mine.svg;
      v.className = "ai-verdict " + (same ? "ok" : "bad");
      v.textContent = F(same ? "ai.chainOk" : "ai.chainBad", { n: r.svg.length.toLocaleString("en-US"), host: r.host });
    }).catch(function () {
      v.className = "ai-verdict bad";
      v.textContent = T("ai.chainFail");
    }).then(function () { btn.disabled = false; });
  });

  /* On-chain model data hash: read modelData() and MODEL_DATA_HASH(), hash the bytes here. */
  $("data-btn").addEventListener("click", function () {
    var btn = $("data-btn"), v = $("data-verdict");
    btn.disabled = true;
    v.className = "ai-verdict";
    v.textContent = T("ai.dataBusy");
    D.modelDataCheck().then(function (r) {
      var ok = r.declared === PUB_DATA && r.computed === PUB_DATA;
      v.className = "ai-verdict " + (ok ? "ok" : "bad");
      v.textContent = F(ok ? "ai.dataOk" : "ai.dataBad", { n: r.size.toLocaleString("en-US"), host: r.host });
    }).catch(function () {
      v.className = "ai-verdict bad";
      v.textContent = T("ai.chainFail");
    }).then(function () { btn.disabled = false; });
  });

  /* Weights hash check. */
  function bytesHex(buf) { return "0x" + M.hex(new Uint8Array(buf)); }
  function checkBytes(nameStr, bytes) {
    $("hash-out").hidden = false;
    $("h-name").textContent = nameStr + " · " + bytes.length.toLocaleString() + " B";
    $("hash-verdict").className = "ai-verdict";
    $("hash-verdict").textContent = T("ai.hashBusy");
    setTimeout(function () {
      var k = "0x" + M.hex(M.keccak256(bytes));
      $("h-keccak").textContent = k;
      var kOk = k === PUB_KECCAK;
      $("h-keccak-ok").className = kOk ? "ok-mark" : "bad-mark";
      $("h-keccak-ok").textContent = T(kOk ? "ai.hashOk" : "ai.hashBad");
      var done = function (s) {
        var sOk = s === PUB_SHA;
        $("h-sha").textContent = s || T("ai.shaNA");
        $("h-sha-ok").className = s ? (sOk ? "ok-mark" : "bad-mark") : "";
        $("h-sha-ok").textContent = s ? T(sOk ? "ai.hashOk" : "ai.hashBad") : "";
        var all = kOk && (!s || sOk);
        $("hash-verdict").className = "ai-verdict " + (all ? "ok" : "bad");
        $("hash-verdict").textContent = T(all ? "ai.hashMatch" : "ai.hashMismatch");
      };
      if (window.crypto && crypto.subtle) crypto.subtle.digest("SHA-256", bytes).then(function (d) { done(bytesHex(d)); }, function () { done(""); });
      else done("");
    }, 20);
  }
  $("w-file").addEventListener("change", function () {
    var f = this.files && this.files[0];
    if (!f) return;
    f.arrayBuffer().then(function (b) { checkBytes(f.name, new Uint8Array(b)); }, function () {
      $("hash-out").hidden = false; $("hash-verdict").textContent = T("ai.hashFail");
    });
    this.value = "";
  });
  $("w-site").addEventListener("click", function () {
    fetch(BASE + "weights-int8.json", { cache: "no-store" }).then(function (r) { return r.arrayBuffer(); })
      .then(function (b) { checkBytes("haha.meme" + BASE + "weights-int8.json", new Uint8Array(b)); })
      .catch(function () { $("hash-out").hidden = false; $("hash-verdict").textContent = T("ai.hashFail"); });
  });

  /* Test vectors: recompute every vector here and compare with the reference SVG bytes. */
  var tvStarted = false;
  var STYLE_KEYS = ["scanlines", "sunburst", "stars", "moon", "glitch"];
  function runVectors() {
    if (tvStarted) return;
    tvStarted = true;
    $("tv-summary").textContent = T("ai.tvLoading");
    Promise.all([ready, getJSON("test-vectors.json")]).then(function (a) {
      var vec = a[1].vectors;
      return Promise.all(vec.map(function (v) {
        var id = ("0" + v.id).slice(-2);
        return fetch(BASE + "test-vectors/tv_" + id + ".svg", { cache: "force-cache" }).then(function (r) { return r.text(); })
          .then(function (ref) { return { v: v, id: id, ref: ref.trim() }; });
      }));
    }).then(function (rows) {
      var pass = 0, html = "";
      rows.forEach(function (row) {
        var v = row.v, r = M.forward(W, M.seedToZ(M.fromHex(v.seed)));
        var cells = r.cells.map(function (c) { return "0123456789A"[c]; }).join("");
        var layersOk = JSON.stringify(r.z) === JSON.stringify(v.z_q) && JSON.stringify(r.hidden) === JSON.stringify(v.hidden)
          && JSON.stringify(r.picks) === JSON.stringify(v.picks) && cells === v.cells_half_16x8;
        var svg = M.toSvg(M.compose(r.cells, r.picks, STYLE_KEYS.indexOf(v.background.style), v.background.color_index));
        var svgOk = svg === row.ref;
        if (layersOk && svgOk) pass++;
        var refUrl = BASE + "test-vectors/tv_" + row.id + ".svg";
        html += "<tr><td>" + v.id + "</td><td><code>" + esc(v.seed.slice(0, 10) + "…" + v.seed.slice(-6)) + "</code></td>"
          + '<td class="img">' + svg + '</td><td class="img"><img src="' + refUrl + '" alt="" width="52" height="52" loading="lazy"></td>'
          + '<td class="' + (layersOk ? "ok-mark" : "bad-mark") + '">' + esc(T(layersOk ? "ai.pass" : "ai.failMark")) + "</td>"
          + '<td class="' + (svgOk ? "ok-mark" : "bad-mark") + '">' + esc(T(svgOk ? "ai.pass" : "ai.failMark")) + " · " + svg.length + " B</td></tr>";
      });
      document.querySelector("#tv-table tbody").innerHTML = html;
      var all = pass === rows.length;
      $("tv-summary").className = "ai-verdict " + (all ? "ok" : "bad");
      $("tv-summary").textContent = F(all ? "ai.tvPass" : "ai.tvFail", { n: pass, t: rows.length });
      $("tv-summary").setAttribute("data-pass", pass + "/" + rows.length);
    }).catch(function () {
      $("tv-summary").className = "ai-verdict bad";
      $("tv-summary").textContent = T("ai.loadFail");
      tvStarted = false;
    });
  }
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (en) {
      if (en.some(function (x) { return x.isIntersecting; })) { io.disconnect(); runVectors(); }
    }, { rootMargin: "400px" });
    io.observe($("verify"));
  } else runVectors();

  if (window.HahaI18n) HahaI18n.onChange(function () {
    paintTraits();
    if (tvStarted && document.querySelector("#tv-table tbody").children.length) { tvStarted = false; runVectors(); }
    var gal = $("gallery").children.length;
    if (gal) gallery();
  });

  var q = null;
  try { q = new URLSearchParams(location.search).get("seed"); } catch (err) {}
  $("seed-in").value = q || "haha ai";
  ready.then(function () { morph(); gallery(); });
  generate($("seed-in").value);
})();
