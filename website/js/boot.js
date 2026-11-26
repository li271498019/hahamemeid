/* 在画第一帧之前定语言。选择记在 localStorage，没有记录时按浏览器语言。 */
(function () {
  var stored = null;
  try { stored = localStorage.getItem("haha.lang"); } catch (err) {}
  var lang = stored;
  if (lang !== "zh" && lang !== "en") {
    var nav = (navigator.languages && navigator.languages[0]) || navigator.language || "zh";
    lang = String(nav).toLowerCase().indexOf("zh") === 0 ? "zh" : "en";
  }
  var root = document.documentElement;
  root.lang = lang === "zh" ? "zh-Hans" : "en";
  root.dataset.lang = lang;
  /* 英文页先藏起来，等文案换完再显示，避免先闪一屏中文。 */
  if (lang === "en") {
    root.setAttribute("data-i18n-pending", "1");
    /* 等 i18n.js 就绪再放行：每 100ms 查一次 booted()，就绪后由 ready() 移除属性；
     * 10 秒仍未就绪（脚本加载失败）才强制放行，避免页面永久空白。 */
    var waited = 0;
    var timer = setInterval(function () {
      waited += 100;
      if (window.HahaI18n && HahaI18n.booted && HahaI18n.booted()) {
        clearInterval(timer);
        return;
      }
      if (waited >= 10000) {
        clearInterval(timer);
        root.removeAttribute("data-i18n-pending");
      }
    }, 100);
  }
})();
