# haha.meme 第一季最终服务器发布记录

> **更正（2026-11-23 16:17，L 指示）：服务器尚未接入 D 提供的模块，链上部署和授权状态待 A 独立核验。**
> 本次发布只完成了代码、迁移与只读服务的部署；“表已建好、进程健康”不等于模块接入完成。
> 不要重复部署、不要重复授权、不要重新生成钱包。后续等 L 给出明确的配置、历史事件回放和逐笔对账步骤后再执行。

## 发布版本（实际提交版本）
- 基线：`6566d9e28de416ee7ac89c92646d23abbad49074`（main HEAD，PR #49 的 merge commit，2026-11-23）
- 包含：A 的 season1 round2（Merkle 共享向量、signer 索引、本机发放工具、上线运行单 `docs/season1/launch-runbook.md`）
- 发布目录：`/var/www/releases/20261123-081321-season1-6566d9e`
- `.release`：`6566d9e28de416ee7ac89c92646d23abbad49074`
- 部署时间：2026-11-23 16:13 +08（UTC 08:13）
- 网站内容与 e531602 相同（web/site/ 无差异）；变化在索引器与 tools/season1/。

## 索引同步区块
- `checkpoint.safe_block`：135237213
- API `/health`：`{"ok": true, "chainId": 56, "safeBlock": 135237213, "headBlock": 135237223, "lagBlocks": 10, "lastError": null}`
- 确认深度 3，滞后 ≤ 40 块为健康；当前滞后 10 块。

## 两份迁移均已应用
- `003_season1.sql`（已于 e531602 发布时应用；6566d9e 版把两张新表并入，IF NOT EXISTS，重跑无影响）
- `004_season1_signers.sql`（本次应用）：新建 `season1_validators`、`season1_reward_signer`
- 现共 8 张 season1 表，属主均为 `haha`：season1_days、season1_orders、season1_verifications、season1_findings、season1_task_packs、season1_entries、season1_validators、season1_reward_signer
- 旧表不受影响。未重跑 `setup_db.sh`。

## 模块接入状态（未接入）
- **服务器尚未接入 D 提供的模块。** `SEASON1_MODULE` 未设（indexer.env 与索引器进程环境均无），`handoff.json` 的 `mainnet.module` 为 null。
- **链上部署和授权状态待 A 独立核验。** A 尚未返回链上核验结果与准确接入步骤；在 A 核验完成之前，不配置模块地址、不重启索引器去追模块事件、不做任何链上授权。
- 索引器未监听任何模块地址；`raw_logs` 仍只有原 8 个 V1 合约地址的日志。
- 8 张 season1 表行数均为 0：尚未接入模块，因此无模块事件可补入。这不是缺失，是未接入的正常表现。
- **“表已建好、进程健康”不等于模块接入完成。** 模块接入以 A 核验通过、模块地址写入 `SEASON1_MODULE`、索引器从部署块起完整补入事件、逐笔对账通过为准。

## 代码同步
- `/opt/haha-indexer/`：syncer.py、schema.sql、season1_store.py、migrations/003、004 已同步 6566d9e，md5 一致；api.py、common.py、season1_read.py、svg.py 无变化。
- `/opt/haha-season1/tools/season1/`：__main__.py、abi_adapter.py、eip712.py、index_model.py、merkle.py 已更新；新增 ops_book.py、ops_server.py、test_round2.py、ops_panel/；venv（eth_account 0.14.0）下 import 正常。
- `haha-indexer` / `haha-api` 均 active/enabled，重启后同步正常。

## 健康检查结果
- 只读 API：days/20781 → 404 not_found；orders?day=20781 → 200 空列表；orders/1 → 404；verify → 404。符合预期（无 root、无订单）。
- 既有 API：`/api/health` 200，`/api/v1/stats` 200（参与 354，已注册 651）。
- 页面路由：/、/season、/season-apply、/season-checklist、/js/season-status.js、/js/season-apply.js 全部 200。
- 公共页面不连钱包。

## 日奖签名钱包（保留现有，未重新生成）
- 公钥地址：`0xbd02a475Cb374B1685e6BAae1CF1FbDc2deE5aaA`（与 e531602 发布时一致）
- 私钥：仍在服务器 `/etc/haha/season1-signer.env`（0600，root），本次未动、未覆盖、未重新生成。私钥不回传。
- 注意：运行单示例用的是 `/etc/haha/season1-signer.key`，与现有 `.env` 文件路径不同；按 L 的指示保留现有 `.env`，不另建。

## 三开关状态（保持关闭）
- 兑换（redeemOpen）：模块未部署，无合约可读，部署时默认 false；未执行 `setSpender` / `setSpenderBudget` / `setEarner`。
- 领奖（rewardsOpen）：同上，默认 false；未执行三笔 `setEarner`。
- 签名：模块地址为空，新版代码实测 `domain(56, None)` 抛 `SignRejected("module address is unset; fail closed")`；未执行 `setValidator` / `setRewardSigner`；`SEASON1_MODULE` 与 `SEASON1_SIGNER_KEY` 均未接入签名服务运行环境。
- 发布完成 ≠ 开放兑换、领奖。

## 首日快照
- 首日快照须到 11 月 24 日 08:00（北京时间）日界后才能确定；本次未提前生成明天的根，也未调用 `setDayRoot`。
- 每个窗口须快照块达 15 个确认且 `root_publish_precheck` 的 `remainingBlocks > 0`，否则当天申请保持关闭。

## 待办（等 L 给出明确步骤后执行，不自行推进）
1. A 独立核验链上部署和授权状态，返回核验结果与准确接入步骤（模块地址、部署块、授权回执）。
2. L 给出明确的配置、历史事件回放和逐笔对账步骤后，再执行：模块地址写入 `SEASON1_MODULE`，重启索引器从部署块起回放并核对事件完整性，逐笔对账。
3. `setValidator(0xbd02a475Cb374B1685e6BAae1CF1FbDc2deE5aaA, true)` 成功且 `validators(地址)` 读回为 1 后，再把签名私钥配进签名进程。
4. 验收门通过后，L 再单独决定是否打开 `redeemOpen` / `rewardsOpen`。

---

## 补录阶段（2026-11-23，PR #52 合并版 9d124ef8，运行单 9d124ef8）

- 补录版本：`9d124ef80b085edc13f530f0d8ffa0ed2656812a`（PR #52 merge commit）
- 模块：`0x4B8a35bFe18750c2058fd01e7159728adD345C00`，部署块 `135231506`
- 网站发布目录保持 `/var/www/releases/20261123-081321-season1-6566d9e`，未再切。
- 补录脚本：仅取合并版的 `indexer/season1_backfill.py`（md5 eb23d7c1db8ca858e280d3f0a72217ac）放到 `/opt/haha-indexer/`。
- 另同步了 PR #52 的签名检查所需文件（`tools/season1/__main__.py`、`mainnet.py`、`sign_gate.py`、`signer_env.py`），仅为运行 `signer-check`，未改网站。

### 预检（--dry-run，不写库）
- ok: true，dryRun: true，范围 135231506 → 135238163
- chainLogCount: 2，missingAnchors: []
- 两条锚点均在链上日志中：ValidatorSet（135233318 / 218）、RewardSignerSet（135233378 / 251）
- checkpointBefore: 135238163

### 正式补录
- ok: true，dryRun: false，范围 135231506 → 135238163
- chainLogCount: 2，missingAnchors: []，ValidatorSet: 1，RewardSignerSet: 1，other: 0，undecoded: 0
- database.checkpoint: 135238163（与补录前相同，未变）
- database.moduleRawLogs: 2 条，与 chainLogs 条数一致，txHash/logIndex 与锚点一致

### 验收三项（全部通过）
1. 全局游标未变：补录前 135238163，补录后 135238163。
2. 链上与库中模块日志一致：链上 2 条，库中 `raw_logs`（模块地址）2 条，txHash 与 logIndex 逐笔一致。
3. 两条签名人设置事件齐全：
   - `season1_validators`：`bd02a475cb374b1685e6baae1cf1fbdc2dee5aaa`，allowed true，块 135233318，logIndex 218
   - `season1_reward_signer`：`083a467259f12602e9053bbae2b3fd5b62976ef7`，块 135233378，logIndex 251
   - `season1_days` 与 `season1_orders` 为 0（尚无 DayRootSet / Redeemed，符合预期）

### 配置模块并恢复索引
- `/etc/haha/indexer.env` 追加 `SEASON1_MODULE=0x4B8a35bFe18750c2058fd01e7159728adD345C00`（未把日奖私钥写进 indexer.env）
- `haha-indexer` 启动，`haha-api` 重启；恢复后 safeBlock 135238465，滞后 7 块，健康 ok。
- `/v1/season1/days/20781` 仍为 404 `{"error":"not_found"}`（无根，符合预期）。

### 签名检查（signer-check，退出码 0）
- `{"address": "0xbd02a475Cb374B1685e6BAae1CF1FbDc2deE5aaA", "addressMatch": true, "validator": true, "signingEnabled": false, "module": "0x4B8a35bFe18750c2058fd01e7159728adD345C00"}`
- 未设置 `SEASON1_SIGNING`。

### 三开关状态（补录后，链上实测）
- redeemOpen: 0（false），rewardsOpen: 0（false），签名 signingEnabled: false。全部关闭。
- 本步骤不需要主网签名，未发任何交易。
