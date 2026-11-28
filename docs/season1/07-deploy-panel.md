# 07 部署面板（D 实现，只签名）

现有面板在 `tools/deploy-panel/`。它只在本地打开，用浏览器钱包签名，不读取私钥。第一季沿用这条。不要把私钥、助记词、BscScan API key 写进仓库、日志或回执文件。

本文件是面板要增加的步骤。提交人A 不在本 PR 改 `app.js`。

## 编译与字节码

新模块与旧合约同一套：

- solc `0.8.28+commit.7893614a`
- optimizer runs 200
- `via_ir = true`
- EVM `cancun`

面板只接受由该次 `forge build` 生成的 creation bytecode。部署前对 creation code 做 keccak，显示在屏幕上，与 `broadcast` 回执里的 input 比对。不一致就停。

构造参数写死为 `01` 的五个主网地址，`snapshotConfirmations = 15`。测试网或 anvil 可以改这个深度，主网框固定 15。进度按 chainId 分开存。

## 签名步骤

每一步一笔交易，点一次签一次。失败不自动重试扣费。

| 顺序 | 调用 | 签名者 | 说明 |
| --- | --- | --- | --- |
| 1 | 部署 `HahaSeason1` | 部署用的管理员地址 | 与现网一样，部署者就是管理员。这是既有事实，不是新权限 |
| 2 | 读回构造参数与 Points、Registrar、Identity、`.ai`、admin | 无 | `eth_call` |
| 3 | `setSpender(season1, true)` | 管理员 | 旧 Points |
| 4 | `setSpenderBudget(200, 4000)` | 管理员 | 已由 20×200 定下。仍要管理员签名，面板不得代签 |
| 5 | `setEarner(SEASON1_VERIFY, …)` | 管理员 | 30 分，次数 1，全网 `100000`，`requireName` true，`PerDay`。拒绝 1000000 和 10000000 |
| 6 | `setEarner(SEASON1_FIND, …)` | 管理员 | 100 分，次数 5，全网 `10000`，`requireName` true，`Lifetime` |
| 6b | `setEarner(SEASON1_ACCIDENT, …)` | 管理员 | 100 分，次数 50（硬顶映射），全网 `10000`，`requireName` false，`Lifetime` |
| 7 | `setValidator` | 管理员 | 等服务器公布公钥。面板不生成、不接收私钥。未填则按钮不可用 |
| 8 | `setRewardSigner` | 管理员 | 填现有管理员地址。撤掉后旧找错和事故签名立即失效 |
| 9 | 打开 `redeemOpen` / `rewardsOpen` | 管理员 | 只在 `10` 的验收门通过后显示为可点 |

第 5、6 步必须显示 actionId 的完整 `bytes32` hex，防止覆盖 `REVIEW_GIVE`、`REVIEW_RECEIVE`、`ACTIVATE`。面板若检测到 actionId 属于这三类或六个内置 reason，拒绝编码。

第 4–6 步的数字已批准，面板按 `02` 填好，不再留空。日奖公钥为空时，只有第 7 步不可用。

## 业务发放不是部署步骤

铸名字不进上述 1–9 步。发放清单是另一屏：

- 每行一个订单：`orderId`、label、tld、recipient、模拟结果。
- 每一行单独的「签名并广播 `adminMint`」。
- 不提供「全部签名」或 multicall。
- 发放确认调用 `attestFulfillment(orderId, mintTxHash)`，参数里没有 tokenId。网站仍以日志核对为准，不以这个声明单独显示已发放。
- 广播前对管理员地址做 `eth_call` 模拟。模拟 revert 则不弹出钱包。
- 模拟成功才请求签名。

管理员密钥仍然可以在面板之外调用 `adminMint`。面板不把这件事说成已经禁止。

## 模拟与回执

沿用现面板：交易哈希进本地状态，刷新后用哈希补查收据。不要把未上链的签名 raw tx 上传到网站。

部署回执只含地址、构造参数、字节码哈希、每步交易哈希。不含私钥。
