# 02 最小新模块与拟议 ABI

## 选型

把兑换、每日验证、找错放进 **一个** 合约 `HahaSeason1`，是提交人A 给 D 的设计建议，不是 L 点名的强制形态。L 强制的是：不新开积分合约，新代码只调用现有 `HahaPoints`。D 若因体积或评审要拆成兑换合约和发分合约，保持本文件的函数签名，把地址分成两个，并在实现 PR 里说明。下文用一个地址描述调用关系。

这个建议中的合约同时是：

- `HahaPoints` 的 spender：只在用户自己的兑换交易里 `spend` 200。
- 三个 earner action 的 module：`SEASON1_VERIFY`、`SEASON1_FIND`、`SEASON1_ACCIDENT`。同一个地址可以登记多次 `setEarner`。

不新增积分合约。不使用 `registerGame`。验证分和找错分都是固定分，不是局内分数。

若 `via_ir` 后运行时字节码超过 24576，再拆成 `HahaSeason1Exchange` 与 `HahaSeason1Rewards`，函数签名保持本文件不变，只把地址分成两个。拆分前先停下来把体积写进测试输出，不要删掉去重或签名检查来硬塞。

旧合约一个字节都不改。

## 常量

```solidity
uint256 public constant SEASON_ID = 1;
uint256 public constant PRICE = 200;
uint64  public constant START_TS = 1795478400;      // 2026-11-24T00:00:00Z
uint64  public constant END_TS = 1796774400;        // 2026-12-09T00:00:00Z
uint64  public constant FULFILL_GRACE = 12 hours;
uint16  public constant DAILY_MAX = 20;
uint16  public constant SEASON_MAX = 300;
bytes32 public constant ACTION_VERIFY = "SEASON1_VERIFY";
bytes32 public constant ACTION_FIND   = "SEASON1_FIND";
bytes32 public constant ACTION_ACCIDENT = "SEASON1_ACCIDENT";
bytes32 public constant REASON_REDEEM = "SEASON1_REDEEM";
bytes32 public constant VERIFY_KEY    = "VERIFY_DAY";
```

`bytes32("SEASON1_VERIFY")` 是右补零的 Solidity 字面量。`VERIFY_KEY` 对所有人、所有天相同。`KeyMode.PerDay` 存在每个 `(actionId, aiId, uniqueKey)` 里的是 UTC 日序号，下一天同一 key 可以再领。这是旧 `earn` 第 408–425 行的行为，模块不要自己再发明滚动 24 小时。

找错的 `uniqueKey` 是复核后的 `canonicalRootCauseId`，`KeyMode.Lifetime`。同一 `.ai` 对同一根因不能领两次。不同 `.ai` 的互斥由本模块的 `canonicalClaimed` 保证，不要指望 Points。用户签名不覆盖这个根因 id，见 `04` 和 `06`。

## 构造

```solidity
constructor(
    address admin_,
    address points_,
    address registrar_,
    address identity_,
    address aiRegistry_,
    uint64 snapshotConfirmations_
)
```

五个地址都必须是 `01` 里的主网地址（测试里用 mock）。`admin_` 是现有管理员，合约不提供换管理员。`snapshotConfirmations_` 的生产值是已批准的 `15`。构造之后不得再改。测试可以传入别的 `>= 1` 的值，用来证明「不够深就不能公布」，但主网构造参数用 15。

不可升级。没有 `selfdestruct`。没有接收 BNB 的 `receive`。

## 枚举与结构

```solidity
enum Tier { Reserved, Boundary } // 0, 1
enum OrderStatus { None, Pending, Fulfilled, CreditOpen, AccidentRefunded, AccidentClosed }
enum Verdict { Match, Discrepancy } // 都发 30 分

struct Order {
    bytes32 aiId;
    address applicant;   // 交易发送者，须为当时的 .ai owner
    address recipient;
    uint8 tld;
    string label;
    uint64 dayIndex;
    uint64 createdAt;
    OrderStatus status;
    Tier tier;
}

struct DayMarket {
    bytes32 merkleRoot;
    uint64 snapshotBlock;
    bytes32 snapshotBlockHash;
    uint16 reservedCount;
    uint16 remainingSlots; // 边界组可成功的笔数，公布后不变
    uint16 boundaryFilled;
    uint16 reservedFilled;
    bool opened;
}

struct ApplyAuth {
    uint256 seasonId;
    uint64 dayIndex;
    bytes32 aiId;
    string label;
    uint8 tld;
    uint256 price;
    address recipient;
    uint256 nonce;
    uint64 deadline;
    bytes32 root;
    uint8 tier;
    uint256 balance;
}
```

`ApplyAuth` 里的 `tier`、`balance`、`root` 必须和 Merkle 叶、当日 root 一致。签名绑这些字段之后，后端不能改接收人或名字。

## 错误

```solidity
error NotAdmin();
error BadTime();
error DayClosed();
error RootFrozen();
error BadRoot();
error BadProof();
error NotEligible();
error BoundaryFull();
error SeasonUsed();
error NameTaken();
error NameCheckFailed();
error OutsidePool();
error BadPrice();
error BadSignature();
error BadNonce();
error AiRequired();
error ZeroAddress();
error EarnNotPaid();
error AlreadyClaimed();
error UnknownCommit();
error CanonicalUsed();
error CanonicalUnassigned();
error ZeroCommit();
error BadReveal();
error StaleGeneration();
error NotOrder();
error StillPending();
error SnapshotTooFresh();
error ConfirmationsLocked();
```

不要用字符串 `require`。

## 事件

```solidity
event DayRootSet(
    uint64 indexed dayIndex,
    bytes32 merkleRoot,
    uint64 snapshotBlock,
    bytes32 snapshotBlockHash,
    uint16 reservedCount,
    uint16 remainingSlots
);

event Redeemed(
    uint256 indexed orderId,
    bytes32 indexed aiId,
    address indexed applicant,
    address recipient,
    uint8 tld,
    string label,
    uint64 dayIndex,
    uint8 tier,
    uint256 price,
    bytes32 root
);

event MintConfirmed(
    uint256 indexed orderId,
    uint256 indexed tokenId,
    address indexed recipient
);

event Verified(
    bytes32 indexed aiId,
    uint64 indexed dayIndex,
    uint256 indexed agentId,
    uint64 generation,
    uint8 verdict,
    bytes32 taskPackHash,
    uint256 points
);

event FindingCommitted(
    bytes32 indexed commitHash,
    bytes32 indexed aiId,
    address indexed committer,
    bytes32 reportEvidenceHash
);

event CanonicalAssigned(
    bytes32 indexed reportEvidenceHash,
    bytes32 indexed canonicalRootCauseId
);

event FindingPaid(
    bytes32 indexed canonicalRootCauseId,
    bytes32 indexed reportEvidenceHash,
    bytes32 indexed aiId,
    address recipient,
    uint256 points
);

event ValidatorSet(address indexed account, bool allowed);
event RewardSignerSet(address indexed account);
event TaskPackSet(uint64 indexed dayIndex, bytes32 taskPackHash);
```

索引器只认这些事件加上旧的 `PointsChanged`、`NameMinted`、`Transfer`。不要另做一条链下「已发放」作为余额或所有权的来源。

## 状态机：兑换

`OrderStatus`：

1. `None`：该 `.ai` 本季没有订单。
2. `apply` 成功 → `Pending`。名字键 `keccak256(abi.encodePacked(tld, label))` 被占用，季名额被占用，积分已扣。
3. 管理员 `attestFulfillment(orderId, mintTxHash)` → `Fulfilled`。这是项目声明，不是铸造回执的链上证明。函数没有 tokenId 参数。tokenId 只能由该订单的 label 和 tld 在合约内算出。
4. 没有 `Cancelled`。没有从 `Pending` 回到 `None` 的函数。当前 `ownerOf` 等于接收人**不能**把状态改成 `Fulfilled`。用户事后把名字转走，也不否定已经发生的铸造日志。网站是否显示「已发放」以 `08` 的日志核对为准。

当日计数：

- `Reserved` 成功一笔，`reservedFilled++`。它不占用 `remainingSlots`。
- `Boundary` 成功一笔，`boundaryFilled++`。`boundaryFilled == remainingSlots` 后，同组其他人 revert `BoundaryFull`。
- 严格高于边界分的人没有来，`remainingSlots` **不准**增加。
- `reservedFilled + boundaryFilled` 当天不得超过 20，全季所有 `Pending+Fulfilled` 不得超过 300。这是断言，不是递补池。

## 兑换 `apply`

```solidity
function applyFor(
    ApplyAuth calldata auth,
    bytes calldata signature,
    bytes32[] calldata proof
) external nonReentrant returns (uint256 orderId);
```

顺序必须是：先只读检查，再写本合约状态，再 `points.spend`，全程 `nonReentrant`。`spend` 若 revert，整笔回滚，锁和名额都不得留下。

检查：

1. `block.timestamp >= START_TS && block.timestamp < END_TS`。`END_TS` 只限制新的兑换申请。它不阻止赛季内已经 commit 的找错在截止后揭示和领奖，也不阻止事故债权在截止后处理。见 `05`、`06`、`12`。
2. `auth.dayIndex == block.timestamp / 86400`，且落在 `[20781, 20795]`。
3. `auth.deadline == (auth.dayIndex + 1) * 86400`。签名不能拖到下一天。
4. `auth.seasonId == 1`，`auth.price == 200`，`auth.root == dayMarkets[day].merkleRoot`，且当天 `opened`。
5. `auth.recipient != address(0)`。允许合约地址。
6. 标签长度 2，且全是 `0-9` 或全是 `a-z`。否则 `OutsidePool`。大写拒绝，模块不负责转小写。
7. `tld` 为 0 或 1。`tokenId = uint256(namehash)`，算法与 `HahaNamehash.namehash` 相同。
8. 该 `tokenId` 是否已铸造，只认 `isMinted(bytes32(tokenId))` 的返回值。`staticcall` 成功且返回恰好 32 字节：`true` 则 `NameTaken`，`false` 才是未铸造。调用失败、返回空、长度不对、解码不出布尔，一律 `NameCheckFailed`，申请终止，不得当成未铸造。不要把任意 revert 当成未铸造。若另走 `ownerOf`，只有 revert 数据严格等于选择器 `0x7e273289` 加上 `abi.encode(tokenId)` 且 tokenId 就是这一笔查询的 id，才可当未铸造；其它情况同样 `NameCheckFailed`。实现选 `isMinted` 这一条即可，它是 Registrar 自己的存在查询（第 182–184 行），未铸造时不 revert。
9. 模块内该名字未锁定。
10. `seasonOrderOf[auth.aiId] == 0`。
11. Merkle 证明见 `03`。叶里的 `aiId`、`balance`、`tier` 与 `auth` 一致，且 `balance >= 200`。
12. `tier == Boundary` 时 `boundaryFilled < remainingSlots`。`Reserved` 不看这个计数。
13. `msg.sender` 通过与旧合约相同的 `.ai` 三重核对，得到的 `aiId` 等于 `auth.aiId`。失败 `AiRequired`。这里**不**要求 `registrar.balanceOf(msg.sender) > 0` 之后才验签名；但 `spend` 会要求持有名字。不持有名字则整笔回滚。这是旧 Points 的行为，不是新门槛。
14. `auth.nonce == nonces[auth.aiId]`。
15. 签名见 `04`。恢复地址或 ERC-1271 必须是 `msg.sender`。不允许第二个人拿着签名代发。用户的 agent 使用 `.ai` 那个钱包。

然后：

1. `nonces[aiId]++`。
2. 写入 `Order`，状态 `Pending`，`orderId` 从 1 递增。
3. 占名字、占 `seasonOrderOf`。
4. 增加对应的 filled 计数。
5. `points.spend(msg.sender, 200, REASON_REDEEM)`。
6. 发 `Redeemed`。

`spend` 使用 `msg.sender` 的 `.ai`，不是 `recipient`。接收人可以没有 `.ai`。

## 确认铸成

链上函数给不出「这笔管理员交易确实铸给了该订单」的完整证明。历史日志不在合约状态里。当前所有者更不能代替历史：用户转走之后 `ownerOf` 不再是接收人，但发放曾经发生过；反过来，接收人后来又买到同名也不该由任意调用者指定一个 tokenId 来结单。

因此：

```solidity
function attestFulfillment(uint256 orderId, bytes32 mintTxHash) external;
function currentOwnerMatches(uint256 orderId) external view returns (bool);
```

`attestFulfillment` 仅管理员。订单必须是 `Pending`。`mintTxHash` 不得为 0。tokenId 由订单里的 label 和 tld 计算，与创建时写入的 `tokenId` 相等，调用者不能另传一个 tokenId。成功则状态改为 `Fulfilled`，记下 `mintTxHash`，发出 `FulfillmentAttested`（字段含订单算出的 tokenId 和接收人）。这表示管理员声明这一笔交易哈希是发放交易。它**不**验证该交易的日志。已是 `Fulfilled` 则返回，不改记录。

`currentOwnerMatches` 用上面的 `isMinted` / `ownerOf` 规则做只读。相等只说明**此刻**所有者是接收人。它不改状态，也不能单独当作网站上的「已发放」。

网站和索引器的发放凭证见 `08`：同一笔交易里，`NameMinted` 与 `Transfer(from = 0, to = 该订单接收人, tokenId = 该订单 namehash)` 同时出现。当前所有者与这条凭证不一致时，以日志为准，并在页面上分开显示。

管理员补发超时订单时，调用的仍是同一笔 `adminMint(label, tld, recipient)`，然后再 `attestFulfillment`。模块不因超时提供退款或重扣。异常扣分（错误 root、铸到错误地址、脚本误扣）没有自动结案函数，见 `03` 和 `10`。

## root

```solidity
function setDayRoot(
    uint64 dayIndex,
    bytes32 merkleRoot,
    uint64 snapshotBlock,
    bytes32 snapshotBlockHash,
    uint16 reservedCount,
    uint16 remainingSlots
) external;
```

仅管理员。要求：

- 该日还没有任何订单（`reservedFilled + boundaryFilled == 0`）。已有订单则 `RootFrozen`。
- `reservedCount + remainingSlots <= 20`。
- `reservedCount + remainingSlots > 0` 或显式允许空日（root 为 0、两个计数为 0）。空日之后不能再打开。
- `snapshotBlock` 必须是按 `03` 锁定的那一块：时间戳不晚于日界，且不存在时间戳仍不晚于日界的更大块号。只是「够深的更早块」则 revert。调用时 `block.number >= snapshotBlock + snapshotConfirmations`，否则 `SnapshotTooFresh`。深度不够就继续等，不要换块。
- 模块不验证 Merkle 是否诚实。错 root 是管理员能力，不是数学证明。公布后的复算见 `03`。有订单之后不能改。

## 每日验证与找错的入口

签名与流程在 `05`、`06`。这里只固定和 Points 的衔接。

```solidity
function claimVerification(VerifyAuth calldata auth, bytes calldata signature) external nonReentrant;
function commitFinding(bytes32 reportEvidenceHash, bytes32 salt) external;
function assignCanonical(bytes32 reportEvidenceHash, bytes32 canonicalRootCauseId) external;
function publishRuling(bytes32 reportEvidenceHash) external;
function claimFinding(FindingAuth calldata auth, bytes calldata signature) external nonReentrant;
```

`claimVerification`：

- 时间必须落在 `START_TS` 与 `END_TS` 之间，并且是该 `dayIndex` 当天。过日不补。
- 若 `verified[aiId][dayIndex]` 已真：直接 return，不再 `earn`，也不增加 nonce。
- 否则检查签名、任务包哈希、`generationOf(agentId) == auth.generation` 且 `generation >= 1`，以及 `auth.nonce`。
- 然后 `uint256 got = points.earn(ACTION_VERIFY, msg.sender, VERIFY_KEY)`。
- `got == 0` 则 `EarnNotPaid`，整笔回滚，不把 `verified` 写成真，也不消耗 key。
- `got == 30` 才写入、增加 nonce，并 `Verified`。

`commitFinding`：

- `reportEvidenceHash == 0` 或 `salt == 0` 则 `ZeroCommit`。
- 调用时做 `.ai` 三重核对。失败则整笔 revert，不记 commit。通过则把当时的 `aiId` 写入 commit 记录。之后失去 `.ai` 不能改这条记录的归属，也不能由后来才持有 `.ai` 的人领取。
- `commitHash = keccak256(abi.encode(block.chainid, address(this), SEASON_ID, aiId, reportEvidenceHash, salt))`。结果为 0 则 `ZeroCommit`。
- 同一 `commitHash` 只接受第一次。
- 事件 `FindingCommitted` 不写交易序号。优先权用这条日志在收据里的块号、交易序号、日志序号，由索引器重建。合约内另存 `block.number` 和 `committedAt = block.timestamp`，供 7 天揭示窗口对照。`committedAt` 必须早于 `END_TS`。

`assignCanonical` 仅找错签名人。把一份报告哈希指到复核后的根因 id。可以在发奖前改指向。不使已有用户签名失效，因为签名里没有根因 id。

`publishRuling` 仅当前找错签名人。报告必须已有 commit 和 `assignCanonical`，且 `block.timestamp <= committedAt + 7 days`。成功时写下 `publishedAt`。重复公示不改第一次的时间。

`claimFinding`：

- 用 `04` 的字段重算 `commitHash`，必须存在，且记录中的 `aiId` 等于 `auth.aiId`，且 `msg.sender` 现在仍通过该 `aiId` 的三重核对。
- `publishedAt != 0`，并且当前时间落在公示后的 24 小时到再加 7 天之间。不读 `END_TS`。
- `auth.nonce == nonces[aiId]`。`auth.deadline` 等于 `publishedAt + 24 hours + 7 days`。
- `reportEvidenceHash` 必须已经 `assignCanonical`。未指定则 `CanonicalUnassigned`。
- `canonicalClaimed[canonicalRootCauseId]` 已真则 `CanonicalUsed`。合并到已支付根因的另一份报告走这里，签名仍然验得过，只是不再发分。
- `got = points.earn(ACTION_FIND, msg.sender, canonicalRootCauseId)`。
- `got == 0` 则整笔 revert，不占 `canonicalClaimed`，也不增加 nonce。触顶可以稍后用同一签名重试。
- `got == 100` 才写入 `canonicalClaimed` 并 `nonces[aiId]++`。

链上不知道哪一份揭示是「充分证据」，也不知道谁是第一个有效揭示。它只核对哈希是否闭合、commit 是否更早存在、签名人是否签了这一份。谁的证据足够、谁赢得优先权，由项目复核写成签名和 `assignCanonical`。这是中心信任，不是链上自动裁判。

pending 的复核、commit 未领奖，都不得增加 `HahaPoints` 余额。余额只在 `earn` 成功时变。

## 管理员配置（部署后，逐笔签名）

不得由部署 EOA 以外的脚本「替管理员广播」，除非那笔交易确实由管理员地址签名。顺序见 `07`。

1. `points.setSpender(season1, true)`
2. `points.setSpenderBudget(season1, SpenderBudget(200, 4000))`。这是 20×200 的映射，主网仍须管理员自己签名，但不再等一次新的业务表决。
3. `points.setEarner(ACTION_VERIFY, EarnerConfig({ module: season1, points: 30, perUserDailyCap: 1, globalDailyPoints: 100000, keyMode: PerDay, requireName: true, enabled: true }))`
4. `points.setEarner(ACTION_FIND, EarnerConfig({ module: season1, points: 100, perUserDailyCap: 5, globalDailyPoints: 10000, keyMode: Lifetime, requireName: true, enabled: true }))`
5. `points.setEarner(ACTION_ACCIDENT, EarnerConfig({ module: season1, points: 100, perUserDailyCap: 50, globalDailyPoints: 10000, keyMode: Lifetime, requireName: false, enabled: true }))`

验证全网是 `100000`，不是 100 万，也不是 1000 万。`1000000` 和 `10000000` 都不要填。事故的 `50` 是旧字段硬顶，用来避免次数配额卡住第二张合法失败订单，不是一项新的「每天 50 次」业务规则。`uniqueKey` 仍是 `bytes32(orderId)`，每张订单只能成功补偿一次。

额度不足时 `earn` 返回 0，且第 415–421 行还没写 key。模块不得把验证、找错或事故补偿标成已领。用户以后用同一授权再试。这就是排队，不是丢奖。

`setRewardSigner` 的主网地址就是现有管理员。`setValidator` 的地址等服务器公布公钥后再写。撤掉 validator 或把 reward signer 设回 0 之后，旧签名立即失败。没有第二套隐藏设置函数。

`setEarner` 的 `points` 为 30 或 100，都在 1–100。`perUserDailyCap` 是次数，上限 50，不是「每天 50 分」。

不要把模块设成可以 `spend` 任意 `user` 的公开函数。唯一的 `spend` 路径是 `applyFor`。`refund` 只出现在下面「退款只走事故」一节。

## 读函数

```solidity
function seasonOrderOf(bytes32 aiId) external view returns (uint256);
function order(uint256 orderId) external view returns (Order memory);
function nameLock(uint8 tld, string calldata label) external view returns (uint256 orderId);
function dayMarket(uint64 dayIndex) external view returns (DayMarket memory);
function nonces(bytes32 aiId) external view returns (uint256);
function verified(bytes32 aiId, uint64 dayIndex) external view returns (bool);
function canonicalClaimed(bytes32 canonicalRootCauseId) external view returns (bool);
function canonicalOf(bytes32 reportEvidenceHash) external view returns (bytes32);
function commitOf(bytes32 commitHash) external view returns (bytes32 aiId, address committer, uint64 blockNumber, uint64 committedAt, uint64 publishedAt);
function accidentOf(uint256 orderId) external view returns (bool refunded, bool compensated);
```

## 截止、nonce、撤销、排队、防双领

`END_TS` 只进入两个检查：`applyFor`，以及 `claimVerification`。`commitFinding` 也必须在 `END_TS` 之前，因为它是赛季内的承诺。`publishRuling`、`claimFinding`、`declareAccident`、`claimAccidentCredit` 不读 `END_TS`。验收没通过时 `redeemOpen` 和 `rewardsOpen` 保持 false，这是另一道开关，不把日期往后推。

`rewardsOpen == false` 时拒绝新的 `claimVerification` 和 `claimFinding`。它不拒绝事故退分和事故补偿。管理员暂停日奖或找错，用撤掉对应签名人，或把该 action 的 `enabled` 设为 false。撤掉之后，恢复地址不再等于当前签名人，旧凭证立刻失败。没有宽限期。

nonce 只有一把：`nonces[aiId]`。`applyFor`、真正发出 30 的 `claimVerification`、真正发出 100 的 `claimFinding` 成功时才加一。幂等的第二次验证在加 nonce 之前返回。`earn` 返回 0 时整笔领奖 revert，nonce、`verified`、`canonicalClaimed` 都保持原样，同一张签名可以再交。这就是排队，而且不消耗 Points 的去重 key。旧 `earn` 在第 415–421 行写 key 之前就返回 0。

找错时间由链上时间戳执行，不再另加「至少 1 个块」：

- `commitFinding` 记下 `committedAt = block.timestamp`，并要求它 `< END_TS`。
- `publishRuling(bytes32 reportEvidenceHash)` 仅当前找错签名人。要求已经 `assignCanonical`，且 `block.timestamp <= committedAt + 7 days`。成功时 `publishedAt = block.timestamp`。过了 7 天不得公示、不得发奖。
- `claimFinding` 要求 `publishedAt != 0`，`block.timestamp >= publishedAt + 24 hours`，并且 `block.timestamp < publishedAt + 24 hours + 7 days`。签名里的 `deadline` 必须等于 `publishedAt + 24 hours + 7 days`。公示 24 小时已经使领奖晚于 commit 所在块。

敏感正文可以先私下交给复核人，修复后再公开。链上只存证据哈希和上述时间，不因此多加等待天数。

## 退款只走事故，且不能双领、双发

本模块没有公开的 `refund(user, amount)`。唯一调用旧 `points.refund` 的地方是 `declareAccident` 和 `claimAccidentCredit`，金额固定 200，reason 固定 `SEASON1_REDEEM`，`user` 固定为该订单原来的 `applicant`。

- 订单不是 `Pending`，或已经 `Fulfilled`，不能宣布事故。
- 宣布前必须确认该 namehash 没有铸出，也没有在途 `adminMint`。否则 revert，名字锁保持。
- 原地址当时能通过原 `aiId` 的三重核对：同一笔里先 `refund`。`refund` revert 则整笔 revert，订单仍是 `Pending`，没有解锁。`refund` 成功后订单进入 `AccidentRefunded`，解开名字锁，再尝试 `earn` 100。`earn` 返回 0 不回滚退分，补偿保持未领。
- 当时不能通过三重核对：不调用 `refund`，不把 200 转给别人。订单进入 `CreditOpen`，债权留在原 `aiId` 和原 `applicant`。可以解锁名字，因为已经确认没铸出。
- `claimAccidentCredit` 只接受原 `applicant` 且此刻 `aiId` 仍核对为这个人。`CreditOpen` 时先退再补。`AccidentRefunded` 时只补 100，禁止第二次 `refund`。`earn` 返回 100 后进入 `AccidentClosed`。再次调用 revert。
- 补偿的 Points key 是 `bytes32(orderId)`，`Lifetime`。模块在调用前先看本订单的 `compensated`。两道都在，避免双领。
- `attestFulfillment` 只接受 `Pending`。事故状态不能被声明成已发放。Registrar 对已存在的 token 拒绝第二次 `adminMint`。索引器对同一 `orderId` 只认一次 `spend`。退分之后若迟到收据证明已经铸给原接收人：不再铸、不再退，页面同时显示两边事实。
- `seasonOrderOf[aiId]` 只在这 200 已经退回之后清掉。`CreditOpen` 期间不清，避免债权未结就再占一个季名额。`reservedFilled` 和 `boundaryFilled` 不减少，当天的空槽不递补。名字锁在确认未铸出、且没有在途 `adminMint` 之后解开。

`spend` 路径仍然只有 `applyFor`。同一 `orderId` 不会第二次扣 200。

这些是索引器和复算的链上对照，不能替代事件。

## 暂停

不给旧合约加暂停。本模块可以有 `bool public redeemOpen` 与 `bool public rewardsOpen`，仅管理员能改。`redeemOpen = false` 只阻止新的 `applyFor`。`rewardsOpen = false` 只阻止新的 `claimVerification` 和 `claimFinding`。两者都不阻止 `declareAccident` 和 `claimAccidentCredit`。已经 `Pending` 的订单仍可由管理员 `attestFulfillment`，管理员仍可逐笔 `adminMint`。不要做「暂停后清空订单」。默认部署时两者都为 `false`。验收门在开季时刻前没过，就保持关闭。日期不因此顺延。这是本模块的开关，不是旧合约的升级。
