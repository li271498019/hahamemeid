# 第一季合约开发文档（给 D）

状态：业务规格 v1.0。提交人A 只写文档，不含生产合约，不含网站业务脚本。未授权部署。是否合并文档 PR 由 L 决定，本任务不代合并。本地测试可以做。主网签名仍等管理员。安全问题以后仍可修。

开工入口：[kickoff/README.md](kickoff/README.md)。A、C、D 的任务书、文件所有权和夹具都在那里。`00` 至 `12` 的业务数字不因开工文档而改变。

上线顺序和停点：[launch-runbook.md](launch-runbook.md)。那份文件不改上面的业务数字。部署必须使用里面写明的提交，不要盲拉当时的 `main`。

源码基线：`0942b75e792246a6376a96b760d185e2e803f1f9`（提交人A，`origin/main` 与本地一致）。旧合约已部署且不可升级，禁止重部署、替换或迁移现有十个合约，禁止新的积分合约或积分代币。

L 于北京时间 2026-11-23 11:07 把赛季改为 **15 天**。全文以 15 为准。14 天、280 单、2026-12-08 截止都已作废。更早的画布或聊天若仍写 14，以本目录为准。

## 修订（质量复核，仍不实现）

相对初稿，只改文档：

1. 找错承诺改为 `abi.encode(chainId, module, seasonId, aiId, reportEvidenceHash, salt)`。原始报告哈希与复核后的根因 id 分开。签名不包含根因 id，合并根因不会使原签名无法验过。优先权是最早一份被裁定为充分的证据，不是更早的空承诺。
2. 未铸造只认 `HahaRegistrar.isMinted` 的干净 `false`。`ownerOf` 只有精确的 `ERC721NonexistentToken(tokenId)` 才能当未铸造，其它失败一律终止。链下 403 不是未铸造。
3. 快照必须先锁定「时间戳不晚于日界的最后一块」，再等这一块达到确认深度。不得为了凑深度改用更早的块。
4. 链上不再用「当前 owner 等于接收人」把订单标成已发放。网站凭证是该订单 namehash 上的 `NameMinted` 加 `Transfer(from=0, to=接收人)`。链上只保留管理员对 `mintTxHash` 的声明，且函数不接收外部传入的 tokenId。
5. 「不退款」只覆盖两件已批准的事：用户成功后不能自己取消或换名；管理员超时只补发、不退款、不重扣、不占新日名额。错误 root 等异常若已扣分，停新单并交给 L，不写成已经批准永不退款。11:30 之后，无法履约并按 `12` 宣布的事故可以退 200 并另补 100。那不是把所有异常都自动退掉。
6. 合成一个 `HahaSeason1` 是设计建议，不是 L 的强制要求。开季时刻前验收没过就不得打开兑换。日期不顺延、不补回已经过去的窗口。

L 于北京时间 2026-11-23 11:28 把每日验证全网预算定为 `100000`（3333 笔，余 10），不是 100 万或 1000 万。11:30 批准 t32 的十行。冻结记录在 `11`。`END_TS` 不切断跨季找错和事故债权。上一轮没有写进 t32 的「事故每天 5 次」和「另加 1 个块间隔」没有被说成已经批准。

## D 怎么读

按文件编号实现。拟议 ABI 在 `02`。与旧 `HahaPoints` 的调用方式以 `02` 的「旧接口核对」为准，不要改旧合约。

| 文件 | 内容 |
| --- | --- |
| [00-parameters.md](00-parameters.md) | v1.0 参数总表、变更史、技术映射 |
| [01-baseline.md](01-baseline.md) | commit、地址、旧 ABI、不可迁移 |
| [02-module-abi.md](02-module-abi.md) | 最小新模块、全部拟议 ABI、状态机、与旧 Points 的配置 |
| [03-snapshot-merkle.md](03-snapshot-merkle.md) | 快照、Merkle、资格、边界同分、重组 |
| [04-authorization.md](04-authorization.md) | EIP-712 / ERC-1271、重放、禁止后台任意扣分 |
| [05-daily-verification.md](05-daily-verification.md) | 每日验证 30 分 |
| [06-findings.md](06-findings.md) | 找错 100 分、去重、跨季揭示和领奖 |
| [07-deploy-panel.md](07-deploy-panel.md) | 部署面板：只签名，不录私钥；业务发放逐笔签 |
| [08-fulfillment-api.md](08-fulfillment-api.md) | 订单汇总、模拟、广播、确认；索引与 API |
| [09-test-matrix.md](09-test-matrix.md) | Foundry 测试矩阵 |
| [10-deploy-checklist.md](10-deploy-checklist.md) | 主网顺序、验收门、故障；分工 |
| [11-open-decisions.md](11-open-decisions.md) | 11:30 冻结的十行，以及仍只是上线填数的项 |
| [12-accident.md](12-accident.md) | 特殊事故退 200 并另补 100 |
| [kickoff/README.md](kickoff/README.md) | A、C、D 开工入口。不改上面的业务数字 |

## 分工

- 提交人A：本目录、复杂网站、索引器、复算工具、设计，并 review C。
- D：按本目录实现合约、测试、部署面板扩展，以及复杂底层测试。不把合约交给别人。
- C：只做简单页面、文案和清单，提交人A review。不做重组、Merkle、签名或索引器迁移。
- B：不参与开发，不排任务。
- L：总决策。v1.0 的产品规则已经冻结在 `00` 和 `11`。仍留空的只有日奖公钥、实铸库存和主网管理员签名。安全问题以后仍可修。

## 明确不做

- 不改、不重部署 `HahaPoints`、`HahaRegistrar` 及其他已部署合约。
- 不新增积分代币，不把赛季分记到新账本。
- 不实现批量 `adminMint`，不承诺一笔签名铸出 20 个名字，不用 multicall 代铸。
- 不把链下签名或中心校验说成 ERC-8004 标准兼容或去中心化证明。
- 不在本 PR 里实现上述功能。
