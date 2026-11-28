# 08 发放流水线与只读 API

实现分两处：链上事件由 D 的合约发出；汇总、模拟队列、网站状态由提交人A 的索引器完成。C 只消费已经稳定的 JSON 做简单列表。本节规定两边的接口，避免各写各的。

## 从事件到一批

索引 `Redeemed`。一个 `orderId` 只有一条。按 `(dayIndex, orderId)` 排序得到当日批次。

稳定条件：

- 事件所在块已经达到索引器确认深度（现为 3）。
- 重组处理与现索引器相同：回滚后按 `raw_logs` 重放。重放不得产生第二个扣分。扣分只发生在用户那笔 `applyFor` 里。索引器不发交易。

批次一旦 `dayIndex` 的窗口结束且确认深度满足，就冻结顺序。晚到的重组若抽掉某条 `Redeemed`，该 `orderId` 从批次消失，对应的积分回滚也由链自己完成。索引器只跟随。

## 模拟与逐笔广播

对冻结批次里仍为 `Pending` 的订单，先用 `isMinted(namehash)` 做只读。返回干净的 `false` 才可以模拟铸造。调用失败、403、空返回都停在「未查清」，不要广播。返回 `true` 则停在「名字已存在，等待 L」，不自动换名，也不自动退款。

可以模拟时：

1. 用管理员地址 `eth_call` `adminMint(label, tld, recipient)`。`eth_call` 本身失败则不广播。
2. 模拟成功：面板对该行单独请求签名。见 `07`。
3. 广播后立刻把 `txHash` 标成「已广播，未收据」。这个状态不是积分，也不是 NFT 所有权。
4. 收据成功后，同一笔交易里必须同时有：
   - `NameMinted`：`tokenId` 等于该订单的 namehash，`owner == recipient`，label 与 tld 一致，`reservedMint == true`。
   - `Transfer`：`from == 0`，`to == recipient`，`tokenId` 与上面相同。
5. 交易 `to` 应是 Registrar `0x4342…50F8`。不要把收据的 `to` 当成接收人。
6. 以上日志齐了，索引器才把网站状态写成「已发放」。这是发放凭证。用户以后把名字转走，凭证仍在，不要改回未发放，也不要去看当前 `ownerOf`。
7. 管理员可以再调用 `attestFulfillment(orderId, mintTxHash)`，链上订单变为 `Fulfilled`。这个函数不接收 tokenId。若只有管理员声明、日志对不上，网站显示「已声明，日志未核对」，不得显示已发放。

`currentOwnerMatches` 只是此刻所有者是否仍为接收人，不能单独结单。

## 重试、替换 nonce、断网

- 同一 `orderId` 只对应一次 `spend`。重发 `adminMint` 不会再次扣分。
- 管理员用同一 nonce 替换 gas：索引器以最新收据为准，旧哈希标成 dropped。不得因此再插一条订单。
- 进程重启：从链上 `Redeemed` 与本地已见收据重建，不从内存队列重建。
- 收据成功但日志里的 `Transfer.to` 不是 `recipient`：标「异常」，不调用成功确认，通知 L。正常 `adminMint` 不会出现这种情况。若出现，说明签错了参数。

超时：窗口结束加 12 小时之后仍是 `Pending`，批次仍然保留。管理员晚些时候对**同一** `recipient` 补签。不占下一天的 20，不第二次 `spend`。最后一批的目标时刻是 `2026-12-09T12:00:00Z`，晚于该时刻的补发仍然允许，只是错过公开时限，页面照实写实际块时间。

## 只读 API

新路径挂在现有索引器上，仍只绑定本机，由 nginx 提供 `/api/`。不要让这些接口发交易。

| 方法 | 路径 | 含义 |
| --- | --- | --- |
| GET | `/v1/season1/days/{dayIndex}` | root、快照块、复算 root 是否一致、`reservedCount`、`remainingSlots`、已用槽 |
| GET | `/v1/season1/eligibility/{aiId}?day=` | `none` / `reserved` / `boundary` / `excluded`，以及排除原因：`balance`、`pending`、`fulfilled`、`below-cutoff` |
| GET | `/v1/season1/orders?day=` | 稳定批次。字段：`orderId, aiId, applicant, recipient, label, tld, tier, status, mintTx, tokenId` |
| GET | `/v1/season1/orders/{orderId}` | 单笔，含模拟错误码（若有），不含签名原文 |
| GET | `/v1/season1/verify/{aiId}?day=` | 是否已领 30，`taskPackHash`，verdict |
| GET | `/v1/season1/findings/{reportEvidenceHash}` | commit 的块号、交易序号、日志序号、是否已指定根因、根因是否已支付。敏感条目只有 `withheld: true`，没有报告正文 |

`eligibility` 的余额来自快照重放，不是当前余额。当前余额可以另给字段 `balanceNow`，避免用户把申请后的余额当成快照余额。

Schema 变更用新的 `indexer/migrations/003_season1.sql`，由提交人A 在实现阶段添加。本 PR 不写 SQL。表至少包括 `season1_orders`、`season1_days`、`season1_verifications`、`season1_findings`，键是链上 id，而不是自增业务 id。重组时删除受影响块之后的行，再从 `raw_logs` 重放。

## 与 A 的接口

D 保证事件字段与 `02` 一致，并在测试里打印一条样例 ABI。提交人A 的解码表按该 ABI 写。C 的页面只渲染上述 GET 的固定字段，不计算 Merkle，不拼签名。
