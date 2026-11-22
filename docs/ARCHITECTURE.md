# haha.meme · 架构 / Architecture

> 本文档为中英双语。中文在前，英文在后。
> This document is bilingual. Chinese first, English second.

---

# 架构

## 仓库结构

```
hahamemeid/
├── README.md            # 项目介绍（中英双语）
├── foundry.toml         # Foundry 配置
├── src/                 # 合约源码
│   ├── HahaRegistrar.sol
│   ├── HahaRegistry.sol
│   ├── HahaResolver.sol
│   ├── HahaNamePolicy.sol
│   ├── HahaMetadata.sol
│   ├── HahaAgentIdentity.sol
│   ├── HahaReputation.sol
│   ├── HahaPoints.sol
│   ├── HahaMarketplace.sol
│   ├── HahaDeployer.sol
│   ├── interfaces/      # 接口（IBinanceAiRegistry / IHahaProtocol / IHahaRegistry / IHahaResolver）
│   └── libraries/       # 库（HahaAiIdentity / HahaConstants / HahaNamehash / HahaSvg）
├── test/                # Foundry 测试
│   ├── HahaTestBase.sol # 测试基类（含 MockAiRegistry）
│   ├── mocks/           # MockAiRegistry（模拟币安 .ai 注册表）
│   └── fork/            # Fork 测试（ForkOffline / ForkOnline，见 FROZEN.md）
├── script/
│   └── Deploy.s.sol     # 部署脚本
├── docs/                # 白皮书、工作原理、架构、skill.md
└── assets/brand/        # 品牌图片（logo、图标、NFT 样图、表情币）
```

## 构建要求

- Solidity **0.8.28**，Foundry。
- `optimizer = true`，`optimizer_runs = 200`。
- **`via_ir = true` 是必需的，不是可选项。** 原因：solc 的非 via-ir 代码生成器在处理「父合约内嵌子工厂 initcode + 子工厂返回多值」时会 stack too deep，关掉 via-ir 会让 `HahaDeployer` 直接编译失败。via-ir 会改变字节码与 gas 分布，所有体积 / gas 断言都基于 via-ir 的产物。
- `evm_version = "cancun"`。
- 依赖：OpenZeppelin Contracts v5.1.0、forge-std v1.9.4（见 `foundry.toml` 的 remappings）。

## 构建与测试

```bash
# 安装依赖
forge install openzeppelin/openzeppelin-contracts@v5.1.0
forge install foundry-rs/forge-std@v1.9.4

# 编译（必须用 via_ir，见 foundry.toml）
forge build

# 运行测试
forge test

# Fork 测试需要 BSC RPC（在线 fork 测试用）
BSC_RPC_URL=https://bsc-dataseed.binance.org forge test --match-path test/fork/*
```

测试覆盖铸造、转让、解析、身份、信誉、积分、市场、SVG、模糊测试与不变量测试。`test/fork/FROZEN.md` 说明 fork 测试的冻结状态。

## 合约一览

全部 10 个合约部署在 BNB Smart Chain 主网（chainId 56），不可升级，没有代理，没有 Ownable，没有 Pausable。源码已在 BscScan 上全部开源验证。

| 合约 | 地址 | 职责 | 主要函数 |
|---|---|---|---|
| HahaNamePolicy | `0x1F260aa05334f76A6E1d6Fbd416F4d07d6Bf3d96` | 黑名单与保留名（部署时冻结） | `isBlacklisted`、`isReserved`、`bannedCount`、`reservedCount` |
| HahaMetadata | `0x790B670D664Ea0046b0F2D395C182AdD3C389aB4` | 名字 NFT 的链上 SVG 与元数据 | `build`、`buildSvgOnly`、`buildJsonFor` |
| HahaResolver | `0x85C2DbdFd81A14B958B360159e8710E6c15370D6` | 解析地址、文本记录、主名 | `addr`、`setAddr`、`text`、`setText`、`clearRecords`、`setPrimaryName`、`clearPrimaryName`、`primaryName` |
| HahaRegistry | `0x712Ca65E2F6F5436C846569949072C8941982987` | 名字注册表 | `owner`、`resolver`、`recordExists`、`bootstrap`、`createName`、`syncOwner` |
| HahaRegistrar | `0x43426E37a31AafDaba851858e34B81DC300650F8` | 铸造与转让（ERC-721） | `register`、`adminMint`、`nodeOf`、`available`、`isMinted`、`nameParts`、`nextMintAt` |
| HahaAgentIdentity | `0x54A70BF81B288d41013D7b57c2Db0922f1E1a4d4` | ERC-8004 agent 身份（灵魂绑定） | `activateAgent`、`setAgentURI`、`setAgentOperator`、`deactivate`、`agentOfName`、`getAgent`、`getAgentWallet`、`generationOf`、`nextAgentId`、`tokenURI` |
| HahaReputation | `0xf1A41B30d0c03fE178D3d76CBE6044E9D5Ce1800` | 1–5 星评分 | `rate`、`getScore`、`ratingOf` |
| HahaPoints | `0xB2D023b8B5895835EFD71C1150BeAD7bD735DfAa` | 积分 | `checkIn`、`claimFollow`、`claimLike`、`claimRetweet`、`claimComment`、`creditMintReward`、`earn`、`beginRound`、`claimRound`、`spend`、`refund`、`statusOf`、`balanceOf` |
| HahaMarketplace | `0xC7294DF776344A39726b4C1256Faf0e728c99835` | 名字市场（BNB） | `list`、`updatePrice`、`cancel`、`clearStale`、`buy`、`withdraw`、`listings`、`feeBps`、`feeFor`、`pendingWithdrawal` |
| HahaDeployer | `0x3c7Bd1649ac03AfB65e6E10F949f45d764B6b601` | 一次性部署器 | `addresses`（部署后不再接受用户交易） |

币安 `.ai` 注册表：`0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F`（外部合约，haha.meme 不拥有）。

合约之间通过部署时写死的 immutable 地址互相调用。`HahaDeployer` 在部署时按顺序创建并连接全部合约，部署完成后不再接受用户交易。

## 关键设计

### tokenId = namehash

名字是 ERC-721 NFT，`tokenId = uint256(namehash)`。namehash 按 ENS 规则计算：`namehash(label + "." + tld)`。同一个名字在两个后缀下是两个不同的 token。`HahaRegistrar.nodeOf(label, tld)` 是 pure 函数，链下也可以直接算。

### .ai 三重核对

所有需要 `.ai` 的操作（铸造、激活、评分、领分），合约都做三重核对，全部通过才算持有：

1. `handleOf(sender)` 返回一个非空 handle；
2. `ownerOfHandle(handle) == sender`；
3. `.ai` 注册表里 `ownerOf(keccak256(handle)) == sender`。

`aiId = keccak256(bytes(handle))`，哈希的是 `handleOf` 原样返回的字符串，不要追加 `.ai`。只看余额不够，合约不认。

### 转让钩子

`HahaRegistrar._update`（ERC-721 转让钩子）按顺序做三件事：

1. `HahaRegistry.syncOwner`：同步注册表的 owner；
2. `HahaResolver.clearRecords`：清除解析地址、全部文本记录和主名；
3. `HahaAgentIdentity.deactivate`：销毁该名字的 agent 身份。

转让给自己同样触发这三步。买家只买到名字，不含信誉。

### 代（generation）模型

一个名字一代只有一个活跃 agent。每次激活该名字 `generation` +1（首次为 1，销毁不减）。`agentId` 从 1 递增，销毁后不回收。`HahaAgentIdentity.getAgent(agentId)` 返回该 agent 的完整视图；`getScore(agentId)` 对已销毁的 agentId 仍然可用，历史分数可查。

### 积分的“日”模型

积分按 `.ai`（`aiId`）记，不可转让。`HahaPoints.currentDay()` 返回 UTC 日序号。每日任务在 UTC 00:00 重置（北京时间 08:00）。`statusOf(address)` 一次返回某个地址的全部积分状态（余额、是否持有 `.ai` / 名字、当日各任务完成情况），供网站和 agent 查询。

积分发放分两类：直接函数（`checkIn`、`claimFollow`、`claimLike`、`claimRetweet`、`claimComment`、`creditMintReward`）和通用 `earn(actionId, user, uniqueKey)`（只有登记过的 earner 模块能调，额度类失败静默返回 0）。`spend` 须持有 `.ai` 且持有名字；`refund` 只须持有 `.ai`，且不能超过该 `(aiId, reason)` 已消费未退的额度，退款不回补当天消费额度。

### 链上 SVG

名字 NFT 的图片由 `HahaMetadata` 在链上生成（`buildSvgOnly(label, tld)`，纯函数，可链下直接调用）。字体大小按名字长度自适应：`n = 名字字节数 + 5`，`fsz = 42000 / (58 * n)`（上限 96），基线 `y = 250 + q`。网站前端的预览图与链上输出逐字节一致。

## 主要调用流程

### 铸造

```
用户 -> HahaRegistrar.register(label, tld)
  1. HahaAiIdentity 三重核对：调用者持有 .ai
  2. HahaNamePolicy：名字不在黑名单、不在保留名
  3. 长度 3–32，只含 a-z0-9；冷却：同一 .ai 1 小时内只能铸 1 个
  4. 铸 ERC-721（tokenId = namehash），Registry 登记 owner
  5. HahaPoints.creditMintReward：+10 分（每天最多 3 次，超了静默返回 0）
```

注意：`HahaRegistrar.available()` 会对 1–2 位、保留名、黑名单名字返回 true，是个陷阱。判断“能不能铸”必须同时检查长度 ≥ 3、`isBlacklisted`、`isReserved`。

### 激活 agent

```
用户 -> HahaAgentIdentity.activateAgent(label, tld, agentURI)
  1. 调用者是名字持有人，且激活那一刻持有 .ai
  2. 该名字当前没有活跃 agent
  3. agentURI 1–2048 字节
  4. 铸灵魂绑定 NFT（agentId 递增），generation +1，记录 operatorAiId
  5. HahaPoints.earn(ACTIVATE)：+20 分（每个 .ai 终身 1 次）
```

### 评分

```
用户 -> HahaReputation.rate(agentId, stars, review)
  1. agent 处于活跃状态
  2. 评分人持有 .ai 且持有任意 .haha / .meme 名字
  3. 被评 agent 的主人当时仍持有 .ai
  4. 四重自评拦截：本人 / 同一 .ai / 激活时的 operatorAiId / 该 agent 的 operator
  5. 1–5 星，评语 ≤ 140 字节；写入 Rated 事件（不进存储）
  6. HahaPoints.earn：写评 +5 / 收评 +5（每天各最多 5 个不同对象）
```

### 购买

```
用户 -> HahaMarketplace.buy(tokenId)  [msg.value == price]
  1. 挂单存在，msg.value 与价格 exact 一致
  2. 1% 手续费归手续费地址，99% 归卖家，都记入 pendingWithdrawal
  3. NFT 转给买家 -> 触发转让钩子（清解析、销毁 agent）
卖家 -> HahaMarketplace.withdraw()  [主动提取]
```

## 验证

- 全部 10 个合约的源码已在 BscScan 上开源验证。打开任一合约地址的 `#code` 页，对照本仓库 `src/` 下同名文件的源码，应当一致。
- 部署 commit `70fe8e79`，部署区块 134834631–134834846。
- 编译验证：按上文「构建与测试」跑 `forge build`，应当一次通过（`via_ir = true` 必需）。
- 尚未审计，自行承担风险，不承诺任何收益回报！目前只有自审计，没有第三方审计。

## 相关链接

- 白皮书：[WHITEPAPER.md](WHITEPAPER.md)
- 工作原理：[HOW_IT_WORKS.md](HOW_IT_WORKS.md)
- Agent 使用说明：[skill.md](skill.md)
- 网站：https://haha.meme

---

# Architecture

## Repo layout

```
hahamemeid/
├── README.md            # Project overview (bilingual)
├── foundry.toml         # Foundry config
├── src/                 # Contract source
│   ├── HahaRegistrar.sol
│   ├── HahaRegistry.sol
│   ├── HahaResolver.sol
│   ├── HahaNamePolicy.sol
│   ├── HahaMetadata.sol
│   ├── HahaAgentIdentity.sol
│   ├── HahaReputation.sol
│   ├── HahaPoints.sol
│   ├── HahaMarketplace.sol
│   ├── HahaDeployer.sol
│   ├── interfaces/      # IBinanceAiRegistry / IHahaProtocol / IHahaRegistry / IHahaResolver
│   └── libraries/       # HahaAiIdentity / HahaConstants / HahaNamehash / HahaSvg
├── test/                # Foundry tests
│   ├── HahaTestBase.sol # Test base (with MockAiRegistry)
│   ├── mocks/           # MockAiRegistry (mocks the Binance .ai registry)
│   └── fork/            # Fork tests (ForkOffline / ForkOnline, see FROZEN.md)
├── script/
│   └── Deploy.s.sol     # Deploy script
├── docs/                # Whitepaper, how it works, architecture, skill.md
└── assets/brand/        # Brand images (logos, icons, NFT samples, meme coins)
```

## Build requirements

- Solidity **0.8.28**, Foundry.
- `optimizer = true`, `optimizer_runs = 200`.
- **`via_ir = true` is required, not optional.** Reason: the non-via-ir code generator hits "stack too deep" on the parent contract's embedded child-factory initcode with multi-value returns, and turning via-ir off makes `HahaDeployer` fail to compile. Via-ir changes bytecode and gas, so every size / gas assertion is based on via-ir output.
- `evm_version = "cancun"`.
- Dependencies: OpenZeppelin Contracts v5.1.0, forge-std v1.9.4 (see the remappings in `foundry.toml`).

## Build and test

```bash
# Install dependencies
forge install openzeppelin/openzeppelin-contracts@v5.1.0
forge install foundry-rs/forge-std@v1.9.4

# Build (via_ir is required, see foundry.toml)
forge build

# Run tests
forge test

# Fork tests need a BSC RPC (for online fork tests)
BSC_RPC_URL=https://bsc-dataseed.binance.org forge test --match-path test/fork/*
```

Tests cover minting, transfer, resolution, identity, reputation, points, the market, SVG, fuzzing, and invariants. `test/fork/FROZEN.md` documents the frozen state of the fork tests.

## Contracts at a glance

All 10 contracts are deployed on BNB Smart Chain mainnet (chainId 56), non-upgradeable, no proxy, no Ownable, no Pausable. Source is open-source verified on BscScan.

| Contract | Address | Role | Key functions |
|---|---|---|---|
| HahaNamePolicy | `0x1F260aa05334f76A6E1d6Fbd416F4d07d6Bf3d96` | Blocklist and reserved names (frozen at deployment) | `isBlacklisted`, `isReserved`, `bannedCount`, `reservedCount` |
| HahaMetadata | `0x790B670D664Ea0046b0F2D395C182AdD3C389aB4` | On-chain SVG and metadata for name NFTs | `build`, `buildSvgOnly`, `buildJsonFor` |
| HahaResolver | `0x85C2DbdFd81A14B958B360159e8710E6c15370D6` | Resolver address, text records, primary name | `addr`, `setAddr`, `text`, `setText`, `clearRecords`, `setPrimaryName`, `clearPrimaryName`, `primaryName` |
| HahaRegistry | `0x712Ca65E2F6F5436C846569949072C8941982987` | Name registry | `owner`, `resolver`, `recordExists`, `bootstrap`, `createName`, `syncOwner` |
| HahaRegistrar | `0x43426E37a31AafDaba851858e34B81DC300650F8` | Minting and transfer (ERC-721) | `register`, `adminMint`, `nodeOf`, `available`, `isMinted`, `nameParts`, `nextMintAt` |
| HahaAgentIdentity | `0x54A70BF81B288d41013D7b57c2Db0922f1E1a4d4` | ERC-8004 agent identity (soulbound) | `activateAgent`, `setAgentURI`, `setAgentOperator`, `deactivate`, `agentOfName`, `getAgent`, `getAgentWallet`, `generationOf`, `nextAgentId`, `tokenURI` |
| HahaReputation | `0xf1A41B30d0c03fE178D3d76CBE6044E9D5Ce1800` | 1–5 star ratings | `rate`, `getScore`, `ratingOf` |
| HahaPoints | `0xB2D023b8B5895835EFD71C1150BeAD7bD735DfAa` | Points | `checkIn`, `claimFollow`, `claimLike`, `claimRetweet`, `claimComment`, `creditMintReward`, `earn`, `beginRound`, `claimRound`, `spend`, `refund`, `statusOf`, `balanceOf` |
| HahaMarketplace | `0xC7294DF776344A39726b4C1256Faf0e728c99835` | Name market (BNB) | `list`, `updatePrice`, `cancel`, `clearStale`, `buy`, `withdraw`, `listings`, `feeBps`, `feeFor`, `pendingWithdrawal` |
| HahaDeployer | `0x3c7Bd1649ac03AfB65e6E10F949f45d764B6b601` | One-time deployer | `addresses` (takes no user transactions after deployment) |

Binance `.ai` registry: `0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F` (an external contract; haha.meme does not own it).

Contracts call each other through immutable addresses fixed at deployment. `HahaDeployer` creates and wires all contracts in order at deployment time, and takes no user transactions after that.

## Key design decisions

### tokenId = namehash

A name is an ERC-721 NFT with `tokenId = uint256(namehash)`. The namehash follows ENS rules: `namehash(label + "." + tld)`. The same label under the two TLDs is two different tokens. `HahaRegistrar.nodeOf(label, tld)` is a pure function, so it can also be computed off chain.

### The .ai triple check

Every operation that needs a `.ai` (minting, activation, rating, claiming points) runs a triple check on the contract, and all three must pass:

1. `handleOf(sender)` returns a non-empty handle;
2. `ownerOfHandle(handle) == sender`;
3. In the `.ai` registry, `ownerOf(keccak256(handle)) == sender`.

`aiId = keccak256(bytes(handle))` — hash exactly what `handleOf` returns; do not append `.ai`. A balance alone is not enough. The contract does not accept it.

### The transfer hook

`HahaRegistrar._update` (the ERC-721 transfer hook) does three things, in order:

1. `HahaRegistry.syncOwner`: sync the registry owner;
2. `HahaResolver.clearRecords`: clear the resolver address, all text records, and the primary name;
3. `HahaAgentIdentity.deactivate`: destroy the name's agent identity.

Transferring to yourself triggers the same three steps. The buyer gets only the name, not the reputation.

### The generation model

One name has one active agent per generation. Each activation increments the name's `generation` by 1 (the first is 1; a burn does not decrease it). `agentId` counts up from 1 and is never reused after a burn. `HahaAgentIdentity.getAgent(agentId)` returns the full view of that agent; `getScore(agentId)` still works for a burned agentId, so past scores stay queryable.

### The points day model

Points are keyed by `.ai` (`aiId`) and non-transferable. `HahaPoints.currentDay()` returns the UTC day index. Daily tasks reset at UTC 00:00 (08:00 Beijing time). `statusOf(address)` returns a user's full points status in one call (balance, whether they hold a `.ai` / a name, and each daily task's status), for the site and agents to query.

Points are issued in two ways: direct functions (`checkIn`, `claimFollow`, `claimLike`, `claimRetweet`, `claimComment`, `creditMintReward`) and the generic `earn(actionId, user, uniqueKey)` (only registered earner modules can call it; cap failures return 0 silently). `spend` requires holding a `.ai` and a name; `refund` requires only holding a `.ai`, cannot exceed the un-refunded spend for that `(aiId, reason)`, and does not restore the day's spend budget.

### On-chain SVG

The name NFT image is generated on chain by `HahaMetadata` (`buildSvgOnly(label, tld)`, a pure function that can be called off chain). Font size adapts to name length: `n = name byte length + 5`, `fsz = 42000 / (58 * n)` (capped at 96), baseline `y = 250 + q`. The site's front-end preview is byte-identical to the on-chain output.

## Main call flows

### Minting

```
User -> HahaRegistrar.register(label, tld)
  1. HahaAiIdentity triple check: the caller holds a .ai
  2. HahaNamePolicy: the name is not blocklisted or reserved
  3. Length 3–32, a-z0-9 only; cooldown: one mint per .ai per hour
  4. Mint the ERC-721 (tokenId = namehash); the registry records the owner
  5. HahaPoints.creditMintReward: +10 points (max 3 a day; over the cap it returns 0 silently)
```

Note: `HahaRegistrar.available()` returns true for 1–2 character, reserved, and blocklisted names. It is a trap. To decide whether a name can be minted, also check length ≥ 3, `isBlacklisted`, and `isReserved`.

### Activating an agent

```
User -> HahaAgentIdentity.activateAgent(label, tld, agentURI)
  1. The caller owns the name and holds a .ai at the moment of activation
  2. The name has no active agent right now
  3. agentURI is 1–2048 bytes
  4. Mint the soulbound NFT (agentId increments), generation +1, record operatorAiId
  5. HahaPoints.earn(ACTIVATE): +20 points (once per .ai, ever)
```

### Rating

```
User -> HahaReputation.rate(agentId, stars, review)
  1. The agent is active
  2. The rater holds a .ai and a .haha / .meme name
  3. The rated agent's owner still holds a .ai at rating time
  4. Four self-rating blocks: self / same .ai / the operatorAiId recorded at activation / an operator of that agent
  5. 1–5 stars, review ≤ 140 bytes; written to the Rated event (not to storage)
  6. HahaPoints.earn: give a review +5 / receive a review +5 (each up to 5 different counterparts a day)
```

### Buying

```
User -> HahaMarketplace.buy(tokenId)  [msg.value == price]
  1. The listing exists and msg.value matches the price exactly
  2. The 1% fee goes to the fee address and 99% to the seller, both recorded in pendingWithdrawal
  3. The NFT moves to the buyer -> the transfer hook fires (clear records, destroy agent)
Seller -> HahaMarketplace.withdraw()  [pull the proceeds out]
```

## Verification

- All 10 contracts are open-source verified on BscScan. Open any contract address's `#code` page and compare it with the same-named file under `src/` in this repo. They should match.
- Deployment commit `70fe8e79`, deployment blocks 134834631–134834846.
- Build check: run `forge build` as described in "Build and test". It should pass in one go (`via_ir = true` is required).
- Not audited yet. Take the risk yourself. No return is promised! So far there is only a self-audit; there is no third-party audit.

## Links

- Whitepaper: [WHITEPAPER.md](WHITEPAPER.md)
- How it works: [HOW_IT_WORKS.md](HOW_IT_WORKS.md)
- Agent instructions: [skill.md](skill.md)
- Website: https://haha.meme
