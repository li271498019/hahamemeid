// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {ERC721} from "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import {IERC2981} from "@openzeppelin/contracts/interfaces/IERC2981.sol";
import {IERC165} from "@openzeppelin/contracts/utils/introspection/IERC165.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

import {HahaConstants} from "../libraries/HahaConstants.sol";
import {HahaAiIdentity} from "../libraries/HahaAiIdentity.sol";
import {IBinanceAiRegistry} from "../interfaces/IBinanceAiRegistry.sol";
import {IHahaRegistrar} from "../interfaces/IHahaProtocol.sol";
import {IHahaDogRenderer} from "../interfaces/IHahaDog.sol";

contract HahaDog is ERC721, IERC2981, ReentrancyGuard {

    error AiRequired();
    error QuotaExceeded(uint256 allowed, uint256 used);
    error SoldOut();
    error BadQuantity();
    error NotTokenOwner();
    error ZeroAddress();

    event Committed(uint256 indexed tokenId, uint256 rerolls, uint256 commitBlock);
    event Snapshot(uint256 indexed blockNumber, bytes32 blockHash);

    uint8 public constant STATUS_NONE = 0;
    uint8 public constant STATUS_GENERATING = 1;
    uint8 public constant STATUS_READY = 2;
    uint8 public constant STATUS_STALLED = 3;

    uint256 public constant MAX_SUPPLY = 10_000;
    uint256 public constant MAX_PER_AI = 2;
    uint256 public constant SEED_DELAY = 4;
    uint256 public constant AUTO_SNAPSHOTS = 3;

    struct Dog {
        uint64 commitBlock;
        uint32 rerolls;
    }

    mapping(uint256 tokenId => Dog) private _dogs;

    mapping(uint256 blockNumber => bytes32) public snapshots;

    mapping(bytes32 aiId => uint256) public mintedByAi;


    uint256 public totalSupply;

    uint256[] private _queue;

    uint256 public queueHead;

    address public immutable renderer;

    address public immutable aiRegistry;

    address public immutable registrar;

    address public immutable feeReceiver;

    address public immutable blockHistory;

    constructor(
        address renderer_,
        address aiRegistry_,
        address registrar_,
        address feeReceiver_,
        address blockHistory_
    ) ERC721("Haha Dog", "HAHADOG") {
        if (
            renderer_ == address(0) || aiRegistry_ == address(0) || registrar_ == address(0)
                || feeReceiver_ == address(0)
        ) revert ZeroAddress();
        renderer = renderer_;
        aiRegistry = aiRegistry_;
        registrar = registrar_;
        feeReceiver = feeReceiver_;
        blockHistory = blockHistory_;
    }

    function mint(uint256 quantity) external nonReentrant {
        if (quantity == 0 || quantity > MAX_PER_AI) revert BadQuantity();
        HahaAiIdentity.Result memory ai = HahaAiIdentity.aiIdentityOf(IBinanceAiRegistry(aiRegistry), msg.sender);
        if (!ai.ok) revert AiRequired();

        uint256 allowed = _quota(msg.sender);
        uint256 used = mintedByAi[ai.aiId];
        if (used + quantity > allowed) revert QuotaExceeded(allowed, used);
        if (totalSupply + quantity > MAX_SUPPLY) revert SoldOut();

        mintedByAi[ai.aiId] += quantity;

        _processQueue(AUTO_SNAPSHOTS);
        for (uint256 i; i < quantity; ++i) {
            uint256 tokenId = ++totalSupply;
            _commit(tokenId, 0);
            _safeMint(msg.sender, tokenId);
        }
    }

    function reroll(uint256 tokenId) external nonReentrant {
        if (ownerOf(tokenId) != msg.sender) revert NotTokenOwner();
        _processQueue(AUTO_SNAPSHOTS);
        _commit(tokenId, uint256(_dogs[tokenId].rerolls) + 1);
    }

    function snapshot(uint256[] calldata tokenIds) external returns (uint256 stored) {
        for (uint256 i; i < tokenIds.length; ++i) {
            if (_snapshotToken(tokenIds[i])) ++stored;
        }
    }

    function processQueue(uint256 maxSteps) external returns (uint256 newHead) {
        _processQueue(maxSteps);
        return queueHead;
    }

    function quotaOf(address account) external view returns (uint256 allowed, uint256 used) {
        HahaAiIdentity.Result memory ai = HahaAiIdentity.aiIdentityOf(IBinanceAiRegistry(aiRegistry), account);
        if (!ai.ok) return (0, 0);
        return (_quota(account), mintedByAi[ai.aiId]);
    }

    function statusOf(uint256 tokenId) public view returns (uint8) {
        Dog memory d = _dogs[tokenId];
        if (d.commitBlock == 0) return STATUS_NONE;
        uint256 target = uint256(d.commitBlock) + SEED_DELAY;
        if (block.number <= target) return STATUS_GENERATING;
        return targetHash(target) == bytes32(0) ? STATUS_STALLED : STATUS_READY;
    }

    function seedOf(uint256 tokenId) public view returns (bytes32) {
        Dog memory d = _dogs[tokenId];
        if (d.commitBlock == 0) return bytes32(0);
        bytes32 h = targetHash(uint256(d.commitBlock) + SEED_DELAY);
        if (h == bytes32(0)) return bytes32(0);
        return keccak256(abi.encode(h, tokenId, uint256(d.rerolls)));
    }

    function dogOf(uint256 tokenId)
        external
        view
        returns (uint256 commitBlock, uint256 targetBlock, uint256 rerolls, uint8 status, bytes32 seed)
    {
        Dog memory d = _dogs[tokenId];
        commitBlock = d.commitBlock;
        targetBlock = commitBlock == 0 ? 0 : commitBlock + SEED_DELAY;
        rerolls = d.rerolls;
        status = statusOf(tokenId);
        seed = seedOf(tokenId);
    }

    function rerollsOf(uint256 tokenId) external view returns (uint256) {
        return _dogs[tokenId].rerolls;
    }

    function needsSnapshot(uint256 tokenId) public view returns (bool) {
        Dog memory d = _dogs[tokenId];
        if (d.commitBlock == 0) return false;
        uint256 target = uint256(d.commitBlock) + SEED_DELAY;
        return block.number > target && snapshots[target] == bytes32(0) && _liveHash(target) != bytes32(0);
    }

    function targetHash(uint256 blockNumber) public view returns (bytes32) {
        bytes32 h = snapshots[blockNumber];
        if (h != bytes32(0)) return h;
        return _liveHash(blockNumber);
    }

    function queueLength() external view returns (uint256) {
        return _queue.length;
    }

    function tokenURI(uint256 tokenId) public view override returns (string memory) {
        _requireOwned(tokenId);
        bytes32 seed = seedOf(tokenId);
        uint8 state = seed == bytes32(0) ? 0 : 1;
        return IHahaDogRenderer(renderer).tokenURI(tokenId, seed, _dogs[tokenId].rerolls, state);
    }

    function royaltyInfo(uint256, uint256 salePrice) external view returns (address, uint256) {
        return (feeReceiver, (salePrice * HahaConstants.FEE_BPS) / HahaConstants.BPS_DENOMINATOR);
    }

    function supportsInterface(bytes4 interfaceId) public view override(ERC721, IERC165) returns (bool) {
        return interfaceId == type(IERC2981).interfaceId || super.supportsInterface(interfaceId);
    }

    function _update(address to, uint256 tokenId, address auth) internal override returns (address) {
        address from = super._update(to, tokenId, auth);
        if (from != address(0)) {
            _snapshotToken(tokenId);
            _processQueue(AUTO_SNAPSHOTS);
        }
        return from;
    }

    function _quota(address account) private view returns (uint256) {
        return IHahaRegistrar(registrar).balanceOf(account) > 0 ? 2 : 1;
    }


    function _commit(uint256 tokenId, uint256 rerolls) private {
        _dogs[tokenId] = Dog({commitBlock: uint64(block.number), rerolls: uint32(rerolls)});
        _queue.push((tokenId << 32) | rerolls);
        emit Committed(tokenId, rerolls, block.number);
    }

    function _liveHash(uint256 blockNumber) private view returns (bytes32 h) {
        if (blockNumber >= block.number) return bytes32(0);
        if (block.number - blockNumber <= 256) return blockhash(blockNumber);
        address history = blockHistory;
        if (history == address(0) || history.code.length == 0) return bytes32(0);
        (bool ok, bytes memory ret) = history.staticcall(abi.encode(blockNumber));
        if (ok && ret.length == 32) h = abi.decode(ret, (bytes32));
    }

    function _snapshotToken(uint256 tokenId) private returns (bool) {
        uint64 c = _dogs[tokenId].commitBlock;
        if (c == 0) return false;
        return _snapshotBlock(uint256(c) + SEED_DELAY);
    }

    function _snapshotBlock(uint256 target) private returns (bool) {
        if (block.number <= target || snapshots[target] != bytes32(0)) return false;
        bytes32 h = _liveHash(target);
        if (h == bytes32(0)) return false;
        snapshots[target] = h;
        emit Snapshot(target, h);
        return true;
    }

    function _processQueue(uint256 maxSteps) private {
        uint256 head = queueHead;
        uint256 len = _queue.length;
        for (uint256 n; n < maxSteps && head < len; ++n) {
            uint256 e = _queue[head];
            Dog memory d = _dogs[e >> 32];
            if (d.rerolls == uint32(e)) {
                uint256 target = uint256(d.commitBlock) + SEED_DELAY;
                if (block.number <= target) break;
                _snapshotBlock(target);
            }
            ++head;
        }
        queueHead = head;
    }
}
