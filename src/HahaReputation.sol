// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {HahaConstants} from "./libraries/HahaConstants.sol";
import {HahaAiIdentity} from "./libraries/HahaAiIdentity.sol";
import {IBinanceAiRegistry} from "./interfaces/IBinanceAiRegistry.sol";
import {IHahaAgentIdentity, IHahaPoints} from "./interfaces/IHahaProtocol.sol";

interface IERC721Balance {
    function balanceOf(address owner) external view returns (uint256);
}

contract HahaReputation {

    struct Score {
        uint64 count;
        uint256 sum;
    }

    struct Rating {
        uint8 stars;
        bool exists;
    }


    error InvalidStars(uint8 stars);
    error ReviewTooLong(uint256 length);
    error AgentNotActive();
    error AiRequired();
    error NameRequired();
    error OwnerAiRequired();
    error SelfRating();
    error ZeroAddress();


    event Rated(
        uint256 indexed agentId,
        bytes32 indexed aiId,
        address indexed rater,
        uint8 stars,
        string review,
        bool edited
    );


    mapping(uint256 agentId => Score) private _scores;

    mapping(uint256 agentId => mapping(bytes32 aiId => Rating)) private _ratings;


    address public immutable identity;

    address public immutable aiRegistry;

    address public immutable points;


    constructor(address identity_, address aiRegistry_, address points_) {
        if (identity_ == address(0) || aiRegistry_ == address(0)) revert ZeroAddress();
        identity = identity_;
        aiRegistry = aiRegistry_;
        points = points_;
    }


    function rate(uint256 agentId, uint8 stars, string calldata review) external {
        if (stars < 1 || stars > 5) revert InvalidStars(stars);
        uint256 reviewLen = bytes(review).length;
        if (reviewLen > HahaConstants.MAX_REVIEW_LENGTH) revert ReviewTooLong(reviewLen);

        IHahaAgentIdentity ident = IHahaAgentIdentity(identity);
        if (!ident.isActive(agentId)) revert AgentNotActive();

        HahaAiIdentity.Result memory ai =
            HahaAiIdentity.aiIdentityOf(IBinanceAiRegistry(aiRegistry), msg.sender);
        if (!ai.ok) revert AiRequired();

        if (IERC721Balance(ident.registrar()).balanceOf(msg.sender) == 0) revert NameRequired();

        address agentOwner = ident.ownerOf(agentId);
        HahaAiIdentity.Result memory ownerAi =
            HahaAiIdentity.aiIdentityOf(IBinanceAiRegistry(aiRegistry), agentOwner);
        if (!ownerAi.ok) revert OwnerAiRequired();

        if (msg.sender == agentOwner) revert SelfRating();
        if (ownerAi.aiId == ai.aiId) revert SelfRating();
        if (ident.operatorAiIdOf(agentId) == ai.aiId) revert SelfRating();
        if (ident.isAgentOperator(agentId, msg.sender)) revert SelfRating();

        Rating storage r = _ratings[agentId][ai.aiId];
        Score storage s = _scores[agentId];

        bool edited = r.exists;
        if (!edited) {
            r.exists = true;
            s.count += 1;
            s.sum += stars;
        } else {
            s.sum = s.sum - r.stars + stars;
        }
        r.stars = stars;

        emit Rated(agentId, ai.aiId, msg.sender, stars, review, edited);

        if (points != address(0)) {
            try IHahaPoints(points).earn(
                HahaConstants.ACTION_REVIEW_GIVE, msg.sender, bytes32(agentId)
            ) returns (uint256) {} catch {}

            try IHahaPoints(points).earn(
                HahaConstants.ACTION_REVIEW_RECEIVE,
                agentOwner,
                keccak256(abi.encode(agentId, ai.aiId))
            ) returns (uint256) {} catch {}
        }
    }


    function getScore(uint256 agentId) external view returns (uint64 count, uint256 sum) {
        Score storage s = _scores[agentId];
        return (s.count, s.sum);
    }

    function ratingOf(uint256 agentId, bytes32 aiId) external view returns (uint8 stars, bool exists) {
        Rating storage r = _ratings[agentId][aiId];
        return (r.stars, r.exists);
    }
}
