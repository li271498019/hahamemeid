(function () {
  var canvas = document.getElementById("fx");
  if (!canvas) return;
  var ctx = canvas.getContext("2d", { alpha: true, desynchronized: true });
  if (!ctx) return;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var mobileQuery = window.matchMedia("(max-width: 800px)");
  var COINS = ["dog-shades","dog-party","dog-wink","cat-scream","cat-smug","frog","hamster","monkey","raccoon","goat","hippo","squirrel","bull","rocket","diamond-hands","moon","lol","haha-smiley"];
  /* Rain art is 64px. CSS size stays at or under 64/dpr so we never scale a bitmap up. */
  var SOURCE = 64;
  var images = [];
  var drops = [];
  var sparks = [];
  var smiley = new Image();
  smiley.decoding = "async";
  smiley.src = "/assets/coins/_smiley-64.webp";
  var pointer = null;
  var looping = false;
  for (var i = 0; i < 48; i++) sparks.push({ on: false });

  function dpr() { return Math.min(2, window.devicePixelRatio || 1); }
  function isMobile() { return mobileQuery.matches; }
  function coinCount() { return isMobile() ? 44 : 84; }
  function maxCss() { return SOURCE / dpr(); }
  function coinSize() {
    var cap = maxCss();
    var s = isMobile() ? 10 + Math.random() * 5 : 12 + Math.random() * 6;
    return s > cap ? cap : s;
  }
  function fallSpeed() { return isMobile() ? 0.22 + Math.random() * 0.28 : 0.28 + Math.random() * 0.38; }
  function snap(v) {
    var r = dpr();
    return Math.round(v * r) / r;
  }

  function resize() {
    var r = dpr();
    var w = Math.max(1, window.innerWidth);
    var h = Math.max(1, window.innerHeight);
    canvas.width = Math.round(w * r);
    canvas.height = Math.round(h * r);
    canvas.style.width = w + "px";
    canvas.style.height = h + "px";
    ctx.setTransform(r, 0, 0, r, 0, 0);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
  }

  function makeCoin() {
    return { img: null, x: 0, y: 0, vy: 1, size: 14, rot: 0, phase: 0, sway: 0.3, alpha: 0.7, caught: false, popping: false, popT: 0 };
  }

  function armCoin(p, index, n) {
    var w = Math.max(80, window.innerWidth);
    var h = Math.max(80, window.innerHeight);
    var cols = isMobile() ? 8 : 14;
    var rows = Math.ceil(n / cols);
    p.img = images[index % images.length];
    p.size = coinSize();
    p.x = (index % cols + 0.15 + Math.random() * 0.7) * (w / cols);
    p.y = (Math.floor(index / cols) + Math.random()) / rows * h;
    p.vy = fallSpeed();
    p.rot = (Math.random() - 0.5) * 0.15;
    p.phase = Math.random() * Math.PI * 2;
    p.sway = 0.15 + Math.random() * 0.35;
    p.alpha = 0.58 + Math.random() * 0.22;
    p.caught = false;
    p.popping = false;
    p.popT = 0;
  }

  function fill() {
    var n = coinCount();
    while (drops.length < n) drops.push(makeCoin());
    if (drops.length > n) drops.length = n;
    for (var i = 0; i < n; i++) armCoin(drops[i], i, n);
  }

  function recycle(p) {
    p.popping = false;
    p.popT = 0;
    p.caught = false;
    p.size = coinSize();
    p.y = -p.size - Math.random() * 40;
    p.x = Math.random() * Math.max(80, window.innerWidth);
    p.vy = fallSpeed();
    p.img = images[Math.floor(Math.random() * images.length)];
    p.alpha = 0.58 + Math.random() * 0.22;
    p.rot = (Math.random() - 0.5) * 0.15;
  }

  function hiddenByUi(target) {
    return target && target.closest && target.closest("a, button, input, textarea, select, label, summary, .card, .nav, .panel, footer, .sheet, .login, .filters");
  }

  function hit(p, x, y) {
    var dx = x - p.x;
    var dy = y - p.y;
    var r = p.size * 0.62 + 4;
    return dx * dx + dy * dy <= r * r;
  }

  function catchAt(x, y) {
    var hitIndex = -1;
    for (var i = drops.length - 1; i >= 0; i--) {
      if (drops[i].popping) continue;
      if (hit(drops[i], x, y)) { hitIndex = i; break; }
    }
    for (var j = 0; j < drops.length; j++) {
      if (!drops[j].popping) drops[j].caught = j === hitIndex;
    }
  }

  function emitBurst(x, y) {
    var kinds = ["dot", "plus", "smile", "dot", "smile", "plus"];
    for (var k = 0; k < kinds.length; k++) {
      var s = null;
      for (var i = 0; i < sparks.length; i++) if (!sparks[i].on) { s = sparks[i]; break; }
      if (!s) s = sparks[k % sparks.length];
      var ang = Math.random() * Math.PI * 2;
      var sp = 1.2 + Math.random() * 2.2;
      s.on = true;
      s.x = x; s.y = y;
      s.vx = Math.cos(ang) * sp;
      s.vy = Math.sin(ang) * sp - 1.2;
      s.life = 1;
      s.kind = kinds[k];
    }
  }

  function popAt(x, y) {
    for (var i = drops.length - 1; i >= 0; i--) {
      var p = drops[i];
      if (p.popping || !hit(p, x, y)) continue;
      p.caught = false;
      if (reduce) { recycle(p); return true; }
      p.popping = true;
      p.popT = 0;
      emitBurst(p.x, p.y);
      return true;
    }
    return false;
  }

  function drawCoin(p) {
    if (!p.img || !p.img.complete) return;
    var t = p.popping ? Math.min(1, p.popT) : 0;
    var bounce = p.popping ? 1 + Math.sin(t * Math.PI) * 0.85 : 1;
    var flip = p.popping ? Math.max(0.18, Math.abs(Math.cos(t * Math.PI * 2.2))) : 1;
    var s = snap(p.size * bounce);
    var lift = p.popping ? t * 36 : 0;
    var x = snap(p.x);
    var y = snap(p.y - lift);
    ctx.save();
    ctx.translate(x, y);
    if (p.popping) ctx.rotate(p.rot + t * 6);
    else if (p.rot) ctx.rotate(p.rot);
    ctx.scale(flip, 1);
    ctx.globalAlpha = p.popping ? 1 : (p.caught ? Math.min(1, p.alpha + 0.28) : p.alpha);
    ctx.drawImage(p.img, -s / 2, -s / 2, s, s);
    ctx.restore();
  }

  function drawSparks() {
    for (var i = 0; i < sparks.length; i++) {
      var s = sparks[i];
      if (!s.on) continue;
      ctx.save();
      ctx.globalAlpha = Math.max(0, s.life);
      if (s.kind === "plus") {
        ctx.fillStyle = "#fff";
        ctx.font = "700 13px ui-sans-serif, system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("+1", snap(s.x), snap(s.y));
      } else if (s.kind === "smile" && smiley.complete && smiley.naturalWidth) {
        var d = snap(12);
        ctx.drawImage(smiley, snap(s.x) - d / 2, snap(s.y) - d / 2, d, d);
      } else {
        ctx.fillStyle = "#ffe27a";
        ctx.beginPath();
        ctx.arc(snap(s.x), snap(s.y), 2, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();
    }
  }

  function paint() {
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
    for (var i = 0; i < drops.length; i++) if (!drops[i].caught && !drops[i].popping) drawCoin(drops[i]);
    for (var j = 0; j < drops.length; j++) if (drops[j].caught || drops[j].popping) drawCoin(drops[j]);
    drawSparks();
  }

  function step() {
    if (!reduce) {
      var w = window.innerWidth;
      var h = window.innerHeight;
      if (pointer) catchAt(pointer.x, pointer.y);
      for (var i = 0; i < drops.length; i++) {
        var p = drops[i];
        if (p.popping) {
          p.popT += 0.045;
          if (p.popT >= 1) recycle(p);
          continue;
        }
        if (p.caught) continue;
        p.phase += 0.02;
        p.y += p.vy;
        p.x += Math.sin(p.phase) * p.sway;
        if (p.y > h + p.size) recycle(p);
        else if (p.x < -p.size) p.x = w + p.size;
        else if (p.x > w + p.size) p.x = -p.size;
      }
      for (var s = 0; s < sparks.length; s++) {
        var sp = sparks[s];
        if (!sp.on) continue;
        sp.x += sp.vx;
        sp.y += sp.vy;
        sp.vy += 0.045;
        sp.life -= 0.02;
        if (sp.life <= 0) sp.on = false;
      }
    }
    paint();
  }

  function loop() {
    if (document.hidden) { looping = false; return; }
    looping = true;
    step();
    if (!reduce) requestAnimationFrame(loop);
    else looping = false;
  }

  window.addEventListener("pointermove", function (e) {
    if (e.pointerType && e.pointerType !== "mouse") return;
    if (hiddenByUi(e.target)) pointer = null;
    else pointer = { x: e.clientX, y: e.clientY };
    if (reduce) {
      if (pointer) catchAt(pointer.x, pointer.y);
      else for (var i = 0; i < drops.length; i++) drops[i].caught = false;
      paint();
    }
  });
  window.addEventListener("pointerdown", function (e) {
    if (hiddenByUi(e.target)) return;
    if (popAt(e.clientX, e.clientY) && reduce) paint();
  });
  window.addEventListener("pointerleave", function () {
    pointer = null;
    for (var i = 0; i < drops.length; i++) if (!drops[i].popping) drops[i].caught = false;
    if (reduce) paint();
  });
  window.addEventListener("resize", function () { resize(); fill(); if (reduce || document.hidden) paint(); });
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden && !looping && !reduce && images.length) loop();
  });

  function boot() {
    resize();
    var pending = COINS.length;
    function done() {
      pending--;
      if (pending > 0) return;
      if (!images.length) return;
      fill();
      if (reduce) paint();
      else loop();
    }
    COINS.forEach(function (name) {
      var img = new Image();
      img.decoding = "async";
      img.onload = function () { images.push(img); done(); };
      img.onerror = done;
      img.src = "/assets/coins/" + name + ".webp";
    });
  }

  function start() {
    if ("requestIdleCallback" in window) requestIdleCallback(boot, { timeout: 1500 });
    else window.addEventListener("load", boot);
  }
  if (document.readyState === "complete") start();
  else window.addEventListener("load", start);
})();
