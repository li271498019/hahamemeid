# 索引器注意事项

状态：给索引器与 API 实现方。日期：2026-11-20。来源：`QUESTIONS.md` 第 5 条裁决。

`SPEC 10` 已经规定了「从零重放日志必须能得到什么」。本文只补充三条**容易踩错**的地方。

## 1. `NameMinted.aiId == bytes32(0)` 的行不代表任何身份

`SPEC 6.3` 的 `NameMinted` 事件把 `aiId` 设成 `indexed`。管理员铸造保留名时 `aiId` 是 `bytes32(0)`：

```solidity
event NameMinted(
    uint256 indexed tokenId,
    address indexed owner,
    uint8 tld,
    bytes32 indexed aiId,      // 管理员铸造时为 bytes32(0)
    string label,
    bool reservedMint          // 管理员铸造时为 true
);
```

**所有保留名铸造都会落到同一个 `aiId = 0` 的分区里。**

- 不要 按 `aiId` 聚合铸造历史，否则 61 个保留名会被当成「同一个身份」的记录。
- 需要区分时用 `reservedMint`：
  - `reservedMint == false` → 公众铸造，`aiId` 是真实身份
  - `reservedMint == true` → 管理员铸造，**忽略 `aiId`**
- 保留名有没有「铸造身份」这个概念？**没有。** 管理员铸给谁就是谁的 NFT，但那次铸造不产生积分、不关联 `.ai`。

## 2. 两个 `Transfer` 事件不是同一个东西

| 事件 | 来源 | 含义 |
| --- | --- | --- |
| `Transfer(address,address,uint256)` | ERC-721（`HahaRegistrar`） | NFT 换了主人 |
| `Transfer(bytes32,address)` | EIP-137（`HahaRegistry`） | 注册表记录的 owner 更新 |

名字转让时两条都会发，但**签名不同、索引的 topic 不同**。按 topic0 过滤时不要混。

`HahaRegistry` 还有一个容易看错的：

```solidity
event NewOwner(bytes32 indexed node, bytes32 indexed label, address owner);
```

这里的 `node` 参数是 **TLD node**（`hahaNode` 或 `memeNode`），`label` 是 labelhash。这与 ENS 一致，但和「node 是这个新名字的 node」不是一回事。新名字自己的 resolver 在紧接着的 `NewResolver` 里。

## 3. `RecordsCleared` 一次清三样

```solidity
event RecordsCleared(bytes32 indexed node);
```

见到它就把这个 node 的**三样东西全部清空**：

1. `addr` 覆盖（对应 `AddrChanged(node, address(0))`，同一次交易里也会发）
2. 全部 `text` 记录（**不会**为每个 key 重复发 `TextChanged`）
3. 「谁把这个 node 设成了主名字」（对应 `PrimaryNameCleared`）

`addr` 覆盖被清掉之后，`addr(node)` **回落到当前 NFT owner**，不是返回 0。索引器重建状态时要按这个语义算，不能把「覆盖为 0」当成「解析结果为 0」。

## 4. 积分只认 `PointsChanged`

`SPEC 6.8` 明确：索引器只把 `PointsChanged` 当作余额来源。不要从 `NameMinted` 或 `Rated` 推算积分。

```
PointsChanged(bytes32 indexed aiId, address indexed user, int256 delta, uint256 newBalance, bytes32 indexed reason)
```

- `newBalance` 是写入后的值，可以直接用，不必自己累加。
- `reason` 是右填充的 `bytes32`：`CHECKIN`、`MINT`、`FOLLOW`、`RETWEET`、`LIKE`、`COMMENT`；`spend`/`refund` 用调用方传入的 reason。
- `refund` 有额度上限（owner 2026-11-20 裁决）：只能退同一 `reason` 下累计 `spend` 且未退回的部分。索引器若要核对 spender 的行为，读 `spendableOf(aiId, reason)`。

## 5. `tokenURI` 很贵，只缓存不吃

`HahaMetadata.build` 是 `view`，用户 `eth_call` 不付 gas，但**链上再调用它会非常贵**（拼 5.3 KB 前缀 + Base64）。

- 索引器应当在**第一次读到**时就缓存，之后按 `Transfer` / `RecordsCleared` 失效。
- 不要在铸造或转账交易里调用 `tokenURI`。`SPEC SVG.md` 明确禁止。

## 6. 一次转让会发多少个事件

理解一次转让的完整事件序列，对索引器很有用：

```
1. Transfer(from, to, tokenId)          // ERC-721，owner 已更新
2. Transfer(node, to)                    // EIP-137，注册表 owner 已同步
3. AddrChanged(node, address(0))         // 只有原本有覆盖时才发
4. RecordsCleared(node)                  // 一定发
5. PrimaryNameCleared(user, node)        // 只有原本有主名字时才发
6. Transfer(prevAgentOwner, 0, agentId)  // 只有原本有 agent 时才发（burn）
7. AgentReset(nameTokenId, agentId, previousOwner)  // 同上
```

顺序是固定的：`syncOwner` → `clearRecords` → `deactivate`。

## 7. 补充规格 v1.1 新增的事实（积分模块、小游戏、ERC-8004）

`docs/specs/SUPPLEMENT-points-games-8004v2.md` 给主网部署前加了 earner、小游戏、评价分、激活分、operator / generation / `operatorAiId`。索引器要认这些**新事件与字段**。

### 7.1 `AgentActivated` 多了两个字段

```solidity
event AgentActivated(
    uint256 indexed agentId,
    uint256 indexed nameTokenId,
    address indexed owner,
    bytes32 operatorAiId,   // 新增：激活时操作者的 .ai
    uint64 generation,      // 新增：这个名字的第几任 agent
    string agentURI
);
```

- **历代 agent 没有链上数组**，只能靠 `AgentActivated` + `AgentReset` 重放。按 `(nameTokenId, generation)` 建「历年 agent」列表。
- `operatorAiId` 是名片上 `.ai` 的**链上真值**。网站展示以它为准，不要读 JSON 里的一句话。
- `generation` 从 1 起，每次重新激活 +1，**不减、不回收**（`nameGeneration` 只增不减）。

### 7.2 积分多了 `Earned` 事件与新的 reason

`earn` 注册表（`setEarner`）发出的分，用独立事件 `Earned`，`reason` 就是 `actionId`：

```
Earned(bytes32 indexed actionId, bytes32 indexed aiId, address indexed user, uint256 amount, bytes32 uniqueKey, uint256 newBalance)
```

`actionId` 是右填充的 `bytes32`，例如 `REVIEW_GIVE`、`REVIEW_RECEIVE`、`ACTIVATE`。`uniqueKey` 是动作的去重键（评价对子、游戏的 `bytes32(sessionId)` 之类），**不是 `nameTokenId`**。

余额仍然**只认 `PointsChanged`**（见第 4 节）。`Earned` 是给「谁在哪个动作上发了多少分」做聚合用的，`newBalance` 与 `PointsChanged.newBalance` 一致。

`PointsChanged.reason` 的取值新增：`REVIEW_GIVE`、`REVIEW_RECEIVE`、`ACTIVATE`，以及游戏发分时的游戏 `gameId`（`bytes32`）。游戏发分的 `reason` 就是那个游戏的 `gameId`，不是 `GAME`。

### 7.3 游戏事件

```
GameRegistered(bytes32 indexed gameId, address indexed module, uint256 maxScorePerRound, uint256 perAiDailyPoints, uint256 globalDailyPoints)
RoundOpened(uint256 indexed sessionId, bytes32 indexed gameId, bytes32 indexed aiId, address player, uint64 openDay)
RoundClaimed(uint256 indexed sessionId, bytes32 indexed gameId, bytes32 indexed aiId, address player, uint256 points)
```

- `sessionId` 只增不减、不回收。
- 分数**只来自游戏合约的 `scoreOf(sessionId)`**，玩家不能自报。索引器核对时读 `scoreOf`，不要信任任何交易 calldata 里的分数。

### 7.4 `statusOf` 是 agent / 网站读任务状态的入口

`statusOf`（按 `.ai` 解析）与 `statusOfAi`（按已知 `aiId`）一次返回：余额、当日各任务次数（含 `gameRoundsToday`、`reviewsGivenToday`、`reviewsReceivedToday`）、`nextResetAt`。`nextResetAt == (currentDay + 1) * 86400`。**没有铸造冷却字段**，冷却另读 `HahaRegistrar.nextMintAt`。

### 7.5 评语仍然只在事件里

评语字符串只存在 `Rated` 事件里，storage 读不到（合约没有任何返回评语的 getter）。这没变，只是再强调一次。

## 8. 没有的东西

阶段一**没有**这些，索引器不要去找：

- 时间相关的字段：没有 `expiry`、没有 `renew`、没有宽限期。`available` 只表示「还没被铸过」。
- 多链地址：没有 `addr(bytes32, uint256)`。
- `contenthash`、`pubkey`、ABI、通配符解析。
- `addr.reverse` 命名空间。主名字用 `HahaResolver.setPrimaryName`，反向查询用 `primaryName(address)`。
- 管理员拉黑、冻结、暂停。这些权力**不存在**。
- 签名者 / EIP-712 / 社交任务的链上核实。
