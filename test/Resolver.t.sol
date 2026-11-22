// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Test, Vm} from "forge-std/Test.sol";
import {HahaTestBase} from "./HahaTestBase.sol";
import {HahaResolver} from "src/HahaResolver.sol";
import {HahaRegistry} from "src/HahaRegistry.sol";
import {HahaRegistrar} from "src/HahaRegistrar.sol";
import {HahaConstants} from "src/libraries/HahaConstants.sol";

/// @title ResolverTest
/// @notice `addr`、`text`、主名字，以及「转让必须清干净」这条最关键的安全性要求。
contract ResolverTest is HahaTestBase {
    bytes32 internal node;
    uint256 internal tokenId;

    function setUp() public override {
        super.setUp();
        tokenId = _register(alice, "abc", 0);
        node = bytes32(tokenId);
    }

    // =====================================================================
    // addr（SPEC 6.4）
    // =====================================================================

    /// @notice 没有覆盖时 `addr` 等于 NFT owner。
    function test_addr_fallsBackToNftOwner() public view {
        assertEq(resolver.addr(node), alice, "no override => nft owner");
    }

    /// @notice 名字不存在时 `addr` 返回 0。
    function test_addr_nonExistent_returnsZero() public view {
        assertEq(resolver.addr(_node("nope", 0)), address(0));
    }

    /// @notice 设置覆盖后 `addr` 等于覆盖地址。
    function test_addr_override() public {
        vm.prank(alice);
        resolver.setAddr(node, bob);

        assertEq(resolver.addr(node), bob, "override wins");
        // NFT owner 没变
        assertEq(registrar.ownerOf(tokenId), alice);
    }

    /// @notice 覆盖被清掉之后，`addr` 回到「当前 NFT owner」，不是返回 0。
    function test_addr_clearOverride_fallsBackToOwner() public {
        vm.prank(alice);
        resolver.setAddr(node, bob);
        assertEq(resolver.addr(node), bob);

        vm.prank(alice);
        resolver.setAddr(node, address(0));
        assertEq(resolver.addr(node), alice, "falls back to owner after clearing");
    }

    /// @notice 只有 node owner 能设置覆盖。
    function test_setAddr_onlyNodeOwner() public {
        vm.prank(bob);
        vm.expectRevert(HahaResolver.NotNodeOwner.selector);
        resolver.setAddr(node, bob);
    }

    /// @notice 名字不存在时不能设地址。
    function test_setAddr_nonExistent_reverts() public {
        vm.prank(alice);
        vm.expectRevert(HahaResolver.NameDoesNotExist.selector);
        resolver.setAddr(_node("nope", 0), bob);
    }

    /// @notice `AddrChanged` 事件。
    function test_setAddr_event() public {
        vm.expectEmit(true, false, false, true, address(resolver));
        emit HahaResolver.AddrChanged(node, bob);

        vm.prank(alice);
        resolver.setAddr(node, bob);
    }

    // =====================================================================
    // text（SPEC 6.4）
    // =====================================================================

    function test_setText_andRead() public {
        vm.prank(alice);
        resolver.setText(node, "description", "hello world");

        assertEq(resolver.text(node, "description"), "hello world");
        assertEq(resolver.text(node, "absent"), "");
    }

    /// @notice 只有 node owner 能写 text。
    function test_setText_onlyNodeOwner() public {
        vm.prank(bob);
        vm.expectRevert(HahaResolver.NotNodeOwner.selector);
        resolver.setText(node, "k", "v");
    }

    /// @notice key 长度 1–64。
    function test_setText_keyLength() public {
        vm.startPrank(alice);

        vm.expectRevert(abi.encodeWithSelector(HahaResolver.InvalidKeyLength.selector, 0));
        resolver.setText(node, "", "v");

        string memory k65 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"; // 65
        assertEq(bytes(k65).length, 65);
        vm.expectRevert(abi.encodeWithSelector(HahaResolver.InvalidKeyLength.selector, 65));
        resolver.setText(node, k65, "v");

        vm.stopPrank();
    }

    /// @notice value 最长 1024 字节。
    function test_setText_valueLength() public {
        bytes memory v1025 = new bytes(1025);
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(HahaResolver.InvalidValueLength.selector, 1025));
        resolver.setText(node, "k", string(v1025));
    }

    /// @notice 每个 node 最多 16 个 key；覆盖已有 key 不占新名额。
    function test_setText_max16Keys() public {
        vm.startPrank(alice);
        for (uint256 i = 0; i < HahaConstants.MAX_TEXT_KEYS; ++i) {
            resolver.setText(node, string.concat("k", vm.toString(i)), "v");
        }

        // 第 17 个失败
        vm.expectRevert(abi.encodeWithSelector(HahaResolver.TooManyTextKeys.selector, 16));
        resolver.setText(node, "k16", "v");

        // 覆盖已有 key 仍然可以
        resolver.setText(node, "k0", "updated");
        assertEq(resolver.text(node, "k0"), "updated");

        vm.stopPrank();
    }

    /// @notice value 为空表示删除该 key，名额可以复用。
    function test_setText_emptyValueDeletes() public {
        vm.startPrank(alice);
        for (uint256 i = 0; i < 16; ++i) {
            resolver.setText(node, string.concat("k", vm.toString(i)), "v");
        }

        // 删一个
        resolver.setText(node, "k0", "");
        assertEq(resolver.text(node, "k0"), "");

        // 现在又有名额了
        resolver.setText(node, "newkey", "v");
        assertEq(resolver.text(node, "newkey"), "v");
        vm.stopPrank();
    }

    /// @notice 对不存在的 key 写空值不占名额、不 revert。
    function test_setText_emptyOnAbsentKey_isNoop() public {
        vm.startPrank(alice);
        for (uint256 i = 0; i < 16; ++i) {
            resolver.setText(node, string.concat("k", vm.toString(i)), "v");
        }
        // 满额时写空值给不存在的 key 不应失败
        resolver.setText(node, "ghost", "");
        vm.stopPrank();
    }

    /// @notice `TextChanged` 事件带 value（比 ENS 多一个字段）。
    function test_setText_event() public {
        vm.expectEmit(true, true, false, true, address(resolver));
        emit HahaResolver.TextChanged(node, "description", "description", "hi");

        vm.prank(alice);
        resolver.setText(node, "description", "hi");
    }

    // =====================================================================
    // clearRecords（SPEC 6.4）
    // =====================================================================

    /// @notice 只有 Registrar 能调用。
    function test_clearRecords_onlyRegistrar() public {
        vm.prank(alice);
        vm.expectRevert(HahaResolver.NotRegistrar.selector);
        resolver.clearRecords(node);
    }

    /// @notice 清空覆盖、text、主名字，并发出 `RecordsCleared`。
    function test_clearRecords_clearsEverything() public {
        vm.startPrank(alice);
        resolver.setAddr(node, bob);
        resolver.setText(node, "description", "hi");
        resolver.setText(node, "url", "https://x");
        vm.stopPrank();

        // bob 设主名字（addr 指向 bob）
        vm.prank(bob);
        resolver.setPrimaryName("abc", 0);

        assertEq(resolver.primaryNode(bob), node);

        // 模拟 Registrar 调用
        vm.prank(address(registrar));
        resolver.clearRecords(node);

        assertEq(resolver.addr(node), alice, "override cleared, falls back to owner");
        assertEq(resolver.text(node, "description"), "");
        assertEq(resolver.text(node, "url"), "");
        assertEq(resolver.primaryNode(bob), bytes32(0), "primary name cleared");
    }

    /// @notice **关键**：对「什么都没有」的 token，`clearRecords` 也必须成功返回。
    /// @dev 否则用户 NFT 会被卡死（SPEC 6.3、11）。
    function test_clearRecords_noopDoesNotRevert() public {
        vm.prank(address(registrar));
        resolver.clearRecords(node); // 没有覆盖、没有 text、没有主名字
    }

    /// @notice `RecordsCleared` 不为每个 key 重复发 `TextChanged`。
    function test_clearRecords_doesNotEmitTextChanged() public {
        vm.startPrank(alice);
        resolver.setText(node, "a", "1");
        resolver.setText(node, "b", "2");
        vm.stopPrank();

        vm.recordLogs();
        vm.prank(address(registrar));
        resolver.clearRecords(node);
        Vm.Log[] memory entries = vm.getRecordedLogs();

        bytes32 textChangedSig = keccak256("TextChanged(bytes32,string,string,string)");
        for (uint256 i = 0; i < entries.length; ++i) {
            assertTrue(entries[i].topics[0] != textChangedSig, "no TextChanged during clear");
        }
    }

    // =====================================================================
    // 主名字（SPEC 6.4）
    // =====================================================================

    /// @notice NFT owner 在没设覆盖时可以直接设主名字（`addr` 回落）。
    function test_setPrimaryName_byNftOwner() public {
        vm.prank(alice);
        resolver.setPrimaryName("abc", 0);

        assertEq(resolver.primaryNode(alice), node);
        assertEq(resolver.primaryName(alice), "abc.haha");
        assertEq(resolver.primaryHolder(node), alice);
    }

    /// @notice 要求当时 `addr(node) == msg.sender`。
    function test_setPrimaryName_requiresAddrEqualsSender() public {
        // bob 既不是 owner 也没被 addr 指向
        vm.prank(bob);
        vm.expectRevert(HahaResolver.AddrNotSelf.selector);
        resolver.setPrimaryName("abc", 0);
    }

    /// @notice owner 把 addr 指到 bob 之后，bob 才能设主名字。
    function test_setPrimaryName_afterAddrOverride() public {
        vm.prank(alice);
        resolver.setAddr(node, bob);

        vm.prank(alice);
        vm.expectRevert(HahaResolver.AddrNotSelf.selector);
        resolver.setPrimaryName("abc", 0);

        vm.prank(bob);
        resolver.setPrimaryName("abc", 0);
        assertEq(resolver.primaryNode(bob), node);
    }

    /// @notice 一个地址只有一个主名字：设新的会替换旧的。
    function test_setPrimaryName_replaces() public {
        _skipCooldown(alice, "alice");
        uint256 token2 = _register(alice, "xyz", 0);
        bytes32 node2 = bytes32(token2);

        vm.prank(alice);
        resolver.setPrimaryName("abc", 0);
        assertEq(resolver.primaryNode(alice), node);

        vm.prank(alice);
        resolver.setPrimaryName("xyz", 0);
        assertEq(resolver.primaryNode(alice), node2, "replaced");
        assertEq(resolver.primaryName(alice), "xyz.haha");
        assertEq(resolver.primaryHolder(node), address(0), "old holder released");
        assertEq(resolver.primaryHolder(node2), alice);
    }

    /// @notice 把 addr 改走之后，旧的主名字视图返回空。
    function test_primaryName_invalidAfterAddrMoved() public {
        vm.prank(alice);
        resolver.setPrimaryName("abc", 0);
        assertEq(resolver.primaryName(alice), "abc.haha");

        // owner 把 addr 指到 carol
        vm.prank(alice);
        resolver.setAddr(node, carol);

        assertEq(resolver.primaryName(alice), "", "stale primary must be empty");
        assertEq(resolver.primaryNode(alice), bytes32(0), "cleared");
        // primaryHolder 也要清掉，不能悬空占用
        assertEq(resolver.primaryHolder(node), address(0), "no dangling holder");
    }

    /// @notice `clearPrimaryName` 清自己的主名字。
    function test_clearPrimaryName() public {
        vm.prank(alice);
        resolver.setPrimaryName("abc", 0);

        vm.prank(alice);
        resolver.clearPrimaryName();

        assertEq(resolver.primaryNode(alice), bytes32(0));
        assertEq(resolver.primaryHolder(node), address(0));
    }

    /// @notice 没有主名字时 `clearPrimaryName` 不 revert。
    function test_clearPrimaryName_noop() public {
        vm.prank(alice);
        resolver.clearPrimaryName();
    }

    /// @notice 名字不存在时不能设主名字。
    function test_setPrimaryName_nonExistentName() public {
        vm.prank(alice);
        vm.expectRevert(HahaResolver.NameDoesNotExist.selector);
        resolver.setPrimaryName("nope", 0);
    }

    /// @notice `PrimaryNameSet` 事件的 fullName。
    function test_setPrimaryName_event() public {
        vm.expectEmit(true, true, false, true, address(resolver));
        emit HahaResolver.PrimaryNameSet(alice, node, "abc.haha");

        vm.prank(alice);
        resolver.setPrimaryName("abc", 0);
    }

    // =====================================================================
    // ERC-165（SPEC 6.4）
    // =====================================================================

    function test_supportsInterface() public view {
        assertTrue(resolver.supportsInterface(0x01ffc9a7), "ERC-165");
        assertTrue(resolver.supportsInterface(0x3b3b57de), "addr(bytes32)");
        assertTrue(resolver.supportsInterface(0x59d1d43c), "text(bytes32,string)");
        // 不支持这些
        assertFalse(resolver.supportsInterface(0xf1cb7e06), "addr(bytes32,uint256) multi-coin");
        assertFalse(resolver.supportsInterface(0xbc1c58d1), "contenthash");
        assertFalse(resolver.supportsInterface(0xc8690233), "pubkey");
        assertFalse(resolver.supportsInterface(0x691f3431), "ENS name(bytes32)");
    }
}
