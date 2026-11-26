(function () {
  "use strict";

  /* 只读状态：已开放只来自只读接口，而且 rootMatch 与 opened
   * 必须同时为真。时间显示走 i18n：中文 UTC+8，英文 UTC。
   * 兑换申请直接嵌在本页：先查名字是否已被申请，再用登录的 .ai
   * 解析接收地址，生成并复制领取指令。 */

  function $(id) { return document.getElementById(id); }

  var ZH_FALLBACK = {
    "season.statusOpen": "状态：当天兑换已开放",
    "season.statusClosed": "状态：尚未开放",
    "season.statusLoading": "状态：正在读取…",
    "season.countdownOver": "申请窗口已过北京时间 2026-12-09 08:00。页面不会自行改成已开放。",
    "season.noteLoading": "正在读取开放记录。读不到或没有根时，保持尚未开放。",
    "season.noteNoRecord": "接口没有返回已开放的当天记录。",
    "season.noteFetchFail": "读不到开放记录，或这一天还没有根。按尚未开放处理，不会显示已开放。",
    "season.noteOpen": "输入两位名字，选后缀，点复制领取指令。",
    "season.applyLabel": "两位名字",
    "season.applyTld": "后缀",
    "season.applyCopy": "复制领取指令",
    "season.applyNeedLogin": "请先用 .ai 登录，再领取指令。",
    "season.applyInvalid": "名字填 2 位小写字母或数字。",
    "season.applyChecking": "正在查这个名字…",
    "season.applyTaken": "这个名字已经被申请了。",
    "season.applyAvailable": "这个名字可以申请，点复制领取指令。",
    "season.applyCheckFail": "查不到这个名字，先确认网络再试。",
    "season.applyResolveFail": "解析 .ai 地址失败，请稍后再试。",
    "season.applyAddrMismatch": "本地保存的地址与链上解析不一致，已按链上地址为准，请重新点复制领取指令。",
    "season.applyCopied": "指令已复制，交给你的 agent 执行。",
    "season.applyCopyFail": "复制失败，请手动选中框里的指令复制。",
    "season.findingsTitle": "找错公示",
    "season.findingsIntro": "为保证积分兑换2位纯字母域名活动公开公正透明，欢迎监督找错，一经核实，奖励100积分！",
    "season.findingsLoading": "正在读取找错公示…",
    "season.findingsCopy": "复制找错指令",
    "season.findingsFlow": "提交 → 7 天内向复核人揭示 → 指定根因公示 24 小时 → 凭签名领 100 分。",
    "season.findingsLoadFail": "找错公示读不到，稍后再试。",
    "season.findingsEmpty": "暂无找错提交，欢迎监督。",
    "season.findingsColReport": "报告",
    "season.findingsColSubmitter": "提交人",
    "season.findingsColTime": "提交时间",
    "season.findingsColContent": "报告内容",
    "season.findingsColAdopted": "是否采纳",
    "season.findingsColReward": "奖励积分",
    "season.findingsColReason": "理由",
    "season.findingsAdopted": "采纳",
    "season.findingsRejected": "不采纳",
    "season.findingsPending": "待审核",
    "season.findingsPendingPublic": "待公示",
    "season.findingsPendingReward": "待定",
    "season.findingsPendingReason": "待复核",
    "season.findingsRewardPaid": "100 已发放",
    "season.findingsRewardUnpaid": "100 待领取",
    "season.findingsExpand": "展开全文",
    "season.findingsCollapse": "收起",
    "season.issuedLoading": "正在读取发放数…",
    "season.issuedLine": "第一季已发放 {x} / 300",
    "season.todayDone": "今日 08:00 已完成：快照、发根、发任务包",
    "season.todayRoot": "当天根",
    "season.rootCheck": "根校验",
    "season.rootMatchYes": "根一致",
    "season.rootMatchNo": "根不一致",
    "season.taskpackHash": "任务包哈希",
    "season.eligTitle": "查兑换资格",
    "season.eligAiPh": "比如 hahameme",
    "season.eligCheck": "查资格",
    "season.eligChecking": "正在查资格…",
    "season.eligNeedAi": "先输入 .ai 名字，或先登录",
    "season.eligFail": "资格查不到，稍后再试",
    "season.eligReserved": "有资格：前 20 名",
    "season.eligBoundary": "有资格：同分边界",
    "season.eligExcluded": "没资格",
    "season.eligReasonPending": "已有待处理兑换单",
    "season.eligReasonFulfilled": "本季已兑换过",
    "season.eligReasonBelow": "积分不够前 20 名",
    "season.eligBalance": "快照积分 {balance}，当前积分 {balanceNow}",
    "season.proofBtn": "查看 Merkle 证明",
    "season.proofTitle": "Merkle 证明",
    "season.proofBalance": "余额 {balance}",
    "season.proofTier": "等级 {tier}",
    "season.proofRoot": "根 {root}",
    "season.proofCopy": "复制证明",
    "season.proofCopied": "证明已复制",
    "season.proofFail": "证明查不到，稍后再试",
    "season.verifyLink": "每日验证在赚取页领 30 分",
    "season.claimCol": "领奖",
    "season.claimBtn": "领奖",
    "season.claimSaltPh": "提交时用的 salt（0x + 64 位）",
    "season.claimSaltNeed": "填当初提交时用的 salt",
    "season.claimSaltInvalid": "salt 格式不对：0x 开头、共 66 位",
    "season.claimCopy": "复制领奖指令",
    "season.claimCopied": "领奖指令已复制，交给你的 agent 执行",
    "season.refundTitle": "事故退款领取",
    "season.refundIntro": "兑换因不可抗力没发放成功，可领回 200 积分并另加 100 分补偿。输入订单号查状态。",
    "season.refundOrderPh": "订单号，比如 1",
    "season.refundCheck": "查订单",
    "season.refundChecking": "正在查订单…",
    "season.refundInvalid": "订单号是数字",
    "season.refundNotFound": "没有这个订单",
    "season.refundFail": "订单查不到，稍后再试",
    "season.refundStatus": "订单 {orderId}：{status}",
    "season.refundCreditOpen": "待领 200 + 100 积分",
    "season.refundAccident": "待领 100 积分",
    "season.refundClaim": "复制领取退款指令",
    "season.refundNotClaimable": "这个订单现在不能领退款"
  };

  function t(key) {
    if (window.HahaI18n && HahaI18n.t) {
      var v = HahaI18n.t(key);
      if (v) return v;
    }
    return ZH_FALLBACK[key] || "";
  }

  function fill(key, vars) {
    if (window.HahaI18n && HahaI18n.fill) return HahaI18n.fill(key, vars);
    var s = t(key);
    return s.replace(/\{(\w+)\}/g, function (_, name) {
      return vars && vars[name] != null ? String(vars[name]) : "";
    });
  }

  var DAY1_BOUNDARY = 1795478400;
  var SEASON_END = 1796774400;

  /* 申请倒计时：数到当天窗口结束（(dayIndex+1)*86400，北京时间次日 08:00）。 */
  var applyCountdownDay = null;
  function fmtCountdown(sec) {
    if (sec < 0) sec = 0;
    var h = Math.floor(sec / 3600);
    var m = Math.floor((sec % 3600) / 60);
    var ss = sec % 60;
    function pad(n) { return (n < 10 ? "0" : "") + n; }
    return pad(h) + ":" + pad(m) + ":" + pad(ss);
  }
  function renderApplyCountdown() {
    var el = $("season-apply-countdown");
    if (!el) return;
    var day = applyCountdownDay || dayToAsk(Math.floor(Date.now() / 1000));
    var remain = (day + 1) * 86400 - Math.floor(Date.now() / 1000);
    el.textContent = fmtCountdown(remain);
  }

  function renderClock() {
    renderApplyCountdown();
    var clock = $("beijing-now");
    var el = $("countdown");
    var now = Math.floor(Date.now() / 1000);
    if (clock) {
      if (window.HahaI18n && HahaI18n.formatTime) {
        clock.textContent = HahaI18n.formatTime(Date.now());
      } else {
        clock.textContent = "";
      }
    }
    if (!el) return;
    if (now < SEASON_END) {
      el.hidden = true;
      el.textContent = "";
    } else {
      el.hidden = false;
      el.textContent = t("season.countdownOver");
    }
  }
  renderClock();
  setInterval(renderClock, 1000);

  function dayToAsk(now) {
    if (now < DAY1_BOUNDARY || now >= SEASON_END) return 20781;
    var day = Math.floor(now / 86400);
    if (day < 20781 || day > 20795) return 20781;
    return day;
  }

  /* 开放状态与申请提示存在这里，语言切换时按当前语言重渲染。 */
  var liveState = "loading";
  var liveMsgKey = "season.noteLoading";
  var liveDayIndex = null;
  var applyMsgKey = null;

  function renderLive() {
    var state = $("season-open-state");
    var note = $("season-cta-note");
    var form = $("season-apply-form");
    var open = liveState === "open";
    if (state) state.textContent = t(liveState === "loading" ? "season.statusLoading" : (open ? "season.statusOpen" : "season.statusClosed"));
    if (form) form.hidden = !open;
    if (note) note.textContent = t(applyMsgKey || liveMsgKey);
  }

  function setApplyMsg(msgKey) {
    applyMsgKey = msgKey;
    renderLive();
  }

  function setClosed(msgKey) {
    liveState = "closed";
    liveMsgKey = msgKey;
    liveDayIndex = null;
    applyMsgKey = null;
    renderLive();
  }

  function loadLive() {
    var base = (window.HAHA_INDEXER_BASE || "/api").replace(/\/$/, "");
    var day = dayToAsk(Math.floor(Date.now() / 1000));
    fetch(base + "/v1/season1/days/" + day, {headers: {"accept": "application/json"}})
      .then(function (res) {
        if (!res.ok) throw new Error(String(res.status));
        return res.json();
      })
      .then(function (body) {
        if (!(body && body.rootMatch === true && body.opened === true)) {
          setClosed("season.noteNoRecord");
          return;
        }
        liveState = "open";
        liveMsgKey = "season.noteOpen";
        liveDayIndex = body.dayIndex;
        applyMsgKey = null;
        renderLive();
      })
      .catch(function () {
        setClosed("season.noteFetchFail");
      });
  }
  loadLive();

  /* ---- 内嵌兑换申请 ---- */
  function apiBase() {
    return (window.HAHA_INDEXER_BASE || "/api").replace(/\/$/, "");
  }

  function getJSON(url) {
    return fetch(url, {headers: {"accept": "application/json"}}).then(function (res) {
      if (!res.ok) throw new Error(String(res.status));
      return res.json();
    });
  }

  function cleanLabel(raw) {
    return String(raw || "").toLowerCase().replace(/[^a-z0-9]/g, "").slice(0, 2);
  }

  function currentAi() {
    try {
      var s = window.HahaSession && HahaSession.get ? HahaSession.get() : null;
      return s && s.ai ? String(s.ai) : "";
    } catch (e) { return ""; }
  }

  function currentAddress() {
    try {
      var s = window.HahaSession && HahaSession.get ? HahaSession.get() : null;
      return s && s.address ? String(s.address) : "";
    } catch (e) { return ""; }
  }

  /* 兑换 recipient 不信任 localStorage（H3）：每次复制指令前都用
   * HahaRPC.resolveAi(ai) 重新链上解析并与本地存的 address 比对。
   * 本地没存就按链上结果存一份；不一致则以链上为准、纠正本地记录，
   * 并报错（这次不生成指令，用户重新点一次即可正常复制）。 */
  function resolveRecipient() {
    var ai = currentAi();
    if (!ai || !window.HahaRPC || !HahaRPC.resolveAi) return Promise.resolve("");
    var stored = currentAddress();
    return HahaRPC.resolveAi(ai).catch(function () { return null; }).then(function (onchain) {
      if (!onchain || !/^0x[0-9a-fA-F]{40}$/.test(String(onchain))) return "";
      onchain = String(onchain);
      if (stored && stored.toLowerCase() !== onchain.toLowerCase()) {
        try { if (window.HahaSession && HahaSession.setAddress) HahaSession.setAddress(onchain); } catch (e) {}
        var err = new Error("stored address does not match on-chain resolveAi");
        err.code = "addrMismatch";
        throw err;
      }
      if (!stored) {
        try { if (window.HahaSession && HahaSession.setAddress) HahaSession.setAddress(onchain); } catch (e) {}
      }
      return onchain;
    });
  }

  /* 已铸走，或当天已有待处理兑换单，都算已被申请。 */
  function isTaken(label, tld) {
    var suffix = tld === 1 ? "meme" : "haha";
    var day = liveDayIndex || dayToAsk(Math.floor(Date.now() / 1000));
    return getJSON(apiBase() + "/v1/names/" + encodeURIComponent(label + "." + suffix)).then(function (body) {
      if (body && body.minted === true) return true;
      return getJSON(apiBase() + "/v1/season1/orders?day=" + day).then(function (ob) {
        var orders = (ob && ob.orders) || [];
        for (var i = 0; i < orders.length; i++) {
          var o = orders[i];
          if (o && String(o.label || "").toLowerCase() === label &&
              Number(o.tld) === tld && o.status === "Pending") return true;
        }
        return false;
      });
    });
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text).then(function () { return true; }, function () { return false; });
    }
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try { ok = !!document.execCommand("copy"); } catch (e) { ok = false; }
    document.body.removeChild(ta);
    return Promise.resolve(ok);
  }

  /* 输入满 2 位就自动查名字，不用等点复制指令。防抖 400ms，
   * 序号 guard 防止旧请求的结果覆盖新输入。 */
  var availSeq = 0;
  var availTimer = null;
  function checkAvailability() {
    if (liveState !== "open") return;
    var labelEl = $("apply-label");
    var label = cleanLabel(labelEl ? labelEl.value : "");
    if (label.length !== 2) {
      availSeq++;
      applyMsgKey = null;
      renderLive();
      return;
    }
    var seq = ++availSeq;
    var tld = selectedTld === 1 ? 1 : 0;
    setApplyMsg("season.applyChecking");
    isTaken(label, tld).then(function (taken) {
      if (seq !== availSeq) return;
      setApplyMsg(taken ? "season.applyTaken" : "season.applyAvailable");
    }).catch(function () {
      if (seq !== availSeq) return;
      setApplyMsg("season.applyCheckFail");
    });
  }
  function scheduleAvailabilityCheck() {
    if (availTimer) clearTimeout(availTimer);
    availTimer = setTimeout(checkAvailability, 400);
  }

  function onApplySubmit(event) {
    event.preventDefault();
    if (liveState !== "open") return;
    var labelEl = $("apply-label");
    var label = cleanLabel(labelEl ? labelEl.value : "");
    if (label.length !== 2) { setApplyMsg("season.applyInvalid"); return; }
    var tld = selectedTld === 1 ? 1 : 0;
    if (!currentAi()) { setApplyMsg("season.applyNeedLogin"); return; }
    setApplyMsg("season.applyChecking");
    resolveRecipient().then(function (recipient) {
      if (!recipient) { setApplyMsg("season.applyResolveFail"); return; }
      return isTaken(label, tld).then(function (taken) {
        if (taken) { setApplyMsg("season.applyTaken"); return; }
        var suffix = tld === 1 ? ".meme" : ".haha";
        var day = liveDayIndex || dayToAsk(Math.floor(Date.now() / 1000));
        var task = fill("season.instruction", { name: label + suffix, recipient: recipient, dayIndex: day, label: label, tld: tld });
        var text = (window.hahaInstruction ? hahaInstruction(task) : task);
        return copyText(text).then(function (ok) {
          setApplyMsg(ok ? "season.applyCopied" : "season.applyCopyFail");
        });
      });
    }).catch(function (err) {
      setApplyMsg(err && err.code === "addrMismatch" ? "season.applyAddrMismatch" : "season.applyCheckFail");
    });
  }

  /* 后缀改成点击选择：两个按钮，点哪个亮哪个。 */
  var selectedTld = 0;
  function paintTld() {
    var btns = document.querySelectorAll("#apply-tld button[data-tld]");
    for (var i = 0; i < btns.length; i++) {
      var b = btns[i];
      b.setAttribute("aria-pressed", Number(b.getAttribute("data-tld")) === selectedTld ? "true" : "false");
    }
  }
  (function () {
    var btns = document.querySelectorAll("#apply-tld button[data-tld]");
    for (var i = 0; i < btns.length; i++) {
      btns[i].addEventListener("click", function () {
        selectedTld = Number(this.getAttribute("data-tld")) === 1 ? 1 : 0;
        paintTld();
        scheduleAvailabilityCheck();
      });
    }
    paintTld();
  })();

  var form = $("season-apply-form");
  if (form) form.addEventListener("submit", onApplySubmit);
  var labelBox = $("apply-label");
  if (labelBox) labelBox.addEventListener("input", scheduleAvailabilityCheck);

  /* ---- 今日数据：快照 + 逐人榜单 ---- */
  function esc(v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c];
    });
  }

  function shortHash(h) {
    if (!h) return "";
    var s = String(h);
    if (s.length <= 16) return s;
    return s.slice(0, 8) + "\u2026" + s.slice(-6);
  }

  function txLink(h) {
    if (!h) return "";
    return '<a href="https://bscscan.com/tx/' + esc(h) + '" target="_blank" rel="noopener noreferrer" title="' + esc(h) + '">' + esc(shortHash(h)) + "</a>";
  }

  function renderToday(dayBody, lbBody) {
    var host = $("season-today-body");
    if (!host) return;
    var dayIndex = (lbBody && lbBody.dayIndex) || dayToAsk(Math.floor(Date.now() / 1000));
    var dayNum = dayIndex - 20780;
    applyCountdownDay = dayIndex;
    var titleEl = $("season-today-title");
    if (titleEl) titleEl.textContent = fill("season.dayTitle", { day: dayNum });
    var html = "";
    if (dayBody) {
      if (dayBody.rootMatch === true && dayBody.opened === true) {
        html += '<p class="note">' + esc(t("season.todayDone")) + "</p>";
      }
      html += '<div class="today-grid">'
        + "<div><b>" + esc(t("season.snapBlock")) + "</b><span>" + esc(dayBody.snapshotBlock) + "</span></div>"
        + "<div><b>" + esc(t("season.snapReserved")) + "</b><span>" + esc(dayBody.reservedCount) + " / 20</span></div>"
        + "<div><b>" + esc(t("season.snapCountdown")) + "</b><span id=\"season-apply-countdown\">--:--:--</span></div>"
        + "</div>";
      /* 当天根 + 根校验 + 任务包哈希。任务包哈希不在 days 接口里，
       * 从链上 taskPack(dayIndex) 读，读不到留空。 */
      html += '<div class="today-grid">'
        + "<div><b>" + esc(t("season.todayRoot")) + "</b><span>" + esc(shortHash(dayBody.merkleRoot)) + "</span></div>"
        + "<div><b>" + esc(t("season.rootCheck")) + "</b><span>" + esc(dayBody.rootMatch === true ? t("season.rootMatchYes") : t("season.rootMatchNo")) + "</span></div>"
        + "<div><b>" + esc(t("season.taskpackHash")) + "</b><span id=\"season-today-taskpack\">—</span></div>"
        + "</div>";
    }
    html += "<h3>" + esc(t("season.lbTitle")) + "</h3>";
    var entries = (lbBody && lbBody.entries) || [];
    if (!entries.length) {
      html += '<p class="note">' + esc(t("season.lbEmpty")) + "</p>";
    } else {
      var invalidCount = 0;
      html += '<div class="lb-scroll"><table><thead><tr>'
        + "<th>" + esc(t("season.lbRank")) + "</th>"
        + "<th>" + esc(t("season.lbAi")) + "</th>"
        + "<th>" + esc(t("season.lbName")) + "</th>"
        + "<th>" + esc(t("season.lbBalance")) + "</th>"
        + "<th>" + esc(t("season.lbApplied")) + "</th>"
        + "<th>" + esc(t("season.lbApplyTx")) + "</th>"
        + "<th>" + esc(t("season.lbSpent")) + "</th>"
        + "<th>" + esc(t("season.lbSpendTx")) + "</th>"
        + "<th>" + esc(t("season.lbIssued")) + "</th>"
        + "<th>" + esc(t("season.lbMintTx")) + "</th>"
        + "</tr></thead><tbody>";
      for (var i = 0; i < entries.length; i++) {
        var e = entries[i];
        var valid = e.valid !== false;
        if (!valid) invalidCount++;
        var applied = !!e.appliedName;
        var issued = "";
        if (!valid) issued = t("season.lbInvalid");
        else if (e.issued) issued = t("season.issuedYes");
        else if (applied) issued = t("season.issuedNo");
        else issued = t("season.lbNotApplied");
        html += '<tr' + (valid ? "" : ' class="invalid"') + "><td>" + esc(valid ? e.rank : "\u2014") + "</td>"
          + "<td>" + esc(valid ? (e.handle ? e.handle + ".ai" : "") : t("season.lbInvalid")) + "</td>"
          + "<td>" + esc(valid ? (e.name || "") : "") + "</td>"
          + "<td>" + esc(valid ? e.balance : "\u2014") + "</td>"
          + "<td>" + esc(e.appliedName || "") + "</td>"
          + "<td>" + (applied ? txLink(e.applyTx) : "") + "</td>"
          + "<td>" + (applied ? esc(e.pointsSpent) : "") + "</td>"
          + "<td>" + (applied ? txLink(e.spendTx) : "") + "</td>"
          + "<td>" + esc(issued) + "</td>"
          + "<td>" + (e.mintTx ? txLink(e.mintTx) : "") + "</td></tr>";
      }
      html += "</tbody></table></div>";
      if (invalidCount > 0) {
        html += '<p class="note">' + esc(fill("season.lbInvalidNote", { n: invalidCount })) + "</p>";
      }
    }
    host.innerHTML = html;
    renderApplyCountdown();
    fillTaskpack(dayIndex);
  }

  /* 任务包哈希：链上 taskPack(dayIndex) 读，读不到留空。 */
  function fillTaskpack(dayIndex) {
    var el = $("season-today-taskpack");
    if (!el) return;
    if (!window.HahaRPC || typeof HahaRPC.taskPackHash !== "function") return;
    HahaRPC.taskPackHash(dayIndex).then(function (h) {
      var cur = $("season-today-taskpack");
      if (!cur) return;
      if (h && /^0x[0-9a-fA-F]{64}$/.test(String(h))) cur.textContent = shortHash(h);
    }).catch(function () {});
  }

  /* 头部“第一季已发放 X / 300”：与首页数据条同一数。按天查
   * /v1/season1/orders，数 status 为 Fulfilled 的单。 */
  function loadIssued() {
    var el = $("season-issued");
    if (!el) return;
    var today = dayToAsk(Math.floor(Date.now() / 1000));
    var days = [];
    for (var d = 20781; d <= today; d++) days.push(d);
    Promise.all(days.map(function (d) {
      return getJSON(apiBase() + "/v1/season1/orders?day=" + d).catch(function () { return null; });
    })).then(function (parts) {
      var n = 0;
      for (var i = 0; i < parts.length; i++) {
        var orders = (parts[i] && parts[i].orders) || [];
        for (var j = 0; j < orders.length; j++) {
          if (orders[j] && orders[j].status === "Fulfilled") n++;
        }
      }
      el.textContent = fill("season.issuedLine", { x: n });
    }).catch(function () {});
  }
  loadIssued();

  function loadToday() {
    var host = $("season-today-body");
    if (!host) return;
    var day = dayToAsk(Math.floor(Date.now() / 1000));
    var base = apiBase();
    Promise.all([
      getJSON(base + "/v1/season1/days/" + day).catch(function () { return null; }),
      getJSON(base + "/v1/season1/leaderboard/" + day).catch(function () { return null; })
    ]).then(function (parts) {
      if (!parts[0] && !parts[1]) {
        host.innerHTML = '<p class="note">' + esc(t("season.todayFail")) + "</p>";
        return;
      }
      renderToday(parts[0], parts[1]);
    });
  }
  loadToday();

  /* ---- 找错公示：索引器列表 + 公开数据文件，按证据哈希合并 ---- */
  function onFindingsCopy() {
    var task = "";
    if (window.HahaI18n && typeof HahaI18n.task === "function") task = HahaI18n.task("finding");
    if (!task) task = t("task.finding");
    var text = (window.hahaInstruction ? hahaInstruction(task) : task);
    copyText(text).then(function (ok) {
      var note = $("findings-note");
      if (note) {
        note.hidden = false;
        note.textContent = t(ok ? "season.applyCopied" : "season.applyCopyFail");
      }
    });
  }

  function renderFindings(findings, pub) {
    var host = $("season-findings-body");
    if (!host) return;
    if (!findings || !findings.length) {
      host.innerHTML = '<p class="note">' + esc(t("season.findingsEmpty")) + "</p>";
      return;
    }
    var html = '<div class="lb-scroll"><table><thead><tr>'
      + "<th>" + esc(t("season.findingsColReport")) + "</th>"
      + "<th>" + esc(t("season.findingsColSubmitter")) + "</th>"
      + "<th>" + esc(t("season.findingsColTime")) + "</th>"
      + "<th>" + esc(t("season.findingsColContent")) + "</th>"
      + "<th>" + esc(t("season.findingsColAdopted")) + "</th>"
      + "<th>" + esc(t("season.findingsColReward")) + "</th>"
      + "<th>" + esc(t("season.findingsColReason")) + "</th>"
      + "<th>" + esc(t("season.claimCol")) + "</th>"
      + "</tr></thead><tbody>";
    for (var i = 0; i < findings.length; i++) {
      var f = findings[i];
      var key = String(f.reportEvidenceHash || "").toLowerCase();
      var p = (pub && pub[key]) || null;
      /* 证据哈希是找错的标识，只显示缩短文本（全哈希放 title 里）；
         BscScan 链接指向真正的提交交易 commitTx——证据哈希本身不是
         交易哈希，链到 bscscan.com/tx/<证据哈希> 会查不到。 */
      var evText = '<span title="' + esc(f.reportEvidenceHash || "") + '">'
        + esc(shortHash(f.reportEvidenceHash)) + "</span>";
      var txPart = f.commitTx ? "<br>" + txLink(f.commitTx) : "";
      /* 报告正文优先用接口（提交者自己发布，服务器验过哈希）；
         接口没有才用 findings.json；reportId 同样接口优先。 */
      var reportId = f.reportId || (p && p.reportId) || null;
      var reportCell = reportId
        ? esc(reportId) + "<br>" + evText + txPart
        : evText + txPart;
      /* 提交人只显示 .ai，不显示钱包地址。 */
      var submitter = f.handle ? esc(f.handle + ".ai") : "";
      var timeCell = "";
      if (f.commitTime) {
        timeCell = (window.HahaI18n && HahaI18n.formatTime)
          ? esc(HahaI18n.formatTime(f.commitTime * 1000))
          : esc(f.commitTime);
      }
      var contentCell;
      if (f.reportContent) {
        contentCell = esc(f.reportTitle || "")
          + ' <button type="button" class="finding-toggle" data-finding-toggle="' + i + '">' + esc(t("season.findingsExpand")) + "</button>"
          + '<div class="finding-content" data-finding-content="' + i + '" hidden>' + esc(f.reportContent) + "</div>";
      } else if (p) {
        contentCell = esc(p.title || "")
          + ' <button type="button" class="finding-toggle" data-finding-toggle="' + i + '">' + esc(t("season.findingsExpand")) + "</button>"
          + '<div class="finding-content" data-finding-content="' + i + '" hidden>' + esc(p.content || "") + "</div>";
      } else {
        contentCell = esc(t("season.findingsPendingPublic"));
      }
      var adoptedCell, adoptedCls;
      if (p) {
        if (p.adopted === true) { adoptedCell = esc(t("season.findingsAdopted")); adoptedCls = "adopted-yes"; }
        else { adoptedCell = esc(t("season.findingsRejected")); adoptedCls = "adopted-no"; }
      } else {
        adoptedCell = esc(t("season.findingsPending")); adoptedCls = "adopted-pending";
      }
      var rewardCell;
      if (p) {
        rewardCell = p.adopted === true
          ? esc(f.canonicalPaid ? t("season.findingsRewardPaid") : t("season.findingsRewardUnpaid"))
          : "0";
      } else {
        rewardCell = esc(t("season.findingsPendingReward"));
      }
      var reasonCell = p ? esc(p.reason || "") : esc(t("season.findingsPendingReason"));
      /* 领奖按钮：被采纳且未发放才出。已发放 / 不采纳 / 待审核都不出。 */
      var claimCell = "";
      if (p && p.adopted === true && f.canonicalPaid === false) {
        claimCell = '<button type="button" class="btn light" data-claim-finding="' + esc(f.reportEvidenceHash || "") + '">' + esc(t("season.claimBtn")) + "</button>";
      }
      html += "<tr><td>" + reportCell + "</td>"
        + "<td>" + submitter + "</td>"
        + "<td>" + timeCell + "</td>"
        + "<td>" + contentCell + "</td>"
        + '<td class="' + adoptedCls + '">' + adoptedCell + "</td>"
        + "<td>" + rewardCell + "</td>"
        + "<td>" + reasonCell + "</td>"
        + "<td>" + claimCell + "</td></tr>";
    }
    html += "</tbody></table></div>";
    host.innerHTML = html;
    var toggles = host.querySelectorAll("[data-finding-toggle]");
    for (var j = 0; j < toggles.length; j++) {
      toggles[j].addEventListener("click", function () {
        var idx = this.getAttribute("data-finding-toggle");
        var body = host.querySelector('[data-finding-content="' + idx + '"]');
        if (!body) return;
        var wasHidden = body.hidden;
        body.hidden = !wasHidden;
        this.textContent = t(wasHidden ? "season.findingsCollapse" : "season.findingsExpand");
      });
    }
    /* 找错领奖：点“领奖”后让提交人输当初提交时用的 salt（链上只存
     * salt 哈希，网站拿不到，只能提交人自填），再生成领奖指令。 */
    var claimBtns = host.querySelectorAll("[data-claim-finding]");
    for (var k = 0; k < claimBtns.length; k++) {
      claimBtns[k].addEventListener("click", function () {
        var hash = this.getAttribute("data-claim-finding");
        var cell = this.parentNode;
        cell.innerHTML = '<input class="field-input" data-claim-salt placeholder="' + esc(t("season.claimSaltPh")) + '" autocomplete="off" spellcheck="false">'
          + ' <button type="button" class="btn" data-claim-go>' + esc(t("season.claimCopy")) + "</button>"
          + ' <span class="note" data-claim-msg>' + esc(t("season.claimSaltNeed")) + "</span>";
        var goBtn = cell.querySelector("[data-claim-go]");
        var saltInput = cell.querySelector("[data-claim-salt]");
        var msg = cell.querySelector("[data-claim-msg]");
        goBtn.addEventListener("click", function () {
          var salt = String(saltInput.value || "").trim();
          if (!/^0x[0-9a-fA-F]{64}$/.test(salt)) { msg.textContent = t("season.claimSaltInvalid"); return; }
          var task = "";
          if (window.HahaI18n && typeof HahaI18n.task === "function") {
            try { task = HahaI18n.task("claimFinding", { reportEvidenceHash: hash, salt: salt }); } catch (err) { task = ""; }
          }
          if (!task) { msg.textContent = t("season.claimSaltInvalid"); return; }
          var text = (window.hahaInstruction ? hahaInstruction(task) : task);
          copyText(text).then(function (ok) { msg.textContent = t(ok ? "season.claimCopied" : "season.applyCopyFail"); });
        });
      });
    }
  }

  function loadFindings() {
    var host = $("season-findings-body");
    if (!host) return;
    var listP = getJSON(apiBase() + "/v1/season1/findings").catch(function () { return null; });
    var pubP = fetch("/season/findings.json", {headers: {"accept": "application/json"}}).then(function (res) {
      if (!res.ok) throw new Error(String(res.status));
      return res.json();
    }).catch(function () { return null; });
    Promise.all([listP, pubP]).then(function (parts) {
      var list = parts[0];
      if (!list || !Array.isArray(list.findings)) {
        host.innerHTML = '<p class="note">' + esc(t("season.findingsLoadFail")) + "</p>";
        return;
      }
      var pub = (parts[1] && parts[1].public) || {};
      renderFindings(list.findings, pub);
    });
  }
  loadFindings();

  var findingsCopyBtn = $("findings-copy");
  if (findingsCopyBtn) findingsCopyBtn.addEventListener("click", onFindingsCopy);

  /* ---- 查兑换资格 + Merkle 证明 ---- */
  var eligState = null; // {ai, aiId, day, body}
  var eligProof = null; // proof 接口返回体
  function cleanAi(raw) {
    return String(raw || "").toLowerCase().replace(/\.ai$/, "").replace(/[^a-z0-9]/g, "").slice(0, 32);
  }
  /* .ai 名字 → 链上地址（resolveAi）→ statusOf 的 aiId，再调资格接口。 */
  function resolveAiId(aiLabel) {
    if (!window.HahaRPC || !HahaRPC.resolveAi || !HahaRPC.statusOf) return Promise.reject(new Error("no rpc"));
    return HahaRPC.resolveAi(aiLabel).then(function (addr) {
      if (!addr) throw new Error("no address");
      return HahaRPC.statusOf(addr);
    }).then(function (st) {
      if (!st || !st.aiId) throw new Error("no aiId");
      return st.aiId;
    });
  }
  function eligDay() { return liveDayIndex || dayToAsk(Math.floor(Date.now() / 1000)); }
  function renderElig() {
    var res = $("elig-result");
    if (!res || !eligState) return;
    var body = eligState.body;
    var statusKey = body.status === "reserved" ? "season.eligReserved"
      : body.status === "boundary" ? "season.eligBoundary" : "season.eligExcluded";
    var html = "<p>" + esc(t(statusKey)) + "</p>";
    if (body.status === "excluded" && body.reason) {
      var rKey = body.reason === "pending" ? "season.eligReasonPending"
        : body.reason === "fulfilled" ? "season.eligReasonFulfilled"
        : body.reason === "below-cutoff" ? "season.eligReasonBelow" : "";
      if (rKey) html += "<p>" + esc(t(rKey)) + "</p>";
    }
    html += "<p>" + esc(fill("season.eligBalance", { balance: body.balance == null ? "—" : String(body.balance), balanceNow: body.balanceNow == null ? "—" : String(body.balanceNow) })) + "</p>";
    if (body.status === "reserved" || body.status === "boundary") {
      html += '<p><button type="button" class="btn light" id="elig-proof-btn">' + esc(t("season.proofBtn")) + "</button></p>";
    }
    res.innerHTML = html;
    var pb = $("elig-proof-btn");
    if (pb) pb.addEventListener("click", loadProof);
    renderProof();
  }
  function renderProof() {
    var box = $("elig-proof");
    if (!box) return;
    if (!eligProof) { box.innerHTML = ""; return; }
    var p = eligProof;
    box.innerHTML = "<h3>" + esc(t("season.proofTitle")) + "</h3>"
      + "<p>" + esc(fill("season.proofBalance", { balance: String(p.balance == null ? "—" : p.balance) })) + "</p>"
      + "<p>" + esc(fill("season.proofTier", { tier: String(p.tier) })) + "</p>"
      + "<p>" + esc(fill("season.proofRoot", { root: String(p.root || "") })) + "</p>"
      + '<p class="proof-lines">' + esc(JSON.stringify(p.proof || [])) + "</p>"
      + '<p><button type="button" class="btn light" id="elig-proof-copy">' + esc(t("season.proofCopy")) + "</button> <span class=\"note\" id=\"elig-proof-msg\"></span></p>";
    var cb = $("elig-proof-copy");
    if (cb) cb.addEventListener("click", function () {
      copyText(JSON.stringify(p.proof || [])).then(function (ok) {
        var m = $("elig-proof-msg");
        if (m) m.textContent = t(ok ? "season.proofCopied" : "season.applyCopyFail");
      });
    });
  }
  function loadProof() {
    if (!eligState) return;
    getJSON(apiBase() + "/v1/season1/proof/" + encodeURIComponent(eligState.aiId) + "?day=" + eligState.day).then(function (body) {
      eligProof = body;
      renderProof();
    }).catch(function () {
      var box = $("elig-proof");
      if (box) box.innerHTML = '<p class="note">' + esc(t("season.proofFail")) + "</p>";
    });
  }
  function checkElig(ai) {
    var res = $("elig-result");
    if (!ai) { if (res) res.textContent = t("season.eligNeedAi"); return; }
    if (res) res.textContent = t("season.eligChecking");
    var box = $("elig-proof");
    if (box) box.innerHTML = "";
    eligProof = null;
    var day = eligDay();
    resolveAiId(ai).then(function (aiId) {
      return getJSON(apiBase() + "/v1/season1/eligibility/" + encodeURIComponent(aiId) + "?day=" + day).then(function (body) {
        eligState = { ai: ai, aiId: aiId, day: day, body: body };
        renderElig();
      });
    }).catch(function () {
      if (res) res.textContent = t("season.eligFail");
    });
  }
  function onEligSubmit(event) {
    event.preventDefault();
    var input = $("elig-ai");
    var ai = cleanAi(input ? input.value : "") || cleanAi(currentAi());
    checkElig(ai);
  }
  (function initElig() {
    var form = $("elig-form");
    if (form) form.addEventListener("submit", onEligSubmit);
    var input = $("elig-ai");
    var ai = cleanAi(currentAi());
    if (input && ai) input.value = ai;
    /* 进页面就自动查：已登录直接查；未登录显示“先输入 .ai 名字，或先登录”，不要停在空白。 */
    checkElig(ai);
  })();

  /* ---- 事故退款领取 ---- */
  var refundState = null; // {orderId, body}
  function renderRefund() {
    var res = $("refund-result");
    if (!res || !refundState) return;
    var body = refundState.body;
    var orderId = refundState.orderId;
    var html = "<p>" + esc(fill("season.refundStatus", { orderId: String(orderId), status: String(body.status || "") })) + "</p>";
    var claimable = body.status === "CreditOpen" || body.status === "AccidentRefunded";
    if (claimable) {
      html += "<p>" + esc(t(body.status === "CreditOpen" ? "season.refundCreditOpen" : "season.refundAccident")) + "</p>"
        + '<p><button type="button" class="btn" id="refund-claim-btn">' + esc(t("season.refundClaim")) + "</button></p>";
    } else {
      html += "<p>" + esc(t("season.refundNotClaimable")) + "</p>";
    }
    res.innerHTML = html;
    var cb = $("refund-claim-btn");
    if (cb) cb.addEventListener("click", function () {
      var task = "";
      if (window.HahaI18n && typeof HahaI18n.task === "function") {
        try { task = HahaI18n.task("claimAccidentCredit", { orderId: String(orderId) }); } catch (err) { task = ""; }
      }
      if (!task) return;
      var text = (window.hahaInstruction ? hahaInstruction(task) : task);
      copyText(text).then(function (ok) {
        var m = $("refund-result");
        if (m) {
          var note = document.createElement("p");
          note.className = "note";
          note.textContent = t(ok ? "season.applyCopied" : "season.applyCopyFail");
          m.appendChild(note);
        }
      });
    });
  }
  function onRefundSubmit(event) {
    event.preventDefault();
    var input = $("refund-order");
    var raw = String(input ? input.value : "").trim();
    var res = $("refund-result");
    if (!/^\d+$/.test(raw)) { if (res) res.textContent = t("season.refundInvalid"); return; }
    if (res) res.textContent = t("season.refundChecking");
    getJSON(apiBase() + "/v1/season1/orders/" + raw).then(function (body) {
      refundState = { orderId: raw, body: body };
      renderRefund();
    }).catch(function (err) {
      if (res) res.textContent = t(err && err.message === "404" ? "season.refundNotFound" : "season.refundFail");
    });
  }
  (function initRefund() {
    var form = $("refund-form");
    if (form) form.addEventListener("submit", onRefundSubmit);
  })();

  if (window.HahaI18n && HahaI18n.onChange) {
    HahaI18n.onChange(function () {
      renderClock();
      renderLive();
      loadToday();
      loadIssued();
      loadFindings();
      if (eligState) renderElig();
      if (refundState) renderRefund();
    });
  }
})();
