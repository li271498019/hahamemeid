(function () {
  var KEY = "haha.session.v1";
  var POINTS_KEY = "haha.points.v1";
  var listeners = [];

  var AI_RE = /^[a-z0-9]{3,32}$/;
  var ADDR_RE = /^0x[0-9a-fA-F]{40}$/;

  /* 读回的 session 必须通过格式校验，否则视为未登录（H3）：
   * ai 只认 [a-z0-9]{3,32}，address 只认 0x + 40 位 hex。localStorage
   * 可被任意页面脚本/扩展写入，里面的 address 不能直接信任。 */
  function valid(data) {
    if (!data || typeof data !== "object") return false;
    if (!AI_RE.test(String(data.ai || ""))) return false;
    if (data.address != null && data.address !== "" && !ADDR_RE.test(String(data.address))) return false;
    return true;
  }

  function read() {
    try {
      var raw = localStorage.getItem(KEY);
      if (raw === null) return null;
      var data = JSON.parse(raw);
      return valid(data) ? data : null;
    } catch (err) { return null; }
  }

  function write(data) {
    try { localStorage.setItem(KEY, JSON.stringify(data)); } catch (err) {}
    listeners.forEach(function (fn) { fn(data); });
  }

  function clean(raw) {
    return String(raw || "").toLowerCase().replace(/[^a-z0-9]/g, "").slice(0, 32);
  }

  window.HahaSession = {
    get: read,
    clean: clean,
    login: function (raw) {
      var name = clean(raw);
      if (name.length < 3) return null;
      var data = { ai: name };
      write(data);
      return data;
    },
    setAddress: function (addr) {
      /* 写之前先校验地址格式：非法地址不写入、不覆盖旧值（H3）。 */
      if (!ADDR_RE.test(String(addr || ""))) return null;
      var data = read();
      if (!data) return null;
      data.address = addr;
      write(data);
      return data;
    },
    logout: function () {
      write(null);
      /* 积分是全站一份缓存。退出时清掉，避免下一位登录者先看到别人的数字。 */
      try { localStorage.removeItem(POINTS_KEY); } catch (err) {}
    },
    setPoints: function (n) {
      try { localStorage.setItem(POINTS_KEY, String(Number(n) || 0)); } catch (err) {}
    },
    getPoints: function () {
      try {
        var raw = localStorage.getItem(POINTS_KEY);
        return raw === null ? 0 : (Number(raw) || 0);
      } catch (err) { return 0; }
    },
    points: function () {
      return window.HahaSession.getPoints();
    },
    onChange: function (fn) { listeners.push(fn); }
  };
})();
