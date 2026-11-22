// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {HahaTestBase} from "./HahaTestBase.sol";
import {HahaAgentIdentity} from "src/HahaAgentIdentity.sol";
import {HahaReputation} from "src/HahaReputation.sol";
import {HahaPoints} from "src/HahaPoints.sol";
import {HahaConstants} from "src/libraries/HahaConstants.sol";

/// @notice 一个受控的 earner mock：`earn` 直接透传给真正的 HahaPoints。
contract MockEarner {
    HahaPoints public immutable points;

    constructor(address points_) {
        points = HahaPoints(points_);
    }

    function earn(bytes32 actionId, address user, bytes32 uniqueKey) external returns (uint256) {
        return points.earn(actionId, user, uniqueKey);
    }
}

/// @notice 一个受控的游戏 mock。分数存 `_scores[sessionId]`，测试里直接写死，
///         验证「分数只能来自游戏合约的 scoreOf，用户交易里没有分数字段」。
contract MockGame {
    HahaPoints public immutable pointsContract;
    bytes32 public immutable gameId;

    mapping(uint256 sessionId => uint256) private _scores;
    mapping(uint256 sessionId => bool) private _settled;

    constructor(address points_, bytes32 gameId_) {
        pointsContract = HahaPoints(points_);
        gameId = gameId_;
    }

    function start() external returns (uint256 sessionId) {
        sessionId = pointsContract.beginRound(gameId, msg.sender);
    }

    function setScore(uint256 sessionId, uint256 score) external {
        _scores[sessionId] = score;
        _settled[sessionId] = true;
    }

    function scoreOf(uint256 sessionId) external view returns (uint256, bool) {
        return (_scores[sessionId], _settled[sessionId]);
    }

    function claim(uint256 sessionId) external returns (uint256 awarded) {
        awarded = pointsContract.claimRound(sessionId);
    }
}

/// @title SupplementTest
/// @notice 补充规格 v1.1 的测试：earner、预算、小游戏、statusOf、激活分、
///         自评三条、operator / generation / operatorAiId。原有 SPEC 12 用例保持通过。
contract SupplementTest is HahaTestBase {
    bytes32 internal aliceAiId;
    bytes32 internal bobAiId;
    bytes32 internal carolAiId;

    bytes32 internal constant A_GIVE = HahaConstants.ACTION_REVIEW_GIVE;
    bytes32 internal constant A_RECEIVE = HahaConstants.ACTION_REVIEW_RECEIVE;
    bytes32 internal constant A_ACTIVATE = HahaConstants.ACTION_ACTIVATE;

    MockEarner internal earner;

    function setUp() public override {
        super.setUp();
        aliceAiId = _aiId("alice");
        bobAiId = _aiId("bob");
        carolAiId = _aiId("carol");

        earner = new MockEarner(address(points));

        // alice 持有主名字 "abc"，供 _aliceAgent 与游戏/评价测试用。
        _register(alice, "abc", 0);
    }

    // ---------------------------------------------------------------------
    // 工具
    // ---------------------------------------------------------------------

    function _setEarner(bytes32 actionId, uint256 pointsPer, uint64 cap, uint256 global, HahaPoints.KeyMode mode, bool requireName)
        internal
    {
        vm.prank(ADMIN);
        points.setEarner(
            actionId,
            HahaPoints.EarnerConfig({
                module: address(earner),
                points: pointsPer,
                perUserDailyCap: cap,
                globalDailyPoints: global,
                keyMode: mode,
                requireName: requireName,
                enabled: true
            })
        );
    }

    function _aliceAgent() internal returns (uint256) {
        vm.prank(alice);
        return identity.activateAgent("abc", 0, "https://x");
    }

    function _raterName(address rater, string memory handle, string memory label) internal {
        _skipCooldown(rater, handle);
        _register(rater, label, 0);
    }

    // =====================================================================
    // 1. earner 注册表：返回 0 的各种路径
    // =====================================================================

    /// @notice 未登记的 action 调用 earn 直接 revert NotEarner。
    function test_earn_unregistered_reverts() public {
        vm.expectRevert(HahaPoints.NotEarner.selector);
        earner.earn(bytes32("NOPE"), alice, bytes32(uint256(1)));
    }

    /// @notice 登记之后：无 `.ai` 返回 0，不增加余额。
    function test_earn_noAi_returnsZero() public {
        _setEarner(bytes32("TEST"), 5, 5, 50000, HahaPoints.KeyMode.None, false);

        address noAi = makeAddr("noAi");
        uint256 a = earner.earn(bytes32("TEST"), noAi, bytes32(0));
        assertEq(a, 0);
    }

    /// @notice requireName 时无名字返回 0（bob 有 .ai 但没名字）。
    function test_earn_noName_returnsZero() public {
        _setEarner(bytes32("TEST"), 5, 5, 50000, HahaPoints.KeyMode.None, true);

        uint256 a = earner.earn(bytes32("TEST"), bob, bytes32(0));
        assertEq(a, 0);
        assertEq(points.balanceOf(bobAiId), 0);
    }

    /// @notice PerDay key 同一天重复返回 0，第二次不写。
    function test_earn_perDayKey_oncePerDay() public {
        _setEarner(bytes32("TEST"), 5, 5, 50000, HahaPoints.KeyMode.PerDay, false);
        bytes32 key = bytes32(uint256(7));

        uint256 before = points.balanceOf(aliceAiId);
        uint256 a1 = earner.earn(bytes32("TEST"), alice, key);
        uint256 a2 = earner.earn(bytes32("TEST"), alice, key);
        assertEq(a1, 5);
        assertEq(a2, 0, "same key same day returns 0");
        assertEq(points.balanceOf(aliceAiId), before + 5, "only one award");
    }

    /// @notice Lifetime key 终身一次，跨日仍 0。
    function test_earn_lifetimeKey_onceForever() public {
        _setEarner(bytes32("TEST"), 5, 5, 50000, HahaPoints.KeyMode.Lifetime, false);
        bytes32 key = bytes32(uint256(7));

        uint256 a1 = earner.earn(bytes32("TEST"), alice, key);
        assertEq(a1, 5);

        vm.warp(block.timestamp + 10 * 86400);
        uint256 a2 = earner.earn(bytes32("TEST"), alice, key);
        assertEq(a2, 0, "lifetime key never resets");
    }

    /// @notice 超个人每日次数返回 0。
    function test_earn_overPerUserCap_returnsZero() public {
        _setEarner(bytes32("TEST"), 5, 3, 50000, HahaPoints.KeyMode.None, false);

        uint256 before = points.balanceOf(aliceAiId);
        earner.earn(bytes32("TEST"), alice, bytes32(uint256(1)));
        earner.earn(bytes32("TEST"), alice, bytes32(uint256(2)));
        earner.earn(bytes32("TEST"), alice, bytes32(uint256(3)));

        uint256 a4 = earner.earn(bytes32("TEST"), alice, bytes32(uint256(4)));
        assertEq(a4, 0, "4th over cap returns 0");
        assertEq(points.balanceOf(aliceAiId), before + 15, "only 3 awards");
    }

    /// @notice 超全网每日预算返回 0。
    function test_earn_overGlobalBudget_returnsZero() public {
        _setEarner(bytes32("TEST"), 5, 50, 5, HahaPoints.KeyMode.None, false);

        uint256 a1 = earner.earn(bytes32("TEST"), alice, bytes32(uint256(1)));
        uint256 a2 = earner.earn(bytes32("TEST"), alice, bytes32(uint256(2)));
        assertEq(a1, 5);
        assertEq(a2, 0, "over global budget returns 0");
    }

    /// @notice 停用 earner 后 earn 直接 revert（enabled=false）。
    function test_earn_disabled_reverts() public {
        _setEarner(bytes32("TEST"), 5, 5, 50000, HahaPoints.KeyMode.None, false);
        vm.prank(ADMIN);
        points.setEarner(
            bytes32("TEST"),
            HahaPoints.EarnerConfig({
                module: address(earner),
                points: 5,
                perUserDailyCap: 5,
                globalDailyPoints: 50000,
                keyMode: HahaPoints.KeyMode.None,
                requireName: false,
                enabled: false
            })
        );

        vm.expectRevert(HahaPoints.NotEarner.selector);
        earner.earn(bytes32("TEST"), alice, bytes32(0));
    }

    /// @notice 换 module 沿用同一 actionId，Lifetime key 仍算已用。
    function test_earn_moduleSwap_lifetimeKeyPersists() public {
        _setEarner(bytes32("TEST"), 5, 5, 50000, HahaPoints.KeyMode.Lifetime, false);
        bytes32 key = bytes32(uint256(7));

        earner.earn(bytes32("TEST"), alice, key);

        MockEarner earner2 = new MockEarner(address(points));
        vm.prank(ADMIN);
        points.setEarner(
            bytes32("TEST"),
            HahaPoints.EarnerConfig({
                module: address(earner2),
                points: 5,
                perUserDailyCap: 5,
                globalDailyPoints: 50000,
                keyMode: HahaPoints.KeyMode.Lifetime,
                requireName: false,
                enabled: true
            })
        );

        uint256 a = earner2.earn(bytes32("TEST"), alice, key);
        assertEq(a, 0, "lifetime key still used after module swap");
    }

    // =====================================================================
    // 2. 日切（UTC 日序号）
    // =====================================================================

    /// @notice 同一 UTC 日内拨 23 小时，PerDay key 不归零。
    function test_dayRollover_23hSameDay() public {
        _setEarner(bytes32("TEST"), 5, 5, 50000, HahaPoints.KeyMode.PerDay, false);
        bytes32 key = bytes32(uint256(7));

        earner.earn(bytes32("TEST"), alice, key);

        uint256 dayStart = (block.timestamp / 86400) * 86400;
        vm.warp(dayStart + 23 * 3600);
        uint256 a2 = earner.earn(bytes32("TEST"), alice, key);
        assertEq(a2, 0, "same day, 23h later, still blocked");
    }

    /// @notice 跨到下一个日序号的第一秒，PerDay key 归零。
    function test_dayRollover_nextDayResets() public {
        _setEarner(bytes32("TEST"), 5, 5, 50000, HahaPoints.KeyMode.PerDay, false);
        bytes32 key = bytes32(uint256(7));

        earner.earn(bytes32("TEST"), alice, key);

        uint256 nextDay = ((block.timestamp / 86400) + 1) * 86400;
        vm.warp(nextDay);
        uint256 a2 = earner.earn(bytes32("TEST"), alice, key);
        assertEq(a2, 5, "next day same key earns again");
    }

    // =====================================================================
    // 3. spender 预算
    // =====================================================================

    /// @notice spender 未设预算时 spend revert BudgetNotSet。
    function test_spend_noBudget_reverts() public {
        SpenderContract2 sp = new SpenderContract2();
        vm.prank(ADMIN);
        points.setSpender(address(sp), true);

        vm.prank(address(sp));
        vm.expectRevert(HahaPoints.BudgetNotSet.selector);
        points.spend(alice, 5, "AUCTION");
    }

    /// @notice refund 不把 gross 预算还回去。
    function test_refund_doesNotRestoreBudget() public {
        SpenderContract2 sp = new SpenderContract2();
        vm.startPrank(ADMIN);
        points.setSpender(address(sp), true);
        points.setSpenderBudget(
            address(sp),
            HahaPoints.SpenderBudget({perUserDailyPoints: 100, globalDailyPoints: 1000})
        );
        vm.stopPrank();

        // 先给 alice 造够余额（签到 + 铸造奖励不够 100，直接花会 InsufficientPoints）
        // 用 spend 前先给 alice 足够积分：这里用 earner 造分。
        _setEarner(bytes32("TEST"), 100, 50, 50000, HahaPoints.KeyMode.None, false);
        earner.earn(bytes32("TEST"), alice, bytes32(uint256(1))); // +100

        vm.prank(address(sp));
        points.spend(alice, 100, "AUCTION"); // 用满 perUser 预算

        vm.prank(address(sp));
        points.refund(alice, 100, "AUCTION"); // 退回余额

        // gross 预算已满，再 spend 1 也 revert（预算没被 refund 退回）
        vm.prank(address(sp));
        vm.expectRevert(abi.encodeWithSelector(HahaPoints.SpendBudgetExceeded.selector, true, 101, 100));
        points.spend(alice, 1, "AUCTION");
    }

    // =====================================================================
    // 4. 小游戏
    // =====================================================================

    function _registerGame(MockGame g) internal {
        bytes32 gid = g.gameId(); // 先取，避免 staticcall 消耗 prank
        vm.prank(ADMIN);
        points.registerGame(
            gid,
            HahaPoints.GameConfig({
                module: address(g),
                maxScorePerRound: 100,
                perAiDailyPoints: 1000,
                globalDailyPoints: 50000,
                enabled: true
            })
        );
    }

    /// @notice 开一局、结算 63、领取加 63。
    function test_game_claimAddsScore() public {
        MockGame g = new MockGame(address(points), bytes32("GAME_A"));
        _registerGame(g);

        uint256 before = points.balanceOf(aliceAiId);
        vm.prank(alice);
        uint256 s = g.start();
        g.setScore(s, 63);

        vm.prank(alice);
        uint256 awarded = g.claim(s);
        assertEq(awarded, 63);
        assertEq(points.balanceOf(aliceAiId), before + 63, "balance +63");
    }

    /// @notice 第 4 局 revert DailyRoundsSpent（跨游戏合计 3 局）。
    function test_game_fourthRound_reverts() public {
        MockGame g1 = new MockGame(address(points), bytes32("GAME_A"));
        MockGame g2 = new MockGame(address(points), bytes32("GAME_B"));
        _registerGame(g1);
        _registerGame(g2);

        vm.startPrank(alice);
        g1.start();
        g1.start();
        g2.start(); // 第 3 局（跨游戏合计）
        vm.expectRevert(abi.encodeWithSelector(HahaPoints.DailyRoundsSpent.selector, points.currentDay()));
        g1.start(); // 第 4 局 revert
        vm.stopPrank();
    }

    /// @notice 超过 maxScorePerRound 领取失败，余额不变。
    function test_game_scoreTooHigh_reverts() public {
        MockGame g = new MockGame(address(points), bytes32("GAME_A"));
        _registerGame(g); // maxScorePerRound = 100

        uint256 before = points.balanceOf(aliceAiId);
        vm.prank(alice);
        uint256 s = g.start();
        g.setScore(s, 101); // > 100

        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(HahaPoints.ScoreTooHigh.selector, 101, 100));
        g.claim(s);
        assertEq(points.balanceOf(aliceAiId), before, "no points added on revert");
    }

    /// @notice 同一 sessionId 第二次领取 revert SessionAlreadyClaimed。
    function test_game_claimTwice_reverts() public {
        MockGame g = new MockGame(address(points), bytes32("GAME_A"));
        _registerGame(g);

        vm.prank(alice);
        uint256 s = g.start();
        g.setScore(s, 10);

        vm.startPrank(alice);
        g.claim(s);
        vm.expectRevert(HahaPoints.SessionAlreadyClaimed.selector);
        g.claim(s);
        vm.stopPrank();
    }

    /// @notice 开局日的下一个 UTC 日再领 revert SessionExpired，局数不退回。
    function test_game_claimNextDay_expired() public {
        MockGame g = new MockGame(address(points), bytes32("GAME_A"));
        _registerGame(g);

        vm.prank(alice);
        uint256 s = g.start();
        g.setScore(s, 10);

        uint256 openDay = points.currentDay();
        uint256 nextDay = ((block.timestamp / 86400) + 1) * 86400;
        vm.warp(nextDay);

        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(HahaPoints.SessionExpired.selector, uint64(openDay), uint64(points.currentDay())));
        g.claim(s);
    }

    /// @notice 未结算就领取 revert SessionNotSettled。
    function test_game_claimUnsettled_reverts() public {
        MockGame g = new MockGame(address(points), bytes32("GAME_A"));
        _registerGame(g);

        vm.prank(alice);
        uint256 s = g.start();
        // 不 setScore

        vm.prank(alice);
        vm.expectRevert(HahaPoints.SessionNotSettled.selector);
        g.claim(s);
    }

    // =====================================================================
    // 5. statusOf 一致性
    // =====================================================================

    /// @notice statusOf 的 nextResetAt == (currentDay + 1) * 86400。
    function test_statusOf_nextResetAt() public {
        HahaPoints.PointsStatus memory s = points.statusOf(alice);
        uint64 expected = uint64((uint256(points.currentDay()) + 1) * 86400);
        assertEq(s.nextResetAt, expected);
        assertEq(s.currentDay, points.currentDay());
    }

    /// @notice statusOf 的 balance 与 balanceOf 一致。
    function test_statusOf_balance() public {
        vm.prank(alice);
        points.checkIn();

        HahaPoints.PointsStatus memory s = points.statusOf(alice);
        assertEq(s.balance, points.balanceOf(aliceAiId));
        assertEq(s.checkInToday, 1);
    }

    /// @notice 没有 `.ai` 时 statusOf 的 holdsAi == false，aiId == 0。
    function test_statusOf_noAi() public {
        address noAi = makeAddr("noAi");
        HahaPoints.PointsStatus memory s = points.statusOf(noAi);
        assertFalse(s.holdsAi);
        assertEq(s.aiId, bytes32(0));
    }

    /// @notice statusOf 的 gameRoundsToday 跨日归零。
    function test_statusOf_gameRoundsToday_resets() public {
        MockGame g = new MockGame(address(points), bytes32("GAME_A"));
        _registerGame(g);

        vm.prank(alice);
        g.start();

        HahaPoints.PointsStatus memory s1 = points.statusOf(alice);
        assertEq(s1.gameRoundsToday, 1);

        uint256 nextDay = ((block.timestamp / 86400) + 1) * 86400;
        vm.warp(nextDay);

        HahaPoints.PointsStatus memory s2 = points.statusOf(alice);
        assertEq(s2.gameRoundsToday, 0, "game rounds reset across day");
    }

    // =====================================================================
    // 6. 激活分（终身一次）
    // =====================================================================

    function _setActivateEarner() internal {
        vm.prank(ADMIN);
        points.setEarner(
            A_ACTIVATE,
            HahaPoints.EarnerConfig({
                module: address(identity),
                points: 20,
                perUserDailyCap: 1,
                globalDailyPoints: 100000,
                keyMode: HahaPoints.KeyMode.Lifetime,
                requireName: true,
                enabled: true
            })
        );
    }

    /// @notice 激活一次领 20 分，同一 `.ai` 换名字再激活不再给。
    function test_activatePoints_lifetimeOncePerAi() public {
        _setActivateEarner();

        vm.prank(alice);
        identity.activateAgent("abc", 0, "https://x");
        // alice 初始 10 分（setUp 铸 "abc"）+ 激活 20 = 30
        assertEq(points.balanceOf(aliceAiId), 30);

        // alice 卖名，再注册新名并激活（同一 .ai）
        vm.prank(alice);
        registrar.transferFrom(alice, bob, uint256(_node("abc", 0)));

        _skipCooldown(alice, "alice");
        _register(alice, "def", 0); // +10 mint = 40
        uint256 beforeSecond = points.balanceOf(aliceAiId);
        vm.prank(alice);
        identity.activateAgent("def", 0, "https://y");

        // 第二次激活不再 +20
        assertEq(points.balanceOf(aliceAiId), beforeSecond, "lifetime activation only once per .ai");
    }

    /// @notice 另一个 `.ai` 有自己的一次。
    function test_activatePoints_otherAiGetsOwn() public {
        _setActivateEarner();

        vm.prank(alice);
        identity.activateAgent("abc", 0, "https://x"); // alice: 10 + 20 = 30

        _raterName(bob, "bob", "xyz"); // bob 铸 "xyz" +10
        uint256 bobBefore = points.balanceOf(bobAiId);
        vm.prank(bob);
        identity.activateAgent("xyz", 0, "https://z"); // bob: +20

        assertEq(points.balanceOf(aliceAiId), 30);
        assertEq(points.balanceOf(bobAiId), bobBefore + 20, "other .ai gets its own activation points");
    }

    /// @notice 未 setEarner 时激活仍然成功（try/catch 吃掉 NotEarner）。
    function test_activate_worksWithoutEarner() public {
        vm.prank(alice);
        uint256 agentId = identity.activateAgent("abc", 0, "https://x");
        assertEq(agentId, 1);
        // 未 setEarner：只有 setUp 铸 "abc" 的 10 分，激活不加分
        assertEq(points.balanceOf(aliceAiId), 10, "no activation points when earner not set");
    }

    // =====================================================================
    // 7. 评价分（REVIEW_GIVE / REVIEW_RECEIVE）
    // =====================================================================

    function _setReviewEarners() internal {
        vm.prank(ADMIN);
        points.setEarner(
            A_GIVE,
            HahaPoints.EarnerConfig({
                module: address(reputation),
                points: 5,
                perUserDailyCap: 5,
                globalDailyPoints: 50000,
                keyMode: HahaPoints.KeyMode.PerDay,
                requireName: true,
                enabled: true
            })
        );
        vm.prank(ADMIN);
        points.setEarner(
            A_RECEIVE,
            HahaPoints.EarnerConfig({
                module: address(reputation),
                points: 5,
                perUserDailyCap: 5,
                globalDailyPoints: 50000,
                keyMode: HahaPoints.KeyMode.PerDay,
                requireName: true,
                enabled: true
            })
        );
    }

    /// @notice 写评价给评分人 +5，收评价给 owner +5。
    function test_review_points_bothSides() public {
        _setReviewEarners();
        _raterName(bob, "bob", "bobname"); // bob 铸 "bobname" +10
        uint256 bobBefore = points.balanceOf(bobAiId);
        uint256 aliceBefore = points.balanceOf(aliceAiId);
        uint256 agentId = _aliceAgent();

        vm.prank(bob);
        reputation.rate(agentId, 5, "great");

        assertEq(points.balanceOf(bobAiId), bobBefore + 5, "reviewer gets 5");
        assertEq(points.balanceOf(aliceAiId), aliceBefore + 5, "owner gets 5 for receiving");
    }

    /// @notice 同一对当天改分，第二次 earn 返回 0（不重复发分）。
    function test_review_points_samePairOncePerDay() public {
        _setReviewEarners();
        _raterName(bob, "bob", "bobname");
        uint256 bobBefore = points.balanceOf(bobAiId);
        uint256 aliceBefore = points.balanceOf(aliceAiId);
        uint256 agentId = _aliceAgent();

        vm.startPrank(bob);
        reputation.rate(agentId, 3, "meh");
        reputation.rate(agentId, 5, "better"); // 改分
        vm.stopPrank();

        assertEq(points.balanceOf(bobAiId), bobBefore + 5, "only one award");
        assertEq(points.balanceOf(aliceAiId), aliceBefore + 5, "only one award");
    }

    /// @notice 同一对同一天只发一次分，无论 rate 多少次（PerDay key 挡住）。
    function test_review_points_sixthAgent_noPoints() public {
        _setReviewEarners();
        _raterName(bob, "bob", "bobname");
        uint256 bobBefore = points.balanceOf(bobAiId);
        uint256 aliceBefore = points.balanceOf(aliceAiId);
        uint256 agentId = _aliceAgent();

        vm.startPrank(bob);
        for (uint256 i = 0; i < 6; i++) {
            reputation.rate(agentId, 5, "");
        }
        vm.stopPrank();

        assertEq(points.balanceOf(bobAiId), bobBefore + 5, "same pair only once per day");
        assertEq(points.balanceOf(aliceAiId), aliceBefore + 5);
    }

    // =====================================================================
    // 8. 自评三条（规格 3.2 缺口 D）
    // =====================================================================

    /// @notice owner 直接 rate revert SelfRating。
    function test_selfRate_ownerRates_reverts() public {
        _setReviewEarners();
        uint256 agentId = _aliceAgent();

        vm.prank(alice);
        vm.expectRevert(HahaReputation.SelfRating.selector);
        reputation.rate(agentId, 5, "me");
    }

    /// @notice owner 没有 `.ai` 时，任何人 rate 都 revert OwnerAiRequired。
    function test_rate_ownerWithoutAi_reverts() public {
        _setReviewEarners();
        uint256 agentId = _aliceAgent();

        // 让 alice 的 .ai 校验失败：把 handleOf("alice") 的 owner 指向 bob（不等于 alice），
        // 触发 aiIdentityOf 第 2 步 `ownerOfHandle != user`。
        ai.forceHandleOf(alice, "alice", bob);

        _raterName(bob, "bob", "bobname");
        vm.prank(bob);
        vm.expectRevert(HahaReputation.OwnerAiRequired.selector);
        reputation.rate(agentId, 5, "x");
    }

    /// @notice operatorAiId 与评分人 aiId 相同时 revert SelfRating。
    /// @dev 被授权为 operator 的地址，即使用的是「另一个 .ai」身份（不是 owner 的 aiId），
    ///      也不能给这个 agent 打分——这是审计 #4 真正可达的自评绕过路径。
    function test_selfRate_operatorAiId_reverts() public {
        _setReviewEarners();
        uint256 agentId = _aliceAgent(); // owner = alice，operatorAiId = aliceAiId

        // operatorAiId 链上记录正确。
        assertEq(identity.operatorAiIdOf(agentId), aliceAiId);

        // alice 授权 bob（持有另一个 .ai "bob"）为 operator。
        vm.prank(alice);
        identity.setAgentOperator(agentId, bob, true);
        assertTrue(identity.isAgentOperator(agentId, bob));

        // bob 持有自己的 .ai 和名字，给这个 agent 打分 → 命中 isAgentOperator 检查，revert SelfRating。
        _raterName(bob, "bob", "bobname");
        vm.prank(bob);
        vm.expectRevert(HahaReputation.SelfRating.selector);
        reputation.rate(agentId, 5, "operator self-rating");
    }

    // =====================================================================
    // 9. generation / operator / operatorAiId
    // =====================================================================

    /// @notice burn 再激活，新 id = 旧 id + 1，generation + 1。
    function test_generation_incrementsOnReactivate() public {
        uint256 a1 = _aliceAgent();
        assertEq(identity.generationOf(a1), 1);
        assertEq(identity.nameGeneration(uint256(_node("abc", 0))), 1);

        vm.prank(alice);
        registrar.transferFrom(alice, bob, uint256(_node("abc", 0)));

        vm.prank(bob);
        uint256 a2 = identity.activateAgent("abc", 0, "https://y");

        assertEq(a2, a1 + 1, "new id = old + 1");
        assertEq(identity.generationOf(a2), 2, "generation increments");
        assertEq(identity.nameGeneration(uint256(_node("abc", 0))), 2, "nameGeneration only increases");
        assertFalse(identity.isActive(a1), "old agent inactive");
    }

    /// @notice owner 可以设 operator，operator 可以代表 agent（isAuthorized）。
    function test_operator_isAuthorized() public {
        uint256 agentId = _aliceAgent();

        vm.prank(alice);
        identity.setAgentOperator(agentId, bob, true);

        assertTrue(identity.isAuthorized(agentId, bob), "operator authorized");
        assertTrue(identity.isAuthorized(agentId, alice), "owner always authorized");
        assertFalse(identity.isAuthorized(agentId, carol), "stranger not authorized");

        vm.prank(bob);
        identity.setAgentURI(agentId, "https://new");
        assertEq(identity.tokenURI(agentId), "https://new");
    }

    /// @notice 每个 agent 最多 8 个 operator。
    function test_operator_maxEight() public {
        uint256 agentId = _aliceAgent();

        vm.startPrank(alice);
        for (uint256 i = 0; i < 8; i++) {
            identity.setAgentOperator(agentId, address(uint160(i + 1)), true);
        }
        vm.expectRevert(abi.encodeWithSelector(HahaAgentIdentity.TooManyOperators.selector, 8));
        identity.setAgentOperator(agentId, address(uint160(999)), true);
        vm.stopPrank();
    }

    /// @notice burn 之后 isAuthorized 对旧 id 一律 false。
    function test_operator_inactiveAlwaysFalse() public {
        uint256 agentId = _aliceAgent();
        vm.prank(alice);
        identity.setAgentOperator(agentId, bob, true);

        vm.prank(alice);
        registrar.transferFrom(alice, bob, uint256(_node("abc", 0)));

        assertFalse(identity.isAuthorized(agentId, bob), "inactive => not authorized");
        assertFalse(identity.isAuthorized(agentId, alice), "inactive => owner not authorized");
    }

    // =====================================================================
    // 10. 审计修复 v1.1.1（PR #6）
    // =====================================================================

    /// @notice 停用游戏后，已开局但未领的局不能再领分（revert GameNotRegistered）。
    function test_audit_disabledGame_cannotClaim() public {
        MockGame g = new MockGame(address(points), bytes32("GAME_A"));
        _registerGame(g);

        uint256 before = points.balanceOf(aliceAiId);
        vm.prank(alice);
        uint256 s = g.start();
        g.setScore(s, 63);

        // 管理员停用游戏。
        bytes32 gid = g.gameId();
        vm.prank(ADMIN);
        points.registerGame(
            gid,
            HahaPoints.GameConfig({
                module: address(g),
                maxScorePerRound: 100,
                perAiDailyPoints: 1000,
                globalDailyPoints: 50000,
                enabled: false
            })
        );

        vm.prank(alice);
        vm.expectRevert(HahaPoints.GameNotRegistered.selector);
        g.claim(s);
        assertEq(points.balanceOf(aliceAiId), before, "no points after disabled claim");
    }

    /// @notice 评价 earner 必须 PerDay + 每日上限 5，配错就 revert。
    function test_audit_reviewEarner_wrongMode_reverts() public {
        // keyMode = Lifetime 应被拒。
        vm.prank(ADMIN);
        vm.expectRevert(HahaPoints.InvalidActionId.selector);
        points.setEarner(
            A_GIVE,
            HahaPoints.EarnerConfig({
                module: address(reputation),
                points: 5,
                perUserDailyCap: 5,
                globalDailyPoints: 50000,
                keyMode: HahaPoints.KeyMode.Lifetime,
                requireName: true,
                enabled: true
            })
        );
    }

    /// @notice 评价 earner 每日上限配成非 5 应 revert。
    function test_audit_reviewEarner_wrongCap_reverts() public {
        vm.prank(ADMIN);
        vm.expectRevert(abi.encodeWithSelector(HahaPoints.CapOutOfRange.selector, 10));
        points.setEarner(
            A_RECEIVE,
            HahaPoints.EarnerConfig({
                module: address(reputation),
                points: 5,
                perUserDailyCap: 10,
                globalDailyPoints: 50000,
                keyMode: HahaPoints.KeyMode.PerDay,
                requireName: true,
                enabled: true
            })
        );
    }

    /// @notice 激活 earner 必须 Lifetime，配成 PerDay 应 revert。
    function test_audit_activateEarner_wrongMode_reverts() public {
        vm.prank(ADMIN);
        vm.expectRevert(HahaPoints.InvalidActionId.selector);
        points.setEarner(
            A_ACTIVATE,
            HahaPoints.EarnerConfig({
                module: address(identity),
                points: 20,
                perUserDailyCap: 1,
                globalDailyPoints: 100000,
                keyMode: HahaPoints.KeyMode.PerDay,
                requireName: true,
                enabled: true
            })
        );
    }

    /// @notice 游戏编号不能占用内置 reason（如 CHECKIN），registerGame 应 revert。
    function test_audit_gameId_builtinReason_reverts() public {
        MockGame g = new MockGame(address(points), HahaConstants.REASON_CHECKIN);
        bytes32 gid = g.gameId(); // 先取，避免 staticcall 消耗 expectRevert
        vm.prank(ADMIN);
        vm.expectRevert(HahaPoints.ActionReserved.selector);
        points.registerGame(
            gid,
            HahaPoints.GameConfig({
                module: address(g),
                maxScorePerRound: 100,
                perAiDailyPoints: 1000,
                globalDailyPoints: 50000,
                enabled: true
            })
        );
    }

    /// @notice 游戏编号不能占用三个保留 action（REVIEW_GIVE / REVIEW_RECEIVE / ACTIVATE）。
    function test_audit_gameId_reservedAction_reverts() public {
        bytes32[3] memory reserved = [A_GIVE, A_RECEIVE, A_ACTIVATE];
        for (uint256 i = 0; i < reserved.length; i++) {
            MockGame g = new MockGame(address(points), reserved[i]);
            bytes32 gid = g.gameId(); // 先取，避免 staticcall 消耗 expectRevert
            vm.prank(ADMIN);
            vm.expectRevert(HahaPoints.ActionReserved.selector);
            points.registerGame(
                gid,
                HahaPoints.GameConfig({
                    module: address(g),
                    maxScorePerRound: 100,
                    perAiDailyPoints: 1000,
                    globalDailyPoints: 50000,
                    enabled: true
                })
            );
        }
    }
}

/// @notice 给 `HahaPoints.setSpender` 用的最小合约。
contract SpenderContract2 {
    function ping() external pure returns (bool) {
        return true;
    }
}
