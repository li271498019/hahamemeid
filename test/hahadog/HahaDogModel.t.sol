// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Test} from "forge-std/Test.sol";

import {HahaDogModel} from "src/hahadog/HahaDogModel.sol";
import {HahaDogRenderer} from "src/hahadog/HahaDogRenderer.sol";

contract HahaDogModelTest is Test {
    string internal constant VECTORS = "test/hahadog/fixtures/model-vectors.json";

    HahaDogModel internal model;
    HahaDogRenderer internal renderer;

    function setUp() public {
        model = new HahaDogModel();
        renderer = new HahaDogRenderer(address(model));
    }

    function test_weightsHash_matchesPublished() public view {
        bytes memory w = vm.readFileBinary("haha-dog/model/weights-int8.json");
        assertEq(keccak256(w), 0x1d2239644b5273c4f1925c489d32900a564262bce6597f94a929489cfbe58078);
        bytes memory blob = vm.readFileBinary("haha-dog/reference/model-data.bin");
        assertEq(keccak256(blob), model.MODEL_DATA_HASH());
        assertEq(keccak256(model.modelData()), model.MODEL_DATA_HASH());
    }

    function test_model_matchesPythonVectors_0() public view {
        _checkVectors(0, 110);
    }

    function test_model_matchesPythonVectors_1() public view {
        _checkVectors(110, 220);
    }

    function test_model_matchesPythonVectors_2() public view {
        _checkVectors(220, 316);
    }

    function _checkVectors(uint256 from, uint256 to) internal view {
        string memory json = vm.readFile(VECTORS);
        bytes32[] memory seeds = vm.parseJsonBytes32Array(json, ".seeds");
        bytes[] memory cells = vm.parseJsonBytesArray(json, ".cells");
        uint256[] memory picks = vm.parseJsonUintArray(json, ".picks");
        uint256[] memory traits = vm.parseJsonUintArray(json, ".traits");
        bytes32[] memory svgHashes = vm.parseJsonBytes32Array(json, ".svgHashes");
        assertEq(seeds.length, 316);
        for (uint256 i = from; i < to; ++i) {
            (bytes memory c, uint8[4] memory p) = model.generate(seeds[i]);
            assertEq(keccak256(c), keccak256(cells[i]), "cells");
            assertEq(uint256(p[0]) | uint256(p[1]) << 8 | uint256(p[2]) << 16 | uint256(p[3]) << 24, picks[i], "picks");
            HahaDogRenderer.Dog memory d = renderer.dog(seeds[i]);
            uint256 packed = uint256(d.style) | uint256(d.color) << 8 | uint256(d.head) << 16
                | uint256(d.eyes) << 24 | uint256(d.mouth) << 32 | uint256(d.neck) << 40 | d.score << 48
                | uint256(d.tier) << 56;
            assertEq(packed, traits[i], "traits");
            if (i < 40) assertEq(keccak256(bytes(renderer.svgOf(seeds[i]))), svgHashes[i], "svg");
        }
    }

    function test_renderer_matchesShippedTestVectorSvgs() public view {
        string[5] memory styles = ["scanlines", "sunburst", "stars", "moon", "glitch"];
        string memory tv = vm.readFile("haha-dog/model/test-vectors.json");
        for (uint256 i; i < 16; ++i) {
            string memory k = string.concat(".vectors[", vm.toString(i), "]");
            bytes32 seed = vm.parseJsonBytes32(tv, string.concat(k, ".seed"));
            string memory st = vm.parseJsonString(tv, string.concat(k, ".background.style"));
            uint256 color = vm.parseJsonUint(tv, string.concat(k, ".background.color_index"));
            uint8 style;
            for (uint8 s; s < 5; ++s) {
                if (keccak256(bytes(styles[s])) == keccak256(bytes(st))) style = s;
            }
            string memory file = string.concat("haha-dog/model/test-vectors/tv_", i < 10 ? "0" : "", vm.toString(i), ".svg");
            assertEq(renderer.svgWith(seed, style, uint8(color)), vm.readFile(file));
        }
    }

    function test_tokenURI_matchesPython() public view {
        string memory json = vm.readFile("test/hahadog/fixtures/token-uris.json");
        uint256[] memory ids = vm.parseJsonUintArray(json, ".tokenIds");
        bytes32[] memory seeds = vm.parseJsonBytes32Array(json, ".seeds");
        uint256[] memory rerolls = vm.parseJsonUintArray(json, ".rerolls");
        uint256[] memory states = vm.parseJsonUintArray(json, ".states");
        bytes32[] memory hashes = vm.parseJsonBytes32Array(json, ".hashes");
        assertEq(renderer.tokenURI(ids[1], seeds[1], rerolls[1], uint8(states[1])), vm.parseJsonString(json, ".sampleUri"));
        for (uint256 i; i < ids.length; ++i) {
            assertEq(keccak256(bytes(renderer.tokenURI(ids[i], seeds[i], rerolls[i], uint8(states[i])))), hashes[i]);
        }
    }

    function test_gas_tokenURI() public {
        uint256 g = gasleft();
        renderer.tokenURI(1, keccak256("haha"), 0, 1);
        emit log_named_uint("tokenURI gas", g - gasleft());
        g = gasleft();
        model.generate(keccak256("haha"));
        emit log_named_uint("model.generate gas", g - gasleft());
    }
}
