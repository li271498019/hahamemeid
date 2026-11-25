# G13 验证注册表（HahaValidation）— 合约测试报告

> 作者：D。日期：2026-11-25。按 `docs/contracts/validation-registry-plan.md`（已冻结·审计修订版）§11.1 执行 T1–T6。

## 1. 交付物

| 项 | 文件 | 说明 |
| --- | --- | --- |
| 合约 | `src/HahaValidation.sol` | EIP-8004 Validation Registry 接口 + v1 新增 dispute/setValidator |
| 部署脚本 | `script/DeployValidation.s.sol` | 构造参数 admin + identity，dry-run 已验证 |
| 测试 | `test/validation/HahaValidation.t.sol` | T1–T6，30 个测试 |

## 2. 合约概览

- **管理员**：`admin`（immutable，部署时写死为 HahaRegistrar 的 admin `0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7`）。
- **验证者**：`validator`（public 存储变量，初始 = admin），管理员可调 `setValidator` 更换。
- **identity**：`identity`（immutable，HahaAgentIdentity 地址 `0x54A70BF81B288d41013D7b57c2Db0922f1E1a4d4`），`validationRequest` 用它做 owner/operator 判断。
- **争议窗口**：`DISPUTE_WINDOW = 3 days`（常量）。
- **requestHash 公式（§3.4）**：`keccak256(abi.encodePacked(validatorAddress, agentId, requestURI))`，合约链上验算，不符 revert。

## 3. T1–T6 测试结果

全部通过（`forge test --match-path test/validation/HahaValidation.t.sol`）。

| # | 测试 | 通过标准 | 结果 |
| --- | --- | --- | --- |
| T1 | 接口签名核对 | 6 个标准函数 + 2 个标准事件 + v1 新增 dispute/setValidator/ValidationDisputed 的 selector/topic0 逐字核对 | ✅ 通过（`test_T1_interface_signatures`） |
| T2 | 验证者限制 | 非管理员调 validationResponse revert；请求指定非验证者 revert；管理员 setValidator 可换、非管理员 revert、零地址 revert；换后旧验证者 revert、新验证者可调 | ✅ 通过（6 个测试） |
| T3 | 验证请求 | owner 可请求；operator 可请求；非 owner/operator revert；requestHash 与公式不符 revert；重复 requestHash revert | ✅ 通过（5 个测试） |
| T4 | 验证结果 | 管理员回应成功（0–100）；response>100 revert；不存在 requestHash 回应 revert；多次回应覆盖 | ✅ 通过（4 个测试） |
| T5 | 争议复核 | 争议后相同结果维持原判；不同结果改判；读接口返回最新；二次 dispute revert；超 3 天 revert；无结果 dispute revert；第三方可 dispute；整点边界含、超 1 秒 revert；更新结果不延长窗口 | ✅ 通过（9 个测试） |
| T6 | 读接口 | getValidationStatus 六字段一致；getSummary count/average（整数除法）+ validator/tag 过滤；getAgentValidations；getValidatorRequests；getIdentityRegistry | ✅ 通过（5 个测试） |

**合计：30 个测试，30 通过，0 失败。**

## 4. 完整测试套件

新增验证测试后，全仓测试套件：

```
forge test  → 381 通过 / 0 失败 / 10 跳过（391 总）
```

（新增 30 个验证测试；此前基线 351 通过。）

## 5. 边界测试覆盖（§11.1 明确要求的边界）

| 边界场景 | 测试 | 结果 |
| --- | --- | --- |
| 争议窗口整点含（`firstResponseTime + 3 天` 整点可争议） | `test_T5_disputeAtExactWindowBoundarySucceeds` | ✅ |
| 超 1 秒 revert（`+ 3 天 + 1 秒` revert） | `test_T5_disputeOneSecondPastWindowReverts` | ✅ |
| operator 可请求 | `test_T3_operatorCanRequest` | ✅ |
| 非管理员调 setValidator revert | `test_T2_nonAdminCannotSetValidator` | ✅ |
| 重复 requestHash revert | `test_T3_duplicateRequestHashReverts` | ✅ |
| 不存在的 requestHash 回应 revert | `test_T4_respondNonexistentRequestHashReverts` | ✅ |
| 更新结果不延长争议窗口 | `test_T5_updateResultDoesNotExtendWindow` | ✅ |

## 6. 部署脚本验证

`script/DeployValidation.s.sol` 已在本地 anvil 完成 dry-run + 广播验证：

```
HahaValidation deployed at: 0x5FbDB2315678afecb367f032d93F642f64180aa3
  admin    : 0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7
  identity : 0x54A70BF81B288d41013D7b57c2Db0922f1E1a4d4
  validator: 0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7
  DISPUTE_WINDOW: 259200 seconds
```

读接口 smoke test 全部正确（admin / validator / getIdentityRegistry / DISPUTE_WINDOW）。

## 7. 测试网部署说明

按 L 确认（2026-11-25）：测试网 T1–T6 用本地 forge 测试（mock identity）已充分覆盖；测试网正式上链广播等 L 批准主网部署时（§15 步骤 3）一并进行，或按需单独在测试网（chainId 97）广播。

> 本报告对应的合约源码、测试、部署脚本见本 PR。主网部署需 L 批准（§15 步骤 3），部署后按 §15 步骤 4 做 BscScan 开源验证，C 核对地址与接口。
