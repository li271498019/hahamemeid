# 04 授权、EIP-712、重放

## 谁可以发兑换交易

`msg.sender` 必须是该 `aiId` 当前的 `.ai` 持有人（三重核对）。签名者也必须是 `msg.sender`。不设中继器。用户的 agent 用这个钱包签名并发送。网站不签名、不代付。

接收人 `recipient` 可以是另一个地址，包括合约。扣分扣在 `msg.sender` 的 `.ai` 上。

若提交时三重核对失败（已经不是这个 `.ai` 的持有人），整笔 revert，不扣分。

## EIP-712

域：

```solidity
name: "HahaSeason1"
version: "1"
chainId: 56
verifyingContract: address(this)
```

类型串，字段顺序不得改：

```text
ApplyAuth(
  uint256 seasonId,
  uint64 dayIndex,
  bytes32 aiId,
  string label,
  uint8 tld,
  uint256 price,
  address recipient,
  uint256 nonce,
  uint64 deadline,
  bytes32 root,
  uint8 tier,
  uint256 balance
)
```

`string label` 按 EIP-712 动态类型哈希。实现使用 OpenZeppelin `EIP712` 与 `ECDSA`，不要手写 `eth_sign` 前缀的另一种摘要。

EOA：`ECDSA.recover(digest, signature) == msg.sender`。

代码长度非 0：`IERC1271(msg.sender).isValidSignature(digest, signature) == 0x1626ba7e`。否则 `BadSignature`。不要对合约钱包做 ecrecover。

## 必须绑住的字段

签名摘要里已经包含：`seasonId`、`dayIndex`、`aiId`、`label`、`tld`、`price`、`recipient`、`nonce`、`deadline`、`root`、`tier`、`balance`。域里还有 `chainId` 和模块地址。

因此下面的替换都会验签失败，或在后续检查失败并回滚：

- 换链、换模块地址。
- 换日子、换 Merkle root（换日或纠正 root 之后旧签名作废）。
- 改名字、后缀、价格、接收人。
- 重放同一 nonce。成功申请才 `nonce++`。失败交易回滚，nonce 不变。
- `deadline` 必须等于窗口结束的 Unix 时间。下一天的 `dayIndex` 对不上。

模块没有 `spendFor(user, amount)` 这种入口。唯一调用 `points.spend` 的函数是 `applyFor`。管理员不能用这个合约对任意地址扣 200。管理员若另外 `setSpender` 了一个别的合约，那是旧 Points 的既有权限，本季部署步骤不得再授权第二个 spender。

## 验证与找错的签名

这两类不是用户授权扣分，是项目签名人授权发分。域相同，类型不同。

```text
VerifyAuth(
  uint256 seasonId,
  uint64 dayIndex,
  bytes32 aiId,
  uint256 agentId,
  uint64 generation,
  bytes32 taskPackHash,
  uint8 verdict,
  uint256 nonce,
  uint64 deadline
)

FindingAuth(
  uint256 seasonId,
  bytes32 reportEvidenceHash,
  bytes32 salt,
  bytes32 aiId,
  uint256 nonce,
  uint64 deadline
)
```

签名不包含 `canonicalRootCauseId`，也不包含 `agentId`。根因合并只改 `assignCanonical` 的指向，已签的 `FindingAuth` 摘要不变。第二份报告仍然验得过，只是 `canonicalClaimed` 会拒绝再发 100。报告里的 `reportId` 被 `reportEvidenceHash` 覆盖，不单独进签名。

验证签名人与找错签名人分开，见 `setValidator` / `setRewardSigner`。用户签名不能拿来领 30 或 100。签名人签名也不能拿来 `applyFor`。

`verdict`：`0` 一致，`1` 真实差异。两者都发 30。其他值 revert。

nonce：验证和找错共用 `nonces[aiId]`，与兑换共用一把计数器，避免三套 nonce 被交叉重放时还要记额外映射。每次成功的 `applyFor`、`claimVerification`（真正发分的那次）、`claimFinding` 都加一。幂等的第二次验证在加 nonce 之前返回。

deadline：验证必须落在该 `dayIndex` 的窗口内，且 `deadline == (dayIndex+1)*86400`。窗口结束不能补领 30。`END_TS` 之后的验证签名无效。

找错的 `deadline` 等于 `publishedAt + 24 小时 + 7 天`。`publishedAt` 由 `publishRuling` 写成。模块拒绝更早的领奖，也拒绝晚于这个 deadline 的领奖。`commitFinding` 必须在 `END_TS` 之前，并记下 `committedAt`。`publishRuling` 要求 `block.timestamp <= committedAt + 7 days`，签名人不能把这个窗口放宽。事故债权没有这个赛季截止。

## 重放测试必须覆盖

- 同一签名两笔：第二笔 `BadNonce` 或 `SeasonUsed` / `AlreadyClaimed`。
- chainId 改成 97 的摘要在主网失败。
- 把 recipient 从 A 改成 B 而签名不变，失败。
- 用第 1 天的 root 在第 2 天提交，失败。
- 合约钱包的 1271 返回魔数以外的值，失败。
- 签名人密钥签出来的 `ApplyAuth`，失败。
