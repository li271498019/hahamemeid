# 指令与 skill.md 教程

给网站开发 C。网站是给 AI agent 调用的。人在页面上不连接钱包，也不签名。每个写操作都是一段自然语言。用户复制到自己的 agent（Binance Agentic Wallet）。agent 阅读 `https://haha.meme/skill.md`，核对合约地址，先把交易预览给用户，用户确认后才发送。

本文说明两件东西如何一起写：

- 页面上每个复制按钮生成的指令。
- `https://haha.meme/skill.md` 里对应的那一节。

不要在指令或 skill.md 里放服务器 IP、私钥、助记词、SSH 口令或 API 密钥。

## 现有指令骨架

`web/site/js/instructions.js` 的 `hahaInstruction(task)` 已经规定了外壳。保持这段外壳，只替换 `task`：

```text
用我的 Binance Agentic Wallet 执行以下任务。若当前环境没有 Agentic Wallet skill，先安装：
npx skills add binance/binance-skills-hub --skill binance-agentic-wallet
若需要登录，我登录完成后会回复「继续」，届时从这里接着执行。
阅读 https://haha.meme/skill.md，按其中规则在 BNB Chain 上{task}。
先确认 Developer Mode 已开启，把交易预览给我看，我确认后再执行。
```

正式站上，链接永远是 `https://haha.meme/skill.md`，不要写成相对路径，不要换成 IP。

测试站在 `haha.meme` 的 skill 还没更新之前，测试指令可以临时把这一行换成 `https://ddao.app/skill.md`，方便 agent 读到正在测的版本。验收正式站之前必须改回 `https://haha.meme/skill.md`。两份 skill 的合约地址必须相同，都是主网地址。

`task` 用用户已经填好的具体值，不要留「某名字」「某价格」让 agent 再问一遍页面上已经有的字段。仍然要让 agent 自己上链核对，不能只信这句话。

现有调用点，改完后仍走这个函数：

| 位置 | 现在的 task |
| --- | --- |
| `index.html` 复制铸造 | `铸造 ` + 全名 |
| `market.html` 购买 | `购买挂单中的 ` + 名字 + `，价格 ` + 价格 + ` BNB` |
| `market.html` 挂单 / 改价 / 撤单 | 名字写死了示例价 `0.5 BNB`。正式站改成用户输入的价格 |
| `erc8004.html` | 激活、设主名、设解析、设文本 |
| `agent.html` | `给 ` + 名字 + ` 打 ` + 星 + ` 星并写评语：` + 评语 |
| `tasks.html` 的每日按钮 | 合并进赚取页后保留一条「每日」指令，见下文 |

## skill.md 怎么提供

- 文件放在网站根目录，URL 是 `/skill.md`。nginx 的 `try_files` 能直接命中这个文件。
- `Content-Type` 为 `text/markdown; charset=utf-8`。在 nginx 里单独给这个文件加：

```nginx
location = /skill.md {
    types { }
    default_type text/markdown;
    charset utf-8;
    charset_types text/markdown;
    add_header Cache-Control "no-store, no-cache, must-revalidate";
    add_header X-Content-Type-Options nosniff;
}
```

现有静态规则把 `js`、`css` 缓存 7 天。`skill.md` 不能走那条规则，否则 agent 会读到旧地址或旧函数。

- 文件开头用 YAML frontmatter，便于 skill 发现：

```yaml
---
name: haha.meme
description: 在 BNB Chain 上铸造和管理 .haha / .meme 名字、市场、ERC-8004 信誉和积分。人不要连钱包，只按本文给的合约地址发交易。
version: 1
chainId: 56
---
```

每次改地址、函数或规则，把 `version` 加 1，并在文件末尾写一行变更。页面指令不用带版本号，agent 以当时拉到的 skill.md 为准。因为禁止缓存，发布后下一次读取就是新版本。

## skill.md 必须包含的固定段落

按这个顺序写。地址与 `docs/website/V1-LAUNCH-REQUIREMENTS.md` 的表一致，这里再列一次，避免 C 写 skill 时还要来回翻。

### 链

- 名称：BNB Smart Chain
- chainId：`56`
- 原生币：BNB，18 位小数
- RPC：写公开端点 `https://bsc-dataseed.binance.org`。并写明 agent 可以使用用户自己的 RPC，但 chainId 必须是 56。不要把自建索引 API 的内网地址写进 skill。

### 安全规则（放在任何动作之前）

- 只向本文列出的合约地址发送交易。地址不符就停止，告诉用户「合约地址和 haha.meme/skill.md 不一致」。
- 不要签名 skill 没有写明的 `eth_sign`、`personal_sign`、任意 `permit`，也不要批准 skill 没点名的 spender。
- `approve` 只批准 `HahaMarketplace`（`0xC7294DF776344A39726b4C1256Faf0e728c99835`），且只针对用户点名的 `tokenId`。不要 `setApprovalForAll`，除非用户在预览里明确同意无限授权。默认用单 token 的 `approve`。
- 价值只在 `buy` 里出现，且 `msg.value` 必须等于当时链上的挂单价格。其它动作的 value 都是 0。
- 交易发送前用 `eth_call` 做本文列出的检查。检查失败就不要发交易，用本文的 revert 说明告诉用户。
- gas 用节点估算值，不要手写一个很大的 gas limit 去硬送。估算失败说明这笔交易会 revert，把错误还给用户。

### 地址

| 名称 | 地址 |
| --- | --- |
| 币安 .ai 注册表 | `0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F` |
| HahaNamePolicy | `0x1F260aa05334f76A6E1d6Fbd416F4d07d6Bf3d96` |
| HahaMetadata | `0x790B670D664Ea0046b0F2D395C182AdD3C389aB4` |
| HahaResolver | `0x85C2DbdFd81A14B958B360159e8710E6c15370D6` |
| HahaRegistry | `0x712Ca65E2F6F5436C846569949072C8941982987` |
| HahaRegistrar | `0x43426E37a31AafDaba851858e34B81DC300650F8` |
| HahaAgentIdentity | `0x54A70BF81B288d41013D7b57c2Db0922f1E1a4d4` |
| HahaPoints | `0xB2D023b8B5895835EFD71C1150BeAD7bD735DfAa` |
| HahaReputation | `0xf1A41B30d0c03fE178D3d76CBE6044E9D5Ce1800` |
| HahaMarketplace | `0xC7294DF776344A39726b4C1256Faf0e728c99835` |

`HahaDeployer` 不接收用户交易，不要写进「可调用」列表。

`.ai` 的 id：`aiId = keccak256(bytes(handleOf(sender)))`。`handleOf` 返回什么字符串就哈希什么，不要自行追加 `.ai`。

名字的 tokenId：`uint256(namehash(tldNode, keccak256(bytes(label))))`。实现时直接调 `HahaRegistrar.nodeOf(label, tld)`，不要在文档里让 agent 手算 node。`tld` 为 `0` 表示 `.haha`，`1` 表示 `.meme`。

## 每个动作怎么写

skill 里每个动作用同一张小表：

- 用户意图
- 合约与函数签名
- selector（函数选择器，供 agent 核对 calldata）
- 参数
- 发送前检查
- value
- 成功事件
- 失败时怎么对用户说

下面每一节都先给一条可复制的页面指令，再给 skill 里要写的内容。指令外壳省略，只写 `{task}`。C 把 task 填进 `hahaInstruction`。

编码示例用 ABI 标准编码。字符串是动态类型。示例里的 selector 由 `keccak256("函数签名")` 的前 4 字节得出，C 实现时用库生成 calldata，不要手拼，但可以用示例做对照测试。

### 铸造

页面 task：

```text
铸造 abc.haha
```

用户在搜索框选了名字和后缀后再复制。`.meme` 则写成 `铸造 abc.meme`。

skill：

- 合约 `HahaRegistrar.register(string label, uint8 tld)`，selector `0x767b79ed`
- `abc.haha` → `label = "abc"`，`tld = 0`。`abc.meme` → `tld = 1`
- value：`0`
- 网页会先把输入转成小写，并且只接受 `a-z` 和 `0-9`。1–2 位，以及 `isReserved` 为 true 的名字，页面状态是「保留」，不给出铸造按钮。agent 仍要自己做下面的检查。
- 发送前：
  1. `label` 仅含 `a-z`、`0-9`，长度 3–32。否则告诉用户「这个名字不能公开铸造：只能用 3 到 32 位小写字母和数字」。不要尝试大写。1–2 位对用户说「这是保留名」，不要说可铸造。
  2. `.ai` 注册表 `handleOf(发送者)` 非空，且 `ownerOf(uint256(keccak256(bytes(handle))))` 等于发送者。失败则说「当前钱包没有持有这个 .ai」。
  3. `HahaNamePolicy.isBlacklisted(label)` 为 false。为 true 则说「这个名字不可用」。不要解释黑名单词表，词表不明文。
  4. `isReserved(label)` 为 false。为 true 则说「这是保留名，不能公开铸造」。
  5. `HahaRegistrar.available(label, tld)` 为 true，并且 `ownerOf(nodeOf(label, tld))` 会 revert 或无人持有。已存在则说「这个名字已经铸出」。注意 `available` 对 1–2 字符和保留名也可能返回 true，所以 1、3、4 不能省。
  6. `nextMintAt(aiId)` 为 0 或小于等于当前区块时间。否则说「这个 .ai 还在冷却，请在 {时间} 之后再铸」，时间用 `CooldownActive` 里的 unix 秒转成 UTC。
- 示例 calldata（`register("abc", 0)`）：

```text
0x767b79ed
  0000000000000000000000000000000000000000000000000000000000000040
  0000000000000000000000000000000000000000000000000000000000000000
  0000000000000000000000000000000000000000000000000000000000000003
  6162630000000000000000000000000000000000000000000000000000000000
```

- 成功事件：`NameMinted(tokenId, owner, tld, aiId, label, reservedMint)`。`reservedMint` 应为 false。同一笔交易里 `HahaPoints` 会发出铸造加分的 `PointsChanged`，每天最多 3 次、每次 10 分。加分失败不应阻止铸造；若没有加分事件，告诉用户「名字已铸出，今日铸造积分可能已满」。
- revert 与对用户的话：

| revert | 对用户说 |
| --- | --- |
| `InvalidCharset` | 只能用小写字母和数字 |
| `LabelTooShort` | 公开铸造至少 3 个字符 |
| `LabelTooLong` | 最长 32 个字符 |
| `InvalidTld` | 后缀只能是 .haha 或 .meme |
| `Blacklisted` | 这个名字不可用 |
| `ReservedName` | 这是保留名，不能公开铸造 |
| `NameTaken` | 这个名字刚刚被别人铸走 |
| `AiRequired` | 这个钱包没有可用的 .ai |
| `CooldownActive` | 这个 .ai 一小时只能铸一个，请等到返回的时间 |

### 授权市场（挂单之前）

页面不单独做一个「授权」按钮。挂单指令里要求 agent 在 `list` 之前检查授权，不够再发一笔 `approve`。两笔都要先预览。

- 合约是名字 NFT，也就是 `HahaRegistrar.approve(address to, uint256 tokenId)`，selector `0x095ea7b3`
- `to` 固定为市场 `0xC7294DF776344A39726b4C1256Faf0e728c99835`
- 检查 `getApproved(tokenId)` 已经是市场地址则跳过
- value：`0`
- 不要批准其它地址

### 挂单

页面 task（价格来自用户输入，不要再写死 0.5）：

```text
以 0.2 BNB 挂单 abc.haha
```

skill：

- `HahaMarketplace.list(uint256 tokenId, uint256 price)`，selector `0x50fd7367`
- `tokenId = nodeOf("abc", 0)`，`price` 用 wei。`0.2 BNB` = `200000000000000000`
- value：`0`
- 发送前：`ownerOf(tokenId)` 是发送者；`listings(tokenId)` 的 seller 是零地址；`feeFor(price)` 大于 0（价格至少能扣出 1% 的 1 wei 以上，实际按 BNB 输入不会碰到）；市场已被 `approve`
- 成功事件：`Listed(tokenId, seller, price)`
- revert：`NotOwner` 说「这个名字不在当前钱包」；`AlreadyListed` 说「已经在挂单，请改价或先撤单」；`NotApproved` 说「需要先批准市场合约，我已把批准放进预览」；`PriceTooLow` 说「价格太低，1% 手续费舍入后是 0」

### 改价

页面 task：

```text
把 abc.haha 的挂单改成 0.15 BNB
```

skill：

- `updatePrice(uint256 tokenId, uint256 newPrice)`，selector `0x82367b2d`
- 发送前：`listings` 的 seller 是发送者，且 `ownerOf` 仍是发送者
- value：`0`
- 事件：`PriceUpdated(tokenId, seller, oldPrice, newPrice)`
- `NotListed` / `NotSeller`：告诉用户当前没有他的挂单

### 撤单

页面 task：

```text
撤销 abc.haha 的挂单
```

skill：

- `cancel(uint256 tokenId)`，selector `0x40e58ee5`
- value：`0`
- 事件：`Cancelled(tokenId, seller)`
- 只有卖家能撤。撤单不转名字。

### 购买

页面 task：

```text
购买挂单中的 abc.haha，价格 0.2 BNB
```

skill：

- `buy(uint256 tokenId)`，selector `0xd96a094a`，payable
- 发送前重新读 `listings(tokenId)`。链上价格必须等于指令里的价格。不等则停止，说「链上价格已变为 {实际价格} BNB，和指令里的不一致，我没有发送交易」。
- `msg.value` 必须精确等于该价格。多了或少了都会 `WrongValue`。
- 卖家仍是 `ownerOf`，且市场仍被批准。否则说「这单已经失效」。
- 成功事件：`Sold(tokenId, seller, buyer, price, fee, proceeds)`。`fee` 约为价格的 1%，`proceeds` 是卖家待提取金额。
- 告诉用户：买到的是名字。这一代 agent 身份会销毁，信誉不跟着走。卖家的货款在市场合约里，要卖家自己 `withdraw`。买家不需要因为这笔购买再调用 `withdraw`。

示例：`buy(1)` 的 calldata 是

```text
0xd96a094a0000000000000000000000000000000000000000000000000000000000000001
```

真实购买要把 `1` 换成 `nodeOf` 的结果，并带上相等的 value。

### 提取货款

卖家和手续费地址都能调用。页面在「我的域名 / 待提取」里提供按钮。

页面 task：

```text
从 haha 市场提取我的待领 BNB
```

skill：

- `HahaMarketplace.withdraw()`，selector `0x3ccfd60b`
- 发送前读 `pendingWithdrawal(发送者)`。为 0 则不要发交易，说「没有待提取的 BNB」。
- value：`0`
- 事件：`Withdrawn(account, amount)`

### 激活 agent

页面 task：

```text
激活 abc.haha 的 agent 身份，agentURI 为 https://example.com/agent.json
```

URI 来自用户输入。空 URI 不要生成指令。

skill：

- `HahaAgentIdentity.activateAgent(string label, uint8 tld, string agentURI)`，selector `0xbff969de`
- 发送前：发送者是该名字的 `ownerOf`；发送者持有 `.ai`；URI 字节长度 1–2048；`agentOfName(tokenId)` 为 0 或当前不活跃（已转让烧毁后可以再次激活，会得到新的 agentId）
- value：`0`
- 事件：`AgentActivated(agentId, nameTokenId, owner, operatorAiId, generation, agentURI)`
- 同一笔里可能有 20 分的 `PointsChanged`。每个 `.ai` 终身一次。没有该事件时说「已激活。这个 .ai 的激活积分之前领过，或者这次没有加上」。
- `AiRequired`：钱包没有 `.ai`。名字不属于发送者时不要把交易发出去。

### 修改 agent URI

页面 task：

```text
把 abc.haha 的 agent URI 改成 https://example.com/agent.json
```

skill：

- `setAgentURI(uint256 agentId, string newURI)`，selector `0x0af28bd3`
- `agentId` 用 `agentOfName(nodeOf(...))`，且 `isActive` 为 true
- 只有该 agent 的主人能改
- 事件：`URIUpdated(agentId, newURI, updatedBy)`

### 评分

页面 task：

```text
给 abc.haha 打 5 星并写评语：nice agent
```

星级和评语来自 `agent.html` 的输入。评语按 UTF-8 字节计，超过 140 就不要复制，页面先拦住。

skill：

- `HahaReputation.rate(uint256 agentId, uint8 stars, string review)`，selector `0x02ece06f`
- 发送前：
  1. `stars` 是 1 到 5 的整数。
  2. `bytes(review).length <= 140`。超长说「评语最长 140 字节」。
  3. `isActive(agentId)` 为 true。否则说「这个名字当前没有激活的 agent」。
  4. 发送者持有 `.ai`，并且 `HahaRegistrar.balanceOf(发送者) > 0`。缺名字说「评分前需要自己持有一个 .haha 或 .meme」。
  5. agent 主人持有 `.ai`。否则 `OwnerAiRequired`，说「对方的 .ai 已不在，现在不能评分」。
  6. 发送者不是主人，发送者的 aiId 不等于主人的 aiId，也不等于 `operatorAiIdOf(agentId)`，并且 `isAgentOperator` 为 false。任一命中就说「不能给自己的 agent 评分」。
- value：`0`
- 事件：`Rated(agentId, aiId, rater, stars, review, edited)`。`edited = true` 表示修改旧分，不算新的一条。
- 积分：写评价最多每天 5 个不同 agent、每个 5 分；对方收评价最多每天 5 个不同评分人、每个 5 分。积分满了评分仍然成功。告诉用户看 `PointsChanged` 有没有增加。
- 示例 `rate(7, 5, "nice")` 的 selector 是 `0x02ece06f`，后面依次是 agentId、stars（uint8 仍占 32 字节）、字符串偏移和内容。用 ABI 库编码，不要手改星级那 32 字节的位置。

### 签到

页面 task：

```text
用我的 .ai 在 haha 签到
```

skill：

- `HahaPoints.checkIn()`，selector `0x183ff085`
- 发送前：`statusOf(发送者)` 里 `holdsAi` 和 `holdsName` 都为 true，`checkInToday` 为 false。缺名字说「要先持有一个 .haha 或 .meme」。今天已签说「今天已经签过，下次重置时间是 {nextResetAt} UTC」。
- value：`0`
- 事件：`PointsChanged`，`delta` 为 30，`reason` 为 `CHECKIN`
- `AlreadyCheckedInToday`：今天已签。`CheckInDisabled`：管理员把分值设成了 0，告诉用户并停止。

### 关注、点赞、转发、评论

这四个都是链上记账，合约不检查社交媒体。skill 里写清楚：agent 只提交合约调用，不代替用户保证站外动作已经发生。页面可以用文案鼓励用户先去做，但不要让 agent 去登录第三方网站。

| 动作 | 页面 task | 函数 | selector | 分 |
| --- | --- | --- | --- | --- |
| 关注 | `领取 haha 关注积分` | `claimFollow()` | `0x768f334b` | 30，终身一次 |
| 点赞 | `领取 haha 今日点赞积分` | `claimLike()` | `0x061bb92c` | 10，每日一次 |
| 转发 | `领取 haha 今日转发积分` | `claimRetweet()` | `0x48ac5c21` | 10，每日一次 |
| 评论 | `领取 haha 今日评论积分` | `claimComment()` | `0x87db41d1` | 10，每日一次 |

共同检查：`holdsAi`、`holdsName`。关注再看 `followClaimed`。其余看对应的 today 标志。value 都是 0。事件都是 `PointsChanged`。

`FollowAlreadyClaimed`：说「这个 .ai 已经领过关注分」。当日重复：说「今天已经领过，UTC 0 点后重置」。

### 每日一条

赚取页保留一个按钮，task：

```text
今天在 haha 签到，并领取今天还没领的点赞、转发、评论积分。不要重复发送已经完成的项。关注只在从未领过时领取。不要铸造，不要评分。
```

skill 要求 agent 先 `statusOf`，只为未完成的项各发一笔，每笔单独预览。不要用一笔交易打包，这些函数不在一个合约入口里组合。

铸造分、写评价分、收评价分、激活分都没有单独的领取函数。每日指令不要调用不存在的 `claimMint` 或 `claimReview`。

### 设为主名、解析地址、文本

页面 task 示例：

```text
把 abc.haha 设为主域名
```

```text
把 abc.haha 的解析地址设为 0x1111111111111111111111111111111111111111
```

```text
把 abc.haha 的文本记录 description 设为 hello
```

地址和 key、value 都来自用户输入。地址必须是 20 字节校验过的十六进制，否则不生成指令。

skill：

- `HahaResolver.setPrimaryName(string label, uint8 tld)`，selector `0xd91f033a`。发送者必须是该名字主人。
- `setAddr(bytes32 node, address a)`，selector `0xd5fa2b00`。`node = nodeOf(label, tld)`。
- `setText(bytes32 node, string key, string value)`，selector `0x10f13a8c`。key 最长 64 字节，value 最长 1024 字节，每个名字最多 16 个 key。
- value 都是 0。
- 读：`primaryName(address)`、`addr(bytes32)`、`text(bytes32,string)`。
- 转让会 `clearRecords`。skill 告诉用户：名字转走后这些记录会被清空。

## 页面怎么把输入填进指令

| 用户输入 | 控件（现状） | 填进 task 的形式 |
| --- | --- | --- |
| 名字 + 后缀 | `index.html` 的 `#q`，以及 `.haha` / `.meme` 切换 | `铸造 {label}.{tld}`，label 用小写 |
| 购买价格 | 市场卡片上的链上价格，不是输入框 | `购买挂单中的 {label}.{tld}，价格 {bnb} BNB`。bnb 用十进制，不要用科学计数法 |
| 挂单 / 改价 | 现在写死 0.5。改为卡片上的价格输入 | `以 {bnb} BNB 挂单 {全名}` / `把 {全名} 的挂单改成 {bnb} BNB` |
| 星级、评语 | `agent.html` 的星和 `#comment` | `给 {全名} 打 {n} 星并写评语：{text}`。text 里的换行改成空格，避免把指令外壳拆断 |
| agent URI、解析地址、文本 | ERC-8004 页需要新增输入。现在的按钮没有参数 | 见上面三节。没有输入就不显示复制按钮 |

复制仍用 `HahaUI.copyText`。成功 toast 可以沿用「铸造指令已复制」这类短句。不要在 toast 里重复整段指令。

## 上线前用真实 agent 测

在 `ddao.app` 上做，做完再切 `haha.meme`。用一个真实的币安 `.ai` 和它的 agent 钱包，不要用演示账号。

1. 打开测试站的 `/skill.md`，确认 `Content-Type` 含 `text/markdown`，响应头有 `Cache-Control: no-store`，`version` 和地址与本文一致。
2. 铸造一个 3 位未被占用的小写名字。BscScan 上能看到 `NameMinted`，接收者是 agent 钱包。
3. 立刻再铸第二个，agent 应拒绝并说明冷却，链上没有第二笔 `register`。
4. 试一个 2 字符和一个大写名字，agent 应在发送前拒绝。
5. 激活、评 5 星、再评一次。第二次 `Rated` 的 `edited` 为 true，`getScore` 的 count 仍是 1。
6. 挂单、用另一个持有 `.ai` 的钱包购买。买家成为 `ownerOf`。卖家 `pendingWithdrawal` 增加标价的 99%。卖家 `withdraw` 后余额增加。
7. 购买后旧 agent `isActive` 为 false。旧评语仍能在 `Rated` 事件里找到。新主人再激活得到新的 agentId。
8. 签到一次，当天第二笔 `checkIn` 被 agent 拒绝。
9. 把测试指令里的 skill URL 改回 `https://haha.meme/skill.md` 后再做一次铸造预览（可以不发送），确认 agent 读到的地址仍然是上表。

任何一步 agent 发到了表外地址，停止上线，先改 skill.md。
