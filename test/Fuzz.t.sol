// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {HahaTestBase} from "./HahaTestBase.sol";
import {HahaRegistrar} from "src/HahaRegistrar.sol";
import {HahaNamehash} from "src/libraries/HahaNamehash.sol";
import {HahaConstants} from "src/libraries/HahaConstants.sol";

/// @title RegistrarFuzzTest
/// @notice SPEC 12「模糊与不变式」第一条：
///         「任意字节串，除非每个字节都是 `a-z0-9` 且长度合法，否则不能铸造成功。」
///
/// @dev 不变量（本测试证明的命题）：
///      `register(label, tld)` 成功 ⟹
///        `isValidLabel(label) ∧ 3 ≤ len(label) ≤ 32 ∧ ¬blacklisted ∧ ¬reserved ∧ ¬minted`
///      等价地：只要上述任一条件不成立，register 必须失败（revert）。
contract RegistrarFuzzTest is HahaTestBase {
    /// @notice 任意字节串：合法则成功（若其它条件也满足），非法则必定失败。
    /// @dev 用一个「干净」的 `.ai` 身份 + 每个用例前后重置冷却，避免冷却干扰。
    function testFuzz_arbitraryBytesOnlyValidLabelsSucceed(bytes memory raw) public {
        // 让 fuzz 输入直接当 label 用（可能是任意字节）
        vm.assume(raw.length <= 64); // 限制规模，超过 32 本来就会失败

        string memory label = string(raw);
        bool charsetOk = HahaNamehash.isValidLabel(label);
        uint256 len = raw.length;
        bool lengthOk = len >= HahaConstants.MIN_PUBLIC_LENGTH && len <= HahaConstants.MAX_LABEL_LENGTH;

        // 只测既不含黑名单也不含保留名的输入，避免被那两个条件遮蔽
        bool listOk = !policy.isBlacklisted(label) && !policy.isReserved(label);

        bool shouldSucceed = charsetOk && lengthOk && listOk;

        // 每次用独立身份，彻底绕开冷却
        address user = address(uint160(uint256(keccak256(abi.encode("user", raw)))));
        if (user == address(0)) return;
        vm.deal(user, 1 ether);
        _giveAi(user, string.concat("h", vm.toString(uint256(keccak256(abi.encode(raw))))));

        vm.prank(user);
        if (shouldSucceed) {
            registrar.register(label, 0);
            (string memory gotLabel, uint8 gotTld) = registrar.nameParts(uint256(_node(label, 0)));
            assertEq(gotLabel, label, "stored label round-trips");
            assertEq(gotTld, 0, "stored tld");
        } else {
            vm.expectRevert();
            registrar.register(label, 0);
        }
    }

    /// @notice 字符集不合法时，**任何**非空字节串都必须失败。
    /// @dev 这条比上面更窄但更硬：只要有一个字节不在 `a-z0-9`，就必须 `InvalidCharset`。
    function testFuzz_invalidCharsetAlwaysRejected(bytes memory raw, uint256 badPos, bytes1 badByte) public {
        vm.assume(raw.length >= 1 && raw.length <= 32);
        vm.assume(badPos < raw.length);
        // 保证 badByte 确实不合法
        uint8 b = uint8(badByte);
        bool isLower = b >= 0x61 && b <= 0x7a;
        bool isDigit = b >= 0x30 && b <= 0x39;
        vm.assume(!isLower && !isDigit);

        raw[badPos] = badByte;
        string memory label = string(raw);

        vm.prank(alice);
        vm.expectRevert(HahaRegistrar.InvalidCharset.selector);
        registrar.register(label, 0);
    }

    /// @notice 长度越界的合法字符集也必须失败，且报对错误。
    function testFuzz_lengthBounds(string memory label) public {
        bytes memory b = bytes(label);
        // 强制成合法字符集，只测长度维度
        for (uint256 i = 0; i < b.length; ++i) {
            b[i] = bytes1(uint8(0x61 + (uint8(b[i]) % 26))); // a-z
        }
        string memory clean = string(b);
        uint256 len = b.length;

        // 每个用例用独立身份，彻底绕开冷却与「已被铸造」的干扰。
        // handle 必须唯一：mock 里 `_handleOf[owner]` 与 `_ownerOfHandle[hash]` 是双向的，
        // 两个地址用同一个 handle 会互相覆盖。
        address user = address(uint160(uint256(keccak256(abi.encode("len", clean)))));
        vm.assume(user != address(0));
        _giveUniqueAi(user, "L");

        // **顺序很重要**：`vm.prank` 只作用于「下一次外部调用」。
        // 如果先 prank 再 `vm.expectRevert`，expectRevert 会消耗掉 prank，
        // 导致实际的 register 由测试合约自己调用（handleOf 为空 -> AiRequired）。
        // 正确写法：先 expectRevert，再 prank，最后调用。
        if (len == 0) {
            vm.expectRevert(HahaRegistrar.InvalidCharset.selector);
            vm.prank(user);
            registrar.register(clean, 0);
        } else if (len < 3) {
            vm.expectRevert(abi.encodeWithSelector(HahaRegistrar.LabelTooShort.selector, len, 3));
            vm.prank(user);
            registrar.register(clean, 0);
        } else if (len > 32) {
            vm.expectRevert(abi.encodeWithSelector(HahaRegistrar.LabelTooLong.selector, len, 32));
            vm.prank(user);
            registrar.register(clean, 0);
        } else {
            // 可能命中保留名，跳过这种情况
            vm.assume(!policy.isReserved(clean) && !policy.isBlacklisted(clean));
            vm.prank(user);
            registrar.register(clean, 0);
            assertEq(registrar.ownerOf(uint256(_node(clean, 0))), user);
        }
    }

    /// @notice 两个 TLD 永远不会撞号。
    function testFuzz_twoTldsNeverCollide(string memory label) public view {
        bytes32 haha = registrar.nodeOf(label, 0);
        bytes32 meme = registrar.nodeOf(label, 1);
        assertTrue(haha != meme, "haha and meme nodes must differ");
    }

    /// @notice namehash 是确定性的且与 labelhash 不同。
    function testFuzz_nodeIsNotLabelhash(string memory label) public view {
        bytes32 node = registrar.nodeOf(label, 0);
        bytes32 lh = keccak256(bytes(label));
        assertTrue(node != lh, "node must not equal labelhash");
    }

    /// @notice 冷却边界：任意时刻 t，`t < last + 3600` 必须失败，`t >= last + 3600` 必须成功。
    function testFuzz_cooldownBoundary(uint32 delta, uint8 tld) public {
        tld = uint8(bound(tld, 0, 1));
        // 每个用例用独立身份，避免 fuzz 重复调用时撞上「已铸造」。
        address user = address(uint160(uint256(keccak256(abi.encode("cd", uint256(delta), uint256(tld))))));
        vm.assume(user != address(0));
        string memory handle = _giveUniqueAi(user, "C");
        bytes32 aiId = keccak256(bytes(handle));

        // 第一次铸：用固定 label + tld 0，保证每个用例从同一状态开始
        vm.prank(user);
        registrar.register("aaa", 0);
        uint256 last = registrar.lastMintAt(aiId);
        assertTrue(last != 0, "first mint must record cooldown");

        delta = uint32(bound(delta, 0, 7200));
        vm.warp(last + delta);

        // 第二次铸一个未占用的 label
        string memory label = (uint256(keccak256(abi.encode(delta, tld))) % 2 == 0) ? "zzz" : "yyy";

        if (delta < 3600) {
            vm.expectRevert(abi.encodeWithSelector(HahaRegistrar.CooldownActive.selector, last + 3600));
            vm.prank(user);
            registrar.register(label, tld);
        } else {
            vm.assume(registrar.available(label, tld));
            vm.prank(user);
            registrar.register(label, tld);
            assertEq(registrar.ownerOf(uint256(_node(label, tld))), user);
        }
    }

    /// @notice 黑名单 208 个词：任何一个都不能公众铸出来。
    function testFuzz_allBlacklistedWordsRejected(uint256 index) public {
        string[208] memory words = _bannedWords();
        index = bound(index, 0, 207);
        string memory w = words[index];

        // 长度不足 3 的词会先被长度拦，这不算黑名单测试的失败，跳过
        vm.assume(bytes(w).length >= 3);

        vm.prank(alice);
        vm.expectRevert(HahaRegistrar.Blacklisted.selector);
        registrar.register(w, 0);

        // 管理员也不行
        vm.prank(ADMIN);
        vm.expectRevert(HahaRegistrar.Blacklisted.selector);
        registrar.adminMint(w, 0, bob);
    }

    /// @notice 保留名：只能管理员铸，公众必失败。
    function testFuzz_allReservedWordsOnlyAdminCanMint(uint256 index, uint8 tld) public {
        string[61] memory words = _reservedWords();
        index = bound(index, 0, 60);
        tld = uint8(bound(tld, 0, 1));
        string memory w = words[index];

        // 公众失败（长度 2 的会报 LabelTooShort，也算失败）
        vm.prank(alice);
        vm.expectRevert();
        registrar.register(w, tld);

        // 管理员成功
        vm.prank(ADMIN);
        registrar.adminMint(w, tld, bob);
        assertEq(registrar.ownerOf(uint256(_node(w, tld))), bob);
    }

    /// @dev 给地址配一个**按地址唯一**的 `.ai` handle。
    ///      mock 的 `_handleOf[owner]` 与 `_ownerOfHandle[hash]` 是双向映射，
    ///      两个地址共用同一 handle 会互相覆盖，导致本该有 `.ai` 的地址变成没有。
    ///      这里用地址的十六进制做 handle，保证唯一。
    /// @dev handle 必须**短且唯一**。主网 `.ai` 的 maxLen 是 20，
    ///      而 `vm.toString(address)` 有 42 个字符，超过主网限制，
    ///      虽然 mock 不校验，但为了与真实行为一致，这里用 8 位十六进制。
    function _giveUniqueAi(address user, string memory prefix) internal returns (string memory handle) {
        uint256 id = uint256(keccak256(abi.encode(prefix, user))) % 0xffffffffffffffff;
        handle = string.concat(prefix, _hex8(id));
        _giveAi(user, handle);
    }

    /// @dev 把 uint64 转成 16 位十六进制字符串，保证唯一性。
    function _hex8(uint256 v) internal pure returns (string memory) {
        bytes memory alphabet = "0123456789abcdef";
        bytes memory out = new bytes(16);
        for (uint256 i = 0; i < 16; ++i) {
            out[15 - i] = alphabet[(v >> (i * 4)) & 0xf];
        }
        return string(out);
    }

    // ---------------------------------------------------------------------
    // 名单（真实数据）
    // ---------------------------------------------------------------------

    function _bannedWords() internal pure returns (string[208] memory w) {
        // 从 blacklist-v2.txt 与 blacklist-v2.md 的完整列表，按字母序。
        // 与 TestLists.bannedHashes() 的顺序一致。
        string[208] memory t = [
            "8964", "ageplay", "alqaeda", "alshabaab", "antisemite", "army", "asan", "baipizhu",
            "bangongting", "bangzi", "beaner", "biden", "bokoharam", "buwei", "buzhang", "caiqi",
            "ccp", "chairman", "chairmanmao", "changwei", "childlover", "childporn", "chink", "chinky",
            "communist", "communistparty", "coon", "cpc", "daesh", "dang", "dangzhongyang", "darkie",
            "dengxiaoping", "dingxuexiang", "dongtu", "dongyabingfu", "dongyiyun", "dyke", "erdogan",
            "ethniccleansing", "extremism", "extremist", "fag", "fagaiwei", "faggot", "falungong",
            "fascist", "fraud", "gangdu", "gaschamber", "general", "genocide", "gestapo", "gongan",
            "gonganbu", "gongchandang", "gook", "gov", "government", "governor", "guoan", "guoanbu",
            "guofangbu", "guowuyuan", "hamas", "hanzheng", "harris", "heigui", "heil", "hezbollah",
            "hitler", "huaguofeng", "hujintao", "ishiba", "isil", "isis", "islamophobe", "jiangdu",
            "jiangjun", "jiangzemin", "jianwei", "jiefangjun", "jiguan", "jihad", "jingcha", "jiwei",
            "junguan", "junqu", "junwei", "kike", "kimjongun", "kishida", "kkk", "kukluxklan",
            "leejaemyung", "lianghui", "likeqiang", "lipeng", "liqiang", "liruhuan", "liushaoqi",
            "liusi", "lixi", "loli", "lolicon", "lolis", "lunzi", "macron", "maozedong", "marshal",
            "mayor", "meloni", "military", "minister", "modi", "moneylaundering", "nazi", "neonazi",
            "nige", "nigga", "nigger", "officer", "paki", "phish", "phishing", "pla", "police",
            "ponzi", "premier", "preteen", "putin", "qiaoshi", "quannengshen", "radicalization",
            "raghead", "renda", "rendadaibiao", "renminjiefangjun", "ribenguizi", "scam", "scammer",
            "scholz", "secretary", "shangjiang", "shaojiang", "shengzhang", "shizhang", "shotacon",
            "shuji", "spic", "starmer", "state", "sunak", "swastika", "taidu", "taiwanduli",
            "taliban", "terror", "terrorism", "terrorist", "tiananmen", "towelhead", "tranny", "trump",
            "underage", "waijiaobu", "wanghuning", "wangyi", "weiyuan", "wenge", "wenhuadageming",
            "wenjiabao", "wetback", "whitepower", "whitepride", "wujing", "xianggangduli", "xiaoriben",
            "xiejiao", "xijinping", "xinjiangduli", "xizangduli", "xjp", "yoon", "yuanshuai", "zangdu",
            "zelensky", "zhanqu", "zhaoleji", "zhengfawei", "zhengfu", "zhengxie", "zhengxieweiyuan",
            "zhengzhiju", "zhina", "zhinazhu", "zhonggong", "zhongguogongchandang", "zhongjiang",
            "zhongxuanbu", "zhongyang", "zhongzubu", "zhouenlai", "zhude", "zhurongji", "zhuxi",
            "zongli", "zongshuji"
        ];
        w = t;
    }

    function _reservedWords() internal pure returns (string[61] memory w) {
        string[61] memory t = [
            "admin", "arbitrum", "binance", "bitfinex", "bitget", "bitmex", "blur", "bnbchain",
            "brian", "brianarmstrong", "bscscan", "bybit", "changpeng", "circle", "coinbase",
            "coingecko", "coinmarketcap", "cz", "elonmusk", "erc8004", "ethereumfoundation",
            "etherscan", "gateio", "haha", "hahameme", "haydenadams", "heyi", "htx", "huobi",
            "justinsun", "kraken", "kucoin", "ledger", "meme", "metamask", "mexc", "musk",
            "official", "okx", "opbnb", "opensea", "optimism", "pancakeswap", "phantom", "polygon",
            "safepal", "saylor", "solanalabs", "spaceid", "star", "starxu", "support", "tether",
            "tokenpocket", "trezor", "trustwallet", "uniswap", "upbit", "vbuterin", "vitalik", "x402"
        ];
        w = t;
    }
}
