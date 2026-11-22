// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

library HahaNamehash {
    bytes32 internal constant ROOT_NODE = bytes32(0);

    bytes32 internal constant HAHA_NODE = 0xaa5a3a58f7c8841455eecaa0c6a6a0b40ace5681fbb31361a0d45b168179128f;

    bytes32 internal constant MEME_NODE = 0x74df4ab2564a9f9bb6d4b6b77bf4fc02ac80f07bd9e1776d3967578b3fc36be4;

    bytes32 private constant _HAHA_CHECK =
        keccak256(abi.encodePacked(ROOT_NODE, keccak256(bytes("haha"))));
    bytes32 private constant _MEME_CHECK =
        keccak256(abi.encodePacked(ROOT_NODE, keccak256(bytes("meme"))));

    function labelhash(string memory label) internal pure returns (bytes32) {
        return keccak256(bytes(label));
    }

    function namehash(bytes32 parentNode, bytes32 labelHash) internal pure returns (bytes32) {
        return keccak256(abi.encodePacked(parentNode, labelHash));
    }

    function tldNode(uint8 tld) internal pure returns (bytes32) {
        if (tld == 0) return HAHA_NODE;
        if (tld == 1) return MEME_NODE;
        return bytes32(0);
    }

    function isValidLabel(string memory label) internal pure returns (bool) {
        bytes memory b = bytes(label);
        if (b.length == 0) return false;
        unchecked {
            for (uint256 i = 0; i < b.length; ++i) {
                bytes1 c = b[i];
                bool lower = (c >= 0x61 && c <= 0x7a);
                bool digit = (c >= 0x30 && c <= 0x39);
                if (!lower && !digit) return false;
            }
        }
        return true;
    }

    function isLengthInRange(string memory label, uint256 minLen, uint256 maxLen)
        internal
        pure
        returns (bool)
    {
        uint256 n = bytes(label).length;
        return n >= minLen && n <= maxLen;
    }

    function fullName(string memory label, uint8 tld) internal pure returns (string memory) {
        return string.concat(label, tld == 0 ? ".haha" : ".meme");
    }
}
