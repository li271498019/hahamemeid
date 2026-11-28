# haha.meme 合约实现：开工前的文档疑问

状态：**已裁决，D 已开工**。日期：2026-11-20。编写：D。

> **裁决摘要（owner，2026-11-20）**
> - 第 1、2、3 条：按 D 的建议执行。
> - 第 4 条：加限额。`refund` 只能退「该用户在同一 `reason` 下累计 `spend` 过、且尚未退回」的额度，新增 `spendable` mapping，超额直接 revert。
> - 第 5、6、7、8、9、10、11 条：按 D 的默认执行。
> - 全部决定已写进 `docs/CHANGELOG.md` 的「2026-11-20 开工前裁决」一节。

规格 `SPEC.md` 已通读，所有可独立复核的事实我都复核过（见文末「已复核通过」）。下面 11 条是**规格内部互相矛盾、或没有答案但我必须写代码**的地方。按 README 的要求，我不自己定规则，先提出来。

标记：**[矛盾]** = 两处文档说法不一致，必须选一个；**[缺失]** = 规格没写，需要一个答案；**[建议]** = 我倾向的答案，可以直接采纳。

---

## 1. [矛盾] `HahaNamePolicy` 部署后冻结，但 Registrar 部署时就要它的地址

- `SPEC 5.4`：两套哈希走**构造参数**写进 mapping（不用 Merkle，理由是"一个参数就铸造"）。
- `SPEC 6.1`：`constructor(bytes32[] bannedHashes, bytes32[] reservedLabelhashes)`，跑完即冻结。
- `SPEC 13.2`：Registry / Registrar / Resolver / Identity / Points 之间用 CREATE2 **事先算好地址**，工厂构造函数只保存地址，不在对方还没部署时回调它。
- `SPEC 13.1`：先有 Policy 和 Metadata。

冲突点：Policy 的地址只有在**真的部署完**（哈希已经写进 storage）之后才固定。如果 Registrar 也要用 CREATE2 预计算，那么工厂的 init code 里必须同时包含 208+61 个哈希（约 8.6 KB，`HahaDeployer` 自己的 init code 会更长）。而 `SPEC 5.4` 说"哈希放在构造参数和 init code 里"，这两句话放一起时，**Policy 的 init code 里有一份、工厂的 init code 里还有一份**。

更麻烦的是 Registrar 需要 `policy` 作为 immutable：如果 Policy 不是预计算的，Registrar 的 immutable 就没有值可填。

**建议**：只对「互相回调」的五个合约（Registry / Registrar / Resolver / Identity / Points）做 CREATE2 预计算，Policy 和 Metadata 在工厂里**先实际部署、再把地址传给后续合约**。理由：这两者不依赖任何业务合约，也没有人会回调它们，Policy 部署完才拿到地址不产生任何时序问题。这样哈希数组在 init code 里只出现一次（Policy 自己的），工厂 init code 也不会逼近 49152 字节的 EIP-3860 上限。

**裁决：采纳。** Policy 与 Metadata 顺序部署取地址，其余五个合约 CREATE2 预计算。见 CHANGELOG「部署时序」。

## 2. [矛盾] 工厂能不能把「部署完的地址」传给后面部署的合约

`SPEC 13.2` 说"构造函数只保存地址，不在对方还没部署时回调它"。这句话严格读的话，工厂在构造函数里**根本不能部署任何合约**（部署=拿到地址=可以回调）。但 13.1 又要求"先有 HahaNamePolicy、HahaMetadata"。

**建议**：13.2 的约束解释为「**业务合约之间**不允许在对方未部署时互相调用」，工厂自身按顺序部署、把已部署好的地址传给下一个合约，是允许的。否则整条部署链无法成立。

**裁决：采纳。** 13.2 解释为「业务合约之间不得在对方未就绪时互相调用」，工厂自身顺序部署允许。见 CHANGELOG「部署时序」。

## 3. [缺失] 工厂部署结束后的 write 权限，具体断在哪一条

`SPEC 13.5`：工厂"部署结束后不保留写函数，可以留下只读的地址 getter"。`SPEC 12` 又要求测试"工厂没有成功的写调用"。

但没有写：构造函数**自己**执行的那几笔 `bootstrap()` / 各合约之间的 setter 算不算"成功的写调用"？测试要怎么断言？

**建议**：工厂**自身不暴露任何外部写函数**（除了 constructor）；工厂内部部署过程中对其他合约的调用不算在内。工厂上没有任何 `function xx(...) external` 是 non-view 的。测试断言方式：用 `vm.getCode` 反查工厂 ABI 里每个外部函数都是 `view`，再加一笔 eth_call 级别的分类测试。

**裁决：采纳。** 工厂无外部写函数，仅 constructor 内部调用；测试枚举 ABI 全为 `view`。见 CHANGELOG「工厂写权限」。

## 4. [缺失] `HahaDeployer` 的构造函数参数里，那两个哈希数组从哪来

`SPEC 13`：构造参数是 `admin`、`feeReceiver`、`aiRegistry`、黑名单哈希、保留名哈希。也就是 208+61 个 `bytes32` 要作为**工厂的构造参数**传进去。

同时 `SPEC 5.4` 说"哈希放在构造参数和 init code 里，不留在运行时字节码里"。

问题：`HahaDeployer` 的 init code = 208+61 个 param 的 ABI decode + 部署 Policy 的 init code + 部署其余合约的 init code。这个总长度需要实测。如果超 49152，按 `SPEC 5.4` 的说法要"改成先部署 Policy 再把地址传给工厂"，但这又和 13 的"构造参数含哈希"冲突。

**建议**：先让我实现并实测 init code 大小。若超限，采用 `SPEC 5.4` 给的备选方案（Policy 先单独部署，工厂接收 Policy 地址 + 校验其状态），并在 CHANGELOG 里记这一条变更。这一条我**建议你先在文档里预埋这个允许**，免得我实测后又要来回一轮。

owner 的回复针对第 8 条，这里的 init code 体积问题由第 1 条的方案顺带解决：哈希只在 Policy 的 init code 里出现一次，工厂 init code 不含哈希数组。

**结论**：`HahaDeployer` 构造函数仍接收 `bytes32[] bannedHashes, bytes32[] reservedLabelhashes`（这是 `SPEC 13` 的接口约定，部署脚本必须现场计算并与 `.hashes.txt` 逐行比对），但它只把数组**透传给 `HahaNamePolicy` 的 constructor**，自己不留存。实测 init code 大小写进测试（`DeployInitCodeSize.t.sol`），超 49152 就让测试失败。

## 5. [矛盾] `NameMinted` 里 `aiId` 是 `indexed`，但管理员铸造时是 `bytes32(0)`

`SPEC 6.3` 的事件定义：`aiId` 是第三个 `indexed` 参数。而管理员铸造时 `aiId = bytes32(0)`。

这不是矛盾，是**索引器的问题**：所有保留名铸造都会落到同一个 `aiId = 0` 的分区里。索引器按 `aiId` 查「这个人的铸造历史」时，会把 61 个保留名全部混在一起。

**建议**：保持事件签名不变（你已批准），但我在 `docs/` 里加一句话给索引器实现方：「`aiId == 0` 且 `reservedMint == true` 的行不代表任何身份，索引器不要按 `aiId` 聚合这些行」。不改代码。

**裁决：采纳，不改代码。** 已在 `docs/contracts/INDEXING.md` 写明索引器注意事项。

## 6. [缺失] `available()` 的语义边界

`SPEC 6.3`：`available` 为「字符集合法、长度 1–32、且该 node 尚未铸造」，**不判断黑名单和保留名**。但同一段又说 `register` 要求长度 ≥ 3。

问题：`available("xi", 0)` 会返回 `true`（字符集合法、长度 2 在 1–32 内、没被铸过），但公众 `register("xi", 0)` 会 revert `LabelTooShort`。网站如果直接用 `available` 判断「能不能注册」，会给出错误答案。

**建议**：`available` 保持规格定义（管理员视角：这个名字还能不能被铸出来），我在 NatSpec 里明确写"公众可注册性请用 `available && !policy.isBlacklisted && !policy.isReserved && len >= 3`"，并在 CHANGELOG 补一条给前端看的说明。不改行为。

**裁决：采纳，不改行为。** `available()` 保持规格定义，NatSpec 写明公众可注册性要叠加 policy 与长度判断。

## 7. [缺失] `setPointParams` 和 `setSpender` 没有事件以外的可观测性要求

`SPEC 6.8` 要求 `setSpender(account, true)` 时 `account` 必须有代码。但没写：**取消授权**（`allowed == false`）时要不要检查代码？如果一个合约被 selfdestruct 了，管理员还能不能取消它的授权？

**建议**：只在 `allowed == true` 时检查 `account.code.length > 0`；`false` 时不检查，永远可以取消。理由：取消授权必须是**无条件可用**的安全阀，否则管理员会被卡住。错误名沿用 `ZeroAddress` 之外新增一个 `NotAContract`？规格没定错误名——我用 `NotAContract`，需要你确认是否接受新增一个 error 名。

**裁决：采纳。** 新增 error `NotAContract`；`setSpender(account, false)` 不检查代码，取消授权无条件放行。见 CHANGELOG「新增 error 名」。

## 8. [缺失] `spend` / `refund` 的 `user` 与调用者的关系，以及 `refund` 能不能超额

`SPEC 6.8`：`refund`「调用者是已授权 spender，`amount > 0`，用户当前仍有 `.ai`」。没说能不能把余额退到超过原值（即凭空造分）。

**建议**：`refund` 只做加法，不设上限。理由：`refund` 是 `spend` 的逆向操作，额度控制是 spender 合约的责任（拍卖合约自己记账）。但这是一条**造分通道**：被授权的合约可以把任意地址的积分刷到无穷大。规格第 8 节已经写"这是管理员钥匙最大的风险点"，所以我按规格不加限制，只在审计报告里再标一次。

**需要你确认**：接受「授权 spender 可以无限造分」，还是要求 `refund` 只能退「该 `reason` 下曾经 spend 过的额度」？后者需要一个新 mapping，规格里没有。

**裁决：owner 要求加限额，规格据此修改。**
- 新增 `mapping(bytes32 aiId => mapping(bytes32 reason => uint256)) spendable`。
- `spend` 成功 → `spendable[aiId][reason] += amount`。
- `refund` 要求 `amount <= spendable[aiId][reason]`，否则 revert `RefundExceedsSpendable(uint256 requested, uint256 available)`；成功 → `-=`。
- 新增只读 `spendableOf(bytes32 aiId, bytes32 reason)`。
- 效果：spender 退还总额永远不超过它在同一 `reason` 下真实扣掉的总额，无法凭空造分。

## 9. [矛盾] ERC-2981 的 `royaltyInfo` 对不存在的 token 也要返回

`SPEC 6.3`：`royaltyInfo` 对任何 tokenId 都返回 `(feeReceiver, salePrice * 100 / 10000)`，不 revert。这条没问题。

但 `SPEC 12` 又要求"`royaltyInfo(tokenId, 1 ether)` 等于 `(feeReceiver, 0.01 ether)`"。`1 ether * 100 / 10000 = 0.01 ether`，**整数除法正好整除**，所以对。

真正的坑在别处：`fee = price * 100 / 10000` 向 0 取整，`price = 99` 时 `fee = 0`。市场要求 `fee > 0` 所以拒绝 99 wei——但 `royaltyInfo(99)` 会返回 `0.0099 → 0`，而 ERC-2981 规范没说必须 > 0。**不冲突，只是记录**。

**建议**：不改代码。测试里明确断言 `royaltyInfo(id, 99) == (feeReceiver, 0)`。

**裁决：不改代码。** 测试断言 `royaltyInfo(id, 99) == (feeReceiver, 0)`。

## 10. [缺失] `HahaResolver.setPrimaryName` 的「一个 node 最多被一个地址当主名字」

`SPEC 6.4`：「设置新的会替换旧的，并维护 `primaryHolder[node]`，保证一个 node 最多被一个地址当作主名字」。

问题：如果 A 把 `abc.haha` 设为主名字，然后 A **把 `addr(node)` 改成 B**，那么 `addr(node) == B != primaryHolder[node] == A`，按 6.4「`setAddr` 之后若 `addr(node)` 不再等于 `primaryHolder[node]`，清掉那个人的主名字」——A 的主名字被清，`primaryHolder[node]` 变成 0。此时 B 能设主名字吗？`addr(node) == B == msg.sender`，可以。

**这条其实自洽**，但没说 `primaryHolder` 在 A 被清掉时要归零。**建议**：清掉 A 的同时 `delete primaryHolder[node]`，否则 `primaryHolder[node]` 悬空，将来有人设主名字时误判「已被占用」。

**裁决：采纳。** 清掉主名字的同时 `delete primaryHolder[node]`，不留悬空占用。

## 11. [缺失] fork 测试的区块号

`SPEC 4` 记录核实区块 `134683411`，`SPEC 12` 要求「固定一个区块，并把 `.ai` 运行时字节码哈希写进测试」。

问题：**那个区块的归档状态可能拿不到**。我今天（2026-11-20 19:5x）实测 `134683411` 在 `bsc-dataseed` 上 `eth_getCode` 仍是同一份字节码（8756 字节，哈希一致），但**存储槽**（alice 的 owner 映射）在非归档节点上可能读不到。归档节点通常要付费 RPC。

**建议**：fork 测试分两层：
- **离线层**（必跑，CI 里跑）：把 `134683411` 的 `.ai` 合约代码 + 三个地址的 storage 槽（alice 持有者、binance 持有者、`.ai` owner/signer）用 `vm.etch` / `vm.store` 冻结进测试，不需要联网。字节码哈希写死断言。
- **在线层**（本地跑，可选）：`--fork-url` 跑真实 RPC，逐条对 4 节的 eth_call 结果。

这样「固定区块、哈希写进测试」的要求被满足，又不会因为 RPC 是付费归档节点而没法跑测试。

**裁决：采纳两层方案。**
- 离线层（CI 必跑）：把锁定区块的 `.ai` 代码与三个地址的 storage 槽冻结进 `test/fork/state/`，用 `vm.etch` / `vm.store` 还原，不联网。字节码哈希写死断言。
- 在线层（本地可选）：`--fork-url` 跑真实 RPC，逐条对第 4 节的 `eth_call` 结果。
- 锁定区块与冻结文件哈希记在 `test/fork/FROZEN.md`。

---

## 已复核通过（无异议）

我用独立脚本（纯 Python keccak，不依赖 forge）复核了：

| 项 | 结果 |
| --- | --- |
| 黑名单 208 个词，md 与 `blacklist-v2.hashes.txt` 词集完全一致 | 通过 |
| 208 个加盐哈希逐条 | 全部匹配 |
| 208 个哈希首尾相接的聚合 keccak | `0xb9bda222…41e1` 一致 |
| `trump` 单条向量 | 一致 |
| 保留名 61 个，md 与 `reserved-names.hashes.txt` 一致 | 通过 |
| 61 个 labelhash 逐条 | 全部匹配 |
| 两名单无交集 | 通过 |
| `hahaNode` / `memeNode` / `node("abc.haha")` / `node("abc.meme")` / `keccak256("abc")` | 5 个向量全部一致 |
| `alice` 的 tokenId 十进制 | 一致 |
| 四个 `*.svgpart` 字节数与 SHA-256 | 全部一致 |
| 三张样例 SVG 由四段常量拼装后逐字节一致 | 通过 |
| 字号/基线表 5 行（含 `n=24` 半偶数→260） | 全部一致 |
| `.ai` 运行时字节码 8756 字节、keccak | `0xc4006e6e…6ace` 一致 |
| `.ai` `alice` 闭环（owner / handleOf / ownerOfHandle / balanceOf） | 通过 |
| `.ai` `ownerOfHandle("Alice")` / `("alice.ai")` / `("")` | 均为 0 |
| `.ai` `supportsInterface` 五种 | 与 4 节表格一致 |
| `.ai` dispatcher 含 `adminRegister`、无 `burn`/`upgradeTo`/`proxiableUUID` | 一致 |

**没有发现文档事实性错误。** 上面 11 条全是「规格内部两句话需要对齐」或「没写但必须选一个」的问题。

## 裁决执行记录

| # | 问题 | 裁决 | 落实位置 |
| --- | --- | --- | --- |
| 1 | Policy 地址与 CREATE2 预计算冲突 | 按建议：Policy/Metadata 顺序部署 | CHANGELOG「部署时序」 |
| 2 | 工厂能否在 constructor 内部署 | 按建议：业务合约之间才禁止 | CHANGELOG「部署时序」 |
| 3 | 工厂写权限边界 | 按建议：工厂无外部写函数 | CHANGELOG「工厂写权限」 |
| 4 | init code 体积与哈希来源 | 哈希透传 Policy，实测 init code | `test/DeployInitCodeSize.t.sol` |
| 5 | `aiId == 0` 的索引器歧义 | 不改代码，补索引文档 | `docs/contracts/INDEXING.md` |
| 6 | `available()` 边界 | 不改行为，补 NatSpec | `HahaRegistrar.available` |
| 7 | 取消授权是否检查代码 | 新增 `NotAContract`，取消不检查 | CHANGELOG「新增 error 名」 |
| 8 | `refund` 无限造分 | **加限额**：`spendable` mapping | CHANGELOG「refund 限额」 |
| 9 | `royaltyInfo` 小额取整 | 不改，测试断言 0 | 单元测试 |
| 10 | `primaryHolder` 悬空 | 清理时一并 delete | `HahaResolver` |
| 11 | fork 区块可获取性 | 两层：离线冻结 + 在线可选 | `test/fork/` |

---

## 我需要你回复的（已全部回复）

以下为原始提问，保留备查。owner 已于 2026-11-20 全部裁决，见上方「裁决摘要」与「裁决执行记录」。

1. **第 1、2、4 条** —— 部署时序。这三条不定，我写不了 `HahaDeployer`。我的建议是：Policy / Metadata 顺序部署取地址，其余五个 CREATE2 预计算，工厂自身无外部写函数。
2. **第 7 条** —— 新增 error 名 `NotAContract` 是否接受（或者你给一个名字）。
3. **第 8 条** —— 授权 spender 可无限 `refund` 造分，接受还是要求限额。
4. **第 11 条** —— fork 测试走「离线冻结 + 可选在线」两层，是否接受。
5. **第 5、6、10 条** —— 只要求我在文档/NatSpec 里补说明，不改行为，默认我这么做，你不反对就跳过。

你回复 1、2、3、4 之后我立刻开工写代码。第 5、6、10 条我按建议默认执行。
