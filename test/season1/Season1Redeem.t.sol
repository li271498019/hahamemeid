// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Season1TestBase} from "./Season1TestBase.sol";
import {HahaSeason1} from "src/HahaSeason1.sol";

contract Season1RedeemTest is Season1TestBase {
    uint64 internal constant DAY = 20781;

    // ---------------------------------------------------------------------
    // 工具
    // ---------------------------------------------------------------------

    /// @dev 准备某天的 root：warp 到当天、roll 块号、setDayRoot。
    function _setupDay(uint64 day, bytes32[] memory leaves, uint16 reservedCount, uint16 remainingSlots)
        internal
        returns (bytes32 root)
    {
        vm.warp(uint256(day) * 86400);
        vm.roll(100);
        uint64 snapshotBlock = 80; // 80 + 15 = 95 <= 100
        (root,) = _rootOf(leaves);
        vm.prank(ADMIN);
        season1.setDayRoot(day, root, snapshotBlock, blockhash(snapshotBlock), reservedCount, remainingSlots);
    }

    function _rootOf(bytes32[] memory leaves) internal pure returns (bytes32 root, bytes32[] memory dummy) {
        if (leaves.length == 1) return (leaves[0], new bytes32[](0));
        (root,) = _merkleRootAndProof(leaves, 0);
    }

    function _applyAuth(uint64 day, bytes32 aiId, string memory label, uint8 tld, bytes32 root, uint8 tier, uint256 balance)
        internal
        view
        returns (HahaSeason1.ApplyAuth memory)
    {
        return HahaSeason1.ApplyAuth({
            seasonId: 1,
            dayIndex: day,
            aiId: aiId,
            label: label,
            tld: tld,
            price: 200,
            recipient: address(0xBEEF),
            nonce: 0,
            deadline: (day + 1) * 86400,
            root: root,
            tier: tier,
            balance: balance
        });
    }

    function _applyAndSign(
        address user,
        uint256 pk,
        HahaSeason1.ApplyAuth memory auth,
        bytes32[] memory proof
    ) internal returns (uint256 orderId) {
        bytes32 digest = _applyAuthDigest(auth);
        bytes memory sig = _sign(pk, digest);
        vm.prank(user);
        orderId = season1.applyFor(auth, sig, proof);
    }

    // ---------------------------------------------------------------------
    // 测试
    // ---------------------------------------------------------------------

    function test_apply_success() public {
        bytes32 aiId = _aiId("salice");
        bytes32[] memory leaves = new bytes32[](1);
        leaves[0] = _leaf(aiId, 1000, uint8(HahaSeason1.Tier.Reserved));
        bytes32 root = _setupDay(DAY, leaves, 1, 0);

        uint256 before = points.balanceOf(aiId);
        HahaSeason1.ApplyAuth memory auth =
            _applyAuth(DAY, aiId, "ab", 0, root, uint8(HahaSeason1.Tier.Reserved), 1000);
        bytes32[] memory proof = new bytes32[](0);

        uint256 orderId = _applyAndSign(sAlice, ALICE_PK, auth, proof);

        assertEq(orderId, 1, "first order id");
        assertEq(points.balanceOf(aiId), before - 200, "spend 200");
        assertEq(season1.seasonOrderOf(aiId), orderId, "season order");
        assertEq(season1.nameLock(0, "ab"), orderId, "name locked");
        HahaSeason1.Order memory o = season1.order(orderId);
        assertEq(uint8(o.status), uint8(HahaSeason1.OrderStatus.Pending), "pending");
        assertEq(o.recipient, address(0xBEEF), "recipient");
        assertEq(uint8(o.tier), uint8(HahaSeason1.Tier.Reserved), "tier");
    }

    function test_apply_wrongPrice_reverts() public {
        bytes32 aiId = _aiId("salice");
        bytes32[] memory leaves = new bytes32[](1);
        leaves[0] = _leaf(aiId, 1000, 0);
        bytes32 root = _setupDay(DAY, leaves, 1, 0);

        HahaSeason1.ApplyAuth memory auth = _applyAuth(DAY, aiId, "ab", 0, root, 0, 1000);
        auth.price = 199;
        bytes32 digest = _applyAuthDigest(auth);
        bytes memory sig = _sign(ALICE_PK, digest);
        vm.prank(sAlice);
        vm.expectRevert(HahaSeason1.BadPrice.selector);
        season1.applyFor(auth, sig, new bytes32[](0));
    }

    function test_apply_wrongTier_reverts() public {
        bytes32 aiId = _aiId("salice");
        bytes32[] memory leaves = new bytes32[](1);
        leaves[0] = _leaf(aiId, 1000, 0);
        bytes32 root = _setupDay(DAY, leaves, 1, 0);

        HahaSeason1.ApplyAuth memory auth = _applyAuth(DAY, aiId, "ab", 0, root, 1, 1000);
        // tier 改成 1 但 leaf 是 tier 0，证明失败
        bytes32 digest = _applyAuthDigest(auth);
        bytes memory sig = _sign(ALICE_PK, digest);
        vm.prank(sAlice);
        vm.expectRevert(HahaSeason1.BadProof.selector);
        season1.applyFor(auth, sig, new bytes32[](0));
    }

    function test_apply_outsidePool_reverts() public {
        bytes32 aiId = _aiId("salice");
        bytes32[] memory leaves = new bytes32[](1);
        leaves[0] = _leaf(aiId, 1000, 0);
        bytes32 root = _setupDay(DAY, leaves, 1, 0);

        // 3 位名字
        HahaSeason1.ApplyAuth memory auth = _applyAuth(DAY, aiId, "abc", 0, root, 0, 1000);
        bytes32 digest = _applyAuthDigest(auth);
        bytes memory sig = _sign(ALICE_PK, digest);
        vm.prank(sAlice);
        vm.expectRevert(HahaSeason1.OutsidePool.selector);
        season1.applyFor(auth, sig, new bytes32[](0));
    }

    function test_apply_mixedCaseOrMixed_reverts() public {
        bytes32 aiId = _aiId("salice");
        bytes32[] memory leaves = new bytes32[](1);
        leaves[0] = _leaf(aiId, 1000, 0);
        bytes32 root = _setupDay(DAY, leaves, 1, 0);

        // 混合位（数字 + 字母）
        HahaSeason1.ApplyAuth memory auth = _applyAuth(DAY, aiId, "a1", 0, root, 0, 1000);
        bytes32 digest = _applyAuthDigest(auth);
        bytes memory sig = _sign(ALICE_PK, digest);
        vm.prank(sAlice);
        vm.expectRevert(HahaSeason1.OutsidePool.selector);
        season1.applyFor(auth, sig, new bytes32[](0));
    }

    function test_apply_seasonUsed_reverts() public {
        bytes32 aiId = _aiId("salice");
        bytes32[] memory leaves = new bytes32[](1);
        leaves[0] = _leaf(aiId, 1000, 0);
        bytes32 root = _setupDay(DAY, leaves, 1, 0);

        HahaSeason1.ApplyAuth memory auth = _applyAuth(DAY, aiId, "ab", 0, root, 0, 1000);
        bytes32 digest = _applyAuthDigest(auth);
        bytes memory sig = _sign(ALICE_PK, digest);
        vm.startPrank(sAlice);
        season1.applyFor(auth, sig, new bytes32[](0));

        // 第二笔（换名字）→ SeasonUsed
        HahaSeason1.ApplyAuth memory auth2 = _applyAuth(DAY, aiId, "cd", 0, root, 0, 1000);
        auth2.nonce = 1; // nonce 已 +1
        bytes32 digest2 = _applyAuthDigest(auth2);
        bytes memory sig2 = _sign(ALICE_PK, digest2);
        vm.expectRevert(HahaSeason1.SeasonUsed.selector);
        season1.applyFor(auth2, sig2, new bytes32[](0));
        vm.stopPrank();
    }

    function test_apply_badSignature_reverts() public {
        bytes32 aiId = _aiId("salice");
        bytes32[] memory leaves = new bytes32[](1);
        leaves[0] = _leaf(aiId, 1000, 0);
        bytes32 root = _setupDay(DAY, leaves, 1, 0);

        HahaSeason1.ApplyAuth memory auth = _applyAuth(DAY, aiId, "ab", 0, root, 0, 1000);
        // 用 bob 的私钥签名（但 msg.sender 是 alice）
        bytes32 digest = _applyAuthDigest(auth);
        bytes memory sig = _sign(BOB_PK, digest);
        vm.prank(sAlice);
        vm.expectRevert(HahaSeason1.BadSignature.selector);
        season1.applyFor(auth, sig, new bytes32[](0));
    }

    function test_apply_boundaryFull_reverts() public {
        bytes32 aiId1 = _aiId("salice");
        bytes32 aiId2 = _aiId("sbob");
        bytes32 aiId3 = _aiId("scarol");
        // 3 个 boundary，remainingSlots = 2，第 3 个 BoundaryFull
        bytes32[] memory leaves = new bytes32[](3);
        leaves[0] = _leaf(aiId1, 1000, 1);
        leaves[1] = _leaf(aiId2, 1000, 1);
        leaves[2] = _leaf(aiId3, 1000, 1);
        bytes32 root = _setupDay(DAY, leaves, 0, 2);

        // alice 成功
        HahaSeason1.ApplyAuth memory a1 = _applyAuth(DAY, aiId1, "ab", 0, root, 1, 1000);
        (bytes32[] memory p1,) = _proofFor(leaves, 0);
        _applyAndSign(sAlice, ALICE_PK, a1, p1);

        // bob 成功
        HahaSeason1.ApplyAuth memory a2 = _applyAuth(DAY, aiId2, "cd", 0, root, 1, 1000);
        (bytes32[] memory p2,) = _proofFor(leaves, 1);
        _applyAndSign(sBob, BOB_PK, a2, p2);

        // carol 第 3 个 → BoundaryFull
        HahaSeason1.ApplyAuth memory a3 = _applyAuth(DAY, aiId3, "ef", 0, root, 1, 1000);
        (bytes32[] memory p3,) = _proofFor(leaves, 2);
        bytes32 digest = _applyAuthDigest(a3);
        bytes memory sig = _sign(CAROL_PK, digest);
        vm.prank(sCarol);
        vm.expectRevert(HahaSeason1.BoundaryFull.selector);
        season1.applyFor(a3, sig, p3);
    }

    function _proofFor(bytes32[] memory leaves, uint256 idx)
        internal
        pure
        returns (bytes32[] memory proof, bytes32 root)
    {
        (root, proof) = _merkleRootAndProof(leaves, idx);
    }
}
