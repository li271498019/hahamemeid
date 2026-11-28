# haha.meme 部署面板

本地运行的部署面板：在浏览器里连上 MetaMask，按顺序点按钮完成全部合约部署、配置、验证与回执导出。

## 安全原则

- **只在本地运行**：不上传服务器，不放 haha.meme，不碰私钥。
- **不碰私钥**：所有交易由 MetaMask 弹窗签名，面板不读取、不保存私钥和助记词。
- **字节码来源固定**：读 `public/artifacts.json`，由 `generate-artifacts.mjs` 从 `forge build` 产物生成，对应 commit `70fe8e79`。
- **参数写死**：构造参数与 `script/Deploy.s.sol` 完全一致，管理员 / 手续费接收 / `.ai` 注册表地址写死，页面只显示、不允许改。

## 启动

```bash
# 0. 首次使用：装 ethers（前端 vendor 与 dry-run 验证脚本共用）
cd tools/deploy-panel
npm install

# 1. （可选）重新生成产物（已提交，一般无需重跑；改了合约才需要）
#    生成 public/artifacts.json + public/verify/*.json（开源验证用 standard-input）
node generate-artifacts.mjs
node generate-standard-input.mjs
# 或合并：npm run generate

# 2. 启动本地面板
npm run deploy-panel
# 或 node server.mjs [端口]，默认 4321
```

浏览器打开 http://localhost:4321 。

三个入口：

| 页面 | 用途 |
| --- | --- |
| `/index.html` | 旧合约部署面板 |
| `/season1.html` | Season1 部署授权 + setDayRoot 快照窗口 |
| `/season1-fulfill.html` | Season1 铸造发放（adminMint，逐笔签名） |
| `/validation.html` | HahaValidation 部署（G13 验证注册表，单合约） |
| `/dog.html` | Haha Dog 部署（4 合约，按序 + 一键开源 + 权重哈希/出图核对） |

> 需要浏览器已安装 **MetaMask 或 OKX 钱包**。前端 ethers 从本地 `node_modules/ethers/dist/ethers.umd.min.js` 加载（`npm install` 后离线可用），不依赖 CDN。

## 固定地址与参数

| 项 | 值 |
| --- | --- |
| 管理员 | `0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7` |
| 手续费接收 | `0x57A76124bC919F7509bEb54924E8448258De90df` |
| `.ai` 注册表 | `0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F` |
| commit | `70fe8e79` |
| 编译器 | solc 0.8.28，optimizer runs 200，via-ir，cancun |

## 使用流程

1. 选择模式：BSC 主网（chainId 56）或 BSC 测试网（chainId 97），两者进度分开保存。
2. 连接钱包（**MetaMask 或 OKX**），检查网络与 BNB 余额。
3. 按顺序点步骤：前 10 步是合约部署（CREATE nonce 预测地址），后 3 步是 `setEarner` 配置（需切换到管理员钱包）。
4. 每步确认后自动读链上核对；断线后重新打开自动恢复，已发送未确认的交易用 tx hash 补查。
5. 全部完成后运行「最终自检」，再一键验证 / 复制回执。

> **管理员步骤（setEarner）提示**：若管理员是 Ledger/Trezor 硬件钱包，MetaMask 直连可能报
> `Invalid Ethereum definition`（硬件钱包对 `eth_sendTransaction` 的限制）。此时改用 **OKX 钱包**
> 导入/连接管理员账户再执行，或换用软件钱包导入管理员私钥（请自行评估安全）。面板已同时支持两套钱包。

## 部署顺序（与 Deploy.s.sol 一致）

| # | 合约 | 构造参数要点 |
| --- | --- | --- |
| 1 | HahaNamePolicy | 208 + 61 个哈希 |
| 2 | HahaMetadata | — |
| 3 | HahaResolver | 预测 registry / registrar |
| 4 | HahaRegistry | 预测 registrar / factory / resolver |
| 5 | HahaRegistrar | abi.encode(9 地址) 打包 bytes |
| 6 | HahaAgentIdentity | registrar / resolver / points / aiRegistry |
| 7 | HahaPoints | registrar / aiRegistry / admin |
| 8 | HahaReputation | identity / aiRegistry / points |
| 9 | HahaMarketplace | registrar / feeReceiver |
| 10 | HahaDeployer | 校验依赖 + bootstrap |

配置步骤（管理员钱包）：3 次 `setEarner`（写评价 5/5/50000、收评价 5/5/50000、激活 20/1/100000）。

## 验证（dry-run）

```bash
# 起本地 anvil（需要 foundry 的 anvil 在 PATH）
anvil --silent --gas-limit 120000000

# 另开一个终端，跑完整 dry-run：部署 10 合约 + 3 次 setEarner + 最终自检
node verify-dryrun.mjs
```

dry-run 会在 anvil 本地链上完整走一遍部署流程，验证字节码、构造参数编码、CREATE 地址预测、bootstrap、setEarner 读回、部署者零权限自检全部正确。**已实测通过。**

## 说明

- 地址用 CREATE nonce 确定性预测，部署 EOA 的起始 nonce 从链上 `getTransactionCount` 实时读取。
- BscScan API Key 仅在页面输入框内存态保存，不写文件、不提交仓库。
- **开源验证用 `solidity-standard-json-input` 模式**：`generate-standard-input.mjs` 为每个合约递归收集 import 依赖
  （含 OpenZeppelin），生成 `public/verify/*.json`，配合 solc `0.8.28+commit.7893614a`、via-ir、optimizer 200 提交 BscScan。
  这比单文件模式可靠（单文件无法处理 import 与 via-ir）。
- 测试网与主网进度用 localStorage 按 chainId 隔离，互不影响。

## 铸造发放面板（season1-fulfill.html）安全原则

- **逐笔签名**：每个名字单独点一次、签一次。**没有「全部签名」/ multicall 按钮**。
- **管理员私钥不进面板、不进服务器**：所有 `adminMint` / `attestFulfillment` 交易由浏览器钱包（MetaMask / OKX）逐笔签名。
- **复用 A 的发放工具编码**：`adminMint` calldata 编码与日志核对规则，与 `tools/season1/ops.py` 完全一致（selector `0x65f5a090`，namehash 与 `HahaNamehash` 一致）。已验证 JS 与 Python 输出逐字节相同。
- **不新增空投规则**：只对 Season1 里已 `Pending` 的兑换订单做既定 `adminMint`。
- **发放流程**：读订单核对原收件人与域名 → `isMinted` 查重 → 模拟（eth_call）→ 逐笔签名广播 → 核对 `NameMinted` + `Transfer` 日志 → 可选 `attestFulfillment` 见证。
- **拒签/失败/pending/替换交易不重复发放**：同一 orderId 有在途交易（sent/pending）时禁止再签；刷新后用 tx hash 补查收据；同 nonce 替换 gas 以最新收据为准，旧哈希标 dropped。

## 时间门禁与快照窗口（season1.html）

- **链上时间门禁**：北京时间 `2026-11-24 08:00`（UTC `START_TS = 1795478400`）前，页面展示与提交交易逻辑都校验链上 `block.timestamp`，不是只禁用按钮。首日正式快照与发布交易被拒绝。
- **快照窗口**：`setDayRoot` 要求快照块深度 15 ~ 255 块（确认 ≥15 块、距快照 <256 块），签名前再次检查。剩余有效块数 = 255 − 当前深度。不把「约 13 分钟」当保证（BSC 出块时间有波动），不自动广播交易。
- **过去日界预演独立标识**：`dayIndex` 早于链上当前 day 时标记「预演」，主网正式发布拒绝预演 dayIndex。

## HahaValidation 部署面板（validation.html，G13）

- **单合约部署**：1 笔交易部署 HahaValidation，构造参数固定为 `admin`（`0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7`）+ `identity`（`0x54A70BF81B288d41013D7b57c2Db0922f1E1a4d4`），页面只显示、不允许改。
- **部署后自检**：读链核对 `admin` / `identity` / `validator`（初始 = admin）/ `DISPUTE_WINDOW`（= 3 天），并验证非 admin 调 `setValidator` 被拒。
- **一键开源**：走 Etherscan V2 统一 API（`/api/bscscan` 本地代理，chainid=56/97），standard-input 由 `generate-standard-input.mjs` 预生成（`public/verify/HahaValidation.json`）。
- 产物导出：`export-validation.mjs` 生成 `public/validation/`（ABI + bytecode + handoff.json）。

## Haha Dog 部署面板（dog.html，4 合约）

- **按序部署 4 合约**：HahaDogModel（无参）→ HahaDogRenderer（model）→ HahaDog（renderer, aiRegistry, registrar, feeReceiver, blockHistory）→ HahaDogMarket（dog, feeReceiver）。前一步「已确认」才能执行下一步。
- **构造参数可核对修改**：`aiRegistry` / `registrar` / `feeReceiver` / `blockHistory` 默认从 `public/dog/handoff.json` 的 `defaults` 带出（与 `DEPLOY.md` 一致），页面上可改。
- **断线续部署**：进度按 chainId 存 localStorage，中断后点「查询确认」补查收据接续，支持导出/导入 JSON。
- **部署后自检**：读链核对 `MODEL_DATA_HASH()` == 权重哈希 `0x1d2239…8078`、`keccak256(modelData())`、`renderer` / `blockHistory` / `totalSupply==0` / `feeBps==100`。
- **tokenURI 出图验证**：对已铸造 tokenId 调 `tokenURI`（解码 base64 JSON），或对固定种子调 `svgOf(seed)` 出图。
- **一键开源（4 个）**：走 Etherscan V2 统一 API（`/api/bscscan` 本地代理，chainid=56/97），standard-input 由 `generate-standard-input.mjs` 预生成（`public/verify/hahadog_*.json`），逐个提交 `verifysourcecode`。
- 产物导出：`export-hahadog.mjs` 生成 `public/dog/`（4 合约 ABI + bytecode + handoff.json）。
- 编译设置与 DEPLOY.md 一致：solc 0.8.28、optimizer 200 runs、via-ir、evm cancun。

## 测试证据

- **合约层完整发放流程**：`test/season1/Season1Fulfill.t.sol`，6 个测试覆盖：
  - `test_fulfill_complete_flow`：apply → adminMint → NameMinted+Transfer 核对 → attestFulfillment → Fulfilled
  - `test_fulfill_double_adminMint_reverts`：重复铸造 NameTaken，不重复发放
  - `test_fulfill_wrong_recipient_owner_mismatch`：铸错地址 → currentOwnerMatches=false
  - `test_fulfill_attest_idempotent` / `test_fulfill_attest_zeroHash_reverts` / `test_fulfill_attest_nonPending_reverts`
- **窗口过期被拒（合约层）**：`test/season1/Season1Root.t.sol` 已覆盖 `SnapshotTooFresh`（深度 <15）与 `StaleSnapshot`（深度 ≥256）。
- 运行：`forge test`，全绿（351 通过 / 0 失败 / 10 跳过）。
