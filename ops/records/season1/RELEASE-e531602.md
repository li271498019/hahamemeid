# haha.meme 第一季服务器发布准备记录

## 发布版本
- 基线：`e531602f7e1a30ab55a07c0b4154a6e5bb536d38`（main HEAD，2026-11-23）
- 包含：docs PR #45、A 链下 PR #46、D 合约 PR #47、C 页面 PR #48 与 round2 PR #50、D 第二轮修复
- 发布目录：`/var/www/releases/20261123-072503-season1-e531602`
- `.release`：`e531602f7e1a30ab55a07c0b4154a6e5bb536d38`
- 部署时间：2026-11-23 15:25 +08（UTC 07:25）

## 索引同步区块
- `checkpoint.safe_block`：135231055
- API `/health`：`{"ok": true, "chainId": 56, "safeBlock": 135231055, "headBlock": 135231064, "lagBlocks": 9, "lastError": null}`
- 确认深度 3，滞后 ≤ 40 块为健康；当前滞后 9 块。

## 数据库
- 库 `haha_indexer`，已执行 `indexer/migrations/003_season1.sql`（全部 IF NOT EXISTS，安全）。
- 新增 6 张表（属主已改为 `haha`）：season1_days、season1_orders、season1_verifications、season1_findings、season1_task_packs、season1_entries。
- 旧表不受影响。未重跑 `setup_db.sh`（会清空生产库）。

## 索引器与 API 代码
- `/opt/haha-indexer/` 已同步基线：api.py、common.py、syncer.py、schema.sql、svg.py、season1_read.py（新增）、season1_store.py（新增），md5 与基线一致。
- `/opt/haha-season1/tools/season1/`（12 个文件，离线签名/检查工具）已同步；venv `/opt/haha-season1/venv` 装有 eth_account 0.14.0，`tools.season1` 可正常 import。
- 修复：迁移后 season1 表属主为 postgres 导致索引器 `InsufficientPrivilege: must be owner of table season1_orders` 反复重启；已将 6 张表属主改为 `haha`，服务恢复。

## 健康检查结果
- 进程守护：`haha-indexer` active/enabled，`haha-api` active/enabled，`Restart=on-failure`。
- 只读 API（season1，6 条）：days/20781 → 404 not_found；eligibility → 404；orders?day=20781 → 200 空列表；orders/1 → 404；verify → 404；findings → 404。全部符合预期（模块未部署，尚无数据；空列表返回 200 不是错误）。
- 既有 API：`/api/health` 200，`/api/v1/stats` 200（参与 354，已注册 651）。
- 页面路由：/、/season、/season.html、/season-apply、/season-apply.html、/season-checklist、/season-checklist.html、/js/season-status.js、/js/season-apply.js、/season/fixtures/day.json 全部 200；首页含“第一季”入口。
- 公共页面不连钱包：season 页无钱包连接调用。

## 日奖签名钱包（独立生成）
- 公钥地址：`0xbd02a475Cb374B1685e6BAae1CF1FbDc2deE5aaA`
- 用途：只签每日验证 VerifyAuth（30 分），不付 gas，不签找错，不签 adminMint。
- 私钥：仅存于服务器 `/etc/haha/season1-signer.env`（0600，root:root），内容为 `SEASON1_SIGNER_KEY=...`。不出服务器、不入 GitHub、不发聊天、不进索引器环境文件。未使用服务器 SSH 登录密钥。
- 派生验证：从存储的私钥重新派生地址，与上述公钥一致。

## 三开关保持关闭（已确认）
- 兑换：模块未部署（`handoff.json` 的 `mainnet.module` 为 null），无模块地址，`redeemOpen` 默认 false，未执行 `setSpender` / `setSpenderBudget` / `setEarner`。
- 领奖：同上，`rewardsOpen` 默认 false，未执行三笔 `setEarner`（VERIFY 30 / FIND 100 / ACCIDENT 100）。
- 签名：模块地址为空，`eip712.domain(56, None)` 实测抛 `SignRejected("module address is unset; fail closed")`，签名服务签不出来（fail-closed）。未执行 `setValidator` / `setRewardSigner`。`SEASON1_MODULE` 未接入签名服务运行环境。
- 未用示例/夹具数据冒充生产数据：页面目前读本地夹具（临时），API 返回真实空态（404 / 空列表）。

## 待办（等 A 联调通过、D 模块地址与授权齐备后再做）
1. D 部署 HahaSeason1 到主网，`handoff.json` 的 `mainnet.module` 填入真实地址。
2. 管理员逐笔授权：`setSpender`、`setSpenderBudget(200, 4000)`、三笔 `setEarner`。
3. 公布日奖公钥（上文地址），模块部署后执行 `setValidator(0xbd02a475Cb374B1685e6BAae1CF1FbDc2deE5aaA, true)`。
4. `setRewardSigner(0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7)`（找错与事故签名人，现有管理员地址）。
5. A 联调通过（读 API 与夹具字段对照表、重放/退款双领/排队复核、页面与安全审查结论）。
6. 验收门通过后才打开 `redeemOpen` / `rewardsOpen`；第一天 manifest 与 `setDayRoot` 另行安排。
