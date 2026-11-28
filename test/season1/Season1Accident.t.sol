// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Season1TestBase} from "./Season1TestBase.sol";
import {HahaSeason1} from "src/HahaSeason1.sol";

contract Season1AccidentTest is Season1TestBase {
    uint64 internal constant DAY = 20781;

    function _applyPending(bytes32 aiId, address user, uint256 pk) internal returns (uint256 orderId) {
        vm.warp(uint256(DAY) * 86400);
        vm.roll(100);
        bytes32[] memory leaves = new bytes32[](1);
        leaves[0] = _leaf(aiId, 1000, 0);
        bytes32 root = leaves[0];
        vm.prank(ADMIN);
        season1.setDayRoot(DAY, root, 80, blockhash(80), 1, 0);

        HahaSeason1.ApplyAuth memory auth = HahaSeason1.ApplyAuth({
            seasonId: 1,
            dayIndex: DAY,
            aiId: aiId,
            label: "ab",
            tld: 0,
            price: 200,
            recipient: address(0xBEEF),
            nonce: 0,
            deadline: (DAY + 1) * 86400,
            root: root,
            tier: 0,
            balance: 1000
        });
        bytes32 digest = _applyAuthDigest(auth);
        bytes memory sig = _sign(pk, digest);
        vm.prank(user);
        orderId = season1.applyFor(auth, sig, new bytes32[](0));
    }

    function test_accident_declare_success() public {
        bytes32 aiId = _aiId("salice");
        uint256 orderId = _applyPending(aiId, sAlice, ALICE_PK);
        uint256 before = points.balanceOf(aiId);

        vm.prank(ADMIN);
        season1.declareAccident(orderId, keccak256("evidence"));

        // refund 200 + earn 100 = +300
        assertEq(points.balanceOf(aiId), before + 300, "refund 200 + compensate 100");
        assertEq(season1.seasonOrderOf(aiId), 0, "season order cleared");
        assertEq(season1.nameLock(0, "ab"), 0, "name unlocked");
        HahaSeason1.Order memory o = season1.order(orderId);
        assertEq(uint8(o.status), uint8(HahaSeason1.OrderStatus.AccidentClosed), "closed");
    }

    function test_accident_noAi_creditOpen() public {
        bytes32 aiId = _aiId("salice");
        uint256 orderId = _applyPending(aiId, sAlice, ALICE_PK);

        // 让 sAlice 失去 .ai
        ai.forceHandleOf(sAlice, "", address(0));

        uint256 before = points.balanceOf(aiId);
        vm.prank(ADMIN);
        season1.declareAccident(orderId, keccak256("evidence"));

        // 不 refund，余额不变
        assertEq(points.balanceOf(aiId), before, "no refund when no ai");
        HahaSeason1.Order memory o = season1.order(orderId);
        assertEq(uint8(o.status), uint8(HahaSeason1.OrderStatus.CreditOpen), "credit open");
        assertEq(season1.seasonOrderOf(aiId), orderId, "season order kept");
    }

    function test_accident_claimCredit_afterRegainAi() public {
        bytes32 aiId = _aiId("salice");
        uint256 orderId = _applyPending(aiId, sAlice, ALICE_PK);

        // 失去 .ai
        ai.forceHandleOf(sAlice, "", address(0));
        uint256 before = points.balanceOf(aiId);
        vm.prank(ADMIN);
        season1.declareAccident(orderId, keccak256("evidence"));

        // 重新获得 .ai
        ai.register("salice", sAlice);

        vm.prank(sAlice);
        season1.claimAccidentCredit(orderId);

        assertEq(points.balanceOf(aiId), before + 300, "refund + compensate after regain");
        HahaSeason1.Order memory o = season1.order(orderId);
        assertEq(uint8(o.status), uint8(HahaSeason1.OrderStatus.AccidentClosed), "closed");
    }

    function test_accident_doubleDeclare_reverts() public {
        bytes32 aiId = _aiId("salice");
        uint256 orderId = _applyPending(aiId, sAlice, ALICE_PK);

        vm.prank(ADMIN);
        season1.declareAccident(orderId, keccak256("evidence"));

        // 第二次 declareAccident → StillPending（已经 AccidentClosed）
        vm.prank(ADMIN);
        vm.expectRevert(HahaSeason1.StillPending.selector);
        season1.declareAccident(orderId, keccak256("evidence2"));
    }

    function test_accident_claimCredit_twice_reverts() public {
        bytes32 aiId = _aiId("salice");
        uint256 orderId = _applyPending(aiId, sAlice, ALICE_PK);

        vm.prank(ADMIN);
        season1.declareAccident(orderId, keccak256("evidence"));

        // AccidentClosed 再 claimAccidentCredit → StillPending
        vm.prank(sAlice);
        vm.expectRevert(HahaSeason1.StillPending.selector);
        season1.claimAccidentCredit(orderId);
    }

    // CreditOpen 路径：claim 成功后，再 claim 第二次 → StillPending（重复领取防护）
    function test_accident_creditOpen_claim_twice_reverts() public {
        bytes32 aiId = _aiId("salice");
        uint256 orderId = _applyPending(aiId, sAlice, ALICE_PK);

        // 失去 .ai → declareAccident 走 CreditOpen
        ai.forceHandleOf(sAlice, "", address(0));
        vm.prank(ADMIN);
        season1.declareAccident(orderId, keccak256("evidence"));

        // 重新获得 .ai
        ai.register("salice", sAlice);

        // 第一次 claim → refund + compensate → AccidentClosed
        vm.prank(sAlice);
        season1.claimAccidentCredit(orderId);

        // 第二次 claim → StillPending
        vm.prank(sAlice);
        vm.expectRevert(HahaSeason1.StillPending.selector);
        season1.claimAccidentCredit(orderId);
    }

    // 补偿 deferred（earn 返回 0）→ AccidentRefunded；跨天后 claimAccidentCredit 只补 100，
    // 不重复退 200（退款只发生一次）。
    function test_accident_deferred_then_claim_no_double_refund() public {
        bytes32 aiId = _aiId("salice");
        uint256 orderId = _applyPending(aiId, sAlice, ALICE_PK);

        // 耗尽 sAlice 当天 ACTION_ACCIDENT 的 perUserDailyCap（50 次），
        // 使 declareAccident 内的 earn 返回 0 → 补偿 deferred。
        vm.startPrank(address(season1));
        for (uint256 i = 0; i < 50; i++) {
            points.earn(ACTION_ACCIDENT, sAlice, bytes32(uint256(0xAAAA) + i));
        }
        vm.stopPrank();

        uint256 before = points.balanceOf(aiId);

        vm.prank(ADMIN);
        season1.declareAccident(orderId, keccak256("evidence"));

        HahaSeason1.Order memory o = season1.order(orderId);
        assertEq(uint8(o.status), uint8(HahaSeason1.OrderStatus.AccidentRefunded), "refunded, deferred");
        (bool refunded, bool compensated) = season1.accidentOf(orderId);
        assertTrue(refunded, "refunded");
        assertFalse(compensated, "not compensated");
        assertEq(points.balanceOf(aiId), before + 200, "only refund 200");

        // 跨天，perUserDailyCap 重置
        vm.warp(uint256(DAY + 1) * 86400);

        vm.prank(sAlice);
        season1.claimAccidentCredit(orderId);

        // 只补 100，不重复退 200
        assertEq(points.balanceOf(aiId), before + 200 + 100, "refund once + compensate 100");
        HahaSeason1.Order memory o2 = season1.order(orderId);
        assertEq(uint8(o2.status), uint8(HahaSeason1.OrderStatus.AccidentClosed), "closed");
    }
}
