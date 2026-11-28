# 01 基线：已部署合约与旧 ABI

## 源码与部署

| 项 | 值 |
| --- | --- |
| 仓库 | 提交人A 的 `https://github.com/li271498019/hahameme` |
| 本规格所读 commit | [`0942b75e792246a6376a96b760d185e2e803f1f9`](https://github.com/li271498019/hahameme/commit/0942b75e792246a6376a96b760d185e2e803f1f9) |
| 合约源码自部署提交 `70fe8e79e864586f86ee5e6f3a819e72ff5dd7bf` 至上述 commit | `src/`、`script/`、`test/` 无差异 |
| 链 | BSC 主网，chainId 56 |
| 编译器（已部署那一版） | solc `0.8.28`，optimizer runs 200，`via_ir`，EVM `cancun` |
| 新模块必须沿用 | 同一编译器、同一 OpenZeppelin v5.1.0、`via_ir = true`。不要升级 OZ |

地址以 [`docs/contracts/DEPLOYED.md`](../contracts/DEPLOYED.md) 为准。新模块只准读取和按下面的方式调用，不准替换。

| 合约 | 地址 |
| --- | --- |
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
| 币安 `.ai` | `0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F` |
| 管理员 | `0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7` |
| 手续费接收 | `0x57A76124bC919F7509bEb54924E8448258De90df` |

`.ai` 上链能核对的只有 `handleOf`、`ownerOfHandle`、`ownerOf(uint256(keccak256(handle)))` 三者一致。灵魂绑定、一人一个、KYC 是外部假设，新模块不得再写一套「证明 KYC」的函数。

## 无迁移

不部署第二套 Registrar、Points、Identity、Reputation。不把用户余额迁到新合约。新模块若被换掉，已写入旧 Points 的余额仍然留在 `0xB2D0…DfAa`。订单状态在新模块里，换模块不能魔法恢复未确认的锁名；所以第一季模块一旦有订单，就不要换地址。升级路径不存在。

## 旧 ABI：本季会用到的

选择器按 `0942b75` 源码签名用仓库内 `tools/keccak.py` 计算。

### HahaRegistrar

源码 [`src/HahaRegistrar.sol`](https://github.com/li271498019/hahameme/blob/0942b75e792246a6376a96b760d185e2e803f1f9/src/HahaRegistrar.sol)。

| 函数 | 选择器 | 权限与行为 |
| --- | --- | --- |
| `adminMint(string,uint8,address)` | `0x65f5a090` | 仅管理员。`tld` 0 或 1。`to` 非 0，**不需要** `.ai`。1–2 位只要 `a-z0-9` 且不在黑名单。已存在则 `NameTaken`。第 139–155 行 |
| `register(string,uint8)` | `0x767b79ed` | 公众，最短 3。本季池内名字走不到这里 |
| `ownerOf(uint256)` | `0x6352211e` | 未铸造 revert |
| `nodeOf(string,uint8)` | 纯函数 | 与 `HahaNamehash` 相同 |
| `approve(address,uint256)` | `0x095ea7b3` | 用户以后自己挂单用。发放交易不要调用它 |
| `setApprovalForAll(address,bool)` | `0xa22cb465` | 同上 |

`adminMint` 内部调用 OpenZeppelin `_mint`，不是 `_safeMint`（Registrar 第 234 行，OZ `ERC721._mint` 第 285 行）。合约地址可以成为接收人，不会调用 `onERC721Received`。之后若有人从市场 `buy`，那一步是 `safeTransferFrom`，合约买家才必须实现接收接口。

没有批量铸造。20 单就是最多 20 笔管理员签名。不要写 multicall 代铸，也不要在新模块里调用 `adminMint`（新模块不是管理员）。

事件：

```solidity
event NameMinted(
    uint256 indexed tokenId,
    address indexed owner,
    uint8 tld,
    bytes32 indexed aiId,
    string label,
    bool reservedMint
);
```

管理员铸造时 `aiId` 为 `bytes32(0)`，`reservedMint` 为 `true`。ERC-721 `Transfer(address indexed from, address indexed to, uint256 indexed tokenId)` 的 `to` 才是接收人。交易回执的 `to` 是 Registrar 地址，不是接收人。

1–2 位的技术边界：全部 `a-z0-9` 的 1–2 位（含数字与字母混合）公众都不能铸。本季池只使用其中的纯数字与纯字母。混合位不在池内，模块必须拒绝。61 个长度 ≥ 3 的显式保留名也不在池内。管理员密钥仍然可以绕过模块直接 `adminMint`。产品不再把「防止私铸」当作本季功能，但测试和面板必须把这条边界写出来。

### HahaPoints

源码 [`src/HahaPoints.sol`](https://github.com/li271498019/hahameme/blob/0942b75e792246a6376a96b760d185e2e803f1f9/src/HahaPoints.sol)，常量 [`src/libraries/HahaConstants.sol`](https://github.com/li271498019/hahameme/blob/0942b75e792246a6376a96b760d185e2e803f1f9/src/libraries/HahaConstants.sol) 第 50–56 行。

| 函数 | 选择器 | 谁调用 | 本季用法 |
| --- | --- | --- | --- |
| `balanceOf(bytes32)` | `0x6c7f1542` | 任何人 | 快照复算的对照，不以它作为历史区块的唯一来源 |
| `statusOf(address)` | `0x97a5d5b5` | 任何人 | 不含兑换冷却，不含本季订单 |
| `statusOfAi(bytes32)` | `0x0ef510ce` | 任何人 | 已知 `aiId` 时用。handle 被改写时它仍能读旧余额 |
| `spendableOf(bytes32,bytes32)` | `0x1cc09416` | 任何人 | 只给已扣未退的 reason。本季不做退款 |
| `isSpender(address)` | `0x9a206ece` | 任何人 | 部署后核对 |
| `spend(address,uint256,bytes32)` | `0xa9f05de6` | 已授权 spender | 兑换模块在用户交易里扣 200。第 518–551 行 |
| `refund(address,uint256,bytes32)` | `0x0e66ac12` | spender | **本季模块不得调用** |
| `earn(bytes32,address,bytes32)` | `0xc1c37da8` | 该 action 的 module | 验证 30、找错 100。第 394–436 行 |
| `setSpender(address,bool)` | `0x6be3f3e0` | 管理员 | 授权兑换模块。取消授权不检查代码 |
| `setSpenderBudget(address,(uint256,uint256))` | `0x6f4167c4` | 管理员 | 见 `00`。未设预算时 `spend` 一律 `BudgetNotSet` |
| `setEarner(bytes32,(address,uint256,uint64,uint256,uint8,bool,bool))` | `0x2206f977` | 管理员 | 只登记两个新 actionId。禁止覆盖已有 id |
| `setPointParams(uint256,uint256,uint256,uint256,uint256,uint256)` | 旧签到等六项 | 管理员 | **本季部署步骤不得调用** |

`spend` 不需要用户对 Points 另做 approve。调用者是 spender 合约时就可以扣，只要用户当时还能通过 `.ai` 三重核对并且 `registrar.balanceOf(user) > 0`（`_requireEligible`，第 966–970 行）。所以兑换模块必须只在验过 EIP-712 之后调用它。后台热钱包不得成为 spender。

`refund` 不恢复当日 gross 预算（第 554–568 行）。本季初版不提供自动退款函数。若 L 以后对异常扣分批准退款，还要单独处理这个预算不会回来的事实。这不是现在已经批准的「一律不退」。

`earn` 的分值来自 `EarnerConfig.points`，调用参数里没有金额。返回 0 表示没发分，而且**在写去重 key 之前**返回（第 408–421 行）。触顶不会把「今天已领」写成真。模块必须看见返回值；返回 0 就 revert，让本模块的已领标记随交易回滚。

`EarnerConfig` 字段顺序：`address module, uint256 points, uint64 perUserDailyCap, uint256 globalDailyPoints, uint8 keyMode, bool requireName, bool enabled`。`KeyMode`：`None = 0`，`PerDay = 1`，`Lifetime = 2`（第 19–23 行）。

硬顶，管理员也超不过：

- 单次 `points`：1 到 `100`（`MAX_EARNER_POINTS`）。30 和 100 都在范围内。200 的兑换**不能**走 `earn`。
- `perUserDailyCap`：1 到 `50`。这是**每个 actionId、每个 aiId、每个 UTC 日的成功次数**，不是分数，也不是全站所有模块共 50 次。
- `globalDailyPoints`：该 action 全网每个 UTC 日发出的分数上限，最大 `1_000_000`，且不得小于单次 `points`。
- 不同 actionId 最多 `32` 个。现有已占用 `REVIEW_GIVE`、`REVIEW_RECEIVE`、`ACTIVATE`。新模块只用两个新 id。

内置奖励不动：签到 30、铸造 10 且每天最多 3 次、关注 30 终身一次、点赞 / 转发 / 评论各 10 每天一次、写评价 5、收评价 5、激活 20 终身一次。不要改 `setPointParams`，不要改这三条已启用的 earner。

禁止当作新 actionId 的旧 reason：`CHECKIN`、`MINT`、`FOLLOW`、`LIKE`、`RETWEET`、`COMMENT`，以及已锁定形态的 `REVIEW_GIVE`、`REVIEW_RECEIVE`、`ACTIVATE`。`setEarner` 对后三个还有额外的 keyMode 限制（第 611–616 行），覆盖它们会弄坏评价和激活。

`PointsChanged(bytes32 indexed aiId, address indexed user, int256 delta, uint256 newBalance, bytes32 indexed reason)` 是余额的链上来源。`Earned(...)` 只多带 `uniqueKey`。快照以 `PointsChanged` 重放为准，不以网站排行榜的当前行为准。

### 身份，仅验证绑代用

[`src/HahaAgentIdentity.sol`](https://github.com/li271498019/hahameme/blob/0942b75e792246a6376a96b760d185e2e803f1f9/src/HahaAgentIdentity.sol) 第 214–224 行：`generationOf(uint256)` 在 burn 之后仍然保留。`deactivate` 不删除代数（第 183–198 行）。每日验证要核对此函数，但不要要求领分时 agent 仍 `isActive`。任务针对的是固定区块上的那一代。

`getScore` 只返回 `(count, sum)`。评语在 `Rated` 事件。新模块不写信誉合约。

## 候选池计数

两位纯数字：`10² = 100`。两位纯字母：`26² = 676`。合计 776 个标签。两个后缀：`776 × 2 = 1552`。混合两位（例如一个数字加一个字母）共 `520 × 2 = 1040` 枚，代码同样只能管理员铸，**但不在本季池**。这是 L 未把它们纳入兑换，不是代码没锁。

黑名单没有长度 ≤ 2 的词，不会单独挡住这 1552 个标签。是否已经铸出，以 `isMinted(bytes32)`（选择器 `0x9e4c0be3`，[`HahaRegistrar.sol`](https://github.com/li271498019/hahameme/blob/0942b75e792246a6376a96b760d185e2e803f1f9/src/HahaRegistrar.sol) 第 182–184 行）的干净布尔值为准。返回 `false` 才是未铸造。调用失败、空返回、长度不是 32 字节、以及 HTTP 403，都是未查清，不是未铸造。本文件不给库存数字。

`ownerOf` 在未铸造时 revert `ERC721NonexistentToken(uint256)`，选择器 `0x7e273289`（OpenZeppelin `draft-IERC6093.sol`，`ERC721._requireOwned` 第 449–454 行）。只有 revert 数据恰好是这个选择器加上**本次查询的** tokenId，才能当作未铸造。其它 revert、空数据、短数据、tokenId 不符，全部失败关闭。不要用集合名称 `name()` 判断一枚名字是否存在。
