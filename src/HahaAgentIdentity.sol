// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {ERC721} from "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import {IERC721} from "@openzeppelin/contracts/token/ERC721/IERC721.sol";
import {IERC165} from "@openzeppelin/contracts/utils/introspection/IERC165.sol";

import {HahaConstants} from "./libraries/HahaConstants.sol";
import {HahaNamehash} from "./libraries/HahaNamehash.sol";
import {HahaAiIdentity} from "./libraries/HahaAiIdentity.sol";
import {IHahaResolver} from "./interfaces/IHahaResolver.sol";
import {IHahaPoints} from "./interfaces/IHahaProtocol.sol";
import {IBinanceAiRegistry} from "./interfaces/IBinanceAiRegistry.sol";

contract HahaAgentIdentity is ERC721 {

    struct AgentView {
        address owner;
        bool active;
        uint256 nameTokenId;
        uint64 generation;
        bytes32 operatorAiId;
        address wallet;
        string uri;
    }


    error Soulbound();
    error NotNameOwner();
    error AgentAlreadyActive(uint256 agentId);
    error NoActiveAgent();
    error InvalidAgentURI(uint256 length);
    error NotRegistrar();
    error ZeroAddress();
    error AiRequired();
    error NotAuthorized();
    error OperatorIsOwner();
    error TooManyOperators(uint256 count);
    error InvalidTld(uint8 tld);


    event AgentActivated(
        uint256 indexed agentId,
        uint256 indexed nameTokenId,
        address indexed owner,
        bytes32 operatorAiId,
        uint64 generation,
        string agentURI
    );

    event URIUpdated(uint256 indexed agentId, string newURI, address indexed updatedBy);

    event AgentReset(uint256 indexed nameTokenId, uint256 indexed agentId, address indexed previousOwner);

    event AgentOperatorSet(uint256 indexed agentId, address indexed operator, bool allowed);


    mapping(uint256 nameTokenId => uint256 agentId) private _agentOfName;

    mapping(uint256 agentId => uint256 nameTokenId) private _nameOfAgent;

    mapping(uint256 agentId => bool) private _active;

    mapping(uint256 agentId => string) private _agentURI;

    mapping(uint256 agentId => bytes32) private _operatorAiId;

    mapping(uint256 agentId => uint64) private _generationOf;

    mapping(uint256 nameTokenId => uint64) private _nameGeneration;

    mapping(uint256 agentId => mapping(address operator => bool)) private _operators;

    mapping(uint256 agentId => uint8) private _operatorCount;

    mapping(uint256 agentId => address) private _lastOwner;

    uint256 private _nextAgentId = 1;


    address public immutable registrar;

    address public immutable resolver;

    address public immutable points;

    address public immutable aiRegistry;


    constructor(address registrar_, address resolver_, address points_, address aiRegistry_)
        ERC721("haha.meme Agent", "HAHAAGENT")
    {
        if (registrar_ == address(0) || resolver_ == address(0) || aiRegistry_ == address(0)) {
            revert ZeroAddress();
        }
        registrar = registrar_;
        resolver = resolver_;
        points = points_;
        aiRegistry = aiRegistry_;
    }


    function activateAgent(string calldata label, uint8 tld, string calldata agentURI)
        external
        returns (uint256 agentId)
    {
        if (tld > HahaConstants.TLD_MEME) revert InvalidTld(tld);

        bytes32 node = HahaNamehash.namehash(HahaNamehash.tldNode(tld), HahaNamehash.labelhash(label));
        uint256 nameTokenId = uint256(node);

        if (IERC721(registrar).ownerOf(nameTokenId) != msg.sender) revert NotNameOwner();

        if (_agentOfName[nameTokenId] != 0) revert AgentAlreadyActive(_agentOfName[nameTokenId]);

        uint256 uriLen = bytes(agentURI).length;
        if (uriLen == 0 || uriLen > HahaConstants.MAX_AGENT_URI_LENGTH) {
            revert InvalidAgentURI(uriLen);
        }

        HahaAiIdentity.Result memory ai =
            HahaAiIdentity.aiIdentityOf(IBinanceAiRegistry(aiRegistry), msg.sender);
        if (!ai.ok) revert AiRequired();

        agentId = _nextAgentId++;

        uint64 gen = _nameGeneration[nameTokenId] + 1;
        _nameGeneration[nameTokenId] = gen;
        _generationOf[agentId] = gen;

        _agentOfName[nameTokenId] = agentId;
        _nameOfAgent[agentId] = nameTokenId;
        _active[agentId] = true;
        _agentURI[agentId] = agentURI;
        _operatorAiId[agentId] = ai.aiId;

        _mint(msg.sender, agentId);

        emit AgentActivated(agentId, nameTokenId, msg.sender, ai.aiId, gen, agentURI);

        if (points != address(0)) {
            try IHahaPoints(points).earn(HahaConstants.ACTION_ACTIVATE, msg.sender, HahaConstants.ACTIVATE_ONCE)
            returns (uint256) {}
            catch {}
        }
    }

    function setAgentURI(uint256 agentId, string calldata newURI) external {
        if (!_active[agentId]) revert NoActiveAgent();
        if (!_isAuthorized(agentId, msg.sender)) revert NotAuthorized();

        uint256 uriLen = bytes(newURI).length;
        if (uriLen == 0 || uriLen > HahaConstants.MAX_AGENT_URI_LENGTH) {
            revert InvalidAgentURI(uriLen);
        }

        _agentURI[agentId] = newURI;
        emit URIUpdated(agentId, newURI, msg.sender);
    }

    function setAgentOperator(uint256 agentId, address operator, bool allowed) external {
        if (!_active[agentId]) revert NoActiveAgent();
        if (_ownerOf(agentId) != msg.sender) revert NotNameOwner();
        if (operator == address(0)) revert ZeroAddress();
        if (operator == msg.sender) revert OperatorIsOwner();

        bool current = _operators[agentId][operator];
        if (current == allowed) return;

        if (allowed) {
            uint8 count = _operatorCount[agentId];
            if (count >= HahaConstants.MAX_AGENT_OPERATORS) revert TooManyOperators(count);
            _operatorCount[agentId] = count + 1;
        } else {
            _operatorCount[agentId] = _operatorCount[agentId] - 1;
        }

        _operators[agentId][operator] = allowed;
        emit AgentOperatorSet(agentId, operator, allowed);
    }


    function deactivate(uint256 nameTokenId) external {
        if (msg.sender != registrar) revert NotRegistrar();

        uint256 agentId = _agentOfName[nameTokenId];
        if (agentId == 0) return;

        address previousOwner = _ownerOf(agentId);

        delete _agentOfName[nameTokenId];
        delete _active[agentId];
        if (previousOwner != address(0)) {
            _lastOwner[agentId] = previousOwner;
            _burn(agentId);
        }

        emit AgentReset(nameTokenId, agentId, previousOwner);
    }


    function agentOfName(uint256 nameTokenId) external view returns (uint256) {
        return _agentOfName[nameTokenId];
    }

    function nameTokenIdOf(uint256 agentId) external view returns (uint256) {
        return _nameOfAgent[agentId];
    }

    function isActive(uint256 agentId) external view returns (bool) {
        return _active[agentId];
    }

    function operatorAiIdOf(uint256 agentId) external view returns (bytes32) {
        return _operatorAiId[agentId];
    }

    function generationOf(uint256 agentId) external view returns (uint64) {
        return _generationOf[agentId];
    }

    function nameGeneration(uint256 nameTokenId) external view returns (uint64) {
        return _nameGeneration[nameTokenId];
    }

    function isAuthorized(uint256 agentId, address account) external view returns (bool) {
        return _isAuthorized(agentId, account);
    }

    function operatorCount(uint256 agentId) external view returns (uint8) {
        return _operatorCount[agentId];
    }

    function isAgentOperator(uint256 agentId, address operator) external view returns (bool) {
        return _operators[agentId][operator];
    }

    function getAgent(uint256 agentId) external view returns (AgentView memory v) {
        v.active = _active[agentId];
        v.nameTokenId = _nameOfAgent[agentId];
        v.generation = _generationOf[agentId];
        v.operatorAiId = _operatorAiId[agentId];
        v.uri = _agentURI[agentId];

        if (v.active) {
            v.owner = _ownerOf(agentId);
            v.wallet = IHahaResolver(resolver).addr(bytes32(v.nameTokenId));
        } else {
            v.owner = _lastOwner[agentId];
            v.wallet = address(0);
        }
    }

    function getAgentWallet(uint256 agentId) external view returns (address) {
        if (!_active[agentId]) return address(0);
        uint256 nameTokenId = _nameOfAgent[agentId];
        return IHahaResolver(resolver).addr(bytes32(nameTokenId));
    }

    function nextAgentId() external view returns (uint256) {
        return _nextAgentId;
    }

    function tokenURI(uint256 agentId) public view override returns (string memory) {
        if (!_active[agentId]) revert NoActiveAgent();
        return _agentURI[agentId];
    }


    function transferFrom(address, address, uint256) public pure override {
        revert Soulbound();
    }

    function safeTransferFrom(address, address, uint256, bytes memory) public pure override {
        revert Soulbound();
    }

    function approve(address, uint256) public pure override {
        revert Soulbound();
    }

    function setApprovalForAll(address, bool) public pure override {
        revert Soulbound();
    }


    function _isAuthorized(uint256 agentId, address account) private view returns (bool) {
        if (!_active[agentId]) return false;
        if (_ownerOf(agentId) == account) return true;
        return _operators[agentId][account];
    }

    function _update(address to, uint256 tokenId, address auth) internal override returns (address) {
        address from = _ownerOf(tokenId);
        if (from != address(0) && to != address(0)) revert Soulbound();
        return super._update(to, tokenId, auth);
    }
}
