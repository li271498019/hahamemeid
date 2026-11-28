(function () {
  "use strict";

  /* 只读状态：只把本地夹具 JSON 填进元素。
   * 不计算 Merkle、不拼签名、不判断边界同分谁赢。
   * 夹具用相对路径 season/fixtures/*.json，以 fetch 读取。 */

  var BASE = "season/fixtures/";

  function $(id) { return document.getElementById(id); }

  function setText(node, v) {
    if (!node) return;
    if (v === null || v === undefined || v === "") { node.textContent = "无"; return; }
    node.textContent = String(v);
  }

  function yesNo(v) { return v ? "是" : "否"; }

  function line(label, value) {
    var p = document.createElement("p");
    var b = document.createElement("b");
    b.textContent = label + "：";
    p.appendChild(b);
    p.appendChild(document.createTextNode(value === null || value === undefined || value === "" ? "无" : String(value)));
    return p;
  }

  function caseBox() {
    var d = document.createElement("div");
    d.className = "case";
    return d;
  }

  function load(name) {
    return fetch(BASE + name).then(function (r) {
      if (!r.ok) throw new Error("http " + r.status);
      return r.json();
    });
  }

  function loadFail(container, name) {
    var box = caseBox();
    box.appendChild(line("夹具加载失败", name));
    if (container) container.appendChild(box);
  }

  /* ---- 当日快照 ---- */
  function renderDay(d, prefix) {
    if (!d) return;
    setText($(prefix + "-dayIndex"), d.dayIndex);
    setText($(prefix + "-merkleRoot"), d.merkleRoot);
    setText($(prefix + "-recomputedRoot"), d.recomputedRoot);
    setText($(prefix + "-rootMatch"), d.rootMatch === true ? "一致" : (d.rootMatch === false ? "复算不一致" : d.rootMatch));
    setText($(prefix + "-snapshotBlock"), d.snapshotBlock);
    setText($(prefix + "-snapshotBlockHash"), d.snapshotBlockHash);
    setText($(prefix + "-confirmations"), d.confirmationsRequired + "/" + d.confirmationsSeen);
    setText($(prefix + "-reservedCount"), d.reservedCount);
    setText($(prefix + "-remainingSlots"), d.remainingSlots);
    setText($(prefix + "-reservedFilled"), d.reservedFilled);
    setText($(prefix + "-boundaryFilled"), d.boundaryFilled);
    setText($(prefix + "-opened"), yesNo(d.opened));
    var slot = $(prefix + "-apply-slot");
    var note = $(prefix + "-mismatch-note");
    if (d.rootMatch === true) {
      if (slot) {
        var a = document.createElement("a");
        a.className = "btn";
        a.href = "/season-apply";
        a.textContent = "去申请";
        slot.appendChild(a);
      }
      if (note) note.hidden = true;
    } else if (d.rootMatch === false) {
      if (note) note.hidden = false;
    }
  }

  /* ---- 资格 ---- */
  function renderEligibility(data) {
    var box = $("eligibility-list");
    if (!box || !data || !data.cases) return;
    data.cases.forEach(function (c) {
      var d = caseBox();
      d.appendChild(line("情形", c.id));
      d.appendChild(line("状态", c.status));
      d.appendChild(line("原因", c.reason));
      d.appendChild(line("快照余额", c.balance));
      d.appendChild(line("当前余额", c.balanceNow));
      box.appendChild(d);
    });
  }

  /* ---- 日志核对文案 ---- */
  function logCheckText(v) {
    if (v === "matched") return "已核对";
    if (v === "mismatch") return "已声明，日志未核对";
    if (v === "unknown") return "未知";
    if (v === "not-minted") return "未铸造";
    return v;
  }

  function tldText(tld) {
    if (tld === 0 || tld === "0") return "0（.haha）";
    if (tld === 1 || tld === "1") return "1（.meme）";
    return tld;
  }

  function orderBox(o) {
    var d = caseBox();
    d.appendChild(line("订单", o.orderId));
    d.appendChild(line("aiId", o.aiId));
    d.appendChild(line("申请人", o.applicant));
    d.appendChild(line("接收人", o.recipient));
    var full = (o.label || "") + "." + (o.tld === 1 || o.tld === "1" ? "meme" : "haha");
    d.appendChild(line("名字", full));
    d.appendChild(line("tld", tldText(o.tld)));
    d.appendChild(line("档位", o.tier));
    d.appendChild(line("状态", o.status));
    d.appendChild(line("铸造交易", o.mintTx));
    d.appendChild(line("tokenId", o.tokenId));
    d.appendChild(line("模拟错误", o.simError));
    d.appendChild(line("日志核对", logCheckText(o.logCheck)));
    return d;
  }

  /* ---- 订单 ---- */
  function renderOrders(data) {
    var list = $("orders-list");
    var empty = $("orders-empty");
    if (!list || !data) return;
    var orders = data.orders || [];
    if (orders.length === 0) {
      if (empty) empty.hidden = false;
      return;
    }
    if (empty) empty.hidden = true;
    orders.forEach(function (o) { list.appendChild(orderBox(o)); });
  }

  /* ---- 订单日志未核对示例 ---- */
  function renderOrderMismatch(o) {
    var box = $("order-mm");
    if (!box || !o) return;
    box.appendChild(orderBox(o));
  }

  /* ---- 每日验证 ---- */
  function renderVerify(data) {
    var box = $("verify-list");
    if (!box || !data || !data.cases) return;
    data.cases.forEach(function (c) {
      var d = caseBox();
      d.appendChild(line("情形", c.id));
      d.appendChild(line("已领", c.claimed ? "已领" : "未领"));
      d.appendChild(line("taskPackHash", c.taskPackHash));
      d.appendChild(line("verdict", c.verdict));
      d.appendChild(line("积分", c.points));
      if (c.queue) {
        d.appendChild(line("排队", c.queue === "global-cap" ? "global-cap（全网 100000 用尽）" : c.queue));
      }
      box.appendChild(d);
    });
  }

  /* ---- 找错公示 ---- */
  function renderFinding(data) {
    var box = $("finding-list");
    if (!box || !data || !data.cases) return;
    data.cases.forEach(function (c) {
      var d = caseBox();
      d.appendChild(line("情形", c.id));
      d.appendChild(line("reportEvidenceHash", c.reportEvidenceHash));
      if (c.withheld === true) {
        d.appendChild(line("扣留状态", "已扣留，不显示正文"));
        box.appendChild(d);
        return;
      }
      d.appendChild(line("commitBlock", c.commitBlock));
      d.appendChild(line("txIndex", c.txIndex));
      d.appendChild(line("logIndex", c.logIndex));
      d.appendChild(line("canonicalAssigned", yesNo(c.canonicalAssigned)));
      d.appendChild(line("canonicalPaid", yesNo(c.canonicalPaid)));
      box.appendChild(d);
    });
  }

  /* ---- 空态与错误态示例：只用 empty-orders 与 unknown-order ---- */
  function renderFailures(data) {
    var box = $("failures-demo");
    if (!box || !data || !data.cases) return;
    data.cases.forEach(function (c) {
      if (c.id === "empty-orders") {
        var e = caseBox();
        e.appendChild(line("情形", "empty-orders（HTTP 200，orders 为空数组）"));
        e.appendChild(line("空态", "暂无订单"));
        box.appendChild(e);
      } else if (c.id === "unknown-order") {
        var u = caseBox();
        u.appendChild(line("情形", "unknown-order（HTTP 404，error 为 not_found）"));
        u.appendChild(line("错误", "没有这笔订单"));
        box.appendChild(u);
      }
    });
  }

  load("day.json").then(function (d) { renderDay(d, "day"); }).catch(function () { loadFail($("season-status"), "day.json"); });
  load("day-mismatch.json").then(function (d) { renderDay(d, "daymm"); }).catch(function () { loadFail($("season-status"), "day-mismatch.json"); });
  load("eligibility.json").then(renderEligibility).catch(function () { loadFail($("eligibility-list"), "eligibility.json"); });
  load("orders.json").then(renderOrders).catch(function () { loadFail($("orders-list"), "orders.json"); });
  load("order-log-mismatch.json").then(renderOrderMismatch).catch(function () { loadFail($("order-mm"), "order-log-mismatch.json"); });
  load("verify.json").then(renderVerify).catch(function () { loadFail($("verify-list"), "verify.json"); });
  load("finding.json").then(renderFinding).catch(function () { loadFail($("finding-list"), "finding.json"); });
  load("failures.json").then(renderFailures).catch(function () { loadFail($("failures-demo"), "failures.json"); });
})();
