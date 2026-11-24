# haha.meme 白皮书 / Whitepaper

> 本文档为中英双语。中文在前，英文在后。
> This document is bilingual. Chinese first, English second.

- 网站 Website：https://haha.meme
- X：https://x.com/aihahameme
- Telegram：https://t.me/aihahameme
- 版本：V1（已上线 BNB Smart Chain 主网）
- 部署 commit：`70fe8e79`，部署区块 134834631–134834846，chainId 56

---

# 白皮书

## 摘要

AI agent 正在替人干活：交易、发帖、谈合作。对面的人（或 agent）需要回答两个问题：这个 agent 是谁？它靠不靠谱？

haha.meme 的回答是链上简历。持有币安 `.ai` 的钱包，可以免费、永久铸造一个 `.haha` 或 `.meme` 名字（haha id）。这个名字是 ERC-721 NFT；激活后，它成为 ERC-8004 agent 身份；别人给它打 1–5 星，评分和评语写在链上，谁都能查，谁也改不了历史。参与行为（签到、铸造、激活、评价）按 `.ai` 累计积分，积分是生态参与活跃度的重要依据。

全部写在链上，公开可核对。网站不碰私钥，也不发交易。

## 1. 问题

AI agent 越来越多，但身份和信誉没有统一的、可核对的载体：

- 一个 agent 自称是谁，没有链上凭证可以核对。
- 一次合作愉快，下一次对方换个名字，历史就断了。
- 好评、差评分散在各个平台，平台可以改，记录可以删。

需要一个东西：名字就是身份，评分就是简历，历史改不了，转让就清零。

## 2. 方案：三层

haha.meme 是三层结构，每一层都建立在上一层之上。

**第一层：币安 .ai 是门票。** 只有持有币安 `.ai` 的钱包，才能铸造、评分、领分。.ai 是 Binance 生态的 agent 身份，先有它，才有后面的一切。合约核对三件事，全部通过才算持有：你的 .ai 有名字、这个名字的持有人是你、名字哈希对应的 NFT 也是你的。只看余额不够，合约不认。

**第二层：.haha / .meme 名字是链上名字。** 一个名字就是一个 ERC-721 NFT（haha id），tokenId 就是名字的哈希。永久属于你，没有续费，可以转让、可以卖。名字还提供解析（指向钱包地址）、主名（一个地址对外只亮一个名字）和文本记录（key 最长 64 字节，value 最长 1024 字节，每个名字最多 16 条）。

**第三层：ERC-8004 身份 + 信誉是简历。** 激活 agent，得到一个 agentId；别人给你打分，分数和评语都写在链上。名字转让，agent 身份销毁，信誉清零，新一代从 0 分开始，旧评语按代数保留、可查。

## 3. 架构

11 个合约，全部不可升级，没有代理，没有 Ownable，没有 Pausable。部署在 BNB Smart Chain 主网（chainId 56），源码已在 BscScan 上全部开源验证。原 10 个合约部署 commit `70fe8e79`，部署区块 134834631–134834846；HahaSeason1 单独部署在区块 135231506。

| 合约 | 职责 |
|---|---|
| HahaNamePolicy | 黑名单与保留名（部署时冻结，不可更改） |
| HahaMetadata | 名字 NFT 的链上 SVG 与元数据 |
| HahaResolver | 解析地址、文本记录、主名 |
| HahaRegistry | 名字注册表（owner / resolver 记录） |
| HahaRegistrar | 铸造与转让（ERC-721） |
| HahaAgentIdentity | ERC-8004 agent 身份（灵魂绑定） |
| HahaReputation | 1–5 星评分 |
| HahaPoints | 积分 |
| HahaMarketplace | 名字市场（BNB） |
| HahaDeployer | 一次性部署器（部署后不再接受用户交易） |
| HahaSeason1 | 第一季：积分兑换 2 位稀有域名（每天 20 个、全季 300 个） |

合约之间通过部署时写死的 immutable 地址互相调用。技术细节见 [ARCHITECTURE.md](ARCHITECTURE.md)，源码见本仓库 [`src/`](../src/)。

## 4. 铸造与命名规则

1. 持有币安 `.ai` 才能铸造，同一 `.ai` 每 1 小时最多铸 1 个，`.haha` 与 `.meme` 两个后缀共用冷却。
2. 名字 3–32 个字符，只允许小写字母和数字。
3. 免费、永久、无续费，只付 gas；名字只能铸给自己（`msg.sender`）。
4. 黑名单 208 个、保留名 61 个，部署时已冻结，不可更改。黑名单词表不公开列出。
5. 保留名不经过公开铸造，后续由管理员铸造，免费空投给生态活跃参与者。第一季（2026-11-24 至 12-09）正在进行，见第 6 节。

名字是 ERC-721 NFT，tokenId 就是名字哈希（namehash）。永久，没有续费逻辑，也没有过期。

## 5. ERC-8004：身份与信誉

haha.meme 实现 ERC-8004 的两块：身份（Identity）与信誉（Reputation）。未实现 Validation Registry，不支持 x402。验证和支付还没做，先把身份和信誉做实。

**身份。** agent 身份是灵魂绑定 NFT，不能转让。一个名字同一时间只能有一个活跃 agent。激活那一刻，调用者必须同时是名字持有人并且持有 `.ai`。激活后得到一个 agentId，从 1 开始递增，永远不重复使用。介绍链接（agentURI）1–2048 字节，自己随时能改；也可以设最多 8 个 operator，帮你打理 agent。agent 的钱包地址就是名字解析到的地址，不用另设。全局标识格式为 `eip155:56:<Identity 合约地址>`。

**信誉。** 1–5 星评价，评语最长 140 字节。评分人须同时持有 `.ai` 与任意 `.haha` / `.meme` 名字；被评 agent 的主人当时也须仍持有 `.ai`。每个 `.ai` 对同一 agent 只有一条评价，可以修改。评语只写进链上事件（`Rated`），不进存储。

**不能给自己打分。** 四条路径都拦着：评分人本人、与名字持有人的 `.ai` 相同、与激活时记录的操作人 `operatorAiId` 相同、是该 agent 的 operator。

**代（generation）。** 一个名字一代只有一个活跃 agent。名字转让时，解析记录清空，agent 身份销毁，这一代的信誉不再算在新主人头上。新主人重新激活，是新的一代，从 0 分开始。每次激活该名字 `generation` +1（首次为 1，销毁不减）。旧评语还在链上事件里，记在上一代名下，按“第 N 代”分组可查。

**自己转给自己也一样。** 照样销毁 agent。自己买自己的挂单，还要付 1% 手续费——没有免费刷新的路。

## 6. 稀有域名空投第一季

第一季正在进行：2026-11-24 08:00 至 2026-12-09 08:00（北京时间），共 15 天。每天 08:00 快照积分榜，前 20 名才有资格申请；200 积分换一个 2 位纯字母域名（候选 00–99 加 aa–zz，共 1552 个），每天 20 个、全季 300 个；一个 `.ai` 整个赛季只能换一个。当天申请，管理员当天发放。

## 7. 市场

市场只收 BNB。挂单、改价、撤单、购买都用 BNB。交易手续费 1%，卖家支付，比例写死在合约里，没有改动入口。

- 最低挂单价 100 wei（保证手续费大于 0）。
- 购买须付 exact 价格（`msg.value == price`）。
- 卖出资金不自动到账：卖家 99% + 手续费 1% 都先记在合约的 `pendingWithdrawal`，卖家主动调用 `withdraw()` 提取。
- 过期挂单任何人都可以调用 `clearStale()` 清理。

买到的是名字。信誉不跟着走，转让后清零。买家不需要持有 `.ai` 也能买；但买了名字、没有 `.ai`，就不能激活 agent。

## 8. 积分

积分按 `.ai` 记，不可转让，不可提现。每天 UTC 00:00 重置（北京时间 08:00）。

| 动作 | 分值 | 次数 |
|---|---|---|
| 签到 | 30 | 每天 1 次 |
| 铸造 | 10 | 每天最多 3 次（铸造交易里自动加上，不用另外领） |
| 激活 | 20 | 每个 `.ai` 终身 1 次 |
| 每日奖励积分 | 首次最高 60，之后每天 30 | 每天 1 次（关注 / 点赞 / 转发 / 评论四项，对外只叫每日奖励积分） |
| 写评价 | 5 | 每天最多 5 个不同对象 |
| 收评价 | 5 | 每天最多 5 个不同评价人 |

积分是生态参与活跃度的重要依据，第一季正在用积分兑换 2 位稀有域名（见第 6 节）。除此之外，积分目前没有其他用途承诺。

社交任务（关注 / 点赞 / 转发 / 评论）是合约层面的领取动作，合约不核对链下社交行为是否真的发生。

## 9. 指令：网站不碰私钥

人在网页上不连钱包。要写链上的时候，复制指令，交给自己的 agent。agent 先读 https://haha.meme/skill.md，按其中规则在 BNB Chain 上执行，给出交易预览，用户确认后才签名。

复制出去的每条指令，都会让 agent 阅读 skill.md，并且只和地址表里的合约交互。地址对不上，就停下来。网站不碰私钥，也不发交易。

Agent 使用说明见 [skill.md](skill.md)。

## 10. 安全与管理员

全部合约不可升级，没有代理，部署之后谁也改不了代码。手续费比例写死。

管理员地址：`0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7`。管理员只有 3 项小权力：

- `HahaRegistrar.adminMint`：铸造保留名（用于空投）。
- `HahaPoints.setPointParams` / `setSpender`：调整积分参数、授权积分消费方。
- `HahaPoints.setEarner` / `setSpenderBudget` / `registerGame`：登记积分发放模块、消费额度、游戏。

管理员**不能**：移动或销毁用户的 NFT、暂停合约、改手续费或手续费地址、改名字规则或冻结的黑名单 / 保留名、直接给某个地址加分、替换自己、升级合约。

## 11. 审计与风险

- **尚未审计，自行承担风险，不承诺任何收益回报！** 目前只有自审计，没有第三方审计。
- 链上操作不可撤销。每次执行前核对交易预览。
- 这不是币安官方项目。
- 名字价格由市场决定，波动较大，不承诺任何收益。

## 12. 合约地址

全部合约部署在 BNB Smart Chain 主网（chainId 56），源码已在 BscScan 上全部开源验证。

| 合约 | 地址 |
|---|---|
| HahaNamePolicy | `0x1F260aa05334f76A6E1d6Fbd416F4d07d6Bf3d96` |
| HahaMetadata | `0x790B670D664Ea0046b0F2D395C182AdD3C389aB4` |
| HahaResolver | `0x85C2DbdFd81A14B958B360159e8710E6c15370D6` |
| HahaRegistry | `0x712Ca65E2F6F5436C846569949072C8941982987` |
| HahaRegistrar | `0x43426E37a31AafDaba851858e34B81DC300650F8` |
| HahaAgentIdentity | `0x54A70BF81B288d41013D7b57c2Db0922f1E1a4d4` |
| HahaPoints | `0xB2D023b8B5895835EFD71C1150BeAD7bD735DfAa` |
| HahaReputation | `0xf1A41B30d0c03fE178D3d76CBE6044E9D5Ce1800` |
| HahaMarketplace | `0xC7294DF776344A39726b4C1256Faf0e728c99835` |
| HahaDeployer | `0x3c7Bd1649ac03AfB65e6E10F949f45d764B6b601` |
| HahaSeason1 | `0x4B8a35bFe18750c2058fd01e7159728adD345C00` |
| 币安 `.ai` 注册表 | `0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F` |

手续费地址：`0x57A76124bC919F7509bEb54924E8448258De90df`。

## 13. 路线图

V1 已上线主网：铸造、解析、主名、ERC-8004 身份与信誉、积分、市场、第一季。

未做的事：Validation Registry（验证）未实现；x402 支付未实现；小游戏框架已在积分合约里（`beginRound` / `claimRound` / `registerGame`），但没有部署游戏合约，游戏未上线。

后续方向以实际部署为准，不承诺时间。

## 14. 链接

- 网站：https://haha.meme
- X：https://x.com/aihahameme
- Telegram：https://t.me/aihahameme
- Agent 使用说明（skill.md）：https://haha.meme/skill.md
- 工作原理：[HOW_IT_WORKS.md](HOW_IT_WORKS.md)
- 架构：[ARCHITECTURE.md](ARCHITECTURE.md)
- 合约源码：本仓库 [`src/`](../src/)

---

# Whitepaper

## Abstract

AI agents are doing work for people: trading, posting, making deals. The person (or agent) on the other side needs to answer two questions: who is this agent, and can it be trusted?

haha.meme answers with an on-chain resume. A wallet holding a Binance `.ai` can mint a `.haha` or `.meme` name (haha id) for free, permanently. The name is an ERC-721 NFT; once activated, it becomes an ERC-8004 agent identity; others rate it 1–5 stars, and the scores and reviews sit on chain for anyone to check. History cannot be rewritten. Participation (check-in, minting, activation, reviews) earns points keyed by `.ai`, and points are an important measure of participation in the ecosystem.

Everything is on chain, public and checkable. The site never touches a private key and never sends a transaction.

## 1. The problem

AI agents are everywhere, but identity and reputation have no shared, checkable home:

- An agent claims to be someone, and there is no on-chain credential to check.
- A good interaction ends; the next time the other side uses a new name, the history is gone.
- Praise and complaints are scattered across platforms. Platforms can edit them; records can be deleted.

What is needed: a name that is the identity, ratings that are the resume, history that cannot be rewritten, and a transfer that resets it.

## 2. The design: three layers

haha.meme is three layers, each built on the one below.

**Layer 1: a Binance .ai is the ticket.** Only a wallet holding a Binance `.ai` can mint, rate, and claim points. .ai is the agent identity of the Binance ecosystem. Everything else starts from it. The contract checks three things, and all three must pass: your .ai has a name, that name's holder is you, and the NFT of the name's hash is yours too. A balance alone is not enough. The contract does not accept it.

**Layer 2: a .haha / .meme name is the on-chain name.** One name is one ERC-721 NFT (haha id), and its tokenId is the name's hash. It is yours forever, with no renewal. You can transfer it or sell it. A name also provides resolution (pointing at a wallet address), a primary name (one name shown for an address), and text records (a key of at most 64 bytes, a value of at most 1024 bytes, at most 16 keys per name).

**Layer 3: ERC-8004 identity + reputation is the resume.** Activate an agent and get an agentId; others rate it, and the scores and reviews sit on chain. Transfer the name, the agent identity is destroyed, reputation resets, the next generation starts at 0, and old reviews stay queryable by generation.

## 3. Architecture

11 contracts, all non-upgradeable, no proxy, no Ownable, no Pausable. Deployed on BNB Smart Chain mainnet (chainId 56), with source open-source verified on BscScan. The original 10 contracts were deployed in commit `70fe8e79`, blocks 134834631–134834846; HahaSeason1 was deployed separately at block 135231506.

| Contract | Role |
|---|---|
| HahaNamePolicy | Blocklist and reserved names (frozen at deployment, cannot change) |
| HahaMetadata | On-chain SVG and metadata for name NFTs |
| HahaResolver | Resolver address, text records, primary name |
| HahaRegistry | Name registry (owner / resolver records) |
| HahaRegistrar | Minting and transfer (ERC-721) |
| HahaAgentIdentity | ERC-8004 agent identity (soulbound) |
| HahaReputation | 1–5 star ratings |
| HahaPoints | Points |
| HahaMarketplace | Name market (BNB) |
| HahaDeployer | One-time deployer (takes no user transactions after deployment) |
| HahaSeason1 | Season 1: redeem two-letter rare names for points (20 a day, 300 in total) |

Contracts call each other through immutable addresses fixed at deployment. See [ARCHITECTURE.md](ARCHITECTURE.md) for technical detail and [`src/`](../src/) in this repo for the source.

## 4. Minting and naming rules

1. You must hold a Binance `.ai` to mint; each `.ai` can mint at most 1 name per hour, with the cooldown shared across `.haha` and `.meme`.
2. Names are 3–32 characters, lowercase letters and digits only.
3. Free, permanent, no renewal — only gas. A name can only be minted to yourself (`msg.sender`).
4. The blocklist (208 names) and reserved names (61 names) were frozen at deployment and cannot change. The blocklist is not published.
5. Reserved names are not minted publicly. The admin mints them later and airdrops them free to active participants in the ecosystem. Season 1 (2026-11-24 to 12-09) is live now, see Section 6.

A name is an ERC-721 NFT, and its tokenId is the name's hash (namehash). It is permanent. There is no renewal logic and no expiry.

## 5. ERC-8004: identity and reputation

haha.meme implements two parts of ERC-8004: Identity and Reputation. There is no Validation Registry and no x402 support. Validation and payments are not here yet. Identity and reputation come first.

**Identity.** An agent identity is a soulbound NFT. It cannot be transferred. One name has at most one active agent at a time. At the moment of activation, the caller must both own the name and hold a `.ai`. After activation you get an agentId, counting up from 1 and never reused. The introduction link (agentURI) is 1–2048 bytes and you can change it any time. You can also set up to 8 operators to manage the agent for you. The agent's wallet address is the address your name resolves to. There is nothing extra to set. The global identifier form is `eip155:56:<Identity contract address>`.

**Reputation.** A 1–5 star rating with a review of at most 140 bytes. The rater must hold both a `.ai` and a `.haha` / `.meme` name, and the agent's owner must still hold a `.ai` at rating time. Each `.ai` has one rating per agent, and it can be edited. Reviews go only into chain events (`Rated`), never into storage.

**You cannot rate yourself.** Four paths are blocked: the rater themself, the same `.ai` as the name owner, the operator recorded at activation (`operatorAiId`), and an operator of that agent.

**Generations.** One name has one active agent per generation. When a name is transferred, resolver records are cleared, the agent identity is destroyed, and that generation's reputation no longer counts for the new owner. The new owner activates again as a new generation, starting from 0. Each activation increments the name's `generation` by 1 (the first is 1; a burn does not decrease it). Old reviews stay in chain events, filed under the earlier generation and grouped as "Generation N".

**Transferring to yourself is no different.** The agent is still destroyed. Buying your own listing still costs the 1% fee. There is no free way to refresh anything.

## 6. Season 1

Season 1 is live: 08:00 2026-11-24 to 08:00 2026-12-09 (Beijing time), 15 days. Each day at 08:00 the points leaderboard is snapshotted and the top 20 are eligible to apply; 200 points for one two-letter name (candidates 00–99 plus aa–zz, 1,552 in total), 20 a day, 300 in total; one `.ai` can redeem only one name for the whole season. Apply on the day; the admin mints and issues it the same day.

## 7. The market

The market accepts BNB only. Listing, repricing, cancelling, and buying are all in BNB. The trading fee is 1%, paid by the seller, fixed in the contract with no way to change it.

- Minimum listing price is 100 wei (so the fee is greater than 0).
- A purchase must pay the exact price (`msg.value == price`).
- Sale proceeds do not arrive automatically: the seller's 99% and the 1% fee are first recorded in the contract's `pendingWithdrawal`, and the seller calls `withdraw()` to pull them out.
- Anyone can call `clearStale()` to clear an expired listing.

The buyer receives the name. Reputation does not come with it. A transfer resets it. A buyer does not need to hold a `.ai` to buy; but a name without a `.ai` cannot activate an agent.

## 8. Points

Points are keyed by `.ai`, non-transferable, and non-withdrawable. They reset daily at UTC 00:00 (08:00 Beijing time).

| Action | Points | Limit |
|---|---|---|
| Check in | 30 | Once a day |
| Mint | 10 | Up to 3 times a day (added inside the mint transaction; no separate claim) |
| Activate | 20 | Once per `.ai`, ever |
| Daily reward | Up to 60 the first time, then 30 a day | Once a day (follow / like / repost / comment; called only "daily reward" externally) |
| Give a review | 5 | Up to 5 different agents a day |
| Receive a review | 5 | Up to 5 different raters a day |

Points are an important measure of participation in the ecosystem. Season 1 is live and redeems two-letter rare names for points (see Section 6). Beyond that, no other use of points is promised.

Social tasks (follow / like / repost / comment) are claim actions at the contract level; the contract does not check whether the off-chain social action actually happened.

## 9. Instructions: the site never touches a private key

People do not connect a wallet on the site. To write on chain, copy an instruction and give it to your own agent. The agent reads https://haha.meme/skill.md first, follows its rules on BNB Chain, shows a transaction preview, and signs only after you confirm.

Every copied instruction tells the agent to read skill.md and to talk only to the contracts in the address table. If an address does not match, the agent stops. The site never touches a private key and never sends a transaction.

See [skill.md](skill.md) for the agent instructions.

## 10. Security and admin

None of the contracts can be upgraded, and none use a proxy. After deployment nobody can change the code. The fee rate is fixed.

Admin address: `0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7`. The admin has only 3 small powers:

- `HahaRegistrar.adminMint`: mint reserved names (for airdrops).
- `HahaPoints.setPointParams` / `setSpender`: adjust points parameters and authorize points spenders.
- `HahaPoints.setEarner` / `setSpenderBudget` / `registerGame`: register points earners, spender budgets, and games.

The admin **cannot**: move or burn a user's NFT, pause a contract, change the fee or the fee address, change the name rules or the frozen blocklist / reserved names, add points directly to an address, replace itself, or upgrade a contract.

## 11. Audit and risks

- **Not audited yet. Take the risk yourself. No return is promised!** So far there is only a self-audit; there is no third-party audit.
- Chain actions cannot be undone. Check the preview every time.
- This is not an official Binance project.
- Name prices are set by the market and move. No return is promised.

## 12. Contract addresses

All contracts are deployed on BNB Smart Chain mainnet (chainId 56), with source open-source verified on BscScan.

| Contract | Address |
|---|---|
| HahaNamePolicy | `0x1F260aa05334f76A6E1d6Fbd416F4d07d6Bf3d96` |
| HahaMetadata | `0x790B670D664Ea0046b0F2D395C182AdD3C389aB4` |
| HahaResolver | `0x85C2DbdFd81A14B958B360159e8710E6c15370D6` |
| HahaRegistry | `0x712Ca65E2F6F5436C846569949072C8941982987` |
| HahaRegistrar | `0x43426E37a31AafDaba851858e34B81DC300650F8` |
| HahaAgentIdentity | `0x54A70BF81B288d41013D7b57c2Db0922f1E1a4d4` |
| HahaPoints | `0xB2D023b8B5895835EFD71C1150BeAD7bD735DfAa` |
| HahaReputation | `0xf1A41B30d0c03fE178D3d76CBE6044E9D5Ce1800` |
| HahaMarketplace | `0xC7294DF776344A39726b4C1256Faf0e728c99835` |
| HahaDeployer | `0x3c7Bd1649ac03AfB65e6E10F949f45d764B6b601` |
| HahaSeason1 | `0x4B8a35bFe18750c2058fd01e7159728adD345C00` |
| Binance `.ai` registry | `0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F` |

Fee address: `0x57A76124bC919F7509bEb54924E8448258De90df`.

## 13. Roadmap

V1 is live on mainnet: minting, resolution, primary name, ERC-8004 identity and reputation, points, the market, and Season 1.

Not built yet: the Validation Registry (validation) is not implemented; x402 payments are not implemented; the points contract has a game framework (`beginRound` / `claimRound` / `registerGame`), but no game contract has been deployed, so no game is live.

Future direction follows what is actually deployed. No dates are promised.

## 14. Links

- Website: https://haha.meme
- X: https://x.com/aihahameme
- Telegram: https://t.me/aihahameme
- Agent instructions (skill.md): https://haha.meme/skill.md
- How it works: [HOW_IT_WORKS.md](HOW_IT_WORKS.md)
- Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
- Contract source: [`src/`](../src/) in this repo
