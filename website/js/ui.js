(function () {
  var toastEl = document.getElementById("toast");
  var toastTimer = 0;
  var addrRestoreTried = false;

  function tr(key, fallback) {
    if (window.HahaI18n && HahaI18n.t) return HahaI18n.t(key);
    return fallback;
  }

  function toast(msg) {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.classList.remove("show"); }, 1600);
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text).then(function () { return true; }).catch(function () { return fallback(text); });
    }
    return Promise.resolve(fallback(text));
  }

  function fallback(text) {
    var t = document.createElement("textarea");
    t.value = text;
    document.body.appendChild(t);
    t.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (err) { ok = false; }
    t.remove();
    if (!ok) toast(tr("toast.copyFail", "复制失败，请手动选择复制"));
    return ok;
  }

  function formatPoints(n) {
    var loc = (window.HahaI18n && HahaI18n.lang && HahaI18n.lang() === "en") ? "en-US" : "zh-Hans";
    return Number(n || 0).toLocaleString(loc);
  }

  function resolveAiWithRetry(name, left) {
    return window.HahaRPC.resolveAi(name).catch(function () { return null; }).then(function (address) {
      if (address) return address;
      if (left <= 0) return null;
      return new Promise(function (resolve) {
        setTimeout(function () { resolveAiWithRetry(name, left - 1).then(resolve); }, 800);
      });
    });
  }

  function paintSession() {
    var data = window.HahaSession.get();
    var hello = document.getElementById("hello");
    var helloName = document.getElementById("hello-name");
    var loginField = document.querySelector(".login-field");
    /* 登录态是全局的：存在 localStorage 里，8 页共用同一份。登录后导航栏显示 Hi! xxx.ai，
     * 输入框收起来，只留退出按钮；退出后恢复输入框。 */
    if (hello) hello.hidden = !data;
    if (helloName && data) helloName.textContent = data.ai + ".ai";
    if (loginField) loginField.hidden = !!data;
    /* 刷新后恢复：如果只有 ai 没有 address（比如旧版本存的），静默补回 address；
     * RPC 一时失败也不掉登录，登录态只由用户点退出清除。 */
    if (data && data.ai && !data.address && !addrRestoreTried) {
      addrRestoreTried = true;
      if (window.HahaRPC && window.HahaRPC.resolveAi) {
        window.HahaRPC.resolveAi(data.ai).then(function (addr) {
          if (addr) window.HahaSession.setAddress(addr);
        }).catch(function () {});
      }
    }
    var points = document.getElementById("points");
    var num = document.getElementById("points-num");
    var input = document.getElementById("ai");
    var btn = document.getElementById("login-btn");
    if (points) points.hidden = !data;
    if (num && data) {
      num.textContent = formatPoints(window.HahaSession.points());
      if (data.address && window.HahaRPC && window.HahaRPC.statusOf) {
        window.HahaRPC.statusOf(data.address).then(function (status) {
          if (!status) {
          num.title = tr("toast.chain", "链上数据暂时读不到");
          return;
        }
        num.title = "";
        window.HahaSession.setPoints(status.balance);
        num.textContent = formatPoints(status.balance);
      }).catch(function () {
        num.title = tr("toast.chain", "链上数据暂时读不到");
      });
      }
    }
    if (btn) btn.textContent = data ? tr("nav.exit", "退出") : tr("nav.enter", "进入");
    if (input && data && document.activeElement !== input) input.value = data.ai;
    document.querySelectorAll("[data-needs-login]").forEach(function (el) {
      el.hidden = !data;
    });
    document.querySelectorAll("[data-needs-guest]").forEach(function (el) {
      el.hidden = !!data;
    });
    if (window.hahaOnSession) window.hahaOnSession(data);
  }

  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-copy]");
    if (!btn) return;
    var text = btn.getAttribute("data-copy");
    copyText(text).then(function (ok) {
      if (ok === false) return;
      var prev = btn.textContent;
      btn.textContent = tr("toast.copied", "已复制");
      toast(tr("toast.instruction", "指令已复制"));
      setTimeout(function () { btn.textContent = prev; }, 1200);
    });
  });

  var form = document.getElementById("login-form");
  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var data = window.HahaSession.get();
      if (data) {
        window.HahaSession.logout();
        var input = document.getElementById("ai");
        if (input) input.value = "";
        toast(tr("toast.logout", "已退出登录"));
        paintSession();
        return;
      }
      var name = window.HahaSession.clean(document.getElementById("ai").value);
      document.getElementById("ai").value = name;
      if (name.length < 3) {
        toast(tr("toast.short", "先输入 3 位以上的 .ai 名字"));
        return;
      }
      if (!window.HahaRPC || !window.HahaRPC.resolveAi) {
        toast(tr("toast.chain", "链上数据暂时读不到"));
        return;
      }
      /* 公开 RPC 偶尔抽风，登录校验失败时 800ms 后重试一次再判，避免把“链上没有”误判给用户。 */
      resolveAiWithRetry(name, 1).then(function (address) {
        if (!address) {
          toast(tr("toast.noAi", "这个 .ai 名字链上没有"));
          return;
        }
        window.HahaSession.login(name);
        window.HahaSession.setAddress(address);
        toast(tr("toast.login", "登录成功"));
        paintSession();
      }).catch(function () {
        toast(tr("toast.noAi", "这个 .ai 名字链上没有"));
      });
    });
    var aiInput = document.getElementById("ai");
    if (aiInput) {
      aiInput.addEventListener("input", function () {
        var next = window.HahaSession.clean(this.value);
        if (next !== this.value) this.value = next;
      });
    }
  }

  /* 正文里的 skill 地址跟本站走：data-skill-url 的地方填本站的 skill.md 地址，两站分开。 */
  function fillSkillUrls() {
    var url = (typeof window !== "undefined" && window.HAHA_SKILL_URL) || "https://haha.meme/skill.md";
    document.querySelectorAll("[data-skill-url]").forEach(function (el) {
      el.textContent = url;
    });
  }

  window.HahaUI = { toast: toast, copyText: copyText, formatPoints: formatPoints, paintSession: paintSession };
  window.HahaSession.onChange(paintSession);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", paintSession);
  else paintSession();
  fillSkillUrls();
})();
