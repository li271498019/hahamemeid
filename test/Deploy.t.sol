// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {HahaTestBase} from "./HahaTestBase.sol";
import {HahaNamehash} from "src/libraries/HahaNamehash.sol";
import {HahaConstants} from "src/libraries/HahaConstants.sol";

/// @notice 部署与常量自检：确认整套合约装得起来、地址链自洽、文档里的向量在链上成立。
contract DeployTest is HahaTestBase {
    // ---------------------------------------------------------------------
    // SPEC 5.2：namehash 测试向量
    // ---------------------------------------------------------------------

    function test_namehashVectors() public pure {
        assertEq(
            HahaNamehash.HAHA_NODE,
            0xaa5a3a58f7c8841455eecaa0c6a6a0b40ace5681fbb31361a0d45b168179128f,
            "hahaNode"
        );
        assertEq(
            HahaNamehash.MEME_NODE,
            0x74df4ab2564a9f9bb6d4b6b77bf4fc02ac80f07bd9e1776d3967578b3fc36be4,
            "memeNode"
        );
        assertEq(
            keccak256(bytes("abc")),
            0x4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45,
            "keccak(abc)"
        );
        // 两个 TLD node 必须不同，否则 abc.haha 与 abc.meme 会撞号。
        assertTrue(HahaNamehash.HAHA_NODE != HahaNamehash.MEME_NODE, "tld nodes must differ");
    }

    /// @notice `abc.haha` 与 `abc.meme` 的 node 必须不同，且等于 5.2 的向量。
    function test_nodeVectors_abcHahaAndAbcMeme() public view {
        bytes32 hahaNode = _node("abc", 0);
        bytes32 memeNode = _node("abc", 1);

        assertEq(hahaNode, 0xc57a55f292f4033cc1612bb06ae0f4e6bf0fc0c57815982253ae7fdd925b7052, "abc.haha");
        assertEq(memeNode, 0x7d6c57ebcb95fc73d48b8e90c54fb409bd65ff84d24423b6a5b13bc744c17d0a, "abc.meme");
        assertTrue(hahaNode != memeNode, "abc.haha != abc.meme");
    }

    /// @notice tokenId 用含 TLD 的 namehash，不是 SPACE ID 那种纯 labelhash。
    function test_tokenIdIsNode() public view {
        assertEq(uint256(_node("abc", 0)), uint256(_node("abc", 0)), "deterministic");
        // 纯 labelhash 会让两个 TLD 撞号。
        bytes32 labelOnly = keccak256(bytes("abc"));
        assertTrue(uint256(_node("abc", 0)) != uint256(labelOnly), "must not be labelhash");
        assertTrue(uint256(_node("abc", 0)) != uint256(_node("abc", 1)), "tld differs");
    }

    // ---------------------------------------------------------------------
    // SPEC 13：部署后核对
    // ---------------------------------------------------------------------

    function test_deployerAddressesWired() public view {
        assertEq(registrar.registry(), address(registry), "registrar.registry");
        assertEq(registrar.resolver(), address(resolver), "registrar.resolver");
        assertEq(registrar.metadata(), address(metadata), "registrar.metadata");
        assertEq(registrar.points(), address(points), "registrar.points");
        assertEq(registrar.identity(), address(identity), "registrar.identity");
        assertEq(registrar.policy(), address(policy), "registrar.policy");
        assertEq(registrar.aiRegistry(), address(ai), "registrar.aiRegistry");
        assertEq(registrar.admin(), ADMIN, "registrar.admin");
        assertEq(registrar.feeReceiver(), FEE_RECEIVER, "registrar.feeReceiver");

        assertEq(registry.registrar(), address(registrar), "registry.registrar");
        assertEq(registry.canonicalResolver(), address(resolver), "registry.canonicalResolver");
        assertEq(registry.factory(), address(deployer), "registry.factory");

        assertEq(resolver.registry(), address(registry), "resolver.registry");
        assertEq(resolver.registrar(), address(registrar), "resolver.registrar");

        assertEq(identity.registrar(), address(registrar), "identity.registrar");
        assertEq(identity.resolver(), address(resolver), "identity.resolver");

        assertEq(points.registrar(), address(registrar), "points.registrar");
        assertEq(points.aiRegistry(), address(ai), "points.aiRegistry");
        assertEq(points.admin(), ADMIN, "points.admin");

        assertEq(reputation.identity(), address(identity), "reputation.identity");
        assertEq(reputation.aiRegistry(), address(ai), "reputation.aiRegistry");

        assertEq(marketplace.registrar(), address(registrar), "marketplace.registrar");
        assertEq(marketplace.feeReceiver(), FEE_RECEIVER, "marketplace.feeReceiver");
    }

    /// @notice bootstrap 之后两个 TLD node 的 owner 是 Registrar，根 node 全零。
    function test_bootstrapState() public view {
        assertEq(registry.owner(HahaNamehash.HAHA_NODE), address(registrar), "haha owner");
        assertEq(registry.owner(HahaNamehash.MEME_NODE), address(registrar), "meme owner");
        assertEq(registry.resolver(HahaNamehash.HAHA_NODE), address(0), "haha resolver is 0");
        assertEq(registry.resolver(HahaNamehash.MEME_NODE), address(0), "meme resolver is 0");

        assertEq(registry.owner(bytes32(0)), address(0), "root owner");
        assertEq(registry.resolver(bytes32(0)), address(0), "root resolver");
        assertTrue(registry.bootstrapped(), "bootstrapped");
    }

    /// @notice bootstrap 第二次必须 revert。
    function test_bootstrapSecondTimeReverts() public {
        vm.prank(address(deployer));
        vm.expectRevert(); // 调用者已 bootstrap 过
        registry.bootstrap();

        // 换成 factory 自己再调也要失败。
        vm.startPrank(address(deployer));
        vm.expectRevert();
        registry.bootstrap();
        vm.stopPrank();
    }

    // ---------------------------------------------------------------------
    // 常量
    // ---------------------------------------------------------------------

    function test_constants() public pure {
        assertEq(HahaConstants.MIN_PUBLIC_LENGTH, 3, "min public");
        assertEq(HahaConstants.MAX_LABEL_LENGTH, 32, "max label");
        assertEq(HahaConstants.COOLDOWN, 3600, "cooldown");
        assertEq(HahaConstants.FEE_BPS, 100, "fee bps");
        assertEq(HahaConstants.MINT_REWARDS_PER_DAY, 3, "mint rewards per day");
        assertEq(HahaConstants.MAX_POINT_PARAM, 999_999_999, "point cap");
    }

    function test_collectionNameAndSymbol() public view {
        assertEq(registrar.name(), "haha id", "collection name");
        assertEq(registrar.symbol(), "HAHAID", "collection symbol");
        assertEq(identity.name(), "haha.meme Agent", "identity name");
        assertEq(identity.symbol(), "HAHAAGENT", "identity symbol");
    }

    /// @notice Policy 的名单数量。
    function test_policyCounts() public view {
        assertEq(policy.bannedCount(), 208, "banned");
        assertEq(policy.reservedCount(), 61, "reserved");
    }
}
