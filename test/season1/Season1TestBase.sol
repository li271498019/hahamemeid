// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {HahaTestBase} from "../HahaTestBase.sol";
import {HahaSeason1} from "src/HahaSeason1.sol";
import {HahaPoints} from "src/HahaPoints.sol";

/// @notice Season1 测试基类：部署 Season1、配置 Points 的 spender / 三个 earner、
///         提供 Merkle 树构建与 EIP-712 签名工具。
abstract contract Season1TestBase is HahaTestBase {
    HahaSeason1 internal season1;

    bytes32 internal constant ACTION_VERIFY = "SEASON1_VERIFY";
    bytes32 internal constant ACTION_FIND = "SEASON1_FIND";
    bytes32 internal constant ACTION_ACCIDENT = "SEASON1_ACCIDENT";

    uint64 internal constant S1_START_TS = 1795478400;
    uint64 internal constant S1_END_TS = 1796774400;

    // 测试私钥（用于 vm.sign）
    uint256 internal constant ALICE_PK = 0xA11CE;
    uint256 internal constant BOB_PK = 0xB0B;
    uint256 internal constant CAROL_PK = 0xC0FFEE;
    uint256 internal constant VALIDATOR_PK = 0x5EED;
    uint256 internal constant REWARD_PK = 0xF00D;

    address internal sAlice;
    address internal sBob;
    address internal sCarol;
    address internal validator;
    address internal rewardSigner;

    function setUp() public virtual override {
        super.setUp();

        sAlice = vm.addr(ALICE_PK);
        sBob = vm.addr(BOB_PK);
        sCarol = vm.addr(CAROL_PK);
        validator = vm.addr(VALIDATOR_PK);
        rewardSigner = vm.addr(REWARD_PK);

        _giveAi(sAlice, "salice");
        _giveAi(sBob, "sbob");
        _giveAi(sCarol, "scarol");

        season1 = new HahaSeason1(ADMIN, address(points), address(registrar), address(identity), address(ai), 15);

        // 配置 Points：spender + 预算 + 三个 earner
        vm.startPrank(ADMIN);
        points.setSpender(address(season1), true);
        points.setSpenderBudget(
            address(season1), HahaPoints.SpenderBudget({perUserDailyPoints: 200, globalDailyPoints: 4000})
        );
        points.setEarner(
            ACTION_VERIFY,
            HahaPoints.EarnerConfig({
                module: address(season1),
                points: 30,
                perUserDailyCap: 1,
                globalDailyPoints: 100000,
                keyMode: HahaPoints.KeyMode.PerDay,
                requireName: true,
                enabled: true
            })
        );
        points.setEarner(
            ACTION_FIND,
            HahaPoints.EarnerConfig({
                module: address(season1),
                points: 100,
                perUserDailyCap: 5,
                globalDailyPoints: 10000,
                keyMode: HahaPoints.KeyMode.Lifetime,
                requireName: true,
                enabled: true
            })
        );
        points.setEarner(
            ACTION_ACCIDENT,
            HahaPoints.EarnerConfig({
                module: address(season1),
                points: 100,
                perUserDailyCap: 50,
                globalDailyPoints: 10000,
                keyMode: HahaPoints.KeyMode.Lifetime,
                requireName: false,
                enabled: true
            })
        );
        vm.stopPrank();

        // 默认打开开关
        vm.prank(ADMIN);
        season1.setRedeemOpen(true);
        vm.prank(ADMIN);
        season1.setRewardsOpen(true);

        // 配置 validator 和 rewardSigner
        vm.startPrank(ADMIN);
        season1.setValidator(validator, true);
        season1.setRewardSigner(rewardSigner);
        vm.stopPrank();

        // 给测试用户铸名字（满足 applyFor -> spend 的持名要求），1 位名字不在候选池
        vm.startPrank(ADMIN);
        registrar.adminMint("x", 0, sAlice);
        registrar.adminMint("y", 0, sBob);
        registrar.adminMint("z", 0, sCarol);
        vm.stopPrank();

        // 给测试用户积分（applyFor 扣 200，余额需 >= 200）
        _mintPoints(sAlice, 1000);
        _mintPoints(sBob, 1000);
        _mintPoints(sCarol, 1000);
    }

    // ---------------------------------------------------------------------
    // 工具：积分
    // ---------------------------------------------------------------------

    /// @dev 给用户发积分（测试专用 earner，module = season1，每次 100 分）。
    function _mintPoints(address user, uint256 amount) internal {
        bytes32 action = keccak256(abi.encodePacked("TEST_SEED", user));
        vm.startPrank(ADMIN);
        points.setEarner(
            action,
            HahaPoints.EarnerConfig({
                module: address(season1),
                points: 100,
                perUserDailyCap: 50,
                globalDailyPoints: 1_000_000,
                keyMode: HahaPoints.KeyMode.PerDay,
                requireName: false,
                enabled: true
            })
        );
        vm.stopPrank();

        uint256 times = amount / 100;
        vm.startPrank(address(season1));
        for (uint256 i = 0; i < times; i++) {
            points.earn(action, user, bytes32(i + 1));
        }
        vm.stopPrank();
    }

    // ---------------------------------------------------------------------
    // 工具：Merkle
    // ---------------------------------------------------------------------

    function _leaf(bytes32 aiId, uint256 balance, uint8 tier) internal pure returns (bytes32) {
        return keccak256(abi.encodePacked(keccak256(abi.encode(aiId, balance, tier))));
    }

    function _hashPair(bytes32 a, bytes32 b) internal pure returns (bytes32) {
        return a < b ? keccak256(abi.encodePacked(a, b)) : keccak256(abi.encodePacked(b, a));
    }

    /// @dev 构建 Merkle 树（haha-season1-merkle-v1）：
    ///      配对按字节排序后 keccak256(abi.encodePacked)，奇数节点原样上提、不与自身配对。
    ///      与 docs/season1/kickoff/fixtures/merkle-v1.json 及 tools/season1/merkle.py 完全一致。
    function _merkleRootAndProof(bytes32[] memory leaves, uint256 idx)
        internal
        pure
        returns (bytes32 root, bytes32[] memory proof)
    {
        uint256 n = leaves.length;
        require(n > 0, "empty tree");
        uint256 layers = 0;
        uint256 m = n;
        while (m > 1) {
            m = (m + 1) / 2;
            layers++;
        }

        bytes32[][] memory tree = new bytes32[][](layers + 1);
        tree[0] = leaves;
        for (uint256 l = 0; l < layers; l++) {
            uint256 curLen = tree[l].length;
            uint256 nextLen = (curLen + 1) / 2;
            bytes32[] memory next = new bytes32[](nextLen);
            uint256 i = 0;
            uint256 w = 0;
            while (i + 1 < curLen) {
                next[w++] = _hashPair(tree[l][i], tree[l][i + 1]);
                i += 2;
            }
            if (i < curLen) {
                // 奇数节点原样上提，不与自己配对
                next[w] = tree[l][i];
            }
            tree[l + 1] = next;
        }
        root = tree[layers][0];

        // proof：该层 sibling 不存在（奇数上提）时跳过，不占位
        uint256 proofLen = 0;
        uint256 cursor = idx;
        for (uint256 l = 0; l < layers; l++) {
            uint256 sibling = cursor ^ 1;
            if (sibling < tree[l].length) proofLen++;
            cursor /= 2;
        }
        proof = new bytes32[](proofLen);
        cursor = idx;
        uint256 p = 0;
        for (uint256 l = 0; l < layers; l++) {
            uint256 sibling = cursor ^ 1;
            if (sibling < tree[l].length) {
                proof[p++] = tree[l][sibling];
            }
            cursor /= 2;
        }
    }

    // ---------------------------------------------------------------------
    // 工具：EIP-712 签名
    // ---------------------------------------------------------------------

    function _domainSeparator() internal view returns (bytes32) {
        bytes32 typehash = keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)");
        return keccak256(
            abi.encode(typehash, keccak256("HahaSeason1"), keccak256("1"), block.chainid, address(season1))
        );
    }

    function _applyAuthDigest(HahaSeason1.ApplyAuth memory auth) internal view returns (bytes32) {
        bytes32 typehash = keccak256(
            "ApplyAuth(uint256 seasonId,uint64 dayIndex,bytes32 aiId,string label,uint8 tld,uint256 price,address recipient,uint256 nonce,uint64 deadline,bytes32 root,uint8 tier,uint256 balance)"
        );
        bytes32 structHash = keccak256(
            abi.encode(
                typehash,
                auth.seasonId,
                auth.dayIndex,
                auth.aiId,
                keccak256(bytes(auth.label)),
                auth.tld,
                auth.price,
                auth.recipient,
                auth.nonce,
                auth.deadline,
                auth.root,
                auth.tier,
                auth.balance
            )
        );
        return keccak256(abi.encodePacked("\x19\x01", _domainSeparator(), structHash));
    }

    function _verifyAuthDigest(HahaSeason1.VerifyAuth memory auth) internal view returns (bytes32) {
        bytes32 typehash = keccak256(
            "VerifyAuth(uint256 seasonId,uint64 dayIndex,bytes32 aiId,uint256 agentId,uint64 generation,bytes32 taskPackHash,uint8 verdict,uint256 nonce,uint64 deadline)"
        );
        bytes32 structHash = keccak256(
            abi.encode(
                typehash,
                auth.seasonId,
                auth.dayIndex,
                auth.aiId,
                auth.agentId,
                auth.generation,
                auth.taskPackHash,
                auth.verdict,
                auth.nonce,
                auth.deadline
            )
        );
        return keccak256(abi.encodePacked("\x19\x01", _domainSeparator(), structHash));
    }

    function _findingAuthDigest(HahaSeason1.FindingAuth memory auth) internal view returns (bytes32) {
        bytes32 typehash =
            keccak256("FindingAuth(uint256 seasonId,bytes32 reportEvidenceHash,bytes32 salt,bytes32 aiId,uint256 nonce,uint64 deadline)");
        bytes32 structHash = keccak256(
            abi.encode(
                typehash,
                auth.seasonId,
                auth.reportEvidenceHash,
                auth.salt,
                auth.aiId,
                auth.nonce,
                auth.deadline
            )
        );
        return keccak256(abi.encodePacked("\x19\x01", _domainSeparator(), structHash));
    }

    function _sign(uint256 pk, bytes32 digest) internal pure returns (bytes memory) {
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(pk, digest);
        return abi.encodePacked(r, s, v);
    }
}
