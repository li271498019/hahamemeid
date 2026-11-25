// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {HahaTestBase} from "../HahaTestBase.sol";
import {HahaValidation} from "src/HahaValidation.sol";

/// @notice G13 验证注册表（HahaValidation）测试。
///         覆盖 T1–T6：接口签名、验证者限制、验证请求、验证结果、争议复核、读接口。
contract HahaValidationTest is HahaTestBase {
    HahaValidation internal validation;

    // 常用请求文档
    string internal constant REQ_URI = "https://example.com/req/1.json";
    string internal constant REQ_URI_2 = "https://example.com/req/2.json";
    string internal constant RESP_URI = "https://example.com/evidence/1.json";
    string internal constant TAG_ENDPOINT = "endpoint-reachable";
    string internal constant TAG_IDENTITY = "identity-verified";

    function setUp() public override {
        super.setUp();
        validation = new HahaValidation(ADMIN, address(identity));
    }

    // ---------------------------------------------------------------------
    // 工具
    // ---------------------------------------------------------------------

    /// @dev 让 `user` 铸名并激活 agent，返回 agentId。
    function _activateAgent(address user, string memory label) internal returns (uint256 agentId) {
        _register(user, label, 0); // 内部已 prank(user)
        vm.prank(user);
        agentId = identity.activateAgent(label, 0, "https://example.com/agent.json");
    }

    /// @dev 按 §3.4 公式算 requestHash。
    function _requestHash(address validatorAddr, uint256 agentId, string memory uri)
        internal
        pure
        returns (bytes32)
    {
        return keccak256(abi.encodePacked(validatorAddr, agentId, uri));
    }

    /// @dev 让管理员提交一次验证结果（100 分）。
    function _respond(bytes32 requestHash) internal {
        vm.prank(ADMIN);
        validation.validationResponse(requestHash, 100, RESP_URI, keccak256(bytes(RESP_URI)), TAG_ENDPOINT);
    }

    // ---------------------------------------------------------------------
    // T1 接口签名核对
    // ---------------------------------------------------------------------

    function test_T1_interface_signatures() public pure {
        // 写接口 selector（EIP-8004 Validation Registry，逐字核对）
        assertTrue(bytes4(keccak256("validationRequest(address,uint256,string,bytes32)")) == 0xaaf400c4);
        assertTrue(bytes4(keccak256("validationResponse(bytes32,uint8,string,bytes32,string)")) == 0x3d659a96);

        // 读接口 selector
        assertTrue(bytes4(keccak256("getValidationStatus(bytes32)")) == 0xff2febfc);
        assertTrue(bytes4(keccak256("getSummary(uint256,address[],string)")) == 0x1b7cabd6);
        assertTrue(bytes4(keccak256("getAgentValidations(uint256)")) == 0x8d5d0c2d);
        assertTrue(bytes4(keccak256("getValidatorRequests(address)")) == 0x4bf3158c);

        // v1 新增函数 selector（§2.5）
        assertTrue(bytes4(keccak256("dispute(bytes32)")) == 0xadd98c70);
        assertTrue(bytes4(keccak256("setValidator(address)")) == 0x1327d3d8);

        // 事件 topic0（含 indexed，§2.3）
        assertTrue(
            keccak256("ValidationRequest(address,uint256,string,bytes32)")
                == 0x530436c3634a98e1e626b0898be2f1e9980cc1bd2a78c07a0aba52d0a48a5059
        );
        assertTrue(
            keccak256("ValidationResponse(address,uint256,bytes32,uint8,string,bytes32,string)")
                == 0xafddf629e874ccc3963b6a888c477bd464a6c8525024fc88759ea3b2326349ae
        );
        assertTrue(
            keccak256("ValidationDisputed(bytes32,address)")
                == 0xe3d32c9b1e490818f4656d2753e75fede5d1b74df812d64ccab705df76583a72
        );
    }

    // ---------------------------------------------------------------------
    // T2 验证者限制
    // ---------------------------------------------------------------------

    function test_T2_initialValidatorIsAdmin() public view {
        assertEq(validation.validator(), ADMIN);
        assertEq(validation.admin(), ADMIN);
    }

    function test_T2_nonValidatorCannotRespond() public {
        uint256 agentId = _activateAgent(alice, "aliceval");
        bytes32 rh = _requestHash(ADMIN, agentId, REQ_URI);
        vm.prank(alice);
        validation.validationRequest(ADMIN, agentId, REQ_URI, rh);

        // 非验证者（alice）调 validationResponse → revert
        vm.prank(alice);
        vm.expectRevert(HahaValidation.NotValidator.selector);
        validation.validationResponse(rh, 100, RESP_URI, keccak256(bytes(RESP_URI)), TAG_ENDPOINT);
    }

    function test_T2_requestWithWrongValidatorReverts() public {
        uint256 agentId = _activateAgent(alice, "aliceval2");
        // 指定一个非当前验证者的地址 → revert
        vm.prank(alice);
        vm.expectRevert(HahaValidation.NotValidator.selector);
        validation.validationRequest(bob, agentId, REQ_URI, _requestHash(bob, agentId, REQ_URI));
    }

    function test_T2_setValidatorByAdminThenSwitch() public {
        // 管理员可换验证者
        vm.prank(ADMIN);
        validation.setValidator(carol);
        assertEq(validation.validator(), carol);

        // 换后旧验证者（admin）调 validationResponse → revert
        uint256 agentId = _activateAgent(alice, "aliceval3");
        bytes32 rh = _requestHash(carol, agentId, REQ_URI);
        vm.prank(alice);
        validation.validationRequest(carol, agentId, REQ_URI, rh);

        vm.prank(ADMIN);
        vm.expectRevert(HahaValidation.NotValidator.selector);
        validation.validationResponse(rh, 100, RESP_URI, keccak256(bytes(RESP_URI)), TAG_ENDPOINT);

        // 新验证者可调
        vm.prank(carol);
        validation.validationResponse(rh, 100, RESP_URI, keccak256(bytes(RESP_URI)), TAG_ENDPOINT);
    }

    function test_T2_nonAdminCannotSetValidator() public {
        vm.prank(alice);
        vm.expectRevert(HahaValidation.NotAdmin.selector);
        validation.setValidator(alice);
    }

    function test_T2_setValidatorZeroAddressReverts() public {
        vm.prank(ADMIN);
        vm.expectRevert(HahaValidation.ZeroAddress.selector);
        validation.setValidator(address(0));
    }

    // ---------------------------------------------------------------------
    // T3 验证请求
    // ---------------------------------------------------------------------

    function test_T3_ownerCanRequest() public {
        uint256 agentId = _activateAgent(alice, "aliceowner");
        bytes32 rh = _requestHash(ADMIN, agentId, REQ_URI);

        vm.prank(alice);
        vm.expectEmit(true, true, false, true, address(validation));
        emit HahaValidation.ValidationRequest(ADMIN, agentId, REQ_URI, rh);
        validation.validationRequest(ADMIN, agentId, REQ_URI, rh);
    }

    function test_T3_operatorCanRequest() public {
        uint256 agentId = _activateAgent(alice, "aliceop");

        // alice 设 bob 为 operator
        vm.prank(alice);
        identity.setAgentOperator(agentId, bob, true);

        bytes32 rh = _requestHash(ADMIN, agentId, REQ_URI);
        // operator（bob）调 validationRequest 成功
        vm.prank(bob);
        validation.validationRequest(ADMIN, agentId, REQ_URI, rh);
    }

    function test_T3_nonOwnerNonOperatorReverts() public {
        uint256 agentId = _activateAgent(alice, "aliceno");
        bytes32 rh = _requestHash(ADMIN, agentId, REQ_URI);

        // carol 既非 owner 也非 operator → revert
        vm.prank(carol);
        vm.expectRevert(HahaValidation.NotAuthorized.selector);
        validation.validationRequest(ADMIN, agentId, REQ_URI, rh);
    }

    function test_T3_wrongRequestHashReverts() public {
        uint256 agentId = _activateAgent(alice, "alicehash");
        bytes32 correct = _requestHash(ADMIN, agentId, REQ_URI);
        bytes32 wrong = _requestHash(ADMIN, agentId, REQ_URI_2); // 不同 URI → 不同 hash

        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(HahaValidation.InvalidRequestHash.selector, correct, wrong));
        validation.validationRequest(ADMIN, agentId, REQ_URI, wrong);
    }

    function test_T3_duplicateRequestHashReverts() public {
        uint256 agentId = _activateAgent(alice, "alicedup");
        bytes32 rh = _requestHash(ADMIN, agentId, REQ_URI);

        vm.startPrank(alice);
        validation.validationRequest(ADMIN, agentId, REQ_URI, rh);

        vm.expectRevert(abi.encodeWithSelector(HahaValidation.RequestAlreadyExists.selector, rh));
        validation.validationRequest(ADMIN, agentId, REQ_URI, rh);
        vm.stopPrank();
    }

    // ---------------------------------------------------------------------
    // T4 验证结果
    // ---------------------------------------------------------------------

    function test_T4_respondSuccess() public {
        uint256 agentId = _activateAgent(alice, "aliceresp");
        bytes32 rh = _requestHash(ADMIN, agentId, REQ_URI);
        vm.prank(alice);
        validation.validationRequest(ADMIN, agentId, REQ_URI, rh);

        bytes32 respHash = keccak256(bytes(RESP_URI));
        vm.prank(ADMIN);
        vm.expectEmit(true, true, true, false, address(validation));
        emit HahaValidation.ValidationResponse(ADMIN, agentId, rh, 100, RESP_URI, respHash, TAG_ENDPOINT);
        validation.validationResponse(rh, 100, RESP_URI, respHash, TAG_ENDPOINT);

        // 读回验证一致
        (address va, uint256 aid, uint8 r, bytes32 rhash, string memory tg, uint256 lu) =
            validation.getValidationStatus(rh);
        assertEq(va, ADMIN);
        assertEq(aid, agentId);
        assertEq(r, 100);
        assertEq(rhash, respHash);
        assertEq(tg, TAG_ENDPOINT);
        assertEq(lu, block.timestamp);
    }

    function test_T4_responseOver100Reverts() public {
        uint256 agentId = _activateAgent(alice, "alice101");
        bytes32 rh = _requestHash(ADMIN, agentId, REQ_URI);
        vm.prank(alice);
        validation.validationRequest(ADMIN, agentId, REQ_URI, rh);

        vm.prank(ADMIN);
        vm.expectRevert(abi.encodeWithSelector(HahaValidation.ResponseOutOfRange.selector, 101));
        validation.validationResponse(rh, 101, RESP_URI, keccak256(bytes(RESP_URI)), TAG_ENDPOINT);
    }

    function test_T4_respondNonexistentRequestHashReverts() public {
        bytes32 rh = keccak256("nonexistent");
        vm.prank(ADMIN);
        vm.expectRevert(abi.encodeWithSelector(HahaValidation.RequestNotFound.selector, rh));
        validation.validationResponse(rh, 100, RESP_URI, keccak256(bytes(RESP_URI)), TAG_ENDPOINT);
    }

    function test_T4_multipleResponsesOverride() public {
        uint256 agentId = _activateAgent(alice, "alicemulti");
        bytes32 rh = _requestHash(ADMIN, agentId, REQ_URI);
        vm.prank(alice);
        validation.validationRequest(ADMIN, agentId, REQ_URI, rh);

        // 第一次 100 分
        _respond(rh);
        // 第二次 0 分（覆盖）
        vm.prank(ADMIN);
        validation.validationResponse(rh, 0, RESP_URI, keccak256(bytes(RESP_URI)), TAG_ENDPOINT);

        (,, uint8 r,,,) = validation.getValidationStatus(rh);
        assertEq(r, 0);
    }

    // ---------------------------------------------------------------------
    // T5 争议复核
    // ---------------------------------------------------------------------

    function test_T5_disputeThenSameResponseUpheld() public {
        uint256 agentId = _activateAgent(alice, "alicedisp");
        bytes32 rh = _requestHash(ADMIN, agentId, REQ_URI);
        vm.prank(alice);
        validation.validationRequest(ADMIN, agentId, REQ_URI, rh);
        _respond(rh); // 100 分

        // 第三方 carol 争议
        vm.prank(carol);
        vm.expectEmit(true, true, false, false, address(validation));
        emit HahaValidation.ValidationDisputed(rh, carol);
        validation.dispute(rh);

        // 验证者复核：相同结果 → 维持原判（仍 100）
        _respond(rh);
        (,, uint8 r,,,) = validation.getValidationStatus(rh);
        assertEq(r, 100);
    }

    function test_T5_disputeThenDifferentResponseOverturned() public {
        uint256 agentId = _activateAgent(alice, "aliceoverturn");
        bytes32 rh = _requestHash(ADMIN, agentId, REQ_URI);
        vm.prank(alice);
        validation.validationRequest(ADMIN, agentId, REQ_URI, rh);
        _respond(rh); // 100 分

        vm.prank(carol);
        validation.dispute(rh);

        // 复核：不同结果 → 改判（0 分）
        vm.prank(ADMIN);
        validation.validationResponse(rh, 0, RESP_URI, keccak256(bytes(RESP_URI)), TAG_ENDPOINT);
        (,, uint8 r,,,) = validation.getValidationStatus(rh);
        assertEq(r, 0);
    }

    function test_T5_disputeTwiceReverts() public {
        uint256 agentId = _activateAgent(alice, "alice2x");
        bytes32 rh = _requestHash(ADMIN, agentId, REQ_URI);
        vm.prank(alice);
        validation.validationRequest(ADMIN, agentId, REQ_URI, rh);
        _respond(rh);

        vm.prank(carol);
        validation.dispute(rh);

        vm.prank(dave);
        vm.expectRevert(abi.encodeWithSelector(HahaValidation.AlreadyDisputed.selector, rh));
        validation.dispute(rh);
    }

    function test_T5_disputeAfterWindowReverts() public {
        uint256 agentId = _activateAgent(alice, "aliceexp");
        bytes32 rh = _requestHash(ADMIN, agentId, REQ_URI);
        vm.prank(alice);
        validation.validationRequest(ADMIN, agentId, REQ_URI, rh);
        _respond(rh);

        // 超过 3 天
        vm.warp(block.timestamp + 3 days + 1);
        vm.prank(carol);
        vm.expectRevert();
        validation.dispute(rh);
    }

    function test_T5_disputeNoResultReverts() public {
        uint256 agentId = _activateAgent(alice, "alicenores");
        bytes32 rh = _requestHash(ADMIN, agentId, REQ_URI);
        vm.prank(alice);
        validation.validationRequest(ADMIN, agentId, REQ_URI, rh);

        // 尚无验证结果 → revert
        vm.prank(carol);
        vm.expectRevert(abi.encodeWithSelector(HahaValidation.NoResultYet.selector, rh));
        validation.dispute(rh);
    }

    function test_T5_disputeByThirdParty() public {
        // 争议可由任意第三方（非 owner、非验证者）发起
        uint256 agentId = _activateAgent(alice, "alice3rd");
        bytes32 rh = _requestHash(ADMIN, agentId, REQ_URI);
        vm.prank(alice);
        validation.validationRequest(ADMIN, agentId, REQ_URI, rh);
        _respond(rh);

        vm.prank(dave); // 与请求、验证都无关的第三方
        validation.dispute(rh);
    }

    function test_T5_disputeAtExactWindowBoundarySucceeds() public {
        uint256 agentId = _activateAgent(alice, "alicebound");
        bytes32 rh = _requestHash(ADMIN, agentId, REQ_URI);
        vm.prank(alice);
        validation.validationRequest(ADMIN, agentId, REQ_URI, rh);
        _respond(rh);

        // 恰好 firstResponseTime + 3 天整点 → 仍可争议
        vm.warp(block.timestamp + 3 days);
        vm.prank(carol);
        validation.dispute(rh);
    }

    function test_T5_disputeOneSecondPastWindowReverts() public {
        uint256 agentId = _activateAgent(alice, "alice1s");
        bytes32 rh = _requestHash(ADMIN, agentId, REQ_URI);
        vm.prank(alice);
        validation.validationRequest(ADMIN, agentId, REQ_URI, rh);
        _respond(rh);

        // firstResponseTime + 3 天 + 1 秒 → revert
        vm.warp(block.timestamp + 3 days + 1);
        vm.prank(carol);
        vm.expectRevert();
        validation.dispute(rh);
    }

    function test_T5_updateResultDoesNotExtendWindow() public {
        uint256 agentId = _activateAgent(alice, "alicewin");
        bytes32 rh = _requestHash(ADMIN, agentId, REQ_URI);
        vm.prank(alice);
        validation.validationRequest(ADMIN, agentId, REQ_URI, rh);
        _respond(rh); // firstResponseTime 固定

        // 2 天后更新结果（不延长窗口）
        vm.warp(block.timestamp + 2 days);
        vm.prank(ADMIN);
        validation.validationResponse(rh, 50, RESP_URI, keccak256(bytes(RESP_URI)), TAG_ENDPOINT);

        // 距第一次结果已超 3 天（2 天后又 1 天）→ dispute revert
        vm.warp(block.timestamp + 1 days + 1);
        vm.prank(carol);
        vm.expectRevert();
        validation.dispute(rh);
    }

    // ---------------------------------------------------------------------
    // T6 读接口
    // ---------------------------------------------------------------------

    function test_T6_getSummaryBasic() public {
        uint256 agentId = _activateAgent(alice, "alicesum");

        // 3 次请求，分数 100 / 0 / 100，tag 均为 endpoint-reachable
        bytes32 rh1 = _requestHash(ADMIN, agentId, REQ_URI);
        bytes32 rh2 = _requestHash(ADMIN, agentId, REQ_URI_2);
        bytes32 rh3 = _requestHash(ADMIN, agentId, "https://example.com/req/3.json");
        vm.startPrank(alice);
        validation.validationRequest(ADMIN, agentId, REQ_URI, rh1);
        validation.validationRequest(ADMIN, agentId, REQ_URI_2, rh2);
        validation.validationRequest(ADMIN, agentId, "https://example.com/req/3.json", rh3);
        vm.stopPrank();

        vm.startPrank(ADMIN);
        validation.validationResponse(rh1, 100, RESP_URI, keccak256(bytes(RESP_URI)), TAG_ENDPOINT);
        validation.validationResponse(rh2, 0, RESP_URI, keccak256(bytes(RESP_URI)), TAG_ENDPOINT);
        validation.validationResponse(rh3, 100, RESP_URI, keccak256(bytes(RESP_URI)), TAG_ENDPOINT);
        vm.stopPrank();

        // 空验证者数组 = 不过滤；空 tag = 不过滤
        (uint64 count, uint8 avg) = validation.getSummary(agentId, new address[](0), "");
        assertEq(count, 3);
        assertEq(avg, 66); // (100+0+100)/3 = 66（整数除法）

        // 按 tag 过滤
        (uint64 countTag, uint8 avgTag) = validation.getSummary(agentId, new address[](0), TAG_ENDPOINT);
        assertEq(countTag, 3);
        assertEq(avgTag, 66);

        // 按验证者过滤（传 [ADMIN]）
        address[] memory vals = new address[](1);
        vals[0] = ADMIN;
        (uint64 countVal, uint8 avgVal) = validation.getSummary(agentId, vals, "");
        assertEq(countVal, 3);
        assertEq(avgVal, 66);

        // 传不匹配的验证者 → 0
        address[] memory other = new address[](1);
        other[0] = bob;
        (uint64 countOther, uint8 avgOther) = validation.getSummary(agentId, other, "");
        assertEq(countOther, 0);
        assertEq(avgOther, 0);
    }

    function test_T6_getAgentValidations() public {
        uint256 agentId = _activateAgent(alice, "aliceag");
        bytes32 rh1 = _requestHash(ADMIN, agentId, REQ_URI);
        bytes32 rh2 = _requestHash(ADMIN, agentId, REQ_URI_2);
        vm.startPrank(alice);
        validation.validationRequest(ADMIN, agentId, REQ_URI, rh1);
        validation.validationRequest(ADMIN, agentId, REQ_URI_2, rh2);
        vm.stopPrank();

        bytes32[] memory hashes = validation.getAgentValidations(agentId);
        assertEq(hashes.length, 2);
        assertEq(hashes[0], rh1);
        assertEq(hashes[1], rh2);
    }

    function test_T6_getValidatorRequests() public {
        uint256 agentId1 = _activateAgent(alice, "alicev1");
        uint256 agentId2 = _activateAgent(bob, "bobv1");
        bytes32 rh1 = _requestHash(ADMIN, agentId1, REQ_URI);
        bytes32 rh2 = _requestHash(ADMIN, agentId2, REQ_URI_2);
        vm.prank(alice);
        validation.validationRequest(ADMIN, agentId1, REQ_URI, rh1);
        vm.prank(bob);
        validation.validationRequest(ADMIN, agentId2, REQ_URI_2, rh2);

        bytes32[] memory hashes = validation.getValidatorRequests(ADMIN);
        assertEq(hashes.length, 2);
        assertEq(hashes[0], rh1);
        assertEq(hashes[1], rh2);
    }

    function test_T6_statusViaAgentValidations() public {
        // 最新结果经 getAgentValidations + getValidationStatus 可取得
        uint256 agentId = _activateAgent(alice, "alicefull");
        bytes32 rh = _requestHash(ADMIN, agentId, REQ_URI);
        vm.prank(alice);
        validation.validationRequest(ADMIN, agentId, REQ_URI, rh);
        _respond(rh);

        bytes32[] memory hashes = validation.getAgentValidations(agentId);
        assertEq(hashes.length, 1);
        (address va, uint256 aid, uint8 r, bytes32 rhash, string memory tg, uint256 lu) =
            validation.getValidationStatus(hashes[0]);
        assertEq(va, ADMIN);
        assertEq(aid, agentId);
        assertEq(r, 100);
        assertEq(rhash, keccak256(bytes(RESP_URI)));
        assertEq(tg, TAG_ENDPOINT);
        assertGt(lu, 0);
    }

    function test_T6_getIdentityRegistry() public view {
        assertEq(validation.getIdentityRegistry(), address(identity));
    }
}
