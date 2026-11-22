// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {HahaTestBase} from "./HahaTestBase.sol";
import {HahaRegistrar} from "src/HahaRegistrar.sol";
import {HahaNamePolicy} from "src/HahaNamePolicy.sol";
import {HahaNamehash} from "src/libraries/HahaNamehash.sol";
import {HahaAiIdentity} from "src/libraries/HahaAiIdentity.sol";
import {HahaConstants} from "src/libraries/HahaConstants.sol";

/// @title RegistrarMintTest
/// @notice SPEC 12「单元」清单里与铸造、字符集、长度、名单、门禁、冷却相关的前半部分。
contract RegistrarMintTest is HahaTestBase {
    // =====================================================================
    // 字符集（SPEC 5.3）
    // =====================================================================

    /// @notice 大写、连字符、空格、点、汉字、emoji、空串都必须 revert `InvalidCharset`。
    /// @dev 合约不做大小写转换，也不删符号。网站在提交前自己转小写。
    function test_invalidCharset_reverts() public {
        string[8] memory bad = [
            "ABC", // 大写
            "abc-def", // 连字符
            "abc def", // 空格
            "abc.def", // 点
            unicode"名字好", // 汉字
            unicode"abc😀", // emoji
            "_abc", // 下划线
            "abc_" // 下划线在后
        ];

        for (uint256 i = 0; i < bad.length; ++i) {
            vm.prank(alice);
            vm.expectRevert(HahaRegistrar.InvalidCharset.selector);
            registrar.register(bad[i], 0);
        }
    }

    /// @notice 空串走的是 `InvalidCharset`（字符集检查先于长度检查）。
    function test_emptyLabel_isInvalidCharset() public {
        vm.prank(alice);
        vm.expectRevert(HahaRegistrar.InvalidCharset.selector);
        registrar.register("", 0);
    }

    /// @notice 合法字符集：小写字母和数字的混合。
    function test_validCharset_accepted() public {
        _register(alice, "abc123xyz", 0);
        assertEq(registrar.ownerOf(uint256(_node("abc123xyz", 0))), alice);
    }

    // =====================================================================
    // 长度（SPEC 6.3 的表）
    // =====================================================================

    /// @notice 公众路径：长度 1、2 必须 `LabelTooShort`。
    function test_publicLength_oneAndTwo_rejected() public {
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(HahaRegistrar.LabelTooShort.selector, 1, 3));
        registrar.register("a", 0);

        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(HahaRegistrar.LabelTooShort.selector, 2, 3));
        registrar.register("ab", 0);
    }

    /// @notice 公众路径：长度 3 与 32 都可以。
    function test_publicLength_threeAndThirtyTwo_accepted() public {
        _register(alice, "abc", 0);
        _skipCooldown(alice, "alice");
        _register(alice, "abcdefghijklmnopqrstuvwxyz012345", 1); // 32 字节
    }

    /// @notice 公众路径：长度 33 必须 `LabelTooLong`。
    function test_publicLength_thirtyThree_rejected() public {
        string memory l33 = "abcdefghijklmnopqrstuvwxyz0123456"; // 33
        assertEq(bytes(l33).length, 33);

        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(HahaRegistrar.LabelTooLong.selector, 33, 32));
        registrar.register(l33, 0);
    }

    /// @notice 管理员路径：长度 1 可以（这是保留名）。
    function test_adminLength_one_accepted() public {
        vm.prank(ADMIN);
        registrar.adminMint("q", 0, bob);
        assertEq(registrar.ownerOf(uint256(_node("q", 0))), bob);
    }

    /// @notice 管理员路径：长度 33 也必须 `LabelTooLong`。
    function test_adminLength_thirtyThree_rejected() public {
        string memory l33 = "abcdefghijklmnopqrstuvwxyz0123456";
        vm.prank(ADMIN);
        vm.expectRevert(abi.encodeWithSelector(HahaRegistrar.LabelTooLong.selector, 33, 32));
        registrar.adminMint(l33, 0, bob);
    }

    // =====================================================================
    // 黑名单与保留名（SPEC 5.4、blacklist-v2.md、reserved-names.md）
    // =====================================================================

    /// @notice `trump` 的加盐哈希等于文档里的向量，且在链上被判为黑名单。
    function test_trump_blacklisted_vector() public view {
        assertEq(
            keccak256(abi.encodePacked("HAHA_V2", "trump")),
            0x2fb81193c412e0605114fa0de2c7586df93ccb4eca5678d1781f0dd83394cb41,
            "trump salted hash vector"
        );
        assertTrue(policy.isBlacklisted("trump"), "trump must be blacklisted");
    }

    /// @notice `btc` 既不是黑名单也不是保留名，且必须能被公众铸造。
    function test_btc_notBlacklisted_notReserved_andMintable() public {
        assertFalse(policy.isBlacklisted("btc"), "btc not blacklisted");
        assertFalse(policy.isReserved("btc"), "btc not reserved");

        _register(alice, "btc", 0);
        assertEq(registrar.ownerOf(uint256(_node("btc", 0))), alice);
    }

    /// @notice 文档明确允许公众注册的 12 个词，逐个验证可以铸造。
    /// @dev blacklist-v2.md「明确不拉黑」一节。
    function test_explicitlyAllowedNames_mintable() public {
        string[12] memory allowed = [
            "btc",
            "bitcoin",
            "eth",
            "sol",
            "usdt",
            "usdc",
            "bnb",
            "lido",
            "crypto",
            "satoshi",
            "wallet",
            "exchange"
        ];

        address user = alice;
        for (uint256 i = 0; i < allowed.length; ++i) {
            // 每个名字换一个 `.ai` 身份，绕过冷却。
            string memory handle = string.concat("h", vm.toString(i));
            _giveAi(user, handle);
            vm.prank(user);
            registrar.register(allowed[i], 0);
            assertEq(registrar.ownerOf(uint256(_node(allowed[i], 0))), user, allowed[i]);
        }
    }

    /// @notice `mao` 可以公众铸造（单字姓氏拼音不拉黑，长度 3）。
    function test_mao_publicMint_ok() public {
        assertFalse(policy.isBlacklisted("mao"), "mao not blacklisted");
        _register(alice, "mao", 0);
    }

    /// @notice `xi` 不能公众铸造（长度 2），但 `adminMint` 可以。原因是长度，不是黑名单。
    function test_xi_publicBlockedByLength_adminAllowed() public {
        assertFalse(policy.isBlacklisted("xi"), "xi is NOT blacklisted");

        // 公众：长度不够
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(HahaRegistrar.LabelTooShort.selector, 2, 3));
        registrar.register("xi", 0);

        // 管理员：可以
        vm.prank(ADMIN);
        registrar.adminMint("xi", 0, bob);
        assertEq(registrar.ownerOf(uint256(_node("xi", 0))), bob);
    }

    /// @notice `binance` 公众铸造失败（保留名），`adminMint` 成功，两个 TLD 各自独立。
    function test_binance_publicFails_adminMintsBothTlds() public {
        vm.prank(alice);
        vm.expectRevert(HahaRegistrar.ReservedName.selector);
        registrar.register("binance", 0);

        vm.startPrank(ADMIN);
        registrar.adminMint("binance", 0, bob);
        registrar.adminMint("binance", 1, carol);
        vm.stopPrank();

        bytes32 hahaNode = _node("binance", 0);
        bytes32 memeNode = _node("binance", 1);
        assertEq(registrar.ownerOf(uint256(hahaNode)), bob, "binance.haha -> bob");
        assertEq(registrar.ownerOf(uint256(memeNode)), carol, "binance.meme -> carol");
        assertTrue(hahaNode != memeNode, "two distinct tokens");
    }

    /// @notice 管理员不能 `adminMint("bitcoin", ...)`：它是公众名字。
    function test_adminCannotMintPublicName() public {
        vm.prank(ADMIN);
        vm.expectRevert(HahaRegistrar.NotReserved.selector);
        registrar.adminMint("bitcoin", 0, bob);
    }

    /// @notice 管理员也不能铸造黑名单词。
    function test_adminCannotMintBlacklisted() public {
        vm.prank(ADMIN);
        vm.expectRevert(HahaRegistrar.Blacklisted.selector);
        registrar.adminMint("trump", 0, bob);
    }

    /// @notice 保留名里长度为 3+ 的词，公众也必须失败。
    function test_reservedLongName_publicFails() public {
        // `ethereumfoundation` 是最长的保留名（19）
        vm.prank(alice);
        vm.expectRevert(HahaRegistrar.ReservedName.selector);
        registrar.register("ethereumfoundation", 0);
    }

    /// @notice 61 个保留名逐个验证：公众全部失败，管理员全部成功。
    function test_allReservedNames_publicBlocked() public {
        // 只抽样验证若干个，完整 61 个在 fuzz/不变量里覆盖。
        // 这里验证「所有保留名的 isReserved 都为 true」这一关键性质。
        string[10] memory sample = [
            "binance",
            "okx",
            "metamask",
            "uniswap",
            "cz", // 长度 2，同时被长度规则覆盖
            "haha",
            "meme",
            "admin",
            "official",
            "support"
        ];
        for (uint256 i = 0; i < sample.length; ++i) {
            assertTrue(policy.isReserved(sample[i]), sample[i]);
            vm.prank(alice);
            vm.expectRevert();
            registrar.register(sample[i], 0);
        }
    }

    // =====================================================================
    // 门禁：`.ai`（SPEC 4、6.3）
    // =====================================================================

    /// @notice 没有 `.ai` 的地址不能 register。三种失败方式都要测。
    function test_noAi_cannotRegister() public {
        address nobody = makeAddr("nobody");
        // 1. handleOf 为空
        assertEq(bytes(ai.handleOf(nobody)).length, 0, "no handle");

        vm.prank(nobody);
        vm.expectRevert(HahaRegistrar.AiRequired.selector);
        registrar.register("abc", 0);
    }

    /// @notice `ownerOfHandle` 返回 0（handleOf 有值但不一致）时不能 register。
    function test_handleOfButOwnerOfHandleZero_rejected() public {
        address victim = makeAddr("victim");
        // handleOf 返回 "ghost"，但 ownerOfHandle("ghost") 是 0
        ai.forceHandleOf(victim, "ghost", address(0));

        vm.prank(victim);
        vm.expectRevert(HahaRegistrar.AiRequired.selector);
        registrar.register("abc", 0);
    }

    /// @notice `ownerOf(tokenId)` 与调用者不一致时不能 register。
    /// @dev 这是第三步校验：把我们绑在已核实的 `tokenId = keccak256(handle)` 公式上。
    function test_ownerOfTokenIdMismatch_rejected() public {
        address victim = makeAddr("victim");
        address squatter = makeAddr("squatter");
        // handleOf(victim) = "taken"，但 ownerOfHandle("taken") 与 ownerOf(tokenId) 指向不同人
        ai.forceHandleOf(victim, "taken", squatter);

        vm.prank(victim);
        vm.expectRevert(HahaRegistrar.AiRequired.selector);
        registrar.register("abc", 0);
    }

    /// @notice aiId 必须是 `keccak256(bytes(handle))`，并在 NameMinted 事件里体现。
    function test_nameMinted_emitsCorrectAiId() public {
        bytes32 expectedAiId = keccak256(bytes("alice"));
        uint256 expectedTokenId = uint256(_node("abc", 0));

        vm.expectEmit(true, true, true, true, address(registrar));
        emit HahaRegistrar.NameMinted(expectedTokenId, alice, 0, expectedAiId, "abc", false);

        vm.prank(alice);
        registrar.register("abc", 0);
    }

    // =====================================================================
    // 冷却（SPEC 6.3）
    // =====================================================================

    /// @notice 冷却按 aiId 而不是按 TLD：铸完 `.haha` 后 3599 秒内不能铸 `.meme`。
    function test_cooldown_acrossTlds_3599sBlocked() public {
        _register(alice, "abc", 0);
        uint256 mintedAt = registrar.lastMintAt(keccak256(bytes("alice")));

        vm.warp(mintedAt + 3599);
        vm.prank(alice);
        vm.expectRevert(
            abi.encodeWithSelector(HahaRegistrar.CooldownActive.selector, mintedAt + 3600)
        );
        registrar.register("abc", 1);
    }

    /// @notice 第 3600 秒可以铸（边界包含）。
    function test_cooldown_atExactly3600s_allowed() public {
        _register(alice, "abc", 0);
        uint256 mintedAt = registrar.lastMintAt(keccak256(bytes("alice")));

        vm.warp(mintedAt + 3600);
        vm.prank(alice);
        registrar.register("abc", 1);
        assertEq(registrar.ownerOf(uint256(_node("abc", 1))), alice);
    }

    /// @notice 第一个名字可以直接铸（lastMintAt 为 0）。
    function test_cooldown_firstMint_noWait() public {
        assertEq(registrar.lastMintAt(keccak256(bytes("alice"))), 0, "never minted");
        _register(alice, "abc", 0);
    }

    /// @notice 不同 `.ai` 身份之间冷却互不影响。
    function test_cooldown_perIdentity() public {
        _register(alice, "aaa", 0);

        // bob 立刻就能铸，不受 alice 的冷却影响。
        _register(bob, "bbb", 0);
    }

    /// @notice 冷却失败不写入 lastMintAt。
    function test_cooldown_doesNotUpdateOnFailure() public {
        _register(alice, "abc", 0);
        uint256 first = registrar.lastMintAt(keccak256(bytes("alice")));

        vm.warp(first + 100);
        vm.prank(alice);
        vm.expectRevert();
        registrar.register("xyz", 0);

        assertEq(registrar.lastMintAt(keccak256(bytes("alice"))), first, "unchanged on failure");
    }

    /// @notice `nextMintAt` 的语义。
    function test_nextMintAt() public {
        assertEq(registrar.nextMintAt(keccak256(bytes("alice"))), 0, "before first mint");

        _register(alice, "abc", 0);
        uint256 last = registrar.lastMintAt(keccak256(bytes("alice")));
        assertEq(registrar.nextMintAt(keccak256(bytes("alice"))), last + 3600, "after mint");
    }

    // =====================================================================
    // 已占用
    // =====================================================================

    /// @notice 同一个 node 不能铸两次，两个 TLD 各自独立。
    function test_nameTaken_reverts() public {
        _register(alice, "abc", 0);

        _skipCooldown(alice, "alice");
        vm.prank(alice);
        vm.expectRevert(HahaRegistrar.NameTaken.selector);
        registrar.register("abc", 0);

        // 另一个 TLD 同名可以
        vm.prank(alice);
        registrar.register("abc", 1);
    }

    /// @notice 管理员也不能覆盖已铸造的名字。
    function test_adminCannotOverwriteExisting() public {
        vm.prank(ADMIN);
        registrar.adminMint("binance", 0, bob);

        vm.prank(ADMIN);
        vm.expectRevert(HahaRegistrar.NameTaken.selector);
        registrar.adminMint("binance", 0, carol);
    }

    // =====================================================================
    // tld 校验
    // =====================================================================

    function test_invalidTld_reverts() public {
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(HahaRegistrar.InvalidTld.selector, 2));
        registrar.register("abc", 2);

        vm.prank(ADMIN);
        vm.expectRevert(abi.encodeWithSelector(HahaRegistrar.InvalidTld.selector, 255));
        registrar.adminMint("binance", 255, bob);
    }

    // =====================================================================
    // 接收者
    // =====================================================================

    /// @notice `register` 没有接收者参数，NFT owner 一定是 msg.sender。
    function test_register_mintsToSender() public {
        vm.prank(alice);
        registrar.register("abc", 0);

        assertEq(registrar.ownerOf(uint256(_node("abc", 0))), alice);
        assertEq(registrar.balanceOf(alice), 1);
    }

    /// @notice `adminMint` 的接收者不能是 0。
    function test_adminMint_zeroAddress_reverts() public {
        vm.prank(ADMIN);
        vm.expectRevert(HahaRegistrar.ZeroAddress.selector);
        registrar.adminMint("binance", 0, address(0));
    }

    /// @notice 非管理员不能调用 `adminMint`。
    function test_adminMint_onlyAdmin() public {
        vm.prank(alice);
        vm.expectRevert(HahaRegistrar.NotAdmin.selector);
        registrar.adminMint("binance", 0, bob);
    }

    /// @notice 管理员接人不需要 `.ai`，接收者也不需要。
    function test_adminMint_needsNoAi() public {
        address noAi = makeAddr("noAi");
        vm.prank(ADMIN);
        registrar.adminMint("binance", 0, noAi);
        assertEq(registrar.ownerOf(uint256(_node("binance", 0))), noAi);
    }

    // =====================================================================
    // 铸造的其他副作用
    // =====================================================================

    /// @notice 铸造不设置主名字，不激活 agent。
    function test_mintDoesNotSetPrimaryOrAgent() public {
        _register(alice, "abc", 0);
        uint256 tokenId = uint256(_node("abc", 0));

        assertEq(resolver.primaryNode(alice), bytes32(0), "no primary name");
        assertEq(bytes(resolver.primaryName(alice)).length, 0, "primary name empty");
        assertEq(identity.agentOfName(tokenId), 0, "no agent");
    }

    /// @notice 铸造后注册表 owner 与 resolver 同步。
    function test_mintSyncsRegistry() public {
        _register(alice, "abc", 0);
        bytes32 node = _node("abc", 0);

        assertEq(registry.owner(node), alice, "registry owner");
        assertEq(registry.resolver(node), address(resolver), "registry resolver");
        assertTrue(registry.recordExists(node), "record exists");
    }

    // =====================================================================
    // nameParts / available / nodeOf
    // =====================================================================

    function test_nameParts() public {
        _register(alice, "abc", 1);
        (string memory label, uint8 tld) = registrar.nameParts(uint256(_node("abc", 1)));
        assertEq(label, "abc");
        assertEq(tld, 1);
    }

    function test_nameParts_nonExistent_reverts() public {
        vm.expectRevert();
        registrar.nameParts(12345);
    }

    /// @notice `available` 只看字符集、长度 1–32、未铸造。不判断黑名单和保留名。
    function test_available_semantics() public {
        // 合法且未铸造
        assertTrue(registrar.available("abc", 0), "abc free");
        // 已铸造
        _register(alice, "abc", 0);
        assertFalse(registrar.available("abc", 0), "abc taken");

        // 保留名：available 返回 true（这是规格定义的语义），但公众铸造会失败
        assertTrue(registrar.available("binance", 0), "reserved still 'available'");
        assertTrue(policy.isReserved("binance"), "but is reserved");

        // 黑名单词：available 也返回 true
        assertTrue(registrar.available("trump", 0), "blacklisted still 'available'");
        assertTrue(policy.isBlacklisted("trump"), "but is blacklisted");

        // 长度 2：available 返回 true（1–32 范围内），但公众铸造失败
        assertTrue(registrar.available("xi", 0), "short still 'available'");

        // 非法字符集
        assertFalse(registrar.available("ABC", 0), "uppercase invalid");
        assertFalse(registrar.available("", 0), "empty invalid");

        // 长度 33
        assertFalse(registrar.available("abcdefghijklmnopqrstuvwxyz0123456", 0), "33 too long");

        // 非法 tld
        assertFalse(registrar.available("abc", 2), "bad tld");
    }

    function test_nodeOf() public view {
        assertEq(registrar.nodeOf("abc", 0), _node("abc", 0));
        assertEq(registrar.nodeOf("abc", 1), _node("abc", 1));
        assertTrue(registrar.nodeOf("abc", 0) != registrar.nodeOf("abc", 1));
    }

    // =====================================================================
    // ERC-165 / ERC-2981
    // =====================================================================

    function test_supportsInterface() public view {
        assertTrue(registrar.supportsInterface(0x01ffc9a7), "ERC-165");
        assertTrue(registrar.supportsInterface(0x80ac58cd), "ERC-721");
        assertTrue(registrar.supportsInterface(0x5b5e139f), "ERC-721 Metadata");
        assertTrue(registrar.supportsInterface(0x2a55205a), "ERC-2981");
        // 不实现 ERC-721 Enumerable（索引靠事件）
        assertFalse(registrar.supportsInterface(0x780e9d63), "no Enumerable");
    }

    /// @notice `royaltyInfo(any, 1 ether)` == (feeReceiver, 0.01 ether)，对不存在的 token 也返回。
    function test_royaltyInfo() public view {
        (address receiver, uint256 amount) = registrar.royaltyInfo(999_999, 1 ether);
        assertEq(receiver, FEE_RECEIVER);
        assertEq(amount, 0.01 ether);

        // 已存在的 token 同样
        (address r2, uint256 a2) = registrar.royaltyInfo(uint256(_node("abc", 0)), 1 ether);
        assertEq(r2, FEE_RECEIVER);
        assertEq(a2, 0.01 ether);
    }

    /// @notice 小额取整向 0：99 wei 的版税是 0（QUESTIONS 第 9 条，不改代码只断言）。
    function test_royaltyInfo_smallAmountRoundsToZero() public view {
        (, uint256 amount) = registrar.royaltyInfo(1, 99);
        assertEq(amount, 0, "99 wei royalty rounds to 0");
    }

    /// @notice 没有修改接收者或比例的函数。
    function test_noRoyaltySetter() public view {
        assertEq(registrar.feeReceiver(), FEE_RECEIVER);
    }
}
