/* Market page, Haha Dog tab: listings from the indexer (chain as fallback), my dogs, agent commands for list/buy/cancel. */
(function () {
  "use strict";
  var D = window.HahaDog, M = window.HahaAIModel;
  var TOTAL_CAP = 10000;

  function $(id) { return document.getElementById(id); }
  function T(k) { return HahaI18n.t(k); }
  function F(k, v) { return T(k).replace(/\{(\w+)\}/g, function (_, n) { return v[n] == null ? "" : String(v[n]); }); }
  function zh() { return HahaI18n.lang() === "zh"; }
  function esc(s) { return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
  function toast(m) { if (window.HahaUI && HahaUI.toast) HahaUI.toast(m); }
  function copyTask(key, vars, doneKey) {
    return HahaUI.copyText(hahaInstruction(HahaI18n.task(key, vars))).then(function (ok) { if (ok !== false) toast(T(doneKey)); });
  }
  /* Same price limits as the haha id market: up to 10000 BNB, at most 18 decimals. */
  function priceOk(v) {
    if (!/^\d*\.?\d+$/.test(v)) return false;
    var parts = String(v).split(".");
    if (parts[1] && parts[1].length > 18) return false;
    var n = parseFloat(v);
    return n > 0 && n <= 10000;
  }
  function validId(v) { var s = String(v || "").trim(); return /^[1-9]\d{0,4}$/.test(s) && Number(s) <= TOTAL_CAP ? Number(s) : 0; }

  /* Tabs. */
  var dogStarted = false;
  function selectTab(which, keepHash) {
    var dog = which === "dog";
    $("mk-names").hidden = dog; $("mk-dog").hidden = !dog;
    $("tab-names").setAttribute("aria-selected", String(!dog)); $("tab-dog").setAttribute("aria-selected", String(dog));
    if (!keepHash) {
      try { history.replaceState(null, "", dog ? "#dog" : location.pathname + location.search); } catch (err) {}
    }
    if (dog && !dogStarted) { dogStarted = true; startDog(); }
  }
  $("tab-names").addEventListener("click", function () { selectTab("names"); });
  $("tab-dog").addEventListener("click", function () { selectTab("dog"); });
  if (location.hash === "#dog") selectTab("dog", true);

  /* Contracts table. */
  $("dog-contracts").innerHTML = [["HahaDog", "dog"], ["HahaDogMarket", "dogMarket"], ["HahaDogRenderer", "dogRenderer"], ["HahaDogModel", "dogModel"]].map(function (n) {
    var a = D.ADDR[n[1]];
    return "<tr><td>" + n[0] + "</td><td><code>" + a + '</code> <a href="' + D.bscscan(a) + '" target="_blank" rel="noopener noreferrer">BscScan</a></td></tr>';
  }).join("");
  Array.prototype.forEach.call(document.querySelectorAll(".dog-addr"), function (el) { el.textContent = D.ADDR[el.getAttribute("data-addr")]; });

  /* Card. mode: buy | mine. */
  function artHtml(d, r) {
    if (r) return r.svg;
    return HahaDogWait.html(!!(d && d.status === D.STATUS.stalled));
  }
  function link(id) { return '<a href="/mint.html?id=' + id + '#view">'; }
  function card(it, mode) {
    var d = it.d, r = it.r, l = it.listing, html = '<article class="card dog-card' + (l && it.valid === false ? " invalid" : "") + '">';
    html += link(d.id) + '<div class="dog-art">' + artHtml(d, r) + "</div></a>";
    html += "<h3>" + link(d.id) + "#" + d.id + "</a>" + (r ? '<small class="t' + r.t.tier + '">' + esc(zh() ? M.NAMES_ZH.tier[r.t.tier] : M.NAMES.tier[r.t.tier]) + " · " + r.t.score + "</small>" : "") + "</h3>";
    if (l) html += '<p class="price">' + esc(D.weiToBnb(l.priceWei)) + " BNB</p>";
    else html += '<p class="price">' + esc(T("dog.mkNotListed")) + "</p>";
    if (l && mode === "buy") html += '<p class="seller">' + esc(T("dog.mkSeller")) + ' <a href="https://bscscan.com/address/' + l.seller + '" target="_blank" rel="noopener noreferrer">' + esc(D.short(l.seller)) + "</a></p>";
    if (l && it.valid === false) html += '<p class="bad-mark" title="' + esc(T("dog.mkInvalidWhy")) + '">' + esc(T("dog.mkInvalid")) + "</p>";
    if (mode === "mine" && ((!l && d.status === D.STATUS.ready) || (l && it.valid !== false))) {
      html += '<input class="price-input" type="text" inputmode="decimal" placeholder="' + esc(T("dog.mkPricePh")) + '" aria-label="' + esc(T("dog.mkPriceAria")) + '">';
    }
    html += '<div class="actions">';
    var me = (mode === "mine" && mineAddr) ? mineAddr.toLowerCase() : "";
    if (mode === "buy" && l && it.valid !== false) html += '<button class="btn" type="button" data-dbuy="' + d.id + '" data-price="' + esc(D.weiToBnb(l.priceWei)) + '">' + esc(T("dog.mkBuy")) + "</button>";
    if (mode === "mine") {
      if (!l && d.status === D.STATUS.ready) html += '<button class="btn" type="button" data-dlist="' + d.id + '">' + esc(T("dog.mkList")) + "</button>";
      if (!l && d.status !== D.STATUS.ready) html += '<span class="muted">' + esc(T("dog.mkReadyOnly")) + "</span>";
      if (l && it.valid !== false) html += '<button class="btn light" type="button" data-dreprice="' + d.id + '">' + esc(T("dog.mkReprice")) + "</button>";
      if (l && l.seller.toLowerCase() === me) html += '<button class="btn light" type="button" data-dcancel="' + d.id + '">' + esc(T("dog.mkCancel")) + "</button>";
    }
    /* Anyone may clear a stale listing; the sale button is already hidden for it. */
    if (l && it.stale) html += '<button class="btn light" type="button" data-dclear="' + d.id + '">' + esc(T("dog.mkClear")) + "</button>";
    return html + "</div></article>";
  }

  /* Build card items for ids: dog state, in-browser render, listing, validity, stale flag.
   * stale = what HahaDogMarket.clearStale accepts: the holder is no longer the seller, or the dog was rerolled. */
  function items(ids) {
    return Promise.all([D.dogsOf(ids), D.listingsOf(ids), D.ownersOf(ids)]).then(function (a) {
      var ds = a[0], ls = a[1], owners = a[2], listed = ids.filter(function (_, i) { return ls[i]; });
      return D.validOf(listed).then(function (vs) {
        var vmap = {};
        listed.forEach(function (id, i) { vmap[id] = vs[i]; });
        return Promise.all(ds.map(function (d, i) {
          var l = ls[i], r = d && d.seed ? D.render(d.seed) : Promise.resolve(null);
          var stale = !!(l && d && ((owners[i] || "").toLowerCase() !== l.seller.toLowerCase() || d.rerolls !== l.rerolls));
          return r.then(function (rr) { return { d: d, r: rr, listing: l, valid: l ? vmap[ids[i]] : null, stale: stale, owner: owners[i], id: ids[i] }; });
        }));
      });
    });
  }

  /* Listings: enumerate 1..totalSupply through the market's listings(tokenId). */
  var listItems = [];
  function sortItems(arr) {
    var mode = $("dog-sort").value, a = arr.slice();
    a.sort(function (x, y) {
      if (mode === "id") return x.id - y.id;
      var px = x.listing.priceWei, py = y.listing.priceWei;
      var c = px < py ? -1 : px > py ? 1 : x.id - y.id;
      return mode === "high" ? -c : c;
    });
    return a;
  }
  function paintListings() {
    var el = $("dog-grid");
    if (!listItems.length) { el.innerHTML = '<p class="note">' + esc(T("dog.mkNoListings")) + "</p>"; return; }
    el.innerHTML = sortItems(listItems).map(function (it) { return card(it, "buy"); }).join("")
      + (listTruncated ? '<p class="note">' + esc(T("dog.mkTruncated")) + "</p>" : "");
  }
  /* Indexer pages (50 at a time, at most 6 pages), then the same card items as the chain path. */
  var LIST_MAX_PAGES = 6, listTruncated = false;
  function listingsFromIndex() {
    var all = [], pages = 0;
    function more(cursor) {
      return D.idx("/v1/dog/listings?limit=50&sort=price_asc" + (cursor ? "&cursor=" + encodeURIComponent(cursor) : "")).then(function (j) {
        all = all.concat(j.items || []);
        if (j.nextCursor && ++pages < LIST_MAX_PAGES) return more(j.nextCursor);
        listTruncated = !!j.nextCursor;
      });
    }
    return more(null).then(function () {
      var rows = all.filter(function (x) { return !x.stale; });
      var ids = rows.map(function (x) { return Number(x.tokenId); });
      return Promise.all([D.completeFromChain(rows.map(D.fromIdx)), D.validOf(ids)]).then(function (a) {
        return Promise.all(a[0].map(function (d, i) {
          var x = rows[i], r = d.seed ? D.render(d.seed) : Promise.resolve(null);
          var listing = { seller: x.seller, priceWei: BigInt(x.priceWei), rerolls: x.rerolls };
          return r.then(function (rr) { return { d: d, r: rr, listing: listing, valid: a[1][i], stale: false, owner: x.owner, id: d.id }; });
        }));
      });
    });
  }
  function listingsFromChain() {
    return D.totalSupply().then(function (n) {
      var ids = [];
      for (var i = 1; i <= n; i++) ids.push(i);
      return D.listingsOf(ids).then(function (ls) {
        var listedIds = ids.filter(function (_, i) { return ls[i]; });
        return items(listedIds);
      });
    });
  }
  var listingsDone = null, listingsViaIndex = false;
  function loadListings() {
    var el = $("dog-grid");
    el.innerHTML = '<p class="note">' + esc(T("dog.mkLoading")) + "</p>";
    listTruncated = false;
    var p = listingsFromIndex().then(function (arr) { listingsViaIndex = true; $("dog-src").textContent = T("dog.mkIndexer"); return arr; }, function () {
      listTruncated = false; listingsViaIndex = false;
      return listingsFromChain().then(function (arr) { $("dog-src").textContent = T("dog.mkChainSrc"); return arr; });
    });
    listingsDone = p.then(function (arr) { listItems = arr; paintListings(); return arr; })
      .catch(function () { el.innerHTML = '<p class="note">' + esc(T("dog.rpcFail")) + "</p>"; return null; });
    return listingsDone;
  }
  $("dog-sort").addEventListener("change", paintListings);

  /* Top stats bar, same five cells as the haha id tab: fee, floor, latest sale, listings, 24h volume.
   * Indexer first; if it is down, floor and count come from the listings read off the chain and the sales from Sold logs. */
  var dogStats = null;
  function statHtml(value, labelKey) { return '<div class="stat"><b>' + esc(value) + "</b><span>" + esc(T(labelKey)) + "</span></div>"; }
  function paintDogStats() {
    var m = dogStats, bnb = function (w) { return D.weiToBnb(w) + " BNB"; };
    var ph = m ? null : "…";
    $("dog-stats").innerHTML = '<div class="stat"><b>' + esc(T("common.fee")) + "</b><span>" + esc(T("common.feeNote")) + "</span></div>"
      + statHtml(ph || (m.floor != null ? bnb(m.floor) : "—"), "market.floorPrice")
      + statHtml(ph || (m.latest != null ? bnb(m.latest) : "—"), "market.latestPrice")
      + statHtml(ph || (m.count != null ? String(m.count) : "—"), "market.listingCount")
      + statHtml(ph || (m.vol != null ? bnb(m.vol) : "—"), "market.volume24h");
  }
  function loadDogStats() {
    paintDogStats();
    return D.idx("/v1/dog/stats").then(function (j) {
      var k = j.market || {};
      dogStats = { floor: k.floorPriceWei, latest: k.latestTradePriceWei, count: k.listings, vol: k.volume24hWei || "0" };
      paintDogStats();
    }).catch(function () {
      return (listingsDone || Promise.resolve()).then(function () {
        var live = listItems.filter(function (it) { return it.valid !== false; }), floor = null;
        live.forEach(function (it) { if (floor === null || it.listing.priceWei < floor) floor = it.listing.priceWei; });
        dogStats = { floor: floor, latest: null, count: live.length, vol: null };
        paintDogStats();
        return D.recentSales(20).then(function (r) {
          var cut = r.head - r.day, vol = 0n;
          r.sales.forEach(function (x) { if (x.block >= cut) vol += x.price; });
          dogStats.latest = r.sales.length ? r.sales[0].price : null;
          dogStats.vol = r.complete24h ? vol : null;
          paintDogStats();
        }).catch(function () {});
      });
    });
  }

  /* Search by number. */
  var hitSeq = 0;
  function searchHit() {
    var id = validId($("dog-find").value), el = $("dog-hit"), my = ++hitSeq;
    if (!id) { el.innerHTML = ""; if ($("dog-find").value.trim()) toast(T("dog.needId")); return; }
    el.innerHTML = '<p class="note">' + esc(T("dog.mkLoading")) + "</p>";
    items([id]).then(function (a) {
      if (my !== hitSeq) return;
      var it = a[0];
      if (!it.d || it.d.status === D.STATUS.none) { el.innerHTML = '<p class="note">' + esc(F("dog.notMinted", { id: id })) + "</p>"; return; }
      if (!it.listing) { el.innerHTML = '<p class="note">' + esc(F("dog.mkNotForSale", { id: id })) + "</p>"; return; }
      el.innerHTML = '<div class="grid dog-grid">' + card(it, "buy") + "</div>";
    }).catch(function () { if (my === hitSeq) el.innerHTML = '<p class="note">' + esc(T("dog.rpcFail")) + "</p>"; });
  }
  $("dog-find-form").addEventListener("submit", function (e) { e.preventDefault(); searchHit(); });

  /* My dogs: the logged-in address, same as the mint page. No address box. */
  var mineAddr = "", mineSeq = 0;
  function sessionAddr() { var s = window.HahaSession && HahaSession.get(); return s && s.address ? s.address : ""; }
  function emptyBox(titleKey, textKey, action) {
    return '<div class="dog-empty"><b>' + esc(T(titleKey)) + "</b><p>" + esc(T(textKey)) + "</p>"
      + (action ? '<div class="actions">' + action + "</div>" : "") + "</div>";
  }
  function loadMine() {
    var a = sessionAddr(), el = $("dog-mine"), my = ++mineSeq;
    $("dog-withdraw-row").hidden = true;
    mineAddr = a;
    var sess = window.HahaSession && HahaSession.get();
    if (!sess || !sess.ai) { el.innerHTML = emptyBox("dog.mineLoginT", "dog.mineLoginP", '<button class="btn light" type="button" data-dog-login>' + esc(T("dog.loginBtn")) + "</button>"); return Promise.resolve(); }
    if (!a) { el.innerHTML = '<p class="note">' + esc(T("dog.mineNoAddr")) + "</p>"; return Promise.resolve(); }
    el.innerHTML = '<p class="note">' + esc(T("dog.loading")) + "</p>";
    D.pendingOf(a).then(function (w) {
      if (my !== mineSeq) return;
      $("dog-withdraw-row").hidden = w === 0n;
      $("dog-withdraw-amount").textContent = F("dog.mkPending", { amount: D.weiToBnb(w) });
    }).catch(function () {});
    return D.myDogs(a).then(function (r) {
      if (my !== mineSeq) return;
      if (!r.dogs.length) { el.innerHTML = emptyBox("dog.mineNoneT", "dog.mineNoneP", '<a class="btn" href="/mint.html#mint">' + esc(T("dog.mineGoMint")) + "</a>"); return; }
      return items(r.dogs.map(function (d) { return d.id; })).then(function (arr) {
        if (my === mineSeq) el.innerHTML = arr.map(function (it) { return card(it, "mine"); }).join("");
      });
    }).catch(function () { if (my === mineSeq) el.innerHTML = '<p class="note">' + esc(T("dog.rpcFail")) + "</p>"; });
  }
  var prevOnSession = window.hahaOnSession;
  window.hahaOnSession = function () { if (prevOnSession) prevOnSession.apply(this, arguments); if (dogStarted) loadMine(); };
  document.addEventListener("click", function (e) {
    if (e.target.closest("[data-dog-login]")) { var i = $("ai"); if (i) { i.scrollIntoView({ block: "center" }); i.focus(); } }
  });

  /* Copyable commands. */
  function priceFor(btn) {
    var art = btn.closest("article"), input = art ? art.querySelector(".price-input") : null, v = input ? input.value.trim() : "";
    if (!priceOk(v)) { toast(T("dog.toastPrice")); if (input) input.focus(); return null; }
    return v;
  }
  document.addEventListener("click", function (e) {
    var b;
    if ((b = e.target.closest("[data-dbuy]"))) { copyTask("dogBuy", { id: b.getAttribute("data-dbuy"), price: b.getAttribute("data-price") }, "dog.toastBuy"); return; }
    if ((b = e.target.closest("[data-dlist]"))) { var p = priceFor(b); if (p) copyTask("dogList", { id: b.getAttribute("data-dlist"), price: p }, "dog.toastList"); return; }
    if ((b = e.target.closest("[data-dreprice]"))) { var p2 = priceFor(b); if (p2) copyTask("dogReprice", { id: b.getAttribute("data-dreprice"), price: p2 }, "dog.toastReprice"); return; }
    if ((b = e.target.closest("[data-dcancel]"))) { copyTask("dogCancel", { id: b.getAttribute("data-dcancel") }, "dog.toastCancel"); return; }
    if ((b = e.target.closest("[data-dclear]"))) { copyTask("dogClear", { id: b.getAttribute("data-dclear") }, "dog.toastClear"); return; }
    if (e.target.closest("[data-dwithdraw]")) copyTask("dogWithdraw", {}, "dog.toastWithdraw");
  });

  function startDog() {
    loadListings();
    loadDogStats();
    loadMine();
    var q = null;
    try { q = new URLSearchParams(location.search).get("dog"); } catch (err) {}
    if (validId(q)) { $("dog-find").value = q; searchHit(); }
  }
  HahaI18n.onChange(function () {
    if (!dogStarted) return;
    paintListings(); searchHit(); paintDogStats(); loadMine();
    $("dog-src").textContent = T(listingsViaIndex ? "dog.mkIndexer" : "dog.mkChainSrc");
  });
})();
