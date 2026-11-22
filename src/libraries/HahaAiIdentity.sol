// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {IBinanceAiRegistry} from "../interfaces/IBinanceAiRegistry.sol";

library HahaAiIdentity {
    struct Result {
        bytes32 aiId;
        string handle;
        bool ok;
    }

    function aiIdentityOf(IBinanceAiRegistry aiRegistry, address user)
        internal
        view
        returns (Result memory)
    {
        if (user == address(0) || address(aiRegistry).code.length == 0) {
            return Result({aiId: bytes32(0), handle: "", ok: false});
        }

        string memory handle;
        try aiRegistry.handleOf(user) returns (string memory h) {
            handle = h;
        } catch {
            return Result({aiId: bytes32(0), handle: "", ok: false});
        }
        bytes memory handleBytes = bytes(handle);
        if (handleBytes.length == 0) {
            return Result({aiId: bytes32(0), handle: "", ok: false});
        }

        try aiRegistry.ownerOfHandle(handle) returns (address hOwner) {
            if (hOwner != user) {
                return Result({aiId: bytes32(0), handle: handle, ok: false});
            }
        } catch {
            return Result({aiId: bytes32(0), handle: handle, ok: false});
        }

        bytes32 aiId = keccak256(handleBytes);

        try aiRegistry.ownerOf(uint256(aiId)) returns (address tOwner) {
            if (tOwner != user) {
                return Result({aiId: aiId, handle: handle, ok: false});
            }
        } catch {
            return Result({aiId: aiId, handle: handle, ok: false});
        }

        return Result({aiId: aiId, handle: handle, ok: true});
    }
}
