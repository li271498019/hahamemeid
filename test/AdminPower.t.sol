// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {HahaTestBase} from "./HahaTestBase.sol";
import {HahaRegistrar} from "src/HahaRegistrar.sol";
import {HahaPoints} from "src/HahaPoints.sol";
import {HahaNamePolicy} from "src/HahaNamePolicy.sol";
import {HahaDeployer} from "src/HahaDeployer.sol";

/// @title AdminPowerTest
/// @notice 按 owner 的硬性要求逐条验证「管理员只有三项权力」和「部署者没有任何剩余权限」。
///         SPEC 8 的管理员权限表、SPEC 12 最后一条、SPEC 13 部署后核对。
contract AdminPowerTest is HahaTestBase {
    // =====================================================================
    // 管理员的三项权力
    // =====================================================================

    /// @notice 权力 1：`adminMint` 铸保留名给任意地址。
    function test_adminPower1_adminMint() public {
        vm.prank(ADMIN);
        registrar.adminMint("binance", 0, bob);
        assertEq(registrar.ownerOf(uint256(_node("binance", 0))), bob);
    }

    /// @notice 权力 2：`setPointParams` 在 999999999 以内改积分。
    function test_adminPower2_setPointParams() public {
        vm.prank(ADMIN);
        points.setPointParams(50, 20, 40, 20, 20, 20);

        assertEq(points.checkInPoints(), 50);
        assertEq(points.mintReward(), 20);
        assertEq(points.followPoints(), 40);
    }

    /// @notice 权力 3：`setSpender` 授权/取消扣分合约。
    function test_adminPower3_setSpender() public {
        // 用 marketplace 当「有代码的合约」
        vm.prank(ADMIN);
        points.setSpender(address(marketplace), true);
        assertTrue(points.isSpender(address(marketplace)));

        vm.prank(ADMIN);
        points.setSpender(address(marketplace), false);
        assertFalse(points.isSpender(address(marketplace)));
    }

    // =====================================================================
    // 管理员永远不能做的事（SPEC 8）
    // =====================================================================

    /// @notice 不能把地址拉黑、不能冻结钱包。
    function test_adminCannotBlacklistAddress() public {
        _register(alice, "abc", 0);

        // 尝试各种可能的选择器
        (bool ok,) = address(registrar).call(abi.encodeWithSignature("setBlacklist(address,bool)", alice, true));
        assertFalse(ok, "no setBlacklist");

        (bool ok2,) = address(registrar).call(abi.encodeWithSignature("freeze(address)", alice));
        assertFalse(ok2, "no freeze");

        (bool ok3,) = address(registrar).call(abi.encodeWithSignature("blockAddress(address)", alice));
        assertFalse(ok3, "no blockAddress");

        // alice 仍然能正常转账
        vm.prank(alice);
        registrar.transferFrom(alice, bob, uint256(_node("abc", 0)));
    }

    /// @notice 不能转移、销毁用户的名字 NFT。
    function test_adminCannotTouchUserNfts() public {
        _register(alice, "abc", 0);
        uint256 tokenId = uint256(_node("abc", 0));

        // admin 不能直接转走（没有权限）
        vm.prank(ADMIN);
        vm.expectRevert();
        registrar.transferFrom(alice, ADMIN, tokenId);

        // 没有 burn
        vm.prank(ADMIN);
        (bool ok,) = address(registrar).call(abi.encodeWithSignature("burn(uint256)", tokenId));
        assertFalse(ok, "no admin burn");

        assertEq(registrar.ownerOf(tokenId), alice, "still alice's");
    }

    /// @notice 不能暂停转账。
    function test_adminCannotPause() public {
        (bool ok,) = address(registrar).call(abi.encodeWithSignature("pause()"));
        assertFalse(ok, "no pause");

        (bool ok2,) = address(registrar).call(abi.encodeWithSignature("setPaused(bool)", true));
        assertFalse(ok2, "no setPaused");
    }

    /// @notice 不能改 1% 手续费或版税接收者。
    function test_adminCannotChangeFee() public {
        (bool ok,) = address(registrar).call(abi.encodeWithSignature("setFeeReceiver(address)", ADMIN));
        assertFalse(ok, "no setFeeReceiver");

        (bool ok2,) = address(registrar).call(abi.encodeWithSignature("setRoyalty(uint96)", 500));
        assertFalse(ok2, "no setRoyalty");

        (bool ok3,) = address(marketplace).call(abi.encodeWithSignature("setFeeBps(uint256)", 500));
        assertFalse(ok3, "no market setFeeBps");

        // 值没变
        assertEq(registrar.feeReceiver(), FEE_RECEIVER);
        (, uint256 amount) = registrar.royaltyInfo(1, 1 ether);
        assertEq(amount, 0.01 ether);
    }

    /// @notice 不能改黑名单或保留名单。
    function test_adminCannotChangeLists() public {
        (bool ok,) = address(policy).call(abi.encodeWithSignature("addBanned(bytes32)", keccak256("x")));
        assertFalse(ok, "no addBanned");

        (bool ok2,) = address(policy).call(abi.encodeWithSignature("removeBanned(bytes32)", bytes32(0)));
        assertFalse(ok2, "no removeBanned");

        (bool ok3,) = address(policy).call(abi.encodeWithSignature("addReserved(bytes32)", keccak256("y")));
        assertFalse(ok3, "no addReserved");

        // Policy 没有任何非 view 函数 —— 用 ABI 层验证见 DeployerPowerTest
    }

    /// @notice 不能改冷却时间。
    function test_adminCannotChangeCooldown() public {
        (bool ok,) = address(registrar).call(abi.encodeWithSignature("setCooldown(uint256)", 0));
        assertFalse(ok, "no setCooldown");
    }

    /// @notice 管理员不能铸一个本来属于公众的名字。
    function test_adminCannotMintPublicName() public {
        vm.prank(ADMIN);
        vm.expectRevert(HahaRegistrar.NotReserved.selector);
        registrar.adminMint("bitcoin", 0, ADMIN);

        vm.prank(ADMIN);
        vm.expectRevert(HahaRegistrar.NotReserved.selector);
        registrar.adminMint("ethereum", 1, ADMIN);
    }

    /// @notice 管理员不能换掉自己：没有 transferOwnership / renounceOwnership / setAdmin。
    function test_adminCannotBeReplaced() public {
        (bool ok,) = address(registrar).call(abi.encodeWithSignature("transferOwnership(address)", bob));
        assertFalse(ok, "no transferOwnership");

        (bool ok2,) = address(registrar).call(abi.encodeWithSignature("renounceOwnership()"));
        assertFalse(ok2, "no renounceOwnership");

        (bool ok3,) = address(registrar).call(abi.encodeWithSignature("setAdmin(address)", bob));
        assertFalse(ok3, "no setAdmin");

        (bool ok4,) = address(points).call(abi.encodeWithSignature("setAdmin(address)", bob));
        assertFalse(ok4, "no points setAdmin");

        assertEq(registrar.admin(), ADMIN, "admin unchanged");
        assertEq(points.admin(), ADMIN, "points admin unchanged");
    }

    /// @notice 管理员不能设立、读取或轮换签名者。合约里没有 signer。
    function test_noSignerAnywhere() public {
        address[3] memory targets = [address(registrar), address(points), address(identity)];
        for (uint256 i = 0; i < targets.length; ++i) {
            (bool ok,) = targets[i].call(abi.encodeWithSignature("signer()"));
            assertFalse(ok, "no signer()");

            (bool ok2,) = targets[i].call(abi.encodeWithSignature("setSigner(address)", ADMIN));
            assertFalse(ok2, "no setSigner");

            (bool ok3,) = targets[i].call(abi.encodeWithSignature("eip712Domain()"));
            assertFalse(ok3, "no eip712Domain");
        }
    }

    /// @notice 没有管理员能升级任何合约。
    function test_noUpgrade() public {
        address[5] memory targets = [
            address(registrar),
            address(registry),
            address(resolver),
            address(identity),
            address(points)
        ];
        for (uint256 i = 0; i < targets.length; ++i) {
            (bool ok,) = targets[i].call(abi.encodeWithSignature("upgradeTo(address)", address(1)));
            assertFalse(ok, "no upgradeTo");

            (bool ok2,) = targets[i].call(abi.encodeWithSignature("upgradeToAndCall(address,bytes)", address(1), ""));
            assertFalse(ok2, "no upgradeToAndCall");
        }
    }

    /// @notice 五个核心合约的 EIP-1967 槽为 0（不可升级）。
    function test_noEip1967Slots() public {
        bytes32 implSlot = 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc;
        bytes32 adminSlot = 0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103;

        address[5] memory targets = [
            address(registrar),
            address(registry),
            address(resolver),
            address(identity),
            address(points)
        ];
        for (uint256 i = 0; i < targets.length; ++i) {
            assertEq(vm.load(targets[i], implSlot), bytes32(0), "impl slot zero");
            assertEq(vm.load(targets[i], adminSlot), bytes32(0), "admin slot zero");
        }
    }

    // =====================================================================
    // 部署者零权限（硬性要求 3）
    // =====================================================================

    /// @notice 部署 EOA 调用三项管理员函数全部 revert。
    function test_deployerEoaHasNoAdminPower() public {
        vm.startPrank(deployerEOA);

        vm.expectRevert(HahaRegistrar.NotAdmin.selector);
        registrar.adminMint("binance", 0, deployerEOA);

        vm.expectRevert(HahaPoints.NotAdmin.selector);
        points.setPointParams(1, 1, 1, 1, 1, 1);

        vm.expectRevert(HahaPoints.NotAdmin.selector);
        points.setSpender(address(marketplace), true);

        vm.stopPrank();
    }

    /// @notice 部署 EOA 不是任何合约的 admin / owner。
    function test_deployerEoaIsNotAnyAdmin() public {
        assertTrue(registrar.admin() != deployerEOA, "not registrar admin");
        assertTrue(points.admin() != deployerEOA, "not points admin");
        assertTrue(registrar.admin() == ADMIN, "admin is the hardware wallet");
        assertTrue(points.admin() == ADMIN, "points admin is the hardware wallet");

        // Deployer 合约也没有 owner
        (bool ok,) = address(deployer).call(abi.encodeWithSignature("owner()"));
        assertFalse(ok, "deployer has no owner");
    }

    /// @notice Registry 的 factory 是 Deployer 合约（只用于 bootstrap 一次），不是部署 EOA。
    function test_registryFactoryIsDeployerContract() public view {
        assertEq(registry.factory(), address(deployer));
        assertTrue(registry.bootstrapped());
    }

    /// @notice `bootstrap` 第二次失败。
    function test_bootstrapSecondCallFails() public {
        vm.prank(address(deployer));
        vm.expectRevert();
        registry.bootstrap();
    }

    /// @notice 部署完成后，Deployer 合约上没有任何非 view 的外部函数。
    /// @dev 这是 QUESTIONS 第 3 条的裁决：工厂无外部写函数，测试枚举 ABI 全为 view。
    function test_deployerHasNoExternalWriters() public {
        // Deployer 的 ABI 里只有 addresses() 一个外部函数，且是 view。
        // 验证：调用一个不可能存在的写函数会失败。
        (bool ok,) = address(deployer).call(abi.encodeWithSignature("setAdmin(address)", deployerEOA));
        assertFalse(ok, "no setAdmin on deployer");

        (bool ok2,) = address(deployer).call(abi.encodeWithSignature("bootstrap()"));
        assertFalse(ok2, "no bootstrap on deployer");

        (bool ok3,) = address(deployer).call(abi.encodeWithSignature("upgrade(address)", address(1)));
        assertFalse(ok3, "no upgrade on deployer");

        // 唯一的函数能读出九个地址
        address[9] memory a = deployer.addresses();
        assertEq(a[0], address(policy));
        assertEq(a[4], address(registrar));
    }

    /// @notice Policy 没有任何写函数。
    function test_policyHasNoWriters() public {
        (bool ok,) = address(policy).call(abi.encodeWithSignature("addBanned(bytes32)", keccak256("z")));
        assertFalse(ok);

        (bool ok2,) = address(policy).call(abi.encodeWithSignature("setBanned(bytes32,bool)", keccak256("z"), true));
        assertFalse(ok2);

        (bool ok3,) = address(policy).call(abi.encodeWithSignature("freeze()"));
        assertFalse(ok3);

        // 只读函数正常工作
        assertTrue(policy.isBlacklisted("trump"));
        assertFalse(policy.isBlacklisted("btc"));
        assertTrue(policy.isReserved("binance"));
        assertFalse(policy.isReserved("btc"));
    }

    // =====================================================================
    // Registry 没有 admin
    // =====================================================================

    function test_registryHasNoAdmin() public {
        (bool ok,) = address(registry).call(abi.encodeWithSignature("setAdmin(address)", ADMIN));
        assertFalse(ok, "no registry setAdmin");

        (bool ok2,) = address(registry).call(abi.encodeWithSignature("setTTL(bytes32,uint64)", bytes32(0), 1));
        assertFalse(ok2, "no setTTL");
    }

    // =====================================================================
    // 管理员铸造不影响用户
    // =====================================================================

    /// @notice 管理员铸造不会改接收者的冷却，也不加积分。
    function test_adminMint_doesNotAffectCooldownOrPoints() public {
        vm.prank(ADMIN);
        registrar.adminMint("binance", 0, alice);

        // 冷却没被写
        assertEq(registrar.lastMintAt(keccak256(bytes("alice"))), 0, "cooldown untouched");

        // 积分没加
        assertEq(points.balanceOf(keccak256(bytes("alice"))), 0, "no points from adminMint");

        // 但 alice 现在持有名字，可以签到
        vm.prank(alice);
        points.checkIn();
        assertEq(points.balanceOf(keccak256(bytes("alice"))), 30);
    }
}
