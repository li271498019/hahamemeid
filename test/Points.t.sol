// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {HahaTestBase} from "./HahaTestBase.sol";
import {HahaPoints} from "src/HahaPoints.sol";
import {HahaRegistrar} from "src/HahaRegistrar.sol";
import {HahaConstants} from "src/libraries/HahaConstants.sol";

/// @notice 给 `HahaPoints.setSpender` 用的最小合约，用于测授权检查。
contract SpenderContract {
    function ping() external pure returns (bool) {
        return true;
    }
}

/// @title PointsTest
/// @notice SPEC 12「单元」清单里的积分部分：签到、社交领取、铸造奖励、spend/refund 限额。
contract PointsTest is HahaTestBase {
    bytes32 internal aliceAiId;
    bytes32 internal bobAiId;

    function setUp() public override {
        super.setUp();
        aliceAiId = keccak256(bytes("alice"));
        bobAiId = keccak256(bytes("bob"));
    }

    /// @dev 授权 spender 并给它设一个宽松的每日预算（补充规格 1.2：spend 要求 spender 有预算）。
    function _setSpenderWithBudget(SpenderContract sp) internal {
        vm.startPrank(ADMIN);
        points.setSpender(address(sp), true);
        points.setSpenderBudget(
            address(sp),
            HahaPoints.SpenderBudget({perUserDailyPoints: 1_000_000, globalDailyPoints: 100_000_000})
        );
        vm.stopPrank();
    }

    // =====================================================================
    // 日界（SPEC 5.1）
    // =====================================================================

    /// @notice 北京时间 07:59 和 08:00 落在相邻的两个 day。
    /// @dev UTC 日界 = `block.timestamp / 86400`。北京时间 = UTC+8，
    ///      所以北京时间 08:00:00 == UTC 00:00:00 == 日界。
    ///      用 `block.timestamp` 的倍数断言，不用链下时区库。
    function test_dayBoundary_beijing0759vs0800() public {
        // 选一个确定的 UTC 零点：第 20000 天。
        uint256 utcMidnight = 20000 * 86400;

        // 北京时间 07:59:59 = UTC 前一天 23:59:59
        vm.warp(utcMidnight - 1);
        uint256 dayBefore = points.currentDay();

        // 北京时间 08:00:00 = UTC 当天 00:00:00
        vm.warp(utcMidnight);
        uint256 dayAfter = points.currentDay();

        assertEq(dayBefore, 19999, "07:59 is previous day");
        assertEq(dayAfter, 20000, "08:00 is new day");
        assertEq(dayAfter, dayBefore + 1, "adjacent");
    }

    /// @notice `currentDay()` == `block.timestamp / 86400`。
    function test_currentDay_formula() public {
        // 用 86400 的整数倍，避免编译器把常量除法折叠成有理数。
        uint256 ts = 1428 * 86400;
        vm.warp(ts);
        assertEq(points.currentDay(), 1428);
    }

    // =====================================================================
    // 签到
    // =====================================================================

    /// @notice 签到加 `checkInPoints`，默认 30。
    function test_checkIn_awardsDefault() public {
        _register(alice, "abc", 0);

        assertEq(points.balanceOf(aliceAiId), 10, "mint reward 10 first");

        vm.prank(alice);
        points.checkIn();

        assertEq(points.balanceOf(aliceAiId), 40, "10 + 30");
    }

    /// @notice 同一天第二次签到必须 revert。
    function test_checkIn_oncePerDay() public {
        _register(alice, "abc", 0);

        vm.prank(alice);
        points.checkIn();

        vm.prank(alice);
        vm.expectRevert(HahaPoints.AlreadyCheckedInToday.selector);
        points.checkIn();
    }

    /// @notice 跨日后可以再签（不用连续签到）。
    function test_checkIn_nextDayWorks() public {
        _register(alice, "abc", 0);

        vm.prank(alice);
        points.checkIn();

        vm.warp(block.timestamp + 86400);
        vm.prank(alice);
        points.checkIn();

        assertEq(points.balanceOf(aliceAiId), 10 + 30 + 30);
    }

    /// @notice `checkInPoints == 0` 时签到 revert `CheckInDisabled`，且**不消耗今天**。
    function test_checkIn_disabled_doesNotConsumeDay() public {
        _register(alice, "abc", 0);

        vm.prank(ADMIN);
        points.setPointParams(0, 10, 30, 10, 10, 10); // 关闭签到

        vm.prank(alice);
        vm.expectRevert(HahaPoints.CheckInDisabled.selector);
        points.checkIn();

        // 没记今天：把参数改回来，当天就能签。
        vm.prank(ADMIN);
        points.setPointParams(30, 10, 30, 10, 10, 10);

        vm.prank(alice);
        points.checkIn();
        assertEq(points.balanceOf(aliceAiId), 40, "10 + 30");
    }

    /// @notice 没有 `.ai` 不能签到，且不消耗次数。
    function test_checkIn_requiresAi() public {
        address noAi = makeAddr("noAi");
        vm.prank(noAi);
        vm.expectRevert(HahaPoints.AiRequired.selector);
        points.checkIn();
    }

    /// @notice 有 `.ai` 但没有名字不能签到。
    function test_checkIn_requiresHoldingName() public {
        vm.prank(alice);
        vm.expectRevert(HahaPoints.NameRequired.selector);
        points.checkIn();
    }

    /// @notice 失败不消耗次数：没名字失败后，铸个名字就能签。
    function test_checkIn_failureDoesNotConsume() public {
        vm.prank(alice);
        vm.expectRevert(HahaPoints.NameRequired.selector);
        points.checkIn();

        _register(alice, "abc", 0);

        vm.prank(alice);
        points.checkIn();
        assertEq(points.balanceOf(aliceAiId), 40);
    }

    // =====================================================================
    // 社交领取（伪验证）
    // =====================================================================

    /// @notice `claimFollow` 终身一次。
    function test_claimFollow_onceLifetime() public {
        _register(alice, "abc", 0);

        vm.prank(alice);
        points.claimFollow();
        assertEq(points.balanceOf(aliceAiId), 10 + 30);

        // 过很多天也不能再领
        vm.warp(block.timestamp + 86400 * 365);
        vm.prank(alice);
        vm.expectRevert(HahaPoints.FollowAlreadyClaimed.selector);
        points.claimFollow();
    }

    /// @notice like/retweet/comment 各自每个 UTC 日一次，互不影响。
    function test_socialClaims_dailyIndependent() public {
        _register(alice, "abc", 0);

        vm.startPrank(alice);
        points.claimLike();
        points.claimRetweet();
        points.claimComment();
        vm.stopPrank();

        // 10 + 10 + 10 + 10 = 40
        assertEq(points.balanceOf(aliceAiId), 40);

        // 同一天第二次全部失败
        vm.startPrank(alice);
        vm.expectRevert(HahaPoints.AlreadyClaimedToday.selector);
        points.claimLike();
        vm.expectRevert(HahaPoints.AlreadyClaimedToday.selector);
        points.claimRetweet();
        vm.expectRevert(HahaPoints.AlreadyClaimedToday.selector);
        points.claimComment();
        vm.stopPrank();
    }

    /// @notice 跨日（day + 1）之后三项又能领。
    function test_socialClaims_nextDay() public {
        _register(alice, "abc", 0);

        vm.startPrank(alice);
        points.claimLike();
        points.claimRetweet();
        points.claimComment();
        vm.stopPrank();

        vm.warp(block.timestamp + 86400);

        vm.startPrank(alice);
        points.claimLike();
        points.claimRetweet();
        points.claimComment();
        vm.stopPrank();

        assertEq(points.balanceOf(aliceAiId), 10 + 30 + 30);
    }

    /// @notice 社交领取和签到互不影响。
    function test_socialClaims_independentFromCheckIn() public {
        _register(alice, "abc", 0);

        vm.startPrank(alice);
        points.checkIn();
        points.claimLike();
        vm.stopPrank();

        assertEq(points.balanceOf(aliceAiId), 10 + 30 + 10);

        // 签到已用掉今天，但 like 也用了今天；两者各自记账。
        vm.prank(alice);
        vm.expectRevert(HahaPoints.AlreadyCheckedInToday.selector);
        points.checkIn();

        vm.prank(alice);
        vm.expectRevert(HahaPoints.AlreadyClaimedToday.selector);
        points.claimLike();

        // 但 retweet 还没领
        vm.prank(alice);
        points.claimRetweet();
    }

    /// @notice 某一项为 0 时，对应领取 revert，且不标记为已领。
    function test_socialDisabled_doesNotConsume() public {
        _register(alice, "abc", 0);

        vm.prank(ADMIN);
        points.setPointParams(30, 10, 0, 10, 0, 10); // follow=0, like=0

        vm.prank(alice);
        vm.expectRevert(HahaPoints.SocialDisabled.selector);
        points.claimFollow();

        vm.prank(alice);
        vm.expectRevert(HahaPoints.SocialDisabled.selector);
        points.claimLike();

        // 没被标记：改回来就可以领
        vm.prank(ADMIN);
        points.setPointParams(30, 10, 30, 10, 10, 10);

        vm.prank(alice);
        points.claimFollow();
        vm.prank(alice);
        points.claimLike();

        assertEq(points.balanceOf(aliceAiId), 10 + 30 + 10);
    }

    /// @notice 社交领取的参与条件与签到相同。
    function test_socialClaims_sameEligibility() public {
        address noAi = makeAddr("noAi");
        vm.prank(noAi);
        vm.expectRevert(HahaPoints.AiRequired.selector);
        points.claimFollow();

        // 有 .ai 没名字
        vm.prank(alice);
        vm.expectRevert(HahaPoints.NameRequired.selector);
        points.claimFollow();
    }

    /// @notice `day 0` 是合法日序号，不能把「从未领取」存成 day 0。
    function test_dayZeroIsValid() public {
        // timestamp = 0 => day 0
        vm.warp(0);
        _grantNameDirectly(alice, "abc");

        vm.prank(alice);
        points.claimLike();
        assertEq(points.balanceOf(aliceAiId), 10, "only like");

        // 同一天（day 0）第二次必须失败
        vm.prank(alice);
        vm.expectRevert(HahaPoints.AlreadyClaimedToday.selector);
        points.claimLike();

        (uint64 dayIndex, bool done) = points.likeClaim(aliceAiId);
        assertEq(dayIndex, 0, "day index 0");
        assertTrue(done, "done");
    }

    // =====================================================================
    // 卖掉名字之后的行为
    // =====================================================================

    /// @notice 卖掉最后一个名字后不能签到，也不能领社交分；积分余额不变。
    /// @notice 再买一个名字后又能领，余额仍记在原来的 aiId 上。
    function test_soldLastNamelosesEligibility_balancePersists() public {
        _register(alice, "abc", 0);
        uint256 tokenId = uint256(_node("abc", 0));

        vm.prank(alice);
        points.checkIn();
        uint256 balBefore = points.balanceOf(aliceAiId);
        assertEq(balBefore, 40);

        // 转走名字
        vm.prank(alice);
        registrar.transferFrom(alice, bob, tokenId);

        // 余额还在
        assertEq(points.balanceOf(aliceAiId), balBefore, "balance persists");

        // 但不能签到/领分
        vm.prank(alice);
        vm.expectRevert(HahaPoints.NameRequired.selector);
        points.checkIn();

        vm.prank(alice);
        vm.expectRevert(HahaPoints.NameRequired.selector);
        points.claimLike();

        // 再买回来（bob 转回）
        vm.prank(bob);
        registrar.transferFrom(bob, alice, tokenId);

        // 又能签到（同一天已经不签过了，换一天）
        vm.warp(block.timestamp + 86400);
        vm.prank(alice);
        points.checkIn();
        assertEq(points.balanceOf(aliceAiId), balBefore + 30, "same aiId");
    }

    // =====================================================================
    // 铸造奖励：每天 3 次
    // =====================================================================

    /// @notice 同一天第 4 次铸造仍然成功，但积分只加了 3 次。
    /// @dev 冷却 3600 秒，所以要 warp 才能连铸 4 个。
    function test_mintReward_maxThreePerDay() public {
        _register(alice, "aaa", 0);
        assertEq(points.balanceOf(aliceAiId), 10, "1st reward");

        _skipCooldown(alice, "alice");
        _register(alice, "bbb", 0);
        assertEq(points.balanceOf(aliceAiId), 20, "2nd reward");

        _skipCooldown(alice, "alice");
        _register(alice, "ccc", 0);
        assertEq(points.balanceOf(aliceAiId), 30, "3rd reward");

        // 第 4 次：铸造成功，但没有奖励
        _skipCooldown(alice, "alice");
        _register(alice, "ddd", 0);
        assertEq(points.balanceOf(aliceAiId), 30, "4th mint: no reward");

        // NFT 确实铸出来了
        assertEq(registrar.ownerOf(uint256(_node("ddd", 0))), alice);
    }

    /// @notice 次数跨两个 TLD 合并。
    function test_mintReward_countsAcrossTlds() public {
        _register(alice, "aaa", 0); // 1
        _skipCooldown(alice, "alice");
        _register(alice, "aaa", 1); // 2
        _skipCooldown(alice, "alice");
        _register(alice, "bbb", 0); // 3
        _skipCooldown(alice, "alice");
        _register(alice, "bbb", 1); // 4 => no reward

        assertEq(points.balanceOf(aliceAiId), 30, "only 3 rewards");
    }

    /// @notice 次数跨 UTC 日清零。
    function test_mintReward_resetsNextDay() public {
        _register(alice, "aaa", 0);
        _skipCooldown(alice, "alice");
        _register(alice, "bbb", 0);
        _skipCooldown(alice, "alice");
        _register(alice, "ccc", 0);
        assertEq(points.balanceOf(aliceAiId), 30);

        // 跨日：跳到下一个 UTC 日界的整点，而不是简单加 86400。
        // 简单加 86400 只保证过了 24 小时；如果当前时间已经越过日界，
        // 加 86400 会落在同一 day 的后半段，跨不了日。
        vm.warp(_nextUtcDayStart());

        _skipCooldown(alice, "alice");
        _register(alice, "ddd", 0);
        assertEq(points.balanceOf(aliceAiId), 40, "new day, reward again");
    }

    /// @notice `mintReward = 0` 时不发奖，也不占用当日次数。
    function test_mintRewardZero_doesNotConsumeCount() public {
        vm.prank(ADMIN);
        points.setPointParams(30, 0, 30, 10, 10, 10);

        _register(alice, "aaa", 0);
        assertEq(points.balanceOf(aliceAiId), 0, "no reward");
        assertEq(points.mintRewardsToday(aliceAiId), 0, "count not consumed");

        // 打开奖励后，当天仍能拿满 3 次
        vm.prank(ADMIN);
        points.setPointParams(30, 10, 30, 10, 10, 10);

        _skipCooldown(alice, "alice");
        _register(alice, "bbb", 0);
        assertEq(points.balanceOf(aliceAiId), 10);

        _skipCooldown(alice, "alice");
        _register(alice, "ccc", 0);
        _skipCooldown(alice, "alice");
        _register(alice, "ddd", 0);
        assertEq(points.balanceOf(aliceAiId), 30, "3 rewards in the same day");
    }

    /// @notice 把 `mintReward` 改成 20 之后，一天仍然只发 3 次（当天上限 60）。
    function test_mintReward_increasedStillThreeTimes() public {
        vm.prank(ADMIN);
        points.setPointParams(30, 20, 30, 10, 10, 10);

        _register(alice, "aaa", 0);
        _skipCooldown(alice, "alice");
        _register(alice, "bbb", 0);
        _skipCooldown(alice, "alice");
        _register(alice, "ccc", 0);
        assertEq(points.balanceOf(aliceAiId), 60, "3 * 20");

        _skipCooldown(alice, "alice");
        _register(alice, "ddd", 0);
        assertEq(points.balanceOf(aliceAiId), 60, "still 3");
    }

    /// @notice `mintRewardsPerDay()` 是常量 3，没有修改函数。
    function test_mintRewardsPerDayIsConstant() public view {
        assertEq(points.mintRewardsPerDay(), 3);
    }

    /// @notice `creditMintReward` 只能由 Registrar 调用。
    function test_creditMintReward_onlyRegistrar() public {
        _register(alice, "abc", 0);

        vm.prank(bob);
        vm.expectRevert(HahaPoints.NotRegistrar.selector);
        points.creditMintReward(alice, aliceAiId);
    }

    // =====================================================================
    // spend / refund 限额（owner 2026-11-20 裁决）
    // =====================================================================

    /// @notice 未授权地址不能 spend / refund。
    function test_spend_refund_onlySpender() public {
        _register(alice, "abc", 0);
        vm.prank(bob);
        vm.expectRevert(HahaPoints.NotSpender.selector);
        points.spend(alice, 1, "AUCTION");

        vm.prank(bob);
        vm.expectRevert(HahaPoints.NotSpender.selector);
        points.refund(alice, 1, "AUCTION");
    }

    /// @notice 授权后可以 spend，余额减少，`spendable` 增加。
    function test_spend_reducesBalance_andTracksSpendable() public {
        _register(alice, "abc", 0);
        SpenderContract sp = new SpenderContract();
        _setSpenderWithBudget(sp);

        vm.prank(address(sp));
        points.spend(alice, 5, "AUCTION");

        assertEq(points.balanceOf(aliceAiId), 5, "10 - 5");
        assertEq(points.spendableOf(aliceAiId, "AUCTION"), 5, "spendable 5");
    }

    /// @notice **关键**：`refund` 不能超过该 reason 下累计 spend 且未退回的部分。
    function test_refund_exceedingSpendable_reverts() public {
        _register(alice, "abc", 0);
        SpenderContract sp = new SpenderContract();
        _setSpenderWithBudget(sp);

        vm.prank(address(sp));
        points.spend(alice, 5, "AUCTION");

        // 退 6 > 花掉的 5 => 必须 revert
        vm.prank(address(sp));
        vm.expectRevert(abi.encodeWithSelector(HahaPoints.RefundExceedsSpendable.selector, 6, 5));
        points.refund(alice, 6, "AUCTION");

        // 退 5 可以
        vm.prank(address(sp));
        points.refund(alice, 5, "AUCTION");
        assertEq(points.balanceOf(aliceAiId), 10, "restored");
        assertEq(points.spendableOf(aliceAiId, "AUCTION"), 0, "spendable drained");
    }

    /// @notice 退完之后再退也失败（额度已用完）。
    function test_refund_cannotDoubleRefund() public {
        _register(alice, "abc", 0);
        SpenderContract sp = new SpenderContract();
        _setSpenderWithBudget(sp);

        vm.prank(address(sp));
        points.spend(alice, 10, "AUCTION");
        vm.prank(address(sp));
        points.refund(alice, 10, "AUCTION");

        vm.prank(address(sp));
        vm.expectRevert(abi.encodeWithSelector(HahaPoints.RefundExceedsSpendable.selector, 1, 0));
        points.refund(alice, 1, "AUCTION");
    }

    /// @notice 不同 reason 的额度互相独立。
    function test_refund_perReasonIsolation() public {
        _register(alice, "abc", 0);
        SpenderContract sp = new SpenderContract();
        _setSpenderWithBudget(sp);

        vm.prank(address(sp));
        points.spend(alice, 4, "AUCTION");

        // 另一个 reason 没有额度
        vm.prank(address(sp));
        vm.expectRevert(abi.encodeWithSelector(HahaPoints.RefundExceedsSpendable.selector, 1, 0));
        points.refund(alice, 1, "OTHER");
    }

    /// @notice spend 余额不足时 revert，不改变任何状态。
    function test_spend_insufficientBalance_reverts() public {
        _register(alice, "abc", 0);
        SpenderContract sp = new SpenderContract();
        vm.prank(ADMIN);
        points.setSpender(address(sp), true);

        vm.prank(address(sp));
        vm.expectRevert(abi.encodeWithSelector(HahaPoints.InsufficientPoints.selector, 10, 11));
        points.spend(alice, 11, "AUCTION");

        assertEq(points.balanceOf(aliceAiId), 10);
        assertEq(points.spendableOf(aliceAiId, "AUCTION"), 0);
    }

    /// @notice spend 要求用户当前有 `.ai` 且持有名字。
    function test_spend_requiresAiAndName() public {
        SpenderContract sp = new SpenderContract();
        vm.prank(ADMIN);
        points.setSpender(address(sp), true);

        // alice 有 .ai 但没名字（还没铸）
        vm.prank(address(sp));
        vm.expectRevert(HahaPoints.NameRequired.selector);
        points.spend(alice, 1, "AUCTION");
    }

    /// @notice refund 只要求 `.ai`，不要求持有名字。拍卖把分退回原钱包即可。
    function test_refund_requiresOnlyAi() public {
        _register(alice, "abc", 0);
        SpenderContract sp = new SpenderContract();
        _setSpenderWithBudget(sp);

        vm.prank(address(sp));
        points.spend(alice, 10, "AUCTION");

        // alice 卖掉名字
        vm.prank(alice);
        registrar.transferFrom(alice, bob, uint256(_node("abc", 0)));

        // refund 仍然可以（有 .ai）
        vm.prank(address(sp));
        points.refund(alice, 10, "AUCTION");
        assertEq(points.balanceOf(aliceAiId), 10);
    }

    /// @notice amount 为 0 或 reason 为 0 都 revert。
    function test_spend_refund_zeroArgs() public {
        _register(alice, "abc", 0);
        SpenderContract sp = new SpenderContract();
        vm.prank(ADMIN);
        points.setSpender(address(sp), true);

        vm.prank(address(sp));
        vm.expectRevert(HahaPoints.ZeroAmount.selector);
        points.spend(alice, 0, "AUCTION");

        vm.prank(address(sp));
        vm.expectRevert(HahaPoints.ZeroReason.selector);
        points.spend(alice, 1, bytes32(0));

        vm.prank(address(sp));
        vm.expectRevert(HahaPoints.ZeroAmount.selector);
        points.refund(alice, 0, "AUCTION");
    }

    // =====================================================================
    // 管理员
    // =====================================================================

    /// @notice 只有 admin 能改参数。
    function test_setPointParams_onlyAdmin() public {
        vm.prank(alice);
        vm.expectRevert(HahaPoints.NotAdmin.selector);
        points.setPointParams(1, 1, 1, 1, 1, 1);
    }

    /// @notice 任一参数超过 999999999 都 revert。
    function test_setPointParams_cap() public {
        vm.prank(ADMIN);
        vm.expectRevert(abi.encodeWithSelector(HahaPoints.ParamTooLarge.selector, 1_000_000_000));
        points.setPointParams(1_000_000_000, 10, 30, 10, 10, 10);

        // 边界值 999999999 可以
        vm.prank(ADMIN);
        points.setPointParams(999_999_999, 10, 30, 10, 10, 10);
        assertEq(points.checkInPoints(), 999_999_999);
    }

    /// @notice `setSpender(account, true)` 要求 account 有代码。
    function test_setSpender_requiresContract() public {
        vm.prank(ADMIN);
        vm.expectRevert(HahaPoints.NotAContract.selector);
        points.setSpender(alice, true);
    }

    /// @notice 取消授权不检查代码，永远可以（安全阀）。
    function test_setSpender_cancelAlwaysAllowed() public {
        vm.prank(ADMIN);
        points.setSpender(alice, false); // 即使 alice 是 EOA 也不 revert
        assertFalse(points.isSpender(alice));
    }

    /// @notice spender 为 0 时 revert。
    function test_setSpender_zeroAddress() public {
        vm.prank(ADMIN);
        vm.expectRevert(HahaPoints.ZeroAddress.selector);
        points.setSpender(address(0), true);
    }

    /// @notice 没有 signer / setVoucherSigner / EIP-712（SPEC 12 要求）。
    /// @dev 验证方式：这些选择器在合约上不存在，调用会 revert（无 fallback）。
    function test_noSignerNoEip712() public {
        (bool ok,) = address(points).call(abi.encodeWithSignature("signer()"));
        assertFalse(ok, "no signer()");

        (bool ok2,) = address(points).call(abi.encodeWithSignature("setVoucherSigner(address)", alice));
        assertFalse(ok2, "no setVoucherSigner");

        (bool ok3,) = address(points).call(abi.encodeWithSignature("eip712Domain()"));
        assertFalse(ok3, "no eip712Domain");

        (bool ok4,) = address(points).call(abi.encodeWithSignature("renounceOwnership()"));
        assertFalse(ok4, "no renounceOwnership");
    }

    // =====================================================================
    // 只读辅助
    // =====================================================================

    function test_balanceOfUser() public {
        _register(alice, "abc", 0);
        assertEq(points.balanceOfUser(alice), 10);
        // 没有 .ai 的地址返回 0
        assertEq(points.balanceOfUser(makeAddr("x")), 0);
    }

    // =====================================================================
    // 内部
    // =====================================================================

    /// @dev 下一个 UTC 日界（`block.timestamp` 之后最近的 86400 的整数倍）。
    function _nextUtcDayStart() internal view returns (uint256) {
        return ((block.timestamp / 86400) + 1) * 86400;
    }

    /// @dev 直接给 alice 一个名字但不经过 register（用于测 day 0 这种边界）。
    ///      做法：管理员铸造一个保留名。
    function _grantNameDirectly(address user, string memory) internal {
        vm.prank(ADMIN);
        registrar.adminMint("haha", 0, user);
    }
}
