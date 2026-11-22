// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {HahaConstants} from "./libraries/HahaConstants.sol";

contract HahaNamePolicy {

    error WrongBannedCount(uint256 got, uint256 want);
    error WrongReservedCount(uint256 got, uint256 want);
    error DuplicateBannedHash(uint256 index);
    error DuplicateReservedHash(uint256 index);


    event ListsFrozen(uint256 bannedCount, uint256 reservedCount);


    mapping(bytes32 saltedHash => bool) private _banned;

    mapping(bytes32 labelhash => bool) private _reserved;


    constructor(bytes32[] memory bannedHashes, bytes32[] memory reservedLabelhashes) {
        uint256 bannedLen = bannedHashes.length;
        uint256 reservedLen = reservedLabelhashes.length;

        if (bannedLen != HahaConstants.BANNED_COUNT) {
            revert WrongBannedCount(bannedLen, HahaConstants.BANNED_COUNT);
        }
        if (reservedLen != HahaConstants.RESERVED_COUNT) {
            revert WrongReservedCount(reservedLen, HahaConstants.RESERVED_COUNT);
        }

        unchecked {
            for (uint256 i = 0; i < bannedLen; ++i) {
                bytes32 h = bannedHashes[i];
                if (h == bytes32(0) || _banned[h]) revert DuplicateBannedHash(i);
                _banned[h] = true;
            }
            for (uint256 i = 0; i < reservedLen; ++i) {
                bytes32 h = reservedLabelhashes[i];
                if (h == bytes32(0) || _reserved[h]) revert DuplicateReservedHash(i);
                _reserved[h] = true;
            }
        }

        emit ListsFrozen(bannedLen, reservedLen);
    }


    function isBlacklisted(string calldata label) external view returns (bool) {
        return _banned[keccak256(abi.encodePacked("HAHA_V2", label))];
    }

    function isReserved(string calldata label) external view returns (bool) {
        return _reserved[keccak256(bytes(label))];
    }

    function bannedCount() external pure returns (uint256) {
        return HahaConstants.BANNED_COUNT;
    }

    function reservedCount() external pure returns (uint256) {
        return HahaConstants.RESERVED_COUNT;
    }
}
