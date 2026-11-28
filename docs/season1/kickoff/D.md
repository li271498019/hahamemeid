# D 的任务书

## 负责人、范围、必读

负责人：D。

范围：新的赛季模块、Foundry 测试、部署脚本、部署授权面板、ABI 与地址交接。不做运营发放站，不做网站，不做索引器。

必读，按顺序：

1. [README.md](README.md)
2. [../00-parameters.md](../00-parameters.md)、[../02-module-abi.md](../02-module-abi.md)、[../09-test-matrix.md](../09-test-matrix.md)、[../12-accident.md](../12-accident.md)
3. [../01-baseline.md](../01-baseline.md)、[../03-snapshot-merkle.md](../03-snapshot-merkle.md)、[../04-authorization.md](../04-authorization.md)、[../05-daily-verification.md](../05-daily-verification.md)、[../06-findings.md](../06-findings.md)、[../07-deploy-panel.md](../07-deploy-panel.md)、[../10-deploy-checklist.md](../10-deploy-checklist.md)
4. [shared-schema.md](shared-schema.md)、[e2e.md](e2e.md)

`07` 里的发放另一屏不是你的面板。那是 A 的 `tools/season1/ops/`。

## 分支

L 把文档 PR 合并进 `main` 之后：

```sh
git fetch origin main
git checkout -b d/season1-contracts origin/main
```

合并前只读 `cursor/season1-d-docs-a3d0` 上的文档。不要从当时的 `main` 开分支，那时还没有 `docs/season1/`。不要把实现提交推回 `cursor/season1-d-docs-a3d0`。

## 可改与禁改

可改或计划新增：

- `src/HahaSeason1.sol`
- 仅当 `via_ir` 后运行时字节码超过 24576：再新增 `src/HahaSeason1Exchange.sol` 与 `src/HahaSeason1Rewards.sol`，函数签名仍按 `02`
- `test/Season1.t.sol`，以及其它 `test/Season1*.t.sol`
- `script/Season1.s.sol`
- `tools/deploy-panel/season1.html`、`season1.js`、`season1-encode.mjs`
- `tools/deploy-panel/public/season1/`
- `tools/deploy-panel/index.html` 里只加一个到 `season1.html` 的链接

禁改：

- 现有 `src/` 里十个合约、`src/libraries/`、`src/interfaces/`
- 现有 `test/*.t.sol`、`script/Deploy.s.sol`
- `tools/deploy-panel/app.js` 和现有十合约步骤
- `indexer/**`、`web/**`、`tools/season1/**`
- `docs/season1/00` 至 `12` 的数字
- 任何私钥、`.env`、助记词

## 工作包

### D-1 模块与常量

输入：`02` 的常量和 `00` 的表。  
输出：计划新增的 `src/HahaSeason1.sol`。  
依赖：无。可与 A、C 并行。  
边界：`END_TS = 1796774400` 只进 `applyFor` 和 `claimVerification`。`commitFinding` 也必须早于它。`publishRuling`、`claimFinding`、`declareAccident`、`claimAccidentCredit` 不读它。验证全网 `100000`，找错全网 `10000`，事故全网 `10000`，事故 `perUserDailyCap = 50` 只因为旧字段最大是 50。  
验收：构造参数里的 Points、Registrar、Identity、`.ai` 是 `01` 的主网地址。`snapshotConfirmations` 主网为 15。没有 `receive`，没有 `selfdestruct`。

### D-2 兑换、nonce、签名

输入：`03`、`04`。  
输出：`applyFor`、`setDayRoot`。  
依赖：D-1。  
边界：成功才增加 `nonces[aiId]`。失败整笔回滚。用户签名不能由第二个人代发。不实现公开的 `refund(user, amount)`。  
验收：E3、E4。重放第二笔 `BadNonce`。改 recipient 而签名不变则失败。

### D-3 验证、找错、撤销

输入：`05`、`06`、`04`。  
输出：`claimVerification`、`commitFinding`、`assignCanonical`、`publishRuling`、`claimFinding`、`setValidator`、`setRewardSigner`。  
依赖：D-1。  
边界：`earn` 返回 0 则整笔回滚，不写 `verified` 或 `canonicalClaimed`，nonce 不变。撤掉签名人后旧签名立即 `BadSignature`，没有宽限。公示未满 24 小时不能领。只发 `FulfillmentAttested`，不发 `MintConfirmed`。  
验收：E7、E8、E11，以及 [fixtures/failures.json](fixtures/failures.json) 里 `where = chain` 的每一条。

### D-4 事故

输入：`12` 和 `02` 的「退款只走事故」。  
输出：`declareAccident`、`claimAccidentCredit`。  
依赖：D-2。  
边界：先 `refund` 200。补偿 `earn` 返回 0 不回滚这笔退分。同一订单第二次 `refund` 失败。债权留在原 `aiId` 和原 `applicant`。`seasonOrderOf` 只在 200 已经退回后清除。当天 filled 不减少。已铸出或在途 `adminMint` 未清掉时不能宣布。管理员迟到不走这里。  
验收：E10。

### D-5 测试

输入：`09`。  
输出：`forge test --match-contract Season1` 的源码。不要把 `out/` 提交进 git，`.gitignore` 已经忽略它。  
依赖：D-1 至 D-4。  
验收：`09` 的表和 E1 的 `SnapshotTooFresh`。原有 `forge test` 仍通过。字节码大小写进 PR。超过 24576 就拆合约，不删检查。

### D-6 部署授权面板

输入：`07` 的第 1 至 9 步，但第 9 步默认不可点，直到 `10` 的验收门。发放清单不在这个面板。  
输出：计划新增的 `season1.html`、`season1.js`、`season1-encode.mjs`。  
依赖：D-5 的 ABI。  
边界：本地 `http://localhost:4321` ，沿用现有面板的钱包签名。不读取、不保存私钥。日奖公钥为空时 `setValidator` 按钮不可用。三笔 `setEarner` 的数字写死为 `02` 的值，拒绝 `1000000` 和 `10000000`。没有 `adminMint` 按钮，没有 multicall。  
验收：anvil 上能走完部署、`setSpender`、`setSpenderBudget(200, 4000)` 和三笔 `setEarner`。这些交易留在本地链。

### D-7 交给 A

输入：D-5 的 ABI。  
输出：`tools/deploy-panel/public/season1/HahaSeason1.abi.json` 和 `handoff.json`，形状见 [shared-schema.md](shared-schema.md)。  
依赖：D-5。  
验收：`events` 含 [fixtures/events.json](fixtures/events.json) 的赛季事件名，且不含 `MintConfirmed`。`mainnet.module` 为 `null`。PR 正文贴 anvil 地址和字节码大小。A 做安全审查之前，不把这个 PR 标成可以上主网。

## 产物和 PR

一个 PR，基线 `main`，标题说明只含合约、测试和部署授权面板。PR 里写明：没有主网交易，没有私钥，没有修改旧合约。请 A 审查重放、双退和排队。不要自己合并到主网发布流程。

## 不能做

- 不部署主网，不打开 `redeemOpen` / `rewardsOpen`。
- 不改已部署的 Points 或 Registrar，不新增积分代币。
- 不做发放站，不把 `adminMint` 放进部署面板。
- 不实现批量铸造。
- 不保存管理员私钥或日奖私钥。
- 不改业务数字，不把事故次数写成「每天 5 次」或「每天 50 次」的产品规则。
- 不代替 A 写索引器或签名服务。
