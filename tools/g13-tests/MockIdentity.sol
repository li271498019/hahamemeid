// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

/// @notice T10 测试用 HahaAgentIdentity 替身：只实现验证者服务依赖的
/// isAuthorized / ownerOf / tokenURI（另加 setAgent 供测试布署）。
contract MockIdentity {
    mapping(uint256 => address) private _owners;
    mapping(uint256 => string) private _uris;

    function setAgent(uint256 agentId, address owner, string calldata uri) external {
        _owners[agentId] = owner;
        _uris[agentId] = uri;
    }

    function ownerOf(uint256 agentId) external view returns (address) {
        return _owners[agentId];
    }

    function isAuthorized(uint256 agentId, address account) external view returns (bool) {
        return _owners[agentId] == account;
    }

    function tokenURI(uint256 agentId) external view returns (string memory) {
        return _uris[agentId];
    }
}
