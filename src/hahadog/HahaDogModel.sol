// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {HahaDogWeights as Wt} from "./HahaDogWeights.sol";

/// @title Haha AI on-chain model
/// @notice int8 neural network 8 -> 64 -> 32 -> 224 (ReLU). Bit-exact with haha-dog/model/infer_int.py.
contract HahaDogModel {
    bytes32 public constant MODEL_DATA_HASH = keccak256(Wt.DATA);

    function modelData() external pure returns (bytes memory) {
        return Wt.DATA;
    }

    function latent(bytes32 seed) public pure returns (int256[8] memory z) {
        for (uint256 i; i < 8; ++i) {
            uint256 s = uint256(uint8(seed[4 * i])) + uint8(seed[4 * i + 1]) + uint8(seed[4 * i + 2]) + uint8(seed[4 * i + 3]);
            z[i] = ((int256(s) - 510) * 7) >> 5;
        }
    }

    function generate(bytes32 seed) external pure returns (bytes memory cells, uint8[4] memory picks) {
        bytes memory data = Wt.DATA;
        int256[8] memory z = latent(seed);
        int256[64] memory h1;
        int256[32] memory h2;
        int256[224] memory y;
        uint256 m1 = Wt.M1;
        uint256 m2 = Wt.M2;
        assembly ("memory-safe") {
            let p := add(data, 32)
            let half := shl(sub(24, 1), 1)

            for { let j := 0 } lt(j, 64) { j := add(j, 1) } {
                let acc := signextend(1, shr(240, mload(add(p, add(9728, mul(j, 2))))))
                let w := mload(add(p, mul(j, 8)))
                for { let i := 0 } lt(i, 8) { i := add(i, 1) } {
                    acc := add(acc, mul(signextend(0, byte(i, w)), mload(add(z, mul(i, 32)))))
                }
                let v := 0
                if sgt(acc, 0) {
                    v := shr(24, add(mul(acc, m1), half))
                    if gt(v, 127) { v := 127 }
                }
                mstore(add(h1, mul(j, 32)), v)
            }

            for { let j := 0 } lt(j, 32) { j := add(j, 1) } {
                let acc := signextend(1, shr(240, mload(add(p, add(9856, mul(j, 2))))))
                let row := add(p, add(512, mul(j, 64)))
                let w := mload(row)
                for { let i := 0 } lt(i, 32) { i := add(i, 1) } {
                    acc := add(acc, mul(signextend(0, byte(i, w)), mload(add(h1, mul(i, 32)))))
                }
                w := mload(add(row, 32))
                for { let i := 0 } lt(i, 32) { i := add(i, 1) } {
                    acc := add(acc, mul(signextend(0, byte(i, w)), mload(add(h1, mul(add(i, 32), 32)))))
                }
                let v := 0
                if sgt(acc, 0) {
                    v := shr(24, add(mul(acc, m2), half))
                    if gt(v, 127) { v := 127 }
                }
                mstore(add(h2, mul(j, 32)), v)
            }

            for { let k := 0 } lt(k, 224) { k := add(k, 1) } {
                let acc := signextend(1, shr(240, mload(add(p, add(9920, mul(k, 2))))))
                let w := mload(add(p, add(2560, mul(k, 32))))
                for { let i := 0 } lt(i, 32) { i := add(i, 1) } {
                    acc := add(acc, mul(signextend(0, byte(i, w)), mload(add(h2, mul(i, 32)))))
                }
                mstore(add(y, mul(k, 32)), acc)
            }
        }

        cells = new bytes(128);
        uint256 outline = Wt.CONST_OUTLINE;
        assembly ("memory-safe") {
            let p := add(data, 32)
            let c := add(cells, 32)
            for { let i := 0 } lt(i, 128) { i := add(i, 1) } {
                mstore8(add(c, i), and(shr(i, outline), 1))
            }
            for { let v := 0 } lt(v, 99) { v := add(v, 1) } {
                let ci := byte(0, mload(add(p, add(10423, v))))
                let mask := shr(240, mload(add(p, add(10522, mul(v, 2)))))
                let ya := mload(add(y, mul(v, 64)))
                let yb := mload(add(y, add(mul(v, 64), 32)))
                let found := 0
                let best := 0
                let bc := 0
                for { let k := 0 } lt(k, 11) { k := add(k, 1) } {
                    if and(shr(k, mask), 1) {
                        let pw := mload(add(p, add(10368, mul(k, 2))))
                        let cw := shr(232, mload(add(p, add(10390, mul(k, 3)))))
                        let sc := sub(
                            mul(2, add(mul(ya, signextend(0, byte(0, pw))), mul(yb, signextend(0, byte(1, pw))))),
                            cw
                        )
                        if or(iszero(found), sgt(sc, best)) {
                            found := 1
                            best := sc
                            bc := k
                        }
                    }
                }
                mstore8(add(c, ci), bc)
            }
            let off := 198
            for { let g := 0 } lt(g, 4) { g := add(g, 1) } {
                let n := byte(add(28, g), 0x07080605)
                let best := mload(add(y, mul(off, 32)))
                let bi := 0
                for { let k := 1 } lt(k, n) { k := add(k, 1) } {
                    let v := mload(add(y, mul(add(off, k), 32)))
                    if sgt(v, best) {
                        best := v
                        bi := k
                    }
                }
                mstore(add(picks, mul(g, 32)), bi)
                off := add(off, n)
            }
        }
    }
}
