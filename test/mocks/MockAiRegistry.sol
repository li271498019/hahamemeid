// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {IBinanceAiRegistry} from "src/interfaces/IBinanceAiRegistry.sol";

/// @title MockAiRegistry
/// @notice 模拟币安 `.ai` 注册表的四个只读函数，行为与主网实测一致。
///
/// @dev SPEC 12 明确要求：「模拟 `.ai` 的 mock 必须实现第 4 节的四个函数，并且
///      `ownerOf(uint256(keccak256(bytes(handle))))` 与 `handleOf` / `ownerOfHandle` 一致。
///      只 mock `balanceOf` 不算通过。」
///
///      本 mock 严格模拟主网的三个特点：
///      1. tokenId = `uint256(keccak256(bytes(handle)))`，与 `alice` 的实测公式一致。
///      2. 不做归一化：`"Alice"`、`"alice.ai"`、`""` 都查不到。
///      3. 名字 Soulbound：`transferFrom` revert `Soulbound()`，
///         但本 mock 不实现转让，所以直接不提供转让入口，
///         测试「转走 alice 会失败」走真实 fork（见 test/fork/）。
///
///      另外提供几个测试专用的「捣鬼」入口，用来模拟主网可能出现的各种不一致，
///      验证我们的 `aiIdentityOf` 四步校验不会记错账。
contract MockAiRegistry is IBinanceAiRegistry {
    /// @dev handle → owner
    mapping(bytes32 handleHash => address) private _ownerOfHandle;

    /// @dev owner → handle（主网 handleOf 的行为：一个地址返回一个 handle）
    mapping(address owner => string) private _handleOf;

    // ---------------------------------------------------------------------
    // 测试专用
    // ---------------------------------------------------------------------

    /// @notice 给 `owner` 注册一个 handle。
    /// @dev 不做小写转换。传大写进来就是大写，和主网一致。
    function register(string calldata handle, address owner) external {
        bytes32 h = keccak256(bytes(handle));
        _ownerOfHandle[h] = owner;
        _handleOf[owner] = handle;
    }

    /// @notice 直接在 `handleOf` 与 `ownerOfHandle` 之间制造不一致。
    /// @dev 本函数用于测试「第三步/第二步校验失败时不能记错账」。
    /// @param owner 地址
    /// @param handleOfValue 让 `handleOf(owner)` 返回这个值
    /// @param handleOwner 让 `ownerOfHandle(handleOfValue)` 返回这个地址
    function forceHandleOf(address owner, string calldata handleOfValue, address handleOwner) external {
        _handleOf[owner] = handleOfValue;
        if (handleOwner != address(0)) {
            _ownerOfHandle[keccak256(bytes(handleOfValue))] = handleOwner;
        }
    }

    // ---------------------------------------------------------------------
    // IBinanceAiRegistry
    // ---------------------------------------------------------------------

    /// @inheritdoc IBinanceAiRegistry
    function handleOf(address owner) external view returns (string memory) {
        return _handleOf[owner];
    }

    /// @inheritdoc IBinanceAiRegistry
    function ownerOfHandle(string calldata handle) external view returns (address) {
        return _ownerOfHandle[keccak256(bytes(handle))];
    }

    /// @inheritdoc IBinanceAiRegistry
    function ownerOf(uint256 tokenId) external view returns (address) {
        return _ownerOfHandle[bytes32(tokenId)];
    }

    /// @inheritdoc IBinanceAiRegistry
    /// @dev 为了和主网一致：一个地址只承认一个 handle，所以最多为 1。
    function balanceOf(address owner) external view returns (uint256) {
        return bytes(_handleOf[owner]).length == 0 ? 0 : 1;
    }
}
