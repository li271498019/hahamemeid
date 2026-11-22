// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

interface IHahaRegistrar {
    function nameParts(uint256 tokenId) external view returns (string memory label, uint8 tld);

    function isMinted(bytes32 node) external view returns (bool);

    function balanceOf(address owner) external view returns (uint256);
}

interface IHahaMetadata {
    function build(string calldata label, uint8 tld) external view returns (string memory);
}

interface IHahaNamePolicy {
    function isBlacklisted(string calldata label) external view returns (bool);

    function isReserved(string calldata label) external view returns (bool);
}

interface IHahaPoints {
    function creditMintReward(address user, bytes32 aiId) external returns (uint256 awarded);

    function balanceOf(bytes32 aiId) external view returns (uint256);

    function earn(bytes32 actionId, address user, bytes32 uniqueKey) external returns (uint256 awarded);
}

interface IHahaGame {
    function pointsContract() external view returns (address);

    function gameId() external view returns (bytes32);

    function scoreOf(uint256 sessionId) external view returns (uint256 score, bool settled);

    function start() external returns (uint256 sessionId);

    function claim(uint256 sessionId) external returns (uint256 awarded);
}

interface IHahaAgentIdentity {
    function deactivate(uint256 nameTokenId) external;

    function agentOfName(uint256 nameTokenId) external view returns (uint256);

    function ownerOf(uint256 agentId) external view returns (address);

    function isActive(uint256 agentId) external view returns (bool);

    function registrar() external view returns (address);

    function isAuthorized(uint256 agentId, address account) external view returns (bool);

    function isAgentOperator(uint256 agentId, address operator) external view returns (bool);

    function generationOf(uint256 agentId) external view returns (uint64);

    function nameGeneration(uint256 nameTokenId) external view returns (uint64);

    function operatorAiIdOf(uint256 agentId) external view returns (bytes32);
}
