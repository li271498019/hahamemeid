// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Test} from "forge-std/Test.sol";

import {HahaNamePolicy} from "src/HahaNamePolicy.sol";
import {HahaMetadata} from "src/HahaMetadata.sol";
import {HahaResolver} from "src/HahaResolver.sol";
import {HahaRegistry} from "src/HahaRegistry.sol";
import {HahaRegistrar} from "src/HahaRegistrar.sol";
import {HahaAgentIdentity} from "src/HahaAgentIdentity.sol";
import {HahaPoints} from "src/HahaPoints.sol";
import {HahaReputation} from "src/HahaReputation.sol";
import {HahaMarketplace} from "src/HahaMarketplace.sol";
import {HahaDeployer} from "src/HahaDeployer.sol";

import {HahaNamehash} from "src/libraries/HahaNamehash.sol";
import {MockAiRegistry} from "./mocks/MockAiRegistry.sol";
import {TestLists} from "./TestLists.sol";

/// @title HahaTestBase
/// @notice 全部测试的公共基类：部署一整套合约、准备 `.ai` 身份、提供常用工具函数。
///
/// @dev 部署顺序必须与 `script/Deploy.s.sol` 完全一致，否则依赖环解不开。
///      见 `src/HahaDeployer.sol` 顶部注释里的依赖表。
abstract contract HahaTestBase is Test {
    // ---------------------------------------------------------------------
    // 地址常量（与 SPEC 5.5 一致）
    // ---------------------------------------------------------------------

    /// @notice 管理员。硬件钱包，单签，部署后不可更换。
    address internal constant ADMIN = 0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7;

    /// @notice 手续费与版税接收者。
    address internal constant FEE_RECEIVER = 0x57A76124bC919F7509bEb54924E8448258De90df;

    /// @notice 币安 `.ai` 注册表主网地址。单测里换成 mock，但常量留着给 fork 测试用。
    address internal constant AI_REGISTRY_MAINNET = 0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F;

    // ---------------------------------------------------------------------
    // 合约
    // ---------------------------------------------------------------------

    MockAiRegistry internal ai;
    HahaNamePolicy internal policy;
    HahaMetadata internal metadata;
    HahaResolver internal resolver;
    HahaRegistry internal registry;
    HahaRegistrar internal registrar;
    HahaAgentIdentity internal identity;
    HahaPoints internal points;
    HahaReputation internal reputation;
    HahaMarketplace internal marketplace;
    HahaDeployer internal deployer;

    // ---------------------------------------------------------------------
    // 常用地址
    // ---------------------------------------------------------------------

    address internal alice = makeAddr("alice");
    address internal bob = makeAddr("bob");
    address internal carol = makeAddr("carol");
    address internal dave = makeAddr("dave");
    address internal deployerEOA = makeAddr("deployerEOA");

    // ---------------------------------------------------------------------
    // setUp
    // ---------------------------------------------------------------------

    function setUp() public virtual {
        // 把时间设到一个真实的 UTC 日界之后，避免测试从 `timestamp = 1`（day 0）开始。
        // 从 day 0 开始会让「加 86400 是否跨日」这类断言变得难以推理，
        // 也会让 day 0 这个合法日序号的边界问题混进无关测试。
        // 用 2026-01-01 00:00:00 UTC（不是整点也行，但要离日界足够远）。
        vm.warp(1_767_225_600); // 2026-01-01 00:00:00 UTC，正好是日界

        vm.startPrank(deployerEOA);

        // 用 nonce 预测解开依赖环。**基准 nonce 从链上读**，不靠假设：
        // forge 的测试账户初始 nonce 会随环境变化，硬编码会算错。
        uint256 n = vm.getNonce(deployerEOA);

        ai = new MockAiRegistry();                                        // n+0
        policy = new HahaNamePolicy(TestLists.bannedHashes(), TestLists.reservedHashes()); // n+1
        metadata = new HahaMetadata();                                    // n+2

        address resolverP = vm.computeCreateAddress(deployerEOA, n + 3);
        address registryP = vm.computeCreateAddress(deployerEOA, n + 4);
        address registrarP = vm.computeCreateAddress(deployerEOA, n + 5);
        address identityP = vm.computeCreateAddress(deployerEOA, n + 6);
        address pointsP = vm.computeCreateAddress(deployerEOA, n + 7);
        address reputationP = vm.computeCreateAddress(deployerEOA, n + 8);
        address marketplaceP = vm.computeCreateAddress(deployerEOA, n + 9);
        address deployerP = vm.computeCreateAddress(deployerEOA, n + 10);

        // Resolver 需要 registry + registrar（都还没部署，只保存地址）
        resolver = new HahaResolver(registryP, registrarP);
        assert(address(resolver) == resolverP);

        // Registry 需要 registrar + factory + resolver。factory 必须是 bootstrap 的调用者，
        // 也就是稍后才部署的 HahaDeployer。
        registry = new HahaRegistry(registrarP, deployerP, address(resolver));
        assert(address(registry) == registryP);

        // Registrar（constructor 收 bytes，避开 9 参数 stack too deep）
        registrar = new HahaRegistrar(
            abi.encode(
                address(registry),
                address(resolver),
                address(metadata),
                pointsP,
                identityP,
                address(policy),
                address(ai),
                ADMIN,
                FEE_RECEIVER
            )
        );
        assert(address(registrar) == registrarP);

        identity = new HahaAgentIdentity(address(registrar), address(resolver), pointsP, address(ai));
        assert(address(identity) == identityP);

        points = new HahaPoints(address(registrar), address(ai), ADMIN);
        assert(address(points) == pointsP);

        reputation = new HahaReputation(address(identity), address(ai), address(points));
        assert(address(reputation) == reputationP);

        marketplace = new HahaMarketplace(address(registrar), FEE_RECEIVER);
        assert(address(marketplace) == marketplaceP);

        // Deployer：校验全部依赖并 bootstrap
        address[9] memory addrs = [
            address(policy),
            address(metadata),
            address(resolver),
            address(registry),
            address(registrar),
            address(identity),
            address(points),
            address(reputation),
            address(marketplace)
        ];
        deployer = new HahaDeployer(addrs, ADMIN, FEE_RECEIVER, address(ai));
        assert(address(deployer) == deployerP);

        vm.stopPrank();

        // 默认给几个测试用户配上 `.ai`
        _giveAi(alice, "alice");
        _giveAi(bob, "bob");
        _giveAi(carol, "carol");
        _giveAi(dave, "dave");

        // 给测试用户一些 BNB，供市场测试使用。
        // `makeAddr` 创建的地址默认余额为 0，直接 `buy{value:}` 会 OutOfFunds。
        vm.deal(alice, 1000 ether);
        vm.deal(bob, 1000 ether);
        vm.deal(carol, 1000 ether);
        vm.deal(dave, 1000 ether);
    }

    // ---------------------------------------------------------------------
    // 工具
    // ---------------------------------------------------------------------

    /// @dev 给地址配一个 `.ai` handle。
    function _giveAi(address user, string memory handle) internal {
        ai.register(handle, user);
    }

    /// @dev 让 `user` 公众铸造一个名字。
    function _register(address user, string memory label, uint8 tld) internal returns (uint256 tokenId) {
        vm.prank(user);
        registrar.register(label, tld);
        tokenId = uint256(_node(label, tld));
    }

    /// @dev 计算 node。
    function _node(string memory label, uint8 tld) internal pure returns (bytes32) {
        return HahaNamehash.namehash(HahaNamehash.tldNode(tld), keccak256(bytes(label)));
    }

    /// @dev 计算 aiId。
    function _aiId(string memory handle) internal pure returns (bytes32) {
        return keccak256(bytes(handle));
    }

    /// @dev 把时间推到该 aiId 的冷却结束后。
    /// @dev **只前进，不倒退**。如果当前时间已经过了冷却结束点，什么都不做。
    ///      不加这个保护会出问题：测试里先 `warp` 到未来某天，再调本函数，
    ///      会把时间退回到 `lastMintAt + 3600`，从而离开刚 warp 到的那一天。
    function _skipCooldown(address user, string memory handle) internal {
        user; // 未使用，保留参数以便将来按用户扩展
        uint256 readyAt = registrar.nextMintAt(_aiId(handle));
        if (readyAt > block.timestamp) {
            vm.warp(readyAt);
        }
    }
}
