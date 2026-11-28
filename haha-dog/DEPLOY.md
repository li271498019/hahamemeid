# Haha Dog 开源与部署流程

Haha AI，链上运行的 AI 大模型。本文件给部署人（D）按顺序操作。产品规则以 [SPEC.md](SPEC.md)（v1.0，已冻结）为准。

共 4 个合约，全部不可升级、无管理员、无暂停：

| 顺序 | 合约 | 构造参数 |
|---|---|---|
| 1 | `HahaDogModel` | 无 |
| 2 | `HahaDogRenderer` | `model` = 第 1 步地址 |
| 3 | `HahaDog` | `renderer` = 第 2 步地址，`aiRegistry`，`registrar`，`feeReceiver`，`blockHistory` |
| 4 | `HahaDogMarket` | `dog` = 第 3 步地址，`feeReceiver` |

默认参数（BSC 主网，与现有合约一致）：

| 参数 | 地址 | 环境变量（可覆盖） |
|---|---|---|
| `aiRegistry`（.ai 注册表） | `0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F` | `AI_REGISTRY_ADDRESS` |
| `registrar`（HahaRegistrar，haha id） | `0x43426E37a31AafDaba851858e34B81DC300650F8` | `REGISTRAR_ADDRESS` |
| `feeReceiver`（手续费 / 版税地址） | `0x57A76124bC919F7509bEb54924E8448258De90df` | `FEE_RECEIVER_ADDRESS` |
| `blockHistory`（EIP-2935 区块哈希历史合约） | `0x0000F90827F1C53a10cb7A02335B175320002935` | `BLOCK_HISTORY_ADDRESS` |

## 1. 拉取

```bash
git clone https://github.com/li271498019/hahamemeid.git
cd hahamemeid
```

## 2. 测试

```bash
forge build --sizes
forge test
forge test --match-path 'test/hahadog/*' -vv
```

- `forge test` 必须全部通过（原有测试 + Haha Dog 测试；需要联网 fork 的测试会跳过）。
- 4 个合约运行时字节码都必须小于 24,576 字节（`--sizes` 表里 Runtime Margin 为正）。
- 可选：`python3 haha-dog/reference/gen_solidity.py` 和 `python3 haha-dog/reference/gen_fixtures.py`
  重新生成后 `git status` 应该没有变化，证明链上数据和测试数据都由权重文件推出。

## 3. 部署（主网）

先确认 EIP-2935 合约在 BSC 上存在（返回以 `0x3373ff` 开头的代码即可）：

```bash
cast code 0x0000F90827F1C53a10cb7A02335B175320002935 --rpc-url $BSC_RPC_URL
```

私钥只走环境变量，不写进任何文件：

```bash
export BSC_RPC_URL=...
export DEPLOYER_PK=...          # 临时部署钱包，部署后对合约没有任何权限
export BSCSCAN_API_KEY=...

# 先模拟（不广播）
forge script script/DeployHahaDog.s.sol:DeployHahaDog --rpc-url $BSC_RPC_URL -vvv

# 再广播并验证
forge script script/DeployHahaDog.s.sol:DeployHahaDog --rpc-url $BSC_RPC_URL \
  --broadcast --verify --etherscan-api-key $BSCSCAN_API_KEY -vvv
```

脚本按 Model → Renderer → HahaDog → Market 顺序部署，结束时打印 4 个地址、权重哈希和链上数据哈希，
并校验 `keccak256(model.modelData()) == MODEL_DATA_HASH`。部署后没有任何初始化步骤，铸造立即开放。

## 4. BscScan 验证

`--verify` 通常一次完成。若失败，逐个手动验证（编译设置：solc 0.8.28，optimizer 200 runs，via-ir，evm cancun）：

```bash
forge verify-contract <MODEL> src/hahadog/HahaDogModel.sol:HahaDogModel --chain bsc --watch
forge verify-contract <RENDERER> src/hahadog/HahaDogRenderer.sol:HahaDogRenderer --chain bsc --watch \
  --constructor-args $(cast abi-encode "constructor(address)" <MODEL>)
forge verify-contract <DOG> src/hahadog/HahaDog.sol:HahaDog --chain bsc --watch \
  --constructor-args $(cast abi-encode "constructor(address,address,address,address,address)" \
    <RENDERER> 0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F 0x43426E37a31AafDaba851858e34B81DC300650F8 \
    0x57A76124bC919F7509bEb54924E8448258De90df 0x0000F90827F1C53a10cb7A02335B175320002935)
forge verify-contract <MARKET> src/hahadog/HahaDogMarket.sol:HahaDogMarket --chain bsc --watch \
  --constructor-args $(cast abi-encode "constructor(address,address)" <DOG> 0x57A76124bC919F7509bEb54924E8448258De90df)
```

## 5. 公布哈希与主网地址

BSC 主网（chainId 56）已部署，四个合约均不可升级：

| 合约 | 地址 |
|---|---|
| HahaDogModel | `0x3277990797Ed8B15B3674ee0C557011F5a1eCCC9` |
| HahaDogRenderer | `0xCA760D9D3E76DcDC7AC6bcc55D53346b8a2c107E` |
| HahaDog | `0x26f88A5db4925e9aFa35B1096FdD6DBa09f056c6` |
| HahaDogMarket | `0xD7F5502Bd7a52E17959bF4b7F1180f6e3611fd49` |

同时公布以下哈希（任何人可自行核对）：

- 模型权重 keccak256：`0x1d2239644b5273c4f1925c489d32900a564262bce6597f94a929489cfbe58078`
  （文件 `haha-dog/model/weights-int8.json` 原始字节的 keccak256）
- 链上数据 keccak256：`0x72f92c628a64bc0d5652d285c6789fa0f84cb462d328604cf3dcff224704f8da`
  （`HahaDogModel.MODEL_DATA_HASH()`，等于 `keccak256(HahaDogModel.modelData())`）
- 4 个合约地址和 BscScan 验证链接

核对命令：

```bash
cast keccak $(xxd -p haha-dog/model/weights-int8.json | tr -d '\n' | sed 's/^/0x/')
cast call <MODEL> "MODEL_DATA_HASH()(bytes32)" --rpc-url $BSC_RPC_URL
```

## 6. 网站填地址

在 `web/site/js/addresses.js` 的 `window.HAHA_ADDRESSES` 里加入：

```js
hahaDogModel: "<MODEL>",
hahaDogRenderer: "<RENDERER>",
hahaDog: "<DOG>",
hahaDogMarket: "<MARKET>",
```

（网站改动单独提 PR，不在本补丁内。）

## 7. 开启"链上核对"

`/ai` 页的"链上核对"按钮目前是禁用状态（`ai.html` 里 `disabled`，提示"合约部署后开放"）。开启时：

- 去掉按钮的 `disabled`，点击后对当前种子调用 `HahaDogRenderer.svgOf(bytes32 seed)`（`eth_call`，免费），
  把返回的 SVG 和页面 `HahaAiModel.svgFor(traits(seed))` 的结果逐字比较，一致即显示"链上一致"。
- 也可以对已铸造的 token 核对：`HahaDog.seedOf(tokenId)` 取种子，再同样比较；`HahaDog.tokenURI(tokenId)` 返回完整 base64 JSON。
- 渲染大约需要 450 万 gas，`eth_call` 不花钱，但部分公共 RPC 对 `eth_call` 有 gas 上限，建议用 BSC 官方 RPC 或自建节点。

## 8. 启动快照程序

为什么需要：种子来自 `blockhash(N+4)`。合约能直接读到最近 256 块（`blockhash`）和最近 8191 块（EIP-2935，
BSC 约 0.75 秒一块，约 1.7 小时）。超过窗口且没被快照的 token 会一直显示"出图中"，持有人需要免费重铸。
快照把哈希永久写入合约，之后随时都能出图。铸造、重铸、转账时合约会自动顺带处理 3 个，快照程序负责把剩下的处理完。

快照程序只是普通调用者：调用公开免费函数 `processQueue(uint256)`，不保存、不决定任何数据，任何人都可以运行。

```bash
export BSC_RPC_URL=...
export HAHA_DOG_ADDRESS=<DOG>
export KEEPER_PK=...            # 只放少量 BNB 付 gas 的独立钱包
export MAX_STEPS=100            # 每笔最多处理 100 个，约 300 万 gas 以内
export INTERVAL=30              # 每 30 秒检查一次
nohup bash haha-dog/keeper/keeper.sh > keeper.log 2>&1 &
```

逻辑：先用 `eth_call` 模拟 `processQueue(MAX_STEPS)`，返回的新队首和当前 `queueHead()` 不同才发交易，没有到期的就不花 gas。

手动补救（任何人都可以）：

```bash
cast send <DOG> "processQueue(uint256)" 200 --rpc-url $BSC_RPC_URL --private-key $KEEPER_PK
cast send <DOG> "snapshot(uint256[])" "[1,2,3]" --rpc-url $BSC_RPC_URL --private-key $KEEPER_PK
cast call <DOG> "needsSnapshot(uint256)(bool)" 1 --rpc-url $BSC_RPC_URL
cast call <DOG> "queueHead()(uint256)" --rpc-url $BSC_RPC_URL
cast call <DOG> "queueLength()(uint256)" --rpc-url $BSC_RPC_URL
```

监控：`queueLength() - queueHead()` 应保持很小；如果快照程序停了超过约 1.5 小时，要尽快补跑。

## 9. 部署后自检

```bash
cast call <DOG> "totalSupply()(uint256)" --rpc-url $BSC_RPC_URL            # 0
cast call <DOG> "renderer()(address)" --rpc-url $BSC_RPC_URL               # = RENDERER
cast call <DOG> "blockHistory()(address)" --rpc-url $BSC_RPC_URL          # = 0x0000F908...2935
cast call <DOG> "royaltyInfo(uint256,uint256)(address,uint256)" 1 10000 --rpc-url $BSC_RPC_URL  # feeReceiver, 100
cast call <MARKET> "feeBps()(uint256)" --rpc-url $BSC_RPC_URL              # 100
cast call <RENDERER> "svgOf(bytes32)(string)" 0x0000000000000000000000000000000000000000000000000000000000000001 --rpc-url $BSC_RPC_URL
```

然后用一个持有 .ai 的钱包铸造 1 个，等 4 个块后看 `tokenURI` 是否出图、`statusOf` 是否为 2。
