// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {IERC1271} from "@openzeppelin/contracts/interfaces/IERC1271.sol";
import {MerkleProof} from "@openzeppelin/contracts/utils/cryptography/MerkleProof.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

import {IBinanceAiRegistry} from "./interfaces/IBinanceAiRegistry.sol";
import {HahaAiIdentity} from "./libraries/HahaAiIdentity.sol";
import {HahaNamehash} from "./libraries/HahaNamehash.sol";

/// @notice 第一季兑换、每日验证、找错与事故模块。
///         它是 HahaPoints 的 spender（仅 applyFor 扣 200），
///         也是 SEASON1_VERIFY / SEASON1_FIND / SEASON1_ACCIDENT 三个 earner 的 module。
contract HahaSeason1 is EIP712, ReentrancyGuard {
    // ---------------------------------------------------------------------
    // 常量
    // ---------------------------------------------------------------------

    uint256 public constant SEASON_ID = 1;
    uint256 public constant PRICE = 200;
    uint64 public constant START_TS = 1795478400; // 2026-11-24T00:00:00Z
    uint64 public constant END_TS = 1796774400; // 2026-12-09T00:00:00Z
    uint64 public constant FULFILL_GRACE = 12 hours;
    uint16 public constant DAILY_MAX = 20;
    uint16 public constant SEASON_MAX = 300;

    bytes32 public constant ACTION_VERIFY = "SEASON1_VERIFY";
    bytes32 public constant ACTION_FIND = "SEASON1_FIND";
    bytes32 public constant ACTION_ACCIDENT = "SEASON1_ACCIDENT";
    bytes32 public constant REASON_REDEEM = "SEASON1_REDEEM";
    bytes32 public constant VERIFY_KEY = "VERIFY_DAY";

    uint64 private constant FIRST_DAY = 20781;
    uint64 private constant LAST_DAY = 20795; // 窗口 [20781, 20796)
    uint64 private constant FIND_REVEAL_WINDOW = 7 days;
    uint64 private constant FIND_PUBLICITY = 24 hours;
    uint64 private constant FIND_CLAIM_WINDOW = 7 days;

    // ---------------------------------------------------------------------
    // 枚举
    // ---------------------------------------------------------------------

    enum Tier {
        Reserved, // 0
        Boundary // 1
    }

    enum OrderStatus {
        None, // 0
        Pending, // 1
        Fulfilled, // 2
        CreditOpen, // 3
        AccidentRefunded, // 4
        AccidentClosed // 5
    }

    enum Verdict {
        Match, // 0
        Discrepancy // 1
    }

    // ---------------------------------------------------------------------
    // 结构
    // ---------------------------------------------------------------------

    struct Order {
        bytes32 aiId;
        address applicant;
        address recipient;
        uint8 tld;
        string label;
        uint64 dayIndex;
        uint64 createdAt;
        OrderStatus status;
        Tier tier;
    }

    struct DayMarket {
        bytes32 merkleRoot;
        uint64 snapshotBlock;
        bytes32 snapshotBlockHash;
        uint16 reservedCount;
        uint16 remainingSlots;
        uint16 boundaryFilled;
        uint16 reservedFilled;
        bool opened;
    }

    struct ApplyAuth {
        uint256 seasonId;
        uint64 dayIndex;
        bytes32 aiId;
        string label;
        uint8 tld;
        uint256 price;
        address recipient;
        uint256 nonce;
        uint64 deadline;
        bytes32 root;
        uint8 tier;
        uint256 balance;
    }

    struct VerifyAuth {
        uint256 seasonId;
        uint64 dayIndex;
        bytes32 aiId;
        uint256 agentId;
        uint64 generation;
        bytes32 taskPackHash;
        uint8 verdict;
        uint256 nonce;
        uint64 deadline;
    }

    struct FindingAuth {
        uint256 seasonId;
        bytes32 reportEvidenceHash;
        bytes32 salt;
        bytes32 aiId;
        uint256 nonce;
        uint64 deadline;
    }

    struct Commit {
        bytes32 aiId;
        address committer;
        uint64 blockNumber;
        uint64 committedAt;
        uint64 publishedAt;
    }

    struct Accident {
        bool refunded;
        bool compensated;
    }

    // ---------------------------------------------------------------------
    // 错误
    // ---------------------------------------------------------------------

    error NotAdmin();
    error BadTime();
    error DayClosed();
    error RootFrozen();
    error BadRoot();
    error BadProof();
    error NotEligible();
    error BoundaryFull();
    error SeasonUsed();
    error NameTaken();
    error NameCheckFailed();
    error OutsidePool();
    error BadPrice();
    error BadSignature();
    error BadNonce();
    error AiRequired();
    error ZeroAddress();
    error EarnNotPaid();
    error AlreadyClaimed();
    error UnknownCommit();
    error CanonicalUsed();
    error CanonicalUnassigned();
    error ZeroCommit();
    error BadReveal();
    error StaleGeneration();
    error NotOrder();
    error StillPending();
    error SnapshotTooFresh();
    error StaleSnapshot();
    error ConfirmationsLocked();

    // ---------------------------------------------------------------------
    // 事件
    // ---------------------------------------------------------------------

    event DayRootSet(
        uint64 indexed dayIndex,
        bytes32 merkleRoot,
        uint64 snapshotBlock,
        bytes32 snapshotBlockHash,
        uint16 reservedCount,
        uint16 remainingSlots
    );

    event Redeemed(
        uint256 indexed orderId,
        bytes32 indexed aiId,
        address indexed applicant,
        address recipient,
        uint8 tld,
        string label,
        uint64 dayIndex,
        uint8 tier,
        uint256 price,
        bytes32 root
    );

    event FulfillmentAttested(
        uint256 indexed orderId,
        uint256 indexed tokenId,
        address indexed recipient,
        bytes32 mintTxHash
    );

    event Verified(
        bytes32 indexed aiId,
        uint64 indexed dayIndex,
        uint256 indexed agentId,
        uint64 generation,
        uint8 verdict,
        bytes32 taskPackHash,
        uint256 points
    );

    event FindingCommitted(
        bytes32 indexed commitHash,
        bytes32 indexed aiId,
        address indexed committer,
        bytes32 reportEvidenceHash
    );

    event CanonicalAssigned(bytes32 indexed reportEvidenceHash, bytes32 indexed canonicalRootCauseId);

    event FindingPaid(
        bytes32 indexed canonicalRootCauseId,
        bytes32 indexed reportEvidenceHash,
        bytes32 indexed aiId,
        address recipient,
        uint256 points
    );

    event ValidatorSet(address indexed account, bool allowed);
    event RewardSignerSet(address indexed account);
    event TaskPackSet(uint64 indexed dayIndex, bytes32 taskPackHash);

    event AccidentDeclared(
        uint256 indexed orderId,
        bytes32 indexed aiId,
        address indexed applicant,
        bytes32 evidenceHash
    );
    event AccidentRefunded(uint256 indexed orderId, bytes32 indexed aiId, uint256 amount);
    event AccidentCompensationDeferred(uint256 indexed orderId, bytes32 indexed aiId);
    event AccidentCompensated(uint256 indexed orderId, bytes32 indexed aiId, uint256 amount);

    // ---------------------------------------------------------------------
    // 不可变
    // ---------------------------------------------------------------------

    address public immutable admin;
    address public immutable points;
    address public immutable registrar;
    address public immutable identity;
    address public immutable aiRegistry;
    uint64 public immutable snapshotConfirmations;

    // ---------------------------------------------------------------------
    // 状态
    // ---------------------------------------------------------------------

    bool public redeemOpen;
    bool public rewardsOpen;

    uint256 private _nextOrderId = 1;

    mapping(bytes32 aiId => uint256 orderId) public seasonOrderOf;

    mapping(uint256 orderId => Order) private _orders;

    mapping(bytes32 nameKey => uint256 orderId) private _nameLock;

    mapping(uint64 dayIndex => DayMarket) private _dayMarket;

    mapping(bytes32 aiId => uint256 nonce) public nonces;

    mapping(bytes32 aiId => mapping(uint64 dayIndex => bool)) public verified;

    mapping(uint64 dayIndex => uint256 count) private _verifiedCount;

    mapping(bytes32 canonicalRootCauseId => bool) public canonicalClaimed;

    mapping(bytes32 reportEvidenceHash => bytes32 canonicalRootCauseId) public canonicalOf;

    mapping(bytes32 commitHash => Commit) private _commits;

    mapping(bytes32 reportEvidenceHash => bytes32 commitHash) private _commitByReport;

    mapping(uint256 orderId => Accident) private _accidents;

    mapping(address account => bool) public validators;

    address public rewardSigner;

    mapping(uint64 dayIndex => bytes32 taskPackHash) private _taskPack;

    // ---------------------------------------------------------------------
    // EIP-712 类型哈希
    // ---------------------------------------------------------------------

    bytes32 private constant APPLY_AUTH_TYPEHASH = keccak256(
        "ApplyAuth(uint256 seasonId,uint64 dayIndex,bytes32 aiId,string label,uint8 tld,uint256 price,address recipient,uint256 nonce,uint64 deadline,bytes32 root,uint8 tier,uint256 balance)"
    );

    bytes32 private constant VERIFY_AUTH_TYPEHASH = keccak256(
        "VerifyAuth(uint256 seasonId,uint64 dayIndex,bytes32 aiId,uint256 agentId,uint64 generation,bytes32 taskPackHash,uint8 verdict,uint256 nonce,uint64 deadline)"
    );

    bytes32 private constant FINDING_AUTH_TYPEHASH = keccak256(
        "FindingAuth(uint256 seasonId,bytes32 reportEvidenceHash,bytes32 salt,bytes32 aiId,uint256 nonce,uint64 deadline)"
    );

    // ---------------------------------------------------------------------
    // 构造
    // ---------------------------------------------------------------------

    constructor(
        address admin_,
        address points_,
        address registrar_,
        address identity_,
        address aiRegistry_,
        uint64 snapshotConfirmations_
    ) EIP712("HahaSeason1", "1") {
        if (
            admin_ == address(0) || points_ == address(0) || registrar_ == address(0)
                || identity_ == address(0) || aiRegistry_ == address(0)
        ) {
            revert ZeroAddress();
        }
        admin = admin_;
        points = points_;
        registrar = registrar_;
        identity = identity_;
        aiRegistry = aiRegistry_;
        snapshotConfirmations = snapshotConfirmations_;
    }

    // ---------------------------------------------------------------------
    // 修饰符
    // ---------------------------------------------------------------------

    modifier onlyAdmin() {
        if (msg.sender != admin) revert NotAdmin();
        _;
    }

    // ---------------------------------------------------------------------
    // 兑换
    // ---------------------------------------------------------------------

    function applyFor(ApplyAuth calldata auth, bytes calldata signature, bytes32[] calldata proof)
        external
        nonReentrant
        returns (uint256 orderId)
    {
        if (!redeemOpen) revert DayClosed();
        // 1. 时间窗口
        if (block.timestamp < START_TS || block.timestamp >= END_TS) revert BadTime();
        // 2. 当天
        uint64 day = uint64(block.timestamp / 86400);
        if (auth.dayIndex != day || day < FIRST_DAY || day > LAST_DAY) revert BadTime();
        // 3. deadline 是窗口结束
        if (auth.deadline != (auth.dayIndex + 1) * 86400) revert BadTime();
        // 4. seasonId / price / root / opened
        DayMarket storage m = _dayMarket[day];
        if (auth.seasonId != SEASON_ID) revert BadTime();
        if (auth.price != PRICE) revert BadPrice();
        if (!m.opened) revert DayClosed();
        if (auth.root != m.merkleRoot) revert BadRoot();
        // 5. recipient
        if (auth.recipient == address(0)) revert ZeroAddress();
        // 6. 标签 2 位，纯数字或纯小写字母
        if (!_isPoolLabel(auth.label)) revert OutsidePool();
        // 7. tld
        if (auth.tld > 1) revert OutsidePool();
        // 8. tier 合法
        if (auth.tier > 1) revert BadProof();
        // 9. 名字未铸造
        uint256 tokenId = _tokenId(auth.tld, auth.label);
        if (_isMinted(tokenId)) revert NameTaken();
        // 10. 模块内未锁定
        if (_nameLock[_nameKey(auth.tld, auth.label)] != 0) revert NameTaken();
        // 11. 季名额
        if (seasonOrderOf[auth.aiId] != 0) revert SeasonUsed();
        // 12. Merkle 证明
        bytes32 leaf = _leaf(auth.aiId, auth.balance, auth.tier);
        if (!MerkleProof.verify(proof, m.merkleRoot, leaf)) revert BadProof();
        // 13. 边界组名额
        if (auth.tier == uint8(Tier.Boundary)) {
            if (m.boundaryFilled >= m.remainingSlots) revert BoundaryFull();
        }
        // 14. .ai 三重核对
        HahaAiIdentity.Result memory r = _aiOf(msg.sender);
        if (!r.ok || r.aiId != auth.aiId) revert AiRequired();
        // 15. nonce
        if (auth.nonce != nonces[auth.aiId]) revert BadNonce();
        // 16. 签名（恢复地址必须是 msg.sender）
        _verifyUserSig(_hashApplyAuth(auth), signature);

        // 写状态
        nonces[auth.aiId]++;
        orderId = _nextOrderId++;
        _orders[orderId] = Order({
            aiId: auth.aiId,
            applicant: msg.sender,
            recipient: auth.recipient,
            tld: auth.tld,
            label: auth.label,
            dayIndex: auth.dayIndex,
            createdAt: uint64(block.timestamp),
            status: OrderStatus.Pending,
            tier: auth.tier == uint8(Tier.Boundary) ? Tier.Boundary : Tier.Reserved
        });
        seasonOrderOf[auth.aiId] = orderId;
        _nameLock[_nameKey(auth.tld, auth.label)] = orderId;

        if (auth.tier == uint8(Tier.Boundary)) {
            m.boundaryFilled++;
        } else {
            m.reservedFilled++;
        }

        // 扣分
        ISeason1Points(points).spend(msg.sender, PRICE, REASON_REDEEM);

        emit Redeemed(
            orderId,
            auth.aiId,
            msg.sender,
            auth.recipient,
            auth.tld,
            auth.label,
            auth.dayIndex,
            auth.tier,
            auth.price,
            auth.root
        );
    }

    function setDayRoot(
        uint64 dayIndex,
        bytes32 merkleRoot,
        uint64 snapshotBlock,
        bytes32 snapshotBlockHash,
        uint16 reservedCount,
        uint16 remainingSlots
    ) external onlyAdmin {
        if (dayIndex < FIRST_DAY || dayIndex > LAST_DAY) revert BadTime();
        DayMarket storage m = _dayMarket[dayIndex];
        if (m.reservedFilled + m.boundaryFilled != 0) revert RootFrozen();
        if (reservedCount + remainingSlots > DAILY_MAX) revert BadRoot();
        bool empty = merkleRoot == bytes32(0) && reservedCount == 0 && remainingSlots == 0;
        if (!empty && reservedCount + remainingSlots == 0) revert BadRoot();
        if (snapshotBlock == 0) revert BadRoot();
        if (block.number < snapshotBlock + snapshotConfirmations) revert SnapshotTooFresh();
        // EVM 只能读取最近 256 个块的 blockhash；超过则 blockhash(snapshotBlock) 返回 0，
        // 校验会失效，必须显式拒绝，防止用过期快照块 + 伪造的 0 哈希绕过校验。
        if (block.number >= snapshotBlock + 256) revert StaleSnapshot();
        if (blockhash(snapshotBlock) != snapshotBlockHash) revert BadRoot();

        m.merkleRoot = merkleRoot;
        m.snapshotBlock = snapshotBlock;
        m.snapshotBlockHash = snapshotBlockHash;
        m.reservedCount = reservedCount;
        m.remainingSlots = remainingSlots;
        m.boundaryFilled = 0;
        m.reservedFilled = 0;
        m.opened = true;

        emit DayRootSet(dayIndex, merkleRoot, snapshotBlock, snapshotBlockHash, reservedCount, remainingSlots);
    }

    function attestFulfillment(uint256 orderId, bytes32 mintTxHash) external onlyAdmin {
        Order storage o = _orders[orderId];
        if (o.status == OrderStatus.Fulfilled) return; // 幂等
        if (o.status != OrderStatus.Pending) revert StillPending();
        if (mintTxHash == bytes32(0)) revert ZeroAddress();

        uint256 tokenId = _tokenId(o.tld, o.label);
        o.status = OrderStatus.Fulfilled;
        emit FulfillmentAttested(orderId, tokenId, o.recipient, mintTxHash);
    }

    function currentOwnerMatches(uint256 orderId) external view returns (bool) {
        Order storage o = _orders[orderId];
        if (o.status == OrderStatus.None) return false;
        uint256 tokenId = _tokenId(o.tld, o.label);
        // isMinted 失败视为未查清，返回 false（view 不 revert）
        (bool ok, bytes memory ret) =
            registrar.staticcall(abi.encodeWithSignature("isMinted(bytes32)", bytes32(tokenId)));
        if (!ok || ret.length != 32) return false;
        bool minted = abi.decode(ret, (bool));
        if (!minted) return false;
        (bool ok2, bytes memory ret2) =
            registrar.staticcall(abi.encodeWithSignature("ownerOf(uint256)", tokenId));
        if (!ok2 || ret2.length != 32) return false;
        address owner = abi.decode(ret2, (address));
        return owner == o.recipient;
    }

    // ---------------------------------------------------------------------
    // 每日验证与找错
    // ---------------------------------------------------------------------

    function setTaskPack(uint64 dayIndex, bytes32 taskPackHash) external {
        if (msg.sender != admin && !validators[msg.sender]) revert NotAdmin();
        if (_verifiedCount[dayIndex] != 0) revert ConfirmationsLocked();
        _taskPack[dayIndex] = taskPackHash;
        emit TaskPackSet(dayIndex, taskPackHash);
    }

    function claimVerification(VerifyAuth calldata auth, bytes calldata signature) external nonReentrant {
        if (!rewardsOpen) revert DayClosed();
        if (block.timestamp < START_TS || block.timestamp >= END_TS) revert BadTime();
        uint64 day = uint64(block.timestamp / 86400);
        if (auth.dayIndex != day) revert BadTime();
        if (auth.deadline != (auth.dayIndex + 1) * 86400) revert BadTime();

        if (verified[auth.aiId][auth.dayIndex]) return; // 幂等

        if (auth.seasonId != SEASON_ID) revert BadTime();
        if (auth.verdict > 1) revert BadTime();
        if (_taskPack[auth.dayIndex] == bytes32(0) || _taskPack[auth.dayIndex] != auth.taskPackHash) {
            revert BadRoot();
        }

        uint64 gen = ISeason1Identity(identity).generationOf(auth.agentId);
        if (gen == 0 || gen != auth.generation) revert StaleGeneration();

        HahaAiIdentity.Result memory r = _aiOf(msg.sender);
        if (!r.ok || r.aiId != auth.aiId) revert AiRequired();

        if (auth.nonce != nonces[auth.aiId]) revert BadNonce();

        _verifyValidatorSig(_hashVerifyAuth(auth), signature);

        uint256 got = ISeason1Points(points).earn(ACTION_VERIFY, msg.sender, VERIFY_KEY);
        if (got == 0) revert EarnNotPaid();
        if (got != 30) revert EarnNotPaid();

        verified[auth.aiId][auth.dayIndex] = true;
        _verifiedCount[auth.dayIndex]++;
        nonces[auth.aiId]++;

        emit Verified(auth.aiId, auth.dayIndex, auth.agentId, auth.generation, auth.verdict, auth.taskPackHash, got);
    }

    function commitFinding(bytes32 reportEvidenceHash, bytes32 salt) external {
        if (reportEvidenceHash == bytes32(0) || salt == bytes32(0)) revert ZeroCommit();
        if (block.timestamp >= END_TS) revert BadTime();

        HahaAiIdentity.Result memory r = _aiOf(msg.sender);
        if (!r.ok) revert AiRequired();

        bytes32 commitHash =
            keccak256(abi.encode(block.chainid, address(this), SEASON_ID, r.aiId, reportEvidenceHash, salt));
        if (commitHash == bytes32(0)) revert ZeroCommit();
        if (_commits[commitHash].committer != address(0)) revert AlreadyClaimed();
        if (_commitByReport[reportEvidenceHash] != bytes32(0)) revert AlreadyClaimed();

        _commits[commitHash] = Commit({
            aiId: r.aiId,
            committer: msg.sender,
            blockNumber: uint64(block.number),
            committedAt: uint64(block.timestamp),
            publishedAt: 0
        });
        _commitByReport[reportEvidenceHash] = commitHash;

        emit FindingCommitted(commitHash, r.aiId, msg.sender, reportEvidenceHash);
    }

    function assignCanonical(bytes32 reportEvidenceHash, bytes32 canonicalRootCauseId) external {
        if (msg.sender != rewardSigner) revert NotAdmin();
        if (reportEvidenceHash == bytes32(0) || canonicalRootCauseId == bytes32(0)) revert ZeroCommit();
        canonicalOf[reportEvidenceHash] = canonicalRootCauseId;
        emit CanonicalAssigned(reportEvidenceHash, canonicalRootCauseId);
    }

    function publishRuling(bytes32 reportEvidenceHash) external {
        if (msg.sender != rewardSigner) revert NotAdmin();
        if (canonicalOf[reportEvidenceHash] == bytes32(0)) revert CanonicalUnassigned();

        bytes32 commitHash = _commitByReport[reportEvidenceHash];
        if (commitHash == bytes32(0)) revert UnknownCommit();
        Commit storage c = _commits[commitHash];
        if (block.timestamp > c.committedAt + FIND_REVEAL_WINDOW) revert BadTime();

        if (c.publishedAt == 0) {
            c.publishedAt = uint64(block.timestamp);
        }
    }

    function claimFinding(FindingAuth calldata auth, bytes calldata signature) external nonReentrant {
        if (!rewardsOpen) revert DayClosed();
        if (auth.seasonId != SEASON_ID) revert BadTime();

        bytes32 commitHash = keccak256(
            abi.encode(block.chainid, address(this), SEASON_ID, auth.aiId, auth.reportEvidenceHash, auth.salt)
        );
        Commit storage c = _commits[commitHash];
        if (c.committer == address(0)) revert UnknownCommit();
        if (c.aiId != auth.aiId) revert BadReveal();

        HahaAiIdentity.Result memory r = _aiOf(msg.sender);
        if (!r.ok || r.aiId != auth.aiId) revert AiRequired();

        if (c.publishedAt == 0) revert BadTime();
        uint64 claimStart = c.publishedAt + FIND_PUBLICITY;
        uint64 claimEnd = claimStart + FIND_CLAIM_WINDOW;
        if (block.timestamp < claimStart || block.timestamp >= claimEnd) revert BadTime();
        if (auth.deadline != claimEnd) revert BadTime();

        if (auth.nonce != nonces[auth.aiId]) revert BadNonce();

        _verifyRewardSignerSig(_hashFindingAuth(auth), signature);

        bytes32 canonicalId = canonicalOf[auth.reportEvidenceHash];
        if (canonicalId == bytes32(0)) revert CanonicalUnassigned();
        if (canonicalClaimed[canonicalId]) revert CanonicalUsed();

        uint256 got = ISeason1Points(points).earn(ACTION_FIND, msg.sender, canonicalId);
        if (got == 0) revert EarnNotPaid();
        if (got != 100) revert EarnNotPaid();

        canonicalClaimed[canonicalId] = true;
        nonces[auth.aiId]++;

        emit FindingPaid(canonicalId, auth.reportEvidenceHash, auth.aiId, msg.sender, got);
    }

    function setValidator(address account, bool allowed) external onlyAdmin {
        validators[account] = allowed;
        emit ValidatorSet(account, allowed);
    }

    function setRewardSigner(address account) external onlyAdmin {
        rewardSigner = account;
        emit RewardSignerSet(account);
    }

    // ---------------------------------------------------------------------
    // 事故
    // ---------------------------------------------------------------------

    function declareAccident(uint256 orderId, bytes32 evidenceHash) external onlyAdmin nonReentrant {
        if (evidenceHash == bytes32(0)) revert ZeroCommit();
        Order storage o = _orders[orderId];
        if (o.status != OrderStatus.Pending) revert StillPending();

        uint256 tokenId = _tokenId(o.tld, o.label);
        if (_isMinted(tokenId)) revert NameTaken();

        HahaAiIdentity.Result memory r = _aiOf(o.applicant);
        if (r.ok && r.aiId == o.aiId) {
            // 能通过原 aiId 的三重核对：先退 200
            ISeason1Points(points).refund(o.applicant, PRICE, REASON_REDEEM);
            o.status = OrderStatus.AccidentRefunded;
            _accidents[orderId].refunded = true;
            seasonOrderOf[o.aiId] = 0;
            _nameLock[_nameKey(o.tld, o.label)] = 0;

            emit AccidentDeclared(orderId, o.aiId, o.applicant, evidenceHash);
            emit AccidentRefunded(orderId, o.aiId, PRICE);

            uint256 got = ISeason1Points(points).earn(ACTION_ACCIDENT, o.applicant, bytes32(orderId));
            if (got == 0) {
                emit AccidentCompensationDeferred(orderId, o.aiId);
            } else {
                _accidents[orderId].compensated = true;
                o.status = OrderStatus.AccidentClosed;
                emit AccidentCompensated(orderId, o.aiId, got);
            }
        } else {
            // 不能通过三重核对：不退款，债权留在原 aiId 和原 applicant
            o.status = OrderStatus.CreditOpen;
            _nameLock[_nameKey(o.tld, o.label)] = 0;
            emit AccidentDeclared(orderId, o.aiId, o.applicant, evidenceHash);
        }
    }

    function claimAccidentCredit(uint256 orderId) external nonReentrant {
        Order storage o = _orders[orderId];
        if (o.status != OrderStatus.CreditOpen && o.status != OrderStatus.AccidentRefunded) revert StillPending();
        if (o.applicant != msg.sender) revert NotOrder();

        HahaAiIdentity.Result memory r = _aiOf(msg.sender);
        if (!r.ok || r.aiId != o.aiId) revert AiRequired();

        Accident storage a = _accidents[orderId];
        if (a.compensated) revert AlreadyClaimed();

        if (o.status == OrderStatus.CreditOpen) {
            ISeason1Points(points).refund(o.applicant, PRICE, REASON_REDEEM);
            a.refunded = true;
            o.status = OrderStatus.AccidentRefunded;
            seasonOrderOf[o.aiId] = 0;
            emit AccidentRefunded(orderId, o.aiId, PRICE);
        }
        // AccidentRefunded：只补 100，禁止第二次 refund（上面 CreditOpen 已退出）

        uint256 got = ISeason1Points(points).earn(ACTION_ACCIDENT, o.applicant, bytes32(orderId));
        if (got == 0) {
            emit AccidentCompensationDeferred(orderId, o.aiId);
            return;
        }
        a.compensated = true;
        o.status = OrderStatus.AccidentClosed;
        emit AccidentCompensated(orderId, o.aiId, got);
    }

    // ---------------------------------------------------------------------
    // 开关
    // ---------------------------------------------------------------------

    function setRedeemOpen(bool open) external onlyAdmin {
        redeemOpen = open;
    }

    function setRewardsOpen(bool open) external onlyAdmin {
        rewardsOpen = open;
    }

    // ---------------------------------------------------------------------
    // 读函数
    // ---------------------------------------------------------------------

    function order(uint256 orderId) external view returns (Order memory) {
        return _orders[orderId];
    }

    function nameLock(uint8 tld, string calldata label) external view returns (uint256) {
        return _nameLock[_nameKey(tld, label)];
    }

    function dayMarket(uint64 dayIndex) external view returns (DayMarket memory) {
        return _dayMarket[dayIndex];
    }

    function commitOf(bytes32 commitHash)
        external
        view
        returns (bytes32 aiId_, address committer, uint64 blockNumber, uint64 committedAt, uint64 publishedAt)
    {
        Commit storage c = _commits[commitHash];
        return (c.aiId, c.committer, c.blockNumber, c.committedAt, c.publishedAt);
    }

    function accidentOf(uint256 orderId) external view returns (bool refunded, bool compensated) {
        Accident storage a = _accidents[orderId];
        return (a.refunded, a.compensated);
    }

    function taskPack(uint64 dayIndex) external view returns (bytes32) {
        return _taskPack[dayIndex];
    }

    function verifiedCount(uint64 dayIndex) external view returns (uint256) {
        return _verifiedCount[dayIndex];
    }

    // ---------------------------------------------------------------------
    // 内部工具
    // ---------------------------------------------------------------------

    function _aiOf(address user) internal view returns (HahaAiIdentity.Result memory) {
        return HahaAiIdentity.aiIdentityOf(IBinanceAiRegistry(aiRegistry), user);
    }

    function _tokenId(uint8 tld, string memory label) internal pure returns (uint256) {
        return uint256(HahaNamehash.namehash(HahaNamehash.tldNode(tld), HahaNamehash.labelhash(label)));
    }

    function _nameKey(uint8 tld, string memory label) internal pure returns (bytes32) {
        return keccak256(abi.encodePacked(tld, label));
    }

    function _isPoolLabel(string memory label) internal pure returns (bool) {
        bytes memory b = bytes(label);
        if (b.length != 2) return false;
        bool allDigit = true;
        bool allLower = true;
        for (uint256 i = 0; i < 2; i++) {
            bytes1 c = b[i];
            if (!(c >= 0x30 && c <= 0x39)) allDigit = false;
            if (!(c >= 0x61 && c <= 0x7a)) allLower = false;
        }
        return allDigit || allLower;
    }

    function _isMinted(uint256 tokenId) internal view returns (bool) {
        (bool ok, bytes memory ret) =
            registrar.staticcall(abi.encodeWithSignature("isMinted(bytes32)", bytes32(tokenId)));
        if (!ok || ret.length != 32) revert NameCheckFailed();
        return abi.decode(ret, (bool));
    }

    function _leaf(bytes32 aiId, uint256 balance, uint8 tier) internal pure returns (bytes32) {
        return keccak256(abi.encodePacked(keccak256(abi.encode(aiId, balance, tier))));
    }

    function _hashApplyAuth(ApplyAuth calldata auth) internal view returns (bytes32) {
        return _hashTypedDataV4(
            keccak256(
                abi.encode(
                    APPLY_AUTH_TYPEHASH,
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
            )
        );
    }

    function _hashVerifyAuth(VerifyAuth calldata auth) internal view returns (bytes32) {
        return _hashTypedDataV4(
            keccak256(
                abi.encode(
                    VERIFY_AUTH_TYPEHASH,
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
            )
        );
    }

    function _hashFindingAuth(FindingAuth calldata auth) internal view returns (bytes32) {
        return _hashTypedDataV4(
            keccak256(
                abi.encode(
                    FINDING_AUTH_TYPEHASH,
                    auth.seasonId,
                    auth.reportEvidenceHash,
                    auth.salt,
                    auth.aiId,
                    auth.nonce,
                    auth.deadline
                )
            )
        );
    }

    function _verifyUserSig(bytes32 digest, bytes calldata signature) internal view {
        if (msg.sender.code.length == 0) {
            if (ECDSA.recover(digest, signature) != msg.sender) revert BadSignature();
        } else {
            if (IERC1271(msg.sender).isValidSignature(digest, signature) != 0x1626ba7e) revert BadSignature();
        }
    }

    function _verifyValidatorSig(bytes32 digest, bytes calldata signature) internal view {
        address signer = ECDSA.recover(digest, signature);
        if (!validators[signer]) revert BadSignature();
    }

    function _verifyRewardSignerSig(bytes32 digest, bytes calldata signature) internal view {
        address signer = ECDSA.recover(digest, signature);
        if (signer != rewardSigner) revert BadSignature();
    }
}

// ---------------------------------------------------------------------
// 最小接口（只读旧合约用到的函数）
// ---------------------------------------------------------------------

interface ISeason1Points {
    function spend(address user, uint256 amount, bytes32 reason) external;

    function earn(bytes32 actionId, address user, bytes32 uniqueKey) external returns (uint256 awarded);

    function refund(address user, uint256 amount, bytes32 reason) external;
}

interface ISeason1Identity {
    function generationOf(uint256 agentId) external view returns (uint64);
}
