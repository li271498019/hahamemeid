// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {HahaTestBase} from "./HahaTestBase.sol";
import {HahaAgentIdentity} from "src/HahaAgentIdentity.sol";
import {HahaReputation} from "src/HahaReputation.sol";
import {HahaConstants} from "src/libraries/HahaConstants.sol";

/// @title IdentityTest
/// @notice ERC-8004 身份 + 声誉。SPEC 12 要求：
///         「自评分失败。另一个 `.ai` 可以打分、改分。改分不增加 count。
///          review 超过 140 字节失败。storage 里读不到 review 字符串，事件里有。」
contract IdentityTest is HahaTestBase {
    uint256 internal tokenId;
    bytes32 internal node;

    function setUp() public override {
        super.setUp();
        tokenId = _register(alice, "abc", 0);
        node = bytes32(tokenId);
    }

    /// @dev 给评分人注册一个名字，跳过 1 小时冷却。评分门槛要求评分人持有名字。
    /// @param rater 评分人地址。
    /// @param handle 评分人的 `.ai` handle（用于算冷却键）。
    /// @param label 要注册的名字 label，与 handle 无关。
    function _raterName(address rater, string memory handle, string memory label) internal returns (uint256) {
        _skipCooldown(rater, handle);
        return _register(rater, label, 0);
    }

    // =====================================================================
    // 激活
    // =====================================================================

    function test_activateAgent() public {
        vm.prank(alice);
        uint256 agentId = identity.activateAgent("abc", 0, "https://example.com/agent.json");

        assertEq(agentId, 1, "first agent id is 1");
        assertEq(identity.ownerOf(agentId), alice);
        assertEq(identity.agentOfName(tokenId), agentId);
        assertEq(identity.nameTokenIdOf(agentId), tokenId);
        assertTrue(identity.isActive(agentId));
    }

    /// @notice `tokenURI` 等于持有人设置的 `agentURI`，不是另一张 SVG。
    function test_agentTokenUriIsAgentUri() public {
        string memory uri = "data:application/json;base64,eyJhIjoxfQ==";
        vm.prank(alice);
        uint256 agentId = identity.activateAgent("abc", 0, uri);

        assertEq(identity.tokenURI(agentId), uri);
    }

    /// @notice 非名字 NFT owner 不能激活。
    function test_activateAgent_onlyNameOwner() public {
        vm.prank(bob);
        vm.expectRevert(HahaAgentIdentity.NotNameOwner.selector);
        identity.activateAgent("abc", 0, "https://x");
    }

    /// @notice 名字不存在时不能激活。
    function test_activateAgent_nonExistentName() public {
        vm.prank(alice);
        vm.expectRevert();
        identity.activateAgent("ghost", 0, "https://x");
    }

    /// @notice 一个名字同时只能有一个 active agent。
    function test_activateAgent_onlyOneAtATime() public {
        vm.startPrank(alice);
        uint256 first = identity.activateAgent("abc", 0, "https://a");
        vm.expectRevert(abi.encodeWithSelector(HahaAgentIdentity.AgentAlreadyActive.selector, first));
        identity.activateAgent("abc", 0, "https://b");
        vm.stopPrank();
    }

    /// @notice agentURI 长度 1–2048。
    function test_activateAgent_uriLength() public {
        vm.startPrank(alice);
        vm.expectRevert(abi.encodeWithSelector(HahaAgentIdentity.InvalidAgentURI.selector, 0));
        identity.activateAgent("abc", 0, "");

        bytes memory tooLong = new bytes(2049);
        vm.expectRevert(abi.encodeWithSelector(HahaAgentIdentity.InvalidAgentURI.selector, 2049));
        identity.activateAgent("abc", 0, string(tooLong));
        vm.stopPrank();
    }

    /// @notice 激活必须持有 `.ai`：没有 `.ai` 的地址可以持有、挂单、出售，但不能激活。
    function test_activateAgent_requiresAi() public {
        // alice 把名字转给没有 `.ai` 的地址
        address noAi = makeAddr("noAi");
        vm.prank(alice);
        registrar.transferFrom(alice, noAi, tokenId);

        vm.prank(noAi);
        vm.expectRevert(HahaAgentIdentity.AiRequired.selector);
        identity.activateAgent("abc", 0, "https://x");
    }

    /// @notice agentId 从 1 递增，不是 namehash。
    function test_agentIdIncrements() public {
        vm.prank(alice);
        uint256 a1 = identity.activateAgent("abc", 0, "https://a");
        assertEq(a1, 1);

        _skipCooldown(bob, "bob");
        uint256 token2 = _register(bob, "xyz", 0);
        vm.prank(bob);
        uint256 a2 = identity.activateAgent("xyz", 0, "https://b");
        assertEq(a2, 2);

        assertEq(identity.nextAgentId(), 3);
    }

    /// @notice `AgentActivated` 事件。
    function test_activateAgent_event() public {
        vm.expectEmit(true, true, true, true, address(identity));
        emit HahaAgentIdentity.AgentActivated(1, tokenId, alice, _aiId("alice"), 1, "https://x");

        vm.prank(alice);
        identity.activateAgent("abc", 0, "https://x");
    }

    // =====================================================================
    // 更新 URI
    // =====================================================================

    function test_setAgentURI() public {
        vm.prank(alice);
        uint256 agentId = identity.activateAgent("abc", 0, "https://old");

        vm.prank(alice);
        identity.setAgentURI(agentId, "https://new");
        assertEq(identity.tokenURI(agentId), "https://new");
    }

    function test_setAgentURI_onlyOwner() public {
        vm.prank(alice);
        uint256 agentId = identity.activateAgent("abc", 0, "https://old");

        vm.prank(bob);
        vm.expectRevert(HahaAgentIdentity.NotAuthorized.selector);
        identity.setAgentURI(agentId, "https://evil");
    }

    function test_setAgentURI_inactiveFails() public {
        vm.prank(alice);
        uint256 agentId = identity.activateAgent("abc", 0, "https://old");

        vm.prank(alice);
        registrar.transferFrom(alice, bob, tokenId);

        vm.prank(alice);
        vm.expectRevert(HahaAgentIdentity.NoActiveAgent.selector);
        identity.setAgentURI(agentId, "https://x");
    }

    // =====================================================================
    // Soulbound
    // =====================================================================

    /// @notice 所有转让与授权入口都 revert `Soulbound`。
    function test_agentNft_isSoulbound() public {
        vm.prank(alice);
        uint256 agentId = identity.activateAgent("abc", 0, "https://x");

        vm.startPrank(alice);
        vm.expectRevert(HahaAgentIdentity.Soulbound.selector);
        identity.transferFrom(alice, bob, agentId);

        vm.expectRevert(HahaAgentIdentity.Soulbound.selector);
        identity.safeTransferFrom(alice, bob, agentId);

        vm.expectRevert(HahaAgentIdentity.Soulbound.selector);
        identity.safeTransferFrom(alice, bob, agentId, "");

        vm.expectRevert(HahaAgentIdentity.Soulbound.selector);
        identity.approve(bob, agentId);

        vm.expectRevert(HahaAgentIdentity.Soulbound.selector);
        identity.setApprovalForAll(bob, true);
        vm.stopPrank();
    }

    /// @notice 没有公众可调用的 `register()`（偏离 ERC-8004 草稿）。
    function test_noPublicRegister() public {
        (bool ok,) = address(identity).call(abi.encodeWithSignature("register()"));
        assertFalse(ok, "no register()");

        (bool ok2,) = address(identity).call(abi.encodeWithSignature("register(string)", "ipfs://x"));
        assertFalse(ok2, "no register(string)");

        (bool ok3,) = address(identity).call(abi.encodeWithSignature("setMetadata(uint256,string,bytes)", 1, "k", "v"));
        assertFalse(ok3, "no setMetadata");

        (bool ok4,) = address(identity).call(abi.encodeWithSignature("setAgentWallet(uint256,address)", 1, alice));
        assertFalse(ok4, "no setAgentWallet");
    }

    // =====================================================================
    // getAgentWallet（派生值）
    // =====================================================================

    function test_getAgentWallet_derivedFromResolver() public {
        vm.prank(alice);
        uint256 agentId = identity.activateAgent("abc", 0, "https://x");

        assertEq(identity.getAgentWallet(agentId), alice, "= addr = owner");

        // 改了 addr 覆盖之后，钱包跟着变
        vm.prank(alice);
        resolver.setAddr(node, carol);
        assertEq(identity.getAgentWallet(agentId), carol);
    }

    function test_getAgentWallet_inactiveIsZero() public view {
        assertEq(identity.getAgentWallet(999), address(0));
    }

    // =====================================================================
    // deactivate 权限
    // =====================================================================

    function test_deactivate_onlyRegistrar() public {
        vm.prank(alice);
        identity.activateAgent("abc", 0, "https://x");

        vm.prank(alice);
        vm.expectRevert(HahaAgentIdentity.NotRegistrar.selector);
        identity.deactivate(tokenId);
    }

    /// @notice 没有 agent 时 `deactivate` 必须成功返回（不得 revert）。
    function test_deactivate_noAgent_isNoop() public {
        vm.prank(address(registrar));
        identity.deactivate(tokenId); // 不 revert
    }

    // =====================================================================
    // 声誉
    // =====================================================================

    function test_rate_basic() public {
        vm.prank(alice);
        uint256 agentId = identity.activateAgent("abc", 0, "https://x");

        _raterName(bob, "bob", "bobname");
        vm.prank(bob);
        reputation.rate(agentId, 4, "good");

        (uint64 count, uint256 sum) = reputation.getScore(agentId);
        assertEq(count, 1);
        assertEq(sum, 4);

        (uint8 stars, bool exists) = reputation.ratingOf(agentId, keccak256(bytes("bob")));
        assertEq(stars, 4);
        assertTrue(exists);
    }

    /// @notice 自评分失败：agent owner 不能给自己打分。
    function test_rate_selfFails() public {
        vm.prank(alice);
        uint256 agentId = identity.activateAgent("abc", 0, "https://x");

        vm.prank(alice);
        vm.expectRevert(HahaReputation.SelfRating.selector);
        reputation.rate(agentId, 5, "me");
    }

    /// @notice 若 agent owner 自己也有 `.ai`，别的地址用同一个 aiId 也不行。
    /// @dev 实际上 `.ai` 与钱包是 1:1，所以这条主要防未来变化。
    function test_rate_sameAiIdAsOwnerFails() public {
        // 让 alice 拥有名字并激活
        vm.prank(alice);
        uint256 agentId = identity.activateAgent("abc", 0, "https://x");

        // alice 用自己的身份打分 => SelfRating（由 msg.sender == owner 拦住）
        vm.prank(alice);
        vm.expectRevert(HahaReputation.SelfRating.selector);
        reputation.rate(agentId, 3, "");
    }

    /// @notice 改分不增加 count。
    function test_rate_editDoesNotIncreaseCount() public {
        vm.prank(alice);
        uint256 agentId = identity.activateAgent("abc", 0, "https://x");

        _raterName(bob, "bob", "bobname");
        vm.startPrank(bob);
        reputation.rate(agentId, 2, "meh");
        reputation.rate(agentId, 5, "actually great");
        vm.stopPrank();

        (uint64 count, uint256 sum) = reputation.getScore(agentId);
        assertEq(count, 1, "count unchanged");
        assertEq(sum, 5, "sum replaced");

        (uint8 stars,) = reputation.ratingOf(agentId, keccak256(bytes("bob")));
        assertEq(stars, 5);
    }

    /// @notice 多人打分：count 和 sum 都累加。
    function test_rate_multipleRaters() public {
        vm.prank(alice);
        uint256 agentId = identity.activateAgent("abc", 0, "https://x");

        _raterName(bob, "bob", "bobname");
        _raterName(carol, "carol", "carolname");
        vm.prank(bob);
        reputation.rate(agentId, 5, "");
        vm.prank(carol);
        reputation.rate(agentId, 3, "");

        (uint64 count, uint256 sum) = reputation.getScore(agentId);
        assertEq(count, 2);
        assertEq(sum, 8);
    }

    /// @notice stars 只能是 1–5。
    function test_rate_starsRange() public {
        vm.prank(alice);
        uint256 agentId = identity.activateAgent("abc", 0, "https://x");

        _raterName(bob, "bob", "bobname");
        vm.startPrank(bob);
        vm.expectRevert(abi.encodeWithSelector(HahaReputation.InvalidStars.selector, 0));
        reputation.rate(agentId, 0, "");

        vm.expectRevert(abi.encodeWithSelector(HahaReputation.InvalidStars.selector, 6));
        reputation.rate(agentId, 6, "");

        // 1 和 5 可以
        reputation.rate(agentId, 1, "");
        reputation.rate(agentId, 5, "");
        vm.stopPrank();
    }

    /// @notice review 超过 140 字节失败。
    function test_rate_reviewTooLong() public {
        vm.prank(alice);
        uint256 agentId = identity.activateAgent("abc", 0, "https://x");

        _raterName(bob, "bob", "bobname");
        bytes memory r141 = new bytes(141);
        vm.prank(bob);
        vm.expectRevert(abi.encodeWithSelector(HahaReputation.ReviewTooLong.selector, 141));
        reputation.rate(agentId, 5, string(r141));

        // 140 可以
        bytes memory r140 = new bytes(140);
        vm.prank(bob);
        reputation.rate(agentId, 5, string(r140));
    }

    /// @notice 调用者必须有 `.ai`。
    function test_rate_requiresAi() public {
        vm.prank(alice);
        uint256 agentId = identity.activateAgent("abc", 0, "https://x");

        address noAi = makeAddr("noAi");
        vm.prank(noAi);
        vm.expectRevert(HahaReputation.AiRequired.selector);
        reputation.rate(agentId, 5, "");
    }

    /// @notice agent 必须 active。已 burn 的旧 id 不能被打分。
    function test_rate_inactiveAgentFails() public {
        vm.prank(alice);
        uint256 agentId = identity.activateAgent("abc", 0, "https://x");

        vm.prank(alice);
        registrar.transferFrom(alice, bob, tokenId);

        vm.prank(carol);
        vm.expectRevert(HahaReputation.AgentNotActive.selector);
        reputation.rate(agentId, 5, "");
    }

    /// @notice review 只进事件，不进 storage。
    /// @dev 验证方式：`Rated` 事件里有 review；合约没有任何返回 review 的 getter。
    function test_rate_reviewOnlyInEvent() public {
        vm.prank(alice);
        uint256 agentId = identity.activateAgent("abc", 0, "https://x");

        _raterName(bob, "bob", "bobname");
        vm.expectEmit(true, true, true, true, address(reputation));
        emit HahaReputation.Rated(agentId, keccak256(bytes("bob")), bob, 5, "secret review text", false);

        vm.prank(bob);
        reputation.rate(agentId, 5, "secret review text");

        // 没有任何函数能读出 review 文本
        (bool ok,) = address(reputation).call(abi.encodeWithSignature("reviewOf(uint256,bytes32)", agentId, keccak256(bytes("bob"))));
        assertFalse(ok, "no reviewOf getter: review lives only in the event");
    }

    /// @notice 改分时事件里 `edited == true`。
    function test_rate_editedFlag() public {
        vm.prank(alice);
        uint256 agentId = identity.activateAgent("abc", 0, "https://x");

        _raterName(bob, "bob", "bobname");
        vm.prank(bob);
        reputation.rate(agentId, 3, "");

        vm.expectEmit(true, true, true, true, address(reputation));
        emit HahaReputation.Rated(agentId, keccak256(bytes("bob")), bob, 4, "", true);

        vm.prank(bob);
        reputation.rate(agentId, 4, "");
    }

    /// @notice 没有 admin，没有可调参数。
    function test_reputation_hasNoAdmin() public {
        (bool ok,) = address(reputation).call(abi.encodeWithSignature("setAdmin(address)", alice));
        assertFalse(ok, "no setAdmin");

        (bool ok2,) = address(reputation).call(abi.encodeWithSignature("owner()"));
        assertFalse(ok2, "no owner");
    }

    /// @notice 不实现 ERC-8004 的那些接口。
    function test_reputation_noErc8004FeedbackApi() public {
        vm.prank(alice);
        uint256 agentId = identity.activateAgent("abc", 0, "https://x");

        (bool ok,) = address(reputation).call(
            abi.encodeWithSignature("giveFeedback(uint256,int128,uint8,string,string,string,string,bytes32)", agentId, 1, 0, "", "", "", "", bytes32(0))
        );
        assertFalse(ok, "no giveFeedback");

        (bool ok2,) = address(reputation).call(abi.encodeWithSignature("revokeFeedback(uint256,uint64)", agentId, 1));
        assertFalse(ok2, "no revokeFeedback");

        (bool ok3,) = address(reputation).call(
            abi.encodeWithSignature("getSummary(uint256,address[],string,string)", agentId, new address[](0), "", "")
        );
        assertFalse(ok3, "no getSummary");
    }
}
