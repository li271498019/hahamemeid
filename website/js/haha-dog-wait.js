/* Haha Dog placeholder for a dog whose image is not drawn yet (status 0 / 1 / 3 or no seed).
 * Shows the same "Haha AI latent interpolation" animation as ai.html, pre-rendered once as a 96x96 GIF
 * (/assets/dog/unrendered.gif, 26 KB, one cached file for every card), with a "未出图" label on top.
 * prefers-reduced-motion gets the first frame as a still PNG. HahaDogWait.html(stalled): stalled = status 3,
 * which adds the reroll hint; otherwise the "about 4 blocks" hint. Needs HahaI18n (haha-dog-i18n.js). */
(function () {
  "use strict";
  var GIF = "/assets/dog/unrendered.gif?v=1", PNG = "/assets/dog/unrendered-static.png?v=1";
  function T(k) { return window.HahaI18n ? HahaI18n.t(k) : k; }
  function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
  window.HahaDogWait = {
    html: function (stalled) {
      var label = T("dog.unrendered"), hint = T(stalled ? "dog.stalledShort" : "dog.waitShort");
      return '<div class="dog-wait" role="img" aria-label="' + esc(label + " · " + hint) + '">'
        + '<picture><source media="(prefers-reduced-motion: reduce)" srcset="' + PNG + '">'
        + '<img src="' + GIF + '" alt="" width="96" height="96" decoding="async"></picture>'
        + '<div class="dog-wait-tag"><b>' + esc(label) + "</b><span>" + esc(hint) + "</span></div></div>";
    }
  };
})();
