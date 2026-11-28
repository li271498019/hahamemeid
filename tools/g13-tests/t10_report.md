# T10 测试报告 — G13 验证者服务（计划 §11.2）

日期：2026-11-25。测试人：C。结果：**26 项全部通过，失败 0 项**（v16 新增 EIP-712 4 项，原 22 项全部回归通过）。

## 测试方法（真实跑，不是只写断言）

- 本地 anvil（chain-id 31337，`--block-time 1`，`--base-fee 0`，
  使 1 gwei 的 legacy 交易能打包；服务本身 gas 仍按计划固定 1 gwei）。
- forge 编译的真实 `HahaValidation.sol`（与 D 交付的 PR #101 同源）+
  `MockIdentity` 替身（只实现 `isAuthorized` / `ownerOf` / `tokenURI`）。
- 本地 fixture HTTP 服务：请求文档与注册文件走 `ipfs://` 经网关
  （与生产一致），endpoint 走 `http://127.0.0.1`，覆盖 200/401/404/
  405（GET）/500/12 秒慢响应；另有 70KB 大文档与无效 JSON。
- 真实的 `validator-service.py` 以子进程跑（`VALIDATOR_ONCE=1` 逐场景跑，
  另有一段 live 35 秒观测轮询间隔）。
- 密钥全部是 anvil 公开默认测试密钥，非真实密钥。
- 测试环境已持久化：venv 在 `tests/venv`（eth_account 0.14.0），
  编译产物在 `tests/run`（forge 项目，含 MockIdentity.sol）；
  不再用 /tmp（/tmp 跨 turn 不保留）。

运行：`tests/t10_run.py`（Python 3.12，eth_account 0.14.0）。

## 结果

| # | 测试 | 结果 |
|---|---|---|
| 1 | anvil 启动 | 通过 |
| 2 | 接口可达 2xx → 100 | 通过（链上 score=100，tag=endpoint-reachable） |
| 3 | 接口可达 401 → 100 | 通过 |
| 4 | 接口可达 404 → 0 | 通过 |
| 5 | 接口可达 405 改 POST 空 JSON → 100 | 通过（POST 的 Content-Type 与 body 已在 fixture 侧校验） |
| 6 | 接口可达 5xx → 0 | 通过 |
| 7 | 接口可达 超时（12 秒 > 10 秒超时）→ 0 | 通过 |
| 8 | endpoint 未在注册文件 → 0 | 通过 |
| 9 | 身份真实性 签名有效 → 100 | 通过（EIP-191 签 requestHash 32 字节原始值） |
| 10 | 身份真实性 签名无效（他人签）→ 0 | 通过 |
| 11 | 身份真实性 EIP-712 签名有效 → 100 | 通过（v16 新增；IdentityChallenge{agentId, requestHash}，domain HahaValidation/1/56/主网合约地址） |
| 12 | 身份真实性 EIP-712 无类型提示 → 100 | 通过（v16 新增；无 signatureType 时两种都试） |
| 13 | 身份真实性 EIP-712 签名无效 → 0 | 通过（v16 新增；他人签 EIP-712 → 0） |
| 14 | 身份真实性 EIP-191 显式类型 → 100（回归） | 通过（v16 新增；signatureType "eip191" 优先试 EIP-191） |
| 15 | 请求文档不可达（网关 404）→ 0 | 通过 |
| 16 | 请求文档超 64KB（70KB）→ 0 | 通过 |
| 17 | 请求文档 JSON 无效 → 0 | 通过 |
| 18 | 证据记录场景 2xx → 100 | 通过 |
| 19 | 证据 responseHash = keccak256(记录) | 通过（链上值与独立计算值一致，`0x635d950d…`） |
| 20 | 争议前 2xx → 100 | 通过 |
| 21 | 收到 ValidationDisputed 后重新检查并提交新结果 | 通过（endpoint 改成 404 后复核 score 变 0） |
| 22 | requestHash 公式与合约链上验算一致 | 通过（全部 validationRequest 均未 revert） |
| 23 | 默认轮询间隔 30 秒 | 通过（POLL_INTERVAL=30） |
| 24 | 轮询约 30 秒一轮（live 35 秒观测） | 通过（state.json 水位推进间隔 [30.0] 秒） |
| 25 | nonce 冲突重试 3 次成功 | 通过（进程内桩 RPC：前 2 次 `nonce too low`，第 3 次成功） |
| 26 | validatorAddress 不是当前验证者 → 忽略、不提交 | 通过（进程内桩 RPC：返回 None，0 次广播） |

## 说明与保留

- 第 21、22 项是进程内桩 RPC 测试，不是链上事件：链上根本发不出
  validatorAddress 错误的请求（合约会 revert），nonce 冲突也无法在
  anvil 上稳定复现；测的是服务里真实的重试与忽略分支代码。
- 测试中发现并已修复服务两个真问题（见下），修复后重跑 22/22 全过：
  1. `Account.sign_transaction` 拒收小写 `to` 地址——服务现对合约地址
     做校验和转换（生产地址本就是校验和格式，此修只为稳妥）。
  2. 失败事件后水位推进会把失败事件永久跳过——现只有区间内无新事件
     时才推进水位，失败事件下轮重试。
- 未在服务器上部署、未启动任何服务、未改服务器任何文件（只读查看）。
- 未测主网真实提交：主网提交须 L 在服务器上部署后由服务实际跑，
  上线后按计划 §11.3 做 V3 验证。
