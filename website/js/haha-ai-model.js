/* Haha AI: integer inference, Haha Dog renderer and rarity, bit-exact with
 * haha-dog/model/infer_int.py and haha-dog/reference/hahadog_ref.py. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.HahaAIModel = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var RC = [
    [0x00000000, 0x00000001], [0x00000000, 0x00008082], [0x80000000, 0x0000808a], [0x80000000, 0x80008000],
    [0x00000000, 0x0000808b], [0x00000000, 0x80000001], [0x80000000, 0x80008081], [0x80000000, 0x00008009],
    [0x00000000, 0x0000008a], [0x00000000, 0x00000088], [0x00000000, 0x80008009], [0x00000000, 0x8000000a],
    [0x00000000, 0x8000808b], [0x80000000, 0x0000008b], [0x80000000, 0x00008089], [0x80000000, 0x00008003],
    [0x80000000, 0x00008002], [0x80000000, 0x00000080], [0x00000000, 0x0000800a], [0x80000000, 0x8000000a],
    [0x80000000, 0x80008081], [0x80000000, 0x00008080], [0x00000000, 0x80000001], [0x80000000, 0x80008008]
  ];
  var ROT = [0, 1, 62, 28, 27, 36, 44, 6, 55, 20, 3, 10, 43, 25, 39, 41, 45, 15, 21, 8, 18, 2, 61, 56, 14];

  function keccakF(lo, hi) {
    var cLo = new Int32Array(5), cHi = new Int32Array(5);
    var bLo = new Int32Array(25), bHi = new Int32Array(25);
    for (var round = 0; round < 24; round++) {
      var x, y, i;
      for (x = 0; x < 5; x++) {
        cLo[x] = lo[x] ^ lo[x + 5] ^ lo[x + 10] ^ lo[x + 15] ^ lo[x + 20];
        cHi[x] = hi[x] ^ hi[x + 5] ^ hi[x + 10] ^ hi[x + 15] ^ hi[x + 20];
      }
      for (x = 0; x < 5; x++) {
        var nLo = cLo[(x + 1) % 5], nHi = cHi[(x + 1) % 5];
        var dLo = cLo[(x + 4) % 5] ^ ((nLo << 1) | (nHi >>> 31));
        var dHi = cHi[(x + 4) % 5] ^ ((nHi << 1) | (nLo >>> 31));
        for (y = 0; y < 25; y += 5) { lo[x + y] ^= dLo; hi[x + y] ^= dHi; }
      }
      for (x = 0; x < 5; x++) {
        for (y = 0; y < 5; y++) {
          i = x + 5 * y;
          var r = ROT[i], l = lo[i], h = hi[i], rl, rh;
          if (r === 0) { rl = l; rh = h; }
          else if (r < 32) { rl = (l << r) | (h >>> (32 - r)); rh = (h << r) | (l >>> (32 - r)); }
          else if (r === 32) { rl = h; rh = l; }
          else { var m = r - 32; rl = (h << m) | (l >>> (32 - m)); rh = (l << m) | (h >>> (32 - m)); }
          var j = y + 5 * ((2 * x + 3 * y) % 5);
          bLo[j] = rl; bHi[j] = rh;
        }
      }
      for (y = 0; y < 25; y += 5) {
        for (x = 0; x < 5; x++) {
          lo[y + x] = bLo[y + x] ^ (~bLo[y + (x + 1) % 5] & bLo[y + (x + 2) % 5]);
          hi[y + x] = bHi[y + x] ^ (~bHi[y + (x + 1) % 5] & bHi[y + (x + 2) % 5]);
        }
      }
      lo[0] ^= RC[round][1]; hi[0] ^= RC[round][0];
    }
  }

  function keccak256(bytes) {
    var rate = 136, lo = new Int32Array(25), hi = new Int32Array(25);
    var n = bytes.length, full = Math.floor(n / rate) * rate, off, k;
    var block = new Uint8Array(rate);
    function absorb(buf, start) {
      for (var w = 0; w < 17; w++) {
        var p = start + w * 8;
        lo[w] ^= buf[p] | (buf[p + 1] << 8) | (buf[p + 2] << 16) | (buf[p + 3] << 24);
        hi[w] ^= buf[p + 4] | (buf[p + 5] << 8) | (buf[p + 6] << 16) | (buf[p + 7] << 24);
      }
      keccakF(lo, hi);
    }
    for (off = 0; off < full; off += rate) absorb(bytes, off);
    for (k = 0; k < n - full; k++) block[k] = bytes[full + k];
    block[n - full] ^= 0x01;
    block[rate - 1] ^= 0x80;
    absorb(block, 0);
    var out = new Uint8Array(32);
    for (k = 0; k < 4; k++) {
      out[8 * k] = lo[k] & 255; out[8 * k + 1] = (lo[k] >>> 8) & 255;
      out[8 * k + 2] = (lo[k] >>> 16) & 255; out[8 * k + 3] = (lo[k] >>> 24) & 255;
      out[8 * k + 4] = hi[k] & 255; out[8 * k + 5] = (hi[k] >>> 8) & 255;
      out[8 * k + 6] = (hi[k] >>> 16) & 255; out[8 * k + 7] = (hi[k] >>> 24) & 255;
    }
    return out;
  }

  function hex(bytes) {
    var s = "";
    for (var i = 0; i < bytes.length; i++) s += (bytes[i] < 16 ? "0" : "") + bytes[i].toString(16);
    return s;
  }

  function fromHex(s) {
    s = s.replace(/^0x/i, "");
    var out = new Uint8Array(s.length / 2);
    for (var i = 0; i < out.length; i++) out[i] = parseInt(s.substr(2 * i, 2), 16);
    return out;
  }

  function utf8(s) {
    if (typeof TextEncoder !== "undefined") return new TextEncoder().encode(s);
    return new Uint8Array(Buffer.from(s, "utf8"));
  }

  function seedToZ(seed) {
    var z = [];
    for (var i = 0; i < 8; i++) {
      var s = seed[4 * i] + seed[4 * i + 1] + seed[4 * i + 2] + seed[4 * i + 3] - 510;
      z.push(Math.floor((s * 7) / 32));
    }
    return z;
  }

  function forward(w, z) {
    var SH = w.SH, scale = Math.pow(2, SH), half = Math.pow(2, SH - 1);
    var h = z.slice(), hidden = [], i, j, k;
    for (var L = 0; L < w.layers.length; L++) {
      var layer = w.layers[L], nh = [];
      for (j = 0; j < layer.W.length; j++) {
        var acc = layer.b[j], row = layer.W[j];
        for (i = 0; i < h.length; i++) acc += row[i] * h[i];
        nh.push(acc <= 0 ? 0 : Math.min(127, Math.floor((acc * layer.M + half) / scale)));
      }
      h = nh;
      hidden.push(h);
    }
    var y = [];
    for (k = 0; k < w.W_out.length; k++) {
      var a = w.b_out[k], r = w.W_out[k];
      for (j = 0; j < h.length; j++) a += r[j] * h[j];
      y.push(a);
    }
    var cells = new Array(128).fill(0);
    Object.keys(w.const_cells).forEach(function (key) { cells[+key] = w.const_cells[key]; });
    for (var v = 0; v < w.var_cells.length; v++) {
      var ya = y[2 * v], yb = y[2 * v + 1], mask = w.var_masks[v], best = null, bc = 0;
      for (var c = 0; c < 11; c++) {
        if ((mask >> c) & 1) {
          var sc = 2 * (ya * w.P[c][0] + yb * w.P[c][1]) - w.C[c];
          if (best === null || sc > best) { best = sc; bc = c; }
        }
      }
      cells[w.var_cells[v]] = bc;
    }
    var picks = [], off = 2 * w.var_cells.length;
    w.groups.forEach(function (n) {
      var best2 = null, bi = 0;
      for (var q = 0; q < n; q++) if (best2 === null || y[off + q] > best2) { best2 = y[off + q]; bi = q; }
      picks.push(bi);
      off += n;
    });
    return { z: z.slice(), hidden: hidden, cells: cells, picks: picks };
  }

  var INK = [0x17, 0x13, 0x1c], WHITE = [0xfb, 0xf7, 0xee], PINK = [0xf0, 0x8d, 0xa0];
  var FUR = [[0xe3, 0x95, 0x4a], [0xc9, 0x60, 0x2d], [0x3b, 0x34, 0x43], [0xf1, 0xd9, 0xad], [0xa7, 0xb0, 0xbb], [0x7f, 0xe3, 0xe0], [0xf4, 0xb9, 0x28]];
  var MARK = [[0xfb, 0xec, 0xd2], [0xf8, 0xe3, 0xc6], [0xef, 0xd7, 0xb0], [0xff, 0xfa, 0xf0], [0xe1, 0xe6, 0xec], [0xd6, 0xfb, 0xf8], [0xff, 0xf0, 0xb3]];
  var CLOTH = [[0x2a, 0x27, 0x33], [0xe8, 0x42, 0x3f], [0x3f, 0x8e, 0xf0], [0xef, 0x68, 0xa8], [0x8d, 0x5c, 0xf0], [0x4c, 0xc3, 0x6b], [0xf2, 0xf0, 0xe8], [0xff, 0x9d, 0x2e]];
  var ACC = [[0xf2, 0xb6, 0x2b], [0xc3, 0xca, 0xd3], [0x36, 0x31, 0x3f], [0xff, 0x51, 0x48], [0x3f, 0xe0, 0xf0], [0xff, 0x7c, 0xba]];
  var GLOW = [[0xff, 0x3b, 0x3b], [0x3f, 0xe9, 0xff], [0x7d, 0xff, 0x6a], [0xff, 0x5c, 0xc8], [0xff, 0xd2, 0x3f]];
  var BG = [[0xff, 0x6f, 0x59], [0xff, 0x5d, 0x8f], [0xff, 0x9a, 0x3c], [0xff, 0xc9, 0x3c], [0x9b, 0xe1, 0x5d], [0xe8, 0x4a, 0x5f], [0xb1, 0x5d, 0xe5], [0xff, 0x8f, 0xab]];
  var NIGHT_BG = [1, 5, 6];
  var STAR = [255, 248, 220], GLITCH_A = [255, 242, 117], GLITCH_B = [255, 63, 164];
  var STYLE_CUM = [30, 55, 75, 90, 100];
  var STAR_SPOTS = [[2, 2, 1], [20, 3, 1], [5, 8, 0], [19, 9, 0], [12, 1, 0], [22, 13, 0], [1, 14, 0], [8, 4, 0], [15, 5, 0], [3, 19, 0], [21, 18, 0]];
  var MOON_STARS = [[3, 3], [8, 1], [12, 5], [1, 9], [22, 12], [6, 11]];
  var GLITCH_BARS = [[2, 0, 9, GLITCH_A], [3, 14, 24, GLITCH_B], [7, 3, 6, GLITCH_B], [8, 18, 24, GLITCH_A], [12, 0, 4, GLITCH_A], [13, 20, 24, GLITCH_B]];

  var NAMES = {
    fur: ["Classic Tan", "Red", "Black and Tan", "Cream", "Cyborg", "Hologram", "Gold"],
    cloth: ["Ink", "Red", "Blue", "Pink", "Purple", "Green", "White", "Orange"],
    acc: ["Gold", "Silver", "Black", "Red", "Cyan", "Pink"],
    glow: ["Red", "Cyan", "Lime", "Magenta", "Yellow"],
    bgColor: ["Coral", "Rose", "Tangerine", "Sunflower", "Lime", "Crimson", "Violet", "Blush"],
    style: ["Scanlines", "Sunburst", "Stars", "Moon", "Glitch", "Plain"],
    head: ["Beanie", "Cap", "Backwards Cap", "Headband", "Hood", "Headphones", "Tuft", "Spiky", "Mohawk", "Party Hat", "Propeller", "Crown", "Halo", "Third Eye"],
    eyes: ["Normal", "Shades", "Laser", "Visor", "Neon Specs", "Squint Smile", "Wide Stare", "Sleepy", "Angry", "Smug"],
    mouth: ["Smile", "Tongue", "Grin", "Laugh", "O Mouth", "Flat", "Bubblegum", "Bandana"],
    neck: ["None", "Gold Chain", "Spiked Collar", "Bell Collar", "Hoodie"],
    tier: ["Common", "Rare", "Epic", "Legendary"]
  };
  var NAMES_ZH = {
    fur: ["经典黄", "赤红", "黑褐", "奶油", "赛博银", "全息", "黄金"],
    cloth: ["墨黑", "红", "蓝", "粉", "紫", "绿", "白", "橙"],
    acc: ["金", "银", "黑", "红", "青", "粉"],
    glow: ["红", "青", "青柠", "品红", "黄"],
    bgColor: ["珊瑚", "玫瑰", "橘子", "向日葵", "青柠", "绯红", "紫罗兰", "樱粉"],
    style: ["扫描线", "放射光", "星空", "月夜", "故障", "纯色"],
    head: ["毛线帽", "棒球帽", "反戴帽", "头带", "兜帽", "耳机", "呆毛", "刺头", "莫西干", "派对帽", "竹蜻蜓帽", "王冠", "光环", "第三只眼"],
    eyes: ["普通", "墨镜", "激光眼", "护目镜", "霓虹眼镜", "眯眼笑", "瞪眼", "困倦", "生气", "得意"],
    mouth: ["微笑", "吐舌", "咧嘴", "大笑", "O 型嘴", "抿嘴", "泡泡糖", "面罩"],
    neck: ["无", "金链子", "铆钉项圈", "铃铛项圈", "卫衣"],
    tier: ["普通", "稀有", "史诗", "传说"]
  };
  var POINTS = {
    head: [7, 7, 7, 7, 7, 7, 8, 7, 7, 9, 9, 9, 9, 10],
    eyes: [3, 5, 8, 7, 8, 11, 9, 9, 6, 8],
    mouth: [1, 8, 20, 13, 20, 9, 15, 8],
    neck: [1, 5, 10, 9, 7],
    fur: [2, 6, 6, 7, 6, 8, 12],
    style: [3, 4, 5, 5, 7]
  };
  var TIER_MIN = [0, 30, 35, 40];
  var GROUP = [0, 1, 2, 2, 2, 5, 5, 7, 8, 9, 10];
  var CATEGORIES = ["head", "eyes", "mouth", "neck"];

  function shade(c) { return [Math.floor(c[0] * 3 / 4), Math.floor(c[1] * 3 / 4), Math.floor(c[2] * 3 / 4)]; }
  function mapc(c, f) { return [f(c[0]), f(c[1]), f(c[2])]; }

  function tones(c) {
    return {
      base: c.slice(),
      dark: mapc(c, function (v) { return Math.floor(v * 3 / 4); }),
      light: mapc(c, function (v) { return Math.floor((v * 3 + 255) / 4); }),
      night: mapc(c, function (v) { return Math.floor(v * 5 / 8); })
    };
  }

  function fill(c) {
    var im = [];
    for (var y = 0; y < 24; y++) { var row = []; for (var x = 0; x < 24; x++) row.push(c); im.push(row); }
    return im;
  }

  function scanlines(t) {
    var im = fill(t.base);
    for (var y = 1; y < 24; y += 2) for (var x = 0; x < 24; x++) im[y][x] = t.dark;
    return im;
  }

  function sunburst(t) {
    var im = fill(t.base);
    for (var y = 0; y < 24; y++) {
      for (var x = 0; x < 24; x++) {
        var dx = 2 * x + 1 - 23, dy = 2 * y + 1 - 27;
        var ax = Math.abs(dx), ay = Math.abs(dy);
        var big = Math.max(ax, ay), small = Math.min(ax, ay);
        var sub = small * 12 > big * 5 ? 1 : 0;
        var octant = (dx < 0 ? 4 : 0) + (dy < 0 ? 2 : 0) + (ax < ay ? 1 : 0);
        var xr = ((dx < 0) !== (dy < 0)) ? 1 : 0;
        if ((octant + sub + xr) % 2 === 1) im[y][x] = t.light;
      }
    }
    return im;
  }

  function stars(t) {
    var im = fill(t.night);
    STAR_SPOTS.forEach(function (s) {
      if (s[2]) {
        [[0, 0], [1, 0], [-1, 0], [0, 1], [0, -1]].forEach(function (d) {
          var px = s[0] + d[0], py = s[1] + d[1];
          if (py >= 0 && py < 24 && px >= 0 && px < 24) im[py][px] = STAR;
        });
      } else im[s[1]][s[0]] = STAR;
    });
    return im;
  }

  function moon(t) {
    var im = fill(t.night), r1 = Math.pow(3.6, 2), r2 = Math.pow(3.2, 2);
    for (var y = 0; y < 24; y++) {
      for (var x = 0; x < 24; x++) {
        var full = (x - 18.5) * (x - 18.5) + (y - 4.5) * (y - 4.5) < r1;
        var bite = (x - 20) * (x - 20) + (y - 3.5) * (y - 3.5) < r2;
        if (full && !bite) im[y][x] = STAR;
      }
    }
    MOON_STARS.forEach(function (s) { im[s[1]][s[0]] = STAR; });
    return im;
  }

  function glitch(t) {
    var im = scanlines(t);
    GLITCH_BARS.forEach(function (b) { for (var x = b[1]; x < b[2]; x++) im[b[0]][x] = b[3]; });
    return im;
  }

  var STYLES = [scanlines, sunburst, stars, moon, glitch];

  function backgroundImage(style, color) {
    if (style === 5) return fill(BG[color]);
    return STYLES[style](tones(BG[color]));
  }

  function classRgb(cls, p) {
    return [null, INK, FUR[p[0]], shade(FUR[p[0]]), MARK[p[0]], CLOTH[p[1]], shade(CLOTH[p[1]]), ACC[p[2]], GLOW[p[3]], WHITE, PINK][cls];
  }

  function compose(cells, picks, style, color) {
    var im = backgroundImage(style, color).map(function (r) { return r.slice(); });
    for (var i = 0; i < 18; i++) {
      var r = Math.min(i, 15), y = 6 + i;
      for (var c = 0; c < 16; c++) {
        var cls = cells[r * 8 + (c < 8 ? c : 15 - c)];
        if (cls) im[y][4 + c] = classRgb(cls, picks);
      }
    }
    return im;
  }

  function hx(c) {
    return "#" + c.map(function (v) { return (v < 16 ? "0" : "") + v.toString(16); }).join("");
  }

  function toSvg(im) {
    var parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" shape-rendering="crispEdges">'];
    for (var y = 0; y < 24; y++) {
      var x = 0;
      while (x < 24) {
        var col = im[y][x], x1 = x;
        while (x1 < 24 && im[y][x1][0] === col[0] && im[y][x1][1] === col[1] && im[y][x1][2] === col[2]) x1++;
        parts.push('<rect x="' + x + '" y="' + y + '" width="' + (x1 - x) + '" height="1" fill="' + hx(col) + '"/>');
        x = x1;
      }
    }
    return parts.join("") + "</svg>";
  }

  function backgroundOf(seed) {
    var r = BigInt("0x" + hex(keccak256(seed)));
    var roll = Number(r % 100n), style = 0;
    while (roll >= STYLE_CUM[style]) style++;
    var cr = r >> 128n;
    var color = (style === 2 || style === 3) ? NIGHT_BG[Number(cr % 3n)] : Number(cr % 8n);
    return { style: style, color: color };
  }

  function classify(templates, cells) {
    return CATEGORIES.map(function (cat) {
      var t = templates[cat], best = -1, bi = 0;
      t.table.forEach(function (row, i) {
        var s = 0;
        for (var k = 0; k < t.cells.length; k++) if (GROUP[cells[t.cells[k]]] === row[k]) s++;
        if (s > best) { best = s; bi = i; }
      });
      return bi;
    });
  }

  function rarity(head, eyes, mouth, neck, fur, style) {
    var score = POINTS.head[head] + POINTS.eyes[eyes] + POINTS.mouth[mouth] + POINTS.neck[neck] + POINTS.fur[fur] + POINTS.style[style];
    var tier = 0;
    TIER_MIN.forEach(function (m, i) { if (score >= m) tier = i; });
    if (fur === 6 && (head === 11 || head === 12)) tier = 3;
    else if ((eyes === 2 || eyes === 3) && style === 4 && tier < 2) tier = 2;
    return { score: score, tier: tier };
  }

  function traits(w, templates, seed) {
    var r = forward(w, seedToZ(seed));
    var bg = backgroundOf(seed);
    var cl = classify(templates, r.cells);
    var rr = rarity(cl[0], cl[1], cl[2], cl[3], r.picks[0], bg.style);
    return {
      cells: r.cells, picks: r.picks, hidden: r.hidden, z: r.z, style: bg.style, color: bg.color,
      head: cl[0], eyes: cl[1], mouth: cl[2], neck: cl[3], score: rr.score, tier: rr.tier
    };
  }

  function svgFor(t) { return toSvg(compose(t.cells, t.picks, t.style, t.color)); }

  return {
    keccak256: keccak256, hex: hex, fromHex: fromHex, utf8: utf8,
    seedToZ: seedToZ, forward: forward, backgroundOf: backgroundOf, backgroundImage: backgroundImage,
    classify: classify, rarity: rarity, traits: traits, compose: compose, toSvg: toSvg, svgFor: svgFor,
    NAMES: NAMES, NAMES_ZH: NAMES_ZH, POINTS: POINTS
  };
});
