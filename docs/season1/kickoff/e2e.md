# 端到端验收

这些场景用于以后的实现 PR。现在没有一条已经在链上或网站上跑通。每条注明唯一负责人和要对照的样本。

| ID | 场景 | 负责人 | 通过标准 | 样本 |
| --- | --- | --- | --- | --- |
| E1 | 日界前最后一块锁定后再等 15 块。深度不够不改用更早的块 | A 复算，D 的 `setDayRoot` 拒绝过新的块 | 块时间戳不晚于该 UTC 0，且不存在更晚的合格块。`SnapshotTooFresh` 出现在失败样本里 | [fixtures/day.json](fixtures/day.json)、[fixtures/failures.json](fixtures/failures.json) 的 `snapshot-too-fresh` |
| E2 | 独立复算 root 与管理员 root 不一致 | A | `rootMatch = false`。申请指令不出现 | [fixtures/day-mismatch.json](fixtures/day-mismatch.json) |
| E3 | 保留名额与边界同分只抢剩余槽。未申请不递补 | D 链上计数，A 展示 | 高于边界分的人没来时 `remainingSlots` 不增加 | [fixtures/eligibility.json](fixtures/eligibility.json) |
| E4 | 用户 agent 自己提交兑换，扣 200，锁名。失败全回滚 | D | 一笔交易。没有后台代扣 | `09` 的兑换用例 |
| E5 | 20 个名字是 20 笔 `adminMint`。管理员钱包逐笔签名 | A 的 ops 出 calldata，管理员签名 | 没有批量按钮，面板不保存私钥。收据 `to` 是 Registrar | [fixtures/orders.json](fixtures/orders.json) |
| E6 | 日志齐了才显示已发放。只有管理员声明时显示未核对 | A 计算 `logCheck`，C 照文案显示 | `mismatch` 不写成已发放 | [fixtures/order-log-mismatch.json](fixtures/order-log-mismatch.json) |
| E7 | 当日验证 30 分，每人一次，全网 100000。过日不补。额度不足不占 key | D 链上，A 签名与 API | `claimed` 保持 false，nonce 不变。第二天不是补昨天 | [fixtures/verify.json](fixtures/verify.json) 的 `queued` |
| E8 | 找错 100，与当天 30 可叠加。同一根因只付最早一份。公示 24 小时后才能领，可跨过 `1796774400` | D | 公示期内领取失败。`END_TS` 之后、公示后的 7 天内可以领 | [fixtures/failures.json](fixtures/failures.json) 的 `finding-claim-inside-publicity` |
| E9 | 敏感 finding 只有 withheld | A API，C 页面 | 响应里没有正文 | [fixtures/finding.json](fixtures/finding.json) 的 `withheld` |
| E10 | 事故退 200 再补 100。补偿额度不足时不回滚退分。同一订单不能退第二次。债权不转给别人 | D | `CreditOpen` 期间不能再占季名额。当天 filled 不减少 | [fixtures/failures.json](fixtures/failures.json) 的 `double-refund` |
| E11 | 撤掉日奖或找错签名人后，旧签名失败 | D | `BadSignature` | `revoked-validator` |
| E12 | 验收没过，两个开关保持关闭。日期不顺延 | D 开关默认 false，A 不发申请指令 | `1795478400` 到了也不自动打开 | `00` 的验收行 |
| E13 | 空列表与未知订单 | A API，C 空态和错误态 | 200 空数组；404 `not_found` | `empty-orders`、`unknown-order` |
| E14 | 重组后退回的 `Redeemed` 不留下第二笔扣分 | A 索引器 | 沿用现有 checkpoint 回滚，赛季表一起重放 | `indexer/README.md` 的重组段落 |
| E15 | C 的静态页在夹具上就能读，不依赖 D 的字节码 | C | 断网打开夹具，仍能看到 15 天、200、30、100 和不连接钱包 | C 的任务书 C-3 |

失败测试的归属：链上错误归 D，索引和 HTTP 归 A，文案归 C。不要把同一条失败交给两个人各写一套判断。
