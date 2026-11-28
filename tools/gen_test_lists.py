#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 docs/contracts/*.hashes.txt 生成 test/TestLists.sol，供测试直接引用真实名单。

为什么要生成而不是在测试里硬写：测试必须验证的正是「链上部署用的名单」，
所以数据源必须是仓库里的 .hashes.txt，而不是另抄一份。生成脚本会逐行校验
哈希格式与字母序，任何不一致直接中止。

产物：test/TestLists.sol，内含两个常量数组。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "test" / "TestLists.sol"

SRC = {
    "BANNED": (ROOT / "docs/contracts/blacklist-v2.hashes.txt", 208,
               "keccak256(abi.encodePacked(\"HAHA_V2\", label))",
               "0xb9bda22217d260c2032c02472ab75de873d668a59e15358431284b2e99ff41e1"),
    "RESERVED": (ROOT / "docs/contracts/reserved-names.hashes.txt", 61,
                 "keccak256(bytes(label))", None),
}


def load(path: Path, want_count: int):
    rows = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        parts = raw.split()
        if len(parts) != 2:
            raise SystemExit(f"{path.name}: 行格式不对: {raw!r}")
        word, h = parts
        if not re.fullmatch(r"0x[0-9a-f]{64}", h):
            raise SystemExit(f"{path.name}: 哈希格式不对: {word} {h}")
        rows.append((word, h))
    if len(rows) != want_count:
        raise SystemExit(f"{path.name}: 期望 {want_count} 行，实际 {len(rows)}")
    words = [w for w, _ in rows]
    if words != sorted(words):
        raise SystemExit(f"{path.name}: 不是字母序")
    if len(set(words)) != len(words):
        raise SystemExit(f"{path.name}: 有重复")
    return rows


def emit_const(name: str, rows, comment: str) -> str:
    lines = [f"    /// @dev {comment}"]
    lines.append(f"    function {name}() internal pure returns (bytes32[] memory out) {{")
    lines.append(f"        out = new bytes32[]({len(rows)});")
    for i, (word, h) in enumerate(rows):
        lines.append(f"        out[{i}] = {h}; // {word}")
    lines.append("    }")
    return "\n".join(lines)


def main() -> int:
    banned_rows = load(*SRC["BANNED"][:2])
    reserved_rows = load(*SRC["RESERVED"][:2])

    body = f'''// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

/// @title TestLists
/// @notice 真实名单的哈希数组，由 `tools/gen_test_lists.py` 从 `docs/contracts/*.hashes.txt` 生成。
///
/// @dev **不要手改本文件。** 改名单请先改 `blacklist-v2.md` / `reserved-names.md`，
///      再重新生成 `.hashes.txt`，最后重新运行生成脚本。
///      测试用这份数据验证链上部署时写入的名单，因此数据源必须与部署源一致。
library TestLists {{
    /// @notice 黑名单数量。
    uint256 internal constant BANNED_COUNT = {len(banned_rows)};

    /// @notice 保留名数量。
    uint256 internal constant RESERVED_COUNT = {len(reserved_rows)};

{emit_const("bannedHashes", banned_rows, "208 个 keccak256(abi.encodePacked(HAHA_V2, label)) 加盐哈希，按字母序。")}

{emit_const("reservedHashes", reserved_rows, "61 个 keccak256(bytes(label))，按字母序。")}
}}
'''

    OUT.write_text(body, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(banned_rows)} banned, {len(reserved_rows)} reserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
