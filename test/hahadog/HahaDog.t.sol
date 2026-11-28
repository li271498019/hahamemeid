// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {IERC2981} from "@openzeppelin/contracts/interfaces/IERC2981.sol";
import {IERC721} from "@openzeppelin/contracts/token/ERC721/IERC721.sol";

import {HahaDogTestBase} from "./HahaDogTestBase.sol";
import {HahaDog} from "src/hahadog/HahaDog.sol";

contract HahaDogTest is HahaDogTestBase {
    function test_mint_aiOnly_getsOne() public {
        uint256 id = _mint(alice, 1);
        assertEq(id, 1);
        assertEq(dog.ownerOf(1), alice);
        (uint256 allowed, uint256 used) = dog.quotaOf(alice);
        assertEq(allowed, 1);
        assertEq(used, 1);
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(HahaDog.QuotaExceeded.selector, 1, 1));
        dog.mint(1);
    }

    function test_mint_aiAndHahaId_getsTwo() public {
        _register(alice, "alicedog", 0);
        _mint(alice, 2);
        assertEq(dog.balanceOf(alice), 2);
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(HahaDog.QuotaExceeded.selector, 2, 2));
        dog.mint(1);
    }

    function test_mint_twoWithoutHahaId_reverts() public {
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(HahaDog.QuotaExceeded.selector, 1, 0));
        dog.mint(2);
    }

    function test_mint_noAi_reverts() public {
        vm.prank(eve);
        vm.expectRevert(HahaDog.AiRequired.selector);
        dog.mint(1);
    }

    function test_mint_hahaIdWithoutAi_reverts() public {
        uint256 nameId = _register(alice, "alicedog", 0);
        vm.prank(alice);
        registrar.transferFrom(alice, eve, nameId);
        assertEq(registrar.balanceOf(eve), 1);
        vm.prank(eve);
        vm.expectRevert(HahaDog.AiRequired.selector);
        dog.mint(1);
    }

    function test_mint_badQuantity() public {
        vm.startPrank(alice);
        vm.expectRevert(HahaDog.BadQuantity.selector);
        dog.mint(0);
        vm.expectRevert(HahaDog.BadQuantity.selector);
        dog.mint(3);
        vm.stopPrank();
    }

    function test_quota_hahaIdLaterAddsOne() public {
        _mint(alice, 1);
        _register(alice, "alicedog", 0);
        _mint(alice, 1);
        assertEq(dog.balanceOf(alice), 2);
    }

    function test_quota_boundToAi_transfersNeverAdd() public {
        uint256 nameId = _register(alice, "alicedog", 0);
        _mint(alice, 2);
        vm.startPrank(alice);
        dog.transferFrom(alice, bob, 1);
        dog.transferFrom(alice, bob, 2);
        registrar.transferFrom(alice, bob, nameId);
        vm.stopPrank();
        _skipCooldown(alice, "alice");
        _register(alice, "alicedog2", 0);
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(HahaDog.QuotaExceeded.selector, 2, 2));
        dog.mint(1);
        _mint(bob, 2);
        assertEq(dog.balanceOf(bob), 4);
        vm.prank(bob);
        vm.expectRevert(abi.encodeWithSelector(HahaDog.QuotaExceeded.selector, 2, 2));
        dog.mint(1);
    }

    function test_quota_countedPerAiOnly() public {
        _register(alice, "alicedog", 0);
        (uint256 allowed, uint256 used) = dog.quotaOf(alice);
        assertEq(allowed, 2);
        assertEq(used, 0);
        _mint(alice, 1);
        assertEq(dog.mintedByAi(keccak256(bytes("alice"))), 1);
        (, used) = dog.quotaOf(alice);
        assertEq(used, 1);

        _giveAi(alice, "alice2");
        (allowed, used) = dog.quotaOf(alice);
        assertEq(allowed, 2);
        assertEq(used, 0);
        _mint(alice, 2);
        assertEq(dog.balanceOf(alice), 3);
        assertEq(dog.mintedByAi(keccak256(bytes("alice"))), 1);
        assertEq(dog.mintedByAi(keccak256(bytes("alice2"))), 2);
    }

    function test_quotaOf_noAi() public view {
        (uint256 allowed, uint256 used) = dog.quotaOf(address(0xBEEF));
        assertEq(allowed, 0);
        assertEq(used, 0);
    }

    function test_supplyCap() public {
        _register(alice, "alicedog", 0);
        _setTotalSupply(9999);
        vm.prank(alice);
        vm.expectRevert(HahaDog.SoldOut.selector);
        dog.mint(2);
        _mint(alice, 1);
        assertEq(dog.totalSupply(), 10_000);
        assertEq(dog.ownerOf(10_000), alice);
        vm.prank(bob);
        vm.expectRevert(HahaDog.SoldOut.selector);
        dog.mint(1);
    }

    function test_generating_untilTargetBlockIsMined() public {
        uint256 n = vm.getBlockNumber();
        _mint(alice, 1);
        for (uint256 b = n; b <= n + 4; ++b) {
            _rollTo(b);
            assertEq(dog.statusOf(1), dog.STATUS_GENERATING());
            assertEq(dog.seedOf(1), bytes32(0));
            assertEq(dog.tokenURI(1), renderer.tokenURI(1, bytes32(0), 0, 0));
        }
    }

    function test_ready_atTargetPlusOne_withoutAnyTx() public {
        uint256 n = vm.getBlockNumber();
        _mint(alice, 1);
        _rollTo(n + 5);
        assertEq(dog.statusOf(1), dog.STATUS_READY());
        bytes32 seed = _expectedSeed(1, n, 0);
        assertEq(dog.seedOf(1), seed);
        assertEq(dog.tokenURI(1), renderer.tokenURI(1, seed, 0, 1));
        (uint256 commitBlock, uint256 targetBlock, uint256 rerolls, uint8 status, bytes32 s) = dog.dogOf(1);
        assertEq(commitBlock, n);
        assertEq(targetBlock, n + 4);
        assertEq(rerolls, 0);
        assertEq(status, 2);
        assertEq(s, seed);
    }

    function test_seed_isFixedAtCommit_sameAcrossBlocks() public {
        uint256 n = vm.getBlockNumber();
        _mint(alice, 1);
        _rollTo(n + 5);
        bytes32 s1 = dog.seedOf(1);
        _rollTo(n + 200);
        assertEq(dog.seedOf(1), s1);
    }

    function test_history_extendsWindow_thenStalled() public {
        uint256 n = vm.getBlockNumber();
        _mint(alice, 1);
        _rollTo(n + 4 + 257);
        assertEq(dog.statusOf(1), dog.STATUS_STALLED());
        assertEq(dog.tokenURI(1), renderer.tokenURI(1, bytes32(0), 0, 0));
        _setHistory(n + 4);
        assertEq(dog.statusOf(1), dog.STATUS_READY());
        assertEq(dog.seedOf(1), _expectedSeed(1, n, 0));
        vm.roll(n + 4 + HISTORY_WINDOW);
        assertEq(dog.seedOf(1), _expectedSeed(1, n, 0));
        vm.roll(n + 4 + HISTORY_WINDOW + 1);
        assertEq(dog.statusOf(1), dog.STATUS_STALLED());
        assertEq(dog.seedOf(1), bytes32(0));
    }

    function test_noHistoryContract_stallsAfter256() public {
        HahaDog d2 = new HahaDog(address(renderer), address(ai), address(registrar), FEE_RECEIVER, address(0));
        uint256 n = vm.getBlockNumber();
        vm.prank(alice);
        d2.mint(1);
        _setHistory(n + 4);
        _rollTo(n + 4 + 256);
        assertEq(d2.statusOf(1), 2);
        _rollTo(n + 4 + 257);
        assertEq(d2.statusOf(1), 3);
    }

    function test_snapshot_publicAndPermanent() public {
        uint256 n = vm.getBlockNumber();
        _mint(alice, 1);
        uint256[] memory ids = new uint256[](1);
        ids[0] = 1;
        assertEq(dog.snapshot(ids), 0);
        _rollTo(n + 5);
        assertTrue(dog.needsSnapshot(1));
        vm.prank(eve);
        assertEq(dog.snapshot(ids), 1);
        assertEq(dog.snapshots(n + 4), _hashFor(n + 4));
        assertFalse(dog.needsSnapshot(1));
        assertEq(dog.snapshot(ids), 0);
        vm.roll(n + 100_000);
        assertEq(dog.statusOf(1), dog.STATUS_READY());
        assertEq(dog.seedOf(1), _expectedSeed(1, n, 0));
    }

    function test_snapshot_fromHistoryAfter256() public {
        uint256 n = vm.getBlockNumber();
        _mint(alice, 1);
        _rollTo(n + 2000);
        _setHistory(n + 4);
        uint256[] memory ids = new uint256[](1);
        ids[0] = 1;
        assertEq(dog.snapshot(ids), 1);
        vm.store(HISTORY, bytes32((n + 4) % HISTORY_WINDOW), bytes32(0));
        vm.roll(n + 50_000);
        assertEq(dog.seedOf(1), _expectedSeed(1, n, 0));
    }

    function test_autoSnapshot_onTransfer() public {
        uint256 n = vm.getBlockNumber();
        _mint(alice, 1);
        _rollTo(n + 6);
        vm.prank(alice);
        dog.transferFrom(alice, bob, 1);
        assertEq(dog.snapshots(n + 4), _hashFor(n + 4));
    }

    function test_autoSnapshot_queueOnMintAndReroll() public {
        uint256 n = vm.getBlockNumber();
        _mint(alice, 1);
        _rollTo(n + 5);
        _mint(bob, 1);
        assertEq(dog.snapshots(n + 4), _hashFor(n + 4));
        assertEq(dog.queueHead(), 1);
        _rollTo(n + 10);
        vm.prank(alice);
        dog.reroll(1);
        assertEq(dog.snapshots(n + 9), _hashFor(n + 9));
    }

    function test_processQueue_public_skipsStale() public {
        uint256 n = vm.getBlockNumber();
        _mint(alice, 1);
        vm.prank(alice);
        dog.reroll(1);
        _rollTo(n + 5);
        assertEq(dog.queueLength(), 2);
        vm.prank(eve);
        assertEq(dog.processQueue(10), 2);
        assertEq(dog.snapshots(n + 4), _hashFor(n + 4));
    }

    function test_processQueue_stopsAtUndueEntry() public {
        uint256 n = vm.getBlockNumber();
        _mint(alice, 1);
        _rollTo(n + 3);
        _mint(bob, 1);
        _rollTo(n + 5);
        assertEq(dog.processQueue(10), 1);
        assertEq(dog.snapshots(n + 4), _hashFor(n + 4));
        assertEq(dog.snapshots(n + 7), bytes32(0));
    }

    function test_reroll_onlyHolder() public {
        _mint(alice, 1);
        vm.prank(bob);
        vm.expectRevert(HahaDog.NotTokenOwner.selector);
        dog.reroll(1);
    }

    function test_reroll_free_discardsOldImage_newSeed() public {
        uint256 n = vm.getBlockNumber();
        _mint(alice, 1);
        _rollTo(n + 5);
        bytes32 oldSeed = dog.seedOf(1);
        vm.prank(alice);
        dog.reroll(1);
        assertEq(dog.rerollsOf(1), 1);
        assertEq(dog.statusOf(1), dog.STATUS_GENERATING());
        assertEq(dog.seedOf(1), bytes32(0));
        assertEq(dog.tokenURI(1), renderer.tokenURI(1, bytes32(0), 1, 0));
        _rollTo(n + 10);
        bytes32 newSeed = dog.seedOf(1);
        assertEq(newSeed, _expectedSeed(1, n + 5, 1));
        assertTrue(newSeed != oldSeed);
        assertEq(dog.tokenURI(1), renderer.tokenURI(1, newSeed, 1, 1));
    }

    function test_reroll_unlimited_anyState() public {
        uint256 n = vm.getBlockNumber();
        _mint(alice, 1);
        vm.startPrank(alice);
        for (uint256 i; i < 12; ++i) {
            dog.reroll(1);
        }
        vm.stopPrank();
        assertEq(dog.rerollsOf(1), 12);
        _rollTo(n + 5);
        assertEq(dog.seedOf(1), _expectedSeed(1, n, 12));
    }

    function test_reroll_recoversStalledToken() public {
        uint256 n = vm.getBlockNumber();
        _mint(alice, 1);
        _rollTo(n + 4 + HISTORY_WINDOW + 10);
        assertEq(dog.statusOf(1), dog.STATUS_STALLED());
        uint256 m = vm.getBlockNumber();
        vm.prank(alice);
        dog.reroll(1);
        _rollTo(m + 5);
        assertEq(dog.statusOf(1), dog.STATUS_READY());
        assertEq(dog.seedOf(1), _expectedSeed(1, m, 1));
    }

    function test_reroll_notPayable() public {
        _mint(alice, 1);
        vm.prank(alice);
        (bool ok,) = address(dog).call{value: 1 wei}(abi.encodeCall(HahaDog.reroll, (1)));
        assertFalse(ok);
    }

    function test_tokenURI_nonexistent_reverts() public {
        vm.expectRevert();
        dog.tokenURI(1);
    }

    function test_royalty_onePercent_toFeeReceiver() public view {
        (address r, uint256 amt) = dog.royaltyInfo(1, 1 ether);
        assertEq(r, FEE_RECEIVER);
        assertEq(amt, 0.01 ether);
        assertTrue(dog.supportsInterface(type(IERC2981).interfaceId));
        assertTrue(dog.supportsInterface(type(IERC721).interfaceId));
    }

    function test_metadata() public view {
        assertEq(dog.name(), "Haha Dog");
        assertEq(dog.symbol(), "HAHADOG");
        assertEq(dog.MAX_SUPPLY(), 10_000);
    }

    function test_gas_report() public {
        uint256 n = vm.getBlockNumber();
        _register(alice, "alicedog", 0);
        uint256 g = gasleft();
        vm.prank(bob);
        dog.mint(1);
        emit log_named_uint("mint(1) cold", g - gasleft());
        g = gasleft();
        vm.prank(alice);
        dog.mint(2);
        emit log_named_uint("mint(2)", g - gasleft());
        _rollTo(n + 5);
        g = gasleft();
        vm.prank(carol);
        dog.mint(1);
        emit log_named_uint("mint(1) + auto snapshot of 3 queued", g - gasleft());
        g = gasleft();
        vm.prank(alice);
        dog.reroll(2);
        emit log_named_uint("reroll", g - gasleft());
        g = gasleft();
        vm.prank(bob);
        dog.transferFrom(bob, dave, 1);
        emit log_named_uint("transfer (token already snapshotted)", g - gasleft());
        _rollTo(n + 20);
        uint256[] memory ids = new uint256[](1);
        ids[0] = 4;
        g = gasleft();
        dog.snapshot(ids);
        emit log_named_uint("snapshot(1 token)", g - gasleft());
        g = gasleft();
        dog.tokenURI(1);
        emit log_named_uint("tokenURI ready", g - gasleft());
        vm.prank(alice);
        dog.reroll(3);
        g = gasleft();
        dog.tokenURI(3);
        emit log_named_uint("tokenURI generating", g - gasleft());
    }
}
