// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {HahaDogTestBase} from "./HahaDogTestBase.sol";
import {HahaDogMarket} from "src/hahadog/HahaDogMarket.sol";

contract RejectingSeller {
    receive() external payable {
        revert();
    }
}

contract HahaDogMarketTest is HahaDogTestBase {
    uint256 internal n0;

    function setUp() public override {
        super.setUp();
        n0 = vm.getBlockNumber();
        _mint(alice, 1);
        vm.prank(alice);
        dog.setApprovalForAll(address(market), true);
    }

    function _ready() internal {
        _rollTo(n0 + 5);
    }

    function test_list_requiresReady() public {
        vm.prank(alice);
        vm.expectRevert(HahaDogMarket.NotReady.selector);
        market.list(1, 1 ether);
        _ready();
        vm.prank(alice);
        market.list(1, 1 ether);
        (address seller, uint256 price, uint256 rerolls) = market.listings(1);
        assertEq(seller, alice);
        assertEq(price, 1 ether);
        assertEq(rerolls, 0);
        assertTrue(market.isValid(1));
    }

    function test_list_requiresOwnerApprovalAndPrice() public {
        _ready();
        vm.prank(bob);
        vm.expectRevert(HahaDogMarket.NotOwner.selector);
        market.list(1, 1 ether);
        vm.prank(alice);
        vm.expectRevert(HahaDogMarket.PriceTooLow.selector);
        market.list(1, 99);
        vm.prank(alice);
        dog.setApprovalForAll(address(market), false);
        vm.prank(alice);
        vm.expectRevert(HahaDogMarket.NotApproved.selector);
        market.list(1, 1 ether);
    }

    function test_buy_feeOnePercent_pullPayments() public {
        _ready();
        vm.prank(alice);
        market.list(1, 2 ether);
        vm.prank(bob);
        market.buy{value: 2 ether}(1);
        assertEq(dog.ownerOf(1), bob);
        assertEq(market.pendingWithdrawal(alice), 1.98 ether);
        assertEq(market.pendingWithdrawal(FEE_RECEIVER), 0.02 ether);
        uint256 before = alice.balance;
        vm.prank(alice);
        market.withdraw();
        assertEq(alice.balance, before + 1.98 ether);
        vm.prank(FEE_RECEIVER);
        market.withdraw();
        assertEq(FEE_RECEIVER.balance, 0.02 ether);
        vm.prank(alice);
        vm.expectRevert(HahaDogMarket.NothingToWithdraw.selector);
        market.withdraw();
    }

    function test_buy_wrongValue() public {
        _ready();
        vm.prank(alice);
        market.list(1, 1 ether);
        vm.prank(bob);
        vm.expectRevert(abi.encodeWithSelector(HahaDogMarket.WrongValue.selector, 1 ether, 0.5 ether));
        market.buy{value: 0.5 ether}(1);
    }

    function test_buy_refusedAfterRerollWhileGenerating() public {
        _ready();
        vm.prank(alice);
        market.list(1, 1 ether);
        vm.prank(alice);
        dog.reroll(1);
        assertFalse(market.isValid(1));
        vm.prank(bob);
        vm.expectRevert(HahaDogMarket.NotReady.selector);
        market.buy{value: 1 ether}(1);
    }

    function test_buy_refusedAfterRerollOnceNewImageReady() public {
        _ready();
        vm.prank(alice);
        market.list(1, 1 ether);
        vm.prank(alice);
        dog.reroll(1);
        _rollTo(vm.getBlockNumber() + 5);
        vm.prank(bob);
        vm.expectRevert(HahaDogMarket.PriceChanged.selector);
        market.buy{value: 1 ether}(1);
        vm.prank(eve);
        market.clearStale(1);
        (address seller,,) = market.listings(1);
        assertEq(seller, address(0));
    }

    function test_buy_refusedWhenStalled() public {
        _ready();
        vm.prank(alice);
        market.list(1, 1 ether);
        vm.roll(n0 + 4 + HISTORY_WINDOW + 1);
        vm.prank(bob);
        vm.expectRevert(HahaDogMarket.NotReady.selector);
        market.buy{value: 1 ether}(1);
    }

    function test_buy_snapshotsOnTransfer() public {
        _ready();
        vm.prank(alice);
        market.list(1, 1 ether);
        vm.prank(bob);
        market.buy{value: 1 ether}(1);
        assertEq(dog.snapshots(n0 + 4), _hashFor(n0 + 4));
    }

    function test_cancel_updatePrice_clearStale() public {
        _ready();
        vm.startPrank(alice);
        market.list(1, 1 ether);
        market.updatePrice(1, 3 ether);
        vm.stopPrank();
        (, uint256 price,) = market.listings(1);
        assertEq(price, 3 ether);
        vm.prank(bob);
        vm.expectRevert(HahaDogMarket.NotSeller.selector);
        market.cancel(1);
        vm.prank(eve);
        vm.expectRevert(HahaDogMarket.NotStale.selector);
        market.clearStale(1);
        vm.prank(alice);
        dog.transferFrom(alice, carol, 1);
        vm.prank(bob);
        vm.expectRevert(HahaDogMarket.PriceChanged.selector);
        market.buy{value: 3 ether}(1);
        market.clearStale(1);
        vm.prank(carol);
        dog.setApprovalForAll(address(market), true);
        vm.prank(carol);
        market.list(1, 1 ether);
        vm.prank(carol);
        market.cancel(1);
        vm.prank(carol);
        vm.expectRevert(HahaDogMarket.NotListed.selector);
        market.cancel(1);
    }

    function test_withdraw_failingReceiverReverts() public {
        RejectingSeller rs = new RejectingSeller();
        _giveAi(address(rs), "rejector");
        _ready();
        vm.prank(alice);
        market.list(1, 1 ether);
        vm.prank(bob);
        market.buy{value: 1 ether}(1);
        vm.prank(address(rs));
        vm.expectRevert(HahaDogMarket.NothingToWithdraw.selector);
        market.withdraw();
    }

    function test_constructor_zeroAddress() public {
        vm.expectRevert(HahaDogMarket.ZeroAddress.selector);
        new HahaDogMarket(address(0), FEE_RECEIVER);
    }

    function test_feeBps() public view {
        assertEq(market.feeBps(), 100);
        assertEq(market.feeFor(1 ether), 0.01 ether);
    }
}
