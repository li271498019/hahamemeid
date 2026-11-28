# 09 测试矩阵

D 用 Foundry，沿用 `foundry.toml` 的 `via_ir`、fuzz 1000、invariant 128×48。新测试放在 `test/season1/`。不要为了本季去改旧合约的断言。下面每条都要有对应测试函数名，写进 PR 说明。未实现的函数不算通过。

固定块测试使用 `vm.roll` / `vm.warp`，不需要每天打主网。另有一组 fork 测试，只读，不广播。

## 单元：兑换

| 断言 | 期望 |
| --- | --- |
| 非 `.ai` 持有人 `applyFor` | `AiRequired`，余额不变，无订单 |
| 签名 recipient 与参数不一致 | `BadSignature` |
| 价格不是 200 | `BadPrice` |
| 三位名字、混合两位、大写 | `OutsidePool` |
| 两个后缀同一标签 | 两个不同 `tokenId`，可分别被不同 `.ai` 锁定 |
| 同一 `.ai` 第二笔，即使换名字 | `SeasonUsed` |
| 余额 199 | Merkle 不包含；若伪造叶，证明失败。直接 `spend` 余额不足时整笔回滚 |
| 不持有 `.haha/.meme` | `spend` 因 `NameRequired` 失败，订单不留下 |
| 名字已被 `adminMint` | `NameTaken` |
| 合约接收人 | 订单成功。不调用 `onERC721Received`。之后 `ownerOf` 仍不存在，直到管理员铸造 |
| 边界组 `remainingSlots == 2`，第三人 | `BoundaryFull`。前两笔的槽还在 |
| 18 个 Reserved 都不申请 | `remainingSlots` 仍是初始值，边界组不能因此变成 20 |
| 25 人同分 | 只有 20 笔成功，第 21 笔 `BoundaryFull` |
| 同块两笔边界申请 | 测试里顺序执行即 log 顺序。先调用者成功 |
| 窗口最后一秒成功，下一秒 | `BadTime` 或 `DayClosed` |
| `2026-12-09T00:00:00Z` | 不能再 `applyFor` |
| 成功后没有 cancel 函数 | 接口里不存在；低级调用失败 |
| 重放签名 | 第二笔失败，余额只减 200 一次 |
| ERC-1271 魔数正确 / 错误 | 成功 / `BadSignature` |
| 管理员调用不存在的 `spendFor` | 无此函数 |

并发同名：两笔不同 `.ai` 申请同一 `label+tld`。第一笔锁定，第二笔 `NameTaken`。用 `vm.prank` 顺序表示，不需要真实并行。

Gas：`applyFor` 在 11 层证明、标签 2 字节时记录 gas，断言上限。上限取首次实现的 120% 写进测试，防止以后把循环放进申请。不要为了好看去优化到某个拍脑袋数字。

## 单元：root 与快照

| 断言 | 期望 |
| --- | --- |
| 日界前最后一块只确认了 2 块，更早的块已超过深度 | `setDayRoot` 拒绝更早的块，也拒绝在最后一块未达标时公布 |
| 同一块达到深度后 | 只能用这一块的哈希 `setDayRoot` |
| root 之前该块被重组 | 按新主链重新锁定最后一块，不得沿用旧块 |
| 已有订单再 `setDayRoot` | `RootFrozen` |
| `reservedCount + remainingSlots > 20` | revert |
| 错误证明、错误 tier、错误余额 | `BadProof` |
| pending 的 ai 不在提交人A 的向量里 | 链下向量测试，见 `03` |

## 单元：验证与找错

| 断言 | 期望 |
| --- | --- |
| verdict 0 和 1 | 都是 30，`PointsChanged` delta 30 |
| 同一天第二笔 | 不增加余额 |
| 下一天同一 `.ai` | 再加 30，若窗口仍开放且有新任务包 |
| generation 不符或为 0 | `StaleGeneration`，余额不变 |
| burn 之后 generation 仍匹配 | 可以领。不要求 `isActive` |
| `earn` 返回 0（把全网预算设成 0 或已用尽） | `EarnNotPaid`，`verified` 仍为 false，随后把预算调高可以再领 |
| 撤掉 validator 后再用旧签名 | 失败 |
| `isMinted` 返回 true | `NameTaken` |
| `isMinted` 调用失败或返回不是 32 字节 | `NameCheckFailed`，没有订单 |
| `ownerOf` 的 revert 不是 `ERC721NonexistentToken` 加本 tokenId | 若测试这条备用路径，必须 `NameCheckFailed` |
| 任意地址调用旧的无权限 `confirmMint` | 无此函数 |
| 管理员 `attestFulfillment` 不传 tokenId | 状态可变 `Fulfilled`，事件里的 tokenId 等于订单 namehash |
| 当前所有者已不是接收人 | `currentOwnerMatches` 为 false，且不把已核对的日志凭证改掉 |
| 无 `.ai` 的 `commitFinding` | revert，无 commit |
| `reportEvidenceHash` 或 salt 为 0 | `ZeroCommit` |
| 两份报告并到同一根因 | 两份签名都验得过；只付最早一份被裁定为充分的报告；第二份 `CanonicalUsed` |
| 更早 commit 但揭示对不上哈希 | 不获得优先权 |
| 同块两条 commit | 测试记录交易序号和日志序号，不能只断言块号 |
| 同一人领两次 | 第二次失败，余额只加 100 |
| commit 本身 | 余额不变 |
| 未 `commit` 就 `claimFinding` | `UnknownCommit` |
| 尚未 `assignCanonical` | `CanonicalUnassigned`，签名即使有效也不发分 |
| `START_TS` / `END_TS` | 等于 `1795478400` / `1796774400`，测试不得改成验收完成日 |
| 把验证 `globalDailyPoints` 配成 `100000` | 旧 `setEarner` 成功。配成 `1000000` 或 `10000000` 都不是本季配置；后者必须 revert |
| `END_TS` 之后 `claimVerification` | 失败。同一时刻 `claimFinding` 若仍在公示后的 7 天内则成功。`claimAccidentCredit` 不受 `END_TS` 限制 |
| 找错 `earn` 返回 0 | `canonicalClaimed` 仍为 false，稍后同一签名可以再试 |
| 第二张事故补偿同一天 | 不被 `perUserDailyCap` 拒绝。同一 `orderId` 第二次补偿失败 |
| 事故在无 `.ai` 时 | 不调用 `refund`，债权仍绑定原 `aiId` 与原地址 |
| `earn` 补偿返回 0 | 200 已退回，补偿可稍后领，交易不整体回滚 |
| 仅管理员迟到 | 不发出 `AccidentDeclared`，不调用 `refund` |
| `AccidentRefunded` 再退一次 | revert，`spendable` 不增加第二遍 |
| `CreditOpen` 时再 `applyFor` | `SeasonUsed`。退分成功的下一笔才可以再占季名额 |
| 事故后当天 filled 计数 | 不减少，边界组不能因此多成功一笔 |
| `publishRuling` 晚于 commit 7 天 | revert，不能领 100 |
| 公示未满 24 小时就 `claimFinding` | revert。满 24 小时且未过随后 7 天则成功，即使已经超过 `END_TS` |
| 撤掉 validator 或 reward signer 之后用旧签名领奖 | `BadSignature` |
| `rewardsOpen = false` | 验证和找错领奖失败。`declareAccident` 仍可退分 |
| 盐错误 | `BadReveal` |

找错的「触顶后可重试」：先把 `globalDailyPoints` 设成 0 的配置在旧 Points 上是 `enabled` 且 `globalDailyPoints` 不能为 0（`setEarner` 要求大于 0）。测试用「先让别人把当日额度打满」来让 `earn` 返回 0。

## 不变量

处理器随机调用 `applyFor`、边界与保留两类用户、`claimVerification`、`commitFinding`、`claimFinding`。

- 所有 `Pending+Fulfilled` 的订单数 `<= 300`。
- 每一天 `reservedFilled + boundaryFilled <= 20`。
- `boundaryFilled <= remainingSlots`。
- 每个 `aiId` 至多一笔订单。
- 每个 `label+tld` 至多一笔订单。
- 模块地址的 BNB 余额始终为 0。
- Points 上该 reason 的负向 `delta` 之和等于 `200 * 订单数`。不要把这个不变量写成「积分被销毁」：分还在 Points 里，只是从用户转到了扣减。总供给减少 200 每单，这是 `spend` 的语义，不是转给国库。
- 验证成功次数 `<=` 有过成功 `earn` 的 `(aiId, day)` 数。找不到余额增加而不发 `Verified` 的路径。

`fail_on_revert = false` 与现有不变式测试一致，因为随机输入大多会 revert。

## Fork

`BSC_RPC_URL` 可选。无 URL 则 skip。

- 读主网 Points `admin()`、Registrar `admin()`，等于 `01` 的管理员。
- 读 `SEASON1_VERIFY` 的 `earner()` 在**未部署模块之前**是空。这条防止测试误连到已经配置的环境还以为自己部署了。
- 不要在 fork 上 `broadcast`。
- 用一个历史块重放本地导出的少量 `PointsChanged` 夹具，与 `balanceOf` 在该块的 `eth_call` 一致。夹具由提交人A 的复算工具生成，D 把夹具提交进 `test/season1/fixtures/`。在夹具落地前，fork 测试可以先 skip，但单元向量不能 skip。

## 明确不测成「公平已自动化」

不写「管理员无法提交错误 root」这种断言。错误 root 在无订单时能写上链。测试应断言：公开向量与错误 root 不一致时，**诚实叶的证明失败**；以及有订单后不能改 root。
