// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {StdStorage, stdStorage} from "forge-std/StdStorage.sol";

import {HahaTestBase} from "../HahaTestBase.sol";
import {HahaDogModel} from "src/hahadog/HahaDogModel.sol";
import {HahaDogRenderer} from "src/hahadog/HahaDogRenderer.sol";
import {HahaDog} from "src/hahadog/HahaDog.sol";
import {HahaDogMarket} from "src/hahadog/HahaDogMarket.sol";

abstract contract HahaDogTestBase is HahaTestBase {
    using stdStorage for StdStorage;

    address internal constant HISTORY = 0x0000F90827F1C53a10cb7A02335B175320002935;
    bytes internal constant HISTORY_CODE =
        hex"3373fffffffffffffffffffffffffffffffffffffffe14604657602036036042575f35600143038111604257611fff81430311604257611fff9006545f5260205ff35b5f5ffd5b5f35611fff60014303065500";
    uint256 internal constant HISTORY_WINDOW = 8191;

    HahaDogModel internal model;
    HahaDogRenderer internal renderer;
    HahaDog internal dog;
    HahaDogMarket internal market;

    address internal eve = makeAddr("eve");

    function setUp() public virtual override {
        super.setUp();
        vm.roll(1_000_000);
        vm.etch(HISTORY, HISTORY_CODE);
        model = new HahaDogModel();
        renderer = new HahaDogRenderer(address(model));
        dog = new HahaDog(address(renderer), address(ai), address(registrar), FEE_RECEIVER, HISTORY);
        market = new HahaDogMarket(address(dog), FEE_RECEIVER);
        vm.deal(eve, 1000 ether);
    }

    function _hashFor(uint256 blockNumber) internal pure returns (bytes32) {
        return keccak256(abi.encode("block", blockNumber));
    }

    function _rollTo(uint256 n) internal {
        vm.roll(n);
        for (uint256 b = n > 300 ? n - 300 : 0; b < n; ++b) {
            vm.setBlockhash(b, _hashFor(b));
        }
    }

    function _setHistory(uint256 blockNumber) internal {
        vm.store(HISTORY, bytes32(blockNumber % HISTORY_WINDOW), _hashFor(blockNumber));
    }

    function _expectedSeed(uint256 tokenId, uint256 commitBlock, uint256 rerolls) internal pure returns (bytes32) {
        return keccak256(abi.encode(_hashFor(commitBlock + 4), tokenId, rerolls));
    }

    function _mint(address user, uint256 qty) internal returns (uint256 firstId) {
        firstId = dog.totalSupply() + 1;
        vm.prank(user);
        dog.mint(qty);
    }

    function _setTotalSupply(uint256 v) internal {
        stdstore.target(address(dog)).sig("totalSupply()").checked_write(v);
    }
}
