/* V1 正式配置：不再是预览。 */
window.HAHA_PREVIEW = false;
/* 读链走本站代理：浏览器只跟本站说话（同源，快且稳），nginx 再把请求转给 BSC 公开节点。
 * 用户网络直连各公开节点慢或失败时，查询也不用等 1 分钟；上游仍是 bsc-dataseed，
 * rpc.js 里只有 4 个节点在竞速（本站代理 + 3 个公开节点），没有测速排序和 50 节点表。 */
window.HAHA_RPC_URL = "/rpc/";
/* 按 V1-INDEXER-SPEC.md，索引器验收（health ok、10 条验收中可验项通过，2/3/7 主网部分因链上零活动暂无法验、已用夹具验证逻辑）之后设成 "/api"；列表从此走真实索引 API。 */
window.HAHA_INDEXER_BASE = "/api";
/* skill 地址已在 instructions.js 里写死为 https://haha.meme/skill.md，
 * 不再由 config 设置：任何脚本改写 window.HAHA_SKILL_URL 也覆盖不了它（H1）。
 * 这里只留展示用的 label。本地 file:// 打开时 origin 不可用，默认回正式站地址。 */
(function () {
  var origin = "";
  try { origin = (window.location && window.location.origin) || ""; } catch (err) {}
  if (origin.indexOf("http") !== 0) origin = "https://haha.meme";
  window.HAHA_SKILL_LABEL = origin.replace(/^https?:\/\//, "") + "/skill.md";
})();
