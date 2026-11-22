// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Base64} from "@openzeppelin/contracts/utils/Base64.sol";
import {Strings} from "@openzeppelin/contracts/utils/Strings.sol";
import {HahaSvg} from "./libraries/HahaSvg.sol";
import {HahaConstants} from "./libraries/HahaConstants.sol";

contract HahaMetadata {
    using Strings for uint256;


    error InvalidTld(uint8 tld);


    uint256 private constant MAX_FONT_SIZE = 96;

    uint256 private constant FONT_NUMERATOR = 42000;

    uint256 private constant FONT_DENOMINATOR_PER_CHAR = 58;

    uint256 private constant BASELINE_OFFSET = 250;

    uint256 private constant BASELINE_SCALE = 35;


    function build(string calldata label, uint8 tld) external pure returns (string memory) {
        (uint256 fsz, uint256 y) = fontSizeAndBaseline(bytes(label).length + 5);
        string memory svg = buildSvg(label, tld, fsz, y);
        return buildJson(label, tld, svg);
    }

    function buildSvgOnly(string calldata label, uint8 tld) external pure returns (string memory) {
        (uint256 fsz, uint256 y) = fontSizeAndBaseline(bytes(label).length + 5);
        return buildSvg(label, tld, fsz, y);
    }

    function buildJsonFor(string calldata label, uint8 tld) external pure returns (string memory) {
        (uint256 fsz, uint256 y) = fontSizeAndBaseline(bytes(label).length + 5);
        return buildJson(label, tld, buildSvg(label, tld, fsz, y));
    }


    function fontSizeAndBaseline(uint256 n) internal pure returns (uint256 fsz, uint256 y) {
        unchecked {
            fsz = FONT_NUMERATOR / (FONT_DENOMINATOR_PER_CHAR * n);
            if (fsz > MAX_FONT_SIZE) fsz = MAX_FONT_SIZE;

            uint256 num = fsz * BASELINE_SCALE;
            uint256 q = num / 100;
            uint256 r = num % 100;

            if (r > 50 || (r == 50 && (q % 2 == 1))) {
                q = q + 1;
            }
            y = BASELINE_OFFSET + q;
        }
    }


    function buildSvg(string calldata label, uint8 tld, uint256 fsz, uint256 y)
        internal
        pure
        returns (string memory)
    {
        return string.concat(
            HahaSvg.PREFIX,
            y.toString(),
            HahaSvg.MID,
            fsz.toString(),
            HahaSvg.NAME_OPEN,
            label,
            ".",
            _tldOf(tld),
            HahaSvg.SUFFIX
        );
    }

    function _tldOf(uint8 tld) private pure returns (string memory) {
        if (tld == HahaConstants.TLD_HAHA) return "haha";
        if (tld == HahaConstants.TLD_MEME) return "meme";
        revert InvalidTld(tld);
    }


    function buildJson(string calldata label, uint8 tld, string memory svg)
        internal
        pure
        returns (string memory)
    {
        string memory tldStr = _tldOf(tld);
        string memory fullName = string.concat(label, ".", tldStr);
        string memory image = string.concat("data:image/svg+xml;base64,", Base64.encode(bytes(svg)));

        bytes memory json = abi.encodePacked(
            '{"name":"',
            fullName,
            '","description":"haha.meme agent identity for ',
            fullName,
            '","image":"',
            image,
            '","attributes":[{"trait_type":"TLD","value":"',
            tldStr,
            '"},{"trait_type":"Length","display_type":"number","value":',
            uint256(bytes(label).length).toString(),
            "}]}"
        );

        return string.concat("data:application/json;base64,", Base64.encode(json));
    }
}
