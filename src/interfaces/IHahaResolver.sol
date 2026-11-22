// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

interface IHahaResolver {
    function addr(bytes32 node) external view returns (address);

    function setAddr(bytes32 node, address a) external;

    function text(bytes32 node, string calldata key) external view returns (string memory);

    function setText(bytes32 node, string calldata key, string calldata value) external;

    function clearRecords(bytes32 node) external;

    function setPrimaryName(string calldata label, uint8 tld) external;

    function clearPrimaryName() external;

    function primaryNode(address user) external view returns (bytes32);

    function primaryName(address user) external view returns (string memory fullName);
}
