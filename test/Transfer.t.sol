// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {HahaTestBase} from "./HahaTestBase.sol";
import {HahaRegistry} from "src/HahaRegistry.sol";
import {HahaResolver} from "src/HahaResolver.sol";
import {HahaAgentIdentity} from "src/HahaAgentIdentity.sol";
import {HahaRegistrar} from "src/HahaRegistrar.sol";
import {HahaReputation} from "src/HahaReputation.sol";

/// @title TransferTest
/// @notice SPEC 6.3 的转账钩子：owner 更新后依次 `syncOwner` → `clearRecords` → `deactivate`，
///         且这三步在「什么都没有」时也必须成功返回，否则用户 NFT 会被卡死。
///         这是审计重点之一：「转让是否一定清掉解析和 agent」。
contract TransferTest is HahaTestBase {
    uint256 internal tokenId;
    bytes32 internal node;

    function setUp() public override {
        super.setUp();
        tokenId = _register(alice, "abc", 0);
        node = bytes32(tokenId);
    }

    // =====================================================================
    // 基本同步
    // =====================================================================

    /// @notice 转账后注册表 owner 跟随 NFT owner。
    function test_transfer_syncsRegistryOwner() public {
        vm.prank(alice);
        registrar.transferFrom(alice, bob, tokenId);

        assertEq(registrar.ownerOf(tokenId), bob, "nft owner");
        assertEq(registry.owner(node), bob, "registry owner");
        assertEq(registry.resolver(node), address(resolver), "resolver unchanged");
    }

    /// @notice 注册表发出 EIP-137 的 `Transfer`（不是 ERC-721 的）。
    function test_transfer_emitsRegistryTransfer() public {
        vm.expectEmit(true, false, false, true, address(registry));
        emit HahaRegistry.Transfer(node, bob);

        vm.prank(alice);
        registrar.transferFrom(alice, bob, tokenId);
    }

    // =====================================================================
    // 清空解析记录
    // =====================================================================

    /// @notice 转账后 addr 覆盖为 0、text 为空。
    function test_transfer_clearsResolverRecords() public {
        vm.startPrank(alice);
        resolver.setAddr(node, carol);
        resolver.setText(node, "description", "hello");
        resolver.setText(node, "url", "https://x");
        vm.stopPrank();

        assertEq(resolver.addr(node), carol);
        assertEq(resolver.text(node, "description"), "hello");

        vm.prank(alice);
        registrar.transferFrom(alice, bob, tokenId);

        // 覆盖被清 => addr 回到新 owner
        assertEq(resolver.addr(node), bob, "addr falls back to new owner");
        assertEq(resolver.text(node, "description"), "", "text cleared");
        assertEq(resolver.text(node, "url"), "", "text cleared");
    }

    /// @notice 转账后主名字被清空。
    function test_transfer_clearsPrimaryName() public {
        vm.prank(alice);
        resolver.setPrimaryName("abc", 0);
        assertEq(resolver.primaryName(alice), "abc.haha");

        vm.prank(alice);
        registrar.transferFrom(alice, bob, tokenId);

        assertEq(resolver.primaryNode(alice), bytes32(0), "primary cleared");
        assertEq(bytes(resolver.primaryName(alice)).length, 0);
        assertEq(resolver.primaryHolder(node), address(0), "holder released");
    }

    /// @notice 若主名字挂在 addr 指向的第三方上，转让也要清掉那个人的主名字。
    function test_transfer_clearsThirdPartyPrimaryName() public {
        vm.prank(alice);
        resolver.setAddr(node, carol);

        vm.prank(carol);
        resolver.setPrimaryName("abc", 0);
        assertEq(resolver.primaryName(carol), "abc.haha");

        vm.prank(alice);
        registrar.transferFrom(alice, bob, tokenId);

        assertEq(resolver.primaryNode(carol), bytes32(0), "third-party primary cleared");
    }

    // =====================================================================
    // 清空 agent
    // =====================================================================

    /// @notice 转让后 agent 被 burn，`agentOfName` 为 0，旧 agent `ownerOf` revert。
    function test_transfer_burnsAgent() public {
        vm.prank(alice);
        uint256 agentId = identity.activateAgent("abc", 0, "ipfs://meta");
        assertEq(identity.agentOfName(tokenId), agentId);
        assertTrue(identity.isActive(agentId));

        vm.prank(alice);
        registrar.transferFrom(alice, bob, tokenId);

        assertEq(identity.agentOfName(tokenId), 0, "agentOfName cleared");
        assertFalse(identity.isActive(agentId), "inactive");

        vm.expectRevert();
        identity.ownerOf(agentId);
    }

    /// @notice 转让后声誉：旧 agentId 的历史分数保留，新 agent 从 0 开始。
    function test_transfer_reputationResetsNewAgent() public {
        vm.prank(alice);
        uint256 oldAgentId = identity.activateAgent("abc", 0, "ipfs://meta");

        // bob 打分（评分门槛：bob 必须持有名字）
        _skipCooldown(bob, "bob");
        _register(bob, "bobname", 0);
        vm.prank(bob);
        reputation.rate(oldAgentId, 5, "great");

        (uint64 count, uint256 sum) = reputation.getScore(oldAgentId);
        assertEq(count, 1);
        assertEq(sum, 5);

        // 转让
        vm.prank(alice);
        registrar.transferFrom(alice, bob, tokenId);

        // 旧 id 的历史还在
        (uint64 count2, uint256 sum2) = reputation.getScore(oldAgentId);
        assertEq(count2, 1, "history kept");
        assertEq(sum2, 5);

        // 新持有人重新激活，拿到新 id，分数为 0
        vm.prank(bob);
        uint256 newAgentId = identity.activateAgent("abc", 0, "ipfs://meta2");
        assertTrue(newAgentId != oldAgentId, "new id");

        (uint64 count3, uint256 sum3) = reputation.getScore(newAgentId);
        assertEq(count3, 0, "new agent starts at 0");
        assertEq(sum3, 0);

        // 对旧 id 打分必须失败（不再 active）
        vm.prank(carol);
        vm.expectRevert(HahaReputation.AgentNotActive.selector);
        reputation.rate(oldAgentId, 3, "");
    }

    /// @notice 转让后 `getAgentWallet` 对旧 id 返回 0。
    function test_transfer_oldAgentWalletZero() public {
        vm.prank(alice);
        uint256 agentId = identity.activateAgent("abc", 0, "ipfs://meta");
        assertEq(identity.getAgentWallet(agentId), alice, "wallet = addr = owner");

        vm.prank(alice);
        registrar.transferFrom(alice, bob, tokenId);

        assertEq(identity.getAgentWallet(agentId), address(0), "inactive => 0");
    }

    // =====================================================================
    // 「什么都没有」时也必须成功（关键）
    // =====================================================================

    /// @notice 一个既没有解析记录也没有 agent 的名字，转让必须成功。
    /// @dev 这是 SPEC 6.3 与 11 明确要求的：否则用户 NFT 会被卡死。
    function test_transfer_bareToken_succeeds() public {
        // setUp 里铸的 abc 什么都没有。
        vm.prank(alice);
        registrar.transferFrom(alice, bob, tokenId);
        assertEq(registrar.ownerOf(tokenId), bob);
    }

    /// @notice 连续多次转让都成功。
    function test_transfer_multipleHops() public {
        vm.prank(alice);
        registrar.transferFrom(alice, bob, tokenId);

        vm.prank(bob);
        registrar.transferFrom(bob, carol, tokenId);

        vm.prank(carol);
        registrar.transferFrom(carol, dave, tokenId);

        assertEq(registrar.ownerOf(tokenId), dave);
        assertEq(registry.owner(node), dave);
    }

    /// @notice 带 `safeTransferFrom` 也要走同一套钩子。
    function test_transfer_safeTransferAlsoHooks() public {
        vm.startPrank(alice);
        resolver.setAddr(node, carol);
        resolver.setText(node, "k", "v");
        vm.stopPrank();

        vm.prank(alice);
        registrar.safeTransferFrom(alice, bob, tokenId);

        assertEq(registry.owner(node), bob);
        assertEq(resolver.addr(node), bob);
        assertEq(resolver.text(node, "k"), "");
    }

    // =====================================================================
    // 不能 burn
    // =====================================================================

    /// @notice 转到 address(0) 必须失败。
    function test_transferToZero_reverts() public {
        vm.prank(alice);
        vm.expectRevert();
        registrar.transferFrom(alice, address(0), tokenId);
    }

    /// @notice 合约没有暴露 burn。
    function test_noBurnFunction() public {
        (bool ok,) = address(registrar).call(abi.encodeWithSignature("burn(uint256)", tokenId));
        assertFalse(ok, "no burn");
    }

    // =====================================================================
    // resolver 与 registry 的所有权一致性（不变式的手动版本）
    // =====================================================================

    /// @notice 任何时刻 registry.owner 都等于 NFT owner。
    function test_registryOwnerAlwaysMatchesNft() public {
        assertEq(registry.owner(node), registrar.ownerOf(tokenId));

        vm.prank(alice);
        registrar.transferFrom(alice, bob, tokenId);
        assertEq(registry.owner(node), registrar.ownerOf(tokenId));

        vm.prank(bob);
        registrar.transferFrom(bob, carol, tokenId);
        assertEq(registry.owner(node), registrar.ownerOf(tokenId));
    }

    /// @notice registry.resolver 永远是规范解析器。
    function test_registryResolverAlwaysCanonical() public {
        assertEq(registry.resolver(node), address(resolver));

        vm.prank(alice);
        registrar.transferFrom(alice, bob, tokenId);

        assertEq(registry.resolver(node), address(resolver), "resolver never changes");
    }

    // =====================================================================
    // Registry 的权限边界（SPEC 6.2）
    // =====================================================================

    /// @notice 只有 Registrar 能 createName / syncOwner。
    function test_registry_onlyRegistrar() public {
        vm.startPrank(alice);
        vm.expectRevert(HahaRegistry.NotRegistrar.selector);
        registry.createName(0xaa5a3a58f7c8841455eecaa0c6a6a0b40ace5681fbb31361a0d45b168179128f, keccak256("zzz"), alice);

        vm.expectRevert(HahaRegistry.NotRegistrar.selector);
        registry.syncOwner(node, alice);
        vm.stopPrank();
    }

    /// @notice 没有 setOwner / setResolver / setTTL / setSubnodeOwner / reclaim。
    function test_registry_noUserEscalation() public {
        string[5] memory sigs = [
            "setOwner(bytes32,address)",
            "setResolver(bytes32,address)",
            "setTTL(bytes32,uint64)",
            "setSubnodeOwner(bytes32,bytes32,address)",
            "reclaim(bytes32,address)"
        ];
        for (uint256 i = 0; i < sigs.length; ++i) {
            (bool ok,) = address(registry).call(
                abi.encodeWithSignature(sigs[i], node, alice)
            );
            assertFalse(ok, sigs[i]);
        }
    }

    /// @notice 根 node 永远是 0，不能创建新 TLD。
    function test_registry_rootStaysZero() public view {
        assertEq(registry.owner(bytes32(0)), address(0));
        assertEq(registry.resolver(bytes32(0)), address(0));
    }

    /// @notice TLD node 的 owner 是 Registrar，不能 syncOwner 改它。
    function test_registry_cannotSyncTldNode() public {
        vm.prank(address(registrar));
        vm.expectRevert();
        registry.syncOwner(0xaa5a3a58f7c8841455eecaa0c6a6a0b40ace5681fbb31361a0d45b168179128f, bob);
    }
}
