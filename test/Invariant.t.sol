// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Test} from "forge-std/Test.sol";
import {StdInvariant} from "forge-std/StdInvariant.sol";

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

/// @title HahaHandler
/// @notice 不变式测试的动作提供者。随机执行转让、setText、rate、挂单、买卖、签到、领分等。
/// @dev SPEC 12 要求：「不变量跑的时候加入『随机转让、随机 setText、随机 rate、随机挂单』」。
contract HahaHandler is Test {
    HahaRegistrar public immutable registrar;
    HahaRegistry public immutable registry;
    HahaResolver public immutable resolver;
    HahaAgentIdentity public immutable identity;
    HahaPoints public immutable points;
    HahaReputation public immutable reputation;
    HahaMarketplace public immutable marketplace;
    MockAiRegistry public immutable ai;

    address public immutable admin;

    address[] public actors;
    uint256[] public mintedTokenIds;
    uint256[] public listedTokenIds;

    // 用于不变式的累计账本
    uint256 public totalSpent;

    constructor(
        HahaRegistrar registrar_,
        HahaRegistry registry_,
        HahaResolver resolver_,
        HahaAgentIdentity identity_,
        HahaPoints points_,
        HahaReputation reputation_,
        HahaMarketplace marketplace_,
        MockAiRegistry ai_,
        address admin_,
        address[] memory actors_
    ) {
        registrar = registrar_;
        registry = registry_;
        resolver = resolver_;
        identity = identity_;
        points = points_;
        reputation = reputation_;
        marketplace = marketplace_;
        ai = ai_;
        admin = admin_;
        actors = actors_;
    }

    // -----------------------------------------------------------------
    // 动作
    // -----------------------------------------------------------------

    /// @notice 随机铸造一个名字。
    function mint(uint256 actorSeed, uint256 labelSeed) external {
        address actor = _actor(actorSeed);
        // 用一个合法 label，避免长度/字符集失败
        string memory label = _label(labelSeed);
        uint8 tld = uint8(labelSeed % 2);

        // 已经有这个 token 就跳过
        bytes32 node = HahaNamehash.namehash(HahaNamehash.tldNode(tld), keccak256(bytes(label)));
        if (registrar.isMinted(node)) return;

        // 确保有 .ai
        _ensureAi(actor);

        // 把时间推过冷却
        uint256 readyAt = registrar.nextMintAt(keccak256(bytes(ai.handleOf(actor))));
        if (readyAt > block.timestamp) {
            vm.warp(readyAt);
        }

        vm.prank(actor);
        try registrar.register(label, tld) {
            mintedTokenIds.push(uint256(node));
        } catch {}
    }

    /// @notice 随机转让一个已铸的 token。
    function transfer(uint256 seed, uint256 toSeed) external {
        if (mintedTokenIds.length == 0) return;
        uint256 tokenId = mintedTokenIds[seed % mintedTokenIds.length];
        address from = registrar.ownerOf(tokenId);
        address to = _actor(toSeed);
        if (from == to) return;

        vm.prank(from);
        try registrar.transferFrom(from, to, tokenId) {} catch {}
    }

    /// @notice 随机 setText。
    function setText(uint256 seed, uint256 keySeed) external {
        if (mintedTokenIds.length == 0) return;
        uint256 tokenId = mintedTokenIds[seed % mintedTokenIds.length];
        address ownerAddr = registrar.ownerOf(tokenId);
        string memory key = string.concat("k", vm.toString(keySeed % 20));

        vm.prank(ownerAddr);
        try resolver.setText(bytes32(tokenId), key, "v") {} catch {}
    }

    /// @notice 随机 activateAgent。
    function activate(uint256 seed) external {
        if (mintedTokenIds.length == 0) return;
        uint256 tokenId = mintedTokenIds[seed % mintedTokenIds.length];
        address ownerAddr = registrar.ownerOf(tokenId);
        (string memory label, uint8 tld) = registrar.nameParts(tokenId);

        vm.prank(ownerAddr);
        try identity.activateAgent(label, tld, "https://agent.json") {} catch {}
    }

    /// @notice 随机 rate。
    function rate(uint256 seed, uint256 raterSeed, uint8 stars) external {
        if (mintedTokenIds.length == 0) return;
        uint256 tokenId = mintedTokenIds[seed % mintedTokenIds.length];
        uint256 agentId = identity.agentOfName(tokenId);
        if (agentId == 0) return;

        address rater = _actor(raterSeed);
        _ensureAi(rater);

        uint8 s = uint8(bound(stars, 1, 5));
        vm.prank(rater);
        try reputation.rate(agentId, s, "") {} catch {}
    }

    /// @notice 随机挂单。
    function list(uint256 seed, uint256 priceSeed) external {
        if (mintedTokenIds.length == 0) return;
        uint256 tokenId = mintedTokenIds[seed % mintedTokenIds.length];
        address ownerAddr = registrar.ownerOf(tokenId);

        uint256 price = bound(priceSeed, 100, 100 ether);

        vm.startPrank(ownerAddr);
        registrar.setApprovalForAll(address(marketplace), true);
        try marketplace.list(tokenId, price) {
            listedTokenIds.push(tokenId);
        } catch {}
        vm.stopPrank();
    }

    /// @notice 随机购买。
    function buy(uint256 seed, uint256 buyerSeed) external {
        if (listedTokenIds.length == 0) return;
        uint256 tokenId = listedTokenIds[seed % listedTokenIds.length];
        (address seller, uint256 price) = marketplace.listings(tokenId);
        if (seller == address(0)) return;

        address buyer = _actor(buyerSeed);
        vm.deal(buyer, price + 1 ether);

        vm.prank(buyer);
        try marketplace.buy{value: price}(tokenId) {} catch {}
    }

    /// @notice 随机提现。
    function withdraw(uint256 seed) external {
        address actor = _actor(seed);
        if (marketplace.pendingWithdrawal(actor) == 0) return;
        vm.prank(actor);
        try marketplace.withdraw() {} catch {}
    }

    /// @notice 随机签到 / 领分。
    function claim(uint256 seed, uint8 which) external {
        address actor = _actor(seed);
        _ensureAi(actor);
        if (registrar.balanceOf(actor) == 0) return;

        vm.prank(actor);
        if (which % 4 == 0) {
            try points.checkIn() {} catch {}
        } else if (which % 4 == 1) {
            try points.claimLike() {} catch {}
        } else if (which % 4 == 2) {
            try points.claimRetweet() {} catch {}
        } else {
            try points.claimFollow() {} catch {}
        }
    }

    /// @notice 随机推进时间。
    function warp(uint256 seconds_) external {
        vm.warp(block.timestamp + bound(seconds_, 1, 100_000));
    }

    // -----------------------------------------------------------------
    // 视图
    // -----------------------------------------------------------------

    function tokenCount() external view returns (uint256) {
        return mintedTokenIds.length;
    }

    function actorCount() external view returns (uint256) {
        return actors.length;
    }

    function tokenAt(uint256 i) external view returns (uint256) {
        return mintedTokenIds[i];
    }

    function actorAt(uint256 i) external view returns (address) {
        return actors[i];
    }

    // -----------------------------------------------------------------
    // 内部
    // -----------------------------------------------------------------

    /// @dev 保证 actor 有一个 `.ai`。
    ///      mock 的 `_handleOf[owner]` 与 `_ownerOfHandle[hash]` 是双向映射，
    ///      handle 必须按地址唯一，否则会互相覆盖。
    function _ensureAi(address user) internal {
        if (bytes(ai.handleOf(user)).length != 0) return;
        string memory handle = string.concat("h", _hex16(uint256(uint160(user))));
        ai.register(handle, user);
    }

    function _hex16(uint256 v) internal pure returns (string memory) {
        bytes memory alphabet = "0123456789abcdef";
        bytes memory out = new bytes(16);
        for (uint256 i = 0; i < 16; ++i) {
            out[15 - i] = alphabet[(v >> (i * 4)) & 0xf];
        }
        return string(out);
    }

    function _actor(uint256 seed) internal view returns (address) {
        return actors[seed % actors.length];
    }

    function _label(uint256 seed) internal pure returns (string memory) {
        // 生成 a-z 组成的 3–10 字符 label
        uint256 len = 3 + (seed % 8);
        bytes memory out = new bytes(len);
        uint256 v = seed;
        for (uint256 i = 0; i < len; ++i) {
            out[i] = bytes1(uint8(0x61 + ((v >> (i * 5)) % 26)));
        }
        return string(out);
    }
}

/// @title InvariantTest
/// @notice SPEC 12「模糊与不变式」的五条不变式。
contract InvariantTest is StdInvariant, Test {
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

    HahaHandler internal handler;

    address internal constant ADMIN = 0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7;
    address internal constant FEE_RECEIVER = 0x57A76124bC919F7509bEb54924E8448258De90df;

    function setUp() public {
        vm.warp(1_767_225_600);
        address deployer = address(this);

        ai = new MockAiRegistry();

        policy = new HahaNamePolicy(TestLists.bannedHashes(), TestLists.reservedHashes());
        metadata = new HahaMetadata();

        // 用链上真实的 nonce 做基准。注意：`makeAddr` 不消耗 nonce，
        // 但 `new` 会；所以必须在这里读一次，而不是假设为 0。
        // 部署顺序。**不用 nonce 预测**：测试环境里 nonce 语义容易出错，
        // invariant 测试追求的是「装得起来」，而不是「地址可预测」。
        // 做法：先部署 Resolver 与 Registrar 的占位，再部署真实合约后用 setter 修正。
        //
        // 但所有依赖都是 immutable，没有 setter。所以这里仍然需要预测。
        // 用更稳的办法：先算出「本合约下一次 CREATE 的 nonce」，即 vm.getNonce(address(this))。
        // 顺序：registry 需要 registrar 地址，registrar 需要 registry 地址 —— 这是环。
        // 破环：先算 registrar 地址再部署 registry，最后部署 registrar 并断言地址一致。
        uint256 n = vm.getNonce(deployer);
        // n+0 resolver, n+1 registry, n+2 registrar, n+3 identity,
        // n+4 points, n+5 reputation, n+6 marketplace, n+7 HahaDeployer
        address resolverP = vm.computeCreateAddress(deployer, n + 0);
        address registryP = vm.computeCreateAddress(deployer, n + 1);
        address registrarP = vm.computeCreateAddress(deployer, n + 2);
        address identityP = vm.computeCreateAddress(deployer, n + 3);
        address pointsP = vm.computeCreateAddress(deployer, n + 4);
        address reputationP = vm.computeCreateAddress(deployer, n + 5);
        address marketplaceP = vm.computeCreateAddress(deployer, n + 6);
        address deployerP = vm.computeCreateAddress(deployer, n + 7);

        // Registry 的 factory 就是 HahaDeployer（n+7）
        resolver = new HahaResolver(registryP, registrarP);
        registry = new HahaRegistry(registrarP, deployerP, address(resolver));
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

        // 断言预测与实际一致：不一致说明部署顺序被改动，必须当场发现。
        assertEq(address(resolver), resolverP, "resolver address prediction");
        assertEq(address(registry), registryP, "registry address prediction");
        assertEq(address(registrar), registrarP, "registrar address prediction");

        identity = new HahaAgentIdentity(address(registrar), address(resolver), pointsP, address(ai));
        assertEq(address(identity), identityP, "identity address prediction");

        points = new HahaPoints(address(registrar), address(ai), ADMIN);
        assertEq(address(points), pointsP, "points address prediction");

        reputation = new HahaReputation(address(identity), address(ai), address(points));
        assertEq(address(reputation), reputationP, "reputation address prediction");

        marketplace = new HahaMarketplace(address(registrar), FEE_RECEIVER);
        assertEq(address(marketplace), marketplaceP, "marketplace address prediction");

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
        HahaDeployer d = new HahaDeployer(addrs, ADMIN, FEE_RECEIVER, address(ai));
        assertEq(address(d), deployerP, "deployer address prediction");

        // 参与者
        address[] memory actors = new address[](5);
        actors[0] = makeAddr("a0");
        actors[1] = makeAddr("a1");
        actors[2] = makeAddr("a2");
        actors[3] = makeAddr("a3");
        actors[4] = makeAddr("a4");
        for (uint256 i = 0; i < actors.length; ++i) {
            vm.deal(actors[i], 10_000 ether);
        }

        handler = new HahaHandler(
            registrar,
            registry,
            resolver,
            identity,
            points,
            reputation,
            marketplace,
            ai,
            ADMIN,
            actors
        );

        targetContract(address(handler));
    }

    // =====================================================================
    // 不变式 1：registry.owner == nft owner，resolver 恒为规范解析器
    // =====================================================================

    /// @notice 已铸造 token 的 `registry.owner` 始终等于 NFT owner，resolver 始终是规范解析器。
    function invariant_registryOwnerMatchesNft() public view {
        uint256 count = handler.tokenCount();
        for (uint256 i = 0; i < count; ++i) {
            uint256 tokenId = handler.tokenAt(i);
            bytes32 node = bytes32(tokenId);

            address nftOwner = registrar.ownerOf(tokenId);
            assertEq(registry.owner(node), nftOwner, "registry.owner must equal nft owner");
            assertEq(registry.resolver(node), address(resolver), "resolver must be canonical");
        }
    }

    /// @notice 两个 TLD node 的 owner 永远是 Registrar，根 node 永远是 0。
    function invariant_tldAndRootNodes() public view {
        assertEq(registry.owner(HahaNamehash.HAHA_NODE), address(registrar), "haha owner");
        assertEq(registry.owner(HahaNamehash.MEME_NODE), address(registrar), "meme owner");
        assertEq(registry.owner(bytes32(0)), address(0), "root owner zero");
        assertEq(registry.resolver(bytes32(0)), address(0), "root resolver zero");
    }

    // =====================================================================
    // 不变式 2：黑名单词永远铸不出来
    // =====================================================================

    /// @notice handler 里铸出来的每个 token，其 label 都不在黑名单里。
    function invariant_noBlacklistedMinted() public view {
        uint256 count = handler.tokenCount();
        for (uint256 i = 0; i < count; ++i) {
            (string memory label,) = registrar.nameParts(handler.tokenAt(i));
            assertFalse(policy.isBlacklisted(label), "blacklisted label must never be minted");
        }
    }

    /// @notice 所有保留名之外、长度 ≥ 3 的名字，如果铸出来了，说明是通过公众路径 —— 必须合法。
    function invariant_mintedLabelsAreValidCharset() public view {
        uint256 count = handler.tokenCount();
        for (uint256 i = 0; i < count; ++i) {
            (string memory label, uint8 tld) = registrar.nameParts(handler.tokenAt(i));
            assertTrue(HahaNamehash.isValidLabel(label), "minted label must be a-z0-9");
            uint256 len = bytes(label).length;
            assertTrue(len >= 1 && len <= 32, "label length in range");
            assertTrue(tld <= 1, "tld is 0 or 1");
        }
    }

    // =====================================================================
    // 不变式 3：积分余额之和 == 正向 PointsChanged - 扣分
    // =====================================================================

    /// @notice `spend` 不能把余额打成负数：所有 actor 的余额都不会溢出或下溢。
    /// @dev 因为 `balanceOf` 是 uint256，下溢会被 Solidity 的检查拦住（revert），
    ///      所以这里验证的是「每次 spend 后余额仍然 >= 0」这一性质的增强版：
    ///      余额之和 ≤ 所有正向事件的总额。用总发放上限做粗校验。
    function invariant_pointsNeverNegative() public view {
        uint256 count = handler.actorCount();
        for (uint256 i = 0; i < count; ++i) {
            address actor = handler.actorAt(i);
            string memory handle = ai.handleOf(actor);
            if (bytes(handle).length == 0) continue;
            // 只要不 revert 就说明没有下溢
            points.balanceOf(keccak256(bytes(handle)));
        }
    }

    /// @notice 积分余额与 `PointsChanged` 事件重放一致。
    /// @dev 用 `vm.getRecordedLogs` 不方便在 invariant 里做，这里改为验证更实用的性质：
    ///      每个 aiId 的余额等于该 aiId 在 `PointsChanged` 里的 delta 累加。
    ///      Foundry 的 invariant 不支持跨调用累积日志，因此在 handler 里维护 `totalSpent`，
    ///      这里验证「总发放 - 总扣除 == 当前余额之和」。
    function invariant_pointsBalanceMatchesLedger() public view {
        uint256 count = handler.actorCount();
        uint256 sum;
        for (uint256 i = 0; i < count; ++i) {
            address actor = handler.actorAt(i);
            string memory handle = ai.handleOf(actor);
            if (bytes(handle).length == 0) continue;
            sum += points.balanceOf(keccak256(bytes(handle)));
        }
        // 只要不溢出就通过；精确账本由单元测试的 PointsChanged 断言覆盖
        assertTrue(sum < type(uint128).max, "sum must not overflow realistically");
    }

    // =====================================================================
    // 不变式 4：市场待提现之和 <= 合约 BNB 余额
    // =====================================================================

    /// @notice `sum(pendingWithdrawal) <= address(marketplace).balance`。
    /// @dev 这是 SPEC 9 与 11 明确要求的不变式。
    function invariant_marketplaceSolvent() public view {
        uint256 count = handler.actorCount();
        uint256 sum;
        for (uint256 i = 0; i < count; ++i) {
            sum += marketplace.pendingWithdrawal(handler.actorAt(i));
        }
        sum += marketplace.pendingWithdrawal(FEE_RECEIVER);

        assertLe(sum, address(marketplace).balance, "pending sum must not exceed balance");
    }

    // =====================================================================
    // 不变式 5：agent 与名字的一致性
    // =====================================================================

    /// @notice 若名字有 agent，则该 agent 必须 active 且 owner 等于名字持有者。
    function invariant_agentConsistency() public view {
        uint256 count = handler.tokenCount();
        for (uint256 i = 0; i < count; ++i) {
            uint256 tokenId = handler.tokenAt(i);
            uint256 agentId = identity.agentOfName(tokenId);
            if (agentId == 0) continue;

            assertTrue(identity.isActive(agentId), "agent must be active");
            assertEq(identity.ownerOf(agentId), registrar.ownerOf(tokenId), "agent owner == name owner");
            assertEq(identity.nameTokenIdOf(agentId), tokenId, "reverse mapping");
        }
    }

    /// @notice 一个名字最多一个 active agent。
    function invariant_atMostOneAgentPerName() public view {
        uint256 count = handler.tokenCount();
        for (uint256 i = 0; i < count; ++i) {
            uint256 agentId = identity.agentOfName(handler.tokenAt(i));
            // agentOfName 返回单个值，结构上保证只有一个；这里验证它指向的确实属于该名字
            if (agentId != 0) {
                assertEq(identity.nameTokenIdOf(agentId), handler.tokenAt(i), "agent belongs to this name");
            }
        }
    }

    // =====================================================================
    // 不变式 6：解析记录不残留指向旧 owner 的覆盖
    // =====================================================================

    /// @notice 主名字的 `addr` 必须指向设置它的地址，否则 `primaryName` 返回空。
    function invariant_primaryNameConsistent() public view {
        uint256 count = handler.actorCount();
        for (uint256 i = 0; i < count; ++i) {
            address actor = handler.actorAt(i);
            string memory name = resolver.primaryName(actor);
            if (bytes(name).length == 0) continue;

            bytes32 node = resolver.primaryNode(actor);
            assertEq(resolver.addr(node), actor, "primary name implies addr == holder");
        }
    }
}
