/* Mint page: live count, quota lookup, my dogs (reroll cards), token viewer, gallery, copyable agent commands. */
(function () {
  "use strict";
  var D = window.HahaDog, M = window.HahaAIModel;
  var TOTAL = 10000;

  function $(id) { return document.getElementById(id); }
  function T(k) { return HahaI18n.t(k); }
  function F(k, v) { return T(k).replace(/\{(\w+)\}/g, function (_, n) { return v[n] == null ? "" : String(v[n]); }); }
  function zh() { return HahaI18n.lang() === "zh"; }
  function esc(s) { return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
  function toast(m) { if (window.HahaUI && HahaUI.toast) HahaUI.toast(m); }
  function copyTask(key, vars, doneKey) {
    return HahaUI.copyText(hahaInstruction(HahaI18n.task(key, vars))).then(function (ok) { if (ok !== false) toast(T(doneKey)); });
  }
  function tierName(t) { return zh() ? M.NAMES_ZH.tier[t] : M.NAMES.tier[t]; }
  function statusText(d) {
    if (!d || d.status === D.STATUS.none) return T("dog.stNone");
    if (d.status === D.STATUS.generating) return F("dog.stGenerating", { block: d.targetBlock });
    if (d.status === D.STATUS.stalled) return T("dog.stStalled");
    return T("dog.stReady");
  }
  function validId(v) { var s = String(v || "").trim(); return /^[1-9]\d{0,4}$/.test(s) && Number(s) <= TOTAL ? Number(s) : 0; }

  /* Contract table. */
  var NAMES = [["dogModel", "HahaDogModel"], ["dogRenderer", "HahaDogRenderer"], ["dog", "HahaDog"], ["dogMarket", "HahaDogMarket"]];
  $("dog-contracts").innerHTML = NAMES.map(function (n) {
    var a = D.ADDR[n[0]];
    return "<tr><td>" + n[1] + '</td><td><code>' + a + '</code> <a href="' + D.bscscan(a) + '" target="_blank" rel="noopener noreferrer">BscScan</a></td></tr>';
  }).join("");
  Array.prototype.forEach.call(document.querySelectorAll(".dog-addr"), function (el) { el.textContent = D.ADDR[el.getAttribute("data-addr")]; });

  /* Live count. */
  var supply = 0;
  function paintCount() {
    $("dog-count").textContent = supply.toLocaleString("en-US");
    $("dog-bar-fill").style.width = Math.min(100, supply / TOTAL * 100) + "%";
    $("dog-bar").setAttribute("aria-valuenow", String(supply));
    $("dog-left").textContent = F("dog.left", { n: (TOTAL - supply).toLocaleString("en-US") });
  }
  function refreshCount() {
    return D.totalSupply().then(function (n) {
      var grew = n !== supply;
      supply = n; paintCount();
      return grew;
    }).catch(function () { $("dog-left").textContent = T("dog.rpcFail"); return false; });
  }

  /* Quota lookup. */
  function sessionAddr() {
    var s = window.HahaSession && HahaSession.get();
    return s && s.address ? s.address : "";
  }
  function lookupQuota() {
    var a = $("quota-addr").value.trim(), out = $("quota-out");
    out.className = "ai-verdict";
    if (!D.isAddr(a)) { out.textContent = T("dog.quotaBadAddr"); return; }
    out.textContent = T("dog.loading");
    D.quotaOf(a).then(function (q) {
      if (!q.allowed) { out.className = "ai-verdict bad"; out.textContent = T("dog.quotaNoAi"); return; }
      var left = Math.max(0, q.allowed - q.used);
      out.className = "ai-verdict " + (left ? "ok" : "bad");
      out.textContent = F(left ? "dog.quotaOk" : "dog.quotaFull", { allowed: q.allowed, used: q.used, left: left });
    }).catch(function () { out.className = "ai-verdict bad"; out.textContent = T("dog.rpcFail"); });
  }
  $("quota-form").addEventListener("submit", function (e) { e.preventDefault(); lookupQuota(); });
  var lastMineAddr = null;
  function fillFromSession() {
    var a = sessionAddr();
    if (a && !$("quota-addr").value) { $("quota-addr").value = a; lookupQuota(); }
    if (a !== lastMineAddr) { lastMineAddr = a; mineList = null; loadMine(); }
  }
  window.hahaOnSession = fillFromSession;

  /* Copyable agent commands. */
  document.addEventListener("click", function (e) {
    var m = e.target.closest("[data-dog-mint]");
    if (m) { copyTask("dogMint", { qty: m.getAttribute("data-dog-mint") }, "dog.copiedMint"); return; }
  });

  /* My dogs as cards: the logged-in address, no number to type. 重铸 copies that dog's reroll instruction. */
  var mineSeq = 0, mineList = null;
  function emptyBox(titleKey, textKey, action) {
    return '<div class="dog-empty"><b>' + esc(T(titleKey)) + "</b><p>" + esc(T(textKey)) + "</p>" + (action ? '<div class="actions">' + action + "</div>" : "") + "</div>";
  }
  function loggedIn() { var s = window.HahaSession && HahaSession.get(); return !!(s && s.ai); }
  function mineCard(d, r) {
    var tier = r ? '<small class="t' + r.t.tier + '">' + esc(tierName(r.t.tier)) + " · " + r.t.score + "</small>" : "";
    var st = d.status === D.STATUS.ready ? T("dog.cardReady") : d.status === D.STATUS.stalled ? T("dog.cardStalled") : T("dog.cardGen");
    var rr = d.rerolls ? " · " + F("dog.cardRerolls", { n: d.rerolls }) : "";
    return '<article class="card dog-card" data-id="' + d.id + '">'
      + '<button type="button" class="dog-art dog-open" data-view="' + d.id + '" aria-label="' + esc(F("dog.cardView", { id: d.id })) + '">' + (r ? r.svg : placeholder(d)) + "</button>"
      + "<h3><span>#" + d.id + "</span>" + tier + "</h3>"
      + '<p class="seller">' + esc(st + rr) + "</p>"
      + '<div class="actions"><button class="btn" type="button" data-reroll="' + d.id + '" title="' + esc(F("dog.rerollBtnTip", { id: d.id })) + '">' + esc(T("dog.rerollBtn")) + "</button></div></article>";
  }
  function paintMine() {
    var el = $("mine-grid"), cnt = $("mine-count");
    cnt.textContent = "";
    $("mine-refresh").hidden = !loggedIn();
    if (!loggedIn()) { el.innerHTML = emptyBox("dog.mineLoginT", "dog.mineLoginP", '<button class="btn light" type="button" data-dog-login>' + esc(T("dog.loginBtn")) + "</button>"); return; }
    if (!sessionAddr()) { el.innerHTML = '<p class="note">' + esc(T("dog.mineNoAddr")) + "</p>"; return; }
    if (!mineList) { el.innerHTML = '<p class="note">' + esc(T("dog.loading")) + "</p>"; return; }
    if (mineList.error) { el.innerHTML = '<p class="note">' + esc(T("dog.rpcFail")) + "</p>"; return; }
    if (!mineList.items.length) { el.innerHTML = emptyBox("dog.mineNoneT", "dog.mineNoneP", '<a class="btn" href="#mint">' + esc(T("dog.mineGoMint")) + "</a>"); return; }
    cnt.textContent = F("dog.mineCount", { n: mineList.items.length });
    el.innerHTML = mineList.items.map(function (x) { return mineCard(x.d, x.r); }).join("");
  }
  function loadMine() {
    var my = ++mineSeq, a = sessionAddr();
    if (!loggedIn() || !a) { mineList = null; paintMine(); return Promise.resolve(); }
    if (!mineList) paintMine();
    return D.myDogs(a).then(function (res) {
      return Promise.all(res.dogs.map(function (d) { return d.seed ? D.render(d.seed) : null; })).then(function (rs) {
        if (my !== mineSeq) return;
        mineList = { items: res.dogs.map(function (d, i) { return { d: d, r: rs[i] }; }) };
        paintMine();
      });
    }).catch(function () { if (my !== mineSeq) return; mineList = { error: true }; paintMine(); });
  }
  $("mine-refresh").addEventListener("click", function () { mineList = null; loadMine(); });
  $("mine-grid").addEventListener("click", function (e) {
    var b = e.target.closest("[data-reroll]");
    if (b) { copyTask("dogReroll", { id: b.getAttribute("data-reroll") }, "dog.copiedReroll"); return; }
    if (e.target.closest("[data-dog-login]")) { var i = $("ai"); if (i) { i.scrollIntoView({ block: "center" }); i.focus(); } }
  });

  /* Viewer. */
  var cur = null, poll = 0, seq = 0;
  function showMsg(t) { var el = $("view-msg"); el.hidden = !t; el.textContent = t || ""; }
  function placeholder(d) {
    return HahaDogWait.html(!!(d && d.status === D.STATUS.stalled));
  }
  function traitRows(t) {
    var rows = [["ai.tHead", "head", t.head], ["ai.tEyes", "eyes", t.eyes], ["ai.tMouth", "mouth", t.mouth], ["ai.tNeck", "neck", t.neck],
      ["ai.tFur", "fur", t.picks[0]], ["ai.tCloth", "cloth", t.picks[1]], ["ai.tAcc", "acc", t.picks[2]], ["ai.tGlow", "glow", t.picks[3]],
      ["ai.tBg", "style", t.style], ["ai.tBgColor", "bgColor", t.color]];
    return rows.map(function (r) {
      var en = M.NAMES[r[1]][r[2]], z = M.NAMES_ZH[r[1]][r[2]];
      return "<tr><td>" + esc(T(r[0])) + "</td><td>" + (zh() ? esc(z) + " <small>" + esc(en) + "</small>" : esc(en)) + "</td></tr>";
    }).join("");
  }
  function paintView() {
    if (!cur) return;
    var d = cur.d, out = $("view-out");
    out.hidden = false;
    $("view-art").innerHTML = cur.r ? cur.r.svg : placeholder(d);
    $("view-dl").disabled = $("view-chain").disabled = !cur.r;
    var badge = $("view-tier");
    if (cur.r) {
      badge.className = "ai-tier t" + cur.r.t.tier;
      badge.textContent = zh() ? M.NAMES_ZH.tier[cur.r.t.tier] + " · " + M.NAMES.tier[cur.r.t.tier] : M.NAMES.tier[cur.r.t.tier];
      $("view-score").textContent = cur.r.t.score;
      $("view-table").innerHTML = traitRows(cur.r.t);
    } else {
      badge.className = "ai-tier"; badge.textContent = T("dog.generating"); $("view-score").textContent = "–"; $("view-table").innerHTML = "";
    }
    var rows = [
      [T("dog.vId"), "#" + d.id],
      [T("dog.vStatus"), esc(statusText(d))],
      [T("dog.vOwner"), cur.owner ? '<a href="https://bscscan.com/address/' + cur.owner + '" target="_blank" rel="noopener noreferrer">' + esc(D.short(cur.owner)) + "</a>" : "–"],
      [T("dog.vRerolls"), d.rerolls],
      [T("dog.vBlocks"), d.commitBlock + " → " + d.targetBlock],
      [T("dog.vSeed"), d.seed ? "<code>" + d.seed + "</code>" : "–"]
    ];
    $("view-table").innerHTML = rows.map(function (r) { return "<tr><td>" + esc(r[0]) + "</td><td>" + r[1] + "</td></tr>"; }).join("") + $("view-table").innerHTML;
    $("view-src").textContent = cur.r ? T("dog.srcLocal") : "";
    if (!cur.chainNote) $("view-verdict").textContent = "";
  }
  function loadView(id, quiet) {
    var my = ++seq;
    clearTimeout(poll);
    if (!quiet) { cur = null; $("view-out").hidden = true; showMsg(T("dog.loading")); }
    return Promise.all([D.dogsOf([id]), D.ownersOf([id])]).then(function (a) {
      if (my !== seq) return;
      var d = a[0][0], owner = a[1][0];
      if (!d || d.status === D.STATUS.none || !owner) { cur = null; $("view-out").hidden = true; showMsg(F("dog.notMinted", { id: id })); return; }
      showMsg("");
      var keep = cur && cur.d.id === id && cur.d.seed === d.seed && cur.r ? cur.r : null;
      if (!d.seed) {
        cur = { d: d, owner: owner, r: null }; paintView();
        if (d.status === D.STATUS.generating) poll = setTimeout(function () { loadView(id, true); }, 2500);
        return;
      }
      return (keep ? Promise.resolve(keep) : D.render(d.seed)).then(function (r) {
        if (my !== seq) return;
        cur = { d: d, owner: owner, r: r }; paintView();
      });
    }).catch(function () { if (my === seq) showMsg(T("dog.rpcFail")); });
  }
  $("view-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var id = validId($("view-id").value);
    if (!id) { toast(T("dog.needId")); return; }
    history.replaceState(null, "", "?id=" + id + "#view");
    loadView(id);
  });
  $("view-chain").addEventListener("click", function () {
    if (!cur || !cur.r) return;
    var v = $("view-verdict"), btn = $("view-chain"), id = cur.d.id, svg = cur.r.svg;
    btn.disabled = true; v.className = "ai-verdict"; v.textContent = T("dog.chainBusy"); cur.chainNote = true;
    D.chainToken(id).then(function (c) {
      var same = c.svg === svg;
      v.className = "ai-verdict " + (same ? "ok" : "bad");
      v.textContent = F(same ? "dog.chainOk" : "dog.chainBad", { n: c.svg.length.toLocaleString("en-US"), host: c.host, name: c.meta.name || "" });
    }).catch(function () { v.className = "ai-verdict bad"; v.textContent = T("dog.chainFail"); }).then(function () { btn.disabled = false; });
  });
  $("view-dl").addEventListener("click", function () {
    if (!cur || !cur.r) return;
    var url = URL.createObjectURL(new Blob([cur.r.svg], { type: "image/svg+xml" })), a = document.createElement("a");
    a.href = url; a.download = "haha-dog-" + cur.d.id + ".svg";
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  });

  /* Gallery of the newest dogs. */
  var shown = 0, PAGE = 12;
  function cardHtml(d, r) {
    var art = r ? r.svg : placeholder(d);
    var tag = r ? '<span class="t' + r.t.tier + '">' + esc(tierName(r.t.tier)) + " · " + r.t.score + "</span>" : "<span>" + esc(T("dog.generating")) + "</span>";
    return '<button type="button" data-view="' + d.id + '"><div class="dog-art">' + art + "</div><b>#" + d.id + "</b>" + tag + "</button>";
  }
  function loadGallery(reset) {
    if (reset) { shown = 0; $("dog-gallery").innerHTML = ""; }
    var from = supply - shown, ids = [];
    for (var i = 0; i < PAGE && from - i >= 1; i++) ids.push(from - i);
    if (!ids.length) { $("dog-more").hidden = true; if (!supply) $("dog-gallery").innerHTML = '<p class="muted">' + esc(T("dog.noneYet")) + "</p>"; return Promise.resolve(); }
    return D.dogsOf(ids).then(function (ds) {
      return Promise.all(ds.map(function (d) { return d && d.seed ? D.render(d.seed) : null; })).then(function (rs) {
        $("dog-gallery").insertAdjacentHTML("beforeend", ds.map(function (d, i) { return d ? cardHtml(d, rs[i]) : ""; }).join(""));
        shown += ids.length;
        $("dog-more").hidden = supply - shown < 1;
      });
    }).catch(function () { $("dog-gallery").insertAdjacentHTML("beforeend", '<p class="muted">' + esc(T("dog.rpcFail")) + "</p>"); });
  }
  $("dog-more").addEventListener("click", function () { loadGallery(false); });
  function openView(id) {
    $("view-id").value = id;
    history.replaceState(null, "", "?id=" + id + "#view");
    loadView(id);
    $("view").scrollIntoView({ behavior: "smooth", block: "start" });
  }
  [$("dog-gallery"), $("mine-grid")].forEach(function (box) {
    box.addEventListener("click", function (e) {
      var b = e.target.closest("[data-view]");
      if (b) openView(Number(b.getAttribute("data-view")));
    });
  });

  HahaI18n.onChange(function () { paintCount(); paintView(); loadGallery(true); lookupMaybe(); paintMine(); });
  function lookupMaybe() { if (D.isAddr($("quota-addr").value.trim())) lookupQuota(); }

  var q = null;
  try { q = new URLSearchParams(location.search).get("id"); } catch (err) {}
  if (validId(q)) { $("view-id").value = q; loadView(validId(q)); }
  refreshCount().then(function () { return loadGallery(true); });
  fillFromSession();
  setInterval(function () {
    if (document.hidden) return;
    refreshCount().then(function (grew) { if (grew) { loadGallery(true); if (sessionAddr()) loadMine(); } });
  }, 20000);
})();
