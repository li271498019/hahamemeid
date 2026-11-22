// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {HahaConstants} from "./libraries/HahaConstants.sol";
import {HahaAiIdentity} from "./libraries/HahaAiIdentity.sol";
import {IBinanceAiRegistry} from "./interfaces/IBinanceAiRegistry.sol";

interface IRegistrarBalance {
    function balanceOf(address owner) external view returns (uint256);
}

contract HahaPoints {

    struct DayClaim {
        uint64 dayIndex;
        bool done;
    }

    enum KeyMode {
        None,
        PerDay,
        Lifetime
    }

    struct EarnerConfig {
        address module;
        uint256 points;
        uint64 perUserDailyCap;
        uint256 globalDailyPoints;
        KeyMode keyMode;
        bool requireName;
        bool enabled;
    }

    struct SpenderBudget {
        uint256 perUserDailyPoints;
        uint256 globalDailyPoints;
    }

    struct GameRound {
        bytes32 gameId;
        bytes32 aiId;
        address player;
        uint64 openDay;
        bool claimed;
        uint256 score;
    }

    struct GameConfig {
        address module;
        uint256 maxScorePerRound;
        uint256 perAiDailyPoints;
        uint256 globalDailyPoints;
        bool enabled;
    }

    struct PointsStatus {
        bytes32 aiId;
        uint256 balance;
        bool holdsAi;
        bool holdsName;
        uint64 currentDay;
        uint64 nextResetAt;
        uint64 checkInToday;
        uint64 mintRewardsToday;
        uint64 likeToday;
        uint64 retweetToday;
        uint64 commentToday;
        uint64 gameRoundsToday;
        uint64 reviewsGivenToday;
        uint64 reviewsReceivedToday;
        uint8 mintRewardsPerDay;
        uint8 gameRoundsPerDay;
        bool followClaimed;
    }

    struct ActionStatus {
        bytes32 actionId;
        uint256 pointsEach;
        uint64 todayCount;
        uint64 dailyCap;
        uint64 nextResetAt;
        uint256 globalPointsToday;
        uint256 globalDailyPoints;
        uint8 keyMode;
        bool enabled;
        bool underCap;
    }


    error NotAdmin();
    error NotRegistrar();
    error NotSpender();
    error AiRequired();
    error NameRequired();
    error CheckInDisabled();
    error SocialDisabled();
    error AlreadyCheckedInToday();
    error FollowAlreadyClaimed();
    error AlreadyClaimedToday();
    error ParamTooLarge(uint256 value);
    error NotAContract();
    error ZeroAddress();
    error ZeroAmount();
    error InsufficientPoints(uint256 available, uint256 requested);
    error RefundExceedsSpendable(uint256 requested, uint256 available);
    error ZeroReason();


    error NotEarner();
    error InvalidActionId();
    error ActionReserved();
    error TooManyModules(uint256 count);
    error ModuleNotContract();
    error PointsOutOfRange(uint256 value);
    error CapOutOfRange(uint256 value);
    error GlobalBudgetOutOfRange(uint256 value);
    error GlobalBudgetBelowPoints(uint256 globalDaily, uint256 points);
    error BudgetNotSet();
    error SpendBudgetExceeded(bool perUser, uint256 attempted, uint256 budget);
    error TooManyActions(uint256 count);
    error GameNotRegistered();
    error DailyRoundsSpent(uint64 day);
    error SessionNotSettled();
    error SessionAlreadyClaimed();
    error SessionExpired(uint64 openDay, uint64 currentDay);
    error ScoreTooHigh(uint256 score, uint256 maxScore);
    error GameBudgetExceeded(bool perUser, uint256 attempted, uint256 budget);
    error ScoreCallFailed();
    error GameScoreOutOfRange(uint256 value);
    error GameBudgetOutOfRange(uint256 value);


    event PointsChanged(
        bytes32 indexed aiId,
        address indexed user,
        int256 delta,
        uint256 newBalance,
        bytes32 indexed reason
    );

    event PointParamsUpdated(
        uint256 checkInPoints,
        uint256 mintReward,
        uint256 followPoints,
        uint256 retweetPoints,
        uint256 likePoints,
        uint256 commentPoints
    );

    event SpenderUpdated(address indexed spender, bool allowed);

    event Earned(
        bytes32 indexed actionId,
        bytes32 indexed aiId,
        address indexed user,
        uint256 amount,
        bytes32 uniqueKey,
        uint256 newBalance
    );

    event EarnerUpdated(
        bytes32 indexed actionId,
        address indexed module,
        uint256 points,
        uint64 perUserDailyCap,
        uint256 globalDailyPoints,
        uint8 keyMode,
        bool requireName,
        bool enabled
    );

    event SpenderBudgetUpdated(
        address indexed spender, uint256 perUserDailyPoints, uint256 globalDailyPoints
    );

    event RoundOpened(
        uint256 indexed sessionId, bytes32 indexed gameId, bytes32 indexed aiId, address player, uint64 openDay
    );

    event RoundClaimed(
        uint256 indexed sessionId, bytes32 indexed gameId, bytes32 indexed aiId, uint256 amount
    );

    event GameUpdated(
        bytes32 indexed gameId,
        address indexed module,
        uint256 maxScorePerRound,
        uint256 perAiDailyPoints,
        uint256 globalDailyPoints,
        bool enabled
    );


    mapping(bytes32 aiId => uint256) private _balance;

    mapping(bytes32 aiId => uint64) private _lastCheckInDay;

    mapping(bytes32 aiId => bool) private _hasCheckedIn;

    mapping(bytes32 aiId => DayCounter) private _mintRewardDay;

    mapping(bytes32 aiId => bool) private _followClaimed;

    mapping(bytes32 aiId => DayClaim) private _likeClaim;
    mapping(bytes32 aiId => DayClaim) private _retweetClaim;
    mapping(bytes32 aiId => DayClaim) private _commentClaim;

    mapping(bytes32 aiId => mapping(bytes32 reason => uint256)) private _spendable;

    struct DayCounter {
        uint64 dayIndex;
        uint8 count;
    }


    mapping(bytes32 actionId => EarnerConfig) private _earner;

    bytes32[] private _actionIds;

    mapping(bytes32 actionId => bool) private _actionIdSeen;

    mapping(bytes32 actionId => mapping(bytes32 aiId => DayCounter)) private _userDailyCount;

    mapping(bytes32 actionId => DayCounter256) private _globalDailyPoints;

    mapping(bytes32 actionId => mapping(bytes32 aiId => mapping(bytes32 uniqueKey => uint64))) private _keyDay;

    mapping(bytes32 aiId => DayCounter) private _gameRounds;

    mapping(uint256 sessionId => GameRound) private _rounds;

    uint256 private _nextSessionId;

    mapping(bytes32 gameId => GameConfig) private _games;

    mapping(bytes32 gameId => mapping(bytes32 aiId => DayCounter256)) private _gameUserPoints;

    mapping(bytes32 gameId => DayCounter256) private _gameGlobalPoints;

    mapping(address spender => SpenderBudget) private _budget;

    mapping(address spender => mapping(bytes32 aiId => DayCounter256)) private _spendUserGross;

    mapping(address spender => DayCounter256) private _spendGlobalGross;

    struct DayCounter256 {
        uint64 dayIndex;
        uint256 amount;
    }


    uint256 public checkInPoints = 30;

    uint256 public mintReward = 10;

    uint256 public followPoints = 30;

    uint256 public retweetPoints = 10;

    uint256 public likePoints = 10;

    uint256 public commentPoints = 10;

    mapping(address account => bool) public isSpender;


    address public immutable registrar;

    address public immutable aiRegistry;

    address public immutable admin;


    modifier onlyAdmin() {
        if (msg.sender != admin) revert NotAdmin();
        _;
    }

    modifier onlySpender() {
        if (!isSpender[msg.sender]) revert NotSpender();
        _;
    }


    constructor(address registrar_, address aiRegistry_, address admin_) {
        if (registrar_ == address(0) || aiRegistry_ == address(0) || admin_ == address(0)) {
            revert ZeroAddress();
        }
        registrar = registrar_;
        aiRegistry = aiRegistry_;
        admin = admin_;
    }


    function checkIn() external {
        HahaAiIdentity.Result memory ai = _requireEligible(msg.sender);

        if (checkInPoints == 0) revert CheckInDisabled();

        uint64 day = _currentDay();
        if (_hasCheckedIn[ai.aiId] && _lastCheckInDay[ai.aiId] >= day) revert AlreadyCheckedInToday();

        _hasCheckedIn[ai.aiId] = true;
        _lastCheckInDay[ai.aiId] = day;

        _balance[ai.aiId] += checkInPoints;
        emit PointsChanged(
            ai.aiId, msg.sender, int256(checkInPoints), _balance[ai.aiId], HahaConstants.REASON_CHECKIN
        );
    }

    function claimFollow() external {
        HahaAiIdentity.Result memory ai = _requireEligible(msg.sender);

        if (followPoints == 0) revert SocialDisabled();
        if (_followClaimed[ai.aiId]) revert FollowAlreadyClaimed();

        _followClaimed[ai.aiId] = true;

        _balance[ai.aiId] += followPoints;
        emit PointsChanged(
            ai.aiId, msg.sender, int256(followPoints), _balance[ai.aiId], HahaConstants.REASON_FOLLOW
        );
    }

    function claimLike() external {
        HahaAiIdentity.Result memory ai = _requireEligible(msg.sender);

        if (likePoints == 0) revert SocialDisabled();
        _requireDayClaim(_likeClaim[ai.aiId]);

        _likeClaim[ai.aiId] = DayClaim({dayIndex: _currentDay(), done: true});

        _balance[ai.aiId] += likePoints;
        emit PointsChanged(
            ai.aiId, msg.sender, int256(likePoints), _balance[ai.aiId], HahaConstants.REASON_LIKE
        );
    }

    function claimRetweet() external {
        HahaAiIdentity.Result memory ai = _requireEligible(msg.sender);

        if (retweetPoints == 0) revert SocialDisabled();
        _requireDayClaim(_retweetClaim[ai.aiId]);

        _retweetClaim[ai.aiId] = DayClaim({dayIndex: _currentDay(), done: true});

        _balance[ai.aiId] += retweetPoints;
        emit PointsChanged(
            ai.aiId, msg.sender, int256(retweetPoints), _balance[ai.aiId], HahaConstants.REASON_RETWEET
        );
    }

    function claimComment() external {
        HahaAiIdentity.Result memory ai = _requireEligible(msg.sender);

        if (commentPoints == 0) revert SocialDisabled();
        _requireDayClaim(_commentClaim[ai.aiId]);

        _commentClaim[ai.aiId] = DayClaim({dayIndex: _currentDay(), done: true});

        _balance[ai.aiId] += commentPoints;
        emit PointsChanged(
            ai.aiId, msg.sender, int256(commentPoints), _balance[ai.aiId], HahaConstants.REASON_COMMENT
        );
    }


    function creditMintReward(address user, bytes32 aiId) external returns (uint256 awarded) {
        if (msg.sender != registrar) revert NotRegistrar();
        if (user == address(0) || aiId == bytes32(0)) revert ZeroAddress();

        if (IRegistrarBalance(registrar).balanceOf(user) == 0) revert NameRequired();

        HahaAiIdentity.Result memory ai = HahaAiIdentity.aiIdentityOf(IBinanceAiRegistry(aiRegistry), user);
        if (!ai.ok || ai.aiId != aiId) revert AiRequired();

        if (mintReward == 0) return 0;

        uint64 day = _currentDay();
        DayCounter memory c = _mintRewardDay[aiId];
        uint8 count = c.dayIndex == day ? c.count : 0;
        if (count >= HahaConstants.MINT_REWARDS_PER_DAY) return 0;

        _mintRewardDay[aiId] = DayCounter({dayIndex: day, count: count + 1});

        awarded = mintReward;
        _balance[aiId] += awarded;
        emit PointsChanged(aiId, user, int256(awarded), _balance[aiId], HahaConstants.REASON_MINT);
    }


    function earn(bytes32 actionId, address user, bytes32 uniqueKey) external returns (uint256 awarded) {
        EarnerConfig memory cfg = _earner[actionId];

        if (!cfg.enabled || cfg.module != msg.sender) revert NotEarner();

        if (cfg.points == 0) return 0;
        if (user == address(0)) return 0;

        HahaAiIdentity.Result memory ai = HahaAiIdentity.aiIdentityOf(IBinanceAiRegistry(aiRegistry), user);
        if (!ai.ok) return 0;
        if (cfg.requireName && IRegistrarBalance(registrar).balanceOf(user) == 0) return 0;

        uint64 day = _currentDay();

        if (cfg.keyMode != KeyMode.None) {
            if (uniqueKey == bytes32(0)) return 0;
            uint64 stored = _keyDay[actionId][ai.aiId][uniqueKey];
            if (stored == type(uint64).max) return 0;
            if (cfg.keyMode == KeyMode.PerDay && stored == day) return 0;
        }

        DayCounter memory uc = _userDailyCount[actionId][ai.aiId];
        uint64 usedToday = uc.dayIndex == day ? uc.count : 0;
        if (usedToday >= cfg.perUserDailyCap) return 0;

        DayCounter256 memory gc = _globalDailyPoints[actionId];
        uint256 globalToday = gc.dayIndex == day ? gc.amount : 0;
        if (globalToday + cfg.points > cfg.globalDailyPoints) return 0;

        if (cfg.keyMode != KeyMode.None) {
            _keyDay[actionId][ai.aiId][uniqueKey] =
                cfg.keyMode == KeyMode.Lifetime ? type(uint64).max : day;
        }
        _userDailyCount[actionId][ai.aiId] = DayCounter({dayIndex: day, count: uint8(usedToday + 1)});
        _globalDailyPoints[actionId] = DayCounter256({dayIndex: day, amount: globalToday + cfg.points});

        awarded = cfg.points;
        uint256 newBalance = _balance[ai.aiId] + awarded;
        _balance[ai.aiId] = newBalance;

        emit PointsChanged(ai.aiId, user, int256(awarded), newBalance, actionId);
        emit Earned(actionId, ai.aiId, user, awarded, uniqueKey, newBalance);
    }


    function beginRound(bytes32 gameId, address player) external returns (uint256 sessionId) {
        GameConfig memory g = _games[gameId];
        if (!g.enabled || g.module != msg.sender) revert GameNotRegistered();

        HahaAiIdentity.Result memory ai = HahaAiIdentity.aiIdentityOf(IBinanceAiRegistry(aiRegistry), player);
        if (!ai.ok) revert AiRequired();
        if (IRegistrarBalance(registrar).balanceOf(player) == 0) revert NameRequired();

        uint64 day = _currentDay();

        DayCounter memory rc = _gameRounds[ai.aiId];
        uint64 opened = rc.dayIndex == day ? rc.count : 0;
        if (opened >= HahaConstants.GAME_ROUNDS_PER_DAY) revert DailyRoundsSpent(day);

        _gameRounds[ai.aiId] = DayCounter({dayIndex: day, count: uint8(opened + 1)});

        unchecked {
            sessionId = ++_nextSessionId;
        }
        _rounds[sessionId] = GameRound({
            gameId: gameId,
            aiId: ai.aiId,
            player: player,
            openDay: day,
            claimed: false,
            score: 0
        });

        emit RoundOpened(sessionId, gameId, ai.aiId, player, day);
    }

    function claimRound(uint256 sessionId) external returns (uint256 awarded) {
        GameRound memory r = _rounds[sessionId];
        if (r.gameId == bytes32(0)) revert SessionNotSettled();

        GameConfig memory g = _games[r.gameId];
        if (g.module != msg.sender) revert GameNotRegistered();
        if (!g.enabled) revert GameNotRegistered();

        if (r.claimed) revert SessionAlreadyClaimed();

        uint64 day = _currentDay();
        if (day != r.openDay) revert SessionExpired(r.openDay, day);

        (bool ok, bytes memory ret) =
            g.module.staticcall(abi.encodeWithSignature("scoreOf(uint256)", sessionId));
        if (!ok || ret.length < 64) revert ScoreCallFailed();
        (uint256 score, bool settled) = abi.decode(ret, (uint256, bool));
        if (!settled) revert SessionNotSettled();

        if (score > g.maxScorePerRound) revert ScoreTooHigh(score, g.maxScorePerRound);

        DayCounter256 memory uc = _gameUserPoints[r.gameId][r.aiId];
        uint256 userToday = uc.dayIndex == day ? uc.amount : 0;
        if (userToday + score > g.perAiDailyPoints) {
            revert GameBudgetExceeded(true, userToday + score, g.perAiDailyPoints);
        }
        DayCounter256 memory gc = _gameGlobalPoints[r.gameId];
        uint256 globalToday = gc.dayIndex == day ? gc.amount : 0;
        if (globalToday + score > g.globalDailyPoints) {
            revert GameBudgetExceeded(false, globalToday + score, g.globalDailyPoints);
        }

        r.claimed = true;
        r.score = score;
        _rounds[sessionId] = r;

        _gameUserPoints[r.gameId][r.aiId] = DayCounter256({dayIndex: day, amount: userToday + score});
        _gameGlobalPoints[r.gameId] = DayCounter256({dayIndex: day, amount: globalToday + score});

        awarded = score;
        uint256 newBalance = _balance[r.aiId] + awarded;
        _balance[r.aiId] = newBalance;

        emit RoundClaimed(sessionId, r.gameId, r.aiId, awarded);
        emit PointsChanged(r.aiId, r.player, int256(awarded), newBalance, r.gameId);
    }


    function spend(address user, uint256 amount, bytes32 reason) external onlySpender {
        if (amount == 0) revert ZeroAmount();
        if (reason == bytes32(0)) revert ZeroReason();

        HahaAiIdentity.Result memory ai = _requireEligible(user);

        uint256 bal = _balance[ai.aiId];
        if (bal < amount) revert InsufficientPoints(bal, amount);

        SpenderBudget memory b = _budget[msg.sender];
        if (b.perUserDailyPoints == 0 && b.globalDailyPoints == 0) revert BudgetNotSet();

        uint64 day = _currentDay();

        DayCounter256 memory ug = _spendUserGross[msg.sender][ai.aiId];
        uint256 userGross = ug.dayIndex == day ? ug.amount : 0;
        if (userGross + amount > b.perUserDailyPoints) {
            revert SpendBudgetExceeded(true, userGross + amount, b.perUserDailyPoints);
        }

        DayCounter256 memory gg = _spendGlobalGross[msg.sender];
        uint256 globalGross = gg.dayIndex == day ? gg.amount : 0;
        if (globalGross + amount > b.globalDailyPoints) {
            revert SpendBudgetExceeded(false, globalGross + amount, b.globalDailyPoints);
        }

        _spendUserGross[msg.sender][ai.aiId] = DayCounter256({dayIndex: day, amount: userGross + amount});
        _spendGlobalGross[msg.sender] = DayCounter256({dayIndex: day, amount: globalGross + amount});

        _spendable[ai.aiId][reason] += amount;

        uint256 newBal = bal - amount;
        _balance[ai.aiId] = newBal;
        emit PointsChanged(ai.aiId, user, -int256(amount), newBal, reason);
    }

    function refund(address user, uint256 amount, bytes32 reason) external onlySpender {
        if (amount == 0) revert ZeroAmount();
        if (reason == bytes32(0)) revert ZeroReason();

        HahaAiIdentity.Result memory ai = HahaAiIdentity.aiIdentityOf(IBinanceAiRegistry(aiRegistry), user);
        if (!ai.ok) revert AiRequired();

        uint256 available = _spendable[ai.aiId][reason];
        if (amount > available) revert RefundExceedsSpendable(amount, available);

        _spendable[ai.aiId][reason] = available - amount;

        uint256 newBal = _balance[ai.aiId] + amount;
        _balance[ai.aiId] = newBal;
        emit PointsChanged(ai.aiId, user, int256(amount), newBal, reason);
    }


    function setPointParams(
        uint256 checkInPoints_,
        uint256 mintReward_,
        uint256 followPoints_,
        uint256 retweetPoints_,
        uint256 likePoints_,
        uint256 commentPoints_
    ) external onlyAdmin {
        _requireParamInRange(checkInPoints_);
        _requireParamInRange(mintReward_);
        _requireParamInRange(followPoints_);
        _requireParamInRange(retweetPoints_);
        _requireParamInRange(likePoints_);
        _requireParamInRange(commentPoints_);

        checkInPoints = checkInPoints_;
        mintReward = mintReward_;
        followPoints = followPoints_;
        retweetPoints = retweetPoints_;
        likePoints = likePoints_;
        commentPoints = commentPoints_;

        emit PointParamsUpdated(
            checkInPoints_, mintReward_, followPoints_, retweetPoints_, likePoints_, commentPoints_
        );
    }

    function setSpender(address spender, bool allowed) external onlyAdmin {
        if (spender == address(0)) revert ZeroAddress();
        if (allowed && spender.code.length == 0) revert NotAContract();

        isSpender[spender] = allowed;
        emit SpenderUpdated(spender, allowed);
    }

    function setEarner(bytes32 actionId, EarnerConfig calldata cfg) external onlyAdmin {
        if (actionId == bytes32(0)) revert InvalidActionId();
        if (HahaConstants.isBuiltinReason(actionId)) revert ActionReserved();

        if (actionId == HahaConstants.ACTION_REVIEW_GIVE || actionId == HahaConstants.ACTION_REVIEW_RECEIVE) {
            if (cfg.keyMode != KeyMode.PerDay) revert InvalidActionId();
            if (cfg.perUserDailyCap != HahaConstants.REVIEW_GIVE_DAILY_CAP) revert CapOutOfRange(cfg.perUserDailyCap);
        } else if (actionId == HahaConstants.ACTION_ACTIVATE) {
            if (cfg.keyMode != KeyMode.Lifetime) revert InvalidActionId();
        }

        if (cfg.enabled) {
            if (cfg.module == address(0) || cfg.module.code.length == 0) revert ModuleNotContract();
            if (cfg.points == 0 || cfg.points > HahaConstants.MAX_EARNER_POINTS) {
                revert PointsOutOfRange(cfg.points);
            }
            if (cfg.perUserDailyCap == 0 || cfg.perUserDailyCap > HahaConstants.MAX_PER_USER_DAILY) {
                revert CapOutOfRange(cfg.perUserDailyCap);
            }
            if (
                cfg.globalDailyPoints == 0
                    || cfg.globalDailyPoints > HahaConstants.MAX_GLOBAL_DAILY_POINTS
            ) {
                revert GlobalBudgetOutOfRange(cfg.globalDailyPoints);
            }
            if (cfg.globalDailyPoints < cfg.points) {
                revert GlobalBudgetBelowPoints(cfg.globalDailyPoints, cfg.points);
            }
        }

        if (_earner[actionId].module == address(0) && !_actionIdSeen[actionId]) {            if (_actionIds.length >= HahaConstants.MAX_MODULES) revert TooManyModules(_actionIds.length);
            _actionIdSeen[actionId] = true;
            _actionIds.push(actionId);
        }

        _earner[actionId] = cfg;

        emit EarnerUpdated(
            actionId,
            cfg.module,
            cfg.points,
            cfg.perUserDailyCap,
            cfg.globalDailyPoints,
            uint8(cfg.keyMode),
            cfg.requireName,
            cfg.enabled
        );
    }

    function setSpenderBudget(address spender, SpenderBudget calldata budget) external onlyAdmin {
        if (spender == address(0)) revert ZeroAddress();
        if (
            budget.perUserDailyPoints == 0
                || budget.perUserDailyPoints > HahaConstants.MAX_SPEND_USER_DAILY
        ) revert SpendBudgetExceeded(true, budget.perUserDailyPoints, HahaConstants.MAX_SPEND_USER_DAILY);
        if (
            budget.globalDailyPoints == 0
                || budget.globalDailyPoints > HahaConstants.MAX_SPEND_GLOBAL_DAILY
        ) revert SpendBudgetExceeded(false, budget.globalDailyPoints, HahaConstants.MAX_SPEND_GLOBAL_DAILY);

        _budget[spender] = budget;
        emit SpenderBudgetUpdated(spender, budget.perUserDailyPoints, budget.globalDailyPoints);
    }

    function registerGame(bytes32 gameId, GameConfig calldata cfg) external onlyAdmin {
        if (gameId == bytes32(0)) revert GameNotRegistered();
        if (
            HahaConstants.isBuiltinReason(gameId) || gameId == HahaConstants.ACTION_REVIEW_GIVE
                || gameId == HahaConstants.ACTION_REVIEW_RECEIVE || gameId == HahaConstants.ACTION_ACTIVATE
        ) revert ActionReserved();

        if (cfg.enabled) {
            if (cfg.module == address(0) || cfg.module.code.length == 0) revert ModuleNotContract();
            if (cfg.maxScorePerRound == 0 || cfg.maxScorePerRound > HahaConstants.MAX_GAME_SCORE_PER_ROUND) {
                revert GameScoreOutOfRange(cfg.maxScorePerRound);
            }
            if (cfg.perAiDailyPoints == 0 || cfg.globalDailyPoints == 0) {
                revert GameBudgetExceeded(false, 0, 0);
            }
            if (
                cfg.perAiDailyPoints > HahaConstants.MAX_GLOBAL_DAILY_POINTS
                    || cfg.globalDailyPoints > HahaConstants.MAX_GLOBAL_DAILY_POINTS
            ) revert GameBudgetOutOfRange(cfg.globalDailyPoints);
        }

        _games[gameId] = cfg;

        emit GameUpdated(
            gameId, cfg.module, cfg.maxScorePerRound, cfg.perAiDailyPoints, cfg.globalDailyPoints, cfg.enabled
        );
    }


    function balanceOf(bytes32 aiId) external view returns (uint256) {
        return _balance[aiId];
    }

    function balanceOfUser(address user) external view returns (uint256) {
        HahaAiIdentity.Result memory ai = HahaAiIdentity.aiIdentityOf(IBinanceAiRegistry(aiRegistry), user);
        if (!ai.ok) return 0;
        return _balance[ai.aiId];
    }

    function spendableOf(bytes32 aiId, bytes32 reason) external view returns (uint256) {
        return _spendable[aiId][reason];
    }

    function currentDay() public view returns (uint256) {
        return _currentDay();
    }

    function lastCheckInDay(bytes32 aiId) external view returns (uint64) {
        return _lastCheckInDay[aiId];
    }

    function hasCheckedIn(bytes32 aiId) external view returns (bool) {
        return _hasCheckedIn[aiId];
    }

    function followClaimed(bytes32 aiId) external view returns (bool) {
        return _followClaimed[aiId];
    }

    function likeClaim(bytes32 aiId) external view returns (uint64 dayIndex, bool done) {
        DayClaim memory c = _likeClaim[aiId];
        return (c.dayIndex, c.done);
    }

    function retweetClaim(bytes32 aiId) external view returns (uint64 dayIndex, bool done) {
        DayClaim memory c = _retweetClaim[aiId];
        return (c.dayIndex, c.done);
    }

    function commentClaim(bytes32 aiId) external view returns (uint64 dayIndex, bool done) {
        DayClaim memory c = _commentClaim[aiId];
        return (c.dayIndex, c.done);
    }

    function mintRewardsToday(bytes32 aiId) external view returns (uint256) {
        DayCounter memory c = _mintRewardDay[aiId];
        if (c.dayIndex != _currentDay()) return 0;
        return c.count;
    }

    function mintRewardsPerDay() external pure returns (uint256) {
        return HahaConstants.MINT_REWARDS_PER_DAY;
    }


    function earner(bytes32 actionId) external view returns (EarnerConfig memory) {
        return _earner[actionId];
    }

    function earnerActionIds() external view returns (bytes32[] memory) {
        return _actionIds;
    }

    function userEarnedToday(bytes32 actionId, bytes32 aiId) public view returns (uint64 count) {
        DayCounter memory c = _userDailyCount[actionId][aiId];
        return c.dayIndex == _currentDay() ? c.count : 0;
    }

    function globalPointsToday(bytes32 actionId) public view returns (uint256) {
        DayCounter256 memory g = _globalDailyPoints[actionId];
        return g.dayIndex == _currentDay() ? g.amount : 0;
    }

    function uniqueKeyUsed(bytes32 actionId, bytes32 aiId, bytes32 uniqueKey)
        external
        view
        returns (bool)
    {
        uint64 stored = _keyDay[actionId][aiId][uniqueKey];
        if (stored == 0) return false;
        if (stored == type(uint64).max) return true;
        return stored == _currentDay();
    }

    function pairClaimedToday(bytes32 actionId, bytes32 aiId, bytes32 uniqueKey)
        external
        view
        returns (bool)
    {
        return _keyDay[actionId][aiId][uniqueKey] == _currentDay();
    }

    function spenderBudget(address spender) external view returns (SpenderBudget memory) {
        return _budget[spender];
    }

    function spenderUsedToday(address spender, bytes32 aiId)
        external
        view
        returns (uint256 userPoints, uint256 globalPoints)
    {
        uint64 day = _currentDay();
        DayCounter256 memory ug = _spendUserGross[spender][aiId];
        DayCounter256 memory gg = _spendGlobalGross[spender];
        userPoints = ug.dayIndex == day ? ug.amount : 0;
        globalPoints = gg.dayIndex == day ? gg.amount : 0;
    }

    function statusOf(address user) public view returns (PointsStatus memory s) {
        uint64 day = _currentDay();
        s.currentDay = day;
        s.nextResetAt = uint64((uint256(day) + 1) * 86400);
        s.mintRewardsPerDay = uint8(HahaConstants.MINT_REWARDS_PER_DAY);
        s.gameRoundsPerDay = uint8(HahaConstants.GAME_ROUNDS_PER_DAY);

        if (user == address(0)) return s;

        HahaAiIdentity.Result memory ai = HahaAiIdentity.aiIdentityOf(IBinanceAiRegistry(aiRegistry), user);
        if (!ai.ok) return s;

        s.aiId = ai.aiId;
        s.holdsAi = true;
        s.balance = _balance[ai.aiId];
        s.holdsName = IRegistrarBalance(registrar).balanceOf(user) > 0;

        s.checkInToday = (_hasCheckedIn[ai.aiId] && _lastCheckInDay[ai.aiId] == day) ? 1 : 0;

        DayCounter memory mc = _mintRewardDay[ai.aiId];
        s.mintRewardsToday = mc.dayIndex == day ? mc.count : 0;

        DayClaim memory lc = _likeClaim[ai.aiId];
        s.likeToday = (lc.done && lc.dayIndex == day) ? 1 : 0;

        DayClaim memory rc = _retweetClaim[ai.aiId];
        s.retweetToday = (rc.done && rc.dayIndex == day) ? 1 : 0;

        DayClaim memory cc = _commentClaim[ai.aiId];
        s.commentToday = (cc.done && cc.dayIndex == day) ? 1 : 0;

        DayCounter memory gr = _gameRounds[ai.aiId];
        s.gameRoundsToday = gr.dayIndex == day ? gr.count : 0;

        s.reviewsGivenToday = userEarnedToday(HahaConstants.ACTION_REVIEW_GIVE, ai.aiId);
        s.reviewsReceivedToday = userEarnedToday(HahaConstants.ACTION_REVIEW_RECEIVE, ai.aiId);

        s.followClaimed = _followClaimed[ai.aiId];
    }

    function statusOfAi(bytes32 aiId) external view returns (PointsStatus memory s) {
        uint64 day = _currentDay();
        s.currentDay = day;
        s.nextResetAt = uint64((uint256(day) + 1) * 86400);
        s.mintRewardsPerDay = uint8(HahaConstants.MINT_REWARDS_PER_DAY);
        s.gameRoundsPerDay = uint8(HahaConstants.GAME_ROUNDS_PER_DAY);
        s.aiId = aiId;

        s.balance = _balance[aiId];
        s.checkInToday = (_hasCheckedIn[aiId] && _lastCheckInDay[aiId] == day) ? 1 : 0;

        DayCounter memory mc = _mintRewardDay[aiId];
        s.mintRewardsToday = mc.dayIndex == day ? mc.count : 0;

        DayClaim memory lc = _likeClaim[aiId];
        s.likeToday = (lc.done && lc.dayIndex == day) ? 1 : 0;

        DayClaim memory rc = _retweetClaim[aiId];
        s.retweetToday = (rc.done && rc.dayIndex == day) ? 1 : 0;

        DayClaim memory cc = _commentClaim[aiId];
        s.commentToday = (cc.done && cc.dayIndex == day) ? 1 : 0;

        DayCounter memory gr = _gameRounds[aiId];
        s.gameRoundsToday = gr.dayIndex == day ? gr.count : 0;

        s.reviewsGivenToday = userEarnedToday(HahaConstants.ACTION_REVIEW_GIVE, aiId);
        s.reviewsReceivedToday = userEarnedToday(HahaConstants.ACTION_REVIEW_RECEIVE, aiId);

        s.followClaimed = _followClaimed[aiId];

        try IBinanceAiRegistry(aiRegistry).ownerOf(uint256(aiId)) returns (address holder) {
            if (holder != address(0)) {
                s.holdsAi = true;
                s.holdsName = IRegistrarBalance(registrar).balanceOf(holder) > 0;
            }
        } catch {
        }
    }

    function actionStatus(address user, bytes32[] calldata actionIds)
        external
        view
        returns (ActionStatus[] memory out)
    {
        if (actionIds.length > HahaConstants.MAX_STATUS_ACTIONS) revert TooManyActions(actionIds.length);

        HahaAiIdentity.Result memory ai = HahaAiIdentity.aiIdentityOf(IBinanceAiRegistry(aiRegistry), user);
        uint64 day = _currentDay();

        out = new ActionStatus[](actionIds.length);
        for (uint256 i = 0; i < actionIds.length; ++i) {
            bytes32 id = actionIds[i];
            EarnerConfig memory cfg = _earner[id];

            out[i] = ActionStatus({
                actionId: id,
                pointsEach: cfg.points,
                todayCount: ai.ok ? userEarnedToday(id, ai.aiId) : 0,
                dailyCap: cfg.perUserDailyCap,
                nextResetAt: uint64((uint256(day) + 1) * 86400),
                globalPointsToday: globalPointsToday(id),
                globalDailyPoints: cfg.globalDailyPoints,
                keyMode: uint8(cfg.keyMode),
                enabled: cfg.enabled,
                underCap: ai.ok && cfg.enabled && _underCap(id, ai.aiId, cfg, day)
            });
        }
    }

    function spendBudgetOf(address spender) external view returns (SpenderBudget memory) {
        return _budget[spender];
    }

    function game(bytes32 gameId) external view returns (GameConfig memory) {
        return _games[gameId];
    }

    function gameRoundsToday(bytes32 aiId) public view returns (uint64) {
        DayCounter memory c = _gameRounds[aiId];
        return c.dayIndex == _currentDay() ? c.count : 0;
    }

    function gameRoundsPerDay() external pure returns (uint64) {
        return HahaConstants.GAME_ROUNDS_PER_DAY;
    }

    function roundOf(uint256 sessionId)
        external
        view
        returns (bytes32 gameId, bytes32 aiId, address player, uint64 openDay, bool claimed)
    {
        GameRound memory r = _rounds[sessionId];
        return (r.gameId, r.aiId, r.player, r.openDay, r.claimed);
    }

    function nextSessionId() external view returns (uint256) {
        return _nextSessionId;
    }

    function gamePointsToday(bytes32 gameId, bytes32 aiId)
        external
        view
        returns (uint256 userPoints, uint256 globalPoints)
    {
        uint64 day = _currentDay();
        DayCounter256 memory u = _gameUserPoints[gameId][aiId];
        DayCounter256 memory g = _gameGlobalPoints[gameId];
        userPoints = u.dayIndex == day ? u.amount : 0;
        globalPoints = g.dayIndex == day ? g.amount : 0;
    }


    function _currentDay() private view returns (uint64) {
        return uint64(block.timestamp / 86400);
    }

    function _requireEligible(address user) private view returns (HahaAiIdentity.Result memory) {
        HahaAiIdentity.Result memory ai = HahaAiIdentity.aiIdentityOf(IBinanceAiRegistry(aiRegistry), user);
        if (!ai.ok) revert AiRequired();
        if (IRegistrarBalance(registrar).balanceOf(user) == 0) revert NameRequired();
        return ai;
    }

    function _requireDayClaim(DayClaim memory c) private view {
        if (c.done && c.dayIndex == _currentDay()) revert AlreadyClaimedToday();
    }

    function _requireParamInRange(uint256 v) private pure {
        if (v > HahaConstants.MAX_POINT_PARAM) revert ParamTooLarge(v);
    }

    function _underCap(bytes32 actionId, bytes32 aiId, EarnerConfig memory cfg, uint64 day)
        private
        view
        returns (bool)
    {
        DayCounter memory uc = _userDailyCount[actionId][aiId];
        uint64 used = uc.dayIndex == day ? uc.count : 0;
        if (used >= cfg.perUserDailyCap) return false;

        DayCounter256 memory gc = _globalDailyPoints[actionId];
        uint256 globalToday = gc.dayIndex == day ? gc.amount : 0;
        return globalToday + cfg.points <= cfg.globalDailyPoints;
    }
}
