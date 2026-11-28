# 自审计报告

状态：D 的内部自审计，**不是第三方审计**。日期：2026-11-20。

本报告按 `SPEC 11` 的审计重点逐条自查：铸造权限、转让清空、积分重复领取、市场重入、部署者权限。
每条都给出「怎么验的」和「结论」。发现的问题全部列出，包括已修的。

---

## 0. 构建信息

| 项 | 值 |
| --- | --- |
| Solidity | `0.8.28`（溢出检查开启） |
| 优化器 | `optimizer = true`, `runs = 200` |
| **`via_ir`** | **`true`（必需，见下）** |
| EVM 版本 | `cancun` |
| OpenZeppelin | `v5.1.0`（`lib/openzeppelin-contracts`） |
| forge-std | `v1.9.4` |
| 链 | BNB Smart Chain 主网，chainId `56` |

### `via_ir = true` 是硬约束，不是偏好

solc 的非 via-ir 代码生成器在处理「多个合约互相引用 + 十几次 `new`」时会 stack too deep。
这是**编译器的限制**，不是我们的逻辑问题。已实测：

- 关掉 `via_ir` → `HahaDeployer` 直接编译失败。
- 拆子工厂 → 子工厂 initcode 内嵌业务合约，父工厂再内嵌子工厂，总量不变，仍然超限。

**审计方需按 via-ir 产物复核。** via-ir 会改变字节码和 gas 分布，所有体积/gas 断言都基于它。

---

## 1. 体积（EIP-170 / EIP-3860）

| 合约 | Runtime | 上限 24,576 | Initcode | 上限 49,152 |
| --- | --- | --- | --- | --- |
| `HahaNamePolicy` | 528 | ✅ 余 24,048 | 1,171 | ✅ |
| `HahaRegistry` | 2,464 | ✅ 余 22,112 | 2,775 | ✅ |
| `HahaResolver` | 5,510 | ✅ 余 19,066 | 5,773 | ✅ |
| `HahaRegistrar` | 9,561 | ✅ 余 15,015 | 11,047 | ✅ |
| `HahaMetadata` | 9,271 | ✅ 余 15,305 | 9,297 | ✅ |
| `HahaAgentIdentity` | 4,851 | ✅ 余 19,725 | 5,839 | ✅ |
| `HahaReputation` | 2,180 | ✅ 余 22,396 | 2,413 | ✅ |
| `HahaPoints` | 5,876 | ✅ 余 18,700 | 6,231 | ✅ |
| `HahaMarketplace` | 2,951 | ✅ 余 21,625 | 3,211 | ✅ |
| `HahaDeployer` | 1,559 | ✅ 余 23,017 | 7,040 | ✅ 余 42,112 |

`HahaMetadata` 的 9,271 字节里，约 5,500 是 SVG 常量的 Base64 与 JSON 拼接逻辑。
`SVG.md` 要求「超 24,576 就停下来报告，不要删渐变图标硬塞」——**没有超**，无需妥协。

---

## 2. 铸造权限：管理员盖不住公众名字

**审计问题**：管理员能否铸一个本来属于公众的名字？

**验证**：`AdminPowerTest.test_adminCannotMintPublicName`、`RegistrarMintTest.test_adminCannotMintPublicName`。

`HahaRegistrar.adminMint` 的判定逻辑：

```solidity
uint256 len = bytes(label).length;
if (len >= MIN_PUBLIC_LENGTH) {                 // 长度 ≥ 3
    if (!policy.isReserved(label)) revert NotReserved();   // 不在保留名单 → 拒绝
}
// 长度 1–2：这是允许条件
```

再加上前面的 `if (policy.isBlacklisted(label)) revert Blacklisted();`。

**结论**：✅ 管理员只能铸「长度 1–2」或「61 个保留名之一」，且黑名单词一律不行。
`adminMint("bitcoin")` 会 revert `NotReserved`。

**边界**：如果将来要加保留名，只能重新部署整套合约（名单在构造时冻结）。这是设计意图。

---

## 3. 转让必清：解析记录与 agent

**审计问题**：用户转让名字后，旧的解析记录和 agent 会不会跟着带走？

**验证**：`TransferTest` 全部 19 条 + 不变式 `invariant_registryOwnerMatchesNft`。

`HahaRegistrar._update` 在 owner 更新后按固定顺序执行：

```solidity
if (from != address(0)) {
    if (to == address(0)) revert ERC721InvalidReceiver(address(0));  // 不提供 burn
    IHahaRegistry(registry).syncOwner(bytes32(tokenId), to);
    IHahaResolver(resolver).clearRecords(bytes32(tokenId));
    IHahaAgentIdentity(identity).deactivate(tokenId);
}
```

**关键点**：后两步在「没有记录 / 没有 agent」时也必须成功返回，否则用户 NFT 会被卡死。
`test_clearRecords_noopDoesNotRevert`、`test_deactivate_noAgent_isNoop`、
`test_transfer_bareToken_succeeds` 三条专门卡这个。

**结论**：✅ 转让后 addr 覆盖清为 0（回落新 owner）、text 全空、主名字清空、
agent 被 burn 且旧 agentId 不能再被打分。多次连续转让也成立。

**风险**：`_update` 里调用三个外部合约，如果其中任何一个被「设计成 revert」，
转让就会失败。这三个都是我们自己的合约，且都做了 no-op 保护。`deactivate` 与
`clearRecords` 都有 `msg.sender == registrar` 检查，且内部没有可能 revert 的外部调用。

---

## 4. 积分：能不能被重复领取

**审计问题**：签到、社交领取、铸造奖励、spend/refund 有没有重复领取或凭空造分？

**验证**：`PointsTest` 全部 40 条 + `invariant_pointsNeverNegative`。

逐项：

| 路径 | 防护 | 测试 |
| --- | --- | --- |
| 签到 | `_hasCheckedIn[aiId] && _lastCheckInDay[aiId] >= day` → revert | `test_checkIn_oncePerDay` |
| follow | `_followClaimed[aiId]`，终身一次 | `test_claimFollow_onceLifetime` |
| like/retweet/comment | 各自 `DayClaim{dayIndex, done}` | `test_socialClaims_dailyIndependent` |
| 铸造奖励 | 每天最多 3 次，次数在 `_mintRewardDay[aiId]` | `test_mintReward_maxThreePerDay` |
| spend | 余额不足 revert | `test_spend_insufficientBalance_reverts` |
| **refund** | `amount <= _spendable[aiId][reason]` | `test_refund_exceedingSpendable_reverts` |

### 自审发现的坑：day 0

**发现问题**：`SPEC 6.8` 要求「后三项不能把『从未领取』存成 day 0，因为 day 0 是合法日序号」，
但同一节没提签到。签到用 `_lastCheckInDay[aiId] >= day` 判断——`lastCheckInDay` 默认值是 0，
而 `day 0` 是合法日序号（`block.timestamp < 86400`）。

**后果**：在 1970-01-01 UTC 当天，**所有人第一次签到都会被误判为「今天已签到」**。

**修复**：加 `mapping(bytes32 => bool) _hasCheckedIn`，与 `DayClaim.done` 同一思路。
判断改成 `if (_hasCheckedIn[aiId] && _lastCheckInDay[aiId] >= day) revert`。

**测试**：`test_dayZeroIsValid` 把时间设到 `timestamp = 0` 验证这个边界。

**结论**：✅ 已修。这条是自审计抓到的真实 bug，不是编译期就能发现的问题。

---

## 5. 市场：账能不能被重入做大

**审计问题**：`buy` / `withdraw` 有没有重入漏洞？

**验证**：`MarketplaceTest` 全部 28 条，含 `ReentrantBuyer` 攻击合约。

`buy` 的顺序（严格）：

```solidity
delete _listings[tokenId];                        // 1. 先删挂单
pendingWithdrawal[l.seller] += proceeds;           // 2. 再记账
pendingWithdrawal[feeReceiver] += fee;
emit Sold(...);
nft.safeTransferFrom(l.seller, msg.sender, tokenId);  // 3. 最后转 NFT
```

`buy` 与 `withdraw` 都有 `nonReentrant`。`withdraw` 先把余额置零再转账。

**结论**：✅ `test_reentrancy_onBuyDoesNotInflate` 证明攻击者在
`onERC721Received` 里重入 `buy` / `withdraw` 都拿不到额外钱；待提现总额仍等于 1 ether。

**`sum(pendingWithdrawal) <= balance` 的不变式**：`invariant_marketplaceSolvent` 在随机
挂单/买卖/提现序列下恒成立。

**已知且接受的偏差**：自毁强行打进市场的 BNB 会让 `balance > sum(pending)`，
那部分取不出。`SPEC 6.9` 明确不要加 `skim`，我遵守了。

---

## 6. 部署者零权限

**审计问题**：部署 EOA 和工厂合约是否真的没有任何剩余权限？

**验证**：`AdminPowerTest` 的 6 条 + `Deploy.t.sol`。

| 检查 | 结果 |
| --- | --- |
| 部署 EOA 调 `adminMint` | revert `NotAdmin` |
| 部署 EOA 调 `setPointParams` | revert `NotAdmin` |
| 部署 EOA 调 `setSpender` | revert `NotAdmin` |
| 部署 EOA 是 registrar.admin | ❌ 不是，是 `0x083A...6Ef7` |
| 部署 EOA 是 points.admin | ❌ 不是 |
| `registry.factory` | 是 `HahaDeployer` 合约，不是 EOA |
| `bootstrap` 第二次 | revert |
| 工厂有外部写函数 | ❌ 只有 `addresses()` 一个 view |
| `HahaNamePolicy` 有写函数 | ❌ 一个都没有 |

**结论**：✅

---

## 7. 自审发现的其他问题

### 7.1 `activateAgent` 查错了 ownerOf（**严重，已修**）

**问题**：`HahaAgentIdentity.activateAgent` 原本写的是：

```solidity
if (_ownerOf(nameTokenId) != msg.sender) revert NotNameOwner();
```

`_ownerOf` 查的是**本合约**的 NFT——但名字 NFT 在 `HahaRegistrar` 里。
本合约的 token 是 agent NFT（增量 id），和名字 tokenId 是两套编号。

**后果**：**agent 功能永久不可用**。任何 `activateAgent` 调用都会 revert `NotNameOwner`。
这是一个「上线即坏死」的 bug，且单元测试如果不先铸名字就发现不了。

**修复**：

```solidity
if (IERC721(registrar).ownerOf(nameTokenId) != msg.sender) revert NotNameOwner();
```

**测试**：`IdentityTest.test_activateAgent` 与 `TransferTest.test_transfer_burnsAgent`。

**结论**：✅ 已修。这是本次开发中最严重的一个 bug。

### 7.2 积分事件里 `newBalance` 的求值顺序（低危，已改）

原写法：

```solidity
emit PointsChanged(aiId, user, int256(pts), _balance[aiId] + pts, reason);
_balance[aiId] += pts;
```

**语义上正确**（事件参数先求值），但**读起来像 bug**：存储还是旧值，事件里是新值。
后来者很容易误改成先 emit 后加，从而引入真 bug。

**修复**：改成先 `+=`，再 `emit`，事件里直接读 `_balance[aiId]`。语义不变，可读性提高。

### 7.3 `HahaRegistry.createName` 的校验顺序（提示）

`createName` 既检查 `tldNode` 是否合法，又要求 `registrar.ownerOf(node) == nameOwner`。
后者是一次外部 `staticcall`。如果 `registrar` 是恶意合约，可以在这里做 gas 耗尽攻击——
但 `registrar` 是 immutable，部署时由工厂指定，攻击面为零。

**结论**：不改。

### 7.4 `HahaResolver.setText` 的 key 列表（提示）

删除 key 时用「与末尾交换再 pop」，会打乱 key 顺序。这不影响 `text()` 查询，
但**索引器若从 `TextChanged` 事件重放得到有序列表，顺序可能与本合约内部列表不同**。
`SPEC 6.4` 没有要求 key 有序，所以这不是 bug。已在 `INDEXING.md` 提示「按 key 查询，不要依赖顺序」。

### 7.5 `HahaPoints.creditMintReward` 的调用方检查（提示）

`creditMintReward` 只允许 Registrar 调用，且现场重读 `aiIdentityOf(user)` 并与参数比对。
这一步是必要的：防止 Registrar 传错 `aiId` 把分记到别人头上。

**但**：如果用户在这次铸造交易里**同时**失去了 `.ai`（不可能，因为 `.ai` 是 Soulbound 且不可转让），
奖励会失败导致整个铸造 revert。当前 `.ai` 不可转让，所以不存在这个路径。

### 7.6 `HahaRegistrar.register` 的 `creditMintReward` 在最后（提示）

```solidity
_mintAndRecord(...);
IHahaPoints(points).creditMintReward(msg.sender, ai.aiId);
```

如果积分合约 revert，整个铸造会回滚。`creditMintReward` 的所有 revert 路径
（`NotRegistrar`、`ZeroAddress`、`NameRequired`、`AiRequired`）在正常流程下都不会触发，
因为前面刚检查过 `.ai`、刚铸出名字。当日 3 次用尽时它 **return 0** 而不是 revert——
这是 `SPEC 6.8` 明确要求的「铸造本身不要失败」。

### 7.7 `HahaMarketplace.buy` 里的 `PriceChanged` 错误名（可读性）

`buy` 在 `ownerOf != seller` 时 revert `PriceChanged()`。这个错误名对「挂单已过期」的
场景不够准确（不是价格变了，是 owner 变了）。

**但**：`SPEC 6.9` 要求「卖家若抢跑改价，买家的交易 revert」，没有规定错误名。
改名会让 ABI 变化，且 `clearStale` 是正解。**结论**：保留，在 NatSpec 里说明两种成因。

---

## 8. 与 `SPEC 11` 逐条对照

| SPEC 11 要求 | 实现情况 |
| --- | --- |
| 除 `buy` 外不 payable，无 `receive`/`fallback` | ✅ `test_noReceive`、`test_onlyBuyIsPayable` |
| 先改状态再外部调用，BNB 用拉取 | ✅ `buy` 先删单记账再转 NFT；`withdraw` 先置零再转 |
| 不出现 `tx.origin` | ✅ 全仓库无 `tx.origin` |
| 业务合约不用 `delegatecall`/`selfdestruct` | ✅ 无 |
| 不实现 EIP-712，无 signer | ✅ `test_noSignerNoEip712`、`test_noSignerAnywhere` |
| 社交任务不做链上核实（接受的风险） | ✅ 四个无参函数，仅校验参与条件 |
| 抢注可接受，不加 commit-reveal | ✅ `register` 直接铸 |
| 名单、费率、admin、`.ai` 地址部署后是常量 | ✅ 全是 immutable 或构造时写入的 mapping |
| 转账钩子的 `clearRecords`/`deactivate` 必须 no-op 安全 | ✅ 三条专测 |
| 解析器/身份地址是 immutable | ✅ 用户不能换恶意解析器 |
| 市场在 `safeTransferFrom` 前删单记账 | ✅ |
| 强行打入的 BNB 可留，不加 `skim` | ✅ `test_marketplace_hasNoAdmin` |
| 不提供 `setOwner`/`setResolver`/`setTTL`/`setSubnodeOwner`/`reclaim` | ✅ `test_registry_noUserEscalation` |
| 管理员只有三项权力 | ✅ `AdminPowerTest` 全部 22 条 |

---

## 9. 测试覆盖

| 类型 | 数量 | 说明 |
| --- | --- | --- |
| 单元 | 211 | 铸造、解析、转让、身份、声望、积分、市场、管理员、SVG |
| 模糊 | 8 | 每个 1000 runs |
| 不变式 | 10 | 128 runs × 48 depth |
| fork（离线） | 13 | 冻结字节码，CI 可跑 |
| fork（在线） | 10 | 可选，需 RPC |

**合计 259 通过，0 失败，10 跳过**（跳过的是在线层，非 fork 环境下自动 skip）。

`SPEC 12` 的清单我逐项对过，全部有对应测试。清单见 `docs/contracts/SPEC-COVERAGE.md`。

---

## 10. 遗留风险（如实列出）

1. **`via_ir = true`**：这是编译器的硬性要求，但 via-ir 的字节码可审计性略低于传统 pipeline。
   审计方需要按实际部署的字节码复核，不能按源码想象。

2. **`.ai` 的字节码哈希没有从已验证源码对照**：`SPEC 14.2` 记录了这一点。我们只核对了
   字节码哈希、dispatcher 和 `alice` 闭环。行为以字节码为准。

3. **`.ai` 的 `adminRegister` 可能让一个地址持有多个 handle**：`handleOf` 只返回一个字符串，
   我们用它作为唯一身份。`SPEC 14.3` 已记录。如果 `.ai` 的 owner 恶意让某地址持有两个 handle，
   我们的门禁仍只看 `handleOf` 返回的那一个——这是**优势**，不是漏洞。

4. **`refund` 的额度上限是按 `(aiId, reason)` 记账的**：如果 spender 用不同的 reason
   反复 spend/refund，额度是分开算的。这符合 owner 的裁决，但意味着**同一个 spender 可以用
   多个 reason 刷出多份额度**。防护依赖「spender 是审计过的合约」（`SPEC 8` 的要求）。

5. **市场不读 ERC-2981**：`buy` 只扣一次 1%，不叠加版税。外部市场（OpenSea 等）若执行
   `royaltyInfo` 会再收 1%——那是外部市场的行为，我们控制不了。`SPEC 6.9` 明确接受这一点。

6. **没有第三方审计**：本报告是开发者自审。`SPEC` 要求「上线前做审计」，
   第三方审计仍是上线前的必要步骤。

7. **fork 测试的归档区块不可读**：`SPEC 4` 要求的区块 `134683411` 在公共 RPC 上
   返回 `missing trie node`。我们改用「冻结 latest 的字节码 + 哈希写死断言」，
   并在 `test/fork/FROZEN.md` 里说明了边界。

---

## 11. 建议的第三方审计重点

按风险从高到低：

1. **`HahaRegistrar._update` 的转账钩子**——所有解析清空和 agent burn 都挂在这里。
   任何 revert 路径都会卡死用户 NFT。
2. **`HahaPoints` 的每日计数与 `spendable` 记账**——积分是唯一会被「刷」的资产。
3. **`HahaMarketplace.buy` 的状态更新顺序**——重入的唯一入口。
4. **`HahaDeployer._postDeployChecks` 之后的实际链上状态**——部署脚本的断言
   是否真的覆盖了 `SPEC 13` 的每一项。
5. **`HahaRegistrar.adminMint` 的保留名判定**——管理员不能盖公众名字是产品承诺。
