# 13 第一季部署授权清单（L 逐笔确认用）

> 本清单是 Season1 模块在 BSC 主网（chainId 56）的部署与授权逐笔交易清单，供 L 的管理员钱包逐笔确认。
> D 只准备 calldata 与验收方法，**不索取管理员私钥、不自行广播主网交易**。每笔交易由 L 在面板上点一次、钱包签一次。

## 0. 可复现构建

| 项 | 值 |
| --- | --- |
| 源码 commit | `293f202`（第二轮修复，已并入 main `e531602`） |
| 编译器 | solc `0.8.28+commit.7893614a` |
| optimizer | runs `200`，`via-ir = true` |
| EVM | `cancun` |
| creation bytecode | `18518` bytes，sha256 `a0f0724116bcc82f1d3733d01ed34361f7623cab112a31b5b8e1077da0a589b7` |
| runtime bytecode | `16920` bytes（< 24576，无需拆分），sha256 `16763aa458ef0028d306e37ebfe383b13214b830694903438764c6f05d7adf54` |

复现命令：

```bash
forge build --skip test --skip script
# 对比 out/HahaSeason1.sol/HahaSeason1.json 的 bytecode sha256 与上表一致
```

面板加载的 `tools/deploy-panel/public/season1/HahaSeason1.bytecode.json` 已与 forge 产物逐字节一致（`== True`）。

## 1. 旧合约地址与固定角色核对（已确认）

| 名称 | 地址 | Season1 用途 |
| --- | --- | --- |
| 管理员（admin，= 部署者） | `0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7` | onlyAdmin / rewardSigner |
| HahaPoints | `0xB2D023b8B5895835EFD71C1150BeAD7bD735DfAa` | spender / 三个 earner 宿主 |
| HahaRegistrar | `0x43426E37a31AafDaba851858e34B81DC300650F8` | 名字 isMinted / ownerOf |
| HahaAgentIdentity | `0x54A70BF81B288d41013D7b57c2Db0922f1E1a4d4` | generationOf(agentId) |
| `.ai` 注册表 | `0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F` | 三重核对 |
| 手续费接收（背景，非本模块参数） | `0x57A76124bC919F7509bEb54924E8448258De90df` | 市场 1% |

构造参数五个地址 + `snapshotConfirmations = 15` 全部写死在面板，不可改。

## 2. 待填项（部署时才知道）

| 项 | 状态 |
| --- | --- |
| **日奖签名公钥**（`setValidator`） | **空**。服务器专用钱包离线签名，只公开地址。未填入前，面板第 7 步不可用；`rewardsOpen` 对验证保持关闭。 |

## 3. 预算与默认关闭状态核对（已确认）

| 项 | 值 |
| --- | --- |
| 兑换 spender 预算 | 每 `.ai` 每日 `200`，全网每日 `4000`（= 20×200，退分不恢复当日 gross） |
| SEASON1_VERIFY | 30 分 / 每人每日 1 / 全网 100000 / `PerDay` / `requireName=true` |
| SEASON1_FIND | 100 分 / 每人每日 5 / 全网 10000 / `Lifetime` / `requireName=true` |
| SEASON1_ACCIDENT | 100 分 / 每人每日 50（硬顶映射）/ 全网 10000 / `Lifetime` / `requireName=false` |
| `redeemOpen` | **默认 `false`**（合约 `bool` 默认值） |
| `rewardsOpen` | **默认 `false`**（合约 `bool` 默认值） |

开关保持关闭，直到 `10-deploy-checklist.md` 的验收门通过、第一天 manifest 复算一致后，才打开。

## 4. 逐笔授权清单（部署顺序）

每一步一笔交易，点一次签一次。前 8 笔为部署授权，第 9/10 笔（开关）在验收门通过后才解锁。**第 1 步前有一步只读核对（不发交易）。**

### 第 0 步：读回核对（只读，不发交易）

- 部署后，面板 `eth_call` 读回 `admin` / `points` / `registrar` / `identity` / `aiRegistry` / `snapshotConfirmations`，逐项比对 §1 表格。

### 第 1 笔：部署 `HahaSeason1`

| 项 | 值 |
| --- | --- |
| 目标 | CREATE（无 to） |
| 构造参数 | `admin`、`points`、`registrar`、`identity`、`aiRegistry`（§1 地址）、`snapshotConfirmations=15` |
| 签名者 | 管理员 `0x083A…6Ef7` |
| 验收 | 交易回执 `contractAddress` 生成；第 0 步读回 5 地址 + 深度全部一致；creation bytecode keccak 与广播 input 一致 |

### 第 2 笔：`setSpender(season1, true)`（旧 Points）

| 项 | 值 |
| --- | --- |
| 参数 | `spender = season1 地址`，`enabled = true` |
| 验收 | `points.isSpender(season1) == true` |

### 第 3 笔：`setSpenderBudget(season1, {200, 4000})`（旧 Points）

| 项 | 值 |
| --- | --- |
| 参数 | `perUserDailyPoints = 200`，`globalDailyPoints = 4000` |
| 验收 | 读回 budget 两字段 == 200 / 4000 |

### 第 4 笔：`setEarner(SEASON1_VERIFY, …)`（旧 Points）

| 参数 | 值 |
| --- | --- |
| actionId | `SEASON1_VERIFY`（bytes32，完整 hex 显示在面板） |
| module | `season1 地址` |
| points / cap / global | `30` / `1` / `100000` |
| keyMode | `PerDay`（enum = 1） |
| requireName / enabled | `true` / `true` |
| 验收 | 读回 earner 配置逐字段一致；actionId 不覆盖 `REVIEW_GIVE`/`REVIEW_RECEIVE`/`ACTIVATE` |

### 第 5 笔：`setEarner(SEASON1_FIND, …)`（旧 Points）

| 参数 | 值 |
| --- | --- |
| actionId | `SEASON1_FIND` |
| points / cap / global | `100` / `5` / `10000` |
| keyMode | `Lifetime`（enum = 2） |
| requireName / enabled | `true` / `true` |

### 第 6 笔：`setEarner(SEASON1_ACCIDENT, …)`（旧 Points）

| 参数 | 值 |
| --- | --- |
| actionId | `SEASON1_ACCIDENT` |
| points / cap / global | `100` / `50` / `10000` |
| keyMode | `Lifetime`（enum = 2） |
| requireName / enabled | `false` / `true` |

### 第 7 笔：`setValidator(日奖公钥, true)`（HahaSeason1）

| 项 | 值 |
| --- | --- |
| 参数 | `account = 服务器日奖公钥地址`，`allowed = true` |
| 前置 | L 提供日奖公钥；未填则按钮不可用 |
| 验收 | `season1.validators(日奖公钥) == true` |

### 第 8 笔：`setRewardSigner(管理员)`（HahaSeason1）

| 项 | 值 |
| --- | --- |
| 参数 | `account = 0x083A…6Ef7`（管理员，找错/事故签名人） |
| 验收 | `season1.rewardSigner() == 0x083A…6Ef7` |

### 第 9 笔：`setRedeemOpen(true)`（HahaSeason1，验收门后）

| 项 | 值 |
| --- | --- |
| 前置 | 验收门通过 + 第一天 manifest 复算一致 + `setDayRoot` 已设 |
| 验收 | `season1.redeemOpen() == true` |

### 第 10 笔：`setRewardsOpen(true)`（HahaSeason1，验收门后）

| 项 | 值 |
| --- | --- |
| 前置 | 验证签名人 + 任务包就绪 |
| 验收 | `season1.rewardsOpen() == true` |

## 5. 部署后运营（非本次逐笔授权范围）

| 操作 | 频率 | 说明 |
| --- | --- | --- |
| `setDayRoot` | 每日 | 快照块深度须在 15~255 块（面板有预检，超窗拒绝、不回退、不顺延） |
| `setTaskPack` | 每日 | 快照块达 15 确认后发布任务包 |
| `adminMint` + `attestFulfillment` | 按订单 | 发放名字，每行单独签名（A 的运营工具，非本面板） |

## 6. 交付后回执

部署完成后，D 提供：

- Season1 模块地址（`HahaSeason1` 合约地址）
- 每笔交易的 tx hash + 区块（部署笔记，不含私钥）
- 权限核对结果（§4 每笔的验收项读回结果）
- 更新后的 `HahaSeason1.abi.json` / `handoff.json`（供 A、C 接入）

模块地址与回执交给 A、C 接入后，Season1 进入运营阶段。
