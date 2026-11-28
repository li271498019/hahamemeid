# 部署记录（DEPLOYED）

> 本文档是 haha.meme 合约在主网的正式部署回执，供产品（B）写网站对接文档使用。
> 部署 commit 固定为 `70fe8e79`，全部合约已开源验证。

## 1. 部署概览

| 项 | 值 |
| --- | --- |
| 网络 | BSC 主网（BNB Smart Chain），chainId **56** |
| 部署 commit | `70fe8e79` |
| 编译器 | solc `0.8.28+commit.7893614a`，optimizer runs **200**，**via-ir**，EVM `cancun` |
| 部署 EOA（= 管理员） | `0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7` |
| 部署区块范围 | 134834631 – 134834846（合约部署）、134837848 – 134837960（配置） |
| 部署日期 | 2026-11-21 |

## 2. 固定地址（不可改）

| 名称 | 地址 | 用途 |
| --- | --- | --- |
| 管理员 | `0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7` | 发分模块注册、积分参数、游戏登记 |
| 手续费接收 | `0x57A76124bC919F7509bEb54924E8448258De90df` | 市场手续费、NFT 版税（1%） |
| `.ai` 注册表 | `0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F` | 币安 `.ai` 身份（SPEC 4） |

## 3. 合约地址

| 合约 | 地址 | 部署交易 | 区块 | 开源 |
| --- | --- | --- | --- | --- |
| HahaNamePolicy | `0x1F260aa05334f76A6E1d6Fbd416F4d07d6Bf3d96` | `0xa9edaff5…d4da21` | 134834631 | ✅ |
| HahaMetadata | `0x790B670D664Ea0046b0F2D395C182AdD3C389aB4` | `0x0a8dff08…1bdca` | 134834660 | ✅ |
| HahaResolver | `0x85C2DbdFd81A14B958B360159e8710E6c15370D6` | `0x060de717…4e2f` | 134834683 | ✅ |
| HahaRegistry | `0x712Ca65E2F6F5436C846569949072C8941982987` | `0xc5660d42…6616` | 134834708 | ✅ |
| HahaRegistrar | `0x43426E37a31AafDaba851858e34B81DC300650F8` | `0xa0c2d124…7736` | 134834735 | ✅ |
| HahaAgentIdentity | `0x54A70BF81B288d41013D7b57c2Db0922f1E1a4d4` | `0xb80ce934…d719` | 134834759 | ✅ |
| HahaPoints | `0xB2D023b8B5895835EFD71C1150BeAD7bD735DfAa` | `0xb1c2a944…86b5` | 134834780 | ✅ |
| HahaReputation | `0xf1A41B30d0c03fE178D3d76CBE6044E9D5Ce1800` | `0x4e775620…6019` | 134834803 | ✅ |
| HahaMarketplace | `0xC7294DF776344A39726b4C1256Faf0e728c99835` | `0xfe5da88d…8ed6` | 134834824 | ✅ |
| HahaDeployer | `0x3c7Bd1649ac03AfB65e6E10F949f45d764B6b601` | `0x6ae05127…c257` | 134834846 | ✅ |

> 每个地址的 BscScan 源码页：`https://bscscan.com/address/<地址>#code`

## 4. 部署后配置（管理员交易）

### 4.1 发分模块（setEarner × 3）

| actionId | 分值 | 每日上限 | 全网每日总额 | KeyMode | requireName | module |
| --- | --- | --- | --- | --- | --- | --- |
| `REVIEW_GIVE`（写评价） | 5 | 5 个不同 agent | 50,000 | PerDay | true | HahaReputation |
| `REVIEW_RECEIVE`（收评价） | 5 | 5 个不同评价人 | 50,000 | PerDay | false | HahaReputation |
| `ACTIVATE`（激活 agent） | 20 | 终身一次 | 100,000 | Lifetime | true | HahaAgentIdentity |

配置交易哈希：
- `REVIEW_GIVE`：`0xb8baa92c…cd4e81`（区块 134837848）
- `REVIEW_RECEIVE`：`0xc54d3ef9…903032`（区块 134837901）
- `ACTIVATE`：`0x998d63c5…d09611`（区块 134837960）

### 4.2 内置积分参数（HahaPoints 默认值，未改动）

| 任务 | 分值 | 说明 |
| --- | --- | --- |
| 每日签到 | 30 | 每天 1 次 |
| 铸造名字 | 10 | 每天最多 3 次（MINT_REWARDS_PER_DAY=3） |
| 关注 | 30 | |
| 转发 | 10 | |
| 点赞 | 10 | |
| 评论 | 10 | |
| 写评价 | 5 | 每天最多 5 个不同 agent |
| 收评价 | 5 | 每天最多 5 个不同评价人 |
| 激活 agent | 20 | 每个 `.ai` 终身一次 |

> 所有积分按 `.ai` 身份记，钱包地址只用来查是哪个 `.ai`。每日任务统一按 UTC 0 点重置（`block.timestamp / 86400`）。

## 5. 最终自检结果

- ✅ HahaDeployer 九个地址引用正确
- ✅ `registrar.admin()` == 管理员
- ✅ `registrar.feeReceiver()` == 手续费接收
- ✅ `bootstrap` 不可再调用
- ✅ `hahaNode` / `memeNode` owner == Registrar
- ✅ 部署者即管理员，admin 天然拥有管理权限（非漏洞）

## 6. 产品对接要点（B）

### 6.1 核心流程

1. **注册名字** → `HahaRegistrar.register(label, tld)`（`tld`：`0`=`.haha`，`1`=`.meme`）
   - 要求调用者持有 `.ai`，且 1 小时铸造冷却（防工作室抢注）。
2. **激活 Agent** → `HahaAgentIdentity.activateAgent(label, tld, agentURI)`
   - 要求持有 `.ai`，激活即发放 20 分（终身一次）。
3. **积分查询** → `HahaPoints.balanceOf(aiId)` / `statusOf(user)`
   - `statusOf` 一次返回余额、今日各任务次数、下次重置时间。
4. **评价** → `HahaReputation.rate(agentId, stars, review)`（1–5 星，可改）
5. **市场** → `HahaMarketplace`（买卖名字，手续费 1%，`feeBps()==100`）

### 6.2 关键只读接口

| 合约 | 函数 | 用途 |
| --- | --- | --- |
| HahaRegistry | `owner(node)` / `resolver(node)` | 域名归属与解析器 |
| HahaResolver | `addr(node)` | 名字绑定的钱包地址 |
| HahaAgentIdentity | `agentOfName(nameTokenId)` / `getAgent(agentId)` | 名字 ↔ agent 映射 |
| HahaPoints | `balanceOf` / `statusOf` / `actionStatus` | 积分与任务状态 |
| HahaReputation | `getScore(agentId)` | agent 评分（count + sum） |

### 6.3 注意事项

- **`.ai` 是 soulbound**：一个地址一个 handle，不可转让。
- **名字转让会销毁 agent**（声誉清零、agentId 不复用、代数 +1）。
- **积分不可提现**，仅站内消费；管理员可授权 spender 扣分（拍卖）。
- 小游戏积分模块由后续小游戏合约单独登记（`registerGame`），本轮未部署。

## 7. 回执文件

完整机器可读回执：`deployment-56.json`（含全部交易哈希、区块、验证状态）。

## 8. Haha Dog（BSC 主网）

Haha AI 的链上模型与 Haha Dog NFT 于主网另一次部署，不属于上面的 haha id 合约组。四个合约不可升级、无管理员。规格见 `haha-dog/SPEC.md`。

| 合约 | 地址 |
| --- | --- |
| HahaDogModel | `0x3277990797Ed8B15B3674ee0C557011F5a1eCCC9` |
| HahaDogRenderer | `0xCA760D9D3E76DcDC7AC6bcc55D53346b8a2c107E` |
| HahaDog | `0x26f88A5db4925e9aFa35B1096FdD6DBa09f056c6` |
| HahaDogMarket | `0xD7F5502Bd7a52E17959bF4b7F1180f6e3611fd49` |

权重文件 `haha-ai/weights-int8.json`（与 `haha-dog/model/weights-int8.json` 字节相同）的 keccak256：

`0x1d2239644b5273c4f1925c489d32900a564262bce6597f94a929489cfbe58078`

链上 `HahaDogModel.MODEL_DATA_HASH()`：

`0x72f92c628a64bc0d5652d285c6789fa0f84cb462d328604cf3dcff224704f8da`
