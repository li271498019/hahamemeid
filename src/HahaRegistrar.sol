// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {ERC721} from "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import {IERC721} from "@openzeppelin/contracts/token/ERC721/IERC721.sol";
import {IERC2981} from "@openzeppelin/contracts/interfaces/IERC2981.sol";
import {IERC165} from "@openzeppelin/contracts/utils/introspection/IERC165.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

import {HahaConstants} from "./libraries/HahaConstants.sol";
import {HahaNamehash} from "./libraries/HahaNamehash.sol";
import {HahaAiIdentity} from "./libraries/HahaAiIdentity.sol";
import {IBinanceAiRegistry} from "./interfaces/IBinanceAiRegistry.sol";
import {IHahaRegistry} from "./interfaces/IHahaRegistry.sol";
import {IHahaResolver} from "./interfaces/IHahaResolver.sol";
import {
    IHahaMetadata,
    IHahaNamePolicy,
    IHahaPoints,
    IHahaAgentIdentity
} from "./interfaces/IHahaProtocol.sol";

contract HahaRegistrar is ERC721, IERC2981, ReentrancyGuard {

    error InvalidTld(uint8 tld);
    error InvalidCharset();
    error LabelTooLong(uint256 length, uint256 maxLength);
    error LabelTooShort(uint256 length, uint256 minLength);
    error Blacklisted();
    error ReservedName();
    error NotReserved();
    error NameTaken();
    error AiRequired();
    error CooldownActive(uint256 readyAt);
    error NotAdmin();
    error ZeroAddress();


    event NameMinted(
        uint256 indexed tokenId,
        address indexed owner,
        uint8 tld,
        bytes32 indexed aiId,
        string label,
        bool reservedMint
    );


    struct Name {
        string label;
        uint8 tld;
    }

    mapping(uint256 tokenId => Name) private _names;

    mapping(bytes32 aiId => uint256) public lastMintAt;


    address public immutable registry;

    address public immutable resolver;

    address public immutable metadata;

    address public immutable points;

    address public immutable identity;

    address public immutable policy;

    address public immutable aiRegistry;

    address public immutable admin;

    address public immutable feeReceiver;


    modifier onlyAdmin() {
        if (msg.sender != admin) revert NotAdmin();
        _;
    }


    constructor(bytes memory cfg) ERC721("haha id", "HAHAID") {
        (
            address registry_,
            address resolver_,
            address metadata_,
            address points_,
            address identity_,
            address policy_,
            address aiRegistry_,
            address admin_,
            address feeReceiver_
        ) = abi.decode(cfg, (address, address, address, address, address, address, address, address, address));

        if (
            registry_ == address(0) || resolver_ == address(0) || metadata_ == address(0)
                || points_ == address(0) || identity_ == address(0) || policy_ == address(0)
                || aiRegistry_ == address(0) || admin_ == address(0) || feeReceiver_ == address(0)
        ) revert ZeroAddress();

        registry = registry_;
        resolver = resolver_;
        metadata = metadata_;
        points = points_;
        identity = identity_;
        policy = policy_;
        aiRegistry = aiRegistry_;
        admin = admin_;
        feeReceiver = feeReceiver_;
    }


    function register(string calldata label, uint8 tld) external nonReentrant {
        if (tld > HahaConstants.TLD_MEME) revert InvalidTld(tld);
        _requireValidLabel(label, HahaConstants.MIN_PUBLIC_LENGTH);

        if (IHahaNamePolicy(policy).isBlacklisted(label)) revert Blacklisted();
        if (IHahaNamePolicy(policy).isReserved(label)) revert ReservedName();

        bytes32 node = HahaNamehash.namehash(HahaNamehash.tldNode(tld), HahaNamehash.labelhash(label));
        if (_exists(node)) revert NameTaken();

        HahaAiIdentity.Result memory ai = HahaAiIdentity.aiIdentityOf(IBinanceAiRegistry(aiRegistry), msg.sender);
        if (!ai.ok) revert AiRequired();

        uint256 last = lastMintAt[ai.aiId];
        if (last != 0 && block.timestamp < last + HahaConstants.COOLDOWN) {
            revert CooldownActive(last + HahaConstants.COOLDOWN);
        }
        lastMintAt[ai.aiId] = block.timestamp;

        _mintAndRecord(label, tld, node, msg.sender, ai.aiId, false);

        IHahaPoints(points).creditMintReward(msg.sender, ai.aiId);
    }

    function adminMint(string calldata label, uint8 tld, address to) external onlyAdmin nonReentrant {
        if (tld > HahaConstants.TLD_MEME) revert InvalidTld(tld);
        if (to == address(0)) revert ZeroAddress();
        _requireValidLabel(label, 1);

        if (IHahaNamePolicy(policy).isBlacklisted(label)) revert Blacklisted();

        uint256 len = bytes(label).length;
        if (len >= HahaConstants.MIN_PUBLIC_LENGTH) {
            if (!IHahaNamePolicy(policy).isReserved(label)) revert NotReserved();
        }

        bytes32 node = HahaNamehash.namehash(HahaNamehash.tldNode(tld), HahaNamehash.labelhash(label));
        if (_exists(node)) revert NameTaken();

        _mintAndRecord(label, tld, node, to, bytes32(0), true);
    }


    function _update(address to, uint256 tokenId, address auth) internal override returns (address) {
        address from = _ownerOf(tokenId);
        address previous = super._update(to, tokenId, auth);

        if (from != address(0)) {
            if (to == address(0)) {
                revert ERC721InvalidReceiver(address(0));
            }
            bytes32 node = bytes32(tokenId);
            IHahaRegistry(registry).syncOwner(node, to);
            IHahaResolver(resolver).clearRecords(node);
            IHahaAgentIdentity(identity).deactivate(tokenId);
        }

        return previous;
    }


    function nameParts(uint256 tokenId) external view returns (string memory label, uint8 tld) {
        _requireOwned(tokenId);
        Name storage n = _names[tokenId];
        return (n.label, n.tld);
    }

    function isMinted(bytes32 node) external view returns (bool) {
        return _exists(node);
    }

    function nodeOf(string calldata label, uint8 tld) external pure returns (bytes32) {
        if (tld > HahaConstants.TLD_MEME) revert InvalidTld(tld);
        return HahaNamehash.namehash(HahaNamehash.tldNode(tld), HahaNamehash.labelhash(label));
    }

    function available(string calldata label, uint8 tld) external view returns (bool) {
        if (tld > HahaConstants.TLD_MEME) return false;
        if (!HahaNamehash.isValidLabel(label)) return false;
        if (!HahaNamehash.isLengthInRange(label, 1, HahaConstants.MAX_LABEL_LENGTH)) return false;
        bytes32 node = HahaNamehash.namehash(HahaNamehash.tldNode(tld), HahaNamehash.labelhash(label));
        return !_exists(node);
    }

    function nextMintAt(bytes32 aiId) external view returns (uint256) {
        uint256 last = lastMintAt[aiId];
        if (last == 0) return 0;
        return last + HahaConstants.COOLDOWN;
    }


    function royaltyInfo(uint256, uint256 salePrice) external view returns (address, uint256) {
        return (feeReceiver, (salePrice * HahaConstants.FEE_BPS) / HahaConstants.BPS_DENOMINATOR);
    }

    function supportsInterface(bytes4 interfaceId) public view override(ERC721, IERC165) returns (bool) {
        return interfaceId == type(IERC2981).interfaceId || super.supportsInterface(interfaceId);
    }


    function _requireValidLabel(string calldata label, uint256 minLen) private pure {
        if (!HahaNamehash.isValidLabel(label)) revert InvalidCharset();
        uint256 len = bytes(label).length;
        if (len > HahaConstants.MAX_LABEL_LENGTH) {
            revert LabelTooLong(len, HahaConstants.MAX_LABEL_LENGTH);
        }
        if (len < minLen) revert LabelTooShort(len, minLen);
    }

    function _mintAndRecord(
        string calldata label,
        uint8 tld,
        bytes32 node,
        address receiver,
        bytes32 aiId,
        bool reservedMint
    ) private {
        uint256 tokenId = uint256(node);

        _mint(receiver, tokenId);
        _names[tokenId] = Name({label: label, tld: tld});

        IHahaRegistry(registry).createName(
            HahaNamehash.tldNode(tld), HahaNamehash.labelhash(label), receiver
        );

        emit NameMinted(tokenId, receiver, tld, aiId, label, reservedMint);
    }

    function _exists(bytes32 node) private view returns (bool) {
        return _ownerOf(uint256(node)) != address(0);
    }
}
