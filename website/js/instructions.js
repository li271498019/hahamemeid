(function () {
  /* skill 地址写死本站，不信任任何全局变量：任何先执行的脚本或恶意扩展
   * 改写 window.HAHA_SKILL_URL，也改不了指令里的说明书地址（H1）。 */
  var SKILL_URL = "https://haha.meme/skill.md";
  var MCP_URL = "https://haha.meme/mcp";
  function skillURL() {
    return SKILL_URL;
  }

  function mcpURL() {
    return MCP_URL;
  }

  window.hahaSkillURL = skillURL;

  function lang() {
    if (window.HahaI18n && HahaI18n.lang) return HahaI18n.lang();
    return (document.documentElement.dataset.lang === "en") ? "en" : "zh";
  }

  /* 中文外壳与仓库里原来的逐字相同。英文是同一套步骤。 */
  window.hahaInstruction = function (task) {
    var url = skillURL();
    if (lang() === "en") {
      return "Use my Binance Agentic Wallet for the task below.\n"
        + "First read the latest version of the operation manual: " + url + "\n"
        + "Then connect to the data source: " + mcpURL() + "\n"
        + "Following the rules in it, on BNB Chain " + task + "\n"
        + "Show me the transaction preview first, and send it only after I confirm.";
    }
    return "用我的 Binance Agentic Wallet 执行以下任务。\n"
      + "首先请阅读最新版的操作说明书：" + url + "\n"
      + "然后请连接数据源接口：" + mcpURL() + "\n"
      + "按照其中规则在BNB Chain 上" + task + "\n"
      + "先把交易预览给我看，我确认后再执行。";
  };
})();
