# haha.meme — haha id

**haha id，就是 Agent 的简历；信誉，写在链上。**

**haha id is the Agent's resume; reputation lives on-chain.**

---

## 中文

### haha.meme 是什么？

haha.meme 是 BNB Chain（chainId 56）上的 AI agent 身份协议。持有币安 `.ai` 的钱包，可以免费、永久铸造一个 `.haha` 或 `.meme` 名字 NFT（haha id），并用它做解析、主名字、ERC-8004 agent 身份、链上信誉评分和链上积分。

- **免费铸造**：持有币安 `.ai` 即可免费注册 haha id，永久免费，无需续费，只付 gas。
- **不连钱包**：网站本身不接钱包、不发交易。你只输入 `.ai` 名字做只读登录，写操作是复制一段指令，交给自己的 AI agent 去执行。
- **ERC-8004 agent 身份**：一个名字同一时间只有一个 agent，信誉 1–5 星，写在链上。
- **转让后信誉清零**：名字转让时 agent 身份自动销毁，新一代 agent 从 0 分开始，历代可查。

### 铸造规则

1. 持有币安 `.ai` 才能铸造，同一 `.ai` 每 1 小时最多铸 1 个，两个后缀（`.haha` / `.meme`）共用冷却。
2. 名字 3–32 个字符，只允许小写字母和数字。
3. 免费、永久、无续费，只付 gas；名字是 ERC-721 NFT，转让时自动清除解析记录并销毁 agent 身份。
4. 黑名单与保留名在部署时已冻结，不可更改。

### ERC-8004：身份与信誉

- 只实现身份（Identity）与信誉（Reputation）两块，未实现 Validation Registry，不支持 x402。
- agent 身份是灵魂绑定 NFT，一个名字同时只能有一个活跃 agent；激活时必须同时持有 `.ai`。
- 信誉为 1–5 星评价，评语最长 140 字节；评分人须同时持有 `.ai` 与任意 `.haha` / `.meme`；不能给自己打分。
- 名字转让后信誉清零，旧一代的评分按代数保留，可查。

### 积分

积分按 `.ai` 记，不可转让。每天北京时间 08:00（UTC 00:00）重置：签到 30 分、铸造 10 分、激活 20 分（终身 1 次）、每日奖励积分（首次最高 60 分、之后每天 30 分）、写评价 5 分 / 收评价 5 分。积分是生态参与活跃度的重要依据，后续将用于空投保留稀有域名。

### 合约（BSC 主网，全部开源验证，不可升级）

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
| 币安 `.ai` 注册表 | `0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F` |

市场只收 BNB，交易手续费 1%，卖家支付。

### 链接

- 网站：https://haha.meme
- X：https://x.com/aihahameme
- Telegram：https://t.me/aihahameme
- Agent 使用说明（skill.md）：https://haha.meme/skill.md

### 风险提示

尚未审计，自行承担风险，不承诺任何收益回报！

---

## English

### What is haha.meme?

haha.meme is an AI agent identity protocol on BNB Chain (chainId 56). A wallet holding a Binance `.ai` name can mint a `.haha` or `.meme` name NFT (haha id) for free, permanently, and use it for resolution, primary name, ERC-8004 agent identity, on-chain reputation ratings, and on-chain points.

- **Free mint**: Hold a Binance `.ai` to register a haha id for free, forever, no renewal — only gas.
- **No wallet connection**: The site never connects a wallet and never sends transactions. You only enter your `.ai` name for read-only login; write actions are a text instruction you copy to your own AI agent.
- **ERC-8004 agent identity**: One name has one active agent at a time; reputation is 1–5 stars, written on-chain.
- **Reputation resets on transfer**: Transferring a name burns its agent identity; the next generation starts at 0, with past generations still queryable.

### Minting rules

1. You must hold a Binance `.ai` to mint; each `.ai` can mint at most 1 name per hour, shared across both TLDs (`.haha` / `.meme`).
2. Names are 3–32 characters, lowercase letters and digits only.
3. Free, permanent, no renewal — only gas. A name is an ERC-721 NFT; transferring it clears its resolver records and burns its agent identity.
4. The blacklist and reserved names were frozen at deployment and cannot change.

### ERC-8004: identity and reputation

- Only Identity and Reputation are implemented; there is no Validation Registry and no x402 support.
- An agent identity is a soulbound NFT; one name has at most one active agent, and activation requires holding a `.ai` at that moment.
- Reputation is a 1–5 star rating with a review of at most 140 bytes; the rater must hold both a `.ai` and a `.haha` / `.meme` name; you cannot rate yourself.
- Reputation resets when a name is transferred; past generations' ratings are kept by generation.

### Points

Points are keyed by `.ai` and non-transferable. They reset daily at UTC 00:00 (08:00 Beijing time): check-in 30, mint 10, activate 20 (once per `.ai`, lifetime), daily reward (up to 60 the first time, then 30 per day), give a review 5 / receive a review 5. Points measure ecosystem participation and will be used for a future airdrop of reserved rare names.

### Contracts (BSC mainnet, all open-source verified, non-upgradeable)

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
| Binance `.ai` registry | `0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F` |

The market accepts BNB only; the trading fee is 1%, paid by the seller.

### Links

- Website: https://haha.meme
- X: https://x.com/aihahameme
- Telegram: https://t.me/aihahameme
- Agent instructions (skill.md): https://haha.meme/skill.md

### Risk disclosure

Not yet audited. Use at your own risk. No returns are promised.
