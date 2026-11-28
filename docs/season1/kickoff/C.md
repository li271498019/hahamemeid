# C 的任务书

## 负责人、范围、必读

负责人：C。

范围：规则说明、提示、只读状态、窄屏、空态、错误态、手工清单。复杂兑换和验证交互不在这里。

必读：

1. [README.md](README.md)、[shared-schema.md](shared-schema.md)、[e2e.md](e2e.md)
2. [../00-parameters.md](../00-parameters.md) 的「已批准」表
3. [fixtures/README.md](fixtures/README.md)
4. 现有 `web/site/README.md`、`web/site/how.html` 的写法

`web/site/README.md` 写了 `js/mock.js`，仓库里没有这个文件。不要新建它，也不要改现有页面的数据。

## 分支

L 合并文档 PR 之后：

```sh
git fetch origin main
git checkout -b c/season1-pages origin/main
```

合并前读 `cursor/season1-d-docs-a3d0` 上的任务书和夹具。不要等 D 的合约，也不要等 A 的 API。夹具就是第一版数据。

## 可改与禁改

可改或计划新增：

- `web/site/season.html`
- `web/site/season-checklist.html`
- `web/site/js/season-status.js`
- `web/site/index.html` 里只加一个指向 `/season` 的链接

禁改：

- `src/**`、`script/**`、`test/**`、`indexer/**`、`tools/**`
- `web/site/js/config.js`、`rpc.js`、`nft.js`、`session.js` 以及其它现有脚本
- A 的 `web/site/season-apply.html`、`web/site/js/season-apply.js`
- `docs/season1/**`，包括夹具。页面读取夹具的副本时，复制到 `web/site/season/fixtures/`，内容与文档夹具字节级一致。需要改字段时停下来，不要自己改契约

## 工作包

### C-1 规则页

输入：`00`。  
输出：`web/site/season.html`。  
依赖：无。  
边界：写明 15 个窗口、北京时间 2026-11-24 08:00 到 2026-12-09 08:00、每天 20、价格 200、验证 30、找错 100、事故退 200 并另补 100。写明网站不连接钱包，用户把指令交给自己的 agent。不写 14 天，不写 100 万或 1000 万。  
验收：E15。页面文案和 `00` 一致。

### C-2 只读状态

输入：[fixtures/day.json](fixtures/day.json)、[fixtures/eligibility.json](fixtures/eligibility.json)、[fixtures/orders.json](fixtures/orders.json)、[fixtures/verify.json](fixtures/verify.json)、[fixtures/finding.json](fixtures/finding.json)。  
输出：`web/site/js/season-status.js`。它只把 JSON 填进元素，不计算 Merkle，不拼签名，不判断谁赢了边界同分。  
依赖：C-1。  
边界：`rootMatch = false` 时不显示申请按钮，只显示「复算不一致」。申请按钮的目标是 A 的 `/season-apply`，在 A 的文件落地前链接可以存在，页面其余部分仍能用夹具打开。`logCheck = mismatch` 的句子是「已声明，日志未核对」。`withheld: true` 不显示正文。`balance` 和 `balanceNow` 分两行。  
验收：E2、E6、E9 的可见文案。断网打开本地夹具仍然完整。

### C-3 空态、错误态、窄屏

输入：[fixtures/failures.json](fixtures/failures.json) 的 `empty-orders` 和 `unknown-order`。  
输出：同一组页面在空数组、404 和宽 360 像素下的样式。  
依赖：C-2。  
边界：空列表不是错误。未知订单写「没有这笔订单」。不实现链上错误名的判断。  
验收：E13 的文案。360 像素下文字不横出屏幕。

### C-4 手工清单

输入：`10` 里交给人看的顺序，去掉命令和私钥。  
输出：`web/site/season-checklist.html`。  
依赖：无。  
边界：清单只列「文档已合并、夹具页能打开、复算不一致时没有申请按钮、发放必须一笔一签」。不写部署命令，不写可以代签。  
验收：清单每一行都能在页面上勾选，勾选状态只留在浏览器本地，不提交到服务器。

### C-5 交给 A

输入：C-1 至 C-4 的 PR。  
输出：PR 正文列出用了哪些夹具 id。  
依赖：页面完成。  
验收：A 审查之前不合并。A 的夹具对照表发布之后，另一次只把数据源从本地夹具改成 `HAHA_INDEXER_BASE` 加上 [shared-schema.md](shared-schema.md) 的路径。那次改动仍由 A 审查。字段对不上就停，不在页面里补字段。

## 产物和 PR

一个 PR，基线 `main`，只含 `web/site/` 里上面列出的文件。说明没有合约、没有索引器、没有签名。附一张窄屏和一张桌面截图，用的是夹具而不是主网。

## 不能做

- 不改合约、索引器、部署面板、签名服务。
- 不写兑换、验证、Merkle、重组或钱包连接。
- 不保存私钥，不制作管理员表格让人把积分抄进去。
- 不把夹具改成「演示用的另一套价格」。
- 不把批量铸造写进说明。
