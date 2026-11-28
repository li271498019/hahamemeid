# 部署流程

状态：给执行部署的人。日期：2026-11-20。

`docs/contracts/DEPLOYED.md`（记录实际部署地址与交易哈希）**在真正部署之前不创建**，
由执行部署的人按本文第 6 节生成。

---

## 1. 准备

### 1.1 工具

```bash
# Foundry（本文档基于 v1.10.0 验证）
forge --version

# 依赖已锁定在 lib/ 下，不要升级
# - openzeppelin-contracts v5.1.0
# - forge-std v1.9.4
forge install    # 一般不需要，lib/ 已经提交
```

### 1.2 环境变量

```bash
export BSC_RPC_URL="https://bsc-dataseed.bnbchain.org"   # 或你自己的归档节点
export DEPLOYER_PK="0x..."                                # 临时部署钱包私钥

# 可选，默认值见 SPEC 5.5
# export ADMIN_ADDRESS="0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7"
# export FEE_RECEIVER_ADDRESS="0x57A76124bC919F7509bEb54924E8448258De90df"
# export AI_REGISTRY_ADDRESS="0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F"
```

### 1.3 部署钱包

- **临时钱包**，只放够用的 gas（预估 < 0.05 BNB，实测 10 个合约约 0.02–0.03 BNB）。
- 部署完成后**权限为零**，可以作废。
- **不要**用硬件钱包跑部署脚本（脚本需要 `--private-key`）。

---

## 2. 部署前必做：跑全部测试

```bash
forge test
```

期望：`259 passed, 0 failed, 10 skipped`（跳过的是在线 fork，非 fork 环境自动 skip）。

**任何失败都不要继续。** 合约不可升级，出错只能重新部署整套。

---

## 3. 部署前必做：核对名单

脚本会自己校验，但你也要过一遍：

```bash
# 208 行
wc -l docs/contracts/blacklist-v2.hashes.txt

# 61 行
wc -l docs/contracts/reserved-names.hashes.txt
```

脚本在 `_loadBannedHashes` 里做的校验：

1. 每行必须是 `词<空格>0x<64 位 hex>`
2. 行数正好 208
3. 无重复、无零哈希
4. 208 个哈希首尾相接的 `keccak256` 必须等于
   `0xb9bda22217d260c2032c02472ab75de873d668a59e15358431284b2e99ff41e1`

任何一条不满足就 **revert，不部署**。

> ⚠️ **保留名单是冻结的。** 漏掉的品牌名不能在部署后追加，只能重新部署整套合约。
> 部署前**最后再读一遍** `docs/contracts/reserved-names.md`。

---

## 4. Dry-run（不花 gas）

### 4.1 本地 fork 上跑一遍

```bash
forge script script/Deploy.s.sol:Deploy \
    --rpc-url $BSC_RPC_URL \
    --private-key $DEPLOYER_PK \
    -vvv
```

不带 `--broadcast` 时 Foundry 会模拟执行并打印所有 `console2.log`。
**检查输出里每条 `OK` 都在**，尤其是：

```
OK   .ai bytecode matches SPEC 4
OK   blacklist: 208 hashes, aggregate hash matches
OK   reserved: 61 hashes
OK   chainId is 56
OK   admin / feeReceiver are not the deployer EOA
OK   deployer EOA has zero admin power
OK   bootstrap cannot be called again
OK   TLD nodes owned by Registrar, root is 0
OK   policy spot checks pass
OK   royalty = 1% to feeReceiver
OK   no EIP-1967 implementation slots
OK   HahaDeployer has no external writers
```

### 4.2 检查预测地址

脚本会用 `vm.computeCreateAddress` 预测 8 个合约的地址并断言与部署结果一致。
如果 dry-run 里出现 `... address mismatch`，说明 nonce 基准算错了，
**不要加 `--broadcast`**。

---

## 5. 正式部署

```bash
forge script script/Deploy.s.sol:Deploy \
    --rpc-url $BSC_RPC_URL \
    --private-key $DEPLOYER_PK \
    --broadcast \
    --verify \
    -vvv
```

`--verify` 需要 `BSCSCAN_API_KEY`。BSC 的合约验证在 BscScan 上进行。

### 5.1 部署顺序（脚本内部固定）

| # | 合约 | 依赖 |
| --- | --- | --- |
| 1 | `HahaNamePolicy` | 208 + 61 个哈希（构造参数） |
| 2 | `HahaMetadata` | 无 |
| 3 | `HahaResolver` | registry（预测地址）、registrar（预测地址） |
| 4 | `HahaRegistry` | registrar（预测地址）、factory（稍后部署）、resolver（已部署） |
| 5 | `HahaRegistrar` | registry、resolver、metadata、points（预测）、identity（预测）、policy、aiRegistry、admin、feeReceiver |
| 6 | `HahaAgentIdentity` | registrar、resolver、points（预测）、aiRegistry |
| 7 | `HahaPoints` | registrar、aiRegistry、admin |
| 8 | `HahaReputation` | identity、aiRegistry、points |
| 9 | `HahaMarketplace` | registrar、feeReceiver |
| 10 | `HahaDeployer` | 以上 9 个地址 → 校验依赖 → `bootstrap()` |

**为什么有预测地址**：`Resolver` 需要 `Registry` 的地址，而 `Registry` 需要 `Resolver` 的地址；
`Registrar` 需要 `Points` 和 `Identity`，而它们又需要 `Registrar`。这是环，只能靠 CREATE 的
nonce 预测解开。脚本每一步都断言预测 == 实际，不一致就当场失败。

**为什么不是一个工厂构造函数搞定**：`SPEC 13` 原本这么要求，实测**在物理上做不到**——
父合约 initcode 必须内嵌所有 `new` 的合约 initcode，实测 56,145 字节，
超过 EIP-3860 的 49,152 上限。详见 `src/HahaDeployer.sol` 顶部注释。

---

## 5.2 部署后的配置交易（硬件钱包管理员发送）

补充规格 v1.1（`docs/specs/SUPPLEMENT-points-games-8004v2.md`）引入的 earner 注册表、小游戏、预算，
**不由部署 EOA 或工厂设置**，而由硬件钱包管理员在部署后手动发。工厂不保留写函数。

### 5.2.1 注册发分模块（`setEarner`）

三个内置动作，module 分别是声誉合约和身份合约，数值见规格 1.3 表：

| actionId | points | perUserDailyCap | globalDailyPoints | keyMode | requireName | module |
| --- | --- | --- | --- | --- | --- | --- |
| `REVIEW_GIVE` | 5 | 5 | （规格 1.3） | `PerDay`，`bytes32(agentId)` | true | `HahaReputation` |
| `REVIEW_RECEIVE` | 5 | 5 | （规格 1.3） | `PerDay`，`keccak256(abi.encode(agentId, raterAiId))` | false | `HahaReputation` |
| `ACTIVATE` | 20 | 1 | （规格 1.3） | `Lifetime`，`ACTIVATE_ONCE` | true | `HahaAgentIdentity` |

### 5.2.2 小游戏上线时注册（`registerGame`）

一个游戏一个 `gameId`，带 `maxScorePerRound`、该 `.ai` 的每日分数上限、全网每日预算。
**不上线就不登记。不要登记 PLAY / WIN 两个动作。**

### 5.2.3 授权拍卖 spender 时同时设预算（`setSpenderBudget`）

只 `setSpender(true)` 而不设预算的，`spend` **会 revert `BudgetNotSet`**。
必须同一轮配置里把 `setSpenderBudget` 一起发掉。

---

## 6. 部署后核对（全部通过才能公布地址）

写进新建的 `docs/contracts/DEPLOYED.md`：

```markdown
# 部署记录

| 项 | 值 |
| --- | --- |
| 链 | BSC 主网，chainId 56 |
| 部署时间 | YYYY-MM-DD HH:MM UTC |
| 部署 EOA | 0x... |
| 部署交易 | 0x... |
| 部署区块 | ... |
| 当前 `.ai` 字节码哈希 | 0xc4006e6e...6ace |

## 合约地址

| 合约 | 地址 | 部署交易 | 区块 | 字节码哈希 |
| --- | --- | --- | --- | --- |
| HahaNamePolicy | | | | |
| HahaMetadata | | | | |
| HahaRegistry | | | | |
| HahaRegistrar | | | | |
| HahaResolver | | | | |
| HahaAgentIdentity | | | | |
| HahaReputation | | | | |
| HahaPoints | | | | |
| HahaMarketplace | | | | |
| HahaDeployer | | | | |

## 核对清单

- [ ] chainId 是 56
- [ ] `.ai` 字节码哈希等于 SPEC 4
- [ ] `registrar.admin()` 是硬件钱包，不是部署 EOA
- [ ] `points` 上没有 `signer()`
- [ ] 部署 EOA 调 `adminMint` / `setPointParams` / `setSpender` 全部 revert
- [ ] `bootstrap` 不能再调用
- [ ] `owner(hahaNode)` 和 `owner(memeNode)` 是 Registrar
- [ ] `owner(bytes32(0))` 是 0
- [ ] `isBlacklisted("trump")` true，`isBlacklisted("btc")` false
- [ ] `isReserved("binance")` true，`isReserved("btc")` false
- [ ] `royaltyInfo(x, 1 ether)` == `(feeReceiver, 0.01 ether)`
- [ ] 市场 `feeBps()` == 100
- [ ] 五个核心合约的 EIP-1967 槽为 0
- [ ] 在 fork 上用一个持有 `.ai` 的地址走一遍 `register`（不要在真主网替用户抢名字）
```

---

## 7. 各部门核对（人工）

脚本已经自动做了上面大部分，但下面这些是**脚本做不到的**：

1. **在 BscScan 上逐个确认源码已验证**——10 个合约。
2. **在 fork 上手动走一遍公众铸造**：
   ```bash
   forge test --match-test test_fork_aliceOwnerCanMint --fork-url $BSC_RPC_URL
   ```
3. **确认部署 EOA 的 nonce 已经空转**（不再有权做任何事）。
4. **把管理员私钥（硬件钱包）放到安全的地方**。钥匙丢了，三项管理员功能永久停用，
   但用户的 NFT 和转账不受影响。这是 owner 已确认的取舍。

---

## 8. 部署后不可回滚

**合约全部不可升级，没有代理，没有 `upgradeTo`。** 部署后：

- 不能改 1% 手续费。
- 不能改版税接收者。
- 不能改黑名单或保留名单。
- 不能改管理员。
- 不能暂停转账。
- 不能拉黑地址。

发现了 bug 只能**部署一整套新合约**，然后靠前端与索引器切换。
所以第 2 节（跑全部测试）与第 4 节（dry-run）**不能跳过**。

---

## 9. 常见问题

### `must deploy on BSC mainnet (chainId 56)`

脚本硬性要求 chainId 56。Chapel 测试网（97）上没有 `.ai` 注册表，
`SPEC 13` 也明确说阶段一只上主网。

### `aiRegistry bytecode hash mismatch`

`.ai` 合约的字节码和 `SPEC 4` 记录的哈希不一致。可能是：

- 连错了链（不是 BSC 主网）
- `.ai` 被升级了（理论上不可能，它没有 `upgradeTo`）

**停下来，不要绕过这条检查。** 按 `SPEC 12` 的要求更新规格，而不是改断言。

### `blacklist aggregate hash mismatch`

`docs/contracts/blacklist-v2.hashes.txt` 被改动过，或者读错了文件。
用 `tools/check_hashes.py` 重新生成并比对。

### `resolver address mismatch` / `registrar address mismatch`

nonce 预测和实际部署不一致。原因通常是：

- dry-run 和 broadcast 之间插了别的交易（部署 EOA 的 nonce 被消耗）
- 脚本里插入或删减了一次 `new`

检查 `vm.getNonce(deployerEoa)` 的读数，以及脚本里 `new` 的数量与顺序。
