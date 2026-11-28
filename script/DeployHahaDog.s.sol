// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Script, console2} from "forge-std/Script.sol";

import {HahaDogModel} from "src/hahadog/HahaDogModel.sol";
import {HahaDogRenderer} from "src/hahadog/HahaDogRenderer.sol";
import {HahaDog} from "src/hahadog/HahaDog.sol";
import {HahaDogMarket} from "src/hahadog/HahaDogMarket.sol";

/// @notice Deploys Model -> Renderer -> HahaDog -> HahaDogMarket. Key: DEPLOYER_PK.
contract DeployHahaDog is Script {
    address internal constant DEFAULT_AI_REGISTRY = 0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F;
    address internal constant DEFAULT_REGISTRAR = 0x43426E37a31AafDaba851858e34B81DC300650F8;
    address internal constant DEFAULT_FEE_RECEIVER = 0x57A76124bC919F7509bEb54924E8448258De90df;
    address internal constant DEFAULT_BLOCK_HISTORY = 0x0000F90827F1C53a10cb7A02335B175320002935;
    bytes32 internal constant WEIGHTS_HASH = 0x1d2239644b5273c4f1925c489d32900a564262bce6597f94a929489cfbe58078;

    function run()
        external
        returns (HahaDogModel model, HahaDogRenderer renderer, HahaDog dog, HahaDogMarket market)
    {
        uint256 pk = vm.envUint("DEPLOYER_PK");
        address aiRegistry = vm.envOr("AI_REGISTRY_ADDRESS", DEFAULT_AI_REGISTRY);
        address registrar = vm.envOr("REGISTRAR_ADDRESS", DEFAULT_REGISTRAR);
        address feeReceiver = vm.envOr("FEE_RECEIVER_ADDRESS", DEFAULT_FEE_RECEIVER);
        address blockHistory = vm.envOr("BLOCK_HISTORY_ADDRESS", DEFAULT_BLOCK_HISTORY);

        require(aiRegistry.code.length > 0, "ai registry has no code");
        require(registrar.code.length > 0, "registrar has no code");
        if (blockHistory != address(0)) require(blockHistory.code.length > 0, "block history has no code");

        vm.startBroadcast(pk);
        model = new HahaDogModel();
        renderer = new HahaDogRenderer(address(model));
        dog = new HahaDog(address(renderer), aiRegistry, registrar, feeReceiver, blockHistory);
        market = new HahaDogMarket(address(dog), feeReceiver);
        vm.stopBroadcast();

        require(keccak256(model.modelData()) == model.MODEL_DATA_HASH(), "model data hash");

        console2.log("weights keccak256");
        console2.logBytes32(WEIGHTS_HASH);
        console2.log("model data keccak256");
        console2.logBytes32(model.MODEL_DATA_HASH());
        console2.log("HahaDogModel   ", address(model));
        console2.log("HahaDogRenderer", address(renderer));
        console2.log("HahaDog        ", address(dog));
        console2.log("HahaDogMarket  ", address(market));
    }
}
