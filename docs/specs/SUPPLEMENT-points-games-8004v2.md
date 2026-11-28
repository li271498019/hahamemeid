# 补充规格：积分模块、小游戏、ERC-8004 验证就绪

状态：主网部署前必须处理的补充规格。日期：2026-11-21。读者：合约开发者 D。

本文件审的是已经进 `main` 的实现（`HahaPoints`、`HahaReputation`、`HahaAgentIdentity`、`HahaRegistrar`、`HahaMarketplace`、`HahaDeployer`），对照 `docs/contracts/SPEC.md`、`docs/CHANGELOG.md` 和 `docs/website/PLAN.md`。ERC-8004 以 2026-11-21 的草案为准：<https://eips.ethereum.org/EIPS/eip-8004>。

合约仍然不可升级，没有代理。本文件要求改的，是**部署前**改。部署之后这些接口补不上。

相对 `SPEC.md` 的冲突，以本节下面这张表为准。表以外的行为，仍然以 `SPEC.md` 和既有 CHANGELOG 为准。

| 原来 | 本文件 |
| --- | --- |
| `SPEC 6.6`：`activateAgent` 不要求持有 `.ai`，买来的名字也能激活 | 激活时，名字 NFT 的当前持有地址必须通过 `aiIdentityOf`。没有 `.ai` 的地址可以持有、挂单、出售，不能激活 |
| `SPEC 6.7`：评分人只要有 `.ai`，且不是 owner、也不是 owner 的 `.ai` | 再加上：评分人当时持有至少一个 `.haha` / `.meme`；agent owner 当时也必须有 `.ai`；评分人的 `aiId` 不得等于该 agent 记录的 `operatorAiId` |
| `SPEC 6.8`：只有签到、铸造、follow、like、retweet、comment，外加 spender 扣分 | 保留这些，数值与次数不变。另加 earner 注册表，用来发评价分、激活分和游戏分 |
| `SPEC 8`：管理员只有三项 | 增加第四项：登记或停用 earner，以及给 spender 设每日预算。管理员仍然不能直接给某个地址加分 |
| `SPEC 9`：将来的 Validation Registry 只读 `isActive`、`agentOfName`、`nameTokenIdOf` | 不够。身份合约还要提供 `isAuthorized`、`generation`、`operatorAiId`。见第 3 节 |

明确不改的决定：

- 社交任务继续伪验证。不恢复 EIP-712，不设签名者，不加后端。
- 积分不是代币，不能 transfer，账本键是 `aiId`。
- 名字转让继续 burn agent NFT。不要改成 ERC-8004 那种把 agent NFT 转给买方。
- 不实现 `giveFeedback` / `revokeFeedback` / `appendResponse` 的兼容包装。
- 转账钩子（`syncOwner` → `clearRecords` → `deactivate`）里不调用 `HahaPoints`。
- 不把 `block.timestamp`、`prevrandao`、`blockhash` 单独当作会发分的随机数。
- 所有「每天」的次数只用 UTC 日序号 `block.timestamp / 86400`，在 UTC 0 点一起归零。禁止从上次操作起算的滚动 24 小时。
- 铸造冷却留在 `HahaRegistrar`，不进积分表，也不进 `statusOf`。行为不改，见「铸造规则」。

## 0. 审阅结论

下面三节是对第 3、4、5 问的直接结论。细节在对应章节。第 6 节是主网前问题清单。

**验证合约（第 3 问）。** 现有身份合约已经具备：`agentId` 从 1 递增且 burn 不回收、`ownerOf`、`isActive`、`agentOfName`、`nameTokenIdOf`、`getAgentWallet`、active 时的 `tokenURI`、`AgentActivated` / `URIUpdated` / `AgentReset`。一个按 `agentId` 记账、并且在请求和响应时都检查 `isActive` 的 Validation Registry，不会把旧验证算到新的 `agentId` 上。

它还缺三样，缺了就只能在部署前补：

1. operator。agent NFT 的 `approve` / `setApprovalForAll` 全部 `revert Soulbound`，`isApprovedForAll` 永远是 false。ERC-8004 规定 `validationRequest` 由 owner **或** operator 发起。现在只有 owner 走得通。
2. generation。burn 之后 `nameTokenIdOf(旧 agentId)` 仍然指着这个名字。只靠「id 不复用」挡得住「算到新 id 上」，挡不住「按名字把旧验证算到新持有人头上」。
3. `operatorAiId`。激活时不读 `.ai`，事件和 storage 里都没有操作者身份。名片 JSON 是持有人自己写的，合约不核对。

声誉合约**不用**改来存放验证分。它没有写入口，部署后也不能加。验证分放在将来单独部署的 Validation Registry 里。网站把 `getScore` 和验证合约的 `getSummary` 并排显示。不要做一层假装兼容的包装。

**声誉与转让（第 4 问）。** 维持「转让就 burn」。ERC-8004 允许转让 agent NFT，那会把信誉变成可以买卖的资产。我们卖的是名字，不是上一代操作者的信任。代码已经这么做了：`HahaRegistrar._update` 在每一次已有 token 的 owner 变更里调用 `deactivate`，包括转给自己、本市场 `buy`、`approve` 之后由被授权人转走、以及任何外部市场的 `transferFrom`。`agentId` 不回收。`getScore(旧 id)` 和 `Rated` 事件都还在，新激活从 `(0, 0)` 开始。只 `approve`、不转移，不会 burn。

持有人可以免费烧掉差评再激活。历史要靠事件看得见，不能只显示当前分数。见第 4 节。

**身份锚（第 5 问）。** 同意这条工作建议，并按代码核对过：

- agent 身份和信誉挂在 `.haha` / `.meme` 名字的**当前一代** `agentId` 上，和名字 1:1，转让就断代。
- 每个评分人、整本积分账，键都是 `.ai`。一个 `.ai` 可以拥有很多名字，签到不会因为名字多而加倍。
- 名片记录操作者的 `.ai`。这一条**代码还没做**，第 3 节的 `operatorAiId` 就是补它的。合约不解析 JSON。

不要把信誉改记到 `.ai` 上。那样一个人的多个 agent 会合成一个分数，卖掉其中一个名字也清不掉这个名字在页面上的信誉。

## 1. 积分规则与可扩展性

**总规则：积分只认 `.ai`。** 余额、每日次数、终身标记、评价对子、游戏局数、spender 的每日预算，键都是 `aiId`（`keccak256(handle)`，soulbound，一个人一个）。地址只用来调用 `aiIdentityOf`，解析出 `aiId` 之后就不再当账本键。名字 NFT、`agentId`、`nameTokenId` 都不拿来记账。同一个人卖掉一个名字再激活另一个，用的还是同一个 `aiId`，额度不重置。

参与条件仍然要当时持有至少一个 `.haha` 或 `.meme`：那是「能不能领」的门槛，不是账本的键。门槛看的是 `registrar.balanceOf(解析出这个 .ai 的那个地址)`。

### 1.1 当前代码审计

参与条件是：调用当时 `aiIdentityOf` 成功，并且 `registrar.balanceOf(该地址) > 0`。余额记在 `aiId` 上，没有 `transfer`。卖掉最后一个名字后余额还在，但不能签到、领社交分、被 `spend`。`refund` 不要求当时持有名字。

日序号一律是 `uint64(block.timestamp / 86400)`，见 `HahaPoints._currentDay`。这是 UTC 日桶，不是「从上次领取起 24 小时」。北京时间的日界是 08:00。`day 0` 是合法日。

下面这张表是**现在链上代码的行为**，不是目标。目标在第 1.3 节。

| 活动 | 分数 | 每日上限 | 重置规则（代码里实际写成的） | 记账键 | 当前代码 | D 要不要改 |
| --- | --- | --- | --- | --- | --- | --- |
| 签到 | 30 | 1 | UTC 日桶。`_hasCheckedIn[aiId] && _lastCheckInDay[aiId] >= day` 则拒绝。今天领过，要等到日序号变大 | `.ai` | `HahaPoints.checkIn` | 否 |
| 铸造奖励 | 10 | 3 | UTC 日桶。`DayCounter.dayIndex == day` 才沿用次数，否则当日次数视为 0。常量 `MINT_REWARDS_PER_DAY = 3`，管理员不能改次数 | `.ai` | `HahaPoints.creditMintReward`，由 `HahaRegistrar.register` 在铸成后调用 | 否。它已经是日任务 |
| 关注 | 30 | 无（终身 1 次） | 不清零。`_followClaimed[aiId]` | `.ai` | `HahaPoints.claimFollow` | 否 |
| 点赞 | 10 | 1 | UTC 日桶。`DayClaim.done && dayIndex == day` | `.ai` | `HahaPoints.claimLike` | 否 |
| 转发 | 10 | 1 | 同点赞 | `.ai` | `HahaPoints.claimRetweet` | 否 |
| 评论 | 10 | 1 | 同点赞 | `.ai` | `HahaPoints.claimComment` | 否 |
| 写出评价 | 0 | 无积分 | 无日界。每个 `(agentId, aiId)` 一条可修改记录 | 评分人的 `.ai` | `HahaReputation.rate` | 要新增为日任务 |
| 收到评价 | 0 | 无 | 无 | 无 | 没有这个发分路径 | 要新增为日任务 |
| 小游戏 | 0 | 无 | 无 | 无 | 没有游戏合约 | 要新增为日任务 |
| 激活分 | 0 | 无 | 无。激活本身可在 burn 之后重做，每次新 `agentId` | 名字 | `HahaAgentIdentity.activateAgent` | 要新增，但是终身一次，不做成日任务 |
| 扣分 / 退分 | 不发分 | 无每日上限 | 无日界 | `.ai` | `HahaPoints.spend` / `refund` | 不是日任务。若加 spender 预算，预算的「今天」必须用同一个日序号 |

签到用 `>= day`，点赞三项用 `== day`。两边都是日桶，不是滚动 24 小时。`>=` 多挡住「存储里的日序号落在未来」这一种情况。不要为了和 `==` 对齐，把签到改成从上次时间戳加 86400。

积分表里的每日任务没有一条用滚动 24 小时。评价、收评价、小游戏、激活分是缺失，不是重置写错。铸造冷却不在这张表里，见下节。

### 铸造规则

铸造冷却属于注册器的抢注限制，和积分合约无关。本轮不改。

- 常量 `HahaConstants.COOLDOWN = 3600`。
- `HahaRegistrar.register` 用 `lastMintAt[aiId]`。距上次不足 3600 秒就 `CooldownActive(last + 3600)`。两个 TLD 共用这一个时间戳。
- `nextMintAt(aiId)` 返回 `lastMintAt + 3600`；从没铸过返回 0。
- `adminMint` 不写 `lastMintAt`，也不发铸造奖励。
- 铸造奖励的每日 3 次在 UTC 0 点归零，冷却不归零。23:30 UTC 铸过之后，00:00 奖励次数已经是 0，00:30 之前 `register` 仍然因为冷却失败。这是两道门，积分表只列奖励那一道。
- `statusOf` 不返回冷却。agent 读 `HahaRegistrar.nextMintAt`。

`spend` / `refund` 只允许 `isSpender` 的合约。扣分和可退额度都按 `(aiId, reason)`，不按地址。`refund` 不能超过该 `.ai` 在这个 `reason` 下曾经 `spend` 且未退回的额度。授权 spender **不能凭空造分**，但可以把这个 `.ai` 的余额扣到 0，目前没有每日上限。下面要加的 spender 每日预算同样按 `aiId`。

没有的东西：

- 没有 earner。除了上面六个写死的函数和 `refund`，没有任何途径再加分。游戏、评价、激活都接不进来。
- 没有 `statusOf`。网站规划第 5 节要的「一次读完冷却、今日次数、是否签到、余额」，现在要拼十几次 `eth_call`。
- 评价和激活不加分。`HahaReputation` 和 `HahaAgentIdentity` 的构造函数里没有 points 地址。

`refund` 的额度限制是对的，保留。本文件要补的是**发分**这一侧，以及 spender 的每日预算。

### 1.2 模块注册表

发分和扣分都走「管理员授权的合约 + `bytes32` action id + 上限」。上限写在 `HahaPoints` 里，不写在游戏合约里。游戏合约换掉、写坏、被盗，都只能在上限之内动分数。

```solidity
enum KeyMode {
    None,      // 只受每日次数和全网预算约束，日切只清次数
    PerDay,    // 同一个 uniqueKey 每个 UTC 日一次，日切后可以再领
    Lifetime   // 同一个 uniqueKey 终身一次，日切不清
}

struct EarnerConfig {
    address module;            // 唯一允许调用 earn 的合约
    uint256 points;            // 每次成功发放的分数
    uint64 perUserDailyCap;    // 每个 aiId 每个 UTC 日最多成功几次
    uint256 globalDailyPoints; // 该 action 全网每个 UTC 日最多发出多少分
    KeyMode keyMode;
    bool requireName;          // true 时，user 当时必须持有至少一个名字
    bool enabled;
}

struct SpenderBudget {
    uint256 perUserDailyPoints; // 每个 aiId 每个 UTC 日，该 spender 最多扣多少分（按 gross）
    uint256 globalDailyPoints;  // 全网每个 UTC 日，该 spender 最多扣多少分（按 gross）
}
```

硬顶，管理员也不能超过。超过就 `revert ParamTooLarge`。这六项目前的 `setPointParams` 上限 `999999999` **不要改**，那个权力是已经拍板的。硬顶只约束新的 earner 和 spender 预算。

| 常量 | 值 | 含义 |
| --- | --- | --- |
| `MAX_EARNER_POINTS` | 100 | 单个 earner action 每次最多发这么多分 |
| `MAX_PER_USER_DAILY` | 50 | `perUserDailyCap` 的上限 |
| `MAX_GLOBAL_DAILY_POINTS` | 1_000_000 | 单个 earner action 每天全网最多发出的分 |
| `MAX_MODULES` | 32 | earner action 的个数上限，防止 `statusOf` 和枚举被撑爆 |
| `MAX_SPEND_USER_DAILY` | 1_000_000_000 | 单个 spender 对单个 `aiId` 的每日 gross 扣分上限 |
| `MAX_SPEND_GLOBAL_DAILY` | 10_000_000_000 | 单个 spender 的全网每日 gross 扣分上限 |

spender 的上限比 earner 高，是因为保留名拍卖的单笔出价可能很大。earner 是印分，上限必须紧。

```solidity
function setEarner(bytes32 actionId, EarnerConfig calldata cfg) external; // onlyAdmin
function setSpender(address spender, bool allowed) external;               // 保留
function setSpenderBudget(address spender, SpenderBudget calldata budget) external; // onlyAdmin

/// @notice 发分。业务条件不满足时返回 0，不 revert。
///         只有「调用者不是该 action 的 enabled module」或 actionId 非法时才 revert。
function earn(bytes32 actionId, address user, bytes32 uniqueKey) external returns (uint256 awarded);

function spend(address user, uint256 amount, bytes32 reason) external;
function refund(address user, uint256 amount, bytes32 reason) external;
```

`setEarner` 的规则：

- `actionId` 不能是 `bytes32(0)`，也不能是 `CHECKIN`、`MINT`、`FOLLOW`、`LIKE`、`RETWEET`、`COMMENT`。这六个 reason 留给现有函数。
- `enabled == true` 时：`module` 有代码，`points` 在 `1 .. MAX_EARNER_POINTS`，两个 cap 都在硬顶之内且大于 0，`globalDailyPoints >= points`。
- `enabled == false` 时不检查代码。停用必须永远做得成，和现在的 `setSpender(account, false)` 同一个理由。
- 停用、换 module、改分值，都不删除 key 记录。`PerDay` 的「今天领过」靠存下的日序号和今天比较，日切自然失效，不用删 storage。`Lifetime` 的标记永远留着。换一个新模块、沿用同一个 `actionId`，领过的激活分领不了第二次。
- 管理员没有 `mintTo(user, amount)`。要加分，只能登记一个模块，由那个模块调用 `earn`。
- 每日次数和全网预算的「今天」就是 `block.timestamp / 86400`。禁止用 `block.timestamp - lastTime < 86400`。

`earn` 的顺序。先写状态再返回，函数内不要外部调用，这样声誉和身份可以安全地在最后一步调用它。

1. `msg.sender` 必须等于该 action 当前 `enabled` 的 `module`，否则 `NotEarner`。
2. 读 `aiIdentityOf(user)`。失败、`requireName` 但不持有名字、`points == 0`、action 已停用：返回 0，不写 storage。
3. `KeyMode.PerDay` 或 `Lifetime` 时，`uniqueKey == bytes32(0)` 返回 0。`PerDay` 且该 key 存的日序号等于今天，返回 0。`Lifetime` 且该 key 已标记，返回 0。**先不要写 key。**
4. 当日该 `aiId` 的成功次数已经达到 `perUserDailyCap`，或者当日已发出的分再加 `points` 会超过 `globalDailyPoints`：返回 0，不写 key。被次数挡住的那一对，今天如果后来还有额度，或者到了下一日，仍然可以领。
5. 写 key（`PerDay` 写下今天的日序号，`Lifetime` 置永久标记）、写当日次数、写当日已发分数、加余额。当日次数存在带 `dayIndex` 的槽里，跨日读取时视为 0。
6. 发 `PointsChanged`，`reason` 就是这个 `actionId`。再发下面的 `Earned`。

返回 0 的路径不发 `PointsChanged`。

`spend` 在现有检查之外增加：该 spender 必须已经 `setSpenderBudget`，否则 `BudgetNotSet`。本次金额加上该 `aiId` 本 UTC 日已被这个 spender 扣过的 gross、以及全网本 UTC 日 gross，任一超预算就 `revert SpendBudgetExceeded`。这里的「本日」同样是 `block.timestamp / 86400`，不是滚动 24 小时。记账的是 gross：`refund` **不**把预算退回去。否则一个坏合约可以 `spend` / `refund` 来回刷，把每日上限洗掉。`refund` 原有的 `spendable` 上限保持不变。

拍卖合约的预算要按「一天里所有出价之和」来设，包括后来被退回的那些出价，不是按「最后锁住的净额」来设。设小了，拍卖会在预算处 revert，这是安全失败，不是丢钱。

事件：

```solidity
event Earned(
    bytes32 indexed actionId,
    bytes32 indexed aiId,
    address indexed user,
    uint256 amount,
    bytes32 uniqueKey,
    uint256 newBalance
);
event EarnerUpdated(
    bytes32 indexed actionId,
    address indexed module,
    uint256 points,
    uint64 perUserDailyCap,
    uint256 globalDailyPoints,
    uint8 keyMode,
    bool requireName,
    bool enabled
);
event SpenderBudgetUpdated(
    address indexed spender,
    uint256 perUserDailyPoints,
    uint256 globalDailyPoints
);
```

索引器继续**只**用 `PointsChanged` 重建余额。`Earned` 是动作明细。

只读：

```solidity
function earner(bytes32 actionId) external view returns (EarnerConfig memory);
function earnerActionIds() external view returns (bytes32[] memory);
function userEarnedToday(bytes32 actionId, bytes32 aiId) external view returns (uint64 count);
function globalPointsToday(bytes32 actionId) external view returns (uint256);
function uniqueKeyUsed(bytes32 actionId, bytes32 aiId, bytes32 uniqueKey) external view returns (bool);
function pairClaimedToday(bytes32 actionId, bytes32 aiId, bytes32 uniqueKey) external view returns (bool);
function spenderBudget(address spender) external view returns (SpenderBudget memory);
function spenderUsedToday(address spender, bytes32 aiId) external view returns (uint256 userPoints, uint256 globalPoints);
```

### 1.3 统一日任务表

日任务和签到同一套日切：日序号 `block.timestamp / 86400`，下一个重置时刻是 `(currentDay + 1) * 86400`，也就是下一个 UTC 0 点。不满 24 小时但过了 0 点，次数归零。满了 24 小时但仍在同一个 UTC 日里，次数不归零。

写出评价、收到评价、小游戏领分，都是这种日任务。铸造奖励也是，次数已经按这个规则写在 `creditMintReward` 里。铸造冷却不在本表。

下面的建议分值是部署后管理员写入 earner 的初始配置，受第 1.2 节硬顶约束。签到、铸造奖励、关注、点赞、转发、评论的分值和次数保持现有实现，不搬进 earner。

| 活动 | 分数 | 每日上限 | 重置规则 | 记账键 | key | D 要不要改 |
| --- | --- | --- | --- | --- | --- | --- |
| 签到 | 30 | 1 | UTC 0 点 | `.ai` | 无。内置 | 否 |
| 铸造奖励 | 10 | 3 | UTC 0 点 | `.ai` | 无。内置 | 否 |
| 关注 | 30 | 终身 1 次 | 不清零 | `.ai` | 无。内置 | 否 |
| 点赞 | 10 | 1 | UTC 0 点 | `.ai` | 无。内置 | 否 |
| 转发 | 10 | 1 | UTC 0 点 | `.ai` | 无。内置 | 否 |
| 评论 | 10 | 1 | UTC 0 点 | `.ai` | 无。内置 | 否 |
| 写出评价 `REVIEW_GIVE` | 5 | 5 个不同 agent | UTC 0 点。同一对当天一次，次日可再领 | 评分人 `.ai` | `PerDay`，`bytes32(agentId)` | 要新增 |
| 收到评价 `REVIEW_RECEIVE` | 5 | 5 个不同评分人 | UTC 0 点。同一对当天一次 | 接收人 `.ai` | `PerDay`，`keccak256(abi.encode(agentId, raterAiId))` | 要新增 |
| 小游戏 `GAME_<短名>` | 该局链上分数，例如 63 分就是 +63 | 所有游戏合计 3 局 | UTC 0 点。局数在开局时扣。见第 2 节 | `.ai` | 一次 `claim(sessionId)`，没有参与/胜利两个动作 | 要新增。3 局跨游戏合计，owner 已确认 |
| 激活 `ACTIVATE` | 20 | 无。每个 `.ai` 终身 1 次 | **不清零。** 卖掉名字再激活另一个名字也不再发 | `.ai` | `Lifetime`，常量 `ACTIVATE_ONCE`，不是 `nameTokenId` | 要新增。owner 已确认 |
| spender 每日预算 | 不发分 | 该 `.ai` 的每日 gross，另有全网 gross | UTC 0 点。`refund` 不把额度退回 | `.ai` | 现有 `spend` 没有每日上限，只按 `(aiId, reason)` 限制可退额度 | 要新增。键是 `aiId`，不是地址 |

全网每日预算（安全阀，不是用户看到的任务次数）：`REVIEW_GIVE` 与 `REVIEW_RECEIVE` 各 50_000，`ACTIVATE` 100_000。每个游戏单独一个全网每日预算，初始建议 50_000，外加该游戏的 `maxScorePerRound`。预算在 UTC 0 点归零。

**已确认：** 小游戏每日 3 局是**所有已登记游戏加在一起**的上限，不是每个游戏各 3 局。计数器放在 `HahaPoints`，按 `aiId` 计，不放在单个游戏里。

评价的防刷，和「这是日任务」同时成立：

- **同一对一天一次。** 同一个评分人 `.ai` 对同一个 `agentId`，一个 UTC 日里写出评价只发 5 分一次。当天改星、改评语，第二次 `earn` 返回 0，不占新的名额。下一个 UTC 日，再调用 `rate`（包括改分）可以再发 5 分，当天最多 5 个不同 agent。这不是终身一次。
- **收评价同样按对、按日，也是 5 分。** key 记在接收人的 `aiId` 下，并带上评分人。当天最多 5 个不同评分人。同一个人当天改分不会让接收人再拿一次。次日这对可以再发。
- **不能自评，也不能同一个 `.ai`。** 这条不随日切失效。`rate` 在调用 `earn` 之前就 revert，见第 3 节。
- **评分人必须持有 `.ai` 和至少一个名字。** 接收人必须是 agent 的当前 owner，并且该地址当时持有 `.ai`。owner 没有 `.ai` 时，这次 `rate` 直接 revert，星星也不记。
- **给分和收分的每日上限分开算。** 给分达到 5 次之后，仍然可以评分（星星照记），只是 `earn` 返回 0。收分同理。不要因为积分发完了就让评分 revert。
- **激活是 20 分，每个 `.ai` 终身一次。** owner 已确认。不是每个名字一次，也没有「每天最多新领 5 个名字」。`uniqueKey` 用常量 `ACTIVATE_ONCE`（非零 `bytes32`），记在这个 `aiId` 下。第一次激活领到 20 分之后，卖掉该名字、再激活同一个或另一个名字，都返回 0。换钱包做不到，因为 `.ai` 是 soulbound。另一个 `.ai` 有自己的一次。`perUserDailyCap` 设为 1，只是多一道当日闸；真正挡住第二次的是 `Lifetime` key，日切不会把它打开。全网每天最多 100_000 分。
- 激活分在 `activateAgent` 成功写完状态并 `_mint` **之后**调用。`deactivate` 和 `HahaRegistrar._update` 禁止调用 `earn`。积分合约一 revert，不能把用户的 NFT 卡死。

`requireName` 对这三个 action 都是 true。module 分别是 `HahaReputation`、`HahaReputation`、`HahaAgentIdentity`。

`HahaReputation.rate` 和 `HahaAgentIdentity.activateAgent` 用 `try/catch` 包住 `earn`：

```solidity
try IHahaPoints(points).earn(actionId, user, uniqueKey) returns (uint256) {} catch {}
```

在管理员还没 `setEarner` 的时候，`earn` 会 `NotEarner`。`try/catch` 把这次失败吃掉，评分和激活照常成功，只是没分。`earn` 内部返回 0 的那些情况不会进 `catch`。这样积分模块的故障不会把声誉和身份的主路径打断。

游戏不要用 `try/catch` 把 `NotEarner` 吃掉。游戏应该让这笔交易失败，让用户看见还没授权。见第 2 节。

声誉合约需要新的 immutable `points`。身份合约需要新的 immutable `points` 和 `aiRegistry`。`HahaPoints` 不需要反过来引用它们。部署顺序仍然用现有脚本的 nonce 预测，不要改回「一个工厂里 `new` 全部合约」。`HahaDeployer` 的地址自洽检查加上这三项。

### 1.4 `statusOf`

```solidity
struct PointsStatus {
    bytes32 aiId;
    uint256 balance;
    bool holdsAi;
    bool holdsName;
    uint64 currentDay;           // block.timestamp / 86400
    uint64 nextResetAt;          // (currentDay + 1) * 86400，所有日任务共用的下一个 UTC 0 点
    uint64 checkInToday;         // 0 或 1
    uint64 mintRewardsToday;     // 0..3
    uint64 likeToday;            // 0 或 1
    uint64 retweetToday;
    uint64 commentToday;
    uint64 gameRoundsToday;      // 0..3，所有游戏合计
    uint64 reviewsGivenToday;    // 0..5
    uint64 reviewsReceivedToday; // 0..5
    uint8 mintRewardsPerDay;     // 恒为 3
    uint8 gameRoundsPerDay;      // 恒为 3。所有游戏合计，owner 已确认
    bool followClaimed;          // 终身。nextResetAt 到了也不变
}

struct ActionStatus {
    bytes32 actionId;
    uint256 pointsEach;
    uint64 todayCount;           // 该 .ai 这个 UTC 日已经成功几次
    uint64 dailyCap;
    uint64 nextResetAt;          // 与 PointsStatus.nextResetAt 相同
    uint256 globalPointsToday;
    uint256 globalDailyPoints;
    uint8 keyMode;               // KeyMode
    bool enabled;
    bool underCap;               // 今日个人次数和全网预算都还没满；不检查某一个 uniqueKey
}

function statusOf(address user) external view returns (PointsStatus memory);
function statusOfAi(bytes32 aiId) external view returns (PointsStatus memory);
function actionStatus(address user, bytes32[] calldata actionIds) external view returns (ActionStatus[] memory);
```

`statusOf` 不 revert。没有 `.ai` 时 `holdsAi = false`，余额和布尔都是 0 / false。

`statusOfAi` 用 `.ai` 注册表的 `ownerOf(uint256(aiId))` 找回地址，再走 `statusOf`。这一步 `try/catch`：注册表 revert 时，只返回该 `aiId` 上的余额和签到 / 社交 / 铸造计数，`holdsAi` 和 `holdsName` 为 false。handle 若被币安侧改掉，`aiId` 对不上现任 token，余额仍然要读得出来。

`nextResetAt` 永远是 `uint64((currentDay + 1) * 86400)`，跟这个地址今天签没签过无关。没有 `.ai` 时也返回这个时间戳，方便界面显示下一次日切。不要返回「上次签到 + 24 小时」，也不要返回北京时间 0 点。

内置日任务的今日次数放在 `PointsStatus` 里：签到、铸造奖励、点赞、转发、评论，加上 `gameRoundsToday`、`reviewsGivenToday`、`reviewsReceivedToday`。关注只有 `followClaimed`。激活的「今天新领了几个」走 `actionStatus`，某个名字领过没有走 `uniqueKeyUsed`。某一对评价今天领过没有，用 `pairClaimedToday`。

`gameRoundsToday` 读 `HahaPoints` 里那一个跨游戏计数器，不要把各游戏自己的局数加起来。评价两项读 `REVIEW_GIVE` / `REVIEW_RECEIVE` 的当日成功次数。

铸造冷却不在这个结构里。agent 要看还能不能铸，另外调用 `HahaRegistrar.nextMintAt`。

`actionStatus` 的数组由调用方传入，长度上限 16，超出 `revert TooManyActions`。网站和 agent 先读 `earnerActionIds()`，再对自己关心的 id 做这一次调用。不要在 `statusOf` 里循环全部模块，避免以后模块增加把一次 `eth_call` 的 gas 撑高。

`skill.md` 的「读接口」用 `statusOf` 覆盖：余额、日任务今日次数、`gameRoundsToday`、`reviewsGivenToday`、`reviewsReceivedToday`、follow 是否已领、`nextResetAt`。日任务什么时候重置，只看 `nextResetAt`。能不能再铸名字，读 `HahaRegistrar.nextMintAt`，不读积分合约。

## 2. 小游戏

网站规划第 5 页写的是：第一期占位，正式游戏在主网前通过积分 earner 接上。游戏合约以后单独部署。主网前必须先有第 1 节的注册表。

没有「参与」和「胜利」两个动作。每个游戏自己定怎么算分。一局结束时合约算出的分数就是这一局的积分。一局打到 63，领取时就是 +63。用户用网站复制给 agent 的指令发一笔 `claim(sessionId)`，不在网页上签名，也没有后端代领。

**已确认：** 每个 `.ai` 每个 UTC 日最多 **3 局，所有游戏合计**。不是每个游戏各 3 局。计数器只有 `HahaPoints` 里的一个，键是 `aiId`。

### 2.1 分数从哪来

**(a) 游戏合约自己算出分数并记在局里。** 开局拿到可验证的随机种子，着法在链上提交，结算时合约按规则把分数写入该 `sessionId`。领取只读这份记录。

**(b) 用户或链下签名者申报一个分数。** 不采用。这和「没有签名者」冲突，也没法区分真分数和自报分数。

随机种子：

- 开局用 commit-reveal，或 Chainlink VRF v2.5。不要用 `block.timestamp`、`prevrandao`、`blockhash` 单独当种子。
- 两人局：双方都 commit 之后至少隔 2 个区块再揭示。同一笔交易里又 commit 又 reveal，禁止。
- 单人、结果靠运气的局：用 VRF v2.5。只靠玩家自己的 commit，输的人可以不揭示。
- VRF 订阅由该游戏合约自己付。只用 v2.5。编写日 BNB Chain 主网 coordinator 是 `0xd691f04bc0C9a24Edb78af9E005Cf85768F694c9`，官方 LINK 是 `0x404460C6A5EdE2D891e8297795264fDe62ADBB75`。部署前对照 <https://docs.chain.link/vrf/v2-5/supported-networks>。不要给管理员加「给 VRF 充值」的函数。

### 2.2 一局怎么走

局号由 `HahaPoints` 发，游戏合约不能自己挑。

```solidity
uint256 public constant GAME_ROUNDS_PER_DAY = 3; // 所有游戏合计，按 aiId。owner 已确认

struct GameConfig {
    address module;
    uint256 maxScorePerRound;   // 管理员设定。单局分数超过这个数，领取失败
    uint256 perAiDailyPoints;   // 该游戏对单个 .ai 的每日分数上限
    uint256 globalDailyPoints;  // 该游戏全网每日分数上限
    bool enabled;
}

function registerGame(bytes32 gameId, GameConfig calldata cfg) external; // onlyAdmin
function beginRound(bytes32 gameId, address player) external returns (uint256 sessionId);
function claimRound(uint256 sessionId) external returns (uint256 awarded);

function scoreOf(uint256 sessionId) external view returns (uint256 score, bool settled);
```

`registerGame`：`module` 有代码；`maxScorePerRound` 在 `1 .. 1000`；`perAiDailyPoints` 和 `globalDailyPoints` 都大于 0，且不超过 `MAX_GLOBAL_DAILY_POINTS`（1_000_000）。`1000` 是单局硬顶，63 这样的分数用得了，管理员不能把一局收成一百万。停用时不检查代码。

`beginRound` 只允许该 `gameId` 的 `module` 调用：

1. 解析 `player` 的 `.ai`。没有 `.ai` 或不持有名字，revert。
2. 本 UTC 日该 `.ai` 已经开过 3 局（含其他游戏），revert `DailyRoundsSpent`。
3. 局数加 1。这一步就扣掉当日名额。弃局、打不完、过了 0 点没领，名额都不退。这样不能先打很多局、再挑最高的 3 局来领。
4. `sessionId` 用合约内递增 nonce，只增不减。记下 `gameId`、`aiId`、`player`、`openDay`、`claimed = false`。

游戏合约在 `beginRound` 之后把种子和着法都绑在这个 `sessionId` 上。结算时把自己算出的分数写入 `scoreOf`。未结算时 `settled = false`。

`claimRound` 没有分数字段。调用者必须是该局的 `module`。它向游戏读 `scoreOf(sessionId)`：

1. 未结算、`sessionId` 不存在、已经领过：revert。
2. `currentDay != openDay`：revert `SessionExpired`。**过期规则选定为：只能在开局的那个 UTC 日领取。** 没有跨日宽限，也没有滚动 24 小时。23:50 开的局要在当天 0 点前领完，否则作废，局数不退。
3. `score > maxScorePerRound`：revert `ScoreTooHigh`。不改成发一个被砍过的数。发出去的分必须等于合约记下的分数。
4. 加上这一分数会超过该游戏的 `perAiDailyPoints` 或 `globalDailyPoints`：revert。这两个预算用同一个日序号，0 点归零。
5. 标记已领，给开局时记下的那个 `aiId` 加上 `score`。`PointsChanged` 的 `reason` 是 `gameId`。`delta` 等于记下的分数。`player` 地址只用来核对这笔 `claim` 是不是该钱包发的，不作为余额的键。

用户的指令只调用游戏的 `claim(uint256 sessionId)`。游戏内部读自己的存储再调用 `claimRound`。用户交易里不出现分数。

```solidity
interface IHahaGame {
    function pointsContract() external view returns (address);
    function gameId() external view returns (bytes32);
    function scoreOf(uint256 sessionId) external view returns (uint256 score, bool settled);
    function start() external returns (uint256 sessionId);
    function claim(uint256 sessionId) external returns (uint256 awarded);
}
```

一个游戏只有一个 `gameId`。不要再拆 PLAY / WIN。`setEarner` 的固定分值路径不用于游戏。评价和激活用 `earn`，游戏用 `beginRound` / `claimRound`。

网站给 agent 的指令是两段：开局 `start()`，结算并领取 `claim(sessionId)`。`sessionId` 以开局交易的返回值或 `RoundOpened` 事件为准。

### 2.3 威胁

| 威胁 | 结论 |
| --- | --- |
| 机器人打到规则允许的最高分 | 接受。每个 `.ai` 每天最多 3 局，每局不超过 `maxScorePerRound`，还要过该游戏的每日预算。机器人还得持有币安 soulbound `.ai` |
| 女巫多开 | 每一份额度都要一个 `.ai`。多铸名字不会多出局数。多开 `.ai` 的成本在币安身份 |
| 用户自己填一个分数 | 做不到。`claimRound` 不接收分数。分数来自游戏合约的 `scoreOf` |
| 重放同一局 | `sessionId` 只发一次，`claimed` 之后再领 revert。nonce 不回收。过了 UTC 0 点未领的局也不能补领 |
| 先打很多局，领最高的 3 个 | 做不到。局数在 `beginRound` 就扣，第 4 次开局 revert |
| 把高分留到第二天领，吃第二天的预算 | 做不到。领取日必须等于开局日 |
| 出块者改着法 | commit 在前，至少隔 2 个区块再揭示。种子来自 VRF 时，出块者看不到未揭示的 VRF 结果 |
| 游戏合约写坏或被换掉，`scoreOf` 返回任意大数 | 单局超过 `maxScorePerRound` 的领取直接失败。没超过的，每个 `.ai` 每天最多 3 局，并且该游戏还有 `perAiDailyPoints` 和 `globalDailyPoints`。管理员 `registerGame(..., enabled: false)` 可以停掉它。换合约不清 `sessionId` 的已领标记 |
| 管理员把 `maxScorePerRound` 设得很大 | 硬顶 1000。再往上 revert。这挡的是配置失误，不是管理员钥匙本身。管理员本来就能把签到分改到 `999999999` |
| 链下签名者伪造分数 | 没有这条路 |

游戏合约禁止 `tx.origin`。领取的收款人是开局时记下的 `player`，不是 `claim` 的 `msg.sender` 随便指定的地址。`claim` 的调用者必须是该 `player`。

## 3. ERC-8004 阶段二（Validation）还缺什么

对照的是草案里的 Validation Registry，不是让我们现在把验证合约部署出来。验证合约以后单独部署。它要能在我们的身份合约上完成这些事：

- `validationRequest(validator, agentId, requestURI, requestHash)` 只能由该 `agentId` 的 owner 或 operator 发起。
- `validationResponse(...)` 里的 `response` 是 0 到 100。响应者必须是请求里指定的 validator。
- 记录按 `agentId` 和 `requestHash` 索引。
- 烧掉的 agent 上的验证，不能算到同一个名字后来的新 agent 上。

声誉草案（`giveFeedback` 等）我们继续不实现。`SPEC 6.7` 的偏离保留。

### 3.1 现有代码已经够用的部分

| 草案需要 | 现在 | 结论 |
| --- | --- | --- |
| 稳定且不复用的 `agentId` | `_nextAgentId` 从 1 开始只加不减。`deactivate` 不把它写回去 | 满足。burn 再激活得到新 id。不存在复用 |
| `ownerOf` | ERC-721。active 时是激活者 | 满足。burn 之后 `ownerOf` **revert**，不是返回 0 |
| `isActive` | `_active[agentId]`，burn 时删除 | 满足。验证合约必须先看它，再调用 `ownerOf` / `tokenURI` |
| `agentOfName` / `nameTokenIdOf` | 有。burn 时只删除正向的 `agentOfName`，**保留** `nameTokenIdOf` | 正向映射满足「这个名字现在没有 agent」。反向映射会把旧 id 继续指回名字，见下面的缺口 |
| `getAgentWallet` | active 时等于 `resolver.addr(nameTokenId)`，否则 0 | 满足我们自己的定义。不是草案里那套 EIP-712 `setAgentWallet`。验证合约不要假设这个地址证明过控制权 |
| 名片 URI | `tokenURI` 在 active 时返回持有人设的 `agentURI` | active 期间满足。burn 时 URI 被 `delete`，`tokenURI` revert |
| 事件 | `AgentActivated`、`URIUpdated`（与草案同名同形）、`AgentReset`，外加 ERC-721 `Transfer` 到 `address(0)` | 我们自己的验证合约读视图即可，不必等 `Registered` / `MetadataSet`。不要为了改名去动 `URIUpdated` |

`getAgentWallet` 跟着解析器走。持有人 `setAddr` 可以把它指到任意地址，没有签名证明。这是 `SPEC 6.6` 已有的偏离。验证和以后的 x402 若要付款，先在产品上写明「收款地址是名字的解析地址，不是一张签过名的 agent 钱包」。本文件不要求补 `setAgentWallet`。

### 3.2 必须在主网前补的缺口

每一条都给出最小接口。验证合约本身不在本阶段实现。

**缺口 A，阻塞。没有 operator。**

`HahaAgentIdentity` 把 `approve`、`setApprovalForAll`、`transferFrom`、`safeTransferFrom` 全部 revert。标准 ERC-721 的 operator 永远设不上。只检查 `ownerOf == msg.sender` 的验证合约能用，但任何「热钱包代发验证请求」都做不到，部署后也加不上。

不要用放开 `approve` 的办法来做。那会把 soulbound 打开。

```solidity
function setAgentOperator(uint256 agentId, address operator, bool allowed) external;
function isAuthorized(uint256 agentId, address account) external view returns (bool);

event AgentOperatorSet(uint256 indexed agentId, address indexed operator, bool allowed);
```

- 调用者是该 agent NFT 的当前 owner。agent 必须 active。
- `operator` 非 0，且不是 owner 本人。
- 每个 agent 最多 8 个 operator。超出 `revert TooManyOperators`。用计数器，不要为了设上限去维护一份 burn 时必须清空的数组。`false → true` 才加一，`true → false` 才减一。重复设置同一状态不改计数。
- `isAuthorized` 为真，当且仅当 active，并且 `account` 是 owner 或已被设为 operator。
- burn 之后不必遍历删除。`isAuthorized` 先看 `isActive`，inactive 一律 false。旧 mapping 留着也没有权限。
- `setAgentURI` 改为允许 `isAuthorized` 的地址调用，不再只允许 owner。
- 这些 operator **不能**转移 agent NFT。转移函数继续 revert。

将来的 `validationRequest` 用 `isAuthorized(agentId, msg.sender)` 作为唯一的准入检查，不要自己再读 `isApprovedForAll`。

**缺口 B，阻塞。没有 generation，反向映射在 burn 后还指着名字。**

`deactivate` 保留 `_nameOfAgent`，这是对的：索引器要能从旧 `agentId` 找回名字。副作用是，只调用 `nameTokenIdOf` 的人会以为这个已经烧掉的 agent 仍然「属于」现在的持有人。

`agentId` 不复用，已经保证旧验证不会出现在新 `agentId` 的账上。generation 解决的是另一件事：按**名字**聚合时，必须有一个链上的数来判断「这个 agent 是不是这个名字的当前一代」。不能把这件事留给每个消费者自己记得去看 `isActive`。验证合约一旦写错，它自己也不可升级。

```solidity
function generationOf(uint256 agentId) external view returns (uint64);
function nameGeneration(uint256 nameTokenId) external view returns (uint64);
```

- 每次 `activateAgent` 成功，该名字的 `nameGeneration` 加 1（第一个是 1），`generationOf[agentId]` 记下这个值。
- burn 不把 `nameGeneration` 减回去，也不把 `generationOf` 清掉。
- 当前这一代的判断：`isActive(agentId) && generationOf(agentId) == nameGeneration(nameTokenIdOf(agentId)) && agentOfName(nameTokenId) == agentId`。
- 验证合约在 `validationRequest` 和 `validationResponse` 时都做这个判断。inactive 或代数对不上，请求 revert，响应也 revert。已经记下的旧请求留在旧 `agentId` 上，不迁移。

**缺口 C，阻塞。没有 `operatorAiId`。**

激活不读 `.ai`。`AgentActivated` 只有 agentId、nameTokenId、owner 地址、URI。名片里的 `.ai` 完全靠持有人上传的 JSON。

```solidity
function operatorAiIdOf(uint256 agentId) external view returns (bytes32);

event AgentActivated(
    uint256 indexed agentId,
    uint256 indexed nameTokenId,
    address indexed owner,
    bytes32 operatorAiId,
    uint64 generation,
    string agentURI
);
```

这是事件签名的变更。主网还没部署，索引器还没有生产数据。`docs/contracts/INDEXING.md` 里「一次转让的事件序列」不用改 `AgentActivated` 的旧形状，但 D 实现时要在 `INDEXING.md` 写上新字段。本规格先把字段定死。

`activateAgent` 增加的检查，按这个顺序：

1. 现有的 tld、owner、尚未激活、URI 长度检查保持不变。
2. `aiIdentityOf(msg.sender)` 必须成功，否则 `AiRequired`。记下 `operatorAiId`。
3. 分配 `agentId`，写入 generation、`operatorAiId`、URI、active，然后 `_mint`。
4. 最后 `try/catch` 调用 `points.earn(ACTIVATE, msg.sender, ACTIVATE_ONCE)`。`ACTIVATE_ONCE` 是常量，每个 `.ai` 终身只成功一次，不带 `nameTokenId`。

没有 `.ai` 的买家仍然可以买下名字、再卖掉。他不能激活。这是相对 `SPEC 6.6` 的改动，理由在第 4、5 节：否则自评可以绕过，名片上也没有可核对的 `.ai`。

**缺口 D，阻塞。自评可以绕过。** 这条在声誉合约上，验证合约也会读到被刷过的星星。

现在的 `rate` 只在两处拒绝自评：`msg.sender == owner`，以及 owner 自己有 `.ai` 且 `aiId` 相同。owner 没有 `.ai` 时，第二处被跳过。

实际路径：Alice 持有 `.ai` 和名字，把名字转到一个没有 `.ai` 的新地址 Carol，Carol 调用 `activateAgent`（当前代码允许），Alice 再 `rate`。`msg.sender` 不是 owner，owner 的 `aiIdentityOf` 失败，评分成功。`test_rate_sameAiIdAsOwnerFails` 并没有构造两个地址，这条没有被测试挡住。

`rate` 在现有检查之后、写 storage 之前，改成：

1. 评分人 `aiIdentityOf` 成功，否则 `AiRequired`。这一条已经有。
2. 评分人 `registrar.balanceOf(msg.sender) > 0`，否则 `NameRequired`。registrar 地址用 `HahaAgentIdentity(identity).registrar()` 读，不必给声誉合约再加一个 immutable。
3. agent owner 的 `aiIdentityOf` 必须成功，否则 `OwnerAiRequired`。
4. `msg.sender == owner`，或者评分人 `aiId` 等于 owner 的 `aiId`，或者等于 `operatorAiIdOf(agentId)`，都 `revert SelfRating`。
5. 写星星。改分不增加 `count`。这一条保持。
6. `try/catch` 依次 `earn(REVIEW_GIVE, msg.sender, bytes32(agentId))` 和 `earn(REVIEW_RECEIVE, owner, keccak256(abi.encode(agentId, raterAiId)))`。

第 3 步在缺口 C 落地之后，正常激活出来的 agent 一定有 owner `.ai`。第 3 步仍然要留着，用来挡住「C 之前的旧假设」和任何 owner 地址本身不持有 `.ai` 的情况。

### 3.3 建议一起做、但不单独构成「验证合约无法部署」的项

这些在改身份合约时一并做掉。单独为它们再发一版不值得，部署后也加不上。

```solidity
struct AgentView {
    address owner;          // inactive 时为 burn 前的 owner，不要 revert
    bool active;
    uint256 nameTokenId;
    uint64 generation;
    bytes32 operatorAiId;
    address wallet;         // inactive 时为 0
    string uri;             // 见下
}

function getAgent(uint256 agentId) external view returns (AgentView memory);
```

- burn 时把 owner 抄进 `lastOwner`，再 `_burn`。`getAgent` 对已 burn 的 id 返回 `lastOwner`，`active = false`，不 revert。现在 `ownerOf` 对已 burn 的 id revert，链上只剩 `AgentReset` 事件里的 `previousOwner`。
- URI 不要在 burn 时 `delete`。`tokenURI` 对 inactive 的行为保持 revert（避免市场把烧掉的 NFT 显示成还活着），但 `getAgent` 返回最后一份 URI。验证请求若需要名片，应当在请求当时自己把字符串存进验证合约；身份合约这份是备用。

### 3.4 声誉合约要不要改，才能「显示验证结果」

不用为这件事改存储。

- `getScore(agentId)` 继续只返回星星的 `count` 和 `sum`，包括已经 burn 的 id。
- 验证分的 0–100、validator、tag，由 Validation Registry 自己的 `getValidationStatus` / `getSummary` 返回。
- 网站和索引器把两者并排。一个以后部署的只读聚合合约也可以同时读两边。聚合合约是新的，不需要声誉合约配合。
- 不要给 `HahaReputation` 加 `importValidation` 之类的写入口。那会把验证者变成可以改星星的人，也和「一条可修改的 1–5 星」混在一起。

声誉合约要改的只有 3.2 缺口 D，以及为了发分而加上的 `points` immutable 和 `try/catch`。

### 3.5 将来的验证合约怎么用这些接口

不在本阶段实现，这里固定接入方式，避免到时候发现身份合约少字段。

- 准入：`isAuthorized(agentId, msg.sender)`。
- 代数：`isActive && generationOf(agentId) == nameGeneration(nameTokenIdOf(agentId))`。请求和响应都查。
- `requestHash` 全局唯一，重复请求 revert。响应可以多次，覆盖上一次的 0–100，和草案一致。
- 响应者必须是请求里的 `validatorAddress`。
- 合约自己存 `agentId`、`requestHash`、validator、response、tag、`lastUpdate`。不要把结果写回声誉合约。
- 不在身份合约上预留验证用的 hook，也不要 `setValidationRegistry`。身份合约不知道验证合约的地址。

## 4. 声誉与转让

### 4.1 和「信誉跟着 NFT 走」相比

ERC-8004 的 agent NFT 默认可转让，信誉按 `agentId` 留在这张 NFT 上，转让之后买家继承。那适合「这个 agent 作为一个主体被卖掉」。我们的主体是名字，agent 只是这个名字当前持有人打开的一层身份。

| | 转让时 burn，信誉归零（维持现状） | agent NFT 可转让，信誉跟着走 |
| --- | --- | --- |
| 买家买到什么 | 名字。当前分数是 0，要重新激活才有新的 `agentId` | 名字加上上一代攒下的星星和验证 |
| 信誉买卖 | 本市场的成交不会带上信誉 | 信誉变成标的的一部分，差评和刷分都可以卖 |
| 买家预期 | 必须在成交前写明「不含信誉」。规划文档第 2 页已经这么写 | 买家会为星星付钱，付完才发现上一代的评价和这一代的行为无关 |
| 差评 | 持有人可以自己转让一次，把当前分数清掉 | 差评会跟着 NFT 走，清不掉，除非再做一个撤销 |
| 历史 | 旧 `agentId` 的 `getScore` 和 `Rated` 还在 | 历史自然还在同一个 id 上 |

维持 burn。买家买不到信任，这是我们想要的。ERC-8004 允许转让，不构成我们要跟着转让的理由。偏离已经写在身份合约的 NatSpec 里，保留。

要接受的另一面：当前持有人可以主动把差评清掉。转给自己再激活，成本只有 gas。所以「当前分数」不是这个名字的终身档案。终身档案是事件里的各代 `agentId`。网站和索引器必须能按名字列出历代 `AgentActivated` / `AgentReset` / `getScore(旧 id)`，不能只显示现在这个 id 的星星。链上不需要为此做数组，事件够用。

### 4.2 代码现在实际做了什么

`HahaRegistrar._update` 在 `from != address(0)` 时，也就是每一次已有 NFT 的 owner 变更，固定调用 `syncOwner`、`clearRecords`、`deactivate`。没有 `from != to` 的例外。OpenZeppelin ERC-721 的 `transferFrom` 允许 `to == from`，会照常走 `_update`。

`deactivate`：

- 没有 active agent 时直接返回，不 revert。转让不会被「没激活过」卡住。
- 有的话：`agentOfName` 写 0，`_active` 和 `_agentURI` 删除，`_nameOfAgent` 保留，然后 `_burn`。
- 发 `AgentReset(nameTokenId, agentId, previousOwner)`，burn 再发一条 ERC-721 `Transfer` 到 `address(0)`。
- 不碰声誉 storage。`getScore(旧 id)` 还是旧的 `count` / `sum`。`rate(旧 id)` revert `AgentNotActive`。
- 不碰积分。

新的 `activateAgent` 使用 `_nextAgentId++`。同一个名字的下一代是新 id，从 `(0, 0)` 开始。id 不会回到 1，也不会复用已经烧掉的号。

各条路径：

| 路径 | agent | 信誉 | 积分 | 挂单 |
| --- | --- | --- | --- | --- |
| 转给自己 | burn | 当前分数不再挂在名字上，旧数字还在旧 id | 不动 | 挂单还在：`clearStale` 要求 owner 变了，这里 owner 没变。单代币 `approve` 会被 ERC-721 清掉，`setApprovalForAll` 还在。卖家可以 `cancel` |
| 转到自己的另一个地址 | 同一次正常转让，burn | 同上 | 积分留在原来那个 `.ai` 上。`.ai` 是 soulbound 的，新地址如果没有自己的 `.ai`，花不了这些分；原地址如果不再持有任何名字，也不能签到，直到名字回来 | 若 owner 已不是 seller，`buy` revert，任何人可以 `clearStale` |
| 本市场 `buy` | `safeTransferFrom` 走同一套钩子，burn | 买家得到的名字没有 active agent | 卖家的积分留在卖家的 `.ai` | 先删挂单再转 NFT。不存在「成交了但挂单还在」 |
| 自己买自己的挂单 | 代码没有 `buyer != seller` 的检查。会走自转，burn，并支付 1% 手续费 | 同上 | 货款进自己的 `pendingWithdrawal`，手续费进 `feeReceiver` | 挂单已删 |
| `approve` / `setApprovalForAll`，但没转 | 不 burn | 不动 | 不动 | 不动 |
| 被授权的人后来 `transferFrom` | burn | 同正常转让 | 同正常转让 | 视 owner 是否还是 seller |
| 外部市场成交 | 只要最终调用了名字 NFT 的转移，钩子就跑，burn | 同上 | 同上 | 本市场的旧挂单变成 stale |

自转会清掉解析记录和 agent。`skill.md` 要写明：不要用「转给自己」来刷新授权，那会毁掉当前 agent。

### 4.3 包装合约

只 `approve` 给一个合约，不会 burn。把名字 NFT **转进**一个金库或包装合约，会 burn 一次。之后如果只是改金库的签名人、转金库的份额，名字 NFT 的 owner 地址没变，不会再 burn。这是「只在 NFT 转移时断代」的边界。

缺口 C 把这条路收窄了：没有 `.ai` 的合约不能重新 `activateAgent`。因此「先转到空合约，再在合约里激活，然后把份额卖掉」做不成。能留下来的信誉，只有「名字一直停在那个持有 `.ai` 的地址上」的情况。把私钥卖掉等于把 `.ai` 一起卖掉，那是另一个身份的移交，不是名字市场的成交。

网站成交前提示保持规划文档的原文：买到的是名字，不含信誉。再加一句：当前星星只代表这一代激活，持有人可以重新激活，历史评价仍可在历代 `agentId` 上查到。

## 5. 身份锚在名字上，还是锚在 `.ai` 上

同意第 0 节的划分。按现在的代码核对如下。

**一个 `.ai` 对很多名字。** 铸造没有单地址个数上限，只有每个 `aiId` 每小时一次。签到、社交、铸造奖励都按 `aiId` 计，不按名字计。十个名字不会变成十次签到。这是对的，积分是「这个人」的账。

**一个名字对一代 agent。** `agentOfName` 同时最多一个 active id。信誉的 `count` / `sum` 存在 `agentId` 上。转让把这个映射清掉，新激活是新 id。这是「这个 agent」的账，不是「这个人的全部 agent」的账。

**评分人是 `.ai`。** `ratingOf(agentId, aiId)` 已经这么做。同一个人换钱包也换不了 `.ai`（soulbound），所以换地址不能再投一票。缺口是第 3.2 节 D：owner 没有 `.ai` 时这道检查被跳过。补上之后，评分人这一侧的锚是完整的。

**积分是 `.ai`。** 已经这么做，本规格把它写成总规则：余额、每日次数、终身一次的激活分、spender 预算都只按 `aiId`。激活分是每个 `.ai` 终身 20 分，卖掉名字再激活另一个名字不再发。不要改成按名字或按地址记账。名字卖掉，分还在；人没有名字，分花不出去。

**名片上的 `.ai`。** 应当记录，而且必须是链上的 `operatorAiId`，不是 JSON 里的一句话。JSON 继续由网站按下面的形状填写，合约不读、不验：

```json
{
  "type": "https://eips.ethereum.org/EIPS/eip-8004#registration-v1",
  "name": "abc.haha",
  "image": "data:image/svg+xml;base64,...",
  "x402Support": false,
  "supportedTrust": ["reputation"],
  "registrations": [
    { "agentId": 1, "agentRegistry": "eip155:56:<HahaAgentIdentity>" }
  ],
  "operatorAi": { "handle": "alice", "aiId": "0x..." }
}
```

`operatorAi.aiId` 必须等于链上 `operatorAiIdOf(agentId)`。网站展示时以链上值为准。`image` 继续复用该名字的链上 SVG。`x402Support` 保持 false，直到有单独的支付合约。

**可携带性。** 积分随 `.ai` 走，卖名字不丢分，也不把分卖出去。信誉不随买家走，也不随卖家带到下一个名字。卖家若想在新名字上重新开始，那是新的 `agentId`，分数是 0。这个不对称是故意的：分是参与奖励，信誉是这个 agent 这一代的外部评价。

**不采纳的另一种。** 把信誉记在 `.ai` 上，所有名字共用一个分数。一个人做一个坏 agent，会污染他别的名字；买家打开买来的名字，看到的是买家自己（或卖家本人）别的人生。和「每个名字是一个 agent」相反。

## 6. 主网前的其他问题

严重级别：**阻塞** = 部署后改不了，或者现在这个行为会让信誉或积分失效。**可后续** = 不改也能上，改了更好。

### 阻塞

1. **Points 没有 earner、没有 `uniqueKey`、没有每日预算、没有 `statusOf`。** 第 1 节全部。不改的话，游戏、评价分、激活分、一次性状态查询都要么做不了，要么得把 `HahaPoints` 换掉。换掉等于整套重部署。
2. **自评绕过。** 第 3.2 节缺口 D。不改的话，把名字转到一个没有 `.ai` 的地址就能给自己打分。
3. **身份合约缺 operator、generation、`operatorAiId`。** 第 3.2 节 A、B、C。验证合约可以以后再部署，但这三个视图必须先在身份合约上。
4. **激活必须绑定 `.ai`，并且激活分的终身 key 在 Points 里。** 否则第 4.3 节的空合约包装、以及「烧掉再激活刷激活分」都还在。key 若只存在游戏或领取合约里，换一次模块就重领。
5. **`rate` / `activateAgent` 对 `earn` 使用 `try/catch`，转账钩子不调用 Points。** 这是实现约束。积分合约 revert 不能卡住 NFT 转移，也不能卡住评分和激活。
6. **索引器和 `skill.md` 在接口定稿后要认这些新事实。** 评语只存在 `Rated` 事件里，storage 读不到。历代 agent 只存在 `AgentActivated` 和 `AgentReset` 里，没有链上数组。`AgentActivated` 将增加 `operatorAiId` 和 `generation`。`statusOf` 是 agent 读任务状态的入口。这些不是合约漏洞，但网站规划第 3、4 节的数据做不出来，除非索引器按此索引。D 改事件时同步改 `INDEXING.md`。

### 可后续

1. **`getAgent` 和 burn 后仍可读的 `lastOwner`、最后一份 URI。** 第 3.3 节。改身份合约时一起做。
2. **自转和自己买自己的挂单。** 行为已经由代码确定，见第 4.2 节。可以另加 `buyer != seller` 的 revert，不作为本规格的要求。`skill.md` 必须警告自转会 burn agent。
3. **`buy` 在 owner 已变时 revert `PriceChanged`。** 这个名字对「挂单过期」不准确。`AUDIT.md` 已记录。不要为了改名去动 ABI，除非正好在改市场。
4. **`spend` 先 `emit` 再写余额，签到是先写余额再 `emit`。** 结果一致，没有外部调用。改 `spend` 加预算时，顺手改成先写余额再发事件。
5. **`activateAgent` 在 tld 非法时 revert `InvalidAgentURI(0)`。** 可以改成现成的某种参数错误，不要为此新开一套只为了好看的错误名，除非实现时本来就要动这个函数。
6. **`IHahaProtocol.IHahaAgentIdentity` 比合约窄。** 外部验证合约应当用合约 ABI，不要用这份内部接口。实现本规格时把 `isAuthorized`、`generationOf`、`operatorAiIdOf`、`getAgent` 补进接口。
7. **名字 NFT 不可枚举。** `SPEC` 已经定了。`我的域名` 继续走索引器，不要为了网站去加 `ERC721Enumerable`。
8. **社交任务伪验证。** 保持。游戏不要抄这个模式。
9. **管理员可以把六项内置分数改到 `999999999`。** 保持。earner 的硬顶不要用来「修正」这项已经拍板的权力。
10. **`.ai` 的 handle 若被币安侧改写，`aiId = keccak256(handle)` 会变，旧余额留在旧 id 上。** 我们没有源码可以证明 handle 永不变。`statusOfAi` 在 `ownerOf` 失败时仍然返回旧余额。不要做迁移函数。
11. **包装与合约钱包。** 第 4.3 节。在缺口 C 之后，这是文档需要写明的边界，不是再加一条链上禁令。
12. **没有第三方审计。** `AUDIT.md` 第 10 节已经写了。本规格带来的 `earn`、预算和 `try/catch` 是新的审计面。上线前的第三方审计要覆盖它们。

### 明确不改

- 市场费率、收款代币、黑名单、保留名、管理员地址、`feeReceiver`。
- 铸造冷却留在 `HahaRegistrar`：`COOLDOWN = 3600`，`lastMintAt` 的滚动算法不改。积分表和 `statusOf` 都不收它。
- `HahaRegistrar._update` 的三步顺序和「没有记录也必须成功」。
- 工厂不保留写函数。`setEarner` 的第一笔交易由硬件钱包管理员在部署后发送，不由部署 EOA 发送。
- `via_ir = true`。`AUDIT.md` 里的体积余量：Points 运行时约 5,876 字节，Identity 约 4,851，Reputation 约 2,180，距 24,576 还有余量。若实现后超限，停下来报告，不要删硬顶或删 `uniqueKey` 来硬塞。

## 7. D 的实现范围与测试

本文件所在的 PR 只提交规格。实现用后续的改动，动这些文件：

- `src/HahaPoints.sol`
- `src/HahaAgentIdentity.sol`
- `src/HahaReputation.sol`
- `src/interfaces/IHahaProtocol.sol`
- `src/libraries/HahaConstants.sol`
- `src/HahaDeployer.sol`（只加地址自洽检查）
- `script/Deploy.s.sol`
- `test/` 下对应的单元、模糊和不变式
- `docs/contracts/INDEXING.md`（新事件字段、`PointsChanged` 的新 reason、评语只在事件里）

不要改 `HahaMarketplace`、`HahaNamePolicy`、`HahaMetadata`、`HahaRegistry`、`HahaResolver` 的行为。`HahaRegistrar` 的转账钩子不加积分调用。

部署后管理员要发的配置交易，写进 `DEPLOY.md` 的运行步骤，不要写进工厂：

1. `setEarner(REVIEW_GIVE, ...)`、`REVIEW_RECEIVE`、`ACTIVATE`，module 分别是声誉合约和身份合约，数值用第 1.3 节的表。
2. 游戏上线时 `registerGame`。一个游戏一个 id，带 `maxScorePerRound`、该 `.ai` 的每日分数上限、全网每日预算。不上线就不登记。不要登记 PLAY / WIN 两个动作。
3. 授权拍卖 spender 时同时 `setSpenderBudget`。只 `setSpender(true)` 而不设预算的，`spend` 必须 revert。

测试要新增的行为，原有 `SPEC 12` 的用例保持通过：

- 未登记的地址调用 `earn` revert；登记之后，无 `.ai`、无名字、超个人次数、超全网预算、当天重复的 `PerDay` key、已用过的 `Lifetime` key，都返回 0 且不增加余额。被次数挡住的那一次不写 key。
- 日切用日序号测，不用「满 24 小时」。同一个 UTC 日内把时间往后拨 23 小时，签到、铸造奖励次数、点赞、评价对子、游戏次数都不归零。拨到下一个日序号的第一秒，这些当日次数读出来是 0。关注标记和激活的 `Lifetime` key 仍然在。
- 停用 earner 或换成新模块，`Lifetime` key 仍算已使用。`PerDay` key 在新的 UTC 日可以再领。
- 写出评价：同一 `.ai` 对同一 `agentId`，同一个 UTC 日里第二次 `rate` 星星可以改，两边的 5 分都返回 0。当天第 6 个不同 agent 的 `REVIEW_GIVE` 返回 0。接收人当天第 6 个不同评分人的 `REVIEW_RECEIVE` 返回 0。下一个 UTC 日同一对可以再各发 5 分。
- 游戏：`beginRound` 第 4 次 revert，两个游戏加在一起也是 4 次就 revert。`claimRound` 没有分数字段，发出的分等于 `scoreOf` 的记录。记录为 63 就加 63。超过 `maxScorePerRound` revert，不加一个被砍过的数。同一 `sessionId` 第二次 revert。开局日的下一个 UTC 日再领，revert `SessionExpired`，局数不退回。用户交易里不存在「自报分数」的参数。
- `statusOf` 与分项 getter 一致：没签到、今天已签、day 0、没有 `.ai`、没有名字、铸造奖励 3 次已满。`nextResetAt` 等于 `(currentDay + 1) * 86400`。`checkInToday`、`mintRewardsToday`、`likeToday`、`retweetToday`、`commentToday`、`gameRoundsToday`、`reviewsGivenToday`、`reviewsReceivedToday` 跨日变为 0。`followClaimed` 跨日不变。`statusOf` 里没有铸造冷却字段。
- 铸造冷却仍由现有 `HahaRegistrar` 测试覆盖：距上次不足 3600 秒 `register` revert。不要把这项改成「过了 UTC 0 点就能铸」，也不要把它挪进 `HahaPoints`。
- 自评：owner 直接 `rate` revert；owner 没有 `.ai` 时任何人 `rate` 都 revert `OwnerAiRequired`；评分人 `aiId` 等于 `operatorAiId` 时 revert。过了 UTC 0 点仍然 revert。
- 激活分：同一个 `.ai` 第二次 `earn(ACTIVATE, ..., ACTIVATE_ONCE)` 返回 0，包括换成另一个名字、卖掉再买回、以及跨过很多个 UTC 日。另一个 `.ai` 仍有自己的一次。不要用 `nameTokenId` 当 key。没有「每天 5 个名字」这道上限。
- `earn` 在 `setEarner` 之前 revert 时，`activateAgent` 和 `rate` 仍然成功。
- `deactivate` 不改变任何积分余额。把 Points 的返回值设成 revert 的测试双生不要求，因为 points 地址是 immutable 的真实合约；用「转让前后余额相等」加上代码审查这条调用不存在即可。
- `statusOf` 的日切断言见上一条。铸造奖励次数跨日归零，和冷却无关。
- spender 未设预算不能 `spend`；超过每日 gross 不能 `spend`；`refund` 不能把 gross 预算还回去，也不能超过 `spendable`。
- `agentId`：burn 再激活，新 id 等于旧 id + 1，`generation` 加 1，`isAuthorized` 对旧 id 为 false，`nameGeneration` 不减。
- 自转、市场成交、仅 `approve` 不转，这三条对 agent 的影响与第 4.2 节的表一致。
- 游戏侧用 mock：`scoreOf` 返回固定分数时 `claimRound` 加的就是这个数；第 4 局开不了；把 `scoreOf` 改成超过 `maxScorePerRound` 时领取失败且余额不变。

不变式在原有「余额之和等于 `PointsChanged`」之上，加上：任一 action 的 `globalPointsToday` 不超过其 `globalDailyPoints`，任一 `aiId` 的当日次数不超过 `perUserDailyCap`。
