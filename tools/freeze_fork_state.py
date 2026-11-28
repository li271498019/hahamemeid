#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
冻结 BSC 主网上 `.ai` 注册表的字节码与关键 storage，供离线 fork 测试使用。

为什么需要冻结（QUESTIONS 第 11 条的裁决）：
    规格 `SPEC 4` 要求在区块 134683411 核实 `.ai`。实测该区块在公共 RPC 上
    取 code/storage 返回 `missing trie node`（非归档节点）。因此：
    - 离线层：把 `.ai` 的 runtime code 与必要 storage 冻结成文件，
      测试用 `vm.etch` / `vm.store` 还原，**不需要联网**，CI 可跑。
    - 在线层：可选地用 `--fork-url` 对真实 RPC 做交叉验证。

冻结内容：
    AiRegistry.code.hex      .ai 合约 runtime bytecode
    AiRegistry.storage.json  {slot: value} 关键槽位
    Meta.json                区块号、字节码哈希、抓取时间、各项断言

关键槽位（实测布局，2026-11-20）：
    slot 0   name 的短字符串存储
    slot 1   symbol 的短字符串存储
    slot 2   mapping(uint256 tokenId => address owner)
    slot 3   mapping(address => uint256)（实测值为 1，疑为「是否已注册」或类似标记）
    slot 10  mapping(address owner => string handle)（短字符串内联存储：`alice` + len 10）
    slot 8   owner()
    slot 9   pendingOwner()
    slot 11  打包的 minLen/maxLen/LEN_CEILING 等
    slot 12  baseURI 长度
    slot 13  uriSuffix 短字符串

用法：
    BSC_RPC_URL=https://bsc-dataseed.bnbchain.org python tools/freeze_fork_state.py
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "test" / "fork" / "state"
sys.path.insert(0, str(ROOT / "tools"))
from keccak import keccak256  # noqa: E402

RPC = os.environ.get("BSC_RPC_URL", "https://bsc-dataseed.bnbchain.org")
AI = "0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F"

# SPEC 4 记录的期望值。抓到的值必须与之一致，否则停下来报告，不要改断言。
EXPECTED_CODE_SIZE = 8756
EXPECTED_CODE_HASH = "0xc4006e6e6ffaaf6996116617392beabe4f5f0a0795841322f91c2ceac34d6ace"

# 需要冻结的地址（测试要用到它们的 `.ai`）
WATCHED = {
    "alice_owner": "0xA506ac7069937571DC56C5f8FDa53c4A729456c6",
    "binance_owner": "0x5E3fBbc8D260a63C9fe19CbBb0A9d5792C3375eA",
}

_rid = [0]


def rpc(method, params):
    _rid[0] += 1
    body = json.dumps({"jsonrpc": "2.0", "id": _rid[0], "method": method, "params": params})
    out = subprocess.run(
        ["curl", "-s", "-X", "POST", RPC, "-H", "Content-Type: application/json", "-d", body],
        capture_output=True,
        text=True,
    ).stdout
    return json.loads(out)


def map_slot_addr(key_hex, slot):
    """mapping(address => X) 的槽位：keccak256(abi.encode(address, slot))。"""
    k = bytes.fromhex(key_hex.replace("0x", "").rjust(64, "0"))
    return "0x" + keccak256(k + slot.to_bytes(32, "big")).hex()


def map_slot_uint(key_hex, slot):
    """mapping(uint256 => X) 的槽位：keccak256(abi.encode(uint256, slot))。"""
    k = bytes.fromhex(key_hex.replace("0x", "").rjust(64, "0"))
    return "0x" + keccak256(k + slot.to_bytes(32, "big")).hex()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    bn = int(rpc("eth_blockNumber", [])["result"], 16)
    code = rpc("eth_getCode", [AI, "latest"])["result"]
    raw = bytes.fromhex(code[2:])
    code_hash = "0x" + keccak256(raw).hex()

    print(f"block      : {bn}")
    print(f"code size  : {len(raw)}")
    print(f"code hash  : {code_hash}")

    if len(raw) != EXPECTED_CODE_SIZE or code_hash != EXPECTED_CODE_HASH:
        print("FAIL: .ai 运行时字节码与 SPEC 4 不一致。")
        print("      按 SPEC 12 的要求，停下来更新规格，不要改断言蒙混。")
        return 1
    print("OK   : 字节码与 SPEC 4 一致")

    # 关键槽位
    slots = {}
    # 结构体/字符串等固定槽
    for s in [0, 1, 8, 9, 11, 12, 13]:
        v = rpc("eth_getStorageAt", [AI, hex(s), "latest"])["result"]
        if v and v != "0x" + "00" * 32:
            slots[hex(s)] = v

    # mapping(uint256 => owner) 在 slot 2
    token_ids = {
        "alice": "0x" + keccak256(b"alice").hex(),
        "binance": "0x" + keccak256(b"binance").hex(),
    }
    for name, tid in token_ids.items():
        ks = map_slot_uint(tid, 2)
        v = rpc("eth_getStorageAt", [AI, ks, "latest"])["result"]
        if v and v != "0x" + "00" * 32:
            slots[ks] = v
            print(f"       slot2[{name}] = {v}")

    # mapping(address => handle) 在 slot 10（实测）；slot 3 是另一个 mapping，值为 1。
    for name, addr in WATCHED.items():
        ks = map_slot_addr(addr, 10)
        v = rpc("eth_getStorageAt", [AI, ks, "latest"])["result"]
        if v and v != "0x" + "00" * 32:
            slots[ks] = v
            print(f"       slot10[{name}] = {v}")

    (OUT / "AiRegistry.code.hex").write_text(code + "\n", encoding="utf-8")
    (OUT / "AiRegistry.storage.json").write_text(
        json.dumps(slots, indent=2) + "\n", encoding="utf-8"
    )
    (OUT / "Meta.json").write_text(
        json.dumps(
            {
                "chainId": 56,
                "address": AI,
                "frozenAtBlock": bn,
                "frozenAt": datetime.now(timezone.utc).isoformat(),
                "rpc": RPC,
                "codeSize": len(raw),
                "codeHash": code_hash,
                "note": (
                    "区块 134683411 在公共 RPC 上返回 missing trie node，"
                    "因此从 latest 冻结。`.ai` 不可升级，字节码哈希与 SPEC 4 一致。"
                ),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
