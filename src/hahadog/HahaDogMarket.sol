// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {IERC721} from "@openzeppelin/contracts/token/ERC721/IERC721.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

import {HahaConstants} from "../libraries/HahaConstants.sol";
import {IHahaDog} from "../interfaces/IHahaDog.sol";

contract HahaDogMarket is ReentrancyGuard {

    struct Listing {
        address seller;
        uint256 price;
        uint256 rerolls;
    }

    error NotOwner();
    error NotSeller();
    error NotApproved();
    error AlreadyListed();
    error NotListed();
    error PriceTooLow();
    error NotStale();
    error NotReady();
    error WrongValue(uint256 expected, uint256 got);
    error PriceChanged();
    error NothingToWithdraw();
    error TransferFailed();
    error ZeroAddress();

    event Listed(uint256 indexed tokenId, address indexed seller, uint256 price, uint256 rerolls);
    event PriceUpdated(uint256 indexed tokenId, address indexed seller, uint256 oldPrice, uint256 newPrice);
    event Cancelled(uint256 indexed tokenId, address indexed seller);
    event StaleCleared(uint256 indexed tokenId, address indexed seller, address indexed currentOwner);
    event Sold(
        uint256 indexed tokenId,
        address indexed seller,
        address indexed buyer,
        uint256 price,
        uint256 fee,
        uint256 proceeds
    );
    event Withdrawn(address indexed account, uint256 amount);

    uint8 internal constant STATUS_READY = 2;

    mapping(uint256 tokenId => Listing) private _listings;

    mapping(address account => uint256) public pendingWithdrawal;

    address public immutable dog;

    address public immutable feeReceiver;

    constructor(address dog_, address feeReceiver_) {
        if (dog_ == address(0) || feeReceiver_ == address(0)) revert ZeroAddress();
        dog = dog_;
        feeReceiver = feeReceiver_;
    }

    function listings(uint256 tokenId) external view returns (address seller, uint256 price, uint256 rerolls) {
        Listing memory l = _listings[tokenId];
        return (l.seller, l.price, l.rerolls);
    }

    function feeBps() external pure returns (uint256) {
        return HahaConstants.FEE_BPS;
    }

    function feeFor(uint256 price) public pure returns (uint256) {
        return (price * HahaConstants.FEE_BPS) / HahaConstants.BPS_DENOMINATOR;
    }

    function isValid(uint256 tokenId) public view returns (bool) {
        Listing memory l = _listings[tokenId];
        if (l.seller == address(0)) return false;
        IERC721 nft = IERC721(dog);
        return nft.ownerOf(tokenId) == l.seller && IHahaDog(dog).statusOf(tokenId) == STATUS_READY
            && IHahaDog(dog).rerollsOf(tokenId) == l.rerolls && _isApprovedForMarket(nft, tokenId, l.seller);
    }

    function list(uint256 tokenId, uint256 price) external {
        IERC721 nft = IERC721(dog);
        if (nft.ownerOf(tokenId) != msg.sender) revert NotOwner();
        if (IHahaDog(dog).statusOf(tokenId) != STATUS_READY) revert NotReady();
        if (feeFor(price) == 0) revert PriceTooLow();
        if (_listings[tokenId].seller != address(0)) revert AlreadyListed();
        if (!_isApprovedForMarket(nft, tokenId, msg.sender)) revert NotApproved();

        uint256 rerolls = IHahaDog(dog).rerollsOf(tokenId);
        _listings[tokenId] = Listing({seller: msg.sender, price: price, rerolls: rerolls});
        emit Listed(tokenId, msg.sender, price, rerolls);
    }

    function updatePrice(uint256 tokenId, uint256 newPrice) external {
        Listing storage l = _listings[tokenId];
        if (l.seller == address(0)) revert NotListed();
        if (l.seller != msg.sender) revert NotSeller();
        if (IERC721(dog).ownerOf(tokenId) != msg.sender) revert NotOwner();
        if (feeFor(newPrice) == 0) revert PriceTooLow();

        uint256 oldPrice = l.price;
        l.price = newPrice;
        emit PriceUpdated(tokenId, msg.sender, oldPrice, newPrice);
    }

    function cancel(uint256 tokenId) external {
        Listing storage l = _listings[tokenId];
        if (l.seller == address(0)) revert NotListed();
        if (l.seller != msg.sender) revert NotSeller();

        address seller = l.seller;
        delete _listings[tokenId];
        emit Cancelled(tokenId, seller);
    }

    function clearStale(uint256 tokenId) external {
        Listing memory l = _listings[tokenId];
        if (l.seller == address(0)) revert NotListed();

        address currentOwner = IERC721(dog).ownerOf(tokenId);
        if (currentOwner == l.seller && IHahaDog(dog).rerollsOf(tokenId) == l.rerolls) revert NotStale();

        delete _listings[tokenId];
        emit StaleCleared(tokenId, l.seller, currentOwner);
    }

    function buy(uint256 tokenId) external payable nonReentrant {
        Listing memory l = _listings[tokenId];
        if (l.seller == address(0)) revert NotListed();

        IERC721 nft = IERC721(dog);
        if (nft.ownerOf(tokenId) != l.seller) revert PriceChanged();
        if (IHahaDog(dog).statusOf(tokenId) != STATUS_READY) revert NotReady();
        if (IHahaDog(dog).rerollsOf(tokenId) != l.rerolls) revert PriceChanged();
        if (!_isApprovedForMarket(nft, tokenId, l.seller)) revert NotApproved();
        if (msg.value != l.price) revert WrongValue(l.price, msg.value);

        uint256 fee = feeFor(l.price);
        uint256 proceeds = l.price - fee;

        delete _listings[tokenId];
        pendingWithdrawal[l.seller] += proceeds;
        pendingWithdrawal[feeReceiver] += fee;

        emit Sold(tokenId, l.seller, msg.sender, l.price, fee, proceeds);

        nft.safeTransferFrom(l.seller, msg.sender, tokenId);
    }

    function withdraw() external nonReentrant {
        uint256 amount = pendingWithdrawal[msg.sender];
        if (amount == 0) revert NothingToWithdraw();

        pendingWithdrawal[msg.sender] = 0;
        emit Withdrawn(msg.sender, amount);

        (bool ok,) = msg.sender.call{value: amount}("");
        if (!ok) revert TransferFailed();
    }

    function _isApprovedForMarket(IERC721 nft, uint256 tokenId, address owner) private view returns (bool) {
        return nft.getApproved(tokenId) == address(this) || nft.isApprovedForAll(owner, address(this));
    }
}
