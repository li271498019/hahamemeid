# 05 每日验证（30 分）

## 它证明什么

它证明：项目的验证签名人愿意为「这个 `.ai` 在这一天、这份任务包、这个 agent 代数上的核对结果」签一次名，并且旧 `HahaPoints.earn` 实际发出了 30 分。

它不证明：

- 用户的 agent 独立跑过脚本。正确答案可以复制。
- 签名服务是去中心化的，或符合 ERC-8004 的 Validation Registry ABI。
- 链上重新执行了评分计算。模块不读 `getScore` 来决定给不给分，因为「真实差异也给 30」。若模块再要求链上结果等于任务包，差异路径就发不出分。

公众能审计的是：任务包、用户提交的结果、签名人地址、最终的 `Verified` 和 `PointsChanged`。服务可以被复盘，这不等于没有信任。

## 任务包

每个 `dayIndex` 一份。在该日快照块达到 15 个确认之后才发布，不能提前到窗口开始前 30 分钟，因为那时日界最后一块往往还没锁定。canonical JSON，UTF-8，键排序，无多余空白。当天没有新事件也要发任务包，核对结果可以是「与已公布展示一致」。项目签名服务停了，没领到的 30 不自动补。

```json
{
  "seasonId": 1,
  "dayIndex": 20781,
  "blockNumber": 0,
  "blockHash": "0x",
  "checks": [
    {
      "id": "score",
      "agentId": "1",
      "generation": "1",
      "name": "example.haha",
      "expectCount": "0",
      "expectSum": "0"
    }
  ]
}
```

`taskPackHash = keccak256(文件字节)`。管理员或验证签名人调用：

```solidity
function setTaskPack(uint64 dayIndex, bytes32 taskPackHash) external;
```

仅 `validators[msg.sender]` 或管理员。同一天在**还没有任何** `Verified` 之前可以改。已有领分则冻结。模块不解释 JSON。

核对内容至少包括，由公开脚本做，不由合约做：

- 固定块上 `HahaReputation.getScore(agentId)` 的 `count` 与 `sum`。
- 该块之前该 `agentId` 的 `Rated` 条数，与 `count` 是否一致；改评语不增加 `count`，脚本必须按「每个 rater aiId 的最后一条」理解，而不是按事件条数当 count。
- `generationOf(agentId)` 是否等于任务包里的 generation。
- 可选：注册文件是否含 `type = https://eips.ethereum.org/EIPS/eip-8004#registration-v1`。这一项可以报差异，**不**单独发分。

脚本放在后续由提交人A 实现的工具里。D 只负责链上领分。脚本的输入是公开 RPC，用户 agent 可以换自己的 RPC。

## 领分

```solidity
struct VerifyAuth {
    uint256 seasonId;
    uint64 dayIndex;
    bytes32 aiId;
    uint256 agentId;
    uint64 generation;
    bytes32 taskPackHash;
    uint8 verdict;
    uint256 nonce;
    uint64 deadline;
}
```

`claimVerification`：

1. 该日 `taskPackHash` 已设置且与 `auth` 相同。
2. `verdict` 为 0 或 1。
3. `identity.generationOf(auth.agentId) == auth.generation && auth.generation >= 1`。代数在 burn 后仍可读。不要求 `isActive`。对不上则 `StaleGeneration`，不发分。
4. `msg.sender` 的 `.ai` 等于 `auth.aiId`。
5. 签名人是 `validators` 中的地址，EIP-712 见 `04`。
6. `block.timestamp >= START_TS && block.timestamp < END_TS`，并且落在该 `dayIndex` 的窗口内，`deadline` 等于窗口结束。过了当天不能补领。`END_TS` 之后的验证签名无效。
7. `auth.nonce == nonces[aiId]`。已领过：在增加 nonce 之前 return，不再 `earn`。
8. `earn(ACTION_VERIFY, msg.sender, VERIFY_KEY)`。返回 0 则 `EarnNotPaid` 并整笔回滚。nonce 和 `verified` 都不变，Points 的去重 key 也没写上。返回值必须是 30。
9. 然后才 `verified[aiId][dayIndex] = true`，并且 `nonces[aiId]++`。

同一 `.ai` 一天只能成功一次，和他有几个名字、几个 agent 无关。任务包可以抽其中一个 agent。换一个 agent 再领，第二次幂等返回，不多给 30。

`requireName` 已批准为 true。领奖时没有 `.haha` 或 `.meme`，旧 `earn` 在第 404 行返回 0。本模块必须 revert，不把当天标成已领。第 415–421 行在写过去重 key 之前就返回 0，所以返 0 不会消耗这次领取。全网触顶同样如此。过了当天窗口不能补领。

全网 `100000` 用尽时同样返回 0。用户只能在**当天窗口结束前**用同一签名再试。窗口结束后这 30 分不再补。下一天是新的任务，不是把昨天的 30 补上。项目服务停了也一样，不自动补。

## 签名人

```solidity
function setValidator(address account, bool allowed) external; // onlyAdmin
```

可以有多个验证签名人，便于轮换。取消授权不检查代码。已发出的、nonce 尚未消耗的签名，在授权取消后必须失败。测试要覆盖「先签后撤权」。

私钥不进仓库、不进面板、不进日志。签名在独立的离线或最小服务里完成。服务被攻破可以滥发 30 分，直到 `globalDailyPoints` 和 `perUserDailyCap`。这是信任边界，要用预算上限卡住，不能靠「我们会看日志」当作唯一防护。
