(function () {
  var canvas = document.getElementById("fx");
  if (!canvas) return;
  var ctx = canvas.getContext("2d");
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var mobileQuery = window.matchMedia("(max-width: 800px)");
  var COINS = ["dog-shades","dog-party","dog-wink","cat-scream","cat-smug","frog","hamster","monkey","raccoon","goat","hippo","squirrel","bull","rocket","diamond-hands","moon","lol","haha-smiley"];
  var images = [];
  var drops = [];
  var sparks = [];
  var smiley = new Image();
  smiley.src = "/assets/coins/_smiley-coin.svg";
  for (var i = 0; i < 96; i++) sparks.push({ on: false });

  function isMobile() { return mobileQuery.matches; }
  function coinCount() { return isMobile() ? 62 : 156; }
  function fallSpeed() { return isMobile() ? 0.85 + Math.random() * 1.35 : 1.25 + Math.random() * 2.15; }
  function coinSize() { return isMobile() ? 18 + Math.random() * 14 : 22 + Math.random() * 24; }

  function resize() {
    var dpr = Math.min(2, window.devicePixelRatio || 1);
    canvas.width = Math.floor(window.innerWidth * dpr);
    canvas.height = Math.floor(window.innerHeight * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function makeCoin() {
    return { img: null, x: 0, y: 0, vy: 1, size: 24, rot: 0, vr: 0, phase: 0, sway: 0.4, alpha: 0.5, caught: false, popping: false, popT: 0 };
  }

  function armCoin(p, index, n) {
    var w = Math.max(80, window.innerWidth);
    var h = Math.max(80, window.innerHeight);
    var cols = isMobile() ? 8 : 12;
    var rows = Math.ceil(n / cols);
    p.img = images[index % images.length];
    p.size = coinSize();
    p.x = (index % cols + 0.12 + Math.random() * 0.76) * (w / cols);
    p.y = (Math.floor(index / cols) + Math.random()) / rows * h;
    p.vy = fallSpeed();
    p.rot = Math.random() * Math.PI * 2;
    p.vr = (Math.random() - 0.5) * 0.03;
    p.phase = Math.random() * Math.PI * 2;
    p.sway = 0.22 + Math.random() * 0.55;
    p.alpha = 0.45 + Math.random() * 0.1;
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
    p.y = -p.size - Math.random() * 50;
    p.x = Math.random() * Math.max(80, window.innerWidth);
    p.vy = fallSpeed();
    p.img = images[Math.floor(Math.random() * images.length)];
    p.alpha = 0.45 + Math.random() * 0.1;
    p.rot = Math.random() * Math.PI * 2;
  }

  function hiddenByUi(target) {
    return target && target.closest && target.closest(".card, .nav, .step, .panel, footer, .sheet");
  }

  function hit(p, x, y) {
    var dx = x - p.x;
    var dy = y - p.y;
    var r = p.size * (p.caught ? 0.8 : 0.62) + 6;
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
    var kinds = ["dot", "plus", "smile", "dot", "smile", "plus", "dot"];
    for (var k = 0; k < kinds.length; k++) {
      var s = null;
      for (var i = 0; i < sparks.length; i++) if (!sparks[i].on) { s = sparks[i]; break; }
      if (!s) s = sparks[k];
      var ang = Math.random() * Math.PI * 2;
      var sp = 1.4 + Math.random() * 2.6;
      s.on = true;
      s.x = x; s.y = y;
      s.vx = Math.cos(ang) * sp;
      s.vy = Math.sin(ang) * sp - 1.4;
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
    if (!p.img) return;
    var t = p.popping ? Math.min(1, p.popT) : 0;
    var bounce = p.popping ? 1 + Math.sin(t * Math.PI) * 1.05 : 1;
    var flip = p.popping ? Math.max(0.12, Math.abs(Math.cos(t * Math.PI * 2.5))) : 1;
    var s = p.size * bounce;
    ctx.save();
    ctx.translate(p.x, p.y - (p.popping ? t * 42 : 0));
    ctx.rotate(p.rot + (p.popping ? t * 7 : 0));
    ctx.scale(flip, 1);
    ctx.globalAlpha = p.popping ? 1 : p.alpha;
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
        ctx.font = "800 15px 'Fusion Pixel', ui-monospace, monospace";
        ctx.textAlign = "center";
        ctx.fillText("+1", s.x, s.y);
      } else if (s.kind === "smile" && smiley.complete && smiley.naturalWidth) {
        var d = 14;
        ctx.drawImage(smiley, s.x - d / 2, s.y - d / 2, d, d);
      } else {
        ctx.fillStyle = "#ffe27a";
        ctx.beginPath();
        ctx.arc(s.x, s.y, 2.5, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();
    }
  }

  function paint() {
    ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
    for (var i = 0; i < drops.length; i++) if (!drops[i].caught && !drops[i].popping) drawCoin(drops[i]);
    for (var j = 0; j < drops.length; j++) if (drops[j].caught || drops[j].popping) drawCoin(drops[j]);
    drawSparks();
  }

  function step() {
    if (!reduce) {
      var w = window.innerWidth;
      var h = window.innerHeight;
      for (var i = 0; i < drops.length; i++) {
        var p = drops[i];
        if (p.popping) {
          p.popT += 0.02;
          if (p.popT >= 1) recycle(p);
          continue;
        }
        if (p.caught) continue;
        p.phase += 0.025;
        p.y += p.vy;
        p.x += Math.sin(p.phase) * p.sway;
        p.rot += p.vr;
        if (p.y > h + p.size) recycle(p);
        else if (p.x < -p.size) p.x = w + p.size;
        else if (p.x > w + p.size) p.x = -p.size;
      }
      for (var s = 0; s < sparks.length; s++) {
        var sp = sparks[s];
        if (!sp.on) continue;
        sp.x += sp.vx;
        sp.y += sp.vy;
        sp.vy += 0.05;
        sp.life -= 0.018;
        if (sp.life <= 0) sp.on = false;
      }
    }
    paint();
  }

  function loop() {
    step();
    if (!reduce) requestAnimationFrame(loop);
  }

  window.addEventListener("pointermove", function (e) {
    if (e.pointerType && e.pointerType !== "mouse") return;
    if (hiddenByUi(e.target)) {
      for (var i = 0; i < drops.length; i++) if (!drops[i].popping) drops[i].caught = false;
    } else catchAt(e.clientX, e.clientY);
    if (reduce) paint();
  });
  window.addEventListener("pointerdown", function (e) {
    if (hiddenByUi(e.target)) return;
    if (popAt(e.clientX, e.clientY) && reduce) paint();
  });
  window.addEventListener("pointerleave", function () {
    for (var i = 0; i < drops.length; i++) if (!drops[i].popping) drops[i].caught = false;
    if (reduce) paint();
  });
  window.addEventListener("resize", function () { resize(); fill(); if (reduce) paint(); });

  function boot() {
    resize();
    Promise.all(COINS.map(function (name) {
      return new Promise(function (resolve) {
        var img = new Image();
        img.onload = function () { images.push(img); resolve(); };
        img.onerror = function () { resolve(); };
        img.src = "/assets/coins/" + name + ".webp";
      });
    })).then(function () {
      if (!images.length) return;
      fill();
      loop();
    });
  }
  boot();
})();
