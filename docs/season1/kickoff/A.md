# A 的任务书

## 负责人、范围、必读

负责人：提交人A。

范围：索引器迁移和重组恢复、快照重放与 Merkle 独立复算、公开 checker、日奖签名服务、只读 API、管理员每日汇总和发放对账、复杂申请/验证页、联调，以及审查 C 和审查 D 的安全项。

必读：

1. [README.md](README.md)、[shared-schema.md](shared-schema.md)、[e2e.md](e2e.md)
2. [../00-parameters.md](../00-parameters.md)、[../03-snapshot-merkle.md](../03-snapshot-merkle.md)、[../05-daily-verification.md](../05-daily-verification.md)、[../08-fulfillment-api.md](../08-fulfillment-api.md)
3. 现有 `indexer/README.md`、`indexer/api.py` 的 `ROUTES`、`indexer/schema.sql`

## 分支

L 合并文档 PR 之后：

```sh
git fetch origin main
git checkout -b a/season1-offchain origin/main
```

合并前读 `cursor/season1-d-docs-a3d0`。不要从没有 `docs/season1/` 的 `main` 开工。不要和 D、C 共用一条分支。

## 可改与禁改

可改：

- `indexer/syncer.py`、`common.py`、`api.py`、`schema.sql`
- 计划新增 `indexer/migrations/003_season1.sql`
- `indexer/tests/fixture_test.py` 只追加赛季用例，不删现有用例
- 计划新增 `tools/season1/merkle/`、`tools/season1/checker/`、`tools/season1/signer/`、`tools/season1/ops/`
- 计划新增 `web/site/season-apply.html`、`web/site/js/season-apply.js`

禁改：

- `src/**`、`test/**`、`script/**`
- `tools/deploy-panel/**`，包括 D 的 `season1.html`
- C 的 `web/site/season.html`、`season-checklist.html`、`js/season-status.js`
- `web/site/index.html`
- `docs/season1/00` 至 `12`
- 私钥和 `indexer/env.example` 里的真实 URL。示例文件保持占位

## 工作包

### A-1 复算

输入：`03`。快照块由只读 RPC 取得。  
输出：计划新增 `tools/season1/merkle/`。  
依赖：无。不必等 D。  
边界：先锁定时间戳不晚于 UTC 0 的最后一块，再等这一块 15 个确认。不回退。确认深度 3 是索引器的，不要拿来锁定快照。1552 是候选数，不是库存。`isMinted` 失败或 HTTP 403 停住，不当成未铸造。  
验收：E1、E2。同一组叶，两次运行 root 相同。

### A-2 索引与重组

输入：现有 `syncer.py` 的 checkpoint 回滚，以及 [fixtures/events.json](fixtures/events.json)。  
输出：`003_season1.sql` 里的 `season1_orders`、`season1_days`、`season1_verifications`、`season1_findings`。键用链上 id。  
依赖：在 D-7 的 `handoff.json` 落地前，topic0 先按 `02` 和 `12` 的事件签名在测试里计算；落地后改读 `handoff.json`，不再手抄。  
边界：重组删除受影响块之后的赛季行，再从 `raw_logs` 重放。不得产生第二笔扣分。索引器不发交易。  
验收：E14。

### A-3 只读 API

输入：[shared-schema.md](shared-schema.md)。  
输出：`api.py` 的六条 GET。  
依赖：A-2。可先用夹具单测路由，不等主网。  
边界：只绑本机。没有 POST。空列表 200。未知 id 404 `not_found`。敏感 finding 不带正文。  
验收：E9、E13。PR 里列出每个夹具 id 和实际 JSON 是否同键。这张表是给 C 的交接。

### A-4 公开 checker

输入：A-1 的 root 和当日任务包。  
输出：计划新增 `tools/season1/checker/`。用户可以换自己的 RPC。  
依赖：A-1。  
边界：一致和真实差异都只是给签名服务的输入，checker 自己不发 30 分。`registration-v1` 可以检查，不另发奖励。  
验收：对同一公开输入，checker 与任务包里的结论一致。外部 RPC 失败时结果是「未查清」，不是差异奖。

### A-5 日奖签名

输入：`05` 的 `VerifyAuth`。  
输出：计划新增 `tools/season1/signer/`。  
依赖：任务包哈希。不等 D 的主网地址；域里的 `verifyingContract` 在 handoff 的 `mainnet.module` 仍为 `null` 时拒绝签名。  
边界：服务器生成专用钱包，只公布地址，仓库和日志里不出现私钥。这个钱包不付 gas。不签找错，不签 `adminMint`，不存管理员密钥。撤掉后由链上 `setValidator` 生效，服务再签也会失败。  
验收：E7 的签名可以被 D 的 anvil 模块验过。错误 day 或过期 deadline 签不出来。

### A-6 发放对账

输入：`08`。  
输出：计划新增 `tools/season1/ops/`。  
依赖：A-3 的订单 GET。  
边界：每个 `Pending` 订单一条 `adminMint` calldata，弹管理员自己的钱包。没有全部签名，没有 multicall。不保存私钥，不手抄积分表。模拟失败不广播。`isMinted` 为 true 则停在「名字已存在」，不换名，不自动退款。日志不齐不调用成功确认。超时只对同一 recipient 补签，不第二次扣分。  
验收：E5、E6。

### A-7 复杂页面

输入：A-3。  
输出：计划新增 `web/site/season-apply.html` 与 `web/site/js/season-apply.js`。  
依赖：A-3。`rootMatch = false` 时可以先做，不需要合约。  
边界：页面不连接钱包。申请是一段交给用户自己 agent 的指令。不把兑换逻辑写进 C 的 `season.html`。  
验收：E2 的页面不出现指令。E4 的指令里价格是 200，名字和接收人来自用户选择。

### A-8 审查

输入：C 的 PR，D 的 PR。  
输出：C 的审查结论；D 的安全审查结论，至少覆盖 nonce、撤销、双退、`earn` 返回 0 不消耗 key。  
依赖：对方 PR 存在。  
验收：没有这两份结论，不建议把实现 PR 合并。本任务书不代替你做这个审查。

## 产物和 PR

可以按 A-1、A-2/A-3、A-5、A-6 分成多个 PR，都从 `a/season1-offchain` 或从它再拉出的短分支，基线仍是 `main`。每个 PR 写清不碰合约、不碰部署面板、不含私钥。A-3 的夹具对照表是 C 的开关。

## 不能做

- 不改合约，不部署，不打开赛季开关。
- 不在 `tools/deploy-panel/` 再做一套授权或发放面板。
- 不把日奖私钥或管理员私钥放进仓库、日志、索引器环境文件。
- 不自动补发过期的 30 分，不把 1552 写成已核实库存。
- 不代替 C 改静态说明页，不代替 D 写 Solidity。
