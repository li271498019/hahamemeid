// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

interface IHahaRegistry {
    function owner(bytes32 node) external view returns (address);

    function resolver(bytes32 node) external view returns (address);

    function recordExists(bytes32 node) external view returns (bool);

    function bootstrap() external;

    function createName(bytes32 tldNode, bytes32 labelhash, address nameOwner) external;

    function syncOwner(bytes32 node, address nameOwner) external;
}
