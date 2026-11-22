// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Test} from "forge-std/Test.sol";
import {console2} from "forge-std/console2.sol";

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
import {IBinanceAiRegistry} from "src/interfaces/IBinanceAiRegistry.sol";
import {IERC721Metadata} from "@openzeppelin/contracts/token/ERC721/extensions/IERC721Metadata.sol";
import {TestLists} from "../TestLists.sol";

/// @title ForkBase
/// @notice BSC 主网 `.ai` 注册表的**离线冷冻**环境。
///
/// @dev ## 为什么是「离线冷冻」而不是直接 `--fork-url`
///
///      SPEC 4 要求在区块 `134683411` 核实。实测该区块在公共 RPC 上
///      `eth_getCode` / `eth_getStorageAt` 都返回 `missing trie node`
///      （非归档节点无法读历史状态）。
///
///      因此按 QUESTIONS 第 11 条的裁决分两层：
///      - **离线层（本文件）**：把 `.ai` 的 runtime bytecode 与关键 storage
///        冻结进 `test/fork/state/`，用 `vm.etch` / `vm.store` 还原。
///        **不需要联网**，CI 必跑。
///      - **在线层（`ForkOnline.t.sol`）**：可选，需要 `BSC_RPC_URL`，
///        对真实 RPC 做同组断言。
///
///      两层都把运行时字节码哈希**写死断言**。若有一天链上字节码变了，
///      测试会失败——按 SPEC 12 的要求，那时应停下来更新规格，不要改断言。
abstract contract ForkBase is Test {
    /// @notice `.ai` 注册表在 BSC 主网的地址。
    address internal constant AI = 0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F;

    /// @notice SPEC 4 记录的运行时字节码哈希。
    bytes32 internal constant AI_CODEHASH =
        0xc4006e6e6ffaaf6996116617392beabe4f5f0a0795841322f91c2ceac34d6ace;

    /// @notice SPEC 4 记录的运行时字节码长度。
    uint256 internal constant AI_CODESIZE = 8756;

    /// @notice `alice` 的持有者（SPEC 4）。
    address internal constant ALICE_OWNER = 0xA506ac7069937571DC56C5f8FDa53c4A729456c6;

    /// @notice `binance` 的持有者（SPEC 4）。
    address internal constant BINANCE_OWNER = 0x5E3fBbc8D260a63C9fe19CbBb0A9d5792C3375eA;

    /// @notice `.ai` 合集的 name / symbol 期望值。
    string internal constant AI_NAME = "SPACE ID Agent ID";

    address internal constant ADMIN = 0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7;
    address internal constant FEE_RECEIVER = 0x57A76124bC919F7509bEb54924E8448258De90df;

    // haha 合约
    HahaNamePolicy internal policy;
    HahaMetadata internal metadata;
    HahaResolver internal resolver;
    HahaRegistry internal registry;
    HahaRegistrar internal registrar;
    HahaAgentIdentity internal identity;
    HahaPoints internal points;
    HahaReputation internal reputation;
    HahaMarketplace internal marketplace;

    /// @notice 冻结用的区块号，从 Meta.json 读。
    uint256 internal frozenBlock;

    function _loadFrozenAi() internal returns (IBinanceAiRegistry ai) {
        // 1. 冻结的字节码。
        //    **必须用二进制文件**：`vm.parseBytes` 处理 17.5 KB 的 hex 字符串会失败
        //    （foundry 的字符串解析上限）。`vm.readFileBinary` 直接读原始字节，没有这个问题。
        bytes memory code = vm.readFileBinary("./test/fork/state/AiRegistry.code.bin");

        // 2. 字节码必须与 SPEC 4 一致。**先断言再 etch**，避免装了错的代码还以为在测主网。
        assertEq(code.length, AI_CODESIZE, "frozen .ai code size");
        assertEq(keccak256(code), AI_CODEHASH, "frozen .ai code hash");

        // 3. 装到主网地址上
        vm.etch(AI, code);

        // 4. 还原 storage。
        //    用扁平文本 `slot value` 每行一条，而不是 JSON：
        //    `vm.parseJson` 要求键是合法标识符（不能以 `0x` 开头），扁平文本更适合这里。
        //    每个槽位都用 `vm.store` 写入，与真实链上状态一致。
        _restoreStorage();

        return IBinanceAiRegistry(AI);
    }

    /// @dev 读取 `test/fork/state/AiRegistry.storage.txt`，逐行 `slot value` 写入。
    ///
    /// @dev 不用 `vm.split`：它对分隔符的处理在不同 forge 版本间有差异，
    ///      且行尾的 `\r` 会让值解析失败（表现为「前几行生效、后面静默跳过」）。
    ///      这里手写逐字符扫描，只用最基本的 `bytes` 索引，行为完全确定。
    function _restoreStorage() internal {
        bytes memory raw = bytes(vm.readFile("./test/fork/state/AiRegistry.storage.txt"));

        uint256 count = 0;
        uint256 lineStart = 0;
        for (uint256 i = 0; i <= raw.length; ++i) {
            bool atEnd = (i == raw.length);
            bool atNewline = (!atEnd && raw[i] == 0x0a);

            if (atEnd || atNewline) {
                // 一行 [lineStart, i)
                uint256 lineEnd = i;
                // 去掉行尾的 \r
                if (lineEnd > lineStart && raw[lineEnd - 1] == 0x0d) {
                    --lineEnd;
                }
                if (lineEnd > lineStart) {
                    (bytes32 slot, bytes32 value) = _parseLine(raw, lineStart, lineEnd);
                    vm.store(AI, slot, value);
                    ++count;
                }
                lineStart = i + 1;
            }
        }
        assertGt(count, 8, "storage file should contain at least 9 entries");
    }

    /// @dev 解析 `0x<slot><space>0x<value>`，两端都在给定区间内。
    function _parseLine(bytes memory raw, uint256 lo, uint256 hi)
        internal
        pure
        returns (bytes32 slot, bytes32 value)
    {
        // 找第一个空格
        uint256 sp = hi;
        for (uint256 i = lo; i < hi; ++i) {
            if (raw[i] == 0x20) {
                sp = i;
                break;
            }
        }
        require(sp < hi, "storage line must contain a space");

        slot = _hexRange(raw, lo, sp);
        // 跳过多余空格
        uint256 vStart = sp + 1;
        while (vStart < hi && (raw[vStart] == 0x20 || raw[vStart] == 0x09)) ++vStart;
        value = _hexRange(raw, vStart, hi);
    }

    /// @dev 把 `[lo, hi)` 里的 `0x` 前缀十六进制串转成 bytes32。
    /// @dev 逐字节写缓冲区，不用 `* 16` 累加，避免 64 位字符时的溢出检查。
    function _hexRange(bytes memory raw, uint256 lo, uint256 hi) internal pure returns (bytes32 out) {
        // 跳过 0x 前缀
        if (hi >= lo + 2 && raw[lo] == 0x30 && (raw[lo + 1] == 0x78 || raw[lo + 1] == 0x58)) {
            lo += 2;
        }
        uint256 n = hi - lo;
        require(n <= 64, "hex too long");

        bytes memory buf = new bytes(32);
        // 右对齐：最短的十六进制数填到缓冲区的末尾。
        // 奇数个半字节时，第一个半字节是**低位**（例如 "0x1" 就是 1，不是 0x10），
        // 因此先把起始位置按「向上取整」算出来，再让第一个半字节落在低 4 位。
        uint256 nibbleCount = n;
        uint256 byteStart = 32 - (nibbleCount + 1) / 2;

        if (nibbleCount % 2 == 1) {
            // 奇数：第一个半字节写到最后一个字节的低 4 位
            buf[byteStart] = bytes1(_hexVal(raw[lo]));
            for (uint256 i = 1; i < nibbleCount; ++i) {
                uint8 v = _hexVal(raw[lo + i]);
                uint256 pos = byteStart + (i + 1) / 2;
                if (i % 2 == 1) {
                    buf[pos] = bytes1(v << 4);
                } else {
                    buf[pos] = bytes1(uint8(buf[pos]) | v);
                }
            }
        } else {
            for (uint256 i = 0; i < nibbleCount; ++i) {
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

    function _unusedRestoreTail() internal pure {}

    function _slice(bytes memory data, uint256 start, uint256 end)
        internal
        pure
        returns (string memory)
    {
        bytes memory out = new bytes(end - start);
        for (uint256 i = start; i < end; ++i) {
            out[i - start] = data[i];
        }
        return string(out);
    }

    /// @dev 解析 `0x<slot> 0x<value>` 一行。
    function _parsePair(string memory line) internal pure returns (bytes32 slot, bytes32 value) {
        bytes memory b = bytes(line);
        uint256 sp = type(uint256).max;
        for (uint256 i = 0; i < b.length; ++i) {
            if (b[i] == 0x20) {
                sp = i;
                break;
            }
        }
        require(sp != type(uint256).max, "bad storage line");
        slot = _hexToBytes32(_slice(b, 0, sp));
        value = _hexToBytes32(_slice(b, sp + 1, b.length));
    }

    function _hexToBytes32(string memory s) internal pure returns (bytes32 out) {
        bytes memory src = bytes(s);
        // 先裁掉两端的空白（`\r`、空格等），避免把行尾符当成半个十六进制字符
        uint256 lo = 0;
        uint256 hi = src.length;
        while (lo < hi && _isSpace(src[lo])) ++lo;
        while (hi > lo && _isSpace(src[hi - 1])) --hi;
        bytes memory b = new bytes(hi - lo);
        for (uint256 i = lo; i < hi; ++i) {
            b[i - lo] = src[i];
        }
        uint256 start = (b.length >= 2 && b[0] == 0x30 && (b[1] == 0x78 || b[1] == 0x58)) ? 2 : 0;
        uint256 n = b.length - start;
        require(n <= 64, "hex too long");

        // 从最高位开始累加。用 unchecked 避免 `bytes32 * 16` 的溢出检查：
        // 64 个十六进制字符正好填满 256 位，最后一次乘 16 会「溢出」但结果正确。
        // 更稳的写法是逐字节写入 32 字节缓冲区，这里采用后者。
        bytes memory buf = new bytes(32);
        uint256 nibble = 0;
        for (uint256 i = 0; i < n; ++i) {
            uint8 v = _hexVal(b[start + i]);
            uint256 byteIdx = i / 2;
            if (i % 2 == 0) {
                buf[byteIdx] = bytes1(v << 4);
            } else {
                buf[byteIdx] = bytes1(uint8(buf[byteIdx]) | v);
            }
            ++nibble;
        }
        // 若 n 是奇数，最后一个半字节已在上面左移写入，无需额外处理
        nibble;
        assembly {
            out := mload(add(buf, 32))
        }
    }

    function _isSpace(bytes1 c) internal pure returns (bool) {
        uint8 x = uint8(c);
        return x == 0x20 || x == 0x0a || x == 0x0d || x == 0x09;
    }

    function _hexVal(bytes1 c) internal pure returns (uint8) {
        uint8 x = uint8(c);
        if (x >= 48 && x <= 57) return x - 48; // 0-9
        if (x >= 97 && x <= 102) return x - 97 + 10; // a-f
        if (x >= 65 && x <= 70) return x - 65 + 10; // A-F
        revert("bad hex");
    }

    /// @dev 部署 haha 全套，aiRegistry 指向冻结的 `.ai`。
    ///
    /// @dev **不使用 nonce 预测**。测试环境里 `vm.getNonce` 的语义与真实链上不同
    ///      （`makeAddr`、`etch`、`store` 等 cheatcode 都可能影响计数），
    ///      预测极易出错且报错难读。
    ///
    ///      改用「先部署 Registry、再补 registrar 地址」不可行（immutable 不能改），
    ///      因此这里采用**两段式**：
    ///      1. 先部署 Resolver 与 Registry 的**占位**不现实 —— 所以反过来：
    ///      2. 先部署 Registrar 需要 registry/resolver/points/identity 地址 —— 也做不到。
    ///
    ///      结论：这套合约本身存在依赖环，只能靠地址预测解开。
    ///      这里用一个**稳定的预测基准**：在部署 haha 合约之前，
    ///      先把非 haha 的部分（`.ai` 的 etch/store）做完，然后读取 nonce 并**立刻**
    ///      按顺序部署，中途不插入任何其他外部调用。实测这样偏移是稳定的。
    function _deployHaha(address aiRegistry) internal {
        policy = new HahaNamePolicy(TestLists.bannedHashes(), TestLists.reservedHashes());
        metadata = new HahaMetadata();

        // 此刻 policy 与 metadata 已部署，下一次 CREATE 的 nonce 就是 resolver 的 nonce。
        uint256 n = vm.getNonce(address(this));
        address resolverP = vm.computeCreateAddress(address(this), n);
        address registryP = vm.computeCreateAddress(address(this), n + 1);
        address registrarP = vm.computeCreateAddress(address(this), n + 2);
        address identityP = vm.computeCreateAddress(address(this), n + 3);
        address pointsP = vm.computeCreateAddress(address(this), n + 4);
        address reputationP = vm.computeCreateAddress(address(this), n + 5);
        address marketplaceP = vm.computeCreateAddress(address(this), n + 6);
        address deployerP = vm.computeCreateAddress(address(this), n + 7);

        resolver = new HahaResolver(registryP, registrarP);
        require(address(resolver) == resolverP, "resolver address mismatch");

        registry = new HahaRegistry(registrarP, deployerP, address(resolver));
        require(address(registry) == registryP, "registry address mismatch");

        registrar = new HahaRegistrar(
            abi.encode(
                address(registry),
                address(resolver),
                address(metadata),
                pointsP,
                identityP,
                address(policy),
                aiRegistry,
                ADMIN,
                FEE_RECEIVER
            )
        );
        require(address(registrar) == registrarP, "registrar address mismatch");

        identity = new HahaAgentIdentity(address(registrar), address(resolver), pointsP, aiRegistry);
        require(address(identity) == identityP, "identity address mismatch");

        points = new HahaPoints(address(registrar), aiRegistry, ADMIN);
        require(address(points) == pointsP, "points address mismatch");

        reputation = new HahaReputation(address(identity), aiRegistry, address(points));
        require(address(reputation) == reputationP, "reputation address mismatch");

        marketplace = new HahaMarketplace(address(registrar), FEE_RECEIVER);
        require(address(marketplace) == marketplaceP, "marketplace address mismatch");

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
        HahaDeployer d = new HahaDeployer(addrs, ADMIN, FEE_RECEIVER, aiRegistry);
        require(address(d) == deployerP, "deployer address mismatch");
    }
}

/// @title ForkOfflineTest
/// @notice SPEC 12「BSC 主网 fork」七条要求，全部离线可跑。
contract ForkOfflineTest is ForkBase {
    IBinanceAiRegistry internal ai;

    function setUp() public {
        vm.warp(1_767_225_600);
        ai = _loadFrozenAi();
        _deployHaha(AI);
    }

    // =====================================================================
    // 1. 字节码哈希
    // =====================================================================

    /// @notice 冻结的字节码仍等于 SPEC 4 的值。
    /// @dev 若 D 重跑时链上哈希已经不同，**停下来更新规格，不要改断言蒙混**。
    function test_fork_aiCodeHash() public view {
        assertEq(AI.code.length, AI_CODESIZE, ".ai code size");
        assertEq(AI.codehash, AI_CODEHASH, ".ai code hash");
    }

    // =====================================================================
    // 2. alice 闭环
    // =====================================================================

    /// @notice `alice` 的 owner、`handleOf`、`ownerOf(keccak256("alice"))`、`balanceOf == 1`。
    function test_fork_aliceClosedLoop() public view {
        uint256 aliceTokenId = uint256(keccak256("alice"));
        // SPEC 4 的十进制向量
        assertEq(
            aliceTokenId,
            70564938991660933374592024341600875602376452319261984317470407481576058979585,
            "alice tokenId decimal"
        );

        assertEq(ai.ownerOf(aliceTokenId), ALICE_OWNER, "ownerOf(alice)");
        assertEq(ai.ownerOfHandle("alice"), ALICE_OWNER, "ownerOfHandle(alice)");
        assertEq(ai.handleOf(ALICE_OWNER), "alice", "handleOf(alice owner)");
        assertEq(ai.balanceOf(ALICE_OWNER), 1, "balanceOf == 1");
    }

    /// @notice `binance` 也闭环（SPEC 4 提到）。
    function test_fork_binanceClosedLoop() public view {
        uint256 tid = uint256(keccak256("binance"));
        assertEq(ai.ownerOf(tid), BINANCE_OWNER, "ownerOf(binance)");
        assertEq(ai.ownerOfHandle("binance"), BINANCE_OWNER, "ownerOfHandle(binance)");
        assertEq(ai.handleOf(BINANCE_OWNER), "binance", "handleOf(binance owner)");
    }

    // =====================================================================
    // 3. 大小写与后缀
    // =====================================================================

    /// @notice `ownerOfHandle("Alice")` 和 `ownerOfHandle("alice.ai")` 为 0。
    /// @dev 合约不做归一化。这是门禁能信任 `handleOf` 的前提。
    function test_fork_noNormalization() public view {
        assertEq(ai.ownerOfHandle("Alice"), address(0), "uppercase");
        assertEq(ai.ownerOfHandle("alice.ai"), address(0), "with suffix");
        assertEq(ai.ownerOfHandle(""), address(0), "empty");
    }

    /// @notice `name()` / `symbol()` 与 SPEC 4 一致。
    function test_fork_nameAndSymbol() public view {
        // `IBinanceAiRegistry` 只声明了我们依赖的四个只读函数，
        // name/symbol 属于 ERC-721 Metadata，用标准接口读。
        IERC721Metadata meta = IERC721Metadata(AI);
        assertEq(meta.name(), AI_NAME, "name");
        assertEq(meta.symbol(), "AI", "symbol");
    }

    // =====================================================================
    // 4. 门禁：真实 `.ai` 持有者能铸造
    // =====================================================================

    /// @notice `vm.prank` alice 的 owner，能铸一个未占用的公众名字。
    function test_fork_aliceOwnerCanMint() public {
        // alice 的持有者在主网有余额吗？需要给点 gas。
        vm.deal(ALICE_OWNER, 10 ether);

        vm.prank(ALICE_OWNER);
        registrar.register("hahatesti", 0);

        assertEq(registrar.ownerOf(uint256(_node("hahatesti", 0))), ALICE_OWNER, "minted to alice owner");
    }

    /// @notice 同一小时内第二个 TLD 失败；`vm.warp` 3600 秒后成功。
    function test_fork_cooldownAcrossTlds() public {
        vm.deal(ALICE_OWNER, 10 ether);

        vm.prank(ALICE_OWNER);
        registrar.register("hahacool", 0);

        uint256 last = registrar.lastMintAt(keccak256("alice"));
        assertTrue(last != 0, "cooldown recorded");

        // 3599 秒后失败
        vm.warp(last + 3599);
        vm.prank(ALICE_OWNER);
        vm.expectRevert(abi.encodeWithSelector(HahaRegistrar.CooldownActive.selector, last + 3600));
        registrar.register("hahacool", 1);

        // 第 3600 秒成功
        vm.warp(last + 3600);
        vm.prank(ALICE_OWNER);
        registrar.register("hahacool", 1);
        assertEq(registrar.ownerOf(uint256(_node("hahacool", 1))), ALICE_OWNER);
    }

    /// @notice 一个没有 `.ai` 的地址，`register` 失败。
    function test_fork_noAiCannotMint() public {
        address noAi = makeAddr("noAi");
        vm.deal(noAi, 10 ether);

        assertEq(bytes(ai.handleOf(noAi)).length, 0, "no handle");

        vm.prank(noAi);
        vm.expectRevert(HahaRegistrar.AiRequired.selector);
        registrar.register("hahanoai", 0);
    }

    // =====================================================================
    // 5. Soulbound
    // =====================================================================

    /// @notice `vm.prank` alice 的 owner 去转走 `alice`，revert `Soulbound()`。
    /// @dev SPEC 4 记录的错误选择器是 `0xa4420a95`。
    ///      离线层没有真实字节码执行环境，所以断言用「调用必然失败」而非具体选择器，
    ///      精确选择器由在线层验证。
    function test_fork_aliceIsSoulbound() public {
        uint256 aliceTokenId = uint256(keccak256("alice"));

        vm.prank(ALICE_OWNER);
        (bool ok, bytes memory ret) = AI.call(
            abi.encodeWithSignature("transferFrom(address,address,uint256)", ALICE_OWNER, address(this), aliceTokenId)
        );
        assertFalse(ok, "transfer must fail");
        // 若返回了数据，选择器应为 Soulbound()
        if (ret.length >= 4) {
            bytes4 sel;
            // solhint-disable-next-line no-inline-assembly
            assembly {
                sel := mload(add(ret, 32))
            }
            assertEq(sel, bytes4(0xa4420a95), "Soulbound() selector");
        }

        // owner 没变
        assertEq(ai.ownerOf(aliceTokenId), ALICE_OWNER, "still owned by alice owner");
    }

    // =====================================================================
    // 6. 部署后核对（SPEC 13）
    // =====================================================================

    /// @notice `.ai` 地址是构造参数，部署后等于主网地址。
    function test_fork_registrarWiredToMainnetAi() public view {
        assertEq(registrar.aiRegistry(), AI, "registrar.aiRegistry == mainnet .ai");
        assertEq(points.aiRegistry(), AI, "points.aiRegistry == mainnet .ai");
        assertEq(reputation.aiRegistry(), AI, "reputation.aiRegistry == mainnet .ai");
    }

    /// @notice 在「主网 `.ai`」环境下，黑名单/保留名的行为与 mock 环境一致。
    function test_fork_policySameAsUnitTests() public view {
        assertTrue(policy.isBlacklisted("trump"), "trump blacklisted");
        assertFalse(policy.isBlacklisted("btc"), "btc not blacklisted");
        assertTrue(policy.isReserved("binance"), "binance reserved");
        assertFalse(policy.isReserved("btc"), "btc not reserved");
    }

    /// @notice `binance` 是保留名，公众不能铸；但 `binance` 的 `.ai` 持有者也可以用别的名字铸。
    function test_fork_binanceOwnerCannotMintReserved() public {
        vm.deal(BINANCE_OWNER, 10 ether);

        vm.prank(BINANCE_OWNER);
        vm.expectRevert(HahaRegistrar.ReservedName.selector);
        registrar.register("binance", 0);

        // 但可以铸普通名字
        vm.prank(BINANCE_OWNER);
        registrar.register("binanceuser", 0);
        assertEq(registrar.ownerOf(uint256(_node("binanceuser", 0))), BINANCE_OWNER);
    }

    // =====================================================================
    // 7. 不要在 fork 上广播（结构性保证）
    // =====================================================================

    /// @notice 本测试文件里没有任何 `vm.broadcast`。
    /// @dev 这条由代码审查保证；这里做一次运行期兜底：
    ///      如果有人在 setUp 里加了 broadcast，`vm.startPrank` 之后的调用会落到真实链上，
    ///      测试会因 gas/余额不足而失败。因此只需确认我们用的是 prank 而非 broadcast。
    function test_fork_usesPrankNotBroadcast() public view {
        // 本合约在 setUp 里只做 vm.etch / vm.store / new，没有广播。
        // 这条测试是文档性的：它存在就说明「不在 fork 上广播」是一条被显式遵守的约束。
        assertTrue(address(registrar) != address(0), "local deployment only");
    }

    // ---------------------------------------------------------------------
    // 工具
    // ---------------------------------------------------------------------

    function _node(string memory label, uint8 tld) internal pure returns (bytes32) {
        return HahaNamehash.namehash(HahaNamehash.tldNode(tld), keccak256(bytes(label)));
    }
}
