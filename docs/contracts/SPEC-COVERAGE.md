# SPEC 12 测试清单对照

状态：逐项打勾。日期：2026-11-20。

`SPEC 12` 要求「D 提交测试时逐项打勾」。本文件是那张清单，每一条都指向实际测试函数。
全部 259 条测试通过。

---

## 单元

| # | 要求 | 测试 | 状态 |
| --- | --- | --- | --- |
| 1 | `abc.haha` 与 `abc.meme` 的 tokenId 不同，且等于 5.2 的向量 | `DeployTest.test_nodeVectors_abcHahaAndAbcMeme`、`test_tokenIdIsNode` | ✅ |
| 2 | 大写/连字符/空格/点/汉字/emoji/空串 revert `InvalidCharset` | `RegistrarMintTest.test_invalidCharset_reverts`、`test_emptyLabel_isInvalidCharset` | ✅ |
| 3 | 长度 0/1/2/3/32/33 在公众与管理员路径的结果 | `test_publicLength_*`（4 条）、`test_adminLength_*`（2 条） | ✅ |
| 4 | `trump` 加盐哈希等于向量；`btc` 不是黑名单也不是保留名 | `test_trump_blacklisted_vector`、`test_btc_notBlacklisted_notReserved_andMintable` | ✅ |
| 5 | `mao` 可公众铸造；`xi` 不能公众铸造但可 `adminMint`（原因是长度） | `test_mao_publicMint_ok`、`test_xi_publicBlockedByLength_adminAllowed` | ✅ |
| 6 | `binance` 公众失败，`adminMint` 成功，两个 TLD 各自独立 | `test_binance_publicFails_adminMintsBothTlds` | ✅ |
| 7 | 管理员不能 `adminMint("bitcoin", ...)` | `test_adminCannotMintPublicName` | ✅ |
| 8 | 没有 `.ai` 不能 `register`；三种失败方式都要测 | `test_noAi_cannotRegister`、`test_handleOfButOwnerOfHandleZero_rejected`、`test_ownerOfTokenIdMismatch_rejected` | ✅ |
| 9 | 冷却按 aiId 不按 TLD；3599 秒不能，3600 秒可以 | `test_cooldown_acrossTlds_3599sBlocked`、`test_cooldown_atExactly3600s_allowed` | ✅ |
| 10 | `register` 没有接收者参数，owner 是 `msg.sender` | `test_register_mintsToSender` | ✅ |
| 11 | 铸造不设置主名字，不激活 agent | `test_mintDoesNotSetPrimaryOrAgent` | ✅ |
| 12 | 同一天第 4 次铸造成功但只加 3 次；跨 TLD 合并；跨日清零；改 `mintReward` 仍只 3 次 | `test_mintReward_maxThreePerDay`、`test_mintReward_countsAcrossTlds`、`test_mintReward_resetsNextDay`、`test_mintReward_increasedStillThreeTimes` | ✅ |
| 13 | `name()` 是 `haha id`，`symbol()` 是 `HAHAID`；单枚 JSON `name` 是 `label.tld` | `DeployTest.test_collectionNameAndSymbol`、`SvgTest.test_tokenUriJsonNameIsFullName` | ✅ |
| 14 | 身份 NFT 的 `tokenURI` 是 `agentURI`，不是另一张 SVG | `IdentityTest.test_agentTokenUriIsAgentUri` | ✅ |
| 15 | 北京时间 07:59 与 08:00 落在相邻 day | `PointsTest.test_dayBoundary_beijing0759vs0800` | ✅ |
| 16 | 签到每天一次；参数为 0 时 revert 且不消耗当天 | `test_checkIn_oncePerDay`、`test_checkIn_disabled_doesNotConsumeDay` | ✅ |
| 17 | 社交领取与签到同条件；没 `.ai` / 没名字都失败且不消耗 | `test_socialClaims_sameEligibility`、`test_checkIn_requiresAi`、`test_checkIn_requiresHoldingName` | ✅ |
| 18 | `claimFollow` 每个 aiId 终身一次 | `test_claimFollow_onceLifetime` | ✅ |
| 19 | like/retweet/comment 各自每日一次，互不影响，和签到/follow 也互不影响 | `test_socialClaims_dailyIndependent`、`test_socialClaims_nextDay`、`test_socialClaims_independentFromCheckIn` | ✅ |
| 20 | 某项积分为 0 时领取 revert 且不标记已领 | `test_socialDisabled_doesNotConsume` | ✅ |
| 21 | 没有 `signer` / `setVoucherSigner` / EIP-712 | `test_noSignerNoEip712`、`AdminPowerTest.test_noSignerAnywhere` | ✅ |
| 22 | 卖掉最后一个名字后不能签到/领分；余额不变；再买回来又可以且仍记原 aiId | `test_soldLastNamelosesEligibility_balancePersists` | ✅ |
| 23 | 自评分失败；他人可打分/改分；改分不加 count；review >140 失败；review 只在事件 | `test_rate_selfFails`、`test_rate_editDoesNotIncreaseCount`、`test_rate_reviewTooLong`、`test_rate_reviewOnlyInEvent` | ✅ |
| 24 | 转让后：addr 覆盖 0、text 空、主名字空、agentOfName 0、旧 agent ownerOf revert、旧分数保留、新 agent 分数 0 | `TransferTest.test_transfer_clearsResolverRecords`、`test_transfer_clearsPrimaryName`、`test_transfer_burnsAgent`、`test_transfer_reputationResetsNewAgent` | ✅ |
| 25 | `addr` 无覆盖等于 NFT owner；有覆盖等于覆盖；转让后回落新 owner | `test_addr_fallsBackToNftOwner`、`test_addr_override`、`test_addr_clearOverride_fallsBackToOwner` | ✅ |
| 26 | 主名字要求当时 `addr(node) == msg.sender`；改走 addr 后旧主名字返回空 | `test_setPrimaryName_requiresAddrEqualsSender`、`test_primaryName_invalidAfterAddrMoved` | ✅ |
| 27 | 市场：未授权不能挂单；改价；取消；转让后 buy 失败且 clearStale 可清；value 必须等于价格；fee+proceeds==price；99 wei 失败、100 wei fee 为 1 | `MarketplaceTest`（`test_list_requiresApproval`、`test_updatePrice`、`test_cancel`、`test_buy_afterTransferFails_thenClearStale`、`test_buy_wrongValue`、`test_buy_feeAndProceedsSumToPrice`、`test_list_feeMustBePositive`） | ✅ |
| 28 | 市场不把 royaltyInfo 的金额再转一次；`royaltyInfo(tokenId,1 ether) == (feeReceiver, 0.01 ether)` | `test_buy_doesNotDoubleChargeRoyalty`、`RegistrarMintTest.test_royaltyInfo` | ✅ |
| 29 | `buy` 的收款合约在 `onERC721Received` 重入 `buy`/`withdraw` 不能把账做大 | `test_reentrancy_onBuyDoesNotInflate`、`test_reentrancy_onWithdrawDoesNotDouble` | ✅ |
| 30 | `withdraw` 先置零；卖家和 feeReceiver 各自只提自己的 | `test_withdraw_seller`、`test_withdraw_feeReceiver`、`test_withdraw_onlyOwn`、`test_withdraw_twiceFails` | ✅ |
| 31 | 三张 SVG 样例解码后与 `assets/svg/samples/` 字节相同；`abcdefghijklmnopqrs.haha` 的 y 是 260 | `SvgTest.test_svg_*_matchesSampleBytes`（3 条）、`test_baselineHalfEven_atN24` | ✅ |
| 32 | 部署者调三项管理员函数全部 revert；Policy 无写函数；bootstrap 第二次 revert；工厂没有成功的写调用 | `AdminPowerTest.test_deployerEoaHasNoAdminPower`、`test_policyHasNoWriters`、`test_bootstrapSecondCallFails`、`test_deployerHasNoExternalWriters` | ✅ |

---

## 模糊与不变式

| # | 要求 | 测试 | 状态 |
| --- | --- | --- | --- |
| 1 | 任意字节串，除全为 `a-z0-9` 且长度合法外不能铸造成功 | `FuzzTest.testFuzz_arbitraryBytesOnlyValidLabelsSucceed`（1000 runs）、`testFuzz_invalidCharsetAlwaysRejected`、`testFuzz_lengthBounds` | ✅ |
| 2 | 已铸 token 的 `registry.owner` 恒等于 NFT owner，resolver 恒为规范解析器 | `InvariantTest.invariant_registryOwnerMatchesNft` | ✅ |
| 3 | 黑名单词永远铸不出来，包括管理员路径 | `testFuzz_allBlacklistedWordsRejected`（1000 runs）、`invariant_noBlacklistedMinted` | ✅ |
| 4 | 积分：余额之和等于正向 PointsChanged 减扣分；`spend` 不能打成负数 | `invariant_pointsNeverNegative`、`invariant_pointsBalanceMatchesLedger`、`test_spend_insufficientBalance_reverts` | ✅ |
| 5 | 市场：待提现之和 <= 合约 BNB 余额 | `invariant_marketplaceSolvent` | ✅ |
| 6 | 不变量里加入随机转让、随机 setText、随机 rate、随机挂单 | `HahaHandler`（`transfer`/`setText`/`rate`/`list`/`buy`/`withdraw`/`claim`/`warp`） | ✅ |

---

## BSC 主网 fork

| # | 要求 | 测试 | 状态 |
| --- | --- | --- | --- |
| 1 | 区块上的字节码哈希等于第 4 节 | `ForkOfflineTest.test_fork_aiCodeHash`、`ForkOnlineTest.test_online_aiCodeHash` | ✅ |
| 2 | `alice` 的 owner、`handleOf`、`ownerOf(keccak256("alice"))`、`balanceOf == 1` | `test_fork_aliceClosedLoop`、`test_online_aliceClosedLoop`、`test_online_aliceTripleConsistency` | ✅ |
| 3 | `ownerOfHandle("Alice")` 和 `ownerOfHandle("alice.ai")` 为 0 | `test_fork_noNormalization`、`test_online_noNormalization` | ✅ |
| 4 | `vm.prank` 去转走 `alice`，revert `Soulbound()` | `test_fork_aliceIsSoulbound`（离线：断言失败）、`test_online_soulboundSelector`（在线：断言选择器 `0xa4420a95`） | ✅ |
| 5 | `vm.prank` alice 的 owner 能铸公众名字；同小时第二个 TLD 失败；warp 3600 后成功 | `test_fork_aliceOwnerCanMint`、`test_fork_cooldownAcrossTlds` | ✅ |
| 6 | `vm.prank` 一个 `handleOf` 为空的地址，`register` 失败 | `test_fork_noAiCannotMint` | ✅ |
| 7 | 只在 fork 上 `prank`，不广播 | `test_fork_usesPrankNotBroadcast`（结构性保证） | ✅ |

### 关于第 1 条与「固定区块」

`SPEC 12` 要求「固定一个区块」。实测区块 `134683411` 在公共 RPC 上返回
`missing trie node`（非归档节点）。因此按 `QUESTIONS` 第 11 条裁决改为：

- 冻结 `latest` 的字节码，**哈希写死断言**（`.ai` 不可升级，所以 `latest` 与目标区块是同一份代码）。
- 冻结的区块号、抓取时间、字节码哈希都记在 `test/fork/state/Meta.json` 与 `test/fork/FROZEN.md`。

这满足「哈希写进测试、不悄悄改期望值」的实质要求。

---

## 额外补充的测试（SPEC 未要求，但审计需要）

| 测试 | 为什么加 |
| --- | --- |
| `AdminPowerTest.test_adminCannotBlacklistAddress` | owner 硬性要求「不能拉黑地址」 |
| `test_adminCannotTouchUserNfts` | 「不能动用户的 NFT」 |
| `test_adminCannotPause` | 「不能暂停转账」 |
| `test_adminCannotChangeFee` | 「手续费和版税各 1%，写死在代码里」 |
| `test_adminCannotBeReplaced` | 「管理员部署后不可更换」 |
| `test_noEip1967Slots` | 「合约全部不可升级，不用代理合约」 |
| `test_noUpgrade` | 同上 |
| `test_policyHasNoWriters` | 「管理员只有三项权力」的反向验证 |
| `test_royaltyInfo_smallAmountRoundsToZero` | QUESTIONS 第 9 条的断言 |
| `test_dayZeroIsValid` | QUESTIONS 第 10 条 + 自审发现的签到 bug |
| `test_clearRecords_noopDoesNotRevert` | 转账钩子不得卡死用户 NFT |
| `test_deactivate_noAgent_isNoop` | 同上 |
| `test_transfer_bareToken_succeeds` | 同上 |
| `SvgTest.test_metadataRuntimeSizeUnderLimit` | `SVG.md` 的 24 KB 要求 |
| `DeployTest.test_bootstrapState` | `SPEC 13` 的 bootstrap 后状态 |
