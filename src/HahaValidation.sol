// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {IHahaAgentIdentity} from "./interfaces/IHahaProtocol.sol";

/// @title HahaValidation
/// @notice G13 验证注册表（Validation Registry），实现 EIP-8004 标准 Validation Registry 接口。
///
///         让第三方能验证 agent 的声明是否真实。验证结果存在本合约里，任何人都能查。
///
/// v1 简化（L 已定，2026-11-25）：
///   - 管理员为唯一验证者，中心化；无质押、无奖励、无惩罚。
///   - 争议就是验证者第二次复核：第二次与第一次一样维持原判，不一样则改判。
///   - 争议窗口 3 天（自第一次结果起算），每个请求最多争议一次。
///   - 只做两类验证：接口可达（endpoint-reachable）与身份真实性（identity-verified）。
///
/// 标准接口（EIP-8004 Validation Registry，逐字核对）：
///   - validationRequest(address validatorAddress, uint256 agentId, string requestURI, bytes32 requestHash)
///   - validationResponse(bytes32 requestHash, uint8 response, string responseURI, bytes32 responseHash, string tag)
///   - getValidationStatus(bytes32) returns (validatorAddress, agentId, response, responseHash, tag, lastUpdate)
///   - getSummary(uint256, address[], string) returns (uint64 count, uint8 averageResponse)
///   - getAgentValidations(uint256) returns (bytes32[])
///   - getValidatorRequests(address) returns (bytes32[])
///   - 事件：ValidationRequest / ValidationResponse（含 indexed）
///
/// v1 新增（非标准，L 已定）：dispute / setValidator / ValidationDisputed 事件。
contract HahaValidation {
    // ---------------------------------------------------------------------
    // 常量
    // ---------------------------------------------------------------------

    /// @notice 争议窗口：第一次结果提交后 3 天内可争议。
    uint64 public constant DISPUTE_WINDOW = 3 days;

    // ---------------------------------------------------------------------
    // 存储结构
    // ---------------------------------------------------------------------

    /// @notice 一次验证请求的完整状态。
    /// @dev 标准存储字段（EIP-8004 Validation Response 一节）：
    ///      requestHash、validatorAddress、agentId、response、responseHash、
    ///      lastUpdate、tag。v1 另存 firstResponseTime 与 disputed（见 §5.1）。
    struct Validation {
        address validatorAddress;
        uint256 agentId;
        uint8 response; // 0–100 分数；0 表示尚未回应
        bytes32 responseHash;
        uint256 lastUpdate;
        string tag;
        uint64 firstResponseTime; // 第一次 validationResponse 的区块时间，之后不再变
        bool disputed; // 是否已争议过（最多一次）
        bool exists; // 该 requestHash 是否已登记
    }

    // ---------------------------------------------------------------------
    // 事件
    // ---------------------------------------------------------------------

    /// @notice 发起验证请求时发（EIP-8004 Validation Request 一节）。
    event ValidationRequest(
        address indexed validatorAddress, uint256 indexed agentId, string requestURI, bytes32 indexed requestHash
    );

    /// @notice 验证者提交结果时发（每次调用都发；EIP-8004 Validation Response 一节）。
    event ValidationResponse(
        address indexed validatorAddress,
        uint256 indexed agentId,
        bytes32 indexed requestHash,
        uint8 response,
        string responseURI,
        bytes32 responseHash,
        string tag
    );

    /// @notice 任何人标记争议时发（v1 新增，非标准事件）。
    event ValidationDisputed(bytes32 indexed requestHash, address indexed disputer);

    // ---------------------------------------------------------------------
    // 错误
    // ---------------------------------------------------------------------

    error ZeroAddress();
    error NotAdmin();
    error NotAuthorized(); // validationRequest 非 owner/operator
    error NotValidator(); // validationResponse 非验证者
    error InvalidRequestHash(bytes32 expected, bytes32 provided);
    error RequestAlreadyExists(bytes32 requestHash);
    error RequestNotFound(bytes32 requestHash);
    error ResponseOutOfRange(uint8 response);
    error NoResultYet(bytes32 requestHash); // dispute：无验证结果
    error DisputeWindowExpired(bytes32 requestHash, uint64 deadline);
    error AlreadyDisputed(bytes32 requestHash);

    // ---------------------------------------------------------------------
    // 状态
    // ---------------------------------------------------------------------

    /// @notice 合约管理员（= HahaRegistrar 的 admin），immutable，部署时写死。
    address public immutable admin;

    /// @notice identity 注册表（HahaAgentIdentity），immutable。
    address public immutable identity;

    /// @notice 当前验证者地址（public 存储变量），初始为管理员。
    address public validator;

    /// @notice 全部验证请求状态。
    mapping(bytes32 requestHash => Validation) private _validations;

    /// @notice 每个 agent 的全部请求哈希。
    mapping(uint256 agentId => bytes32[]) private _agentRequests;

    /// @notice 每个验证者的全部请求哈希。
    mapping(address validatorAddress => bytes32[]) private _validatorRequests;

    // ---------------------------------------------------------------------
    // 构造函数
    // ---------------------------------------------------------------------

    constructor(address admin_, address identity_) {
        if (admin_ == address(0) || identity_ == address(0)) revert ZeroAddress();
        admin = admin_;
        identity = identity_;
        validator = admin_;
    }

    // ---------------------------------------------------------------------
    // 修饰符
    // ---------------------------------------------------------------------

    modifier onlyAdmin() {
        if (msg.sender != admin) revert NotAdmin();
        _;
    }

    // ---------------------------------------------------------------------
    // 标准接口：initialize / getIdentityRegistry
    // ---------------------------------------------------------------------

    /// @notice identity 注册表地址（EIP-8004，定义见 Reputation Registry 一节）。
    /// @dev v1 用 immutable 写死，部署时即设好，无需 initialize。
    function getIdentityRegistry() external view returns (address) {
        return identity;
    }

    // ---------------------------------------------------------------------
    // 标准接口：写
    // ---------------------------------------------------------------------

    /// @notice 发起一次验证请求（EIP-8004 Validation Request 一节）。
    /// @param validatorAddress 指定验证者（v1 必须等于当前 validator，否则 revert）。
    /// @param agentId 被验证的 agent。
    /// @param requestURI 请求文档 URL（https:// 或 ipfs://）。
    /// @param requestHash 请求数据承诺，链下按 §3.4 公式算好传入，合约链上验算。
    function validationRequest(
        address validatorAddress,
        uint256 agentId,
        string calldata requestURI,
        bytes32 requestHash
    ) external {
        // 标准 MUST：由 agent 的 owner 或 operator 调
        if (!IHahaAgentIdentity(identity).isAuthorized(agentId, msg.sender)) revert NotAuthorized();

        // v1：只认管理员（当前验证者）
        if (validatorAddress != validator) revert NotValidator();

        // requestHash 链上验算（§3.4 公式）
        bytes32 expected = keccak256(abi.encodePacked(validatorAddress, agentId, requestURI));
        if (requestHash != expected) revert InvalidRequestHash(expected, requestHash);

        // 重复 requestHash revert（G12）
        Validation storage v = _validations[requestHash];
        if (v.exists) revert RequestAlreadyExists(requestHash);

        v.exists = true;
        v.validatorAddress = validatorAddress;
        v.agentId = agentId;

        _agentRequests[agentId].push(requestHash);
        _validatorRequests[validatorAddress].push(requestHash);

        emit ValidationRequest(validatorAddress, agentId, requestURI, requestHash);
    }

    /// @notice 验证者提交验证结果（EIP-8004 Validation Response 一节）。
    /// @dev 标准 MUST：由请求里指定的 validatorAddress 调。可多次调用（更新结果）。
    function validationResponse(
        bytes32 requestHash,
        uint8 response,
        string calldata responseURI,
        bytes32 responseHash,
        string calldata tag
    ) external {
        Validation storage v = _validations[requestHash];
        if (!v.exists) revert RequestNotFound(requestHash);
        if (msg.sender != v.validatorAddress) revert NotValidator();
        if (response > 100) revert ResponseOutOfRange(response);

        if (v.firstResponseTime == 0) {
            v.firstResponseTime = uint64(block.timestamp);
        }
        v.response = response;
        v.responseHash = responseHash;
        v.lastUpdate = block.timestamp;
        v.tag = tag;

        emit ValidationResponse(v.validatorAddress, v.agentId, requestHash, response, responseURI, responseHash, tag);
    }

    // ---------------------------------------------------------------------
    // 标准接口：读
    // ---------------------------------------------------------------------

    /// @notice 查一次验证请求的状态（最新结果）。
    function getValidationStatus(bytes32 requestHash)
        external
        view
        returns (
            address validatorAddress,
            uint256 agentId,
            uint8 response,
            bytes32 responseHash,
            string memory tag,
            uint256 lastUpdate
        )
    {
        Validation storage v = _validations[requestHash];
        if (!v.exists) revert RequestNotFound(requestHash);
        return (v.validatorAddress, v.agentId, v.response, v.responseHash, v.tag, v.lastUpdate);
    }

    /// @notice 按 agent 查验证汇总（count 为符合过滤的请求数，averageResponse 为最新结果的平均，整数除法）。
    /// @param validatorAddresses 可选过滤（空数组 = 不过滤）。
    /// @param tag 可选过滤（空字符串 = 不过滤）。
    function getSummary(uint256 agentId, address[] calldata validatorAddresses, string calldata tag)
        external
        view
        returns (uint64 count, uint8 averageResponse)
    {
        bool filterValidator = validatorAddresses.length > 0;
        bool filterTag = bytes(tag).length > 0;

        bytes32[] storage hashes = _agentRequests[agentId];
        uint256 total = 0;
        uint64 n = 0;

        for (uint256 i = 0; i < hashes.length; i++) {
            Validation storage v = _validations[hashes[i]];

            if (filterValidator) {
                bool matched = false;
                for (uint256 j = 0; j < validatorAddresses.length; j++) {
                    if (v.validatorAddress == validatorAddresses[j]) {
                        matched = true;
                        break;
                    }
                }
                if (!matched) continue;
            }
            if (filterTag && keccak256(bytes(v.tag)) != keccak256(bytes(tag))) continue;

            total += v.response;
            n++;
        }

        count = n;
        if (n > 0) averageResponse = uint8(total / n);
    }

    /// @notice 查一个 agent 的全部验证请求哈希。
    function getAgentValidations(uint256 agentId) external view returns (bytes32[] memory) {
        return _agentRequests[agentId];
    }

    /// @notice 查一个验证者的全部验证请求哈希。
    function getValidatorRequests(address validatorAddress) external view returns (bytes32[] memory) {
        return _validatorRequests[validatorAddress];
    }

    // ---------------------------------------------------------------------
    // v1 新增（非标准）
    // ---------------------------------------------------------------------

    /// @notice 标记一次验证结果有争议（任何人可调）。争议就是验证者第二次复核。
    /// @dev 前置：已有至少一次 validationResponse，且未争议过，且在 3 天争议窗口内。
    function dispute(bytes32 requestHash) external {
        Validation storage v = _validations[requestHash];
        if (!v.exists) revert RequestNotFound(requestHash);
        if (v.firstResponseTime == 0) revert NoResultYet(requestHash);
        if (v.disputed) revert AlreadyDisputed(requestHash);

        uint64 deadline = v.firstResponseTime + DISPUTE_WINDOW;
        if (block.timestamp > deadline) revert DisputeWindowExpired(requestHash, deadline);

        v.disputed = true;
        emit ValidationDisputed(requestHash, msg.sender);
    }

    /// @notice 管理员更换验证者（新地址不能为零地址）。
    function setValidator(address newValidator) external onlyAdmin {
        if (newValidator == address(0)) revert ZeroAddress();
        validator = newValidator;
    }
}
