// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Season1TestBase} from "./Season1TestBase.sol";
import {HahaSeason1} from "src/HahaSeason1.sol";

contract Season1RootTest is Season1TestBase {
    uint64 internal constant DAY = 20781;

    function test_setDayRoot_snapshotTooFresh_reverts() public {
        vm.warp(uint256(DAY) * 86400);
        vm.roll(100);
        // snapshotBlock = 95，95 + 15 = 110 > 100 → SnapshotTooFresh
        bytes32[] memory leaves = new bytes32[](1);
        leaves[0] = _leaf(_aiId("salice"), 1000, 0);

        vm.prank(ADMIN);
        vm.expectRevert(HahaSeason1.SnapshotTooFresh.selector);
        season1.setDayRoot(DAY, leaves[0], 95, blockhash(95), 1, 0);
    }

    function test_setDayRoot_depth15_passes() public {
        vm.warp(uint256(DAY) * 86400);
        vm.roll(100);
        bytes32[] memory leaves = new bytes32[](1);
        leaves[0] = _leaf(_aiId("salice"), 1000, 0);

        // snapshotBlock = 85，深度 = 100 - 85 = 15，恰好满足确认深度，且 blockhash 可读
        vm.prank(ADMIN);
        season1.setDayRoot(DAY, leaves[0], 85, blockhash(85), 1, 0);

        HahaSeason1.DayMarket memory m = season1.dayMarket(DAY);
        assertTrue(m.opened, "opened");
    }

    function test_setDayRoot_depth257_reverts() public {
        vm.warp(uint256(DAY) * 86400);
        vm.roll(400);
        bytes32[] memory leaves = new bytes32[](1);
        leaves[0] = _leaf(_aiId("salice"), 1000, 0);

        // snapshotBlock = 143，深度 = 400 - 143 = 257 > 256，blockhash 读不到 → StaleSnapshot
        vm.prank(ADMIN);
        vm.expectRevert(HahaSeason1.StaleSnapshot.selector);
        season1.setDayRoot(DAY, leaves[0], 143, blockhash(143), 1, 0);
    }

    function test_setDayRoot_depth256_reverts() public {
        vm.warp(uint256(DAY) * 86400);
        vm.roll(400);
        bytes32[] memory leaves = new bytes32[](1);
        leaves[0] = _leaf(_aiId("salice"), 1000, 0);

        // snapshotBlock = 144，深度 = 256，blockhash(144) 恰好返回 0 → StaleSnapshot
        vm.prank(ADMIN);
        vm.expectRevert(HahaSeason1.StaleSnapshot.selector);
        season1.setDayRoot(DAY, leaves[0], 144, blockhash(144), 1, 0);
    }

    function test_setDayRoot_wrongBlockHash_reverts() public {
        vm.warp(uint256(DAY) * 86400);
        vm.roll(100);
        bytes32[] memory leaves = new bytes32[](1);
        leaves[0] = _leaf(_aiId("salice"), 1000, 0);

        // snapshotBlock = 80 深度够，但 blockhash 传错
        vm.prank(ADMIN);
        vm.expectRevert(HahaSeason1.BadRoot.selector);
        season1.setDayRoot(DAY, leaves[0], 80, keccak256("wrong hash"), 1, 0);
    }

    function test_setDayRoot_overMaxSlots_reverts() public {
        vm.warp(uint256(DAY) * 86400);
        vm.roll(100);
        bytes32[] memory leaves = new bytes32[](1);
        leaves[0] = _leaf(_aiId("salice"), 1000, 0);

        // reservedCount + remainingSlots = 21 > 20
        vm.prank(ADMIN);
        vm.expectRevert(HahaSeason1.BadRoot.selector);
        season1.setDayRoot(DAY, leaves[0], 80, blockhash(80), 10, 11);
    }

    function test_setDayRoot_rootFrozen_reverts() public {
        vm.warp(uint256(DAY) * 86400);
        vm.roll(100);
        bytes32 aiId = _aiId("salice");
        bytes32[] memory leaves = new bytes32[](1);
        leaves[0] = _leaf(aiId, 1000, 0);
        vm.prank(ADMIN);
        season1.setDayRoot(DAY, leaves[0], 80, blockhash(80), 1, 0);

        // applyFor 一个订单
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
            root: leaves[0],
            tier: 0,
            balance: 1000
        });
        bytes32 digest = _applyAuthDigest(auth);
        bytes memory sig = _sign(ALICE_PK, digest);
        vm.prank(sAlice);
        season1.applyFor(auth, sig, new bytes32[](0));

        // 有订单后改 root → RootFrozen
        vm.roll(200);
        vm.prank(ADMIN);
        vm.expectRevert(HahaSeason1.RootFrozen.selector);
        season1.setDayRoot(DAY, keccak256("new root"), 150, blockhash(150), 1, 0);
    }

    function test_setDayRoot_emptyDay() public {
        vm.warp(uint256(DAY) * 86400);
        vm.roll(100);
        // 空日：root 为 0，计数为 0
        vm.prank(ADMIN);
        season1.setDayRoot(DAY, bytes32(0), 80, blockhash(80), 0, 0);

        HahaSeason1.DayMarket memory m = season1.dayMarket(DAY);
        assertTrue(m.opened, "opened");
        assertEq(m.remainingSlots, 0, "no slots");
    }
}
