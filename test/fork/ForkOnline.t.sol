// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Test} from "forge-std/Test.sol";
import {IERC721Metadata} from "@openzeppelin/contracts/token/ERC721/extensions/IERC721Metadata.sol";

/// @title ForkOnlineTest
/// @notice 在线层：对**真实 BSC 主网 RPC** 做与离线层同组的断言，用于交叉验证。
///
/// @dev ## 运行方式
///
/// ```bash
/// export BSC_RPC_URL=https://bsc-dataseed.bnbchain.org
/// forge test --match-contract ForkOnlineTest --fork-url $BSC_RPC_URL
/// ```
///
/// ## 为什么是「可选」而不是 CI 必跑
///
/// - 需要联网，CI 环境不一定允许。
/// - 公共 RPC 对**历史区块**的状态可能不可读（实测区块 `134683411` 返回
///   `missing trie node`）。因此这里用 `latest`，并把字节码哈希**写死断言**：
///   `.ai` 不可升级，只要字节码不变，`latest` 与 SPEC 4 记录的就是同一份代码。
///   一旦字节码变了，测试失败，应该停下来更新规格。
///
/// ## 不使用 `vm.createFork` 的抽象
///
/// 直接 `--fork-url` 起 fork，`block.chainid` 必须是 56。这条断言放在第一个测试里，
/// 防止有人在 Ethereum 主网 RPC 上误跑而得到假的「全部通过」。
contract ForkOnlineTest is Test {
    address internal constant AI = 0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F;
    bytes32 internal constant AI_CODEHASH =
        0xc4006e6e6ffaaf6996116617392beabe4f5f0a0795841322f91c2ceac34d6ace;
    uint256 internal constant AI_CODESIZE = 8756;

    address internal constant ALICE_OWNER = 0xA506ac7069937571DC56C5f8FDa53c4A729456c6;

    bool internal forkReady;

    function setUp() public {
        // 只有真的连着 BSC 主网时才跑。否则跳过所有测试，不让 CI 因为没网而红。
        if (block.chainid != 56) {
            forkReady = false;
            return;
        }
        if (AI.code.length == 0) {
            forkReady = false;
            return;
        }
        forkReady = true;
    }

    modifier onlyFork() {
        if (!forkReady) {
            vm.skip(true);
        }
        _;
    }

    // =====================================================================
    // 链与字节码
    // =====================================================================

    /// @notice chainId 必须是 56。在别的链上跑这个文件没意义。
    /// @dev 非 fork 环境下**跳过**而不是失败：本文件是「可选在线层」，
    ///      `forge test` 不带 `--fork-url` 时应该安静跳过，而不是把 CI 弄红。
    function test_online_chainIdIsBsc() public {
        if (block.chainid != 56) {
            vm.skip(true);
        }
        assertEq(block.chainid, 56, "must run against BSC mainnet");
    }

    /// @notice `.ai` 运行时字节码与 SPEC 4 完全一致。
    /// @dev 若这条失败：**停下来更新规格**，不要改期望值蒙混（SPEC 12 的原文要求）。
    function test_online_aiCodeHash() public onlyFork {
        assertEq(AI.code.length, AI_CODESIZE, ".ai code size");
        assertEq(AI.codehash, AI_CODEHASH, ".ai code hash");
    }

    // =====================================================================
    // alice / binance 闭环
    // =====================================================================

    function test_online_aliceClosedLoop() public onlyFork {
        uint256 aliceTokenId = uint256(keccak256("alice"));

        // 与 SPEC 4 的十进制向量逐位一致
        assertEq(
            aliceTokenId,
            70564938991660933374592024341600875602376452319261984317470407481576058979585,
            "alice tokenId"
        );

        (bool ok, bytes memory ret) = AI.staticcall(abi.encodeWithSignature("ownerOf(uint256)", aliceTokenId));
        assertTrue(ok, "ownerOf call ok");
        address owner = abi.decode(ret, (address));
        assertEq(owner, ALICE_OWNER, "ownerOf(alice)");
    }

    /// @notice `handleOf` / `ownerOfHandle` / `balanceOf` 三者一致。
    function test_online_aliceTripleConsistency() public onlyFork {
        (bool ok, bytes memory ret) = AI.staticcall(
            abi.encodeWithSignature("handleOf(address)", ALICE_OWNER)
        );
        assertTrue(ok, "handleOf ok");
        string memory handle = abi.decode(ret, (string));
        assertEq(handle, "alice", "handleOf(alice owner)");

        (ok, ret) = AI.staticcall(abi.encodeWithSignature("ownerOfHandle(string)", "alice"));
        assertTrue(ok, "ownerOfHandle ok");
        assertEq(abi.decode(ret, (address)), ALICE_OWNER, "ownerOfHandle(alice)");

        (ok, ret) = AI.staticcall(abi.encodeWithSignature("balanceOf(address)", ALICE_OWNER));
        assertTrue(ok, "balanceOf ok");
        assertEq(abi.decode(ret, (uint256)), 1, "balanceOf == 1");
    }

    // =====================================================================
    // 不归一化
    // =====================================================================

    function test_online_noNormalization() public onlyFork {
        string[3] memory variants = ["Alice", "alice.ai", ""];
        for (uint256 i = 0; i < variants.length; ++i) {
            (bool ok, bytes memory ret) =
                AI.staticcall(abi.encodeWithSignature("ownerOfHandle(string)", variants[i]));
            assertTrue(ok, "call ok");
            assertEq(abi.decode(ret, (address)), address(0), variants[i]);
        }
    }

    // =====================================================================
    // Soulbound 的**精确选择器**
    // =====================================================================

    /// @notice 离线层拿不到真实错误选择器，这里补上：必须是 `Soulbound()` = `0xa4420a95`。
    function test_online_soulboundSelector() public onlyFork {
        uint256 aliceTokenId = uint256(keccak256("alice"));

        vm.prank(ALICE_OWNER);
        (bool ok, bytes memory ret) = AI.call(
            abi.encodeWithSignature(
                "transferFrom(address,address,uint256)", ALICE_OWNER, address(this), aliceTokenId
            )
        );
        assertFalse(ok, "transfer must revert");

        bytes4 got;
        // solhint-disable-next-line no-inline-assembly
        assembly {
            got := mload(add(ret, 32))
        }
        assertEq(got, bytes4(0xa4420a95), "Soulbound() selector");
    }

    // =====================================================================
    // name / symbol
    // =====================================================================

    function test_online_nameAndSymbol() public onlyFork {
        IERC721Metadata meta = IERC721Metadata(AI);
        assertEq(meta.name(), "SPACE ID Agent ID", "name");
        assertEq(meta.symbol(), "AI", "symbol");
    }

    // =====================================================================
    // 不可升级
    // =====================================================================

    /// @notice EIP-1967 的 implementation / admin 槽都是 0，不是代理。
    function test_online_notProxy() public onlyFork {
        bytes32 implSlot = 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc;
        bytes32 adminSlot = 0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103;

        assertEq(vm.load(AI, implSlot), bytes32(0), "no EIP-1967 implementation");
        assertEq(vm.load(AI, adminSlot), bytes32(0), "no EIP-1967 admin");
    }

    /// @notice dispatcher 里没有 `upgradeTo` / `proxiableUUID` / `burn`。
    function test_online_noUpgradeOrBurnSelectors() public onlyFork {
        // 调用这些选择器必须失败（合约没有 fallback）
        (bool a,) = AI.staticcall(abi.encodeWithSignature("upgradeTo(address)", address(1)));
        assertFalse(a, "no upgradeTo");

        (bool b,) = AI.staticcall(abi.encodeWithSignature("proxiableUUID()"));
        assertFalse(b, "no proxiableUUID");

        (bool c,) = AI.staticcall(abi.encodeWithSignature("burn(uint256)", 1));
        assertFalse(c, "no burn");
    }

    // =====================================================================
    // 支持/不支持的 ERC-165 接口（SPEC 4 的表）
    // =====================================================================

    function test_online_supportsInterface() public onlyFork {
        bytes4[5] memory ids = [bytes4(0x01ffc9a7), bytes4(0x80ac58cd), bytes4(0x5b5e139f), bytes4(0x780e9d63), bytes4(0x2a55205a)];
        bool[5] memory want = [true, true, true, false, false];

        for (uint256 i = 0; i < ids.length; ++i) {
            (bool ok, bytes memory ret) =
                AI.staticcall(abi.encodeWithSignature("supportsInterface(bytes4)", ids[i]));
            assertTrue(ok, "call ok");
            bool got = abi.decode(ret, (bool));
            assertEq(got, want[i], "supportsInterface");
        }
    }
}
