#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
独立复核仓库里所有可校验的哈希与字节级事实。

这个脚本**不依赖 forge**，只用纯 Python keccak，因此可以作为「第二条独立路径」
印证 Solidity 与测试里的断言。

复核项：
1. 黑名单 208 个词：md 与 .hashes.txt 词集一致，逐条加盐哈希匹配，聚合哈希匹配
2. 保留名 61 个：md 与 .hashes.txt 一致，逐条 labelhash 匹配
3. 两份名单无交集
4. namehash 测试向量（hahaNode / memeNode / abc.haha / abc.meme / keccak("abc")）
5. `alice` 的 tokenId 十进制
6. 四个 svgpart 的字节数与 SHA-256
7. 三张样例 SVG 由四段常量拼装后逐字节一致
8. 字号/基线表（含 n=24 的半偶数关键点）

用法：
    python tools/check_hashes.py
退出码 0 表示全部通过。
"""
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from keccak import keccak256  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs" / "contracts"
SVG = ROOT / "assets" / "svg"

BT = chr(96)  # 反引号
TICK_RE = "[" + BT + "]([^" + BT + "]+)[" + BT + "]"

FAILS = []


def check(name, got, want):
    ok = str(got).lower() == str(want).lower()
    print(("  OK   " if ok else "  FAIL ") + name + ("" if ok else f"\n         got  {got}\n         want {want}"))
    if not ok:
        FAILS.append(name)


def h(b: bytes) -> str:
    return "0x" + keccak256(b).hex()


def load_hashes(path: Path, want: int):
    rows = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        parts = raw.split()
        if len(parts) != 2:
            raise SystemExit(f"{path.name}: 行格式不对: {raw!r}")
        word, hh = parts
        if not re.fullmatch(r"0x[0-9a-f]{64}", hh):
            raise SystemExit(f"{path.name}: 哈希格式不对: {word} {hh}")
        rows.append((word, hh))
    if len(rows) != want:
        raise SystemExit(f"{path.name}: 期望 {want} 行，实际 {len(rows)}")
    words = [w for w, _ in rows]
    if words != sorted(words):
        raise SystemExit(f"{path.name}: 不是字母序")
    if len(set(words)) != len(words):
        raise SystemExit(f"{path.name}: 有重复词")
    return rows


def section_words(md: str, section_marker: str, stop_marker: str) -> list:
    """从 md 的某个小节里抓所有反引号词，按 `###` 分段累加。"""
    body = md.split(section_marker)[1]
    if stop_marker:
        body = body.split(stop_marker)[0]
    words = []
    in_block = False
    for line in body.splitlines():
        if line.startswith("### "):
            in_block = True
            continue
        if line.startswith("#") and in_block:
            in_block = False
        if in_block:
            words += re.findall(TICK_RE, line)
    return words


def main() -> int:
    # ---- 自检 ----
    check('keccak256("") 自检', h(b""), "0xc5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470")

    # ================= 1. 黑名单 =================
    print("\n[黑名单]")
    bl_md = (DOCS / "blacklist-v2.md").read_text(encoding="utf-8")
    bl_rows = load_hashes(DOCS / "blacklist-v2.hashes.txt", 208)
    bl_words = section_words(bl_md, "## 分类", None)

    check("md 解析出 208 个词", len(bl_words), 208)
    check("md 无重复", len(set(bl_words)), len(bl_words))
    check("md 词集 == hashes.txt 词集", sorted(bl_words), sorted(w for w, _ in bl_rows))

    bad = [w for w, hh in bl_rows if h(b"HAHA_V2" + w.encode()).lower() != hh.lower()]
    check("208 条加盐哈希逐条匹配", len(bad), 0)
    if bad:
        print(f"         不匹配: {bad[:5]}")

    concat = b"".join(bytes.fromhex(hh[2:]) for _, hh in bl_rows)
    check(
        "208 个哈希聚合 keccak",
        h(concat),
        "0xb9bda22217d260c2032c02472ab75de873d668a59e15358431284b2e99ff41e1",
    )
    check(
        "trump 单条向量",
        h(b"HAHA_V2trump"),
        "0x2fb81193c412e0605114fa0de2c7586df93ccb4eca5678d1781f0dd83394cb41",
    )
    check("btc 不在黑名单", "btc" in set(bl_words), False)
    check("hashes.txt 按字母序", [w for w, _ in bl_rows] == sorted(w for w, _ in bl_rows), True)

    # ================= 2. 保留名 =================
    print("\n[保留名]")
    res_md = (DOCS / "reserved-names.md").read_text(encoding="utf-8")
    res_rows = load_hashes(DOCS / "reserved-names.hashes.txt", 61)
    res_words = section_words(res_md, "## 名单", "## labelhash")

    check("md 解析出 61 个词", len(res_words), 61)
    check("md 无重复", len(set(res_words)), len(res_words))
    check("md 词集 == hashes.txt 词集", sorted(res_words), sorted(w for w, _ in res_rows))

    bad = [w for w, hh in res_rows if h(w.encode()).lower() != hh.lower()]
    check("61 条 labelhash 逐条匹配", len(bad), 0)
    if bad:
        print(f"         不匹配: {bad[:5]}")

    check("长度 ≤ 2 的只有 cz", [w for w in res_words if len(w) <= 2], ["cz"])

    # md 里的 labelhash 表格
    table = res_md.split("## labelhash")[1]
    table_rows = re.findall(r"\| (\w+) \| `(0x[0-9a-f]{64})` \|", table)
    check("labelhash 表格 61 行", len(table_rows), 61)
    table_bad = [w for w, hh in table_rows if h(w.encode()).lower() != hh.lower()]
    check("labelhash 表格逐条匹配", len(table_bad), 0)

    # ================= 3. 无交集 =================
    print("\n[两份名单]")
    check("黑名单与保留名无交集", sorted(set(bl_words) & set(res_words)), [])

    # ================= 4. namehash 向量 =================
    print("\n[namehash]")

    def namehash(labels):
        node = b"\x00" * 32
        for lb in reversed(labels):
            node = keccak256(node + keccak256(lb.encode()))
        return "0x" + node.hex()

    check(
        "hahaNode",
        namehash(["haha"]),
        "0xaa5a3a58f7c8841455eecaa0c6a6a0b40ace5681fbb31361a0d45b168179128f",
    )
    check(
        "memeNode",
        namehash(["meme"]),
        "0x74df4ab2564a9f9bb6d4b6b77bf4fc02ac80f07bd9e1776d3967578b3fc36be4",
    )
    check("keccak256(abc)", h(b"abc"), "0x4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45")
    check(
        "node(abc.haha)",
        namehash(["abc", "haha"]),
        "0xc57a55f292f4033cc1612bb06ae0f4e6bf0fc0c57815982253ae7fdd925b7052",
    )
    check(
        "node(abc.meme)",
        namehash(["abc", "meme"]),
        "0x7d6c57ebcb95fc73d48b8e90c54fb409bd65ff84d24423b6a5b13bc744c17d0a",
    )
    check(
        "node(abc.haha) != node(abc.meme)",
        namehash(["abc", "haha"]) != namehash(["abc", "meme"]),
        True,
    )

    # ================= 5. alice tokenId =================
    print("\n[.ai tokenId]")
    check(
        "tokenId(alice) = uint256(keccak256(alice))",
        int(h(b"alice"), 16),
        70564938991660933374592024341600875602376452319261984317470407481576058979585,
    )

    # ================= 6. svgpart 字节与哈希 =================
    print("\n[SVG 片段]")
    EXPECTED = {
        "prefix": (5332, "6bfd60bb48abab846f752cddbbb4f1d786b9436eec2d5d099bbdc14d4eee5033"),
        "mid": (54, "d3639713fe82b6cfdf16b8f91b8b82085cbcebe76348164d051963d6ceb460ba"),
        "name-open": (33, "8f725fb3c6dda08a3808a210e4b76cc829cd42039a2d8ef4d7571b85fdd97087"),
        "suffix": (156, "9e939574a89163960d6f2d47ed7a8eaea226f52e24c429d837d5f7f4277a1ec2"),
    }
    parts = {}
    for name, (want_len, want_sha) in EXPECTED.items():
        raw = (SVG / f"{name}.svgpart").read_bytes()
        parts[name] = raw
        check(f"{name}.svgpart 字节数", len(raw), want_len)
        check(f"{name}.svgpart SHA-256", hashlib.sha256(raw).hexdigest(), want_sha)
        check(f"{name}.svgpart 无末尾换行", raw[-1:] != b"\n", True)

    # ================= 7. 样例字节一致 =================
    print("\n[样例拼装]")

    def geo(label, tld):
        n = len(label) + len(tld) + 1
        fsz = 42000 // (58 * n)
        fsz = min(fsz, 96)
        num = fsz * 35
        q, r = divmod(num, 100)
        # 半偶数舍入
        if r > 50 or (r == 50 and q % 2 == 1):
            q += 1
        return fsz, 250 + q

    def build(label, tld):
        fsz, y = geo(label, tld)
        return (
            parts["prefix"]
            + str(y).encode()
            + parts["mid"]
            + str(fsz).encode()
            + parts["name-open"]
            + label.encode()
            + b"."
            + tld.encode()
            + parts["suffix"]
        )

    for label, tld in [("a", "haha"), ("myagent", "meme"), ("superlongagentname2026", "haha")]:
        want = (SVG / "samples" / f"{label}.{tld}.svg").read_bytes()
        got = build(label, tld)
        check(f"{label}.{tld} 拼装逐字节一致", hashlib.sha256(got).hexdigest(), hashlib.sha256(want).hexdigest())

    # ================= 8. 字号表 =================
    print("\n[字号与基线]")
    table = [
        ("a", "haha", 96, 284),
        ("abc", "haha", 90, 282),
        ("myagent", "meme", 60, 271),
        ("abcdefghijklmnopqrs", "haha", 30, 260),
        ("superlongagentname2026", "haha", 26, 259),
    ]
    for label, tld, efsz, ey in table:
        fsz, y = geo(label, tld)
        check(f"{label}.{tld}", f"{fsz}/{y}", f"{efsz}/{ey}")

    # n=24 的半偶数关键点
    check("n=24 时 y 是 260 而不是 261", geo("abcdefghijklmnopqrs", "haha")[1], 260)

    # ================= 结论 =================
    print("\n" + "=" * 50)
    if FAILS:
        print(f"{len(FAILS)} 项失败:")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
