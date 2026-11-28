# 06 找错奖励（100 分）

## 目标

让别人能核对「谁先提出、错误是否成立、奖是否只发了一次」。不能承诺每个人都会信服。最终裁定仍是项目人员做的。本季没有独立第三方审计这项预算，文档不得写成已经有外部审计。

复核人就是实际在岗的 L、提交人A、D。C 只在提交人A 安排下做清单核对，不做根因判定。B 不参与。

## 承诺什么

服务器收到工单的时间可以改。链上只承诺**这一份报告字节**在某个日志位置已经存在。它不承诺报告是真的，也不自动知道谁是第一个有效揭示。

```solidity
function commitFinding(bytes32 reportEvidenceHash, bytes32 salt) external;
```

调用时先做 `.ai` 三重核对，把当时的 `aiId` 存进 commit。没有 `.ai` 不能 commit，也不能先占坑再去取得 `.ai`。`reportEvidenceHash == 0` 或 `salt == 0` 都 revert `ZeroCommit`。

```text
commitHash = keccak256(abi.encode(
    block.chainid,
    address(this),
    SEASON_ID,
    aiId,
    reportEvidenceHash,
    salt
))
```

必须使用 `abi.encode`，不要 `encodePacked`。`reportEvidenceHash = keccak256(报告原始字节)`。报告至少包括：提交人自己取的 `reportId`、最小复现、期望值、实际值、所依据的区块号和块哈希、展示快照的哈希。哈希对不上，就不是这一份承诺。

`reportId` 与复核之后的 `canonicalRootCauseId` 不是同一个东西。根因 id 由复核人指定，可以把多份报告并到同一个 id。并到一起不会改报告哈希，因此旧 commit 仍然闭合，用户签名也不必重签。

自由文本的「根因标题」不会天然相同。不要用标题哈希当 commit。

## 优先权

索引器从 `FindingCommitted` 日志读出 `(blockNumber, transactionIndex, logIndex)`。同块不能只看块号。合约里不接收调用者自报的交易序号，避免伪造。

优先权不是「最早的 commit」。一条 commit 如果始终不揭示，或揭示出来的字节对不上哈希，或复核认为证据不充分（没有可重放的复现、没有期望/实际、没有区块），就没有优先权。

在所有「哈希闭合，且复核认为证据充分」的 commit 里，日志位置最早的那一条优先。这个「充分」是 L、提交人A 和 D 的裁定。链上不能代替这次裁定。公开裁决要写明引用的是哪一条日志的块号、交易序号和日志序号，以及为什么更早的 commit 不被接受。

已批准的时间：赛季内 commit。commit 块时间戳之后 7 天内揭示，可以晚于 `END_TS`。然后公示 24 小时。公示结束后再有 7 天提交领奖。领奖交易因此必然晚于 commit 许多块，模块不再另加「至少 1 块」的业务间隔。过了领奖 deadline，签名作废。额度不足时不发分、不占 `canonicalClaimed`，同一签名可在额度恢复后、deadline 之前再试。

能获奖的错误：可重放，并且影响本项目的数据、每日验证或兑换履约。错别字、主观文案、外部 RPC 短暂故障不奖。提交人A 与 D 各自写意见。分歧由 L 公开理由裁定。同一根因只给最早一份充分证据 100 分一次。当天的 30 分可以另外领，不收回。

找错签名人是现有管理员地址。日奖签名人不是这把密钥。

敏感问题在披露前只提交 `reportEvidenceHash`。原始报告不进事件、不进公开 API。公开裁决写「已受理，细节在修复后披露」，不写用户身份、余额或订单接收地址。

## 领奖签名

`FindingAuth` 只签 `seasonId`、`reportEvidenceHash`、`salt`、`aiId`、`nonce`、`deadline`。复核人另调用 `assignCanonical(reportEvidenceHash, canonicalRootCauseId)`。合并根因时改的是这条指向，签名哈希不变，验证仍然通过。第二份报告若指向一个已经支付的根因，`claimFinding` 验签成功但 `CanonicalUsed`，不再发 100。

## 证据包

公开问题（非敏感）在揭示时同时公布，便于重放：

| 字段 | 要求 |
| --- | --- |
| 固定区块与块哈希 | 问题依赖的状态 |
| 期望值与实际值 | 具体到函数返回或事件 |
| 最小复现 | 一笔 `eth_call` 或一段 Foundry 命令，别人能重放 |
| commit 日志位置 | 块号、交易序号、日志序号。优先权只用这个 |
| reportId | 提交人原文里的编号，与根因 id 分开 |
| canonicalRootCauseId | 复核指定。合并时指向已有 id |
| 裁决 | 成立 / 不成立 / 证据不足 / 合并。写理由，并说明更早的 commit 为何不算充分 |

不成立或证据不足不发分。合并到已支付的根因不发第二份，原签名仍可验过。pending 裁决不计余额。链上不能证明报告内容为真。

## 发奖

找错签名人在公示满 24 小时之后签 `FindingAuth`。领奖时 `requireName` 已批准为 true：调用 `earn` 的地址必须仍持有 `.haha` 或 `.meme`，否则旧合约返回 0，本模块回滚且不把根因标成已付。

`claimFinding` 成功才 `earn` 100，`KeyMode.Lifetime`，`uniqueKey = canonicalRootCauseId`。返回 0 则整笔回滚，`canonicalClaimed` 仍为假，额度恢复后可再提交同一签名，直到 deadline。

同一根因第二个人：签名仍可验过，发分被 `CanonicalUsed` 拒绝。同一人同一根因：模块先查 `canonicalClaimed`，避免无意义消耗 gas。

## 已批准参数

| 项 | 建议 | 状态 |
| --- | --- | --- |
| 公示期 | 24 小时 | 已批准 |
| 揭示期限 | commit 后 7 天，可跨过申请截止 | 已批准 |
| 领奖窗口 | 公示结束后 7 天 | 已批准 |
| `requireName` | `true` | 已批准 |
| 每人每日不同根因 | `5` | 已批准。次数 |
| 全网每日找错积分 | `10000` | 已批准。不够则排队，不丢奖 |
| 获奖范围 | 可重放且影响数据、验证或履约。错别字、主观、外部 RPC 暂故障不奖 | 已批准 |
| 敏感披露 | 私下揭示，修复后再公开正文 | 已批准。不另写天数 |

这些数字可以写进测试和主网 calldata。主网交易仍要管理员自己签名。安全问题以后仍可修。
