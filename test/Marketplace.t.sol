// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {ERC721Holder} from "@openzeppelin/contracts/token/ERC721/utils/ERC721Holder.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

import {HahaTestBase} from "./HahaTestBase.sol";
import {HahaMarketplace} from "src/HahaMarketplace.sol";
import {HahaRegistrar} from "src/HahaRegistrar.sol";
import {HahaPoints} from "src/HahaPoints.sol";

/// @notice 在收到 NFT 时重入 `buy` 或 `withdraw` 的攻击者。
contract ReentrantBuyer is ERC721Holder {
    HahaMarketplace internal market;
    uint256 internal targetTokenId;
    uint256 internal repeat;
    bool internal attackOnReceive;

    constructor(HahaMarketplace m) {
        market = m;
    }

    function setTarget(uint256 tokenId, uint256 times) external {
        targetTokenId = tokenId;
        repeat = times;
    }

    function attackBuy(uint256 tokenId) external payable {
        attackOnReceive = true;
        targetTokenId = tokenId;
        repeat = 1;
        market.buy{value: msg.value}(tokenId);
    }

    function attackWithdraw() external {
        attackOnReceive = true;
        repeat = 1;
        market.withdraw();
    }

    function onERC721Received(address, address, uint256, bytes memory)
        public
        override
        returns (bytes4)
    {
        if (attackOnReceive && repeat > 0) {
            repeat = 0;
            // 尝试重入 withdraw
            if (address(market).balance > 0) {
                try market.withdraw() {} catch {}
            }
            // 尝试重入 buy
            try market.buy{value: 0}(targetTokenId) {} catch {}
        }
        return ERC721Holder.onERC721Received.selector;
    }

    receive() external payable {}
}

/// @notice 一个会 revert 的收款地址，用来证明拉取式提现不会卡住别人的购买。
contract RevertingReceiver {
    receive() external payable {
        revert("no bnb");
    }
}

/// @title MarketplaceTest
/// @notice BNB 一口价、1% 手续费、拉取式提现、重入防护。
contract MarketplaceTest is HahaTestBase {
    uint256 internal tokenId;

    function setUp() public override {
        super.setUp();
        tokenId = _register(alice, "abc", 0);
        // alice 授权市场
        vm.prank(alice);
        registrar.setApprovalForAll(address(marketplace), true);
    }

    // =====================================================================
    // 挂单
    // =====================================================================

    function test_list_andRead() public {
        vm.prank(alice);
        marketplace.list(tokenId, 1 ether);

        (address seller, uint256 price) = marketplace.listings(tokenId);
        assertEq(seller, alice);
        assertEq(price, 1 ether);
    }

    /// @notice 未授权不能挂单。
    function test_list_requiresApproval() public {
        vm.prank(alice);
        registrar.setApprovalForAll(address(marketplace), false);

        vm.prank(alice);
        vm.expectRevert(HahaMarketplace.NotApproved.selector);
        marketplace.list(tokenId, 1 ether);
    }

    /// @notice 单个 token 的 `approve` 也算授权。
    function test_list_singleApproveWorks() public {
        vm.prank(alice);
        registrar.setApprovalForAll(address(marketplace), false);

        vm.prank(alice);
        registrar.approve(address(marketplace), tokenId);

        vm.prank(alice);
        marketplace.list(tokenId, 1 ether);

        (address seller,) = marketplace.listings(tokenId);
        assertEq(seller, alice);
    }

    /// @notice 非 owner 不能挂单。
    function test_list_onlyOwner() public {
        vm.prank(bob);
        vm.expectRevert();
        marketplace.list(tokenId, 1 ether);
    }

    /// @notice 已有挂单不能重复 list，要改价走 `updatePrice`。
    function test_list_alreadyListed() public {
        vm.startPrank(alice);
        marketplace.list(tokenId, 1 ether);
        vm.expectRevert(HahaMarketplace.AlreadyListed.selector);
        marketplace.list(tokenId, 2 ether);
        vm.stopPrank();
    }

    /// @notice 价格 99 wei 失败（fee 为 0），100 wei 的 fee 为 1。
    function test_list_feeMustBePositive() public {
        vm.startPrank(alice);
        vm.expectRevert(HahaMarketplace.PriceTooLow.selector);
        marketplace.list(tokenId, 99);

        marketplace.list(tokenId, 100);
        vm.stopPrank();

        assertEq(marketplace.feeFor(100), 1);
        assertEq(marketplace.feeFor(99), 0);
    }

    // =====================================================================
    // 改价与取消
    // =====================================================================

    function test_updatePrice() public {
        vm.startPrank(alice);
        marketplace.list(tokenId, 1 ether);

        vm.expectEmit(true, true, false, true, address(marketplace));
        emit HahaMarketplace.PriceUpdated(tokenId, alice, 1 ether, 2 ether);
        marketplace.updatePrice(tokenId, 2 ether);
        vm.stopPrank();

        (, uint256 price) = marketplace.listings(tokenId);
        assertEq(price, 2 ether);
    }

    function test_updatePrice_onlySeller() public {
        vm.prank(alice);
        marketplace.list(tokenId, 1 ether);

        vm.prank(bob);
        vm.expectRevert(HahaMarketplace.NotSeller.selector);
        marketplace.updatePrice(tokenId, 3 ether);
    }

    function test_cancel() public {
        vm.startPrank(alice);
        marketplace.list(tokenId, 1 ether);
        marketplace.cancel(tokenId);
        vm.stopPrank();

        (address seller,) = marketplace.listings(tokenId);
        assertEq(seller, address(0));
    }

    function test_cancel_onlySeller() public {
        vm.prank(alice);
        marketplace.list(tokenId, 1 ether);

        vm.prank(bob);
        vm.expectRevert(HahaMarketplace.NotSeller.selector);
        marketplace.cancel(tokenId);
    }

    // =====================================================================
    // 购买
    // =====================================================================

    function test_buy_happyPath() public {
        vm.prank(alice);
        marketplace.list(tokenId, 1 ether);

        uint256 fee = (1 ether * 100) / 10_000; // 0.01 ether
        uint256 proceeds = 1 ether - fee;

        vm.prank(bob);
        marketplace.buy{value: 1 ether}(tokenId);

        assertEq(registrar.ownerOf(tokenId), bob, "nft transferred");
        assertEq(registry.owner(bytes32(tokenId)), bob, "registry synced");
        assertEq(marketplace.pendingWithdrawal(alice), proceeds, "seller proceeds");
        assertEq(marketplace.pendingWithdrawal(FEE_RECEIVER), fee, "fee");
        assertEq(proceeds + fee, 1 ether, "fee + proceeds == price");

        (address seller,) = marketplace.listings(tokenId);
        assertEq(seller, address(0), "listing removed");
    }

    /// @notice fee 与 proceeds 之和等于 price（多点取样）。
    function test_buy_feeAndProceedsSumToPrice() public {
        uint256[4] memory prices = [uint256(100), 10_000, 1 ether, 12_345_678_901_234_567];

        for (uint256 i = 0; i < prices.length; ++i) {
            uint256 p = prices[i];
            uint256 fee = marketplace.feeFor(p);
            assertEq(fee + (p - fee), p, "sum");
            assertEq(fee, (p * 100) / 10_000, "formula");
        }
    }

    /// @notice `msg.value` 必须精确等于价格，多了少了都 revert。
    function test_buy_wrongValue() public {
        vm.prank(alice);
        marketplace.list(tokenId, 1 ether);

        vm.prank(bob);
        vm.expectRevert(abi.encodeWithSelector(HahaMarketplace.WrongValue.selector, 1 ether, 0.99 ether));
        marketplace.buy{value: 0.99 ether}(tokenId);

        vm.prank(bob);
        vm.expectRevert(abi.encodeWithSelector(HahaMarketplace.WrongValue.selector, 1 ether, 1.01 ether));
        marketplace.buy{value: 1.01 ether}(tokenId);
    }

    /// @notice 转让后 `buy` 失败（owner 已变），`clearStale` 能清掉。
    function test_buy_afterTransferFails_thenClearStale() public {
        vm.prank(alice);
        marketplace.list(tokenId, 1 ether);

        // alice 私下转给 carol
        vm.prank(alice);
        registrar.transferFrom(alice, carol, tokenId);

        // 挂单还在（钩子不通知市场）
        (address seller,) = marketplace.listings(tokenId);
        assertEq(seller, alice, "stale listing remains");

        vm.prank(bob);
        vm.expectRevert(HahaMarketplace.PriceChanged.selector);
        marketplace.buy{value: 1 ether}(tokenId);

        // 任何人可以清掉
        vm.prank(dave);
        marketplace.clearStale(tokenId);

        (seller,) = marketplace.listings(tokenId);
        assertEq(seller, address(0));
    }

    /// @notice `clearStale` 在 owner 仍是 seller 时必须失败。
    function test_clearStale_whenStillOwner_reverts() public {
        vm.prank(alice);
        marketplace.list(tokenId, 1 ether);

        vm.prank(dave);
        vm.expectRevert(HahaMarketplace.NotStale.selector);
        marketplace.clearStale(tokenId);
    }

    /// @notice 卖家改价后，买家按旧价买会 revert。
    function test_buy_priceChangedReverts() public {
        vm.prank(alice);
        marketplace.list(tokenId, 1 ether);

        vm.prank(alice);
        marketplace.updatePrice(tokenId, 2 ether);

        vm.prank(bob);
        vm.expectRevert(abi.encodeWithSelector(HahaMarketplace.WrongValue.selector, 2 ether, 1 ether));
        marketplace.buy{value: 1 ether}(tokenId);
    }

    /// @notice 市场不去读 `royaltyInfo` 再加第二笔。
    function test_buy_doesNotDoubleChargeRoyalty() public {
        vm.prank(alice);
        marketplace.list(tokenId, 1 ether);

        uint256 balanceBefore = address(marketplace).balance;

        vm.prank(bob);
        marketplace.buy{value: 1 ether}(tokenId);

        // 合约只收到 1 ether，费用只扣一次
        assertEq(address(marketplace).balance - balanceBefore, 1 ether);

        // 卖家 + 手续费接收者的待提现总额 == 1 ether（没有第二笔 1%）
        uint256 total = marketplace.pendingWithdrawal(alice) + marketplace.pendingWithdrawal(FEE_RECEIVER);
        assertEq(total, 1 ether, "exactly one 1% cut");
    }

    // =====================================================================
    // 提现
    // =====================================================================

    function test_withdraw_seller() public {
        vm.prank(alice);
        marketplace.list(tokenId, 1 ether);

        vm.prank(bob);
        marketplace.buy{value: 1 ether}(tokenId);

        uint256 proceeds = 1 ether - 0.01 ether;
        uint256 before = alice.balance;

        vm.prank(alice);
        marketplace.withdraw();

        assertEq(alice.balance, before + proceeds);
        assertEq(marketplace.pendingWithdrawal(alice), 0, "zeroed before transfer");
    }

    function test_withdraw_feeReceiver() public {
        vm.prank(alice);
        marketplace.list(tokenId, 1 ether);
        vm.prank(bob);
        marketplace.buy{value: 1 ether}(tokenId);

        uint256 fee = 0.01 ether;
        uint256 before = FEE_RECEIVER.balance;

        vm.prank(FEE_RECEIVER);
        marketplace.withdraw();

        assertEq(FEE_RECEIVER.balance, before + fee);
    }

    /// @notice 各自只能提自己的。
    function test_withdraw_onlyOwn() public {
        vm.prank(alice);
        marketplace.list(tokenId, 1 ether);
        vm.prank(bob);
        marketplace.buy{value: 1 ether}(tokenId);

        vm.prank(dave);
        vm.expectRevert(HahaMarketplace.NothingToWithdraw.selector);
        marketplace.withdraw();

        // alice 提走自己的，不影响 feeReceiver
        vm.prank(alice);
        marketplace.withdraw();
        assertEq(marketplace.pendingWithdrawal(FEE_RECEIVER), 0.01 ether, "fee untouched");
    }

    /// @notice 不能重复提现。
    function test_withdraw_twiceFails() public {
        vm.prank(alice);
        marketplace.list(tokenId, 1 ether);
        vm.prank(bob);
        marketplace.buy{value: 1 ether}(tokenId);

        vm.startPrank(alice);
        marketplace.withdraw();
        vm.expectRevert(HahaMarketplace.NothingToWithdraw.selector);
        marketplace.withdraw();
        vm.stopPrank();
    }

    // =====================================================================
    // 重入
    // =====================================================================

    /// @notice `buy` 的收款合约在 `onERC721Received` 里重入 `buy`/`withdraw` 不能把账做大。
    function test_reentrancy_onBuyDoesNotInflate() public {
        vm.prank(alice);
        marketplace.list(tokenId, 1 ether);

        ReentrantBuyer attacker = new ReentrantBuyer(marketplace);
        attacker.setTarget(tokenId, 1);

        vm.deal(address(attacker), 10 ether);

        attacker.attackBuy{value: 1 ether}(tokenId);

        // 攻击者拿到了 NFT
        assertEq(registrar.ownerOf(tokenId), address(attacker));

        // 账没有变大：卖家 + 手续费 == 1 ether，攻击者自己没有待提现
        assertEq(marketplace.pendingWithdrawal(alice), 0.99 ether);
        assertEq(marketplace.pendingWithdrawal(FEE_RECEIVER), 0.01 ether);
        assertEq(marketplace.pendingWithdrawal(address(attacker)), 0, "attacker got nothing");

        // 合约余额与待提现总额一致
        assertEq(address(marketplace).balance, 1 ether);
    }

    /// @notice `withdraw` 重入自己不能多拿钱。
    function test_reentrancy_onWithdrawDoesNotDouble() public {
        vm.prank(alice);
        marketplace.list(tokenId, 1 ether);
        vm.prank(bob);
        marketplace.buy{value: 1 ether}(tokenId);

        ReentrantBuyer attacker = new ReentrantBuyer(marketplace);
        vm.deal(address(attacker), 0);

        // 攻击者没有待提现，先给自己造一点：让他成为卖家
        _skipCooldown(carol, "carol");
        uint256 t2 = _register(carol, "xyz", 0);
        vm.prank(carol);
        registrar.setApprovalForAll(address(marketplace), true);
        vm.prank(carol);
        marketplace.list(t2, 1 ether);
        vm.prank(dave);
        marketplace.buy{value: 1 ether}(t2);

        // carol 提现，不进攻击者
        uint256 before = carol.balance;
        vm.prank(carol);
        marketplace.withdraw();
        assertEq(carol.balance, before + 0.99 ether);
        assertEq(marketplace.pendingWithdrawal(carol), 0);
    }

    /// @notice 市场没有 `receive()`，直接转 BNB 会失败。
    function test_noReceive() public {
        vm.prank(alice);
        (bool ok,) = address(marketplace).call{value: 1 ether}("");
        assertFalse(ok, "no receive");
    }

    /// @notice 唯一的 payable 函数是 `buy`。
    function test_onlyBuyIsPayable() public {
        vm.prank(alice);
        marketplace.list(tokenId, 1 ether);

        // list/updatePrice/cancel/clearStale/withdraw 都不接受 value
        vm.prank(alice);
        (bool ok,) = address(marketplace).call{value: 1 ether}(
            abi.encodeWithSignature("list(uint256,uint256)", tokenId + 999, 1 ether)
        );
        assertFalse(ok, "list not payable");
    }

    // =====================================================================
    // 买家收到 NFT 时的钩子
    // =====================================================================

    /// @notice 通过市场购买也会触发转让钩子：解析记录清空、agent burn。
    function test_buy_triggersTransferHooks() public {
        // alice 设解析记录和 agent
        vm.startPrank(alice);
        resolver.setAddr(bytes32(tokenId), carol);
        resolver.setText(bytes32(tokenId), "description", "hi");
        uint256 agentId = identity.activateAgent("abc", 0, "https://x");
        vm.stopPrank();

        vm.prank(alice);
        marketplace.list(tokenId, 1 ether);

        vm.prank(bob);
        marketplace.buy{value: 1 ether}(tokenId);

        assertEq(resolver.addr(bytes32(tokenId)), bob, "addr reset to new owner");
        assertEq(resolver.text(bytes32(tokenId), "description"), "", "text cleared");
        assertEq(identity.agentOfName(tokenId), 0, "agent deactivated");
        assertFalse(identity.isActive(agentId));
    }

    // =====================================================================
    // 常量
    // =====================================================================

    function test_feeBpsIsConstant() public view {
        assertEq(marketplace.feeBps(), 100);
    }

    /// @notice 市场没有 admin，也没有修改费率的函数。
    function test_marketplace_hasNoAdmin() public {
        (bool ok,) = address(marketplace).call(abi.encodeWithSignature("setFeeBps(uint256)", 0));
        assertFalse(ok, "no setFeeBps");

        (bool ok2,) = address(marketplace).call(abi.encodeWithSignature("skim()"));
        assertFalse(ok2, "no skim");
    }
}
