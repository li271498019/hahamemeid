// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Season1TestBase} from "./Season1TestBase.sol";
import {HahaSeason1} from "src/HahaSeason1.sol";

contract Season1VerifyTest is Season1TestBase {
    uint64 internal constant DAY = 20781;

    function _setupVerifyDay(uint64 day) internal returns (bytes32 taskPackHash, uint256 agentId) {
        vm.warp(uint256(day) * 86400);
        taskPackHash = keccak256("taskpack");
        vm.prank(ADMIN);
        season1.setTaskPack(day, taskPackHash);

        // 激活 agent
        vm.prank(sAlice);
        agentId = identity.activateAgent("x", 0, "https://x");
    }

    function _verifyAuth(uint64 day, bytes32 aiId, uint256 agentId, uint64 generation, bytes32 taskPackHash, uint8 verdict)
        internal
        view
        returns (HahaSeason1.VerifyAuth memory)
    {
        return HahaSeason1.VerifyAuth({
            seasonId: 1,
            dayIndex: day,
            aiId: aiId,
            agentId: agentId,
            generation: generation,
            taskPackHash: taskPackHash,
            verdict: verdict,
            nonce: 0,
            deadline: (day + 1) * 86400
        });
    }

    function test_verify_success() public {
        (bytes32 taskPackHash, uint256 agentId) = _setupVerifyDay(DAY);
        bytes32 aiId = _aiId("salice");
        uint256 before = points.balanceOf(aiId);

        HahaSeason1.VerifyAuth memory auth = _verifyAuth(DAY, aiId, agentId, 1, taskPackHash, 0);
        bytes32 digest = _verifyAuthDigest(auth);
        bytes memory sig = _sign(VALIDATOR_PK, digest);

        vm.prank(sAlice);
        season1.claimVerification(auth, sig);

        assertEq(points.balanceOf(aiId), before + 30, "earn 30");
        assertTrue(season1.verified(aiId, DAY), "verified");
        assertEq(season1.nonces(aiId), 1, "nonce +1");
    }

    function test_verify_verdictOne_success() public {
        (bytes32 taskPackHash, uint256 agentId) = _setupVerifyDay(DAY);
        bytes32 aiId = _aiId("salice");
        uint256 before = points.balanceOf(aiId);

        HahaSeason1.VerifyAuth memory auth = _verifyAuth(DAY, aiId, agentId, 1, taskPackHash, 1);
        bytes32 digest = _verifyAuthDigest(auth);
        bytes memory sig = _sign(VALIDATOR_PK, digest);

        vm.prank(sAlice);
        season1.claimVerification(auth, sig);

        assertEq(points.balanceOf(aiId), before + 30, "earn 30 verdict 1");
    }

    function test_verify_idempotent_secondReturns() public {
        (bytes32 taskPackHash, uint256 agentId) = _setupVerifyDay(DAY);
        bytes32 aiId = _aiId("salice");

        HahaSeason1.VerifyAuth memory auth = _verifyAuth(DAY, aiId, agentId, 1, taskPackHash, 0);
        bytes32 digest = _verifyAuthDigest(auth);
        bytes memory sig = _sign(VALIDATOR_PK, digest);

        vm.startPrank(sAlice);
        season1.claimVerification(auth, sig);
        uint256 after1 = points.balanceOf(aiId);
        // 第二次：verified 已真，直接 return，不再 earn
        season1.claimVerification(auth, sig);
        vm.stopPrank();

        assertEq(points.balanceOf(aiId), after1, "no second earn");
    }

    function test_verify_staleGeneration_reverts() public {
        (bytes32 taskPackHash, uint256 agentId) = _setupVerifyDay(DAY);
        bytes32 aiId = _aiId("salice");

        // generation 不符
        HahaSeason1.VerifyAuth memory auth = _verifyAuth(DAY, aiId, agentId, 2, taskPackHash, 0);
        bytes32 digest = _verifyAuthDigest(auth);
        bytes memory sig = _sign(VALIDATOR_PK, digest);

        vm.prank(sAlice);
        vm.expectRevert(HahaSeason1.StaleGeneration.selector);
        season1.claimVerification(auth, sig);
    }

    function test_verify_revokedValidator_reverts() public {
        (bytes32 taskPackHash, uint256 agentId) = _setupVerifyDay(DAY);
        bytes32 aiId = _aiId("salice");

        HahaSeason1.VerifyAuth memory auth = _verifyAuth(DAY, aiId, agentId, 1, taskPackHash, 0);
        bytes32 digest = _verifyAuthDigest(auth);
        bytes memory sig = _sign(VALIDATOR_PK, digest);

        // 撤销 validator
        vm.prank(ADMIN);
        season1.setValidator(validator, false);

        vm.prank(sAlice);
        vm.expectRevert(HahaSeason1.BadSignature.selector);
        season1.claimVerification(auth, sig);
    }

    function test_verify_wrongTaskPack_reverts() public {
        (bytes32 taskPackHash, uint256 agentId) = _setupVerifyDay(DAY);
        bytes32 aiId = _aiId("salice");

        HahaSeason1.VerifyAuth memory auth = _verifyAuth(DAY, aiId, agentId, 1, keccak256("wrong"), 0);
        bytes32 digest = _verifyAuthDigest(auth);
        bytes memory sig = _sign(VALIDATOR_PK, digest);

        vm.prank(sAlice);
        vm.expectRevert(HahaSeason1.BadRoot.selector);
        season1.claimVerification(auth, sig);
    }
}
