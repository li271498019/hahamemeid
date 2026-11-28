# 第一季开工入口

这是 A、C、D 的总入口。业务规格 v1.0 在上一级 `00` 到 `12`，本目录不改那些数字。这里只规定谁改哪些真实文件、交付什么、怎样交接。

本目录里的文件都是任务文档。下面标成「计划新增」的代码路径，在本仓库里现在不存在。不要把它们当成已经实现。

## 现在读哪一份

仓库：<https://github.com/li271498019/hahameme>

文档 PR：<https://github.com/li271498019/hahameme/pull/45>。合并前，`main` 上没有 `docs/season1/`。只打开 `main` 会漏掉全部规格。

| 时机 | 开工文档 |
| --- | --- |
| PR 尚未合并 | <https://github.com/li271498019/hahameme/blob/cursor/season1-d-docs-a3d0/docs/season1/kickoff/README.md> |
| L 合并进 `main` 之后 | <https://github.com/li271498019/hahameme/blob/main/docs/season1/kickoff/README.md> |

合并后的规格目录：<https://github.com/li271498019/hahameme/tree/main/docs/season1>  
未合并时的规格目录：<https://github.com/li271498019/hahameme/tree/cursor/season1-d-docs-a3d0/docs/season1>

## 三份任务书

| 角色 | 任务书 | 合并后从 `main` 新建的分支 |
| --- | --- | --- |
| A | [A.md](A.md) | `a/season1-offchain` |
| C | [C.md](C.md) | `c/season1-pages` |
| D | [D.md](D.md) | `d/season1-contracts` |

B 没有任务，不建分支。

三条可以转发的开工指令在本文最下面。

## 共享契约

- 接口、事件和失败样本：[shared-schema.md](shared-schema.md)
- 对照 JSON： [fixtures/](fixtures/) 目录。这些是文档样本，不是线上 API 已经返回的数据。
- 端到端验收：[e2e.md](e2e.md)
- 业务数字只以 [../00-parameters.md](../00-parameters.md) 为准。本目录复述是为了能单独开工；若字面冲突，以 `00` 为准。

冻结值：15 个窗口，`1795478400` 至 `1796774400`，末批 `1796817600`；每天 20、全季 300、价格 200；验证 30 分、每人每日 1 次、全网 `100000`；找错 100 分、每人每日 5 个不同根因、全网 `10000`；事故退 200 并另补 100、全网补偿 `10000`、`requireName = false`；快照确认 15 块。不要改回 14 天、100 万或 1000 万。

## 仓库里已经存在、本入口核对过的位置

没有 `extensions/` 目录。不要新建它。新代码按下面的现有树放置。

| 已存在 | 用途 |
| --- | --- |
| `src/*.sol`、`src/interfaces/`、`src/libraries/` | 已部署合约。D 不改这些文件 |
| `test/*.t.sol`、`script/Deploy.s.sol` | 旧测试和旧部署脚本。不改 |
| `tools/deploy-panel/` | 本地部署面板，默认端口 4321。只连钱包，不保存私钥。现有 `app.js` 部署的是已经上线的十个合约 |
| `indexer/api.py`、`syncer.py`、`common.py`、`schema.sql` | 现有只读索引。API 只绑 `127.0.0.1:8787`，只实现了 GET。nginx 把公网 `/api/` 转到这里并去掉前缀 |
| `indexer/migrations/001_name_indexes.sql`、`002_reviews_latest_index.sql` | 已有迁移。没有 `003` |
| `indexer/tests/fixture_test.py` | 已有夹具测试 |
| `web/site/*.html`、`web/site/js/` | 静态站。`js/config.js` 里 `HAHA_INDEXER_BASE` 现为 `"/api"`。`web/site/README.md` 提到 `js/mock.js`，该文件不在树里，不要补造一套全站 mock |
| `docs/contracts/DEPLOYED.md` | 已部署地址。与 [../01-baseline.md](../01-baseline.md) 一致 |
| `foundry.toml` | solc 0.8.28，optimizer 200，`via_ir`，cancun |

现有索引确认深度是 3 块（`indexer/README.md`）。赛季快照确认深度是 15 块。两处都保留，不要互相覆盖。

## 唯一所有权

| 路径 | 谁可以改 | 谁不能改 |
| --- | --- | --- |
| `src/HahaSeason1.sol`（计划新增；体积超过 24576 时才允许再加 `src/HahaSeason1Exchange.sol` 与 `src/HahaSeason1Rewards.sol`） | D | A、C |
| `test/Season1*.t.sol`（计划新增） | D | A、C |
| `script/Season1.s.sol`（计划新增） | D | A、C |
| `script/Deploy.s.sol` 与现有 `src/`、`test/` | 都不改 | A、C、D |
| `tools/deploy-panel/season1.html`、`season1.js`、`season1-encode.mjs`、`public/season1/`（计划新增） | D | A、C |
| `tools/deploy-panel/index.html` 里指向 `season1.html` 的那一个链接 | D | A、C |
| `tools/deploy-panel/app.js` 及现有十合约部署步骤 | 都不改 | A、C、D |
| `indexer/**`、计划新增的 `indexer/migrations/003_season1.sql` | A | C、D |
| `tools/season1/**`（计划新增：复算、公开 checker、日奖签名、发放对账） | A | C、D |
| `web/site/season-apply.html`、`web/site/js/season-apply.js`（计划新增） | A | C、D |
| `web/site/season.html`、`web/site/season-checklist.html`、`web/site/js/season-status.js`（计划新增） | C | A、D |
| `web/site/index.html` 里指向 `/season` 的那一个链接 | C | A、D |
| `docs/season1/00` 至 `12` 的业务数字 | 本轮之后不改。发现安全问题另开文档 PR，不在实现 PR 里改价 | A、C、D |
| `docs/season1/kickoff/fixtures/` | 本任务书的契约。实现 PR 不改字段名 | A、C、D |

签名服务只有一套，放在 A 的 `tools/season1/signer/`。它只签每日验证，使用服务器专用钱包，不放管理员私钥，不付 gas。

管理员面板不做两套。D 的 `tools/deploy-panel/season1.*` 只编码部署和授权交易：部署模块、`setSpender`、`setSpenderBudget(200, 4000)`、三笔 `setEarner`、`setValidator`、`setRewardSigner`、两个开关。`07` 里的「发放清单是另一屏」由 A 的 `tools/season1/ops/` 实现。那一屏只给管理员钱包逐笔弹出 `adminMint`，不保存私钥，不部署，不调用 `setEarner`。没有「全部签名」按钮。`adminMint` 仍是 Registrar `0x43426E37a31AafDaba851858e34B81DC300650F8` 上的 `0x65f5a090`，一笔一个名字。

## 并行

D 按 `02` 写合约，不必等 A。A 按 [shared-schema.md](shared-schema.md) 写索引、复算、签名和读 API，不必等主网地址；D 交出 ABI 之后，A 把解码改成对那个 JSON，不再手抄。C 从 [fixtures/](fixtures/) 做静态页，不必等 D 的合约，也不必等 A 的 API。A 的读 API 与夹具字段一致之后，C 只把数据源从夹具文件换成 GET。

## 交接

1. D 在自己的 PR 里提交 `tools/deploy-panel/public/season1/handoff.json`。字段见 [shared-schema.md](shared-schema.md) 的「D 交给 A」。没有这份文件，A 不接主网解码。
2. A 复核 D 的重放、退款双领、排队不消耗 key，并在 D 的 PR 留下审查结论。这是安全审查，不是 D 自己宣布通过。
3. A 在自己的 PR 里说明读 API 与 `fixtures/` 的字段一致。C 的页面只消费这些 GET。
4. A 审查 C 的 PR。C 不合并未经 A 审查的页面。

## 转发给 A

仓库 <https://github.com/li271498019/hahameme>。先读未合并分支上的 <https://github.com/li271498019/hahameme/blob/cursor/season1-d-docs-a3d0/docs/season1/kickoff/A.md>，不要只看 `main`。L 合并 PR #45 之后，从 `main` 建 `a/season1-offchain`，文档改为 <https://github.com/li271498019/hahameme/blob/main/docs/season1/kickoff/A.md>。你做索引、复算、日奖签名、读 API、发放对账和复杂申请页。不要做第二套部署面板，不要改 `src/`。

## 转发给 C

仓库 <https://github.com/li271498019/hahameme>。先读未合并分支上的 <https://github.com/li271498019/hahameme/blob/cursor/season1-d-docs-a3d0/docs/season1/kickoff/C.md>，不要只看 `main`。L 合并 PR #45 之后，从 `main` 建 `c/season1-pages`，文档改为 <https://github.com/li271498019/hahameme/blob/main/docs/season1/kickoff/C.md>。你只用夹具做静态说明和只读状态。不要等合约完工，也不要改索引器、签名或合约。

## 转发给 D

仓库 <https://github.com/li271498019/hahameme>。先读未合并分支上的 <https://github.com/li271498019/hahameme/blob/cursor/season1-d-docs-a3d0/docs/season1/kickoff/D.md>，不要只看 `main`。L 合并 PR #45 之后，从 `main` 建 `d/season1-contracts`，文档改为 <https://github.com/li271498019/hahameme/blob/main/docs/season1/kickoff/D.md>。你做新模块、Foundry 测试和部署授权面板。不要做发放站，不要改已经部署的合约，不要上主网。
