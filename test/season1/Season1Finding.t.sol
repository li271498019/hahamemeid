// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Season1TestBase} from "./Season1TestBase.sol";
import {HahaSeason1} from "src/HahaSeason1.sol";

contract Season1FindingTest is Season1TestBase {
    bytes32 internal constant EVIDENCE = keccak256("evidence");
    bytes32 internal constant SALT = keccak256("salt");
    bytes32 internal constant CANONICAL = keccak256("canonical");

    function _commitAndPublish(bytes32 aiId, address user)
        internal
        returns (bytes32 commitHash, uint64 publishedAt)
    {
        vm.warp(uint256(S1_START_TS));
        vm.prank(user);
        season1.commitFinding(EVIDENCE, SALT);

        commitHash = keccak256(abi.encode(block.chainid, address(season1), 1, aiId, EVIDENCE, SALT));

        vm.startPrank(rewardSigner);
        season1.assignCanonical(EVIDENCE, CANONICAL);
        season1.publishRuling(EVIDENCE);
        vm.stopPrank();
        publishedAt = uint64(block.timestamp);
    }

    function test_commit_success() public {
        bytes32 aiId = _aiId("salice");
        vm.warp(uint256(S1_START_TS));
        vm.prank(sAlice);
        season1.commitFinding(EVIDENCE, SALT);

        bytes32 commitHash = keccak256(abi.encode(block.chainid, address(season1), 1, aiId, EVIDENCE, SALT));
        (bytes32 cAi, address committer, uint64 bn, uint64 at,) = season1.commitOf(commitHash);
        assertEq(cAi, aiId, "aiId recorded");
        assertEq(committer, sAlice, "committer");
        assertTrue(bn > 0, "block number");
        assertTrue(at < S1_END_TS, "committed before end");
    }

    function test_commit_noAi_reverts() public {
        vm.warp(uint256(S1_START_TS));
        address noAi = makeAddr("noAi");
        vm.prank(noAi);
        vm.expectRevert(HahaSeason1.AiRequired.selector);
        season1.commitFinding(EVIDENCE, SALT);
    }

    function test_commit_zero_reverts() public {
        vm.warp(uint256(S1_START_TS));
        vm.prank(sAlice);
        vm.expectRevert(HahaSeason1.ZeroCommit.selector);
        season1.commitFinding(bytes32(0), SALT);
    }

    function test_claimFinding_success() public {
        bytes32 aiId = _aiId("salice");
        uint256 before = points.balanceOf(aiId);
        (, uint64 publishedAt) = _commitAndPublish(aiId, sAlice);

        // 公示 24h 后
        vm.warp(publishedAt + 24 hours);
        uint64 deadline = publishedAt + 24 hours + 7 days;

        HahaSeason1.FindingAuth memory auth = HahaSeason1.FindingAuth({
            seasonId: 1,
            reportEvidenceHash: EVIDENCE,
            salt: SALT,
            aiId: aiId,
            nonce: 0,
            deadline: deadline
        });
        bytes32 digest = _findingAuthDigest(auth);
        bytes memory sig = _sign(REWARD_PK, digest);

        vm.prank(sAlice);
        season1.claimFinding(auth, sig);

        assertEq(points.balanceOf(aiId), before + 100, "earn 100");
        assertTrue(season1.canonicalClaimed(CANONICAL), "canonical claimed");
    }

    function test_claimFinding_insidePublicity_reverts() public {
        bytes32 aiId = _aiId("salice");
        (, uint64 publishedAt) = _commitAndPublish(aiId, sAlice);

        // 公示未满 24h
        vm.warp(publishedAt + 1 hours);
        uint64 deadline = publishedAt + 24 hours + 7 days;

        HahaSeason1.FindingAuth memory auth = HahaSeason1.FindingAuth({
            seasonId: 1,
            reportEvidenceHash: EVIDENCE,
            salt: SALT,
            aiId: aiId,
            nonce: 0,
            deadline: deadline
        });
        bytes32 digest = _findingAuthDigest(auth);
        bytes memory sig = _sign(REWARD_PK, digest);

        vm.prank(sAlice);
        vm.expectRevert(HahaSeason1.BadTime.selector);
        season1.claimFinding(auth, sig);
    }

    function test_claimFinding_unknownCommit_reverts() public {
        vm.warp(uint256(S1_START_TS) + 1 days);
        bytes32 aiId = _aiId("salice");

        HahaSeason1.FindingAuth memory auth = HahaSeason1.FindingAuth({
            seasonId: 1,
            reportEvidenceHash: EVIDENCE,
            salt: SALT,
            aiId: aiId,
            nonce: 0,
            deadline: 0
        });
        bytes32 digest = _findingAuthDigest(auth);
        bytes memory sig = _sign(REWARD_PK, digest);

        vm.prank(sAlice);
        vm.expectRevert(HahaSeason1.UnknownCommit.selector);
        season1.claimFinding(auth, sig);
    }

    function test_claimFinding_canonicalUnassigned_reverts() public {
        bytes32 aiId = _aiId("salice");
        // commit 但未 assignCanonical
        vm.warp(uint256(S1_START_TS));
        vm.prank(sAlice);
        season1.commitFinding(EVIDENCE, SALT);

        // publishRuling 需要 assignCanonical，这里跳过。直接 claimFinding 会 UnknownCommit 之后是 publishedAt==0。
        // 改成：assignCanonical 了但未 publishRuling
        vm.prank(rewardSigner);
        season1.assignCanonical(EVIDENCE, CANONICAL);

        uint64 deadline = uint64(block.timestamp) + 24 hours + 7 days;
        HahaSeason1.FindingAuth memory auth = HahaSeason1.FindingAuth({
            seasonId: 1,
            reportEvidenceHash: EVIDENCE,
            salt: SALT,
            aiId: aiId,
            nonce: 0,
            deadline: deadline
        });
        bytes32 digest = _findingAuthDigest(auth);
        bytes memory sig = _sign(REWARD_PK, digest);

        vm.prank(sAlice);
        // 未公示，publishedAt == 0 → BadTime
        vm.expectRevert(HahaSeason1.BadTime.selector);
        season1.claimFinding(auth, sig);
    }

    // 跨赛季：commit 在赛季内，claim 在 END_TS 之后、仍处于公示后 7 天内，应成功。
    function test_claimFinding_afterSeasonEnd_success() public {
        bytes32 aiId = _aiId("salice");
        uint256 before = points.balanceOf(aiId);

        // commit 在赛季末尾（END_TS - 1h），仍 < END_TS
        vm.warp(uint256(S1_END_TS) - 1 hours);
        vm.prank(sAlice);
        season1.commitFinding(EVIDENCE, SALT);

        vm.startPrank(rewardSigner);
        season1.assignCanonical(EVIDENCE, CANONICAL);
        season1.publishRuling(EVIDENCE);
        vm.stopPrank();
        uint64 publishedAt = uint64(block.timestamp); // = S1_END_TS - 1h

        uint64 claimStart = publishedAt + 24 hours; // = S1_END_TS + 23h，已过赛季
        uint64 claimEnd = claimStart + 7 days;
        vm.warp(uint256(claimStart) + 1 hours);
        assertTrue(block.timestamp >= S1_END_TS, "after season end");

        HahaSeason1.FindingAuth memory auth = HahaSeason1.FindingAuth({
            seasonId: 1,
            reportEvidenceHash: EVIDENCE,
            salt: SALT,
            aiId: aiId,
            nonce: 0,
            deadline: claimEnd
        });
        bytes32 digest = _findingAuthDigest(auth);
        bytes memory sig = _sign(REWARD_PK, digest);

        vm.prank(sAlice);
        season1.claimFinding(auth, sig);

        assertEq(points.balanceOf(aiId), before + 100, "earn 100 cross-season");
        assertTrue(season1.canonicalClaimed(CANONICAL), "canonical claimed");
    }

    // 领奖过期：超过公示后 7 天，claim 失败。
    function test_claimFinding_afterClaimWindow_reverts() public {
        bytes32 aiId = _aiId("salice");
        (, uint64 publishedAt) = _commitAndPublish(aiId, sAlice);

        uint64 claimEnd = publishedAt + 24 hours + 7 days;
        vm.warp(uint256(claimEnd)); // 恰好到期，>= claimEnd → BadTime

        HahaSeason1.FindingAuth memory auth = HahaSeason1.FindingAuth({
            seasonId: 1,
            reportEvidenceHash: EVIDENCE,
            salt: SALT,
            aiId: aiId,
            nonce: 0,
            deadline: claimEnd
        });
        bytes32 digest = _findingAuthDigest(auth);
        bytes memory sig = _sign(REWARD_PK, digest);

        vm.prank(sAlice);
        vm.expectRevert(HahaSeason1.BadTime.selector);
        season1.claimFinding(auth, sig);
    }
}
