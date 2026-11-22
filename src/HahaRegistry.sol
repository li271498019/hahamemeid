// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {HahaNamehash} from "./libraries/HahaNamehash.sol";

contract HahaRegistry {

    error NotFactory();
    error NotRegistrar();
    error AlreadyBootstrapped();
    error UnknownTld(bytes32 tldNode);
    error TldNotOwnedByRegistrar(bytes32 tldNode);
    error NameExists(bytes32 node);
    error NameDoesNotExist(bytes32 node);
    error OwnerMismatch(address provided, address actual);
    error ZeroAddress();


    event NewOwner(bytes32 indexed node, bytes32 indexed label, address owner);

    event NewResolver(bytes32 indexed node, address resolver);

    event Transfer(bytes32 indexed node, address owner);


    struct Record {
        address owner;
        address resolver;
    }

    mapping(bytes32 node => Record) private _records;


    address public immutable registrar;

    address public immutable factory;

    address public immutable canonicalResolver;

    bool private _bootstrapped;


    modifier onlyRegistrar() {
        if (msg.sender != registrar) revert NotRegistrar();
        _;
    }


    constructor(address registrar_, address factory_, address canonicalResolver_) {
        if (registrar_ == address(0) || factory_ == address(0) || canonicalResolver_ == address(0)) {
            revert ZeroAddress();
        }
        registrar = registrar_;
        factory = factory_;
        canonicalResolver = canonicalResolver_;
    }


    function owner(bytes32 node) external view returns (address) {
        return _records[node].owner;
    }

    function resolver(bytes32 node) external view returns (address) {
        return _records[node].resolver;
    }

    function recordExists(bytes32 node) external view returns (bool) {
        Record storage r = _records[node];
        return r.owner != address(0) || r.resolver != address(0);
    }

    function bootstrapped() external view returns (bool) {
        return _bootstrapped;
    }


    function bootstrap() external {
        if (msg.sender != factory) revert NotFactory();
        if (_bootstrapped) revert AlreadyBootstrapped();
        _bootstrapped = true;

        _records[HahaNamehash.HAHA_NODE] = Record({owner: registrar, resolver: address(0)});
        _records[HahaNamehash.MEME_NODE] = Record({owner: registrar, resolver: address(0)});

    }

    function createName(bytes32 tldNode, bytes32 labelhash, address nameOwner) external onlyRegistrar {
        if (tldNode != HahaNamehash.HAHA_NODE && tldNode != HahaNamehash.MEME_NODE) {
            revert UnknownTld(tldNode);
        }
        if (_records[tldNode].owner != registrar) revert TldNotOwnedByRegistrar(tldNode);

        bytes32 node = HahaNamehash.namehash(tldNode, labelhash);
        if (_records[node].owner != address(0) || _records[node].resolver != address(0)) {
            revert NameExists(node);
        }

        address nftOwner = _ownerOfRegistrar(uint256(node));
        if (nftOwner != nameOwner) revert OwnerMismatch(nameOwner, nftOwner);
        if (nameOwner == address(0)) revert ZeroAddress();

        _records[node] = Record({owner: nameOwner, resolver: canonicalResolver});

        emit NewOwner(tldNode, labelhash, nameOwner);
        emit NewResolver(node, canonicalResolver);
    }

    function syncOwner(bytes32 node, address nameOwner) external onlyRegistrar {
        if (node == HahaNamehash.HAHA_NODE || node == HahaNamehash.MEME_NODE) {
            revert TldNotOwnedByRegistrar(node);
        }
        Record storage r = _records[node];
        if (r.owner == address(0) && r.resolver == address(0)) revert NameDoesNotExist(node);

        address nftOwner = _ownerOfRegistrar(uint256(node));
        if (nftOwner != nameOwner) revert OwnerMismatch(nameOwner, nftOwner);
        if (nameOwner == address(0)) revert ZeroAddress();

        r.owner = nameOwner;
        emit Transfer(node, nameOwner);
    }


    function _ownerOfRegistrar(uint256 tokenId) private view returns (address) {
        (bool ok, bytes memory data) =
            registrar.staticcall(abi.encodeWithSignature("ownerOf(uint256)", tokenId));
        if (!ok || data.length < 32) return address(0);
        return abi.decode(data, (address));
    }
}
