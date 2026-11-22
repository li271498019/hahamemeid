// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

library HahaConstants {
    uint256 internal constant MIN_PUBLIC_LENGTH = 3;

    uint256 internal constant MAX_LABEL_LENGTH = 32;

    uint256 internal constant COOLDOWN = 3600;

    uint256 internal constant FEE_BPS = 100;

    uint256 internal constant BPS_DENOMINATOR = 10_000;

    uint256 internal constant MINT_REWARDS_PER_DAY = 3;

    uint256 internal constant MAX_POINT_PARAM = 999_999_999;

    uint256 internal constant MAX_TEXT_KEYS = 16;

    uint256 internal constant MAX_TEXT_KEY_LENGTH = 64;

    uint256 internal constant MAX_TEXT_VALUE_LENGTH = 1024;

    uint256 internal constant MAX_REVIEW_LENGTH = 140;

    uint256 internal constant MAX_AGENT_URI_LENGTH = 2048;

    uint256 internal constant BANNED_COUNT = 208;

    uint256 internal constant RESERVED_COUNT = 61;

    uint8 internal constant TLD_HAHA = 0;

    uint8 internal constant TLD_MEME = 1;

    bytes32 internal constant REASON_CHECKIN = "CHECKIN";

    bytes32 internal constant REASON_MINT = "MINT";

    bytes32 internal constant REASON_FOLLOW = "FOLLOW";

    bytes32 internal constant REASON_RETWEET = "RETWEET";

    bytes32 internal constant REASON_LIKE = "LIKE";

    bytes32 internal constant REASON_COMMENT = "COMMENT";


    uint256 internal constant MAX_EARNER_POINTS = 100;

    uint64 internal constant MAX_PER_USER_DAILY = 50;

    uint256 internal constant MAX_GLOBAL_DAILY_POINTS = 1_000_000;

    uint256 internal constant MAX_MODULES = 32;

    uint256 internal constant MAX_SPEND_USER_DAILY = 1_000_000_000;

    uint256 internal constant MAX_SPEND_GLOBAL_DAILY = 10_000_000_000;

    uint64 internal constant GAME_ROUNDS_PER_DAY = 3;

    uint256 internal constant MAX_GAME_SCORE_PER_ROUND = 1000;

    uint256 internal constant MAX_AGENT_OPERATORS = 8;


    uint256 internal constant SUGGESTED_REVIEW_POINTS = 5;

    uint256 internal constant SUGGESTED_ACTIVATE_POINTS = 20;

    uint64 internal constant REVIEW_GIVE_DAILY_CAP = 5;

    uint64 internal constant REVIEW_RECEIVE_DAILY_CAP = 5;

    uint256 internal constant REVIEW_GLOBAL_DAILY_POINTS = 50_000;

    uint256 internal constant ACTIVATE_GLOBAL_DAILY_POINTS = 100_000;

    uint256 internal constant GAME_GLOBAL_DAILY_POINTS = 50_000;

    bytes32 internal constant ACTION_REVIEW_GIVE = "REVIEW_GIVE";

    bytes32 internal constant ACTION_REVIEW_RECEIVE = "REVIEW_RECEIVE";

    bytes32 internal constant ACTION_ACTIVATE = "ACTIVATE";

    bytes32 internal constant ACTIVATE_ONCE = "ACTIVATE_ONCE";

    uint256 internal constant MAX_STATUS_ACTIONS = 16;

    function tldString(uint8 tld) internal pure returns (string memory) {
        if (tld == TLD_HAHA) return "haha";
        if (tld == TLD_MEME) return "meme";
        return "";
    }

    function isBuiltinReason(bytes32 actionId) internal pure returns (bool) {
        return actionId == REASON_CHECKIN || actionId == REASON_MINT || actionId == REASON_FOLLOW
            || actionId == REASON_LIKE || actionId == REASON_RETWEET || actionId == REASON_COMMENT;
    }
}
