// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Test} from "forge-std/Test.sol";
import {HahaMetadata} from "src/HahaMetadata.sol";
import {Base64} from "@openzeppelin/contracts/utils/Base64.sol";

/// @title SvgTest
/// @notice `tokenURI` 的字节级校验。SPEC 12 与 SVG.md 要求：
///         三张样例解码后必须与 `assets/svg/samples/` 里的文件逐字节相同。
///
/// @dev 样例文件通过 `vm.readFile` 读入。`foundry.toml` 里已开
///      `fs_permissions = [{ access = "read", path = "./" }]`。
contract SvgTest is Test {
    HahaMetadata internal metadata;

    /// @dev 样例文件的相对路径。
    string internal constant SAMPLE_A = "./assets/svg/samples/a.haha.svg";
    string internal constant SAMPLE_MYAGENT = "./assets/svg/samples/myagent.meme.svg";
    string internal constant SAMPLE_LONG = "./assets/svg/samples/superlongagentname2026.haha.svg";

    function setUp() public {
        metadata = new HahaMetadata();
    }

    // ---------------------------------------------------------------------
    // 字节级比对
    // ---------------------------------------------------------------------

    /// @notice `a.haha` 的 SVG 必须与样例逐字节相同。
    function test_svg_a_haha_matchesSampleBytes() public view {
        string memory got = metadata.buildSvgOnly("a", 0);
        string memory want = vm.readFile(SAMPLE_A);
        assertEq(keccak256(bytes(got)), keccak256(bytes(want)), "a.haha svg mismatch");
    }

    /// @notice `myagent.meme` 的 SVG 必须与样例逐字节相同。
    function test_svg_myagent_meme_matchesSampleBytes() public view {
        string memory got = metadata.buildSvgOnly("myagent", 1);
        string memory want = vm.readFile(SAMPLE_MYAGENT);
        assertEq(keccak256(bytes(got)), keccak256(bytes(want)), "myagent.meme svg mismatch");
    }

    /// @notice `superlongagentname2026.haha` 的 SVG 必须与样例逐字节相同。
    function test_svg_superlong_matchesSampleBytes() public view {
        string memory got = metadata.buildSvgOnly("superlongagentname2026", 0);
        string memory want = vm.readFile(SAMPLE_LONG);
        assertEq(keccak256(bytes(got)), keccak256(bytes(want)), "long svg mismatch");
    }

    // ---------------------------------------------------------------------
    // 字号与基线（SVG.md 第 67 行的表）
    // ---------------------------------------------------------------------

    function test_fontTable() public view {
        _assertFszY("a", 0, 96, 284);                          // n=6
        _assertFszY("abc", 0, 90, 282);                        // n=8
        _assertFszY("myagent", 1, 60, 271);                    // n=12
        _assertFszY("abcdefghijklmnopqrs", 0, 30, 260);        // n=24，半偶数关键点
        _assertFszY("superlongagentname2026", 0, 26, 259);     // n=27
    }

    /// @notice `n = 24` 时基线是 260，不是 261。
    /// @dev 这是 SVG.md 明确要求卡住的点：`fsz = 30`，`30 * 0.35 = 10.5`，
    ///      半偶数舍入 `q = 10`（因为 `q = 10` 是偶数），`y = 260`。
    ///      如果实现成「`.5` 一律进位」会得到 261，与已批准生成器不一致。
    function test_baselineHalfEven_atN24() public view {
        string memory svg = metadata.buildSvgOnly("abcdefghijklmnopqrs", 0);
        // 从拼好的 SVG 里直接查 `y="260"` 与 `font-size="30"`。
        assertTrue(_contains(svg, 'y="260"'), "baseline must be 260");
        assertFalse(_contains(svg, 'y="261"'), "must not round .5 up");
        assertTrue(_contains(svg, 'font-size="30"'), "font size must be 30");
    }

    // ---------------------------------------------------------------------
    // tokenURI 结构
    // ---------------------------------------------------------------------

    /// @notice 返回值必须是 `data:application/json;base64,...`。
    function test_tokenUriPrefix() public view {
        string memory uri = metadata.build("a", 0);
        assertTrue(_startsWith(uri, "data:application/json;base64,"), "uri prefix");
    }

    /// @notice JSON 字段顺序固定为 name、description、image、attributes。
    function test_tokenUriJsonFieldOrder() public view {
        string memory json = _jsonOf("a", 0);

        uint256 iName = _indexOf(json, '"name"');
        uint256 iDesc = _indexOf(json, '"description"');
        uint256 iImg = _indexOf(json, '"image"');
        uint256 iAttr = _indexOf(json, '"attributes"');

        assertLt(iName, iDesc, "name before description");
        assertLt(iDesc, iImg, "description before image");
        assertLt(iImg, iAttr, "image before attributes");
    }

    /// @notice `name` 是 `label.tld`，不是合集名 `haha id`。
    function test_tokenUriJsonNameIsFullName() public view {
        string memory json = _jsonOf("abc", 1);
        assertTrue(_contains(json, '"name":"abc.meme"'), "name must be full name");
        assertFalse(_contains(json, '"name":"haha id"'), "must not be collection name");
    }

    /// @notice description 模板。
    function test_tokenUriJsonDescription() public view {
        string memory json = _jsonOf("abc", 0);
        assertTrue(
            _contains(json, '"description":"haha.meme agent identity for abc.haha"'),
            "description template"
        );
    }

    /// @notice `Length` 是 JSON 数字，且只统计 label 字节数。
    function test_tokenUriJsonLengthIsNumber() public view {
        string memory json = _jsonOf("abc", 0);
        assertTrue(
            _contains(json, '{"trait_type":"Length","display_type":"number","value":3}'),
            "length must be a number equal to label length"
        );
    }

    /// @notice TLD trait。
    function test_tokenUriJsonTldTrait() public view {
        assertTrue(
            _contains(_jsonOf("abc", 0), '{"trait_type":"TLD","value":"haha"}'), "haha tld trait"
        );
        assertTrue(
            _contains(_jsonOf("abc", 1), '{"trait_type":"TLD","value":"meme"}'), "meme tld trait"
        );
    }

    /// @notice `image` 解码后必须与 `buildSvgOnly` 完全一致。
    function test_tokenUriImageDecodesToSameSvg() public view {
        string memory svg = metadata.buildSvgOnly("myagent", 1);
        string memory image = string.concat("data:image/svg+xml;base64,", Base64.encode(bytes(svg)));

        string memory json = _jsonOf("myagent", 1);
        assertTrue(_contains(json, image), "image must be base64 of the same svg");
    }

    /// @notice 解码整条 tokenURI，JSON 必须与 `buildJsonFor` 一致（证明 Base64 无换行、标准字母表）。
    /// @dev OZ 5.1.0 的 `Base64` 只有 `encode`，没有 `decode`，所以这里自带一个标准解码器。
    ///      自带而不是引库，也让「解码结果 == 已知明文」成为一个真正的独立性校验。
    function test_tokenUriIsBase64OfJson() public view {
        string memory uri = metadata.build("abc", 0);
        string memory json = _jsonOf("abc", 0);

        // `build` 是 `data:application/json;base64,<b64>`；解出来必须等于明文 JSON。
        bytes memory b64 = _sliceBytes(bytes(uri), 29, bytes(uri).length);
        bytes memory decoded = _base64Decode(b64);
        assertEq(keccak256(decoded), keccak256(bytes(json)), "decoded json mismatch");
    }

    /// @dev 标准 Base64 解码。只接受 A-Z a-z 0-9 + / 与 = 填充。
    function _base64Decode(bytes memory data) internal pure returns (bytes memory out) {
        // 去掉尾部 '='
        uint256 len = data.length;
        uint256 pad = 0;
        while (len > 0 && data[len - 1] == "=") {
            --len;
            ++pad;
        }
        out = new bytes((len * 6) / 8);

        uint256 acc = 0;
        uint256 bits = 0;
        uint256 oi = 0;
        for (uint256 i = 0; i < len; ++i) {
            uint8 v = _b64Value(data[i]);
            acc = (acc << 6) | v;
            bits += 6;
            if (bits >= 8) {
                bits -= 8;
                out[oi++] = bytes1(uint8(acc >> bits));
            }
        }
    }

    function _b64Value(bytes1 c) internal pure returns (uint8) {
        uint8 x = uint8(c);
        if (x >= 65 && x <= 90) return x - 65; // A-Z
        if (x >= 97 && x <= 122) return x - 97 + 26; // a-z
        if (x >= 48 && x <= 57) return x - 48 + 52; // 0-9
        if (x == 43) return 62; // +
        if (x == 47) return 63; // /
        revert("bad base64 char");
    }

    // ---------------------------------------------------------------------
    // 非法 tld
    // ---------------------------------------------------------------------

    function test_invalidTldReverts() public {
        vm.expectRevert(abi.encodeWithSelector(HahaMetadata.InvalidTld.selector, uint8(2)));
        metadata.build("abc", 2);
    }

    // ---------------------------------------------------------------------
    // 体积
    // ---------------------------------------------------------------------

    /// @notice `HahaMetadata` 运行时字节码必须小于 24576（EIP-170）。
    /// @dev SVG.md 要求：超限时停下来报告，不要删渐变、图标或文字来硬塞。
    function test_metadataRuntimeSizeUnderLimit() public {
        uint256 size = address(metadata).code.length;
        emit log_named_uint("HahaMetadata runtime bytes", size);
        assertLt(size, 24576, "HahaMetadata exceeds EIP-170 limit");
    }

    // ---------------------------------------------------------------------
    // 工具
    // ---------------------------------------------------------------------

    /// @dev 把 `data:application/json;base64,<b64>` 解回明文 JSON。
    ///      `buildJsonFor` 的返回值带前缀，测试里做字符串断言前必须先解码。
    function _jsonOf(string memory label, uint8 tld) internal view returns (string memory) {
        string memory uri = metadata.buildJsonFor(label, tld);
        bytes memory raw = bytes(uri);
        assertTrue(_startsWith(uri, "data:application/json;base64,"), "buildJsonFor prefix");
        bytes memory b64 = _sliceBytes(raw, 29, raw.length);
        return string(_base64Decode(b64));
    }

    function _assertFszY(string memory label, uint8 tld, uint256 fsz, uint256 y) internal view {
        string memory svg = metadata.buildSvgOnly(label, tld);
        string memory yNeedle = string.concat('y="', vm.toString(y), '"');
        string memory fszNeedle = string.concat('font-size="', vm.toString(fsz), '"');
        assertTrue(_contains(svg, yNeedle), string.concat(label, ": baseline"));
        assertTrue(_contains(svg, fszNeedle), string.concat(label, ": font size"));
    }

    function _contains(string memory haystack, string memory needle) internal pure returns (bool) {
        bytes memory h = bytes(haystack);
        bytes memory n = bytes(needle);
        if (n.length == 0 || h.length < n.length) return false;
        for (uint256 i = 0; i <= h.length - n.length; ++i) {
            bool ok = true;
            for (uint256 j = 0; j < n.length; ++j) {
                if (h[i + j] != n[j]) {
                    ok = false;
                    break;
                }
            }
            if (ok) return true;
        }
        return false;
    }

    function _indexOf(string memory haystack, string memory needle) internal pure returns (uint256) {
        bytes memory h = bytes(haystack);
        bytes memory n = bytes(needle);
        for (uint256 i = 0; i <= h.length - n.length; ++i) {
            bool ok = true;
            for (uint256 j = 0; j < n.length; ++j) {
                if (h[i + j] != n[j]) {
                    ok = false;
                    break;
                }
            }
            if (ok) return i;
        }
        revert("not found");
    }

    function _startsWith(string memory s, string memory prefix) internal pure returns (bool) {
        bytes memory a = bytes(s);
        bytes memory b = bytes(prefix);
        if (a.length < b.length) return false;
        for (uint256 i = 0; i < b.length; ++i) {
            if (a[i] != b[i]) return false;
        }
        return true;
    }

    function _sliceBytes(bytes memory data, uint256 start, uint256 end)
        internal
        pure
        returns (bytes memory out)
    {
        out = new bytes(end - start);
        for (uint256 i = start; i < end; ++i) {
            out[i - start] = data[i];
        }
    }
}
