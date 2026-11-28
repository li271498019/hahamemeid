// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Base64} from "@openzeppelin/contracts/utils/Base64.sol";
import {Strings} from "@openzeppelin/contracts/utils/Strings.sol";

import {IHahaDogModel} from "../interfaces/IHahaDog.sol";
import {HahaDogTables as T} from "./HahaDogTables.sol";

contract HahaDogRenderer {
    using Strings for uint256;

    struct Dog {
        bytes cells;
        uint8[4] picks;
        uint8 style;
        uint8 color;
        uint8 head;
        uint8 eyes;
        uint8 mouth;
        uint8 neck;
        uint256 score;
        uint8 tier;
    }

    error ZeroAddress();

    uint8 internal constant STATE_GENERATING = 0;
    uint8 internal constant STATE_READY = 1;

    uint8 internal constant STYLE_SCANLINES = 0;
    uint8 internal constant STYLE_SUNBURST = 1;
    uint8 internal constant STYLE_STARS = 2;
    uint8 internal constant STYLE_MOON = 3;
    uint8 internal constant STYLE_GLITCH = 4;
    uint8 internal constant STYLE_PLAIN = 5;

    uint256 internal constant INK = 0x17131c;
    uint256 internal constant WHITE = 0xfbf7ee;
    uint256 internal constant PINK = 0xf08da0;
    uint256 internal constant STAR = 0xfff8dc;
    uint256 internal constant TANGERINE = 2;

    string internal constant SVG_OPEN =
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" shape-rendering="crispEdges">';

    IHahaDogModel public immutable model;

    constructor(address model_) {
        if (model_ == address(0)) revert ZeroAddress();
        model = IHahaDogModel(model_);
    }

    function background(bytes32 seed) public pure returns (uint8 style, uint8 color) {
        uint256 r = uint256(keccak256(abi.encodePacked(seed)));
        uint256 roll = r % 100;
        if (roll < 30) style = STYLE_SCANLINES;
        else if (roll < 55) style = STYLE_SUNBURST;
        else if (roll < 75) style = STYLE_STARS;
        else if (roll < 90) style = STYLE_MOON;
        else style = STYLE_GLITCH;
        uint256 cr = r >> 128;
        if (style == STYLE_STARS || style == STYLE_MOON) {
            color = uint8(bytes3(0x010506)[cr % 3]);
        } else {
            color = uint8(cr % 8);
        }
    }

    function dog(bytes32 seed) public view returns (Dog memory d) {
        (d.cells, d.picks) = model.generate(seed);
        (d.style, d.color) = background(seed);
        (d.head, d.eyes, d.mouth, d.neck) = classify(d.cells);
        (d.score, d.tier) = rarity(d.head, d.eyes, d.mouth, d.neck, d.picks[0], d.style);
    }

    function classify(bytes memory cells)
        public
        pure
        returns (uint8 head, uint8 eyes, uint8 mouth, uint8 neck)
    {
        bytes memory g = new bytes(128);
        assembly ("memory-safe") {
            let src := add(cells, 32)
            let dst := add(g, 32)
            for { let i := 0 } lt(i, 128) { i := add(i, 1) } {
                let c := byte(0, mload(add(src, i)))
                if or(eq(c, 3), eq(c, 4)) { c := 2 }
                if eq(c, 6) { c := 5 }
                mstore8(add(dst, i), c)
            }
        }
        head = _nearest(g, T.HEAD_CELLS, T.HEAD_TABLE);
        eyes = _nearest(g, T.EYES_CELLS, T.EYES_TABLE);
        mouth = _nearest(g, T.MOUTH_CELLS, T.MOUTH_TABLE);
        neck = _nearest(g, T.NECK_CELLS, T.NECK_TABLE);
    }

    function rarity(uint8 head, uint8 eyes, uint8 mouth, uint8 neck, uint8 fur, uint8 style)
        public
        pure
        returns (uint256 score, uint8 tier)
    {
        score = uint8(T.PTS_HEAD[head]) + uint8(T.PTS_EYES[eyes]) + uint8(T.PTS_MOUTH[mouth])
            + uint8(T.PTS_NECK[neck]) + uint8(T.PTS_FUR[fur]) + uint8(T.PTS_STYLE[style]);
        if (score >= T.TIER_LEGENDARY) tier = 3;
        else if (score >= T.TIER_EPIC) tier = 2;
        else if (score >= T.TIER_RARE) tier = 1;
        if (fur == 6 && (head == 11 || head == 12)) {
            tier = 3;
        } else if ((eyes == 2 || eyes == 3) && style == STYLE_GLITCH && tier < 2) {
            tier = 2;
        }
    }

    function svgOf(bytes32 seed) external view returns (string memory) {
        Dog memory d = dog(seed);
        return _svg(d.cells, d.picks, d.style, d.color);
    }

    function svgWith(bytes32 seed, uint8 style, uint8 color) external view returns (string memory) {
        (bytes memory cells, uint8[4] memory picks) = model.generate(seed);
        return _svg(cells, picks, style, color);
    }

    function generatingSvg() public pure returns (string memory) {
        uint8[4] memory picks;
        return _svg(T.PLACEHOLDER, picks, STYLE_SCANLINES, uint8(TANGERINE));
    }

    function tokenURI(uint256 tokenId, bytes32 seed, uint256 rerolls, uint8 state)
        external
        view
        returns (string memory)
    {
        string memory image;
        string memory attrs;
        if (state != STATE_READY) {
            image = generatingSvg();
            attrs = string.concat(_attr("Status", "Generating"), ",", _num("Rerolls", rerolls));
        } else {
            Dog memory d = dog(seed);
            image = _svg(d.cells, d.picks, d.style, d.color);
            attrs = _attributes(d, rerolls);
        }
        string memory json = string.concat(
            '{"name":"Haha Dog #',
            tokenId.toString(),
            '","description":"',
            T.DESCRIPTION,
            '","image":"data:image/svg+xml;base64,',
            Base64.encode(bytes(image)),
            '","attributes":[',
            attrs,
            "]}"
        );
        return string.concat("data:application/json;base64,", Base64.encode(bytes(json)));
    }

    function _attributes(Dog memory d, uint256 rerolls) private pure returns (string memory) {
        string memory a = string.concat(
            _attr("Rarity", _name(T.N_TIER, d.tier)),
            ",",
            _num("Rarity Score", d.score),
            ",",
            _attr("Fur", _name(T.N_FUR, d.picks[0])),
            ",",
            _attr("Headwear", _name(T.N_HEAD, d.head)),
            ",",
            _attr("Eyes", _name(T.N_EYES, d.eyes)),
            ",",
            _attr("Mouth", _name(T.N_MOUTH, d.mouth)),
            ",",
            _attr("Neck", _name(T.N_NECK, d.neck)),
            ","
        );
        return string.concat(
            a,
            _attr("Cloth", _name(T.N_CLOTH, d.picks[1])),
            ",",
            _attr("Accessory", _name(T.N_ACC, d.picks[2])),
            ",",
            _attr("Glow", _name(T.N_GLOW, d.picks[3])),
            ",",
            _attr("Background", _name(T.N_STYLE, d.style)),
            ",",
            _attr("Background Color", _name(T.N_BG, d.color)),
            ",",
            _attr("Status", "Generated"),
            ",",
            _num("Rerolls", rerolls)
        );
    }

    function _attr(string memory k, string memory v) private pure returns (string memory) {
        return string.concat('{"trait_type":"', k, '","value":"', v, '"}');
    }

    function _num(string memory k, uint256 v) private pure returns (string memory) {
        return string.concat('{"trait_type":"', k, '","display_type":"number","value":', v.toString(), "}");
    }

    function _name(bytes memory packed, uint256 idx) private pure returns (string memory) {
        uint256 start;
        uint256 n;
        uint256 len = packed.length;
        for (uint256 i; i <= len; ++i) {
            if (i == len || packed[i] == "|") {
                if (n == idx) {
                    bytes memory out = new bytes(i - start);
                    for (uint256 j; j < out.length; ++j) {
                        out[j] = packed[start + j];
                    }
                    return string(out);
                }
                ++n;
                start = i + 1;
            }
        }
        return "";
    }

    function _nearest(bytes memory g, bytes memory cellIdx, bytes memory table) private pure returns (uint8 best) {
        assembly ("memory-safe") {
            let n := mload(cellIdx)
            let options := div(mload(table), n)
            let gp := add(g, 32)
            let cp := add(cellIdx, 32)
            let bestScore := 0
            for { let o := 0 } lt(o, options) { o := add(o, 1) } {
                let row := add(add(table, 32), mul(o, n))
                let sc := 0
                for { let i := 0 } lt(i, n) { i := add(i, 1) } {
                    let cell := byte(0, mload(add(cp, i)))
                    sc := add(sc, eq(byte(0, mload(add(gp, cell))), byte(0, mload(add(row, i)))))
                }
                if or(iszero(o), gt(sc, bestScore)) {
                    bestScore := sc
                    best := o
                }
            }
        }
    }

    function _rgb(bytes memory table, uint256 i) private pure returns (uint256) {
        return (uint256(uint8(table[3 * i])) << 16) | (uint256(uint8(table[3 * i + 1])) << 8)
            | uint256(uint8(table[3 * i + 2]));
    }

    function _tone(uint256 c, uint256 mulBy, uint256 add, uint256 div) private pure returns (uint256 out) {
        for (uint256 s; s < 24; s += 8) {
            out |= ((((c >> s) & 0xff) * mulBy + add) / div) << s;
        }
    }

    function _classColors(uint8[4] memory picks) private pure returns (uint256[11] memory col) {
        uint256 fur = _rgb(T.FUR, picks[0]);
        uint256 cloth = _rgb(T.CLOTH, picks[1]);
        col[1] = INK;
        col[2] = fur;
        col[3] = _tone(fur, 3, 0, 4);
        col[4] = _rgb(T.MARK, picks[0]);
        col[5] = cloth;
        col[6] = _tone(cloth, 3, 0, 4);
        col[7] = _rgb(T.ACC, picks[2]);
        col[8] = _rgb(T.GLOW, picks[3]);
        col[9] = WHITE;
        col[10] = PINK;
    }

    function _bit(uint256 w0, uint256 w1, uint256 w2, uint256 p) private pure returns (bool) {
        uint256 w = p < 256 ? w0 : (p < 512 ? w1 : w2);
        return (w >> (p & 255)) & 1 == 1;
    }

    function _bgPixel(uint8 style, uint256[4] memory tones, bytes memory bars, uint256 x, uint256 y) private pure returns (uint256) {
        uint256 p = y * 24 + x;
        if (style == STYLE_SCANLINES) return y & 1 == 1 ? tones[1] : tones[0];
        if (style == STYLE_SUNBURST) return _bit(T.SUN0, T.SUN1, T.SUN2, p) ? tones[2] : tones[0];
        if (style == STYLE_STARS) return _bit(T.STARS0, T.STARS1, T.STARS2, p) ? STAR : tones[3];
        if (style == STYLE_MOON) return _bit(T.MOON0, T.MOON1, T.MOON2, p) ? STAR : tones[3];
        if (style == STYLE_GLITCH) {
            for (uint256 i; i < bars.length; i += 4) {
                if (
                    uint8(bars[i]) == y && x >= uint8(bars[i + 1]) && x < uint8(bars[i + 2])
                ) return uint8(bars[i + 3]) == 0 ? 0xfff275 : 0xff3fa4;
            }
            return y & 1 == 1 ? tones[1] : tones[0];
        }
        return tones[0];
    }

    function _svg(bytes memory cells, uint8[4] memory picks, uint8 style, uint8 color)
        private
        pure
        returns (string memory)
    {
        uint256[11] memory col = _classColors(picks);
        uint256 base = _rgb(T.BG, color);
        uint256[4] memory tones =
            [base, _tone(base, 3, 0, 4), _tone(base, 3, 255, 4), _tone(base, 5, 0, 8)];
        bytes memory buf = new bytes(24 * 24 * 62);
        uint256 ptr;
        assembly ("memory-safe") {
            ptr := add(buf, 32)
        }
        uint256 start = ptr;
        uint256[24] memory row;
        bytes memory bars = T.GLITCH;
        for (uint256 y; y < 24; ++y) {
            for (uint256 x; x < 24; ++x) {
                row[x] = _bgPixel(style, tones, bars, x, y);
            }
            if (y >= 6) {
                uint256 r = y - 6 > 15 ? 15 : y - 6;
                for (uint256 c; c < 16; ++c) {
                    uint8 cls = uint8(cells[r * 8 + (c < 8 ? c : 15 - c)]);
                    if (cls != 0) row[4 + c] = col[cls];
                }
            }
            uint256 x0;
            while (x0 < 24) {
                uint256 x1 = x0 + 1;
                while (x1 < 24 && row[x1] == row[x0]) ++x1;
                ptr = _rect(ptr, x0, y, x1 - x0, row[x0]);
                x0 = x1;
            }
        }
        assembly ("memory-safe") {
            mstore(buf, sub(ptr, start))
        }
        return string.concat(SVG_OPEN, string(buf), "</svg>");
    }

    function _rect(uint256 ptr, uint256 x, uint256 y, uint256 w, uint256 rgb) private pure returns (uint256) {
        assembly ("memory-safe") {
            function dec(q, v) -> r {
                switch lt(v, 10)
                case 1 {
                    mstore8(q, add(48, v))
                    r := add(q, 1)
                }
                default {
                    mstore8(q, add(48, div(v, 10)))
                    mstore8(add(q, 1), add(48, mod(v, 10)))
                    r := add(q, 2)
                }
            }
            mstore(ptr, '<rect x="')
            ptr := dec(add(ptr, 9), x)
            mstore(ptr, '" y="')
            ptr := dec(add(ptr, 5), y)
            mstore(ptr, '" width="')
            ptr := dec(add(ptr, 9), w)
            mstore(ptr, '" height="1" fill="#')
            ptr := add(ptr, 20)
            for { let i := 0 } lt(i, 6) { i := add(i, 1) } {
                mstore8(add(ptr, i), byte(and(shr(sub(20, mul(i, 4)), rgb), 15), "0123456789abcdef"))
            }
            mstore(add(ptr, 6), '"/>')
            ptr := add(ptr, 9)
        }
        return ptr;
    }
}
