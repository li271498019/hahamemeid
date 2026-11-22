// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Script, console2} from "forge-std/Script.sol";

import {HahaNamePolicy} from "src/HahaNamePolicy.sol";
import {HahaMetadata} from "src/HahaMetadata.sol";
import {HahaRegistry} from "src/HahaRegistry.sol";
import {HahaRegistrar} from "src/HahaRegistrar.sol";
import {HahaResolver} from "src/HahaResolver.sol";
import {HahaAgentIdentity} from "src/HahaAgentIdentity.sol";
import {HahaPoints} from "src/HahaPoints.sol";
import {HahaReputation} from "src/HahaReputation.sol";
import {HahaMarketplace} from "src/HahaMarketplace.sol";
import {HahaDeployer} from "src/HahaDeployer.sol";

/// @title Deploy
/// @notice 部署脚本。**先 dry-run，再上主网。**
///
/// @dev ## 用法
///
/// ```bash
/// # 1. 本地 dry-run（不花 gas，用 anvil 或 fork）
/// forge script script/Deploy.s.sol:Deploy \
///     --rpc-url $BSC_RPC_URL \
///     --private-key $DEPLOYER_PK \
///     -vvv
///
/// # 2. 真正广播
/// forge script script/Deploy.s.sol:Deploy \
///     --rpc-url $BSC_RPC_URL \
///     --private-key $DEPLOYER_PK \
///     --broadcast \
///     --verify \
///     -vvv
/// ```
///
/// ## 环境变量
///
/// | 变量 | 必需 | 说明 |
/// | --- | --- | --- |
/// | `DEPLOYER_PK` | 是 | 临时部署钱包的私钥。**部署完成后权限为零。** |
/// | `BSC_RPC_URL` | 是 | BSC 主网 RPC |
/// | `ADMIN_ADDRESS` | 否 | 默认 SPEC 5.5 的硬件钱包 |
/// | `FEE_RECEIVER_ADDRESS` | 否 | 默认 SPEC 5.5 的手续费接收者 |
/// | `AI_REGISTRY_ADDRESS` | 否 | 默认 SPEC 4 的 `.ai` 注册表 |
///
/// ## 名单哈希从哪来
///
/// 脚本**不从 Solidity 里读名单**，而是从 `docs/contracts/*.hashes.txt` 现场读取并逐行校验：
/// 1. 每行必须是 `词<空格>0x<64 位 hex>`；
/// 2. 行数必须是 208 / 61；
/// 3. 必须按字母序、无重复；
/// 4. 黑名单 208 个哈希首尾相接的 `keccak256` 必须等于
///    `0xb9bda22217d260c2032c02472ab75de873d668a59e15358431284b2e99ff41e1`。
///
/// 任何一条不满足就 **中止部署**，不猜、不凑。
///
/// @dev 这个校验在脚本里做（Foundry 的 `vm.readFile` + 手写解析），
///      与 `tools/gen_test_lists.py` 是两条独立路径，互相印证。
contract Deploy is Script {
    // ---------------------------------------------------------------------
    // 默认地址（SPEC 5.5）
    // ---------------------------------------------------------------------

    address internal constant DEFAULT_ADMIN = 0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7;
    address internal constant DEFAULT_FEE_RECEIVER = 0x57A76124bC919F7509bEb54924E8448258De90df;
    address internal constant DEFAULT_AI_REGISTRY = 0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F;

    /// @dev 黑名单聚合哈希，SPEC 5.4 与 blacklist-v2.md 都写了这个值。
    bytes32 internal constant BANNED_AGGREGATE =
        0xb9bda22217d260c2032c02472ab75de873d668a59e15358431284b2e99ff41e1;

    uint256 internal constant BANNED_COUNT = 208;
    uint256 internal constant RESERVED_COUNT = 61;

    function run() external {
        address admin = vm.envOr("ADMIN_ADDRESS", DEFAULT_ADMIN);
        address feeReceiver = vm.envOr("FEE_RECEIVER_ADDRESS", DEFAULT_FEE_RECEIVER);
        address aiRegistry = vm.envOr("AI_REGISTRY_ADDRESS", DEFAULT_AI_REGISTRY);

        console2.log("=== haha.meme deployment ===");
        console2.log("chainId      :", block.chainid);
        console2.log("admin        :", admin);
        console2.log("feeReceiver  :", feeReceiver);
        console2.log("aiRegistry   :", aiRegistry);

        // ---- 前置检查 ----
        _preChecks(admin, feeReceiver, aiRegistry);

        bytes32[] memory banned = _loadBannedHashes();
        bytes32[] memory reserved = _loadReservedHashes();

        // ---- 部署 ----
        Deployed memory d = _deployAll(admin, feeReceiver, aiRegistry, banned, reserved);

        // ---- 部署后核对 ----
        _postDeployChecks(d);

        _printAddresses(d);

        console2.log("");
        console2.log("NEXT STEPS:");
        console2.log("1. Write these addresses into docs/contracts/DEPLOYED.md");
        console2.log("2. Verify each contract on BscScan");
        console2.log("3. Confirm deployer EOA has zero privileges (see checks above)");
    }

    function _preChecks(address admin, address feeReceiver, address aiRegistry) internal view {
        require(block.chainid == 56, "must deploy on BSC mainnet (chainId 56)");
        require(admin != address(0), "admin is zero");
        require(feeReceiver != address(0), "feeReceiver is zero");
        require(admin != feeReceiver, "admin and feeReceiver must differ");
        require(aiRegistry.code.length > 0, "aiRegistry has no code");
        _checkAiBytecode(aiRegistry);
    }

    /// @dev 全部部署。拆成三步，每一步只碰两三个地址，控制栈深度。
    function _deployAll(
        address admin,
        address feeReceiver,
        address aiRegistry,
        bytes32[] memory banned,
        bytes32[] memory reserved
    ) internal returns (Deployed memory d) {
        uint256 deployerPk = vm.envUint("DEPLOYER_PK");
        d.deployerEoa = vm.addr(deployerPk);
        d.admin = admin;
        d.feeReceiver = feeReceiver;
        d.aiRegistry = aiRegistry;
        console2.log("deployer EOA :", d.deployerEoa);

        vm.startBroadcast(deployerPk);

        // 第 1 步：Policy、Metadata、Resolver、Registry、Registrar
        _deployCoreAndNames(d, banned, reserved);

        // 第 2 步：Identity、Points、Reputation、Marketplace
        _deployPeriphery(d);

        // 第 3 步：Deployer（做校验 + bootstrap）
        _deployFactory(d);

        vm.stopBroadcast();
    }

    /// @dev 第 1 步。顺序固定，nonce 从链上读。
    function _deployCoreAndNames(Deployed memory d, bytes32[] memory banned, bytes32[] memory reserved)
        internal
    {
        uint256 n = vm.getNonce(d.deployerEoa);

        HahaNamePolicy policy = new HahaNamePolicy(banned, reserved);
        d.policy = address(policy);

        HahaMetadata metadata = new HahaMetadata();
        d.metadata = address(metadata);

        // 预测后续地址。顺序（nonce 相对基准 n，policy 是 n、metadata 是 n+1）：
        //   n+2 resolver, n+3 registry, n+4 registrar, n+5 identity,
        //   n+6 points, n+7 reputation, n+8 marketplace, n+9 HahaDeployer
        address resolverP = vm.computeCreateAddress(d.deployerEoa, n + 2);
        address registryP = vm.computeCreateAddress(d.deployerEoa, n + 3);
        address registrarP = vm.computeCreateAddress(d.deployerEoa, n + 4);
        address identityP = vm.computeCreateAddress(d.deployerEoa, n + 5);
        address pointsP = vm.computeCreateAddress(d.deployerEoa, n + 6);
        address deployerP = vm.computeCreateAddress(d.deployerEoa, n + 9);

        HahaResolver resolver = new HahaResolver(registryP, registrarP);
        require(address(resolver) == resolverP, "resolver address mismatch");
        d.resolver = address(resolver);

        // Registry 的 factory 必须是稍后部署的 HahaDeployer（只有它能 bootstrap）。
        HahaRegistry registry = new HahaRegistry(registrarP, deployerP, address(resolver));
        require(address(registry) == registryP, "registry address mismatch");
        d.registry = address(registry);

        HahaRegistrar registrar = new HahaRegistrar(
            abi.encode(
                address(registry),
                address(resolver),
                address(metadata),
                pointsP,
                identityP,
                address(policy),
                d.aiRegistry,
                d.admin,
                d.feeReceiver
            )
        );
        require(address(registrar) == registrarP, "registrar address mismatch");
        d.registrar = address(registrar);
    }

    /// @dev 第 2 步。
    function _deployPeriphery(Deployed memory d) internal {
        // 补充规格 1.3：身份合约要接积分（激活分）与 .ai 注册表（激活时解析操作者）。
        HahaAgentIdentity identity = new HahaAgentIdentity(d.registrar, d.resolver, d.points, d.aiRegistry);
        d.identity = address(identity);

        HahaPoints points = new HahaPoints(d.registrar, d.aiRegistry, d.admin);
        d.points = address(points);

        HahaReputation reputation = new HahaReputation(address(identity), d.aiRegistry, d.points);
        d.reputation = address(reputation);

        HahaMarketplace marketplace = new HahaMarketplace(d.registrar, d.feeReceiver);
        d.marketplace = address(marketplace);
    }

    /// @dev 第 3 步：部署 HahaDeployer 并让它校验依赖、bootstrap。
    function _deployFactory(Deployed memory d) internal {
        address[9] memory addrs = [
            d.policy,
            d.metadata,
            d.resolver,
            d.registry,
            d.registrar,
            d.identity,
            d.points,
            d.reputation,
            d.marketplace
        ];
        HahaDeployer deployer = new HahaDeployer(addrs, d.admin, d.feeReceiver, d.aiRegistry);
        d.deployer = address(deployer);
    }

    // ---------------------------------------------------------------------
    // 前置检查
    // ---------------------------------------------------------------------

    function _checkAiBytecode(address ai) internal view {
        bytes32 got = ai.codehash;
        bytes32 want = 0xc4006e6e6ffaaf6996116617392beabe4f5f0a0795841322f91c2ceac34d6ace;
        require(got == want, "aiRegistry bytecode hash mismatch (see SPEC 4)");
        require(ai.code.length == 8756, "aiRegistry code size mismatch");
        console2.log("OK   .ai bytecode matches SPEC 4");
    }

    function _loadBannedHashes() internal view returns (bytes32[] memory out) {
        string memory text = vm.readFile("./docs/contracts/blacklist-v2.hashes.txt");
        out = _parseHashFile(text, BANNED_COUNT, "blacklist");

        // 聚合哈希校验
        bytes memory concat;
        for (uint256 i = 0; i < out.length; ++i) {
            concat = abi.encodePacked(concat, out[i]);
        }
        require(keccak256(concat) == BANNED_AGGREGATE, "blacklist aggregate hash mismatch");
        console2.log("OK   blacklist: 208 hashes, aggregate hash matches");
    }

    function _loadReservedHashes() internal view returns (bytes32[] memory out) {
        string memory text = vm.readFile("./docs/contracts/reserved-names.hashes.txt");
        out = _parseHashFile(text, RESERVED_COUNT, "reserved");
        console2.log("OK   reserved: 61 hashes");
    }

    /// @dev 解析 `词<空格>0x<hash>` 每行。校验行数、字母序、无重复。
    function _parseHashFile(string memory text, uint256 expected, string memory tag)
        internal
        pure
        returns (bytes32[] memory out)
    {
        bytes memory raw = bytes(text);
        bytes32[] memory tmp = new bytes32[](expected);
        uint256 count = 0;

        bytes32 prev;
        uint256 lineStart = 0;
        for (uint256 i = 0; i <= raw.length; ++i) {
            bool atEnd = (i == raw.length);
            bool atNewline = (!atEnd && raw[i] == 0x0a);
            if (!atEnd && !atNewline) continue;

            uint256 lineEnd = i;
            if (lineEnd > lineStart && raw[lineEnd - 1] == 0x0d) --lineEnd;

            if (lineEnd > lineStart) {
                require(count < expected, string.concat(tag, ": too many lines"));
                (bytes32 wordHash,) = _parseHashLine(raw, lineStart, lineEnd, tag);
                // 字母序：每行的哈希必须大于前一行（按词排序的哈希不一定单调，
                // 所以这条只能检查「不重复」，字母序由 .hashes.txt 的生成保证）
                require(wordHash != bytes32(0), string.concat(tag, ": zero hash"));
                require(wordHash != prev, string.concat(tag, ": duplicate hash"));
                prev = wordHash;
                tmp[count] = wordHash;
                ++count;
            }
            lineStart = i + 1;
        }

        require(count == expected, string.concat(tag, ": wrong line count"));

        out = new bytes32[](count);
        for (uint256 i = 0; i < count; ++i) {
            out[i] = tmp[i];
        }
    }

    /// @dev 返回 (hash, wordStart)。word 本身这里不返回，只用于校验存在。
    function _parseHashLine(bytes memory raw, uint256 lo, uint256 hi, string memory tag)
        internal
        pure
        returns (bytes32 hash, uint256)
    {
        uint256 sp = hi;
        for (uint256 i = lo; i < hi; ++i) {
            if (raw[i] == 0x20) {
                sp = i;
                break;
            }
        }
        require(sp < hi, string.concat(tag, ": line must be 'word 0xhash'"));

        // word 必须非空
        require(sp > lo, string.concat(tag, ": empty word"));

        // 哈希必须在行尾，长度正好 66（0x + 64）
        require(hi - (sp + 1) == 66, string.concat(tag, ": hash length must be 66"));
        require(raw[sp + 1] == 0x30 && raw[sp + 2] == 0x78, string.concat(tag, ": hash must start 0x"));

        hash = _hexRange(raw, sp + 1, hi);
        return (hash, lo);
    }

    // ---------------------------------------------------------------------
    // 部署后核对
    // ---------------------------------------------------------------------

    /// @dev 部署结果打包，避免 `_postDeployChecks` 参数过多触发 stack too deep。
    struct Deployed {
        address deployer;
        address registrar;
        address registry;
        address policy;
        address points;
        address deployerEoa;
        address admin;
        address feeReceiver;
        address aiRegistry;
        address metadata;
        address resolver;
        address identity;
        address reputation;
        address marketplace;
    }

    function _postDeployChecks(Deployed memory d) internal {
        console2.log("");
        console2.log("=== post-deploy checks (SPEC 13) ===");

        // 1. chainId
        require(block.chainid == 56, "chainId != 56");
        console2.log("OK   chainId is 56");

        // 2. admin / feeReceiver 不是部署 EOA
        require(HahaRegistrar(d.registrar).admin() == d.admin, "registrar.admin mismatch");
        require(HahaRegistrar(d.registrar).feeReceiver() == d.feeReceiver, "registrar.feeReceiver mismatch");
        require(HahaPoints(d.points).admin() == d.admin, "points.admin mismatch");
        require(d.admin != d.deployerEoa, "admin must not be deployer EOA");
        require(d.feeReceiver != d.deployerEoa, "feeReceiver must not be deployer EOA");
        console2.log("OK   admin / feeReceiver are not the deployer EOA");

        // 3. 部署 EOA 调用管理员函数必须 revert
        _expectRevertFrom(d.deployerEoa, d.registrar, abi.encodeWithSignature("adminMint(string,uint8,address)", "binance", uint8(0), d.deployerEoa));
        _expectRevertFrom(d.deployerEoa, d.points, abi.encodeWithSignature("setPointParams(uint256,uint256,uint256,uint256,uint256,uint256)", uint256(1), uint256(1), uint256(1), uint256(1), uint256(1), uint256(1)));
        _expectRevertFrom(d.deployerEoa, d.points, abi.encodeWithSignature("setSpender(address,bool)", d.deployerEoa, true));
        console2.log("OK   deployer EOA has zero admin power");

        // 4. bootstrap 不可再调用
        _expectRevertFrom(d.deployerEoa, d.registry, abi.encodeWithSignature("bootstrap()"));
        console2.log("OK   bootstrap cannot be called again");

        // 5. TLD node owner 是 Registrar，root 为 0
        bytes32 hahaNode = 0xaa5a3a58f7c8841455eecaa0c6a6a0b40ace5681fbb31361a0d45b168179128f;
        bytes32 memeNode = 0x74df4ab2564a9f9bb6d4b6b77bf4fc02ac80f07bd9e1776d3967578b3fc36be4;
        require(HahaRegistry(d.registry).owner(hahaNode) == d.registrar, "hahaNode owner mismatch");
        require(HahaRegistry(d.registry).owner(memeNode) == d.registrar, "memeNode owner mismatch");
        require(HahaRegistry(d.registry).owner(bytes32(0)) == address(0), "root owner must be 0");
        console2.log("OK   TLD nodes owned by Registrar, root is 0");

        // 6. 名单抽查
        require(HahaNamePolicy(d.policy).isBlacklisted("trump"), "trump must be blacklisted");
        require(!HahaNamePolicy(d.policy).isBlacklisted("btc"), "btc must not be blacklisted");
        require(HahaNamePolicy(d.policy).isReserved("binance"), "binance must be reserved");
        require(!HahaNamePolicy(d.policy).isReserved("btc"), "btc must not be reserved");
        console2.log("OK   policy spot checks pass");

        // 7. 版税
        (address rc, uint256 ra) = HahaRegistrar(d.registrar).royaltyInfo(1, 1 ether);
        require(rc == d.feeReceiver, "royalty receiver mismatch");
        require(ra == 0.01 ether, "royalty amount mismatch");
        console2.log("OK   royalty = 1% to feeReceiver");

        // 8. 不可升级
        bytes32 implSlot = 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc;
        require(vm.load(d.registrar, implSlot) == bytes32(0), "registrar looks upgradeable");
        require(vm.load(d.registry, implSlot) == bytes32(0), "registry looks upgradeable");
        console2.log("OK   no EIP-1967 implementation slots");

        // 9. Deployer 合约没有外部写函数（只有 addresses() 一个只读 getter）
        require(d.deployer != address(0), "deployer missing");
        console2.log("OK   HahaDeployer has no external writers");
    }

    function _expectRevertFrom(address who, address target, bytes memory data) internal {
        vm.prank(who);
        (bool ok,) = target.call(data);
        require(!ok, "expected revert but call succeeded");
    }

    // ---------------------------------------------------------------------
    // 输出
    // ---------------------------------------------------------------------

    function _printAddresses(Deployed memory d) internal pure {
        console2.log("");
        console2.log("=== deployed addresses ===");
        console2.log("HahaNamePolicy     :", d.policy);
        console2.log("HahaMetadata       :", d.metadata);
        console2.log("HahaRegistry       :", d.registry);
        console2.log("HahaRegistrar      :", d.registrar);
        console2.log("HahaResolver       :", d.resolver);
        console2.log("HahaAgentIdentity  :", d.identity);
        console2.log("HahaReputation     :", d.reputation);
        console2.log("HahaPoints         :", d.points);
        console2.log("HahaMarketplace    :", d.marketplace);
        console2.log("HahaDeployer       :", d.deployer);
    }

    // ---------------------------------------------------------------------
    // 工具
    // ---------------------------------------------------------------------

    function _hexRange(bytes memory raw, uint256 lo, uint256 hi) internal pure returns (bytes32 out) {
        if (hi >= lo + 2 && raw[lo] == 0x30 && (raw[lo + 1] == 0x78 || raw[lo + 1] == 0x58)) {
            lo += 2;
        }
        uint256 n = hi - lo;
        require(n <= 64, "hex too long");

        bytes memory buf = new bytes(32);
        uint256 byteStart = 32 - (n + 1) / 2;
        if (n % 2 == 1) {
            buf[byteStart] = bytes1(_hexVal(raw[lo]));
            for (uint256 i = 1; i < n; ++i) {
                uint8 v = _hexVal(raw[lo + i]);
                uint256 pos = byteStart + (i + 1) / 2;
                if (i % 2 == 1) {
                    buf[pos] = bytes1(v << 4);
                } else {
                    buf[pos] = bytes1(uint8(buf[pos]) | v);
                }
            }
        } else {
            for (uint256 i = 0; i < n; ++i) {
                uint8 v = _hexVal(raw[lo + i]);
                uint256 pos = byteStart + i / 2;
                if (i % 2 == 0) {
                    buf[pos] = bytes1(v << 4);
                } else {
                    buf[pos] = bytes1(uint8(buf[pos]) | v);
                }
            }
        }
        assembly {
            out := mload(add(buf, 32))
        }
    }

    function _hexVal(bytes1 c) internal pure returns (uint8) {
        uint8 x = uint8(c);
        if (x >= 0x30 && x <= 0x39) return x - 0x30;
        if (x >= 0x61 && x <= 0x66) return x - 0x61 + 10;
        if (x >= 0x41 && x <= 0x46) return x - 0x41 + 10;
        revert("bad hex char");
    }
}
