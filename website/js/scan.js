/* haha scan — haha.meme 链上数据浏览器。所有数据只读索引器 /api/v1/*，
 * 不直连链、不发交易。每个条目都挂 BscScan 链接，可逐条核对。 */
(function () {
  "use strict";

  var BSC = "https://bscscan.com";
  var REGISTRAR = "0x43426E37a31AafDaba851858e34B81DC300650F8";
  var IDENTITY = "0x54A70BF81B288d41013D7b57c2Db0922f1E1a4d4";
  var SEASON1 = "0x4B8a35bFe18750c2058fd01e7159728adD345C00";
  var ADMIN = "0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7";
  var START_BLOCK = 134834631;
  var FIRST_DAY = 20781;
  var LAST_DAY = 20795;
  var CONFIRMATIONS = 3;

  var base = (window.HAHA_INDEXER_BASE || "/api").replace(/\/$/, "");
  var ADDR = window.HAHA_ADDRESSES || {};

  function T(key) {
    return (window.HahaI18n && HahaI18n.t) ? HahaI18n.t(key) : "";
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c];
    });
  }
  /* agentURI 只认 http(s) 链接：其他 scheme（如 javascript:、data:）只渲染纯文本，
   * 防存储型 XSS。与 agent.html 的 uriLink 同款白名单（H4）。 */
  function uriLink(uri) {
    var u = String(uri == null ? "" : uri).trim();
    if (/^https?:\/\//i.test(u)) return '<a href="' + esc(u) + '" target="_blank" rel="noopener noreferrer">' + esc(u) + "</a>";
    return esc(u);
  }
  function $(id) { return document.getElementById(id); }
  /* API 请求节流（H6）：scan 页一次加载要拉十余个端点，并行全发会撞上
   * /api/ 60r/m 限流（已误伤过真实用户）。全部请求走同一队列：最多 2 个
   * 并发，相邻两次发出至少间隔 100ms；第一季 15 天的请求也一样排队，
   * 不再一次并行发 15 个。搜索等用户触发的请求同样进队，但队列平时
   * 是空的，不会等很久。 */
  var apiQueue = [];
  var apiRunning = 0;
  var apiLastStart = 0;
  var API_MAX_CONCURRENT = 2;
  var API_MIN_GAP_MS = 100;
  function apiQueuePump() {
    if (!apiQueue.length || apiRunning >= API_MAX_CONCURRENT) return;
    var wait = API_MIN_GAP_MS - (Date.now() - apiLastStart);
    if (wait > 0) { setTimeout(apiQueuePump, wait); return; }
    var job = apiQueue.shift();
    apiRunning++;
    apiLastStart = Date.now();
    job();
  }
  function api(path) {
    return new Promise(function (resolve, reject) {
      apiQueue.push(function () {
        fetch(base + path, {headers: {"accept": "application/json"}})
          .then(function (res) {
            if (!res.ok) {
              var e = new Error("http " + res.status);
              e.status = res.status;
              throw e;
            }
            return res.json();
          })
          .then(function (d) { apiRunning--; apiQueuePump(); resolve(d); },
            function (e) { apiRunning--; apiQueuePump(); reject(e); });
      });
      apiQueuePump();
    });
  }
  function fmtTime(v) {
    if (!v) return "—";
    try {
      if (window.HahaI18n && HahaI18n.formatTime) return HahaI18n.formatTime(v);
    } catch (e) {}
    return String(v);
  }
  function shortHash(h) { return h ? h.slice(0, 10) + "…" + h.slice(-8) : "—"; }
  function shortAddr(a) { return a ? a.slice(0, 6) + "…" + a.slice(-4) : "—"; }
  function txLink(h, label) {
    if (!h) return "—";
    return '<a href="' + BSC + "/tx/" + esc(h) + '" target="_blank" rel="noopener noreferrer">' + esc(label || shortHash(h)) + "</a>";
  }
  function addrLink(a, label) {
    if (!a) return "—";
    return '<a href="' + BSC + "/address/" + esc(a) + '" target="_blank" rel="noopener noreferrer">' + esc(label || shortAddr(a)) + "</a>";
  }
  /* 事件名：英文事件名 -> i18n key（中文标签 / 英文标签）。未定义的事件名
   * 显示 scan.eventUnknown。 */
  var EVENT_LABELS = {
    NameMinted: "scan.evNameMinted", Transfer: "scan.evTransfer",
    Approval: "scan.evApproval", ApprovalForAll: "scan.evApprovalForAll",
    Listed: "scan.evListed", PriceUpdated: "scan.evPriceUpdated",
    Cancelled: "scan.evCancelled", StaleCleared: "scan.evStaleCleared",
    Sold: "scan.evSold", Withdrawn: "scan.evWithdrawn",
    AgentActivated: "scan.evAgentActivated", URIUpdated: "scan.evURIUpdated",
    AgentReset: "scan.evAgentReset", AgentOperatorSet: "scan.evAgentOperatorSet",
    Rated: "scan.evRated", PointsChanged: "scan.evPointsChanged",
    Earned: "scan.evEarned", PointParamsUpdated: "scan.evPointParamsUpdated",
    SpenderUpdated: "scan.evSpenderUpdated", EarnerUpdated: "scan.evEarnerUpdated",
    SpenderBudgetUpdated: "scan.evSpenderBudgetUpdated",
    RoundOpened: "scan.evRoundOpened", RoundClaimed: "scan.evRoundClaimed",
    GameUpdated: "scan.evGameUpdated", AddrChanged: "scan.evAddrChanged",
    TextChanged: "scan.evTextChanged", RecordsCleared: "scan.evRecordsCleared",
    PrimaryNameSet: "scan.evPrimaryNameSet", PrimaryNameCleared: "scan.evPrimaryNameCleared",
    NewOwner: "scan.evNewOwner", NewResolver: "scan.evNewResolver",
    ListsFrozen: "scan.evListsFrozen",
    DayRootSet: "scan.evDayRootSet", Redeemed: "scan.evRedeemed",
    FulfillmentAttested: "scan.evFulfillmentAttested",
    Verified: "scan.evVerified", FindingCommitted: "scan.evFindingCommitted",
    CanonicalAssigned: "scan.evCanonicalAssigned",
    FindingPaid: "scan.evFindingPaid", ValidatorSet: "scan.evValidatorSet",
    RewardSignerSet: "scan.evRewardSignerSet", TaskPackSet: "scan.evTaskPackSet",
    AccidentDeclared: "scan.evAccidentDeclared",
    AccidentRefunded: "scan.evAccidentRefunded",
    AccidentCompensationDeferred: "scan.evAccidentCompensationDeferred",
    AccidentCompensated: "scan.evAccidentCompensated",
    ValidationRequest: "scan.evValidationRequest",
    ValidationResponse: "scan.evValidationResponse",
    ValidationDisputed: "scan.evValidationDisputed"
  };
  function eventLabel(name) {
    var k = name && EVENT_LABELS[name];
    return k ? T(k) : T("scan.eventUnknown");
  }
  /* 合约名：API 合约 key -> 短名（英文标识）与中文名 i18n key。
   * addresses.js 的 key（namePolicy/agentIdentity/marketplace）与 API 的
   * key（policy/identity/market）不一样，这里统一归一化到 API key。 */
  var CONTRACT_SHORT = {
    registrar: "Registrar", registry: "Registry", resolver: "Resolver",
    policy: "NamePolicy", identity: "AgentIdentity", points: "Points",
    reputation: "Reputation", market: "Marketplace", metadata: "Metadata",
    deployer: "Deployer", season1: "Season1", aiRegistry: ".ai Registry",
    validation: "Validation"
  };
  var CONTRACT_CN = {
    registrar: "scan.cnRegistrar", registry: "scan.cnRegistry",
    resolver: "scan.cnResolver", policy: "scan.cnNamePolicy",
    identity: "scan.cnIdentity", points: "scan.cnPoints",
    reputation: "scan.cnReputation", market: "scan.cnMarket",
    metadata: "scan.cnMetadata", deployer: "scan.cnDeployer",
    season1: "scan.cnSeason1", aiRegistry: "scan.cnAiRegistry",
    validation: "scan.cnValidation"
  };
  var ADDR_KEY = {namePolicy: "policy", agentIdentity: "identity", marketplace: "market"};
  var ADDR_TO_CONTRACT = {};
  (function () {
    Object.keys(ADDR).forEach(function (k) {
      var a = ADDR[k];
      if (a) ADDR_TO_CONTRACT[String(a).toLowerCase()] = ADDR_KEY[k] || k;
    });
    ADDR_TO_CONTRACT[SEASON1.toLowerCase()] = "season1";
  })();
  function contractKeyOf(addr) {
    return addr ? (ADDR_TO_CONTRACT[String(addr).toLowerCase()] || null) : null;
  }
  function contractDisplay(addr) {
    var k = contractKeyOf(addr);
    if (!k) return null;
    return CONTRACT_SHORT[k] + "-" + T(CONTRACT_CN[k]);
  }
  function fill(key, vars) {
    return (window.HahaI18n && HahaI18n.fill) ? HahaI18n.fill(key, vars) : T(key);
  }
  /* 地址 -> .ai：复用站内 rpc.js 的 HahaRPC.aiName（链上 handleOf，页内有缓存）。
   * 有 .ai 显示 .ai，无 .ai 显示缩短地址。渲染时先放缩短地址，解析到后再换。 */
  function aiSpan(addr) {
    if (!addr) return "—";
    return '<span class="scan-ai" data-addr="' + esc(String(addr).toLowerCase()) + '">' + esc(shortAddr(addr)) + "</span>";
  }
  function aiAddrLink(addr) {
    if (!addr) return "—";
    return '<a href="' + BSC + "/address/" + esc(addr) + '" target="_blank" rel="noopener noreferrer">' + aiSpan(addr) + "</a>";
  }
  function linkAddrs(text) {
    return String(text).replace(/0x[0-9a-fA-F]{40}(?![0-9a-fA-F])/g, function (m) {
      return '<span class="scan-ai" data-addr="' + m.toLowerCase() + '">' + esc(m) + "</span>";
    });
  }
  /* .ai 查询队列：一次渲染可能冒出几十个地址，全并发发 RPC 会把节点
   * 打超时（单次 1.8s），超时的那批就永远显示 EVM 地址。所以这里排队：
   * 最多 3 个并发，相邻两次发出至少间隔 100ms。查到确定结果（有 .ai
   * 或确认无 .ai）才标记为已查；RPC 失败时重试 2 次，3 次都失败才放过。
   * 注意：不要在发起时就标记已查——失败也要能重试。 */
  var aiNameLookedUp = {};
  var aiNameQueued = {};
  var aiQueue = [];
  var aiRunning = 0;
  var aiLastStart = 0;
  var AI_MAX_CONCURRENT = 3;
  var AI_MIN_GAP_MS = 100;
  var AI_MAX_RETRIES = 2;
  function aiQueuePump() {
    if (!aiQueue.length || aiRunning >= AI_MAX_CONCURRENT) return;
    var wait = AI_MIN_GAP_MS - (Date.now() - aiLastStart);
    if (wait > 0) { setTimeout(aiQueuePump, wait); return; }
    var job = aiQueue.shift();
    aiRunning++;
    aiLastStart = Date.now();
    job();
  }
  function aiLookup(a, attempt) {
    HahaRPC.aiName(a).then(function (ai) {
      aiRunning--;
      aiQueuePump();
      // 确定结果：有 .ai 就全页替换；确认无 .ai（null）也标记已查，不再重试。
      aiNameLookedUp[a] = true;
      delete aiNameQueued[a];
      if (!ai) return;
      var list = document.querySelectorAll('span.scan-ai[data-addr="' + a + '"]');
      for (var j = 0; j < list.length; j++) list[j].textContent = ai;
    }).catch(function () {
      aiRunning--;
      aiQueuePump();
      if (attempt < AI_MAX_RETRIES) {
        // RPC 失败（超时/节点忙）：过 1 秒再试一次，不标记已查。
        setTimeout(function () {
          aiQueue.push(function () { aiLookup(a, attempt + 1); });
          aiQueuePump();
        }, 1000);
      } else {
        // 3 次都失败才放过，本次显示 EVM 地址；刷新页面会再试。
        aiNameLookedUp[a] = true;
        delete aiNameQueued[a];
      }
    });
  }
  function resolveAiNames(root) {
    if (!root || !window.HahaRPC || typeof HahaRPC.aiName !== "function") return;
    var seen = {};
    var spans = root.querySelectorAll ? root.querySelectorAll("span.scan-ai[data-addr]") : [];
    for (var i = 0; i < spans.length; i++) {
      var a = spans[i].getAttribute("data-addr");
      if (a && !seen[a] && !aiNameLookedUp[a] && !aiNameQueued[a]) {
        seen[a] = true;
        aiNameQueued[a] = true;
        aiQueue.push((function (addr) { return function () { aiLookup(addr, 0); }; })(a));
      }
    }
    aiQueuePump();
  }
  function blockLink(n) {
    if (n == null) return "—";
    return '<a href="' + BSC + "/block/" + esc(String(n)) + '" target="_blank" rel="noopener noreferrer">' + esc(String(n)) + "</a>";
  }
  function nameTokenLink(tokenId, label) {
    if (!tokenId) return esc(label || "—");
    return '<a href="' + BSC + "/token/" + REGISTRAR + "?a=" + esc(tokenId) + '" target="_blank" rel="noopener noreferrer">' + esc(label || tokenId) + "</a>";
  }
  function agentTokenLink(tokenId, label) {
    if (!tokenId) return esc(label || "—");
    return '<a href="' + BSC + "/token/" + IDENTITY + "?a=" + esc(tokenId) + '" target="_blank" rel="noopener noreferrer">' + esc(label || tokenId) + "</a>";
  }
  function weiToBnb(w) {
    try {
      var b = BigInt(w);
      var whole = b / (10n ** 18n);
      var frac = b % (10n ** 18n);
      if (frac === 0n) return whole.toString();
      var f = frac.toString().padStart(18, "0").replace(/0+$/, "");
      return whole.toString() + "." + f;
    } catch (e) {
      return String(w);
    }
  }
  function dayDate(day) {
    var ms = Date.UTC(2026, 10, 24) + (day - FIRST_DAY) * 86400000;
    var d = new Date(ms);
    var m = d.getUTCMonth() + 1;
    var dd = d.getUTCDate();
    return d.getUTCFullYear() + "-" + (m < 10 ? "0" + m : m) + "-" + (dd < 10 ? "0" + dd : dd);
  }
  function todayDay() {
    return Math.floor(Date.now() / 1000 / 86400);
  }
  function errHtml() {
    return '<p class="note">' + esc(T("scan.errLoad")) + "</p>";
  }

  var state = {
    stats: null, health: null,
    latestEvents: null, latestNames: null,
    names: {items: [], cursor: null, done: false},
    events: {items: [], cursor: null, done: false, contract: "", event: "", address: ""},
    agents: null, reputation: null,
    points: {items: [], cursor: null, done: false},
    listings: null, trades: null,
    seasonDays: {}, seasonFindings: null, findingsPublic: null,
    seasonLoaded: {}
  };

  /* ---------------- 总览 ---------------- */
  function renderOverview() {
    var el = $("scan-overview-body");
    if (!el) return;
    if (!state.stats || !state.health) {
      el.innerHTML = '<p class="note">' + esc(T("scan.loading")) + "</p>";
      return;
    }
    var s = state.stats, h = state.health;
    var cards = [
      [T("scan.statNames"), String(s.registered.total)],
      [T("scan.statHaha"), String(s.registered.haha)],
      [T("scan.statMeme"), String(s.registered.meme)],
      [T("scan.statParticipants"), String(s.participants)],
      [T("scan.statActiveAgents"), String(s.activeAgents)],
      [T("scan.statActivations"), String(s.totalActivations)],
      [T("scan.statInteractions"), String(s.agentInteractions)],
      [T("scan.statListings"), String(s.market.listings)],
      [T("scan.statFloor"), s.market.floorPriceWei == null ? "—" : weiToBnb(s.market.floorPriceWei) + " BNB"],
      [T("scan.statVol24"), weiToBnb(s.market.volume24hWei) + " BNB"]
    ];
    var html = '<div class="scan-stats">' + cards.map(function (c) {
      return '<div><b>' + esc(c[0]) + "</b><span>" + esc(c[1]) + "</span></div>";
    }).join("") + "</div>";
    html += '<div class="scan-sync"><h3>' + esc(T("scan.syncTitle")) + "</h3><p>"
      + esc(T("scan.syncSafe")) + ": " + blockLink(h.safeBlock) + " · "
      + esc(T("scan.syncHead")) + ": " + blockLink(h.headBlock) + " · "
      + esc(T("scan.syncLag")) + ": " + esc(h.lagBlocks == null ? "—" : String(h.lagBlocks)) + " · "
      + esc(T("scan.syncConf")) + ": " + esc(String(CONFIRMATIONS)) + " · "
      + esc(h.ok ? T("scan.syncOk") : T("scan.syncBad")) + "</p></div>";
    html += shortSections(s);
    html += "<h3>" + esc(T("scan.latestEvents")) + "</h3>";
    html += state.latestEvents ? eventTable(state.latestEvents, false) : '<p class="note">' + esc(T("scan.loading")) + "</p>";
    html += "<h3>" + esc(T("scan.latestNames")) + "</h3>";
    if (state.latestNames) {
      html += '<div class="lb-scroll"><table><thead><tr><th>' + esc(T("scan.colName")) + "</th><th>" + esc(T("scan.colOwner")) + "</th><th>" + esc(T("scan.colMintedAt")) + "</th><th>" + esc(T("scan.colBlock")) + "</th></tr></thead><tbody>"
        + state.latestNames.map(function (n) {
          return "<tr><td>" + nameTokenLink(n.tokenId, n.fullName) + "</td><td>" + aiAddrLink(n.owner) + "</td><td>" + esc(fmtTime(n.mintedAt)) + "</td><td>" + blockLink(n.blockNumber) + "</td></tr>";
        }).join("") + "</tbody></table></div>";
    } else {
      html += '<p class="note">' + esc(T("scan.loading")) + "</p>";
    }
    el.innerHTML = html;
    resolveAiNames(el);
  }
  /* 3 位短名 / 3 位字母剩余（从数据看板迁移过来）：一行并排两个卡片，
   * 与 stats.html 的 .board-grid.two + .board-card 同款（两列等宽，窄屏自动叠放）。 */
  function shortSections(s) {
    var card = function (titleKey, data) {
      var num = function (v) { return v == null ? "—" : String(v); };
      if (!data) return '<article class="board-card"><h3>' + esc(T(titleKey)) + "</h3>" + '<p class="note">' + esc(T("scan.loading")) + "</p></article>";
      var h = data.haha || {}, m = data.meme || {};
      return '<article class="board-card"><h3>' + esc(T(titleKey)) + "</h3>"
        + '<div class="split"><span>' + esc(T("scan.shortHahaLeft")) + "</span><b>" + esc(num(h.remaining)) + "</b></div>"
        + '<div class="split"><span>' + esc(T("scan.shortMemeLeft")) + "</span><b>" + esc(num(m.remaining)) + "</b></div>"
        + '<div class="sub">' + esc(fill("scan.shortMinted", {a: num(h.minted), b: num(m.minted)})) + "</div></article>";
    };
    return '<div class="board-grid two">'
      + card("scan.shortDigitTitle", s.threeDigit)
      + card("scan.shortLetterTitle", s.threeLetter)
      + "</div>"
      + '<p class="note">' + esc(T("scan.shortNote")) + "</p>";
  }
  function loadOverview() {
    renderOverview();
    api("/v1/stats").then(function (d) { state.stats = d; renderOverview(); })
      .catch(function () { var el = $("scan-overview-body"); if (el && !state.stats) el.innerHTML = errHtml(); });
    api("/health").then(function (d) { state.health = d; renderOverview(); })
      .catch(function () {});
    api("/v1/events?limit=10").then(function (d) { state.latestEvents = d.events || []; renderOverview(); })
      .catch(function () {});
    api("/v1/names?limit=10").then(function (d) { state.latestNames = d.names || []; renderOverview(); })
      .catch(function () {});
  }

  /* ---------------- 名字 ---------------- */
  function nameRows(items) {
    return items.map(function (n) {
      return "<tr><td>" + nameTokenLink(n.tokenId, n.fullName) + "</td><td>" + esc(n.label) + "</td><td>" + esc(n.tld === 0 ? ".haha" : ".meme") + "</td><td>" + aiAddrLink(n.owner) + "</td><td>" + esc(fmtTime(n.mintedAt)) + "</td><td>" + blockLink(n.blockNumber) + "</td></tr>";
    }).join("");
  }
  function renderNames() {
    var el = $("scan-names-body");
    if (!el) return;
    var btn = $("scan-names-more");
    if (!state.names.items.length) {
      el.innerHTML = '<p class="note">' + esc(T("scan.loading")) + "</p>";
      if (btn) btn.hidden = true;
      return;
    }
    el.innerHTML = '<div class="lb-scroll"><table><thead><tr><th>' + esc(T("scan.colName")) + "</th><th>" + esc(T("scan.colLabel")) + "</th><th>" + esc(T("scan.colTld")) + "</th><th>" + esc(T("scan.colOwner")) + "</th><th>" + esc(T("scan.colMintedAt")) + "</th><th>" + esc(T("scan.colBlock")) + "</th></tr></thead><tbody>"
      + nameRows(state.names.items) + "</tbody></table></div>";
    resolveAiNames(el);
    if (btn) {
      btn.hidden = state.names.done;
      btn.textContent = state.names.done ? T("scan.noMore") : T("scan.loadMore");
    }
  }
  function loadNames(more) {
    if (!more) { state.names = {items: [], cursor: null, done: false}; }
    if (state.names.done) { renderNames(); return; }
    var url = "/v1/names?limit=24" + (state.names.cursor ? "&cursor=" + encodeURIComponent(state.names.cursor) : "");
    renderNames();
    api(url).then(function (d) {
      state.names.items = state.names.items.concat(d.names || []);
      state.names.cursor = d.nextCursor || null;
      state.names.done = !d.nextCursor;
      renderNames();
    }).catch(function () {
      var el = $("scan-names-body");
      if (el && !state.names.items.length) el.innerHTML = errHtml();
    });
  }

  /* ---------------- 事件 ---------------- */
  function eventTable(events, showArgs) {
    if (!events.length) return '<p class="note">' + esc(T("scan.empty")) + "</p>";
    var rows = events.map(function (e) {
      var args = "";
      if (showArgs) {
        var j = JSON.stringify(e.args || {}, null, 1);
        if (j.length > 800) j = j.slice(0, 800) + "…";
        args = "<td><details><summary>" + esc(T("scan.colArgs")) + "</summary><pre>" + linkAddrs(esc(j)) + "</pre></details></td>";
      }
      var cDisp = contractDisplay(e.address);
      var contractCell = cDisp
        ? '<a href="' + BSC + "/address/" + esc(e.address) + '" target="_blank" rel="noopener noreferrer">' + esc(cDisp) + "</a>"
        : addrLink(e.address);
      return "<tr><td>" + esc(fmtTime(e.blockTime)) + "</td><td>" + blockLink(e.blockNumber) + "</td><td>" + esc(e.event || T("scan.eventUnknown")) + "</td><td>" + esc(eventLabel(e.event)) + "</td><td>" + contractCell + "</td><td>" + txLink(e.txHash) + "</td>" + args + "</tr>";
    }).join("");
    var head = "<tr><th>" + esc(T("scan.colTime")) + "</th><th>" + esc(T("scan.colBlock")) + "</th><th>" + esc(T("scan.colEvent")) + "</th><th>" + esc(T("scan.colEventName")) + "</th><th>" + esc(T("scan.colContract")) + "</th><th>" + esc(T("scan.colTx")) + "</th>" + (showArgs ? "<th>" + esc(T("scan.colArgs")) + "</th>" : "") + "</tr>";
    return '<div class="lb-scroll"><table><thead>' + head + "</thead><tbody>" + rows + "</tbody></table></div>";
  }
  function renderEvents() {
    var el = $("scan-events-body");
    if (!el) return;
    var btn = $("scan-events-more");
    if (!state.events.items.length) {
      el.innerHTML = '<p class="note">' + esc(T("scan.loading")) + "</p>";
      if (btn) btn.hidden = true;
      return;
    }
    el.innerHTML = eventTable(state.events.items, true);
    resolveAiNames(el);
    if (btn) {
      btn.hidden = state.events.done;
      btn.textContent = state.events.done ? T("scan.noMore") : T("scan.loadMore");
    }
  }
  function eventsUrl() {
    var f = state.events;
    var url = "/v1/events?limit=24";
    if (f.contract) url += "&contract=" + encodeURIComponent(f.contract);
    if (f.event) url += "&event=" + encodeURIComponent(f.event);
    if (f.address) url += "&address=" + encodeURIComponent(f.address);
    if (f.cursor) url += "&cursor=" + encodeURIComponent(f.cursor);
    return url;
  }
  function loadEvents(more) {
    if (!more) { state.events.items = []; state.events.cursor = null; state.events.done = false; }
    if (state.events.done) { renderEvents(); return; }
    renderEvents();
    api(eventsUrl()).then(function (d) {
      state.events.items = state.events.items.concat(d.events || []);
      state.events.cursor = d.nextCursor || null;
      state.events.done = !d.nextCursor;
      renderEvents();
    }).catch(function () {
      var el = $("scan-events-body");
      if (el && !state.events.items.length) el.innerHTML = errHtml();
    });
  }

  /* ---------------- Agent ---------------- */
  function starsText(sum, count) {
    if (!count) return "—";
    return (sum / count).toFixed(2) + " (" + count + ")";
  }
  function agentRows(items) {
    return items.map(function (a) {
      return "<tr><td>" + agentTokenLink(a.tokenId, "#" + a.agentId) + "</td><td>" + nameTokenLink(a.tokenId, a.fullName) + "</td><td>" + esc(String(a.generation)) + "</td><td>" + aiAddrLink(a.owner) + "</td><td>" + esc(starsText(a.starsSum, a.starsCount)) + "</td><td>" + esc(fmtTime(a.activatedAt)) + "</td></tr>";
    }).join("");
  }
  function renderAgents() {
    var el = $("scan-agents-body");
    if (!el) return;
    var html = "";
    if (!state.agents) {
      html = '<p class="note">' + esc(T("scan.loading")) + "</p>";
    } else if (!state.agents.length) {
      html = '<p class="note">' + esc(T("scan.empty")) + "</p>";
    } else {
      html = '<div class="lb-scroll"><table><thead><tr><th>' + esc(T("scan.colAgent")) + "</th><th>" + esc(T("scan.colName")) + "</th><th>" + esc(T("scan.colGen")) + "</th><th>" + esc(T("scan.colOwner")) + "</th><th>" + esc(T("scan.colStars")) + "</th><th>" + esc(T("scan.colActivated")) + "</th></tr></thead><tbody>" + agentRows(state.agents) + "</tbody></table></div>";
    }
    html += "<h3>" + esc(T("scan.repTitle")) + "</h3>";
    if (!state.reputation) {
      html += '<p class="note">' + esc(T("scan.loading")) + "</p>";
    } else if (!state.reputation.length) {
      html += '<p class="note">' + esc(T("scan.empty")) + "</p>";
    } else {
      html += '<div class="lb-scroll"><table><thead><tr><th>' + esc(T("scan.colRank")) + "</th><th>" + esc(T("scan.colAgent")) + "</th><th>" + esc(T("scan.colName")) + "</th><th>" + esc(T("scan.colStars")) + "</th></tr></thead><tbody>"
        + state.reputation.map(function (a, i) {
          return "<tr><td>" + esc(String(a.rank || (i + 1))) + "</td><td>" + agentTokenLink(a.tokenId, "#" + a.agentId) + "</td><td>" + nameTokenLink(a.tokenId, a.fullName) + "</td><td>" + esc(starsText(a.starsSum, a.starsCount)) + "</td></tr>";
        }).join("") + "</tbody></table></div>";
    }
    el.innerHTML = html;
    resolveAiNames(el);
  }
  function loadAgents() {
    renderAgents();
    api("/v1/agents?limit=24").then(function (d) { state.agents = d.items || []; renderAgents(); })
      .catch(function () { var el = $("scan-agents-body"); if (el && !state.agents) el.innerHTML = errHtml(); });
    api("/v1/leaderboard/reputation?limit=10").then(function (d) { state.reputation = d.items || []; renderAgents(); })
      .catch(function () {});
  }

  /* ---------------- 积分榜 ---------------- */
  function renderPoints() {
    var el = $("scan-points-body");
    if (!el) return;
    var btn = $("scan-points-more");
    if (!state.points.items.length) {
      el.innerHTML = '<p class="note">' + esc(T("scan.loading")) + "</p>";
      if (btn) btn.hidden = true;
      return;
    }
    el.innerHTML = '<div class="lb-scroll"><table><thead><tr><th>' + esc(T("scan.colRank")) + "</th><th>" + esc(T("scan.colAi")) + "</th><th>" + esc(T("scan.colName")) + "</th><th>" + esc(T("scan.colBalance")) + "</th><th>" + esc(T("scan.colUpdated")) + "</th></tr></thead><tbody>"
      + state.points.items.map(function (p) {
        return "<tr><td>" + esc(String(p.rank)) + "</td><td>" + esc(p.handle ? p.handle + ".ai" : shortHash(p.aiId)) + "</td><td>" + (p.name ? nameTokenLink(null, p.name) : "—") + "</td><td>" + esc(String(p.balance)) + "</td><td>" + esc(fmtTime(p.updatedAt)) + "</td></tr>";
      }).join("") + "</tbody></table></div>";
    if (btn) {
      btn.hidden = state.points.done;
      btn.textContent = state.points.done ? T("scan.noMore") : T("scan.loadMore");
    }
  }
  function loadPoints(more) {
    if (!more) { state.points = {items: [], cursor: null, done: false}; }
    if (state.points.done) { renderPoints(); return; }
    var url = "/v1/leaderboard/points?limit=24" + (state.points.cursor ? "&cursor=" + encodeURIComponent(state.points.cursor) : "");
    renderPoints();
    api(url).then(function (d) {
      state.points.items = state.points.items.concat(d.items || []);
      state.points.cursor = d.nextCursor || null;
      state.points.done = !d.nextCursor;
      renderPoints();
    }).catch(function () {
      var el = $("scan-points-body");
      if (el && !state.points.items.length) el.innerHTML = errHtml();
    });
  }

  /* ---------------- 市场 ---------------- */
  function renderMarket() {
    var el = $("scan-market-body");
    if (!el) return;
    var html = "";
    if (!state.listings) {
      html = '<p class="note">' + esc(T("scan.loading")) + "</p>";
    } else if (!state.listings.length) {
      html = '<p class="note">' + esc(T("scan.empty")) + "</p>";
    } else {
      html = '<div class="lb-scroll"><table><thead><tr><th>' + esc(T("scan.colName")) + "</th><th>" + esc(T("scan.colSeller")) + "</th><th>" + esc(T("scan.colPrice")) + "</th><th>" + esc(T("scan.colTime")) + "</th><th>" + esc(T("scan.colTx")) + "</th></tr></thead><tbody>"
        + state.listings.map(function (l) {
          return "<tr><td>" + nameTokenLink(l.tokenId, l.fullName) + "</td><td>" + aiAddrLink(l.seller) + "</td><td>" + esc(weiToBnb(l.priceWei)) + " BNB</td><td>" + esc(fmtTime(l.listedAt)) + "</td><td>" + txLink(l.txHash) + "</td></tr>";
        }).join("") + "</tbody></table></div>";
    }
    html += "<h3>" + esc(T("scan.tradesTitle")) + "</h3>";
    if (!state.trades) {
      html += '<p class="note">' + esc(T("scan.loading")) + "</p>";
    } else if (!state.trades.length) {
      html += '<p class="note">' + esc(T("scan.tradesEmpty")) + "</p>";
    } else {
      html += '<div class="lb-scroll"><table><thead><tr><th>' + esc(T("scan.colName")) + "</th><th>" + esc(T("scan.colSeller")) + "</th><th>" + esc(T("scan.colBuyer")) + "</th><th>" + esc(T("scan.colPrice")) + "</th><th>" + esc(T("scan.colTime")) + "</th><th>" + esc(T("scan.colTx")) + "</th></tr></thead><tbody>"
        + state.trades.map(function (t) {
          return "<tr><td>" + nameTokenLink(t.tokenId, t.fullName) + "</td><td>" + aiAddrLink(t.seller) + "</td><td>" + aiAddrLink(t.buyer) + "</td><td>" + esc(weiToBnb(t.priceWei)) + " BNB</td><td>" + esc(fmtTime(t.tradedAt)) + "</td><td>" + txLink(t.txHash) + "</td></tr>";
        }).join("") + "</tbody></table></div>";
    }
    el.innerHTML = html;
    resolveAiNames(el);
  }
  function loadMarket() {
    renderMarket();
    api("/v1/listings?limit=24").then(function (d) { state.listings = d.items || []; renderMarket(); })
      .catch(function () { var el = $("scan-market-body"); if (el && !state.listings) el.innerHTML = errHtml(); });
    api("/v1/trades?limit=24").then(function (d) { state.trades = d.items || []; renderMarket(); })
      .catch(function () {});
  }

  /* ---------------- 第一季 ---------------- */
  function dayCard(day) {
    var d = state.seasonDays[day];
    var title = T("scan.seasonDay").replace("{n}", String(day - FIRST_DAY + 1)) + " · " + dayDate(day) + " · day " + day;
    if (d === undefined) {
      return '<details class="scan-day" data-day="' + day + '"><summary>' + esc(title) + " — " + esc(T("scan.loading")) + "</summary></details>";
    }
    if (d === null) {
      return '<details class="scan-day" data-day="' + day + '"><summary>' + esc(title) + " — " + esc(T("scan.seasonNotStarted")) + "</summary></details>";
    }
    var match = d.rootMatch
      ? '<span class="scan-ok">✓ ' + esc(T("scan.rootMatchYes")) + "</span>"
      : '<span class="scan-bad">✗ ' + esc(T("scan.rootMatchNo")) + "</span>";
    var body = '<div class="scan-day-body">'
      + "<p>" + esc(T("scan.colRoot")) + ": <code>" + esc(d.merkleRoot) + "</code><br>"
      + esc(T("scan.colRecomputed")) + ": <code>" + esc(d.recomputedRoot || "—") + "</code> " + match + "<br>"
      + esc(T("scan.colSnapshot")) + ": " + blockLink(d.snapshotBlock) + " · " + esc(T("scan.colReserved")) + ": " + esc(String(d.reservedCount)) + " · "
      + esc(T("scan.colSlots")) + ": " + esc(String(d.remainingSlots)) + " · "
      + esc(T("scan.colFilled")) + ": " + esc(String(d.reservedFilled + d.boundaryFilled)) + " · "
      + esc(T("scan.colOpened")) + ": " + esc(d.opened ? T("scan.openedYes") : T("scan.openedNo")) + "</p>"
      + '<p><a href="' + esc(base + "/v1/season1/taskpack/" + day) + '" target="_blank" rel="noopener noreferrer">' + esc(T("scan.seasonTaskpack")) + "</a></p>"
      + '<div class="scan-day-detail" data-day="' + day + '"><p class="note">' + esc(T("scan.loading")) + "</p></div></div>";
    return '<details class="scan-day" data-day="' + day + '"><summary>' + esc(title) + "</summary>" + body + "</details>";
  }
  function renderSeasonDays() {
    var el = $("scan-season-days");
    if (!el) return;
    var html = "";
    for (var day = FIRST_DAY; day <= LAST_DAY; day++) html += dayCard(day);
    el.innerHTML = html;
    bindDayToggles(el);
  }
  function updateDayCard(day) {
    var el = $("scan-season-days");
    if (!el) return;
    var old = el.querySelector('details.scan-day[data-day="' + day + '"]');
    if (!old) { renderSeasonDays(); return; }
    var wasOpen = old.open;
    var tmp = document.createElement("div");
    tmp.innerHTML = dayCard(day);
    var neu = tmp.firstChild;
    if (wasOpen) neu.open = true;
    old.parentNode.replaceChild(neu, old);
    bindDayToggles(neu.parentNode || el);
    if (wasOpen) loadDayDetail(day);
  }
  function renderSeasonFindings() {
    var el = $("scan-season-findings");
    if (!el) return;
    var html = "";
    if (!state.seasonFindings) {
      html = '<p class="note">' + esc(T("scan.loading")) + "</p>";
    } else if (!state.seasonFindings.length) {
      html = '<p class="note">' + esc(T("scan.empty")) + "</p>";
    } else {
      html = '<div class="lb-scroll"><table><thead><tr><th>' + esc(T("scan.colReport")) + "</th><th>" + esc(T("scan.colSubmitter")) + "</th><th>" + esc(T("scan.colBlock")) + "</th><th>" + esc(T("scan.colTx")) + "</th><th>" + esc(T("scan.colAdopted")) + "</th><th>" + esc(T("scan.colReward")) + "</th><th>" + esc(T("scan.colReason")) + "</th></tr></thead><tbody>"
        + state.seasonFindings.map(function (f) {
          /* 采纳/奖励/理由与 season 页找错公示同一规则：public rulings 按小写
             reportEvidenceHash 匹配；采纳且已发放 → 100 已发放，采纳未发放 →
             100 待领取，不采纳 → 0，无 ruling → 待审核/待定/待复核。 */
          var key = String(f.reportEvidenceHash || "").toLowerCase();
          var p = (state.findingsPublic && state.findingsPublic[key]) || null;
          var adoptedCell, rewardCell, reasonCell;
          if (p) {
            adoptedCell = esc(p.adopted === true ? T("season.findingsAdopted") : T("season.findingsRejected"));
            rewardCell = esc(p.adopted === true
              ? (f.canonicalPaid ? T("season.findingsRewardPaid") : T("season.findingsRewardUnpaid"))
              : "0");
            reasonCell = esc(p.reason || "");
          } else {
            adoptedCell = esc(T("season.findingsPending"));
            rewardCell = esc(T("season.findingsPendingReward"));
            reasonCell = esc(T("season.findingsPendingReason"));
          }
          return "<tr><td>" + esc(f.reportId || shortHash(f.reportEvidenceHash)) + "</td><td>" + esc(f.handle ? f.handle + ".ai" : shortHash(f.aiId)) + "</td><td>" + blockLink(f.commitBlock) + "</td><td>" + txLink(f.commitTx) + "</td><td>" + adoptedCell + "</td><td>" + rewardCell + "</td><td>" + reasonCell + "</td></tr>";
        }).join("") + "</tbody></table></div>";
    }
    el.innerHTML = html;
  }
  function renderSeason() {
    renderSeasonDays();
    renderSeasonFindings();
  }
  function bindDayToggles(root) {
    var list = root.querySelectorAll ? root.querySelectorAll("details.scan-day") : [];
    for (var i = 0; i < list.length; i++) {
      (function (det) {
        det.addEventListener("toggle", function () {
          if (det.open) loadDayDetail(parseInt(det.getAttribute("data-day"), 10));
        });
      })(list[i]);
    }
  }
  function loadDayDetail(day) {
    if (state.seasonLoaded[day]) { renderDayDetail(day); return; }
    var box = document.querySelector('.scan-day-detail[data-day="' + day + '"]');
    if (!box) return;
    state.seasonLoaded[day] = "loading";
    Promise.all([
      api("/v1/season1/leaderboard/" + day).catch(function () { return null; }),
      api("/v1/season1/orders?day=" + day).catch(function () { return null; })
    ]).then(function (res) {
      state.seasonLoaded[day] = {lb: res[0], orders: res[1]};
      renderDayDetail(day);
    });
  }
  function renderDayDetail(day) {
    var box = document.querySelector('.scan-day-detail[data-day="' + day + '"]');
    if (!box) return;
    var data = state.seasonLoaded[day];
    if (!data || data === "loading") return;
    var html = "<h4>" + esc(T("scan.seasonLeaderboard")) + "</h4>";
    var entries = (data.lb && data.lb.entries) || [];
    if (!entries.length) {
      html += '<p class="note">' + esc(T("scan.empty")) + "</p>";
    } else {
      html += '<div class="lb-scroll"><table><thead><tr><th>' + esc(T("scan.colRank")) + "</th><th>" + esc(T("scan.colAi")) + "</th><th>" + esc(T("scan.colName")) + "</th><th>" + esc(T("scan.colBalance")) + "</th><th>" + esc(T("scan.colTier")) + "</th><th>" + esc(T("scan.colApplied")) + "</th><th>" + esc(T("scan.colStatus")) + "</th></tr></thead><tbody>"
        + entries.map(function (e) {
          return "<tr" + (e.valid === false ? ' class="invalid"' : "") + "><td>" + esc(e.rank == null ? "—" : String(e.rank)) + "</td><td>" + esc(e.handle ? e.handle + ".ai" : shortHash(e.aiId)) + "</td><td>" + esc(e.name || "—") + "</td><td>" + esc(e.balance) + "</td><td>" + esc(e.tier) + "</td><td>" + esc(e.appliedName || "—") + "</td><td>" + esc(e.status || "—") + "</td></tr>";
        }).join("") + "</tbody></table></div>";
    }
    html += "<h4>" + esc(T("scan.seasonOrders")) + "</h4>";
    var orders = (data.orders && data.orders.orders) || [];
    if (!orders.length) {
      html += '<p class="note">' + esc(T("scan.empty")) + "</p>";
    } else {
      html += '<div class="lb-scroll"><table><thead><tr><th>' + esc(T("scan.colOrder")) + "</th><th>" + esc(T("scan.colApplicant")) + "</th><th>" + esc(T("scan.colName")) + "</th><th>" + esc(T("scan.colTier")) + "</th><th>" + esc(T("scan.colStatus")) + "</th><th>" + esc(T("scan.colTx")) + "</th></tr></thead><tbody>"
        + orders.map(function (o) {
          return "<tr><td>" + esc(o.orderId) + "</td><td>" + aiAddrLink(o.applicant) + "</td><td>" + esc(o.label + (o.tld === 1 ? ".meme" : ".haha")) + "</td><td>" + esc(o.tier) + "</td><td>" + esc(o.status) + "</td><td>" + txLink(o.mintTx || null) + "</td></tr>";
        }).join("") + "</tbody></table></div>";
    }
    box.innerHTML = html;
    resolveAiNames(box);
  }
  function loadSeason() {
    renderSeason();
    var days = [];
    for (var day = FIRST_DAY; day <= LAST_DAY; day++) days.push(day);
    days.forEach(function (day) {
      api("/v1/season1/days/" + day).then(function (d) {
        state.seasonDays[day] = d;
        updateDayCard(day);
      }).catch(function (e) {
        if (e && e.status === 404) { state.seasonDays[day] = null; updateDayCard(day); }
      });
    });
    api("/v1/season1/findings").then(function (d) { state.seasonFindings = d.findings || []; renderSeasonFindings(); })
      .catch(function () {});
    fetch("/season/findings.json", {headers: {"accept": "application/json"}}).then(function (r) { return r.ok ? r.json() : null; }).then(function (d) { state.findingsPublic = (d && d.public) || {}; renderSeasonFindings(); }).catch(function () {});
  }

  /* ---------------- 合约 ---------------- */
  var CONTRACT_ROWS = [
    ["namePolicy", "scan.cNamePolicy", "", "scan.cnNamePolicy"],
    ["metadata", "scan.cMetadata", "", "scan.cnMetadata"],
    ["resolver", "scan.cResolver", "", "scan.cnResolver"],
    ["registry", "scan.cRegistry", "", "scan.cnRegistry"],
    ["registrar", "scan.cRegistrar", "", "scan.cnRegistrar"],
    ["agentIdentity", "scan.cIdentity", "", "scan.cnIdentity"],
    ["points", "scan.cPoints", "", "scan.cnPoints"],
    ["reputation", "scan.cReputation", "", "scan.cnReputation"],
    ["marketplace", "scan.cMarket", "", "scan.cnMarket"],
    ["deployer", "scan.cDeployer", "scan.deployerNote", "scan.cnDeployer"],
    ["aiRegistry", "scan.cAiRegistry", "", "scan.cnAiRegistry"],
    ["validation", "scan.cValidation", "scan.validationNote", "scan.cnValidation"]
  ];
  function renderContracts() {
    var el = $("scan-contracts-body");
    if (!el) return;
    var rows = CONTRACT_ROWS.map(function (r) {
      var addr = ADDR[r[0]];
      return "<tr><td>" + esc(T(r[1]) + (r[3] ? " " + T(r[3]) : "")) + "</td><td>" + (addr ? addrLink(addr) : "—") + "</td><td>" + esc(r[2] ? T(r[2]) : "") + "</td></tr>";
    }).join("");
    rows += "<tr><td>" + esc(T("scan.cAdmin")) + "</td><td>" + addrLink(ADMIN) + "</td><td>" + esc(T("scan.adminNote")) + "</td></tr>";
    rows += "<tr><td>" + esc(T("scan.cFee")) + "</td><td>" + addrLink(ADDR.feeReceiver) + "</td><td></td></tr>";
    rows += "<tr><td>" + esc(T("scan.cSeason1") + " " + T("scan.cnSeason1")) + "</td><td>" + addrLink(SEASON1) + "</td><td>" + esc(T("scan.season1Note")) + "</td></tr>";
    el.innerHTML = '<div class="lb-scroll"><table><thead><tr><th>' + esc(T("scan.colContractName")) + "</th><th>" + esc(T("scan.colAddress")) + "</th><th>" + esc(T("scan.colNote")) + "</th></tr></thead><tbody>" + rows + "</tbody></table></div>"
      + '<p class="note">' + esc(T("scan.contractsNote")) + "</p>";
  }

  /* ---------------- 搜索 ---------------- */
  function searchResult(html) {
    var el = $("scan-search-result");
    if (el) { el.innerHTML = html; resolveAiNames(el); }
  }
  function nameDetailHtml(n, gens) {
    var html = "<h3>" + esc(n.fullName) + "</h3>";
    if (!n.minted) {
      html += '<p class="note">' + esc(T("scan.nameNotMinted")) + "</p>";
      return html;
    }
    html += "<p>" + esc(T("scan.nameTokenId")) + ": " + nameTokenLink(n.tokenId, n.tokenId)
      + "<br>" + esc(T("scan.nameOwner")) + ": " + aiAddrLink(n.owner)
      + "<br>" + esc(T("scan.nameMintedAt")) + ": " + esc(fmtTime(n.mintedAt)) + "</p>";
    if (n.listing) {
      html += "<p>" + esc(T("scan.nameListing")) + ": " + aiAddrLink(n.listing.seller) + " · " + esc(weiToBnb(n.listing.priceWei)) + " BNB · " + esc(fmtTime(n.listing.listedAt)) + "</p>";
    }
    if (gens && gens.generations) {
      html += "<h4>" + esc(T("scan.nameGenerations")) + "</h4>";
      if (!gens.generations.length) {
        html += '<p class="note">' + esc(T("scan.noGenerations")) + "</p>";
      } else {
        html += gens.generations.map(function (g) {
          var revs = (g.reviews || []).map(function (r) {
            return "<li>" + esc(r.stars) + "★ · " + esc(r.raterAi || shortAddr(r.rater)) + (r.review ? " · " + esc(r.review) : "") + " · " + txLink(r.txHash) + "</li>";
          }).join("");
          return "<div class=\"scan-gen\"><p>#" + esc(g.agentId) + " · " + esc(T("scan.colGen")) + " " + esc(String(g.generation)) + " · " + esc(g.active ? T("scan.activeYes") : T("scan.activeNo")) + " · " + esc(starsText(g.starsSum, g.starsCount)) + "<br>"
            + esc(T("scan.nameOwner")) + ": " + aiAddrLink(g.owner) + "<br>"
            + esc(T("scan.colAgentUri")) + ": " + (g.agentURI ? uriLink(g.agentURI) : "—") + "</p>"
            + (revs ? "<ul>" + revs + "</ul>" : "") + "</div>";
        }).join("");
      }
    }
    return html;
  }
  function runSearch(q) {
    q = (q || "").trim();
    var box = $("scan-search-result");
    if (!q) { if (box) box.innerHTML = ""; return; }
    if (box) box.innerHTML = '<p class="note">' + esc(T("scan.loading")) + "</p>";
    var low = q.toLowerCase();
    // 名字 xxx.haha / xxx.meme
    if (/^[a-z0-9]{1,32}\.(haha|meme)$/.test(low)) {
      Promise.all([
        api("/v1/names/" + encodeURIComponent(low)).catch(function (e) { return null; }),
        api("/v1/names/" + encodeURIComponent(low) + "/generations").catch(function (e) { return null; })
      ]).then(function (res) {
        if (!res[0]) { searchResult(errHtml()); return; }
        searchResult(nameDetailHtml(res[0], res[1]));
      });
      return;
    }
    // 钱包地址
    if (/^0x[0-9a-fA-F]{40}$/.test(q)) {
      Promise.all([
        api("/v1/owners/" + q + "/names").catch(function () { return null; }),
        api("/v1/owners/" + q + "/primary").catch(function () { return null; })
      ]).then(function (res) {
        var names = res[0], prim = res[1];
        var html = "<h3>" + aiAddrLink(q) + "</h3>";
        if (prim && prim.primaryName) html += "<p>" + esc(T("scan.ownerPrimary")) + ": " + nameTokenLink(null, prim.primaryName) + "</p>";
        if (!names || !names.items || !names.items.length) {
          html += '<p class="note">' + esc(T("scan.ownerNone")) + "</p>";
        } else {
          html += '<div class="lb-scroll"><table><thead><tr><th>' + esc(T("scan.colName")) + "</th><th>" + esc(T("scan.colMintedAt")) + "</th><th>" + esc(T("scan.colListing")) + "</th></tr></thead><tbody>"
            + names.items.map(function (n) {
              return "<tr><td>" + nameTokenLink(n.tokenId, n.fullName) + "</td><td>" + esc(fmtTime(n.mintedAt)) + "</td><td>" + (n.listing ? esc(weiToBnb(n.listing.priceWei)) + " BNB" : "—") + "</td></tr>";
            }).join("") + "</tbody></table></div>";
        }
        searchResult(html);
      });
      return;
    }
    // 64 位 hex：aiId 或交易哈希
    if (/^0x[0-9a-fA-F]{64}$/.test(q)) {
      var day = todayDay();
      api("/v1/season1/eligibility/" + q + "?day=" + day).then(function (e) {
        var html = "<h3>" + esc(T("scan.aiIdTitle")) + "</h3>"
          + "<p>" + esc(T("scan.aiIdStatus")) + ": " + esc(e.status || "—") + " · " + esc(T("scan.aiIdBalance")) + ": " + esc(String(e.balance == null ? "—" : e.balance)) + "</p>"
          + '<p><a href="' + esc(base + "/v1/season1/proof/" + q + "?day=" + day) + '" target="_blank" rel="noopener noreferrer">' + esc(T("scan.aiIdProof")) + "</a></p>"
          + "<p>" + esc(T("scan.txLinkNote")) + ": " + txLink(q) + "</p>";
        searchResult(html);
      }).catch(function () {
        searchResult("<p>" + esc(T("scan.txLinkNote")) + ": " + txLink(q) + "</p>");
      });
      return;
    }
    // 纯数字：订单号 / agentId / 区块号
    if (/^[0-9]+$/.test(q)) {
      var n = parseInt(q, 10);
      var blockPart = n >= START_BLOCK
        ? "<p>" + esc(T("scan.blockLink")) + ": " + blockLink(n) + "</p>" : "";
      api("/v1/season1/orders/" + n).then(function (o) {
        var html = "<h3>" + esc(T("scan.orderTitle")) + " #" + esc(o.orderId) + "</h3>"
          + "<p>" + esc(T("scan.colApplicant")) + ": " + aiAddrLink(o.applicant) + "<br>"
          + esc(T("scan.colName")) + ": " + esc(o.label + (o.tld === 1 ? ".meme" : ".haha")) + "<br>"
          + esc(T("scan.colTier")) + ": " + esc(o.tier) + " · " + esc(T("scan.colStatus")) + ": " + esc(o.status) + "<br>"
          + esc(T("scan.colTx")) + ": " + txLink(o.mintTx || null) + "</p>" + blockPart;
        searchResult(html);
      }).catch(function () {
        /* 纯数字先是订单号；不是订单就当 agentId，直接调注册文件查。
         * 查到跳到 agent 页（name 字段）；404 明确说没有这个 agentId。 */
        api("/v1/agents/" + n + "/registration.json").then(function (reg) {
          if (reg && reg.name) {
            var go = window.hahaScanGo || function (u) { location.href = u; };
            go("/agent.html?name=" + encodeURIComponent(reg.name));
          } else {
            searchResult('<p class="note">' + esc(T("scan.agentNotFound")) + "</p>" + blockPart);
          }
        }).catch(function () {
          searchResult('<p class="note">' + esc(T("scan.agentNotFound")) + "</p>" + blockPart);
        });
      });
      return;
    }
    searchResult('<p class="note">' + esc(T("scan.errUnknown")) + "</p>");
  }

  /* ---------------- 初始化 ---------------- */
  function renderAll() {
    renderOverview();
    renderNames();
    renderEvents();
    renderAgents();
    renderPoints();
    renderMarket();
    renderSeason();
    renderContracts();
  }
  function init() {
    var form = $("scan-search-form");
    if (form) {
      form.addEventListener("submit", function (ev) {
        ev.preventDefault();
        runSearch($("scan-search-input").value);
      });
    }
    var moreNames = $("scan-names-more");
    if (moreNames) moreNames.addEventListener("click", function () { loadNames(true); });
    var moreEvents = $("scan-events-more");
    if (moreEvents) moreEvents.addEventListener("click", function () { loadEvents(true); });
    var morePoints = $("scan-points-more");
    if (morePoints) morePoints.addEventListener("click", function () { loadPoints(true); });
    var apply = $("scan-events-apply");
    if (apply) {
      apply.addEventListener("click", function () {
        var c = $("scan-filter-contract");
        var e = $("scan-filter-event");
        var a = $("scan-filter-address");
        state.events.contract = c ? c.value.trim() : "";
        state.events.event = e ? e.value.trim() : "";
        state.events.address = a ? a.value.trim() : "";
        loadEvents(false);
      });
    }
    if (window.HahaI18n && HahaI18n.onChange) {
      HahaI18n.onChange(function () { renderAll(); });
    }
    loadOverview();
    loadNames(false);
    loadEvents(false);
    loadAgents();
    loadPoints(false);
    loadMarket();
    loadSeason();
    renderContracts();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
