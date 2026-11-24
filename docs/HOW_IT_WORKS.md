# haha.meme · 工作原理 / How It Works

> 本文档为中英双语。中文在前，英文在后。
> This document is bilingual. Chinese first, English second.

---

# 工作原理

**公开、可核对。**

haha.meme 是基于币安 .ai Agent ID 的链上 agent 身份信誉协议。名字是身份，信誉是简历，积分是参与的记录。全部写在链上，公开可核对。网站不碰私钥，也不发交易。

- 网站：https://haha.meme
- X：https://x.com/aihahameme
- Telegram：https://t.me/aihahameme

---

## 1. 这是什么

AI agent 越来越多替人干活：交易、发帖、谈合作。对方怎么知道这个 agent 是谁、靠不靠谱？看它的链上简历。

haha.meme 给每个 agent 一个链上身份：一个名字，一份改不了的评分记录，一份参与记录。

- **币安 .ai 是门票。** 只有持有币安 .ai 的钱包，才能铸造、评分、领分。.ai 是 Binance 生态的 agent 身份，先有它，才有后面的一切。
- **.haha / .meme 名字是你的链上名字。** 一个名字就是一个 NFT，永久属于你，没有续费，可以转让、可以卖。
- **ERC-8004 agent 身份 + 星级信誉是你的简历。** 激活 agent，别人给你打分，分数和评语都写在链上，谁都能查，谁也改不了历史。

## 2. 五步上手

1. 持有币安 .ai。
2. 免费铸一个 .haha 或 .meme 名字，只付 gas。
3. 激活 ERC-8004 agent，得到一个 agentId。
4. 被别人评分，攒信誉；每天签到、铸造，攒积分。
5. （可选）把名字挂到市场上卖，收 BNB。

## 3. .ai 是门票

铸造、签到、评分、领分，都要求交易发送者持有币安 .ai。网页登录只是把这个名字带进指令和只读查询，不代表链上持有。

合约核对三件事，全部通过才算持有：你的 .ai 有名字、这个名字的持有人是你、名字哈希对应的 NFT 也是你的。只看余额不够，合约不认。

## 4. 铸造

铸造免费，不续费，只能铸造给自己。.haha 和 .meme 两个后缀共用每个 .ai 一小时限制铸造一次的额度。规则如下：

1. 币安 .ai 域名持有者即可免费铸造 haha id，永久免费，无需续费。
2. 名称规则：3–32 位小写字母或数字。
3. 每个 .ai 每小时最多可铸造 1 个，防女巫抢注。
4. 保留名：1–2 位短名和部分 3 位以上的名字为保留名，通过第一季（见第 10 节）兑换给活跃参与者！

有些词铸不了，黑名单词表不公开列出。

名字是 ERC-721 NFT，tokenId 就是名字的哈希。永久，没有续费逻辑，也没有过期。

保留名不经过公开铸造，第一季里由管理员铸造并发放给符合条件的参与者（见第 10 节）。

## 5. 名字能干什么

名字不只是一个名字，它是你的链上身份入口。

- **解析。** 名字可以指向一个钱包地址，那就是你的 agent 的收款地址、身份地址。没设指向时，默认指向名字持有人。
- **主名。** 一个地址对外只亮一个名字。设了主名，别人搜你的钱包，看到的就是这个名字。
- **文本记录。** 名字上可以写文本，比如介绍、链接。key 最长 64 字节，value 最长 1024 字节，每个名字最多 16 条。

转让时，这些记录全部清空。

## 6. ERC-8004

haha id，就是 Agent 的简历；信誉，写在链上。

ERC-8004 是 agent 的链上身份与信誉标准，分三块：身份、信誉、验证。haha.meme 做了前两块：身份（灵魂绑定，不可转让）+ 信誉（1–5 星评分）。验证（Validation Registry）和 x402 支付还没做，先把身份和信誉做实。

激活是自愿的，一个名字一代只有一个 agent。激活那一刻，你必须持有 .ai。激活后得到一个 agentId，从 1 开始递增，永远不重复使用。

agent 身份是灵魂绑定 NFT，不能转让。介绍链接（agentURI）1–2048 字节，自己随时能改；也可以设最多 8 个 operator，帮你打理 agent。你的 agent 钱包地址，就是名字解析到的地址，不用另设。

评分：1–5 星，评语 140 字节以内，每人每个 agent 一条，可改。评分的人自己也要同时持有 .ai 和一个 haha id；被评的 agent 的主人当时也要还持有 .ai。

不能给自己打。以下四条路都拦着：本人、同一个 .ai、激活时的操作人、agent 的 operator。

评语只写进链上事件，不进存储。想看评语，去链上事件里找——本站的历代页面就是从事件里读出来的。

一个名字一代只有一个活跃 agent。名字转让，agent 身份销毁，这一代的信誉不再算在新主人头上。新主人重新激活，是新的一代，从 0 分开始。旧评语还在链上事件里，记在上一代名下，按“第 N 代”分组可查。

## 7. 转让会发生什么

名字可以转。转走后，解析地址和文本记录清空，agent 身份销毁，这一代的信誉不再算在新主人头上。旧评语还在链上事件里，记在上一代名下。

自己转给自己也一样：照样销毁 agent。自己买自己的挂单，还要付 1% 手续费——没有免费刷新的路。

## 8. 市场

交易手续费 1%，卖家支付。

用 BNB 挂单、改价、撤单、购买。手续费 1%，卖家支付。买到的是名字。信誉不跟着走，转让后清零。

买家不需要持有 .ai 也能买。但买了名字、没有 .ai，就不能激活 agent。

## 9. 积分

| 动作 | 分值 | 次数 |
|---|---|---|
| 签到 | 30 | 每天 1 次 |
| 铸造 | 10 | 每天最多 3 次 |
| 激活 | 20 | 每个 .ai 终身 1 次 |

每日重置时间：UTC 00:00（北京时间 08:00）。

积分记在 .ai 名下，不可转让。每天 UTC 0 点重置日任务（北京时间 08:00）。铸造分在铸造交易里自动加上，不用另外领。

积分有什么用。积分是生态参与活跃度的重要依据。第一季已经上线：200 积分可以换一个 2 位保留稀有域名，详见第 10 节。

## 10. 第一季

第一季已经上线：2026 年 11 月 24 日 08:00 至 2026 年 12 月 9 日 08:00（北京时间），共 15 天。

- 200 积分换一个 2 位纯字母稀有域名。候选：00–99 加 aa–zz，共 1552 个。
- 每天 20 个名额，全季 300 个。一个 .ai 整个赛季只能换一个。
- 每天 08:00 快照积分榜，前 20 名才有资格。当天申请，管理员当天发放（窗口结束 12 小时内）。
- 第一季里多赚积分：每日验证 +30 分（核对当天任务包）；找错 +100 分（发现真实问题，审核通过后领）。

## 11. 指令

人在网页上不连钱包。要写链上的时候，复制指令，交给自己的 agent。agent 先读 https://haha.meme/skill.md，给出交易预览，用户确认后才签名。

网站不碰私钥，也不发交易。

复制出去的每条指令，都会让 agent 阅读 https://haha.meme/skill.md，并且只和本文地址表里的合约交互。地址对不上，就停下来。

一个写操作就是一段自然语言，复制给自己的 agent（Binance Agentic Wallet），agent 按 skill.md 执行。15 个写操作：铸造、授权、挂单、改价、撤单、清过期挂单、购买、提取、激活、改 URI、设 agent operator、评分、签到、关注 / 点赞 / 转发 / 评论、设主名 / 解析 / 文本。

## 12. 合约与开源

下面是全部合约地址，点地址可以在 BscScan 上查看已开源验证的代码。

11 个合约的源码已在 BscScan 上全部开源验证。部署在 BNB Smart Chain 主网（chainId 56）。原 10 个合约部署 commit 70fe8e79，部署区块 134834631–134834846；HahaSeason1 单独部署在区块 135231506。

| 合约 | 地址 |
|---|---|
| HahaNamePolicy（部署区块 134834631） | `0x1F260aa05334f76A6E1d6Fbd416F4d07d6Bf3d96` |
| HahaMetadata（部署区块 134834660） | `0x790B670D664Ea0046b0F2D395C182AdD3C389aB4` |
| HahaResolver（部署区块 134834683） | `0x85C2DbdFd81A14B958B360159e8710E6c15370D6` |
| HahaRegistry（部署区块 134834708） | `0x712Ca65E2F6F5436C846569949072C8941982987` |
| HahaRegistrar（部署区块 134834735） | `0x43426E37a31AafDaba851858e34B81DC300650F8` |
| HahaAgentIdentity（部署区块 134834759） | `0x54A70BF81B288d41013D7b57c2Db0922f1E1a4d4` |
| HahaPoints（部署区块 134834780） | `0xB2D023b8B5895835EFD71C1150BeAD7bD735DfAa` |
| HahaReputation（部署区块 134834803） | `0xf1A41B30d0c03fE178D3d76CBE6044E9D5Ce1800` |
| HahaMarketplace（部署区块 134834824） | `0xC7294DF776344A39726b4C1256Faf0e728c99835` |
| HahaDeployer（部署区块 134834846） | `0x3c7Bd1649ac03AfB65e6E10F949f45d764B6b601` |
| HahaSeason1（部署区块 135231506） | `0x4B8a35bFe18750c2058fd01e7159728adD345C00` |
| 币安 .ai 注册表 | `0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F` |
| 管理员地址 | `0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7` |
| 手续费地址 | `0x57A76124bC919F7509bEb54924E8448258De90df` |

全部合约不可升级，没有代理，部署之后谁也改不了代码。手续费比例写死。管理员不能改手续费，不能没收用户的名字。

## 13. 审计与开源

尚未审计，自行承担风险，不承诺任何收益回报！

## 14. 风险和常见问题

- 链上操作不可撤销。每次执行前核对预览。
- 这不是币安官方项目。

---

## 相关链接

- 白皮书：[docs/WHITEPAPER.md](WHITEPAPER.md)
- 架构：[docs/ARCHITECTURE.md](ARCHITECTURE.md)
- Agent 使用说明：[docs/skill.md](skill.md)（网站版：https://haha.meme/skill.md）
- 合约源码：本仓库 [`src/`](../src/)

---

# How It Works

**Public and checkable.**

haha.meme is an on-chain agent identity and reputation protocol built on Binance .ai Agent IDs. A name is your identity, reputation is your resume, and points record your participation. Everything is on chain, public and checkable. The site never touches a private key and never sends a transaction.

- Website: https://haha.meme
- X: https://x.com/aihahameme
- Telegram: https://t.me/aihahameme

---

## 1. What this is

AI agents do more and more work for people: trading, posting, making deals. How does the other side know who an agent is, and whether it can be trusted? Look at its on-chain resume.

haha.meme gives every agent an on-chain identity: a name, a rating record that cannot be changed, and a record of participation.

- **A Binance .ai is the ticket.** Only a wallet holding a Binance .ai can mint, rate, and claim points. .ai is the agent identity of the Binance ecosystem. Everything else starts from it.
- **A .haha or .meme name is your on-chain name.** One name is one NFT. It is yours forever, with no renewal. You can transfer it or sell it.
- **An ERC-8004 agent identity plus star ratings is your resume.** Activate an agent, let others rate it, and the scores and reviews sit on chain for anyone to check. History cannot be rewritten.

## 2. Five steps

1. Hold a Binance .ai.
2. Mint a .haha or .meme name for free. You only pay gas.
3. Activate an ERC-8004 agent and get an agentId.
4. Get rated by others to build reputation. Check in and mint daily to earn points.
5. (Optional) List the name on the market and receive BNB.

## 3. .ai is the ticket

Minting, check-in, rating, and claiming points all require the sender to hold a Binance .ai. Logging in on the site only puts that name into instructions and read-only lookups. It does not prove the chain holds it.

The contract checks three things, and all three must pass: your .ai has a name, that name's holder is you, and the NFT of the name's hash is yours too. A balance alone is not enough. The contract does not accept it.

## 4. Minting

Minting is free, with no renewal, and you can only mint to yourself. The .haha and .meme suffixes share a limit of one mint per .ai per hour. The rules:

1. Anyone who holds a Binance .ai can mint a haha id for free, forever, with no renewal.
2. Names are 3–32 lowercase letters or digits.
3. Each .ai can mint at most once per hour, to slow sniping.
4. Reserved names: 1–2 character names, and some longer ones, are reserved for active participants and redeemed through Season 1 (see Section 10).

Some words cannot be minted. The blocklist is not published.

A name is an ERC-721 NFT. Its tokenId is the hash of the name. It is permanent. There is no renewal logic and no expiry.

Reserved names are not minted publicly. In Season 1 the admin mints and issues them to qualifying participants (see Section 10).

## 5. What a name can do

A name is more than a name. It is the entry point to your on-chain identity.

- **Resolution.** A name can point to a wallet address: your agent's receiving address and identity address. Without an override, it points to the name's holder.
- **Primary name.** An address shows only one name to the outside world. Set a primary name, and anyone looking up your wallet sees that name.
- **Text records.** A name can carry text, such as an introduction or a link. A key is at most 64 bytes, a value at most 1024 bytes, and a name holds at most 16 keys.

A transfer clears all of these records.

## 6. ERC-8004

A haha id is an agent's resume. Reputation is written on chain.

ERC-8004 is the on-chain standard for agent identity and reputation. It has three parts: identity, reputation, and validation. haha.meme ships the first two: identity (soulbound, non-transferable) and reputation (1–5 star ratings). Validation (the Validation Registry) and x402 payments are not here yet. Identity and reputation come first.

Activation is voluntary. One name has one agent per generation. At the moment of activation, you must hold a .ai. After activation you get an agentId, counting up from 1 and never reused.

An agent identity is a soulbound NFT. It cannot be transferred. The introduction link (agentURI) is 1–2048 bytes and you can change it any time. You can also set up to 8 operators to manage the agent for you. Your agent's wallet address is the address your name resolves to. There is nothing extra to set.

Rating: 1–5 stars, a review of at most 140 bytes, one review per person per agent, editable. The rater must hold a .ai and a haha id themselves, and the agent's owner must still hold a .ai at rating time.

You cannot rate yourself. Four paths are blocked: yourself, the same .ai, the operator recorded at activation, and an operator of that agent.

Reviews go only into chain events, never into storage. To read a review, look at the events. This site's generation pages read them from there.

One name has one active agent per generation. When a name is transferred, the agent identity is destroyed, and that generation's reputation no longer counts for the new owner. The new owner activates again as a new generation, starting from 0. Old reviews stay in chain events, filed under the earlier generation and grouped as "Generation N".

## 7. What a transfer does

Names can be transferred. Resolver addresses and text records are cleared, the agent identity is destroyed, and that generation's reputation no longer counts for the new owner. Old reviews remain in chain events, on the previous generation.

Transferring to yourself is no different: the agent is still destroyed. Buying your own listing still costs the 1% fee. There is no free way to refresh anything.

## 8. The market

Trading fee is 1%, paid by the seller.

List, reprice, cancel, and buy with BNB. The fee is 1%, paid by the seller. The buyer receives the name. Reputation does not come with it. A transfer resets it.

A buyer does not need to hold a .ai to buy. But a name without a .ai cannot activate an agent.

## 9. Points

| Action | Points | Limit |
|---|---|---|
| Check in | 30 | Once a day |
| Mint | 10 | Up to 3 times a day |
| Activate | 20 | Once per .ai, ever |

Daily reset: UTC 00:00 (08:00 Beijing time).

Points sit on your .ai and cannot be transferred. Daily tasks reset at 00:00 UTC (08:00 Beijing time). Mint points are added inside the mint transaction, so there is nothing extra to claim.

What are points for? Points are an important measure of participation in the ecosystem. Season 1 is already live: 200 points can be exchanged for a two-character reserved rare name. See Section 10.

## 10. Season 1

Season 1 is live: 08:00, 24 November 2026 to 08:00, 9 December 2026 (Beijing time), 15 days in total.

- 200 points for one two-character pure-letter rare name. Candidates: 00–99 plus aa–zz, 1,552 in total.
- 20 slots a day, 300 for the whole season. One .ai can redeem at most one name for the whole season.
- Every day at 08:00 the points leaderboard is snapshotted; only the top 20 qualify. Apply the same day; the admin mints and issues the name the same day (within 12 hours after the window ends).
- Earn extra points in Season 1: daily verification +30 points (check the day's task pack); finding a real problem +100 points (after review).

## 11. Instructions

People do not connect a wallet on the site. To write on chain, copy an instruction and give it to your own agent. The agent reads https://haha.meme/skill.md, shows a transaction preview, and signs only after you confirm.

The site never touches a private key and never sends a transaction.

Every copied instruction tells the agent to read https://haha.meme/skill.md and to talk only to the contracts in this page's address table. If an address does not match, the agent stops.

One write action is one piece of plain language. Copy it to your own agent (Binance Agentic Wallet) and the agent follows skill.md. 15 write actions: mint, approve, list, reprice, cancel, clear stale listing, buy, withdraw, activate, change URI, set agent operator, rate, check in, follow / like / repost / comment, and set primary name / resolver address / text.

## 12. Contracts and source

Every contract address is below. Open an address to read the verified source on BscScan.

All 11 contracts are open-source verified on BscScan. They are deployed on BNB Smart Chain mainnet (chainId 56). The original 10 contracts were deployed in commit 70fe8e79, blocks 134834631–134834846; HahaSeason1 was deployed separately in block 135231506.

| Contract | Address |
|---|---|
| HahaNamePolicy (deployed in block 134834631) | `0x1F260aa05334f76A6E1d6Fbd416F4d07d6Bf3d96` |
| HahaMetadata (deployed in block 134834660) | `0x790B670D664Ea0046b0F2D395C182AdD3C389aB4` |
| HahaResolver (deployed in block 134834683) | `0x85C2DbdFd81A14B958B360159e8710E6c15370D6` |
| HahaRegistry (deployed in block 134834708) | `0x712Ca65E2F6F5436C846569949072C8941982987` |
| HahaRegistrar (deployed in block 134834735) | `0x43426E37a31AafDaba851858e34B81DC300650F8` |
| HahaAgentIdentity (deployed in block 134834759) | `0x54A70BF81B288d41013D7b57c2Db0922f1E1a4d4` |
| HahaPoints (deployed in block 134834780) | `0xB2D023b8B5895835EFD71C1150BeAD7bD735DfAa` |
| HahaReputation (deployed in block 134834803) | `0xf1A41B30d0c03fE178D3d76CBE6044E9D5Ce1800` |
| HahaMarketplace (deployed in block 134834824) | `0xC7294DF776344A39726b4C1256Faf0e728c99835` |
| HahaDeployer (deployed in block 134834846) | `0x3c7Bd1649ac03AfB65e6E10F949f45d764B6b601` |
| HahaSeason1 (deployed in block 135231506) | `0x4B8a35bFe18750c2058fd01e7159728adD345C00` |
| Binance .ai registry | `0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F` |
| Admin address | `0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7` |
| Fee address | `0x57A76124bC919F7509bEb54924E8448258De90df` |

None of the contracts can be upgraded, and none use a proxy. After deployment nobody can change the code. The fee rate is fixed. The admin cannot change the fee and cannot take a user's name.

## 13. Audit and source

Not audited yet. Take the risk yourself. No return is promised!

## 14. Risks and common questions

- Chain actions cannot be undone. Check the preview every time.
- This is not an official Binance project.

---

## Links

- Whitepaper: [docs/WHITEPAPER.md](WHITEPAPER.md)
- Architecture: [docs/ARCHITECTURE.md](ARCHITECTURE.md)
- Agent instructions: [docs/skill.md](skill.md) (live site: https://haha.meme/skill.md)
- Contract source: [`src/`](../src/) in this repo
