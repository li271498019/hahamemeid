// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Season1TestBase} from "./Season1TestBase.sol";
import {MerkleProof} from "@openzeppelin/contracts/utils/cryptography/MerkleProof.sol";

/// @notice 用 docs/season1/kickoff/fixtures/merkle-v1.json 的权威向量，
///         验证测试基类的 _leaf / _merkleRootAndProof 与生产生成器（tools/season1/merkle.py）
///         及合约 MerkleProof.verify 三者完全一致。
///         算法：haha-season1-merkle-v1 —— 叶 = keccak256(keccak256(abi.encode(aiId,balance,uint8 tier)))，
///         配对按字节排序后 keccak256(abi.encodePacked)，奇数节点原样上提、不与自身配对。
contract Season1MerkleTest is Season1TestBase {
    function _assertProofEq(bytes32[] memory actual, bytes32[] memory expected) internal pure {
        assertEq(actual.length, expected.length, "proof len");
        for (uint256 i = 0; i < expected.length; i++) {
            assertEq(actual[i], expected[i], "proof elem");
        }
    }

    function _leaf1(uint256 ai, uint256 balance, uint8 tier) internal pure returns (bytes32) {
        return _leaf(bytes32(ai), balance, tier);
    }

    // ------------------------------------------------------------------
    // case 1：单叶子，root == leaf，proof 为空
    // ------------------------------------------------------------------
    function test_merkle_v1_case_1() public {
        bytes32 leaf = _leaf1(1, 1000, 0);
        assertEq(leaf, 0x1de1fef56350455c6f48356a12aa86d66ae67ce6be00cb4a62a0db64043f7881, "leaf");

        bytes32[] memory leaves = new bytes32[](1);
        leaves[0] = leaf;
        (bytes32 root, bytes32[] memory proof) = _merkleRootAndProof(leaves, 0);

        assertEq(root, 0x1de1fef56350455c6f48356a12aa86d66ae67ce6be00cb4a62a0db64043f7881, "root");
        assertEq(proof.length, 0, "proof empty");
        assertTrue(MerkleProof.verify(proof, root, leaf), "verify");
    }

    // ------------------------------------------------------------------
    // case 2：两个叶子
    // ------------------------------------------------------------------
    function test_merkle_v1_case_2() public {
        bytes32 leaf1 = _leaf1(1, 1000, 0);
        bytes32 leaf2 = _leaf1(2, 200, 1);
        assertEq(leaf1, 0x1de1fef56350455c6f48356a12aa86d66ae67ce6be00cb4a62a0db64043f7881, "leaf1");
        assertEq(leaf2, 0x5f534703d592a7368e582265cf25e86495dd80555261319bb9ada5540aee0a33, "leaf2");

        bytes32[] memory leaves = new bytes32[](2);
        leaves[0] = leaf1;
        leaves[1] = leaf2;

        bytes32[] memory expectedProof1 = new bytes32[](1);
        expectedProof1[0] = 0x5f534703d592a7368e582265cf25e86495dd80555261319bb9ada5540aee0a33;
        bytes32[] memory expectedProof2 = new bytes32[](1);
        expectedProof2[0] = 0x1de1fef56350455c6f48356a12aa86d66ae67ce6be00cb4a62a0db64043f7881;

        (bytes32 root, bytes32[] memory proof1) = _merkleRootAndProof(leaves, 0);
        (, bytes32[] memory proof2) = _merkleRootAndProof(leaves, 1);

        assertEq(root, 0x68cdba65f45692225a7e6ff1982faedd4c3ab207361e24dd704faae1c451041f, "root");
        _assertProofEq(proof1, expectedProof1);
        _assertProofEq(proof2, expectedProof2);
        assertTrue(MerkleProof.verify(proof1, root, leaf1), "verify1");
        assertTrue(MerkleProof.verify(proof2, root, leaf2), "verify2");
    }

    // ------------------------------------------------------------------
    // case 3：三个叶子（奇数节点上提）
    // ------------------------------------------------------------------
    function test_merkle_v1_case_3() public {
        bytes32 leaf1 = _leaf1(1, 501, 0);
        bytes32 leaf2 = _leaf1(2, 502, 1);
        bytes32 leaf3 = _leaf1(3, 503, 1);
        assertEq(leaf1, 0x40cd85bff3a59b3cd77276e3172491c401f6320973b4bc8b11af6def4f7f342c, "leaf1");
        assertEq(leaf2, 0x9c40e0f2d22a41bc5c6607435acbb39458f24990511b95b9ae1253f0815876b6, "leaf2");
        assertEq(leaf3, 0xdf0ad868a31f1dab71e60bbca6b5c72ef001e8db9c80037be9c9e3024c82d95f, "leaf3");

        bytes32[] memory leaves = new bytes32[](3);
        leaves[0] = leaf1;
        leaves[1] = leaf2;
        leaves[2] = leaf3;

        bytes32[] memory expectedProof1 = new bytes32[](2);
        expectedProof1[0] = 0x9c40e0f2d22a41bc5c6607435acbb39458f24990511b95b9ae1253f0815876b6;
        expectedProof1[1] = 0xdf0ad868a31f1dab71e60bbca6b5c72ef001e8db9c80037be9c9e3024c82d95f;
        bytes32[] memory expectedProof2 = new bytes32[](2);
        expectedProof2[0] = 0x40cd85bff3a59b3cd77276e3172491c401f6320973b4bc8b11af6def4f7f342c;
        expectedProof2[1] = 0xdf0ad868a31f1dab71e60bbca6b5c72ef001e8db9c80037be9c9e3024c82d95f;
        bytes32[] memory expectedProof3 = new bytes32[](1);
        expectedProof3[0] = 0xc989af00a25a1b57d8cae5cdd7f3f1d25a7acb34530e5fd52415b87d60437cdb;

        (bytes32 root, bytes32[] memory proof1) = _merkleRootAndProof(leaves, 0);
        (, bytes32[] memory proof2) = _merkleRootAndProof(leaves, 1);
        (, bytes32[] memory proof3) = _merkleRootAndProof(leaves, 2);

        assertEq(root, 0xace5aeef4c07deed5fa8c765e93793b69e5af253a5981f17bd2e139573b77057, "root");
        _assertProofEq(proof1, expectedProof1);
        _assertProofEq(proof2, expectedProof2);
        _assertProofEq(proof3, expectedProof3);
        assertTrue(MerkleProof.verify(proof1, root, leaf1), "verify1");
        assertTrue(MerkleProof.verify(proof2, root, leaf2), "verify2");
        assertTrue(MerkleProof.verify(proof3, root, leaf3), "verify3");
    }

    // ------------------------------------------------------------------
    // case 5：五个叶子（两层 + 奇数上提）
    // ------------------------------------------------------------------
    function test_merkle_v1_case_5() public {
        bytes32 leaf1 = _leaf1(1, 800, 0);
        bytes32 leaf2 = _leaf1(2, 800, 0);
        bytes32 leaf3 = _leaf1(3, 200, 1);
        bytes32 leaf4 = _leaf1(4, 200, 1);
        bytes32 leaf5 = _leaf1(5, 200, 1);
        assertEq(leaf1, 0x66641d8a1ee62a5e613540d5a7bf8870c9bbc6f44583649d8f27b5bf6bef38f0, "leaf1");
        assertEq(leaf2, 0x8bc1b88cc52f807d524aa874332acfafce2ae4e6f513996885d5360e1d2b1571, "leaf2");
        assertEq(leaf3, 0xaf4b472d47cd77f4e5ae7d406ac0469638ebe9ccad879a20c6aeebbe86148cff, "leaf3");
        assertEq(leaf4, 0x7a297bc477a99247620d8e30927f4816db85f65edbc4eb9a320ce9d286add6b4, "leaf4");
        assertEq(leaf5, 0x6249e3e622b4c0f476728a24a8dd730a0eedfefd8e9f55fba85d7103a18a3ad6, "leaf5");

        bytes32[] memory leaves = new bytes32[](5);
        leaves[0] = leaf1;
        leaves[1] = leaf2;
        leaves[2] = leaf3;
        leaves[3] = leaf4;
        leaves[4] = leaf5;

        // 每层的期望 proof（来自文件）
        bytes32[] memory expectedProof1 = new bytes32[](3);
        expectedProof1[0] = 0x8bc1b88cc52f807d524aa874332acfafce2ae4e6f513996885d5360e1d2b1571;
        expectedProof1[1] = 0x9597d8d3967c0428ccf6beddc82ab7605431d001bd32a388389fbf5f229edfd8;
        expectedProof1[2] = 0x6249e3e622b4c0f476728a24a8dd730a0eedfefd8e9f55fba85d7103a18a3ad6;
        bytes32[] memory expectedProof5 = new bytes32[](1);
        expectedProof5[0] = 0xaf7688fbab0ece84192c5b0b2ae539df8e4f57d5fbf07a173f5812c287c3b2b7;

        (bytes32 root, bytes32[] memory proof1) = _merkleRootAndProof(leaves, 0);
        (, bytes32[] memory proof5) = _merkleRootAndProof(leaves, 4);

        assertEq(root, 0x1a622ce55fdd0fa6c41dccf9fdcda6fda3798b466aeb6134a9d7bd8bfe13a4ba, "root");
        _assertProofEq(proof1, expectedProof1);
        _assertProofEq(proof5, expectedProof5);

        // 所有叶子都能用文件 root 验证通过
        for (uint256 i = 0; i < 5; i++) {
            (, bytes32[] memory p) = _merkleRootAndProof(leaves, i);
            assertTrue(MerkleProof.verify(p, root, leaves[i]), "verify all");
        }
    }

    // ------------------------------------------------------------------
    // case 20：二十个叶子（root 权威 + 首尾 proof 精确 + 全部 verify）
    // ------------------------------------------------------------------
    function test_merkle_v1_case_20() public {
        bytes32[] memory leaves = new bytes32[](20);
        // 前 12 个：aiId 1..12，balance 999..988，tier 0
        // 后 8 个：aiId 13..20，balance 200，tier 1
        for (uint256 i = 0; i < 20; i++) {
            uint256 ai = i + 1;
            if (i < 12) {
                leaves[i] = _leaf1(ai, 1000 - ai, 0);
            } else {
                leaves[i] = _leaf1(ai, 200, 1);
            }
        }

        // 文件里的 leaf 抽查（首尾）
        assertEq(leaves[0], 0x23a47e26ba690508016519a706d11eec2ff929d3d0cc6ddf271db057f502d901, "leaf[1]");
        assertEq(leaves[19], 0x1712c115389a09aab6bea8d6368b705f5c612f3878f78cae9513ef0b80729a93, "leaf[20]");

        (bytes32 root, bytes32[] memory proof1) = _merkleRootAndProof(leaves, 0);
        assertEq(root, 0xbff1068ef69fd1896a19e5b29949e8dd58da7a96d5460ad5d14c1282c458714e, "root");

        // 首叶子 proof 精确断言（文件权威值）
        bytes32[] memory expectedProof1 = new bytes32[](5);
        expectedProof1[0] = 0x059e7aa488158161aaebc8b7b768671b8b00256e5faa4ef995d6b52b5b6b914e;
        expectedProof1[1] = 0xc9a1d48efbb824da100ce64f87152322c9c65302056d972148d2ffa2ee651702;
        expectedProof1[2] = 0xb039350f64a13fc11177b0d1c921ea2431b7b8b70ab3583452da4bd059fdec8e;
        expectedProof1[3] = 0x59f1d25552d9d65a8a66f9330bb4a8982a2f9467f7ae6b7b868a2b723784b7cd;
        expectedProof1[4] = 0x58c6b2f41acdfa001861a9ce0a3288ea678ffde70090afc4805835f5a08df973;
        _assertProofEq(proof1, expectedProof1);

        // 所有叶子都能用文件 root 验证通过（证明证明正确）
        for (uint256 i = 0; i < 20; i++) {
            (, bytes32[] memory p) = _merkleRootAndProof(leaves, i);
            assertTrue(MerkleProof.verify(p, root, leaves[i]), "verify all");
        }
    }
}
