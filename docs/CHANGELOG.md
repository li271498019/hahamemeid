# 变更记录

## 2026-11-21 索引器规格与阶段 A（只改文档）

- 新增 `docs/website/V1-INDEXER-SPEC.md`。从区块 134834631 索引主网事件，规定派生表、REST 字段、同步与重组、以及在同一台机器的 `/api/` 上怎么跑。
- `docs/website/V1-LAUNCH-REQUIREMENTS.md` 增加分期：阶段 A 先上单条 RPC 和空列表，删掉 `mock.js`；`haha.meme` 等索引器在 `ddao.app` 核对通过后再发。

## 2026-11-21 网站 V1 需求确认（只改文档）

老板确认了原先待决的文案。`docs/website/V1-LAUNCH-REQUIREMENTS.md` 文末改为「已确认（2026-11-21）」。

- 名称规则第②条定为「3–32 位小写字母或数字」。输入框转小写，只接受 a-z0-9，长度 3–32。
- 保留名第④条定为「1–2 位短名和部分 3 位以上的名字为保留名」。搜索结果显示「保留」。
- 市场只写「手续费1%」，不提外部版税。
- 「登录成功」写在 toast 和首页状态，不写页脚。
- 市场在所有桌面宽度固定每行 4 个，移动端 auto-fit。

## 2026-11-21 网站 V1 上线文档（给 C，只改文档）

- 新增 `docs/website/V1-LAUNCH-REQUIREMENTS.md`：正式站需求。保持现有视觉框架，接上 BSC 主网合约，并逐条写明文案、字体、金币雨、市场、ERC-8004、赚取页和工作原理。待决文案已在同日确认，见上一条。
- 新增 `docs/website/AGENT-INSTRUCTIONS-AND-SKILL-GUIDE.md`：复制指令如何填参数，以及 `https://haha.meme/skill.md` 每个动作的函数、检查、calldata 和 revert 说明。
- 新增 `docs/website/C-DEPLOY-GUIDE.md`：先部署测试站 `ddao.app`，老板验收后再上 `haha.meme`。不含 IP、密码或密钥。

## 2026-11-21 补充规格实现（D 交付，contracts/v1.1-supplement）

按 `docs/specs/SUPPLEMENT-points-games-8004v2.md` 落地，主网部署前补齐。涉及 `HahaPoints`、`HahaAgentIdentity`、`HahaReputation`、接口与常量，以及工厂检查、部署脚本、索引器文档。

- **积分模块化（earner 注册表）**：`HahaPoints` 新增 `setEarner` / `earn` / `setSpenderBudget`，每个发分动作有 module、分值、单个 `.ai` 每日上限、全网每日总额、`KeyMode`（`PerDay` / `Lifetime`）与 `requireName`。管理员可授权新模块，不必重部署积分合约；单个模块漏洞也刷不爆（硬顶 `MAX_PER_USER_DAILY`、`MAX_GLOBAL_DAILY_POINTS`、`MAX_MODULES`）。
- **四项新积分**：写评价 5 分（每 `.ai` 每天 5 个不同 agent，同一对每天一次）、收评价 5 分（每天 5 个不同评分人）、小游戏（加链上结算得分，跨游戏每 `.ai` 每天 3 局，开局扣局，分数只来自游戏合约 `scoreOf`）、激活 agent 20 分（每 `.ai` 终身一次，key 是 `ACTIVATE_ONCE`，卖名再激活不再给）。
- **消费预算**：`spend` 要求 spender 已设预算（否则 `BudgetNotSet`），按 `.ai` 每日额度与全站每日总额，`refund` 不恢复当天额度（按 gross 记账）。
- **总览查询**：新增 `statusOf` / `statusOfAi`，一次返回余额、各任务当日次数（含 `gameRoundsToday` / `reviewsGivenToday` / `reviewsReceivedToday`）与 `nextResetAt`。
- **ERC-8004 修自评漏洞**：激活必须持 `.ai`，并把操作员 `.ai` 写在链上（`operatorAiId`）。
- **二期验证预留**：身份合约新增 operator（`setAgentOperator` / `isAuthorized`，最多 8 个）、代数编号（`generationOf` / `nameGeneration`，旧 agent 验证不落到新主人）、`getAgent` / `lastOwner` / burn 后保留 URI。
- **声誉 `rate` 新门槛**：评分人必须持名字（`NameRequired`）、agent owner 必须持 `.ai`（`OwnerAiRequired`）、评分人 `aiId` 不得等于 `operatorAiId`（`SelfRating`）；通过 `try/catch` 发 `REVIEW_GIVE` / `REVIEW_RECEIVE` 分，积分发满不阻断评分。
- **事件签名变更**：`AgentActivated` 增加 `operatorAiId` 与 `generation`；新增 `Earned`、`GameRegistered`、`RoundOpened`、`RoundClaimed`、`AgentOperatorSet`。索引器见 `docs/contracts/INDEXING.md` 第 7 节。
- **工厂/脚本**：`HahaDeployer` 增加身份/声誉的 `points`、`aiRegistry` 自洽检查；`Deploy.s.sol` 更新 nonce 顺序与构造函数参数。

## 2026-11-21 补充规格修订（游戏按局领分、评价改为 5）

- 小游戏不再拆参与分和胜利分。一局的积分等于合约记下的分数，`claim(sessionId)` 领取一次。每个 `.ai` 每天 3 局，所有游戏合计（owner 已确认）。未领的局只能在开局当天的 UTC 日内领。
- 写出评价、收到评价都是 5 分，各自每天最多 5 个不同对象。不能自评，同一对当天一次。
- 铸造冷却留在铸造规则里，不进积分表，行为不改。
- 激活是 20 分，每个 `.ai` 终身一次（不是每个名字一次，也没有每天 5 个名字的上限）。owner 已确认。
- 积分的余额、次数、预算全部按 `.ai` 记账。
- `statusOf` 增加 `gameRoundsToday`、`reviewsGivenToday`、`reviewsReceivedToday`，日切时间仍是 `nextResetAt`。

## 2026-11-21 补充规格修订（日任务与 UTC 日切）

- 写出评价、收到评价、小游戏改为每个 `.ai` 的每日任务，在 UTC 0 点与签到一起归零。同一评价对子当天只算一次。
- 铸造奖励写进统一日任务表：每次 10 分，每天最多 3 次，日切与签到相同。1 小时铸造冷却单独一行，标为 cooldown, pending owner decision，本轮不改。
- 关注，以及每个名字每个 `.ai` 的激活分，仍是终身一次，日切不清。
- `statusOf` 返回每项今日次数，以及所有日任务共用的下一次重置时间（下一个 UTC 0 点）。

## 2026-11-21 补充规格（积分模块、小游戏、ERC-8004 验证）

- 新增 `docs/specs/SUPPLEMENT-points-games-8004v2.md`。这是给 D 的主网前规格，本轮不改合约。
- 覆盖：积分 earner / spender 预算、小游戏如何发分、ERC-8004 Validation 在不可升级前提下缺的接口、转让时 burn 信誉的取舍、身份挂在名字上而积分和评分人挂在 `.ai` 上。
- 与 `SPEC.md` 冲突的地方，以该补充规格开头的对照表为准。

## 2026-11-21 预览部署

- 09:15（UTC+8）把 `8fe44c2a33712b85afa80b830921bfae3abd9d40` 发到 https://haha.meme。归档 sha256 `5118d5ffdaca616a8f0d5c88c7868ed4207b07bd3eb9da88272cf84effbe9879`。`window.HAHA_PREVIEW = true`。服务器、目录、nginx 和上线清单在 [`docs/website/DEPLOY.md`](website/DEPLOY.md)。

## 2026-11-21 网站视觉

- 网站用原创硬币。不用第三方币标和商标，不画真人，不画 Pepe。青蛙只留在币雨里的那一枚硬币。
- 数字旁边用像素笑脸硬币，页面上不写「积分」。
- 鼠标接住落下的硬币时，硬币停下并高亮，离开后继续落。不用绕着光标转的光环。
- 币雨改小一半、数量大约四倍，半透明下落；接住时不透明并高亮。点一下会弹起、翻转，溅出小笑脸和 +1，再从顶上重新落下。
- 六页静态站放在 `web/site/`：交易市场、ERC-8004、任务、游戏、工作原理，加上 haha id。写操作仍是复制给 agent 的指令。演示数据在 `js/mock.js`。导航换成拍板的笑脸金币。
- 预览站顶栏、复制按钮旁的「主网上线后才会生效」，以及 `noindex`，都由 `web/site/js/config.js` 的 `HAHA_PREVIEW` 控制。上线时改成 `false`。

## 2026-11-20 网站规划

- 加入网站规划 v0.1：`docs/website/PLAN.md`。

## 2026-11-20 实现阶段（D 交付）

本轮把规格变成可部署的代码。下面按「文档改动」与「实现改动」分开记。

### 文档层面新增/修订

- 新增 `docs/contracts/QUESTIONS.md`：开工前提出的 11 条疑问与裁决结论，含「裁决执行记录」表。
- 新增 `docs/contracts/AUDIT.md`：自审计报告。列出全部发现的问题（含两个真实 bug）、构建信息、遗留风险、第三方审计建议重点。
- 新增 `docs/contracts/SPEC-COVERAGE.md`：`SPEC 12` 测试清单逐项打勾，每条指向实际测试函数。
- 新增 `docs/contracts/INDEXING.md`：给索引器的 7 条注意事项（`aiId == 0` 的歧义、两种 `Transfer`、`RecordsCleared` 一次清三样、积分只认 `PointsChanged`、`tokenURI` 缓存、一次转让的完整事件序列、阶段一没有的东西）。
- 新增 `docs/contracts/DEPLOY.md`：部署流程、dry-run、部署后核对、故障排查。
- 新增 `test/fork/FROZEN.md`：fork 冻结数据的来源、槽位布局、边界与风险。
- **`docs/contracts/DEPLOYED.md` 仍未创建**，按 `SPEC 13` 要求，真正部署后才生成。

### 实现层面必须记录的两个技术决定

#### 1. `via_ir = true` 是硬约束

实测：solc 的非 via-ir 代码生成器在处理「多个合约互相引用 + 十几次 `new`」时会 stack too deep。
关掉 `via_ir` 时 `HahaDeployer` 直接编译失败。拆子工厂也不能解决：
子工厂 initcode 里内嵌业务合约，父工厂再内嵌子工厂，总量不变。

因此 `foundry.toml` 里 `via_ir = true`。所有体积与 gas 断言都基于 via-ir 产物，
审计方需按实际部署字节码复核（`AUDIT.md` 第 10 节第 1 条已列此风险）。

#### 2. 部署不是「一个构造函数搞定」

`SPEC 13` 原本要求单个 `HahaDeployer` 构造函数完成全部部署。**实测在物理上做不到**：

| 需要内嵌 | initcode 字节 |
| --- | --- |
| HahaRegistrar | 11,047 |
| HahaCoreDeployer（Policy + Metadata） | 10,940 |
| HahaRegistrarDeployer | 11,368 |
| HahaPeripheryDeployer（4 个合约） | 18,124 |
| HahaNameSystemDeployer | 8,970 |
| 小计 | 49,402 |
| 加父工厂自身逻辑 | 6,743 |
| **总计** | **56,145 → 超 EIP-3860 的 49,152** |

改为：**`HahaDeployer` 只做编排与校验，业务合约由部署脚本按固定顺序 CREATE**。
脚本用 nonce 预测解开依赖环（Resolver 需要 Registry、Registry 需要 Resolver；
Registrar 需要 Points/Identity、它们又需要 Registrar），每一步断言「预测 == 实际」。

`HahaDeployer` 的职责因此收敛为：
1. 校验十个合约互相保存的地址是否自洽（22 条断言）；
2. 校验 Policy 的两份名单数量；
3. 调一次 `registry.bootstrap()`。

它的 initcode 从 56,145 降到 **7,040 字节**。

`SPEC 13` 的实质要求一条不减：不可升级、部署 EOA 零权限、部署后无写函数、`bootstrap` 只成功一次。
这条偏离已写入 `QUESTIONS.md`，**需要 owner 在下次复核时确认**。

### 自审计发现并修复的两个真实 bug

#### 1. `activateAgent` 查错了 `ownerOf`（严重）

`HahaAgentIdentity.activateAgent` 原本用 `_ownerOf(nameTokenId)` 判断调用者是不是名字持有人。
但 `_ownerOf` 查的是**本合约**的 NFT——名字 NFT 在 `HahaRegistrar` 里，
本合约的 token 是 agent NFT（增量 id），两套编号完全不同。

后果：**agent 功能上线即坏死**，任何 `activateAgent` 都会 revert `NotNameOwner`。

修复为 `IERC721(registrar).ownerOf(nameTokenId)`。

#### 2. 签到在 day 0 误判（中）

`SPEC 6.8` 明确禁止「把『从未领取』存成 day 0」（对 like/retweet/comment），
但签到用 `_lastCheckInDay[aiId] >= day` 判断，而该 mapping 默认值是 0、day 0 也是合法日序号。
在 1970-01-01 UTC 当天，所有人第一次签到都会被误判为「今天已签到」。

修复：新增 `_hasCheckedIn[aiId]` 标记，与 `DayClaim.done` 同一思路。
新增只读 `hasCheckedIn(bytes32)`。

### `refund` 限额（owner 第 4 条裁决的落地）

- 新增 `mapping(bytes32 => mapping(bytes32 => uint256)) _spendable`。
- `spend` 成功 → `_spendable[aiId][reason] += amount`。
- `refund` 要求 `amount <= _spendable[aiId][reason]`，否则 revert
  `RefundExceedsSpendable(uint256 requested, uint256 available)`；成功 → `-=`。
- 新增只读 `spendableOf(bytes32 aiId, bytes32 reason)`。
- 新增 error `NotAContract`（`setSpender(account, true)` 时 account 无代码）。

### fork 测试：改为两层

`SPEC 4` 要求在区块 `134683411` 核实。实测该区块在公共 RPC 上返回 `missing trie node`
（非归档节点读不了历史状态）。因此按 `QUESTIONS` 第 11 条裁决：

- **离线层**（`test/fork/ForkOffline.t.sol`，13 条）：`.ai` 字节码与关键 storage 冻结进
  `test/fork/state/`，用 `vm.etch` / `vm.store` 还原。不联网，CI 必跑。
- **在线层**（`test/fork/ForkOnline.t.sol`，10 条）：`--fork-url` 起真实 fork，非 fork 环境自动 skip。

两层都把运行时字节码哈希 `0xc4006e6e...6ace` **写死断言**。

### 测试结果

```
259 passed, 0 failed, 10 skipped
```

| 类型 | 数量 |
| --- | --- |
| 单元 | 211 |
| 模糊（1000 runs / 条） | 8 |
| 不变式（128 runs × 48 depth） | 10 |
| fork 离线 | 13 |
| fork 在线（可选） | 10 |

### 工具

- `tools/keccak.py`：纯 Python keccak256，无第三方依赖（仓库脚本不依赖仓库外的工具）。
- `tools/check_hashes.py`：独立复核全部哈希与 SVG 字节级一致性。**不经过 forge**，作为第二条验证路径。
- `tools/gen_svg_literals.py`：从 `assets/svg/*.svgpart` 生成 `src/libraries/HahaSvg.sol`。
- `tools/gen_test_lists.py`：从 `*.hashes.txt` 生成 `test/TestLists.sol`。
- `tools/freeze_fork_state.py`：冻结 `.ai` 字节码与 storage.

## 2026-11-20 开工前裁决（D 提问，owner 回复）

D 通读规格后提出 11 条疑问，见 `docs/contracts/QUESTIONS.md`。owner 裁决如下，本节优先于 `SPEC.md` 中的冲突表述。

### 部署时序（对应 QUESTIONS 第 1、2 条）

- `HahaNamePolicy` 与 `HahaMetadata` 在工厂里**先实际部署**，再把地址传给后续合约。二者不依赖任何业务合约，也没有人会回调它们，因此不参与 CREATE2 预计算。
- 只有互相回调的五个合约（`HahaRegistry`、`HahaRegistrar`、`HahaResolver`、`HahaAgentIdentity`、`HahaPoints`）用 CREATE2 预计算地址，构造函数只保存地址。
- 这样 208+61 个哈希在 init code 里只出现一次（`HahaNamePolicy` 自己的），避免 `HahaDeployer` 逼近 EIP-3860 的 49152 字节上限。
- `SPEC 13.2`「不在对方还没部署时回调它」解释为：**业务合约之间**不得在对方未就绪时互相调用。工厂自身按依赖顺序部署、把已部署好的地址传给下一个合约，是允许的。否则整条部署链无法成立。

### 工厂写权限（对应 QUESTIONS 第 3 条）

- `HahaDeployer` 自身不暴露任何外部写函数，constructor 完成后没有任何状态修改入口，只保留只读地址 getter。
- 工厂在 constructor 内部对其他合约发起的调用（部署、`bootstrap`、依赖注入）不计入「工厂的写权限」。
- 测试断言方式：枚举工厂 ABI 的每个外部函数，要求全部是 `view`。

### `refund` 限额（对应 QUESTIONS 第 8 条）—— owner 改动了规格

- 原规格 `6.8` 的 `refund` 无上限，等于给授权 spender 开一条无限造分通道。owner 要求加限制。
- 新增状态：`mapping(bytes32 aiId => mapping(bytes32 reason => uint256)) spendable`，记录「该 `.ai` 在该 `reason` 下累计 `spend` 过、且尚未退回的额度」。
- `spend` 成功后 `spendable[aiId][reason] += amount`。
- `refund` 要求 `amount <= spendable[aiId][reason]`，否则 revert `RefundExceedsSpendable(uint256 requested, uint256 available)`；成功后 `spendable[aiId][reason] -= amount`。
- 因此 spender 无法凭空造分：退还总额永远不会超过它在同一 `reason` 下真实扣掉的总额。
- `refund` 的其余条件不变：调用者必须是已授权 spender、`amount > 0`、用户当前仍有 `.ai`（否则不知道记到哪个 `aiId`）、不要求此刻持有名字。
- 新增只读函数 `spendableOf(bytes32 aiId, bytes32 reason) external view returns (uint256)` 供 spender 与索引器核对。
- `SPENDABLE` 只增不减地受 `spend` 约束，`refund` 只能消减它。这条是阶段二拍卖合约的额度来源。

### 新增 error 名（对应 QUESTIONS 第 7 条）

- `NotAContract`：`setSpender(account, true)` 时 `account` 没有代码。
- `RefundExceedsSpendable(uint256 requested, uint256 available)`：见上。
- `setSpender(account, false)` 不检查代码，取消授权永远放行。理由：取消授权必须是管理员可无条件使用的安全阀，否则合约被 selfdestruct 后就再也摘不掉授权。

### 以下按 D 的建议默认执行，owner 未反对

- **`available()` 语义**：保持规格定义（字符集合法、长度 1–32、未铸造），不判断黑名单与保留名。NatSpec 里写明公众可注册性要叠加 `policy` 查询与 `len >= 3`。前端误判风险记在 QUESTIONS 第 6 条。
- **`NameMinted.aiId == bytes32(0)`**：保留名铸造全落在同一 `aiId` 分区。不改事件签名，在 `docs/contracts/INDEXING.md` 提示索引器：`aiId == 0 && reservedMint == true` 的行不代表任何身份，不得按 `aiId` 聚合。
- **`primaryHolder` 清理**：`setAddr` 导致 `addr(node) != primaryHolder[node]` 时，清掉该用户主名字的同时 `delete primaryHolder[node]`，避免悬空占用。
- **fork 测试分层**：离线层把锁定区块的 `.ai` 代码与相关 storage 冻结进 `test/fork/`，用 `vm.etch` / `vm.store` 还原，CI 无需联网；在线层用 `--fork-url` 跑真实 RPC 做交叉验证。两层都把运行时字节码哈希写死断言。

### 本次新增文件

- `docs/contracts/QUESTIONS.md`：11 条疑问与裁决结论。
- `docs/contracts/INDEXING.md`：给索引器实现方的注意事项。
- `docs/contracts/DEPLOYED.md`：本阶段**不创建**，部署完成后按 `SPEC 13` 生成。

## 2026-11-20 复核（续）

- 每天的铸造奖励次数写死为 3。默认每次 10 分，默认一天最多 30 分。管理员仍可在 `999999999` 以内修改每次的分数，不能修改次数。删掉「管理员最多把次数改到 10」。
- 域名 NFT 合集名是 `haha id`，符号是 `HAHAID`。单枚 metadata 里的 `name` 仍是 `label.tld`。
- ERC-8004 身份 NFT 不另做图画。`tokenURI` 返回注册文件；文件里的 `image` 复用所绑定域名的链上 SVG。
- 名字转让时 burn agent NFT，owner 已确认，从「未决」划掉。
- label 最长 32 继续作为默认留在未决问题里。

## 2026-11-20 复核（PR #1）

owner 看过规格后改了这些决定。下面几条覆盖同日第一条记录里相应的句子。

- 社交任务改为伪验证。没有后端，没有 EIP-712 凭证，没有 nonce，没有签名者，也没有轮换签名者的管理员功能。参与条件和签到相同：调用时持有 `.ai`，并且持有至少一个 `.haha` 或 `.meme`，积分记在 `.ai` 身份上。用户直接调用合约领取。
- `follow` 为 30 分，每个 `.ai` 终身一次。`like`、`retweet`、`comment` 各 10 分，各自每个 UTC 日一次，日界与签到相同。
- 链上不核实这些动作是否真的发生。接受的风险是：满足条件就能领，但 follow 终身最多一次，另外三项每个 `.ai` 每天最多一次。
- 管理员只剩三项：铸造保留名、修改积分参数、授权或取消积分 spender。
- 单项积分的硬上限从 1000 改为 `999999999`。每天的铸造次数后来改为写死 3，见上面的续记，不要再实现「最多改到 10」。
- owner 确认：管理员地址部署后不可更换；市场阶段一只收 BNB。这两项从「未决」划掉。
- label 最长 32：owner 没有反对，继续按 32 实现，但仍留在未决问题里作为默认。

## 2026-11-20

确立阶段一的合约规格。本阶段不写 Solidity。

已拍板：

- 链是 BSC 主网。两个 TLD `.haha` 和 `.meme` 共用一套合约。`abc.haha` 和 `abc.meme` 是两个名字。tokenId 用含 TLD 的 namehash，不用 SPACE ID 那种 labelhash。
- 铸造免费、永久、无续费、无总量上限、单地址没有个数上限。每次只铸一个，只铸给 `msg.sender`。
- 门禁是调用者当前持有币安 `.ai`。冷却 1 小时，按 `.ai` 身份计，两个 TLD 共用。
- 公众名字至少 3 个字符，只允许 `a-z` 和 `0-9`。大写直接拒绝，网站负责转小写。label 最长 32。owner 复核时没有反对，但仍作为默认留在未决问题里。
- 1–2 字符全部保留。另有 61 个保留名，部署时写死，管理员不能追加。不预铸造，管理员按需铸给任意地址。
- 黑名单 v2 共 208 个词，加盐哈希 `keccak256(abi.encodePacked("HAHA_V2", label))`，部署后冻结，管理员也不能注册。leet 和组合词只在链下拦。
- 明确允许公众注册 `btc`、`bitcoin`、`eth`、`sol`、`usdt`、`usdc`、`bnb`、`lido`、`crypto`、`satoshi`、`wallet`、`exchange`。`trump` 留在黑名单。
- 解析器只做正向 `addr`（未设置时回落到 NFT owner，转让时清除）、手动主名字、通用 text。转让时 text 一并清除。不做多链地址、contenthash、pubkey、ABI、通配符和 CCIP。
- ERC-8004 阶段一只做身份和声誉。激活与名字 1:1。名字转让则 burn agent，声誉对这个名字归零，旧事件保留。评分只允许 `.ai` 持有人，1–5 星，每人每 agent 一条可修改记录，不能给自己打分。评论文本最长 140 字节，只进事件。
- Validation Registry 和 x402 留到后面的独立合约。
- 积分不是代币，按 `.ai` 身份记账。持有 `.haha` 或 `.meme` 才能签到和领分。UTC 日界。签到 30，铸造奖励 10 且每天最多 3 次。社交任务的领取方式见上面的复核记录，不再使用 EIP-712。没有连续签到奖励。
- 自有市场只做 BNB 一口价，卖家付 1%，比例写死。NFT 另声明 ERC-2981 的 1% 给同一接收者，供外部市场参考。本市场不叠加第二笔版税。
- 管理员 `0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7`。手续费接收者 `0x57A76124bC919F7509bEb54924E8448258De90df`。部署 EOA 结束后权限为零。全部合约不可升级。
- 管理员只能：铸造保留名、改积分参数、授权积分 spender。不能拉黑地址、动用户 NFT、改手续费、改黑名单、暂停转账，也不能设立签名者。复核记录把「轮换凭证签名者」删掉了。
- 链上 SVG 使用已批准的橙黄渐变底图。`tokenURI` 读取时拼接，不按 token 存储图片。

同一天核实：

- `.ai` 注册表 `0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F` 在区块 `134683411` 的运行时字节码哈希为 `0xc4006e6e6ffaaf6996116617392beabe4f5f0a0795841322f91c2ceac34d6ace`。它是 ERC-721，`handleOf` / `ownerOfHandle` 可用，tokenId 等于 `keccak256(handle)`，转账 revert `Soulbound()`。不是 EIP-1967 代理。
- SPACE ID 对照代码取自 `@siddomains/sid-contracts@0.1.31`。GitHub 上的 `Space-ID/SpaceIDContract` 当天返回 404。
