#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 assets/svg/*.svgpart 转成 Solidity 字符串常量，生成 src/libraries/HahaSvg.sol。

契约（见 docs/contracts/SVG.md）：
- 四个片段没有末尾换行，拷进 Solidity 时不要再加 \\n。
- 文件是 UTF-8。金币上的 Ð 是 U+00D0，UTF-8 为 C3 90，不是 ASCII D。
- 拼接顺序：prefix + decimal(y) + mid + decimal(fsz) + nameOpen + label + "." + tld + suffix
- label 只含 a-z0-9，不需要 XML 转义。不要做 HTML escape，否则样例对不上。

本脚本只在开发时运行一次，产物 HahaSvg.sol 进仓库。CI 用 test/SvgLiteral.t.sol
重新拼装三张样例并与 assets/svg/samples/ 逐字节比对，因此万一有人手改了
HahaSvg.sol，测试会失败。
"""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SVG_DIR = ROOT / "assets" / "svg"
OUT = ROOT / "src" / "libraries" / "HahaSvg.sol"

# SVG.md 第 24 行的期望值，作为生成前的前置断言。
EXPECTED = {
    "prefix": (5332, "6bfd60bb48abab846f752cddbbb4f1d786b9436eec2d5d099bbdc14d4eee5033"),
    "mid": (54, "d3639713fe82b6cfdf16b8f91b8b82085cbcebe76348164d051963d6ceb460ba"),
    "name-open": (33, "8f725fb3c6dda08a3808a210e4b76cc829cd42039a2d8ef4d7571b85fdd97087"),
    "suffix": (156, "9e939574a89163960d6f2d47ed7a8eaea226f52e24c429d837d5f7f4277a1ec2"),
}


def solidity_string(raw: bytes) -> str:
    """把 UTF-8 字节转成 Solidity 字面量。

    规则：
    - 用单引号包裹，内容里的双引号就不用转义（SVG 片段里全是双引号）。
    - 反斜杠转义成 \\\\，单引号转义成 \\'。
    - 非 ASCII 字节逐个写成 \\xNN，保证源码是纯 ASCII，任何编译器和编辑器都不会改字节。
      Ð(U+00D0) 会变成 \\xc3\\x90，这与 SVG.md 要求的 C3 90 完全对应。
    """
    out = ["'"]
    for b in raw:
        if b == 0x5C:            # backslash
            out.append("\\\\")
        elif b == 0x27:          # single quote
            out.append("\\'")
        elif b == 0x0A:
            raise SystemExit("片段里不该有换行，SVG.md 说没有末尾换行")
        elif 0x20 <= b <= 0x7E:
            out.append(chr(b))
        else:
            out.append("\\x%02x" % b)
    out.append("'")
    return "".join(out)


def main() -> int:
    parts = {}
    for name, (want_len, want_sha) in EXPECTED.items():
        raw = (SVG_DIR / f"{name}.svgpart").read_bytes()
        got_sha = hashlib.sha256(raw).hexdigest()
        if len(raw) != want_len or got_sha != want_sha:
            print(f"FAIL {name}.svgpart 长度或哈希与 SVG.md 不符", file=sys.stderr)
            print(f"  got  {len(raw)} {got_sha}", file=sys.stderr)
            print(f"  want {want_len} {want_sha}", file=sys.stderr)
            return 1
        parts[name] = raw
        print(f"OK   {name}.svgpart {want_len} bytes")

    def const(name: str, key: str) -> str:
        return f"    string internal constant {name} = {solidity_string(parts[key])};"

    body = f'''// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

/// @title HahaSvg
/// @notice 已批准的链上 SVG 常量，由 `assets/svg/*.svgpart` 逐字节转换而来。
///
/// @dev 本文件由 `tools/gen_svg_literals.py` 生成，**不要手改**。
///      改图先改 `assets/svg/` 里的片段与 `svg-generator.py`，再重新生成。
///
///      四个片段没有末尾换行，所以常量里也没有 `\\n`。
///      非 ASCII 字节写成 `\\xNN`，保证源码是纯 ASCII；金币上的 `Ð` 因此是 `\\xc3\\x90`
///      （U+00D0 的 UTF-8 编码），不是 ASCII 的 `D`。
///
///      拼接规则（见 docs/contracts/SVG.md）：
///      {{prefix}} {{decimal(y)}} {{mid}} {{decimal(fsz)}} {{nameOpen}} {{label}} "." {{tld}} {{suffix}}
///      中间不补零、不加空格。label 只含 `a-z0-9`，不做 XML 转义。
library HahaSvg {{
    /// @dev `prefix.svgpart`，5332 字节，SHA-256 `6bfd60bb48abab846f752cddbbb4f1d786b9436eec2d5d099bbdc14d4eee5033`。
    ///      从 `<svg` 开始，到名字 `<text>` 的 `y="` 为止。
{const("PREFIX", "prefix")}

    /// @dev `mid.svgpart`，54 字节，SHA-256 `d3639713fe82b6cfdf16b8f91b8b82085cbcebe76348164d051963d6ceb460ba`。
    ///      `y` 与 `font-size` 之间的静态片段，以 `"` 开头、以 `font-size="` 结尾。
{const("MID", "mid")}

    /// @dev `name-open.svgpart`，33 字节，SHA-256 `8f725fb3c6dda08a3808a210e4b76cc829cd42039a2d8ef4d7571b85fdd97087`。
    ///      字号与名字文本之间，以 `"` 开头、以 `">` 结尾。
{const("NAME_OPEN", "name-open")}

    /// @dev `suffix.svgpart`，156 字节，SHA-256 `9e939574a89163960d6f2d47ed7a8eaea226f52e24c429d837d5f7f4277a1ec2`。
    ///      从名字的 `</text>` 到 `</svg>`。
{const("SUFFIX", "suffix")}
}}
'''
    OUT.write_text(body, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(body)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
