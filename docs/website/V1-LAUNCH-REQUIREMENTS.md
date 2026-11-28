# V1 正式上线需求

给网站开发 C。只改网站需要改的地方。本文不改合约、不改测试。文案以老板 2026-11-21 确认后的原文为准，写在各节和文末「已确认」。不要再改这些字。

地址、函数、事件以 PR #7 合并后的 `docs/contracts/DEPLOYED.md` 和 `src/` 为准。链是 BNB Smart Chain 主网，chainId `56`。编译器 `solc 0.8.28`，optimizer 200，via-ir。部署字节码提交 `70fe8e79`。`docs/contracts/DEPLOYED.md` 里的部署交易哈希是截断的，本文不补全，BscScan 用地址页。

## 全局规则

整站视觉框架保持现状。当前站点就是主题和骨架，只改下面点名的项。不要重做页面、不要换布局体系、不要换配色、不要换金币素材、不要重画 logo。

可以改：文案、导航项、登录后的状态句、字体文件、金币雨数量和悬停、数据从演示换成链上、预览条和 noindex、市场网格列数、把任务页和游戏页收成一页、补全工作原理、发布 `skill.md`。

不要改：橙黄渐变背景、导航结构（logo 在左、链接在中、登录在右）、卡片和面板的圆角与阴影、金币雨点击爆开、NFT 预览画法、复制指令的句式骨架（见 `web/site/js/instructions.js` 的 `hahaInstruction`）。

每条需求都按「页面 / 文件 → 现状原文 → 目标 → 实现说明 → 验收」做。现状引号里的字必须和代码一致。

## 分期（2026-11-21，B 确认）

阶段 A 现在就做，不等索引器。范围是：文案、字体、金币雨、任务页和游戏页合并，以及所有单条查询走 BSC RPC。单条查询包括名字能否铸造、是否保留、持有人、冷却、`HahaPoints.statusOf` 和余额、agent 是否激活、代数、星级（`getScore`）。

所有列表都先空着：市场网格、成交、agent 广场、信誉榜、历代评语、积分榜。空状态可以写「还没有数据」。禁止再用演示数据。删除 `web/site/js/mock.js`，任何页面都不要加载它。

列表的前端仍按 `docs/website/V1-INDEXER-SPEC.md` 的路径和 JSON 字段来写。API 根地址只放在 `web/site/js/config.js` 的 `window.HAHA_INDEXER_BASE`。阶段 A 设成空字符串，列表不发请求，直接空状态。索引器就绪后把这一处改成 `/api`，不要改各页的字段解析。

索引器与阶段 A 并行做。`ddao.app` 可以先发阶段 A。`haha.meme` 正式站只在索引器已经在跑、并且列表在 `ddao.app` 上对过链之后才发布。本文后面要求「列表与链上一致」的验收，到那时再做。阶段 A 只验收单条 RPC 和空列表。

## 主网合约

全部已在 BscScan 验证源码。链接是 `https://bscscan.com/address/<地址>#code`。部署区块是索引起点。

| 合约 | 地址 | 部署区块 |
| --- | --- | --- |
| HahaNamePolicy | [`0x1F260aa05334f76A6E1d6Fbd416F4d07d6Bf3d96`](https://bscscan.com/address/0x1F260aa05334f76A6E1d6Fbd416F4d07d6Bf3d96#code) | 134834631 |
| HahaMetadata | [`0x790B670D664Ea0046b0F2D395C182AdD3C389aB4`](https://bscscan.com/address/0x790B670D664Ea0046b0F2D395C182AdD3C389aB4#code) | 134834660 |
| HahaResolver | [`0x85C2DbdFd81A14B958B360159e8710E6c15370D6`](https://bscscan.com/address/0x85C2DbdFd81A14B958B360159e8710E6c15370D6#code) | 134834683 |
| HahaRegistry | [`0x712Ca65E2F6F5436C846569949072C8941982987`](https://bscscan.com/address/0x712Ca65E2F6F5436C846569949072C8941982987#code) | 134834708 |
| HahaRegistrar | [`0x43426E37a31AafDaba851858e34B81DC300650F8`](https://bscscan.com/address/0x43426E37a31AafDaba851858e34B81DC300650F8#code) | 134834735 |
| HahaAgentIdentity | [`0x54A70BF81B288d41013D7b57c2Db0922f1E1a4d4`](https://bscscan.com/address/0x54A70BF81B288d41013D7b57c2Db0922f1E1a4d4#code) | 134834759 |
| HahaPoints | [`0xB2D023b8B5895835EFD71C1150BeAD7bD735DfAa`](https://bscscan.com/address/0xB2D023b8B5895835EFD71C1150BeAD7bD735DfAa#code) | 134834780 |
| HahaReputation | [`0xf1A41B30d0c03fE178D3d76CBE6044E9D5Ce1800`](https://bscscan.com/address/0xf1A41B30d0c03fE178D3d76CBE6044E9D5Ce1800#code) | 134834803 |
| HahaMarketplace | [`0xC7294DF776344A39726b4C1256Faf0e728c99835`](https://bscscan.com/address/0xC7294DF776344A39726b4C1256Faf0e728c99835#code) | 134834824 |
| HahaDeployer | [`0x3c7Bd1649ac03AfB65e6E10F949f45d764B6b601`](https://bscscan.com/address/0x3c7Bd1649ac03AfB65e6E10F949f45d764B6b601#code) | 134834846 |

固定地址，不是本次新部署：

| 角色 | 地址 |
| --- | --- |
| 币安 .ai 注册表 | [`0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F`](https://bscscan.com/address/0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F#code) |
| 管理员 | [`0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7`](https://bscscan.com/address/0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7) |
| 手续费与版税收款 | [`0x57A76124bC919F7509bEb54924E8448258De90df`](https://bscscan.com/address/0x57A76124bC919F7509bEb54924E8448258De90df) |

积分模块授权交易在区块 134837848（写评价）、134837901（收评价）、134837960（激活）。索引器从区块 **134834631** 扫到最新，并包含这三笔配置。

`tokenId` = `uint256(namehash(tldNode, labelhash))`。`tld`：`0` = `.haha`，`1` = `.meme`。`.ai` 的 id 是 `keccak256(bytes(handleOf 返回的字符串))`，不要自己拼 `.ai` 后缀，先用一个已知地址核对 `handleOf` 的返回值。

## 读链和写链怎么分工

人在网页上不连钱包、不签名。网页只读。写操作一律是复制指令，交给用户自己的 agent。指令和 `skill.md` 的写法见 `docs/website/AGENT-INSTRUCTIONS-AND-SKILL-GUIDE.md`。

推荐：单条查询走 BSC RPC；列表、排行、历史评语走同一台服务器上的索引 API，字段见 `docs/website/V1-INDEXER-SPEC.md`。市场没有「列出全部挂单」的函数，`listings(tokenId)` 只能按已知 tokenId 查。评语正文只在 `Rated` 事件里，不在存储里。索引器还没接上时，这些列表显示空状态，不使用演示数据。分期见上文。

公开 RPC 有频率限制。浏览器里可以对用户正在看的一个名字做几次 `eth_call`。网格、成交列表、积分榜不要在浏览器里扫区块。

| 页面要的数据 | 来源 | 方式 |
| --- | --- | --- |
| 登录的 `.ai` 是否仍由该地址持有 | `.ai` 注册表 `handleOf(address)`、`ownerOfHandle(string)` | RPC，登录后核对 |
| 名字是否已铸造、持有人、后缀 | `HahaRegistrar.ownerOf`、`nameParts`、`nodeOf`、`isMinted` | RPC |
| 能否公开铸造 | 先 `isValidLabel` 规则（见下），再 `HahaNamePolicy.isBlacklisted`、`isReserved`，再 `HahaRegistrar.available` | RPC。`available` 对 1–2 字符、保留名、黑名单也会返回 true，不能单独当「可铸造」 |
| 冷却 | `HahaRegistrar.nextMintAt(aiId)` | RPC |
| 挂单价格 | `HahaMarketplace.listings(tokenId)` | 已知 tokenId 用 RPC；市场网格用索引 |
| 市场列表、最近成交 | 事件 `Listed`、`PriceUpdated`、`Cancelled`、`Sold`、`StaleCleared` | 索引。当前有效挂单 = 最后一次 `Listed`/`PriceUpdated` 且之后没有 `Cancelled`/`Sold`/`StaleCleared` |
| 手续费 | `feeBps()`、`feeFor(uint256)`，都是 100 / 10000 = 1% | RPC 一次即可，写死展示前先读一次核对 |
| 外部版税 | `HahaRegistrar.royaltyInfo` 仍返回 1%，本站 `buy` 不扣这笔 | 页面、工作原理和统计都不要写。老板 2026-11-21 已确认只展示「手续费1%」 |
| 激活状态、代数、URI | `HahaAgentIdentity.agentOfName`、`isActive`、`getAgent`、`generationOf`、`tokenURI` | RPC |
| 当前星级 | `HahaReputation.getScore(agentId)` 返回 `(count, sum)`，均分 = sum / count | RPC |
| 某条评语、历代评语 | 事件 `Rated(agentId, aiId, rater, stars, review, edited)`；转让时 `AgentReset` | 索引。按 `nameTokenId` 的历史 `agentId` 分组，不要只画当前 `getScore` |
| 积分余额和今日次数 | `HahaPoints.balanceOf(bytes32 aiId)`、`statusOf(address)` | RPC |
| 积分榜 | 事件 `PointsChanged` | 索引。合约没有「列出所有 `.ai`」 |
| NFT 图 | `HahaMetadata` / `tokenURI`，链上 SVG | 可直接用现有 `web/site/js/nft.js` 的画法，数据改成真实 label |

写入不由网页发送。agent 要调的函数见下一份文档。网页按钮只复制自然语言指令。

## 1. 去掉预览，接上真实数据

**页面 / 文件**

- `web/site/js/config.js`
- `web/site/js/preview.js`
- `web/site/js/mock.js`
- 各页 `<footer>`，以及仍引用 `HAHA_MOCK` 的页面脚本

**现状**

`config.js`：

```js
window.HAHA_PREVIEW = true;
```

`preview.js` 在该值为 `true` 时插入顶栏，原文是：

> 预览版 · 合约尚未上线，页面数据为演示，请勿执行复制的指令

并在复制按钮后面插入：

> 主网上线后这条指令才会生效

同时给没有 robots 标签的页面加上 `<meta name="robots" content="noindex, nofollow">`。

`mock.js` 文件头：`演示数据。接入索引服务后只替换本文件。`

各页页脚原文（`index.html`、`market.html`、`erc8004.html`、`agent.html`、`tasks.html`、`games.html`、`how.html` 相同）：

> haha.meme · 不连接钱包，不发送交易 · 链上数字接入前，标了「演示数据」的都是样例

**目标**

- `window.HAHA_PREVIEW = false`。顶栏、复制按钮旁的那句提示、由 `preview.js` 注入的 noindex，全部不再出现。
- 删除上面那句页脚。正式站不要 noindex。测试站 `ddao.app` 必须 noindex，做法见部署指南，不要靠把 `HAHA_PREVIEW` 留在 true。
- 删除 `mock.js`，页面不再引用它。演示名字、假价格、假积分、假评语不得出现。阶段 A 的列表是空状态；索引器接上后，同一套前端改 `HAHA_INDEXER_BASE` 即可读到列表。单条查询从阶段 A 起就走 RPC。
- 合约地址集中放一处（建议 `web/site/js/config.js` 或同级 `addresses.js`），十个项目合约加上 `.ai` 注册表，与上表逐字相同。

**实现说明**

- 读不到 RPC 或索引时，显示明确的失败状态（例如「链上数据暂时读不到」），不要退回演示名字。
- 美元折算删除。市场页那句「演示数据 · 美元按 1 BNB = 620 美元折算，不是实时价」属于本项，也属于第 6 项。
- 工作原理页地址表的 `TBD after mainnet deploy` 换成上表，这是第 9 项的一部分，地址来源相同。

**验收**

- 正式站源码和渲染结果里都找不到「预览版」「演示数据」「主网上线后这条指令才会生效」「noindex」。
- 搜索一个真实已铸造名字，持有人和后缀与 BscScan 上 `ownerOf` 一致。
- 搜索一个未铸造、符合公开规则的名字，不显示 mock 里的假挂单。
- 市场网格里的每一条都能在索引里找到对应 `Listed`，且 `listings(tokenId)` 的价格一致。

## 2. 右上角登录

**页面 / 文件**

七个页面的导航，以及 `web/site/js/ui.js`、`web/site/js/session.js`、`web/site/index.html` 末尾内联脚本。

**现状**

每个页面的登录框：

```html
<input id="ai" autocomplete="off" spellcheck="false" maxlength="32" placeholder=".ai 登录" aria-label=".ai 登录">
```

登录成功时 `ui.js` 的 toast 原文是（半角空格，没有冒号）：

```js
toast("正在观察 " + name + ".ai");
```

退出 toast：`已退出观察模式`。名字短于 3 位：`先输入 3 位以上的 .ai 名字`。

首页 `#status` 初始文字是 `观察模式`。搜索脚本把它写成：

```js
"观察模式 · " + s.ai + ".ai · 持有 .ai · 冷却还剩 41:12"
```

未登录时：`还没登录。输入 .ai 只是看看，不会签名。`

页脚没有「正在观察：XXX.ai」。登录状态只出现在 toast 和首页 `#status`。

**目标**

- `placeholder` 和 `aria-label` 改为：`输入您的.ai域名`
- 登录成功后，用户看见的状态文案改为：`登录成功`
- toast 同样改为：`登录成功`
- 删除首页那句写死的「观察模式 · … · 冷却还剩 41:12」。冷却改由 `nextMintAt` 读链，不要再写 41:12，也不要再写 heyi.ai。`session.js` 里的默认演示用户不要再自动登录。

**实现说明**

- 输入仍只取 label，后缀 `.ai` 由旁边的 `<em>.ai</em>` 展示，和现在一样。
- 「登录成功」表示：格式通过，并且 `ownerOfHandle` 能返回一个地址（或用户只声明名字、页面只做观察）。网页仍然不签名。若链上查无此名，不要显示「登录成功」，toast 说明这个名字链上没有。
- 已确认（2026-11-21）：「登录成功」就写在现在显示登录状态的两处，也就是 `ui.js` 的 toast 和首页 `#status`。不要往页脚加这句话，页脚里本来没有观察句。

**验收**

- 七个页面的 placeholder 都是「输入您的.ai域名」。
- 输入一个链上存在的 `.ai` 并提交后，toast 和首页状态都是「登录成功」，页面上不再出现「正在观察」「观察模式」「41:12」。
- 不弹出钱包，不发起交易。

## 3. 全站像素字体

**页面 / 文件**

`web/site/css/site.css` 的 `body`，以及新的字体文件目录 `web/site/assets/fonts/`。

**现状**

```css
color: #fff;
font-family: Inter, "WenQuanYi Micro Hei", "Droid Sans Fallback", "Noto Sans", sans-serif;
font-weight: 700;
```

正文字色已经是白色。白底面板（`.panel`、`.card`、`.sheet`）上的字是深色 `#7C2D12` / `#9A3412`，否则看不清。

**目标**

全站改成像素字体，字重保持粗，橙底上的字保持白色。

**字体**

使用 Fusion Pixel Font（TakWolf，`fusion-pixel-font`），SIL Open Font License 1.1。它有简体中文，可以自托管。选 12px 比例体的 `zh_hans` woff2。

- 文件放在 `web/site/assets/fonts/`，同目录放该字体包里的 `OFL.txt`。
- 不要用 CDN，不要热链 GitHub。
- `@font-face` 的 `font-family` 用 `"Fusion Pixel"`。
- 回退：`"Fusion Pixel", ui-monospace, "WenQuanYi Micro Hei", monospace`。
- Zpix 只作备选。上线前必须把所选 Zpix 发行包里的许可证一并放进仓库。许可证不允许网站嵌入时，不要用 Zpix。

像素字体通常只有一个字重。CSS 写 `font-weight: 700`，并加 `font-synthesis: none`，避免浏览器把字形涂糊。不要再加描边冒充更粗。

**实现说明**

橙底、导航、按钮上的字用白色。白底卡片上的字继续用现在的深色，否则白字落在白卡片上不可读。不要为了全站白字去改卡片底色。

`image-rendering: pixelated` 只用于金币和 logo，不要加在 `body` 上。

**验收**

- 网络面板里字体从本站 `/assets/fonts/` 加载，不是 Google Fonts 或其它 CDN。
- 首页、市场、ERC-8004、赚取页、工作原理的中文都是该像素字体，没有退回 Inter。
- 白卡片上的字仍然可读。
- 仓库里有 `OFL.txt`。

## 4. 金币雨

**页面 / 文件**

`web/site/js/rain.js` 的 `coinCount`、`drawCoin`。

**现状**

```js
function coinCount() { return isMobile() ? 48 : 120; }
```

移动端断点是 `(max-width: 800px)`。

悬停命中后 `p.caught` 为真。绘制时：

```js
var bounce = p.popping ? 1 + Math.sin(t * Math.PI) * 1.05 : (p.caught ? 1.7 : 1);
ctx.globalAlpha = p.popping || p.caught ? 1 : p.alpha;
```

`p.caught` 时还会画一圈白环（`rgba(255, 248, 210, 0.95)` 填充加白色描边）。金币会停住，同时放大到 1.7 倍且不透明度变成 1。

点击的 `popping` 路径（翻转、上抛、笑脸火花、回收）保持不动。

**目标**

- 数量大约增加三成：桌面 **156**（现 120），移动端 **62**（现 48）。
- 悬停只让这枚金币停住。尺寸仍是 `p.size`，不透明度仍是 `p.alpha`。不要放大，不要白环，不要把 alpha 设成 1。
- 点击动画与现在相同。

**验收**

- 宽屏画布上同时存在的金币数约为 156，窄于 800px 时约为 62。
- 鼠标停在一枚金币上，它停止下落，截图像素尺寸和透明度与悬停前一致。
- 点击仍会翻转、上抛、爆出笑脸火花，然后回收。
- `prefers-reduced-motion: reduce` 时的现有降级仍然有效。

## 5. HAHA ID 页

**页面 / 文件**

`web/site/index.html`，以及该页内联脚本、`web/site/js/ui.js` 里驱动 `#status` 的部分。

**现状**

```html
<p class="kicker">HAHA ID · 搜索并铸造</p>
<h1>给你的 agent 一个永久的名字</h1>
<p class="lede">持有币安 .ai，就能免费铸造 .haha 或 .meme。不续费，不连接钱包。复制指令，交给你自己的 agent。</p>
<p class="status demo-flag" id="status">观察模式</p>
```

老板要删的「（给你的 agent 一个永久的名字）」对应上面的 `<h1>`。代码里的 h1 没有括号。

页脚见第 1 项，本页也要删。

**目标文案（逐字）**

- 标题改为：`免费铸造您的haha id`
- 删除 h1「给你的 agent 一个永久的名字」，不要留空标题占位。
- 引导段改为：`持有币安 .ai即可免费注册haha id，永久免费，无需续费，不连钱包，复制指令给你的agent，快来抢注吧！`
- 删除状态行「观察模式 · heyi.ai · 持有 .ai · 冷却还剩 41:12」及其演示。代码里的等价句是第 2 项引用的那行，连同写死的 `41:12` 一起删。
- 删除页脚「haha.meme · 不连接钱包，不发送交易 · 链上数字接入前，标了「演示数据」的都是样例」。
- 在铸造框下面增加规则，四条原文如下，标号和标点都不要改：

①币安.ai域名持有者即可免费铸造haha id 永久免费，无需续费。

②名称规则：3–32 位小写字母或数字。

③每个.ai每小时最多可铸造1个，防女巫抢注。

④保留名：1–2 位短名和部分 3 位以上的名字为保留名，将用于空投激励活跃参与者！

**实现说明**

搜索、后缀切换、复制铸造指令、NFT 预览都保留，只换数据源。可铸造 / 已铸造 / 保留的判断以链上为准。

输入框在客户端处理，再拿结果去查链：

- 输入时把 `A-Z` 转成小写。
- 只允许 `a-z` 和 `0-9` 进入输入框。连字符、空格、下划线和其它符号不要留下，也不要静默删掉后当成另一个名字。
- 长度按转小写后的 label 计，必须是 3–32。不到 3 或超过 32 时，不出现复制铸造按钮。
- 1–2 位，以及 `HahaNamePolicy.isReserved(label)` 为 true 的名字，搜索结果状态写成「保留」，不要写成「可铸造」或「该名称可用」。已经铸出的名字仍显示「已铸造」和持有人，不要改叫保留。
- 黑名单显示不可铸造，不要叫可铸造，也不要叫保留。

合约实际规则（给校验用，不要写进上面四条文案）：

- 公开铸造 `register(string label, uint8 tld)`，免费，`msg.value` 必须是 0。
- 字符集只有小写 `a-z` 和数字 `0-9`。大写、连字符、空格、下划线都会 `InvalidCharset`。
- 公开铸造长度 3–32。短于 3 是 `LabelTooShort`，长于 32 是 `LabelTooLong`。
- 每个 `aiId` 冷却 3600 秒，未到时间 `CooldownActive(readyAt)`。
- 必须由 `.ai` 持有人自己的地址发起，`AiRequired`。
- 黑名单 `Blacklisted`，保留名 `ReservedName`。`HahaNamePolicy` 里冻结了 61 个保留名哈希（`RESERVED_COUNT = 61`），不全是 1–2 字符。
- `available` 不检查黑名单、保留名和最短 3 字符。页面上「可铸造」必须额外查 `isBlacklisted`、`isReserved`，并自己卡长度 3–32。

第②条和第④条是老板 2026-11-21 确认后的原文，与上面的校验一致。不要改回「任意字母或者数字」。

**验收**

- 首屏标题是「免费铸造您的haha id」，页面上找不到「搜索并铸造」「给你的 agent 一个永久的名字」「观察模式」「41:12」「演示数据」。
- 铸造框下能逐字看到 `②名称规则：3–32 位小写字母或数字。` 和 `④保留名：1–2 位短名和部分 3 位以上的名字为保留名，将用于空投激励活跃参与者！`
- 输入 `AbC12` 后，框里是 `abc12`。未铸造、非保留、非黑名单时出现复制按钮，指令里的名字是小写。
- 输入 `ab` 或 `a1`，状态是「保留」，没有复制铸造按钮。
- 一个 `isReserved` 为 true 的 3 位以上名字，状态是「保留」，不是「可铸造」。
- 已铸造名字显示链上持有人，不显示 mock。

## 6. 交易市场

**页面 / 文件**

`web/site/market.html`，该页内联脚本里拼统计数字的数组，`web/site/css/site.css` 的 `.grid`。

**现状**

```html
<h1>只看挂单</h1>
<p class="lede">成交收取 1%，卖家支付，比例写死。外部市场版税另有 1%。买到的是域名，不含信誉。</p>
<p class="demo-flag">演示数据 · 美元按 1 BNB = 620 美元折算，不是实时价</p>
```

说明段：

```html
<p class="note">域名转手后 ERC-8004 agent 身份销毁、信誉清零。买到的是域名，不含信誉。</p>
```

统计由脚本拼出，标签原文是：

```js
["1% / 1%", "成交费卖家付 · 外部版税"]
```

网格 CSS：

```css
.grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 14px; }
@media (max-width: 980px) {
  .grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 800px) {
  .grid { grid-template-columns: 1fr; }
}
```

宽于 980px 时代码已经是 4 列，980px 以下会变成 2 列，800px 以下变成 1 列。这个断点要改，见目标。

**目标**

- 删除 h1「只看挂单」。
- 引导段改为：`交易手续费1%，卖家支付。`
- 「买到的是域名，不含信誉。」改为：`域名信誉值不跟随转移，信誉转账清零。`
- 上面两句都出现的地方都要换。lede 整段替换成第一句。note 里删掉「买到的是域名，不含信誉。」，信誉那半句用第二句。转让后 agent 身份销毁的事实可以留在工作原理，市场 note 不要再写老板已替换掉的那半句。
- 删除「演示数据 · 美元按 1 BNB = 620 美元折算，不是实时价」。价格只显示 BNB。
- 统计改为：`手续费1%`。引导段写「交易手续费1%，卖家支付。」页面任何位置都不要出现「外部版税」「1% / 1%」或 royalty。老板 2026-11-21 已确认只展示手续费。
- 所有桌面宽度固定每行 4 个 NFT：视口宽于 800px 时用 `repeat(4, 1fr)`，包括现在会变成 2 列的 900px。删掉 `@media (max-width: 980px)` 里把 `.grid` 改成 2 列的规则。800px 及以下改为 `repeat(auto-fit, minmax(160px, 1fr))`，不要再写死 1 列。桌面不要因为 auto-fit 变成 3 列或 5 列。

**实现说明**

- 数据来自索引的有效挂单，不是 `mock.js`。
- 成交费：`buy` 时 `msg.value` 必须等于标价。合约从标价中扣 1% 给手续费地址，卖家得到 99%，记入 `pendingWithdrawal`，卖家再调 `withdraw()`。这就是「卖家支付」。
- 买到名字会触发 `HahaRegistrar` 的转账钩子：解析记录清空，agent 身份 `deactivate`，代数 +1，旧 `agentId` 的星级还留在旧 id 上，新主人从 0 开始。所以信誉不跟着走。
- 链上 `royaltyInfo` 仍返回 1%，本站 `buy` 不扣这笔。不要把这件事写进市场页、工作原理或统计。已确认（2026-11-21）。

**验收**

- 页面上找不到「只看挂单」「外部版税」「1% / 1%」「620」「演示数据」「买到的是域名，不含信誉。」
- 能看到「交易手续费1%，卖家支付。」「域名信誉值不跟随转移，信誉转账清零。」「手续费1%」。
- 1440px 和 900px 宽时都是 4 列。390px 宽时是 auto-fit，不是固定 4 列。
- 抽一条挂单，价格与 `listings(tokenId)` 一致，没有美元价。

## 7. ERC-8004

**页面 / 文件**

`web/site/erc8004.html`、`web/site/agent.html`。可以新增样式，但必须用现有橙色、像素字体和 `web/site/assets/coins/` 里的金币。不要引入新的形象。

**现状**

`erc8004.html` 引导段：

> 激活是自愿的。只有 .ai 持有人能打分，每人每 agent 一条，可修改，不能给自己打分。1–5 星，评语 140 字节以内。

另有 `<p class="demo-flag">演示数据</p>`。

**目标**

引导段改为：

> haha id，就是 Agent 的简历；信誉，写在链上。

然后用动画把玩法讲清楚，仍然是现在这个站的语气，不要改成文档长文。至少覆盖：

- 激活：名字的主人自愿激活，一个名字同一时间一个 agent。
- 签到：和积分页同一套规则，这里可以有一枚笑脸金币跳一下，链到赚取页。
- 评价：1–5 星，评语不超过 140 字节，每人每个 agent 一条，可以改，不能给自己打。
- 历代：同一个名字转让后信誉清零。旧一代的评语按代数展开，标明「第 N 代」，当前代的分数来自 `getScore`，旧代来自索引到的 `Rated`。

**动画（只用现有素材）**

- 激活：一枚 `/assets/coins/_smiley-coin.svg` 从卡片外落到名字上，落地停住，不放大。用 CSS `steps()` 或现有 canvas 的像素感，时长约 600ms。
- 星级：五颗小笑脸金币排成一行，点亮时逐个 `opacity` 从 0.35 到 1，不要缩放弹跳（缩放留给点击金币雨）。
- 转让清零：当前代的笑脸金币缩小到 0 并淡出，下面展开上一代的评语列表。这是说明动画，数据仍来自索引。
- 不要用第三方 logo、商标、真人脸、Pepe 或新的青蛙图案。金币雨里已有的 `frog` 素材可以继续在雨里出现，不要拿到本页当吉祥物。

**实现说明**

链上规则，动画文案可以缩短，但不要说错：

- `activateAgent(label, tld, agentURI)`。必须是名字主人且持有 `.ai`。URI 长度 1–2048。
- `rate(agentId, stars, review)`。`stars` 为 1–5。`review` 的字节长度 ≤ 140。评分人必须持有 `.ai` 和一个 `.haha` 或 `.meme`。agent 必须 `isActive`。不能是主人本人、不能是同一个 `.ai`、不能是该 agent 的 operator。
- 同一 `(agentId, 评分人 aiId)` 再评是修改：`Rated` 的 `edited = true`，`count` 不加。
- 评语字符串只在事件里。页面展示评语必须走索引。
- 转让调用 `deactivate`：该 `agentId` 不再 active，新激活会是新的 `agentId`，`generation` 增加。旧分还在旧 id 上。

**验收**

- 引导段是老板那句，后面能看到激活、签到、评价、历代四块，而不是只有一段规则说明。
- 打开一个发生过转让的名字（测试站先铸、激活、评分、再转到另一个地址），当前分数为 0 或新一代的分数，上一代评语仍在「第 N 代」里。
- 动画只使用本站金币和 CSS，没有外链图片，没有新的青蛙图。
- 演示旗标「演示数据」不再出现。

## 8. 任务和游戏合并为「赚取积分」

**页面 / 文件**

- 新页面：`web/site/earn.html`，路径 `/earn`（沿用 nginx `try_files`，`/earn` 会打开 `earn.html`）。
- 导航：七个现有 HTML 的 `<nav class="links">`。
- 旧页面 `tasks.html`、`games.html` 改为跳转，或由 nginx 301。两处都要做，避免漏配。

**现状**

导航原文（以 `index.html` 为例，当前页的 `aria-current` 不同）：

```html
<nav class="links" aria-label="全站"><a href="/">haha id</a><a href="/market.html">交易市场</a><a href="/erc8004.html">ERC-8004</a><a href="/tasks.html">任务</a><a href="/games.html">游戏</a><a href="/how.html">工作原理</a></nav>
```

`tasks.html`：kicker「任务」，h1「今天能做的事」，lede「必须持有 .haha 或 .meme 才能参与。数字记在 .ai 上，不可转让。社交任务是伪验证：链上不核实动作是否真的发生。」另有「演示数据 · 完成状态是样例」。

`games.html`：kicker「游戏」，h1「即将上线」，lede「第一期先占着这个位置。后面的小游戏会通过积分 earner 接口加分，补充规格排在当前合约交付之后、主网部署之前。」

**目标**

导航顺序：

`haha id` | `交易市场` | `ERC-8004` | `赚取` + 笑脸金币 | `工作原理`

「积分」两个字不要出现在导航里，用像素笑脸金币代替。图片用已有的 `/assets/coins/_smiley-coin.svg`，`alt=""`，宽高约 18px，`image-rendering: pixelated`。链接文字读屏用 visually-hidden「赚取积分」，可视文字是「赚取」加图标。

`/tasks`、`/tasks.html`、`/games`、`/games.html` 都 301 到 `/earn`。

页面上半是社交与链上任务，下半是小游戏。

上半列出：关注、转发、点赞、评论、签到、铸造、写评价、收到评价、激活。每项旁边写上下表，数字不要改。

| 动作 | 分值 | 次数 |
| --- | --- | --- |
| 签到 | 30 | 每天 1 次 |
| 铸造 | 10 | 每天最多 3 次 |
| 点赞 | 10 | 每天 1 次 |
| 转发 | 10 | 每天 1 次 |
| 评论 | 10 | 每天 1 次 |
| 关注 | 30 | 终身 1 次 |
| 写评价 | 5 | 每天最多 5 个不同 agent |
| 收到评价 | 5 | 每天最多 5 个不同评分人 |
| 激活 | 20 | 每个 `.ai` 终身 1 次 |

日切是 UTC 00:00。余额、次数、终身标记都记在 `.ai` 上，不记在单个名字上，也不能转到别的 `.ai`。

下半标题「小游戏」，正文只有：

> 敬请期待，马上上线！

不要留「即将上线」和原来那段补充规格说明。

**实现说明**

- 登录后的「今日已完成」用 `HahaPoints.statusOf(address)`。字段包括 `checkInToday`、`mintRewardsToday`、`likeToday`、`retweetToday`、`commentToday`、`followClaimed`、`reviewsGivenToday`、`reviewsReceivedToday`、`nextResetAt`。激活终身一次不在这个结构的日计数里，用索引或 `PointsChanged` 里 reason 为激活的记录判断；若 C 没有把握，激活行只展示规则和复制指令，不要用假的「已完成」。
- 铸造分由 `register` 内部 `creditMintReward` 发放，没有单独的「领取铸造分」交易。
- 写评价、收评价、激活分由 `rate` / `activateAgent` 内部 `earn` 发放，积分发满也不会让评分或激活 revert。
- 签到、关注、点赞、转发、评论才是用户直接调用的函数：`checkIn`、`claimFollow`、`claimLike`、`claimRetweet`、`claimComment`。调用前合约要求持有 `.ai` 并且至少持有一个名字（`_requireEligible`）。
- 点赞、转发、评论、关注在合约里不核验社交媒体。工作原理页要向普通用户说明这一点。赚取页按老板要的任务列表展示，不要再挂「演示数据」旗标。
- 排行榜来自 `PointsChanged` 索引。没有索引数据时显示空状态，不要用 `mock.js` 的假榜。

**验收**

- 导航只有五项，顺序如上，第四项是「赚取」加笑脸金币，没有单独的「任务」「游戏」。
- `/tasks` 和 `/games` 都到 `/earn`。
- 九行分值和次数与表一致，页面写明 UTC 00:00 重置、记在 `.ai` 上。
- 小游戏区域只有「敬请期待，马上上线！」。
- 登录后签到状态与 `statusOf` 一致。

## 9. 工作原理

**页面 / 文件**

`web/site/how.html`。这页要写完，给普通用户看，不是给开发者看。句子短，少用函数名；函数名可以放在括号里一次。地址必须是可点击的 BscScan 链接。

**现状**

kicker「工作原理」，h1「公开、可核对」，lede「haha.meme 是基于币安 .ai Agent ID 的链上身份。网站不碰私钥，也不发交易。」

正文已有 12 节，但是预览口径：地址表是 `TBD after mainnet deploy`，积分表缺写评价、收评价和激活，市场仍写「外部市场版税 1%」。这些都要改成和主网一致，并覆盖下面每一块。

**目标结构（写进页面的内容，不是给 C 的备注）**

1. 这是什么。`.haha` 和 `.meme` 两个后缀，一套合约。人在网页上不连钱包。要写链上的时候，复制指令，交给自己的 agent。agent 读 `https://haha.meme/skill.md`，先给出交易预览，用户确认后才签名。
2. `.ai` 是门票。铸造、签到、评分、领分都要求交易发送者持有币安 `.ai`。网页登录只是把这个名字带进指令和只读查询。
3. 铸造。免费，不续费，铸给自己。两个后缀共用每个 `.ai` 一小时一次。把 HAHA ID 页四条规则的确认原文再写一遍，其中第②条是「3–32 位小写字母或数字」，第④条是「1–2 位短名和部分 3 位以上的名字为保留名」。不要写「任意字母或者数字」。黑名单词表仍然不公开，用一句话说明有些词铸不了、词表不列出。
4. 转让会发生什么。名字可以转。转走后解析地址和文本记录清空，agent 身份销毁，这一代信誉不再算在新主人头上。旧评语还在链上事件里，记在上一代。
5. 市场。用 BNB 挂单、改价、撤单、购买。只写手续费 1%，卖家支付。买到的是名字。信誉不跟着走，转账清零。不要写外部版税。已确认（2026-11-21）。
6. ERC-8004。激活自愿，一个名字一代一个 agent。只有 `.ai` 持有人能评分，还要自己持有一个 haha id。1–5 星，评语 140 字节以内，每人每 agent 一条，可改，不能给自己打。转让后看新的一代。
7. 积分。把第 8 项的表原样写上。说明记在 `.ai`、每天 UTC 0 点重置日任务、关注和激活是终身一次、铸造分在铸造交易里自动加上。说明点赞、转发、评论、关注是链上记账，合约不检查社交媒体是否真的点过。
8. 指令。说明复制出去的每条指令都会让 agent 阅读 `https://haha.meme/skill.md`，并且只和本文地址表里的合约交互。
9. 地址。十个项目合约、`.ai` 注册表、手续费地址，用本文上表的链接。管理员地址可以保留，并写「硬件钱包，不可更换」。删掉所有 `TBD after mainnet deploy`。
10. 合约不可升级，没有代理。手续费比例写死。管理员不能改手续费，不能没收用户的名字。

审计报告若仍没有，保留「审计报告尚未发布」这一句，不要编一个链接。

**验收**

- 普通用户不看合约仓库也能回答：谁能铸造、多久一次、什么名字铸不了、买名字要付什么、信誉会不会跟着走、积分记在谁头上、几点重置、指令交给谁。
- 每个项目合约地址可点击，打开的是对应 BscScan 源码页，和 `DEPLOYED.md` 一致。
- 页面上没有「演示数据」、没有 TBD 地址、没有「外部版税」。

## 已确认（2026-11-21）

下面各项老板已经定了，按正文实现。这里不再待决。

1. 名称规则第②条定为：`②名称规则：3–32 位小写字母或数字。` 输入框当场转成小写，只接受 `a-z` 和 `0-9`，长度 3–32。
2. 保留名第④条定为：`④保留名：1–2 位短名和部分 3 位以上的名字为保留名，将用于空投激励活跃参与者！` 搜索里，1–2 位以及 `isReserved` 为真的未铸造名字显示「保留」，不显示可铸造。
3. 市场只展示「手续费1%」，卖家支付。不提外部版税。
4. 「登录成功」放在现有登录状态上：toast 和首页 `#status`。页脚没有「正在观察」这句，不要往页脚加。
5. 市场网格在所有桌面宽度固定每行 4 个。移动端（800px 及以下）auto-fit。

积分表和 `docs/contracts/DEPLOYED.md` 一致，没有改动：签到 30、铸造 10 且每天 3 次、点赞 / 转发 / 评论各 10、关注 30 一次、写评价 5 且每天 5 个 agent、收评价 5 且每天 5 个评分人、激活 20 且每个 `.ai` 终身一次、UTC 日切。
