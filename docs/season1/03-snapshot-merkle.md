# 03 快照、Merkle、资格

算法版本：`haha-season1-merkle-v2`（2026-11-25 第 20782 天起生效）。v1（2026-11-24 第 20781 天）没有轮换规则；v2 增加“过期排除、顺延、随机补位”（见“分组”）。叶与树的哈希规则、Manifest 格式不变。

## 日界

窗口 `D` 的 `dayIndex = D`。申请时间是 `[D * 86400, (D+1) * 86400)`。边界时刻 `boundaryTs = D * 86400`。

选块分两步，顺序不能反：

1. 在**当前主链**上，找出时间戳 `<= boundaryTs` 的块号最大的那一块，记为 `B`。这一步只看时间戳，不看确认深度。
2. 若公布 root 时 `block.number < B + snapshotConfirmations`，则还不能 `setDayRoot`，也不能打开当天申请。等到 `B` 自己达到深度再用 `B`。不得改选更早的、已经够深的块来凑数。

`B` 的块哈希必须与 `setDayRoot` 传入的 `snapshotBlockHash` 一致。传入一个更早的块，即使它更「安全」，也要 revert。

root 写入之前如果主链重组，按同一条规则重新找 `B`。不要保留旧的 `B` 只因为它当时已经够深。

这才是「日界前最后一块，并且这一块已经确认」。不要用网站服务器看见 0 点的本地时间。

`snapshotConfirmations` 的生产值已批准为 15。索引器自己的重组深度仍是 3，不能拿来替换这 15，也不能因此改选更早的块。

## 余额怎么来

对快照块及之前的全部 `PointsChanged` 重放。每个 `aiId` 取最后一条的 `newBalance`。不要用领奖当时的网站缓存，不要用 `statusOf` 的「现在」。

重放范围从 Points 部署块 `134834780` 到快照块。`aiId == bytes32(0)` 的事件丢弃。

本季订单：

- `Pending`、`Fulfilled` 或 `CreditOpen` 的 `aiId` 从资格里删除，即使余额仍 `>= 200`。pending 跨日继续排除，直到赛季结束。他们的 200 已经扣过，排除是资格规则，不只是余额变小。
- 只存在于内存、还没上链的「打算申请」不是 pending。

轮换规则（v2，2026-11-25 第 20782 天起生效）：

- 上一天有资格却没申请的人（在上一天快照 `entries` 里、且无订单），当天从快照名单里排除。名额顺延给后面满 200 分的人，优先后面满 200 分的人。
- 如果后面满 200 分的人不够 20 个，前面被排除的人有机会随机补位到 20 人。随机补位用当天快照区块哈希当种子，公开可验证：任何人用同一块哈希、同一余额表重算，得到的补位名单相同。
- 每天名额仍是 20 个，全季 300 个不变。

## 分组

设过滤后的集合为 `E`（余额 `>= 200`、无 `Pending` / `Fulfilled` / `CreditOpen` 订单）。把 `E` 分成两组：

- 新鲜组 `F`：不在上一天快照 `entries` 里的人（从没进过快照，或之前进过但已申请过——后者已被订单排除，不会在 `E` 里）。
- 过期组 `X`：在上一天快照 `entries` 里、且无订单的人（上一天有资格却没申请）。

优先新鲜组。按 `balance` 降序排列（同分按 `aiId` 升序）。排序只用于找分界，不用于把边界组里的人预先排成前 20。

- 若 `|F| >= 20`：只在 `F` 里分组，过期组 `X` 当天不进树。
  - 令 `cutoff` 为 `F` 按余额降序的第 20 人的余额。
  - `balance > cutoff` 的人是 `Reserved`。人数记为 `reservedCount`。他们的槽保留。
  - `balance == cutoff` 的人是 `Boundary`。
  - `remainingSlots = 20 - reservedCount`。边界组只抢这几个槽，先成功上链的 `applyFor` 获得，同块内 log index 较小者优先。这是链上顺序，不是后台到达时间。
  - `balance < cutoff` 的人不进树。
- 若 `|F| < 20`：`F` 全体是 `Reserved`。再从过期组 `X` 里随机补位到 20 人（`X` 不足时全补，仍不到 20 就按实际人数）。随机补位用当天快照区块哈希当种子（确定性伪随机，同一输入两次结果相同），补位的人也是 `Reserved`。`remainingSlots = 0`。

全员同分时 `reservedCount = 0`，`remainingSlots = 20`，所有人抢 20。这和「全体再抽签」不同：没有随机，只有交易顺序。随机只用在过期组补位那一步。

第 20 人的分数若与第 21 人不同，则第 20 人自己构成一个大小为 1 的边界组，`remainingSlots` 至少为 1，他申请就能成功。效果和保留槽一样。

v1（第 20781 天）没有轮换：`|E| <= 20` 时全体 `Reserved`、`remainingSlots = 0`，没来的人不递补。v2 起，上一天有资格没申请的人被排除、由后面的人递补，不再出现“前 20 名一直占位不申请、后面的人永远进不来”。

## 叶与树

使用仓库里 OpenZeppelin v5.1.0 的 `MerkleProof.verify`。配对哈希是排序后的 `commutativeKeccak256`（`MerkleProof.sol` 的 multiproof 路径使用 `Hashes.commutativeKeccak256`）。D 必须用同一个 `verify(proof, root, leaf)` 实现，并在测试里用一份链下脚本生成证明，链上验证通过。不要自造未排序的二叉树。

```text
leaf = keccak256(bytes.concat(keccak256(abi.encode(aiId, balance, uint8(tier)))))
```

`abi.encode` 三个字段，不要 `encodePacked`，避免 `aiId` 和余额粘连。

内部节点：与 OZ 相同，`a < b` 时 `keccak256(abi.encodePacked(a, b))`，否则对调。证明由链下按这个规则生成。

空集合：`merkleRoot = bytes32(0)`，`reservedCount = 0`，`remainingSlots = 0`。模块拒绝任何 `applyFor`。不要把「空证明返回 proof[0]」当成有资格。

## Manifest

每个窗口一份 JSON，上线前公开，字段顺序固定，UTF-8，无多余空白。`task` 与找错无关。

```json
{
  "seasonId": 1,
  "dayIndex": 20781,
  "boundaryTs": 1795478400,
  "snapshotBlock": 0,
  "snapshotBlockHash": "0x",
  "points": "0xB2D023b8B5895835EFD71C1150BeAD7bD735DfAa",
  "module": "0x",
  "reservedCount": 0,
  "remainingSlots": 0,
  "root": "0x",
  "entries": [
    {"aiId": "0x", "balance": "0", "tier": 0}
  ]
}
```

`entries` 按 `aiId` 字节升序，便于 diff。`balance` 用十进制字符串。`tier` 0 保留，1 边界。

文件哈希：`keccak256(manifest 字节)`。模块**不**存储这个文件哈希，避免管理员用链上哈希代替复算。网站同时显示：

- 管理员 `setDayRoot` 的 root、块号、块哈希。
- 任何人用公开脚本从该块重放得到的 root。

两者不一致时，网站不得放出申请指令。模块仍然可能接受针对错误 root 的证明。这不是「管理员 root 等于真相」。有订单之后 `setDayRoot` 必须失败，所以错误 root 若已有人申请，立刻关掉 `redeemOpen`，公开两边的 root、快照块和已扣分的 `orderId`。这不是用户成功后的取消，也不是管理员超时。不要在没有 `declareAccident` 时自动 `refund`。若 L 把它裁定成无法履约的事故，走 `12`：退 200、另补 100，并先排除已铸和在途铸造。决定之前不得再开当天或下一天的申请。

## 重组

公布 root 之前发现快照块被重组：重新选块，重新公布，此时还没有订单。

公布之后、尚无订单：允许再 `setDayRoot` 一次覆盖。事件以最后一条 `DayRootSet` 为准。

已有 `Redeemed`：禁止换根。若重组导致重放余额与叶不一致，停 `redeemOpen`。已经扣掉的 200 先保持 pending，凭据留在事件里。这不属于「用户成功后不许取消」，也不属于「管理员超时只补发」。只有按 `12` 宣布事故才退，本规格不因为重组自动退。

索引器确认深度与 `snapshotConfirmations` 可以不同。索引器继续用它自己的 3。快照脚本用模块里的构造值。不要混用两个深度还声称是同一块。

## 复算脚本的验收

提交人A 做工具，D 的 Foundry 测试用同一组向量。

输入：RPC 或导出的 `PointsChanged` 日志、模块订单事件、块头。输出：manifest 与 root。

断言：

- 同一输入两次，root 相同。
- 插入一条快照块之后的 `PointsChanged`，root 不变。
- pending 的 `aiId` 不在 `entries`。
- 余额 199 不在 `entries`。
- 构造 `03` 里的 18 个高分加 10 个同分：`reservedCount == 18`，`remainingSlots == 2`，10 个边界叶的 tier 为 1。
- 25 个完全同分：`reservedCount == 0`，`remainingSlots == 20`。

v2 追加断言（从第 20782 天起）：

- 上一天在 `entries` 里、无订单的人，不在当天 `entries` 里（除非被随机补位选中）。
- 后面满 200 分的人按余额降序顺延进 `entries`，优先于过期组。
- 后面满 200 分的人不够 20 个时，`entries` 补到 20 人（过期组不足时按实际人数），补位的人 tier 为 0。
- 同一快照块哈希、同一余额表，两次重算 root 相同（随机补位是确定性的）。
