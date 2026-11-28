// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

interface IHahaDogModel {
    function generate(bytes32 seed) external pure returns (bytes memory cells, uint8[4] memory picks);
}

interface IHahaDogRenderer {
    function tokenURI(uint256 tokenId, bytes32 seed, uint256 rerolls, uint8 state)
        external
        view
        returns (string memory);
}

interface IHahaDog {
    function statusOf(uint256 tokenId) external view returns (uint8);

    function rerollsOf(uint256 tokenId) external view returns (uint256);
}
