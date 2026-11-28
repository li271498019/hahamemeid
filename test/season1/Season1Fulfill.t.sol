// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Season1TestBase} from "./Season1TestBase.sol";
import {HahaSeason1} from "src/HahaSeason1.sol";
import {HahaNamehash} from "src/libraries/HahaNamehash.sol";

/// @notice 完整发放流程测试：applyFor → adminMint（逐笔）→ 日志核对 → attestFulfillment。
///         覆盖：完整发放、重复铸造拒绝、铸到错误地址、attestFulfillment 幂等/零哈希/非 Pending 拒绝。
contract Season1FulfillTest is Season1TestBase {
    uint64 internal constant DAY = 20781;

    event NameMinted(uint256 indexed tokenId, address indexed owner, uint8 tld, bytes32 indexed aiId, string label, bool reservedMint);
    event Transfer(address indexed from, address indexed to, uint256 indexed tokenId);
    event FulfillmentAttested(uint256 indexed orderId, uint256 indexed tokenId, address indexed recipient, bytes32 mintTxHash);

    // ---------------------------------------------------------------------
    // 工具
    // ---------------------------------------------------------------------

    function _setupDayWithAlice(uint64 day, string memory label, uint8 tld)
        internal
        returns (bytes32 root, HahaSeason1.ApplyAuth memory auth, uint256 orderId)
    {
        bytes32 aiId = _aiId("salice");
        bytes32[] memory leaves = new bytes32[](1);
        leaves[0] = _leaf(aiId, 1000, uint8(HahaSeason1.Tier.Reserved));
        (root,) = _merkleRootAndProof(leaves, 0);

        vm.warp(uint256(day) * 86400);
        vm.roll(100);
        uint64 snapshotBlock = 80;
        vm.prank(ADMIN);
        season1.setDayRoot(day, root, snapshotBlock, blockhash(snapshotBlock), 1, 0);

        auth = HahaSeason1.ApplyAuth({
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
            tier: uint8(HahaSeason1.Tier.Reserved),
            balance: 1000
        });
        bytes32 digest = _applyAuthDigest(auth);
        bytes memory sig = _sign(ALICE_PK, digest);
        vm.prank(sAlice);
        orderId = season1.applyFor(auth, sig, new bytes32[](0));
    }

    // ---------------------------------------------------------------------
    // 测试
    // ---------------------------------------------------------------------

    /// 完整发放流程：apply 后 adminMint 铸给原收件人，NameMinted + Transfer 事件齐，
    /// 然后 attestFulfillment 把订单变成 Fulfilled。
    function test_fulfill_complete_flow() public {
        (,, uint256 orderId) = _setupDayWithAlice(DAY, "ab", 0);
        uint256 tokenId = uint256(HahaNamehash.namehash(HahaNamehash.tldNode(0), keccak256("ab")));

        // adminMint 铸给原收件人 0xBEEF（逐笔，一次一个名字）
        // 注意：adminMint 铸造的名字 aiId = bytes32(0)（管理员铸造，不绑定 aiId）
        vm.startPrank(ADMIN);
        vm.expectEmit(true, true, true, true, address(registrar));
        emit NameMinted(tokenId, address(0xBEEF), 0, bytes32(0), "ab", true);
        registrar.adminMint("ab", 0, address(0xBEEF));
        vm.stopPrank();

        // 名字已铸造
        assertTrue(registrar.isMinted(bytes32(tokenId)), "minted");
        assertEq(registrar.ownerOf(tokenId), address(0xBEEF), "owner is recipient");

        // 订单仍是 Pending（attestFulfillment 之前）
        HahaSeason1.Order memory o = season1.order(orderId);
        assertEq(uint8(o.status), uint8(HahaSeason1.OrderStatus.Pending), "still pending before attest");

        // currentOwnerMatches 为 true（此刻所有者仍为接收人）
        assertTrue(season1.currentOwnerMatches(orderId), "current owner matches");

        // attestFulfillment（参数里没有 tokenId，只有 orderId + mintTxHash）
        bytes32 mintTxHash = keccak256("mint-tx");
        vm.startPrank(ADMIN);
        vm.expectEmit(true, true, true, true, address(season1));
        emit FulfillmentAttested(orderId, tokenId, address(0xBEEF), mintTxHash);
        season1.attestFulfillment(orderId, mintTxHash);
        vm.stopPrank();

        o = season1.order(orderId);
        assertEq(uint8(o.status), uint8(HahaSeason1.OrderStatus.Fulfilled), "fulfilled");
    }

    /// 重复铸造同一名字会 revert（NameTaken），不重复发放。
    function test_fulfill_double_adminMint_reverts() public {
        _setupDayWithAlice(DAY, "ab", 0);
        vm.startPrank(ADMIN);
        registrar.adminMint("ab", 0, address(0xBEEF));
        vm.expectRevert(); // NameTaken
        registrar.adminMint("ab", 0, address(0xBEEF));
        vm.stopPrank();
    }

    /// 铸到错误地址：NameMinted owner != 原收件人，currentOwnerMatches 返回 false，
    /// 不能据此标「已发放」。面板层据此标 mismatch，不调用成功确认。
    function test_fulfill_wrong_recipient_owner_mismatch() public {
        (,, uint256 orderId) = _setupDayWithAlice(DAY, "ab", 0);
        address wrong = address(0xC0FFEE);

        vm.prank(ADMIN);
        registrar.adminMint("ab", 0, wrong);

        // 名字铸给了错误地址
        assertEq(registrar.ownerOf(uint256(HahaNamehash.namehash(HahaNamehash.tldNode(0), keccak256("ab")))), wrong, "owner is wrong");
        // currentOwnerMatches 为 false
        assertFalse(season1.currentOwnerMatches(orderId), "owner does not match recipient");
        // 订单仍 Pending（未见证）
        HahaSeason1.Order memory o = season1.order(orderId);
        assertEq(uint8(o.status), uint8(HahaSeason1.OrderStatus.Pending), "still pending");
    }

    /// attestFulfillment 幂等：第二次调用直接 return，不再发事件。
    function test_fulfill_attest_idempotent() public {
        (,, uint256 orderId) = _setupDayWithAlice(DAY, "ab", 0);
        vm.startPrank(ADMIN);
        registrar.adminMint("ab", 0, address(0xBEEF));
        bytes32 mintTxHash = keccak256("mint-tx");
        season1.attestFulfillment(orderId, mintTxHash);
        // 第二次调用幂等，不 revert
        season1.attestFulfillment(orderId, mintTxHash);
        vm.stopPrank();
        HahaSeason1.Order memory o = season1.order(orderId);
        assertEq(uint8(o.status), uint8(HahaSeason1.OrderStatus.Fulfilled), "fulfilled once");
    }

    /// attestFulfillment 传零 mintTxHash 会 revert（ZeroAddress）。
    function test_fulfill_attest_zeroHash_reverts() public {
        (,, uint256 orderId) = _setupDayWithAlice(DAY, "ab", 0);
        vm.startPrank(ADMIN);
        registrar.adminMint("ab", 0, address(0xBEEF));
        vm.expectRevert(HahaSeason1.ZeroAddress.selector);
        season1.attestFulfillment(orderId, bytes32(0));
        vm.stopPrank();
    }

    /// 非 Pending 订单不能 attestFulfillment（已 Fulfilled 幂等已覆盖；这里测 CreditOpen）。
    function test_fulfill_attest_nonPending_reverts() public {
        (,, uint256 orderId) = _setupDayWithAlice(DAY, "ab", 0);
        // 先见证成功 → Fulfilled；再测一个不存在的 orderId（status=None）→ StillPending
        vm.startPrank(ADMIN);
        registrar.adminMint("ab", 0, address(0xBEEF));
        season1.attestFulfillment(orderId, keccak256("mint-tx"));
        vm.stopPrank();

        // 不存在的订单 status=None → StillPending
        vm.prank(ADMIN);
        vm.expectRevert(HahaSeason1.StillPending.selector);
        season1.attestFulfillment(9999, keccak256("mint-tx"));
    }
}
