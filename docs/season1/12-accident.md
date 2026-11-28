# 12 特殊事故：退 200，另补 100

L 已批准的只有这一类结果：错误快照等原因，分已经扣了，名字却无法按订单铸给接收人。退回这 200，并额外补 100。管理员仅仅迟到，不走这里，继续等补发，不赔 100。

退 200、另补 100、每张失败订单一次、`requireName = false`、全网每日补偿积分 10000、排队、债权不转给别人、先排除已铸和在途铸造，都已在 11:30 的 t32 第 7、8 行批准。`perUserDailyCap = 50` 只是旧字段硬顶，见 `00` 的技术映射。

## 旧退分实际做什么

[`HahaPoints.refund`](https://github.com/li271498019/hahameme/blob/0942b75e792246a6376a96b760d185e2e803f1f9/src/HahaPoints.sol) 第 554–568 行：

- 只有当时扣款的那个 spender 能调。
- `reason` 必须与扣款时相同，这里是 `SEASON1_REDEEM`。额度记在 `(aiId, reason)` 上。
- `user` 当时必须通过 `.ai` 三重核对，否则 revert `AiRequired`。没有「返回 0」。
- **不**检查是否还持有 `.haha` / `.meme`。持名是 `spend` 的条件（第 966–970 行），不是 `refund` 的条件。
- 金额超过 `spendableOf` 则 revert `RefundExceedsSpendable`。
- 不恢复当日 spender 预算。第 544–545 行把 gross 加上之后，退分没有减回去。所以同一个 UTC 日里，即使退了 200，若预算就是 200，当天不能再 `spend` 200。

`earn` 在额度不够时返回 0，而且发生在写 key 之前（第 415–421 行）。`refund` 不会这样轻轻返回。

补偿 100 用独立 action `SEASON1_ACCIDENT`，`points = 100`，`KeyMode.Lifetime`，`uniqueKey` 为 `bytes32(orderId)`。不要用 `SEASON1_FIND`。找错和事故的账必须能分开审计。

## 谁可以宣布事故

仅管理员，并且链下已经有两份独立意见：提交人A 一份，D 一份。意见不一致时由 L 写明裁定。没有这两份意见，面板不编码 `declareAccident`。这不是第三方审计机构。

超时补发的订单不能被脚本自动改成事故。

## 宣布前必须同时满足

- 订单仍是 `Pending`，没有 `attestFulfillment`。
- 索引器找不到该订单 namehash 上 `NameMinted` 且 `Transfer(from=0, to=订单接收人)` 的交易。
- 管理员内存池或面板里没有尚未落地的 `adminMint`。若有，先用同一 nonce 替换掉，等它消失，再宣布。
- 公开证据包：快照块与块哈希、错误说明、订单号、为什么不能履约。敏感个人信息不要放进事件。事件只放证据哈希。

## 状态

与 `02` 的 `OrderStatus` 是同一套。

1. 原申请人现在仍能通过**同一个** `aiId` 的三重核对：同一笔交易里先 `refund(applicant, 200, SEASON1_REDEEM)`。这一步失败则整笔 revert，订单仍是 `Pending`，季名额和名字锁都保持。退分成功后进入 `AccidentRefunded`，清掉 `seasonOrderOf[aiId]`，再 `earn`。`earn` 返回 0 时**不**回滚退分，订单留在 `AccidentRefunded`，并发 `AccidentCompensationDeferred`。`earn` 返回 100 则进入 `AccidentClosed`。退分不被补偿额度卡住。
2. 现在不能通过三重核对：不调用 `refund`，也不把 200 转给别人。订单变为 `CreditOpen`。债权记在原来的 `aiId` 和原来的 `applicant`。`seasonOrderOf` 先不清，避免 200 还没退就再兑下一个名字。以后只有原地址再次通过原 `aiId` 的核对，才能 `claimAccidentCredit`。

`claimAccidentCredit`：`CreditOpen` 先退再补，退分成功才清季名额；`AccidentRefunded` 只补 100，禁止第二次 `refund`。补成分后进入 `AccidentClosed`。`AccidentClosed` 或 `Fulfilled` 再调用就 revert。`END_TS` 和 `rewardsOpen` 都不挡住这两笔。

名字锁：只在确认没有铸造日志、也没有在途 `adminMint` 之后解开。已经铸出的不解锁。当天的 `reservedFilled` / `boundaryFilled` 不减少，空槽不递补。

季名额：200 已经退回之后，该 `.ai` 可以在以后的窗口再进前 20。同一 UTC 日不能再扣 200，因为 `refund` 不把当日 spender gross 加回去，而预算是 200。这是旧合约第 544–545 行的结果，不是一条新的业务禁令。

退分之后若迟到的收据证明已经铸给原接收人：不要再补发，不要再退第二次。页面同时显示「已铸」和「已退」，交给 L。不自动再扣。

## 拟议函数

```solidity
function declareAccident(uint256 orderId, bytes32 evidenceHash) external; // onlyAdmin
function claimAccidentCredit(uint256 orderId) external nonReentrant;
```

`evidenceHash` 为 0 则拒绝。事件：

```solidity
event AccidentDeclared(uint256 indexed orderId, bytes32 indexed aiId, address indexed applicant, bytes32 evidenceHash);
event AccidentRefunded(uint256 indexed orderId, bytes32 indexed aiId, uint256 amount);
event AccidentCompensationDeferred(uint256 indexed orderId, bytes32 indexed aiId);
event AccidentCompensated(uint256 indexed orderId, bytes32 indexed aiId, uint256 amount);
```

测试至少覆盖：无 `.ai` 时不调用 `refund` 且债权不能转给第二地址；`earn` 返回 0 时 200 已经加回；在途铸造未清掉时 `declareAccident` 失败；管理员超时路径不发出这些事件。
