// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {IERC165} from "@openzeppelin/contracts/utils/introspection/IERC165.sol";

import {HahaNamehash} from "./libraries/HahaNamehash.sol";
import {HahaConstants} from "./libraries/HahaConstants.sol";
import {IHahaRegistry} from "./interfaces/IHahaRegistry.sol";

interface IRegistrarNameParts {
    function nameParts(uint256 tokenId) external view returns (string memory label, uint8 tld);
}

contract HahaResolver is IERC165 {

    bytes4 private constant _INTERFACE_ID_ERC165 = 0x01ffc9a7;
    bytes4 private constant _INTERFACE_ID_ADDR = 0x3b3b57de;
    bytes4 private constant _INTERFACE_ID_TEXT = 0x59d1d43c;


    error NotNodeOwner();
    error NotRegistrar();
    error NameDoesNotExist();
    error InvalidKeyLength(uint256 length);
    error InvalidValueLength(uint256 length);
    error TooManyTextKeys(uint256 count);
    error AddrNotSelf();


    event AddrChanged(bytes32 indexed node, address a);

    event TextChanged(bytes32 indexed node, string indexed indexedKey, string key, string value);

    event RecordsCleared(bytes32 indexed node);

    event PrimaryNameSet(address indexed user, bytes32 indexed node, string fullName);
    event PrimaryNameCleared(address indexed user, bytes32 indexed node);


    mapping(bytes32 node => address) private _addrOverride;

    mapping(bytes32 node => mapping(string key => string value)) private _text;

    mapping(bytes32 node => string[]) private _textKeys;

    mapping(bytes32 node => mapping(string key => bool)) private _textKeyExists;

    mapping(address user => bytes32) public primaryNode;

    mapping(bytes32 node => address) public primaryHolder;


    address public immutable registry;

    address public immutable registrar;


    constructor(address registry_, address registrar_) {
        if (registry_ == address(0) || registrar_ == address(0)) revert AddrNotSelf();
        registry = registry_;
        registrar = registrar_;
    }


    function addr(bytes32 node) public view returns (address) {
        address overrideAddr = _addrOverride[node];
        if (overrideAddr != address(0)) return overrideAddr;
        return IHahaRegistry(registry).owner(node);
    }

    function setAddr(bytes32 node, address a) external {
        address nodeOwner = IHahaRegistry(registry).owner(node);
        if (nodeOwner == address(0)) revert NameDoesNotExist();
        if (msg.sender != nodeOwner) revert NotNodeOwner();

        _addrOverride[node] = a;
        emit AddrChanged(node, a);

        _dropPrimaryIfMismatched(node);
    }


    function text(bytes32 node, string calldata key) external view returns (string memory) {
        return _text[node][key];
    }

    function setText(bytes32 node, string calldata key, string calldata value) external {
        address nodeOwner = IHahaRegistry(registry).owner(node);
        if (nodeOwner == address(0)) revert NameDoesNotExist();
        if (msg.sender != nodeOwner) revert NotNodeOwner();

        uint256 keyLen = bytes(key).length;
        if (keyLen == 0 || keyLen > HahaConstants.MAX_TEXT_KEY_LENGTH) {
            revert InvalidKeyLength(keyLen);
        }
        uint256 valueLen = bytes(value).length;
        if (valueLen > HahaConstants.MAX_TEXT_VALUE_LENGTH) revert InvalidValueLength(valueLen);

        bool exists = _textKeyExists[node][key];
        if (!exists) {
            if (valueLen == 0) return;
            uint256 count = _textKeys[node].length;
            if (count >= HahaConstants.MAX_TEXT_KEYS) revert TooManyTextKeys(count);
            _textKeys[node].push(key);
            _textKeyExists[node][key] = true;
        }

        if (valueLen == 0) {
            delete _text[node][key];
            _textKeyExists[node][key] = false;
            _removeKeyFromList(node, key);
        } else {
            _text[node][key] = value;
        }

        emit TextChanged(node, key, key, value);
    }


    function clearRecords(bytes32 node) external {
        if (msg.sender != registrar) revert NotRegistrar();

        if (_addrOverride[node] != address(0)) {
            delete _addrOverride[node];
            emit AddrChanged(node, address(0));
        }

        string[] storage keys = _textKeys[node];
        uint256 n = keys.length;
        for (uint256 i = 0; i < n; ++i) {
            string memory k = keys[i];
            if (_textKeyExists[node][k]) {
                delete _text[node][k];
                _textKeyExists[node][k] = false;
            }
        }
        if (n > 0) {
            delete _textKeys[node];
        }

        _dropPrimaryIfMismatched(node);

        emit RecordsCleared(node);
    }


    function setPrimaryName(string calldata label, uint8 tld) external {
        if (tld > HahaConstants.TLD_MEME) revert NameDoesNotExist();

        bytes32 node = HahaNamehash.namehash(HahaNamehash.tldNode(tld), HahaNamehash.labelhash(label));
        if (IHahaRegistry(registry).owner(node) == address(0)) revert NameDoesNotExist();
        if (addr(node) != msg.sender) revert AddrNotSelf();

        bytes32 old = primaryNode[msg.sender];
        if (old != bytes32(0) && old != node) {
            emit PrimaryNameCleared(msg.sender, old);
            if (primaryHolder[old] == msg.sender) delete primaryHolder[old];
        }

        address previousHolder = primaryHolder[node];
        if (previousHolder != address(0) && previousHolder != msg.sender) {
            if (primaryNode[previousHolder] == node) delete primaryNode[previousHolder];
            emit PrimaryNameCleared(previousHolder, node);
        }

        primaryNode[msg.sender] = node;
        primaryHolder[node] = msg.sender;

        emit PrimaryNameSet(msg.sender, node, HahaNamehash.fullName(label, tld));
    }

    function clearPrimaryName() external {
        bytes32 node = primaryNode[msg.sender];
        if (node == bytes32(0)) return;
        delete primaryNode[msg.sender];
        if (primaryHolder[node] == msg.sender) delete primaryHolder[node];
        emit PrimaryNameCleared(msg.sender, node);
    }

    function primaryName(address user) external view returns (string memory) {
        bytes32 node = primaryNode[user];
        if (node == bytes32(0)) return "";
        if (addr(node) != user) return "";
        (string memory label, uint8 tld) = IRegistrarNameParts(registrar).nameParts(uint256(node));
        return HahaNamehash.fullName(label, tld);
    }


    function supportsInterface(bytes4 interfaceId) external pure returns (bool) {
        return interfaceId == _INTERFACE_ID_ERC165 || interfaceId == _INTERFACE_ID_ADDR
            || interfaceId == _INTERFACE_ID_TEXT;
    }


    function _dropPrimaryIfMismatched(bytes32 node) private {
        address holder = primaryHolder[node];
        if (holder == address(0)) return;

        if (primaryNode[holder] == node) {
            delete primaryNode[holder];
            delete primaryHolder[node];
            emit PrimaryNameCleared(holder, node);
        } else {
            delete primaryHolder[node];
        }
    }

    function _removeKeyFromList(bytes32 node, string calldata key) private {
        string[] storage keys = _textKeys[node];
        bytes32 target = keccak256(bytes(key));
        uint256 n = keys.length;
        for (uint256 i = 0; i < n; ++i) {
            if (keccak256(bytes(keys[i])) == target) {
                keys[i] = keys[n - 1];
                keys.pop();
                return;
            }
        }
    }
}
