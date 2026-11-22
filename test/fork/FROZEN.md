# 冻结的 fork 状态

状态：`test/fork/` 的数据来源说明。日期：2026-11-20。来源：`QUESTIONS.md` 第 11 条裁决。

## 为什么冻结

`SPEC 4` 要求在区块 `134683411` 核实 `.ai` 注册表。实测：

```
$ curl -s -X POST https://bsc-dataseed.bnbchain.org \
    -H 'Content-Type: application/json' \
    -d '{"jsonrpc":"2.0","id":1,"method":"eth_getCode","params":["0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F","0x806F103"]}'
{"jsonrpc":"2.0","error":{"code":-32000,"message":"missing trie node"}}
```

**公共 RPC 不提供那个区块的归档状态。** 因此按裁决分两层：

- **离线层**（`ForkOffline.t.sol`）：把 `.ai` 的字节码与必要 storage 冻结成本目录的文件，
  测试用 `vm.etch` / `vm.store` 还原。**不联网**，CI 必跑。
- **在线层**（`ForkOnline.t.sol`）：`--fork-url` 起真实 fork，对 `latest` 做同组断言。
  可选，非 fork 环境下自动跳过。

## 冻结了什么

| 文件 | 内容 |
| --- | --- |
| `AiRegistry.code.bin` | `.ai` 合约的 runtime bytecode（8756 字节） |
| `AiRegistry.code.hex` | 同上，十六进制（给人看的） |
| `AiRegistry.storage.txt` | 关键 storage，每行 `slot value` |
| `Meta.json` | 区块号、字节码哈希、抓取时间、冻结原因 |

## 不变式：字节码必须与 SPEC 4 一致

```
code size : 8756
code hash : 0xc4006e6e6ffaaf6996116617392beabe4f5f0a0795841322f91c2ceac34d6ace
```

`ForkOfflineTest.test_fork_aiCodeHash` 与 `ForkOnlineTest.test_online_aiCodeHash` 都把这个哈希**写死断言**。

**如果有一天这个哈希变了**：按 `SPEC 12` 的原文要求，停下来更新规格，不要改断言蒙混。
`.ai` 目前不可升级（EIP-1967 槽为 0、dispatcher 里没有 `upgradeTo`），所以理论上不会变；
但它的 `owner` 可以 `adminRegister` 新名字，也能改动 signer/URI/长度，这些**不改变字节码**。

## storage 槽位布局（实测）

| 槽 | 类型 | 说明 |
| --- | --- | --- |
| `0x0` | `string name` | 短字符串内联，`SPACE ID Agent ID` |
| `0x1` | `string symbol` | 短字符串内联，`AI` |
| `0x2` | `mapping(uint256 => address)` | tokenId → owner |
| `0x3` | `mapping(address => uint256)` | 实测值为 1，`balanceOf` 从这里读 |
| `0x8` | `address` | `owner()` |
| `0x9` | `address` | `pendingOwner()` |
| `0xb` | packed | 长度上下限等 |
| `0xc` / `0xd` | `string` | `baseURI` / `uriSuffix` |
| `keccak256(addr, 10)` | `mapping(address => string)` | handle（短字符串内联） |

短字符串编码：内容从左填充，**最低字节 = `len * 2`**。例如 `"AI"` → `0x4149` 加 `04`。
注意 `"0x1"` 这类**奇数个**十六进制半字节要从低位对齐（`1` 不是 `0x10`），
`ForkOffline.t.sol` 的 `_hexRange` 专门处理了这个分支。

## 冻结的地址

| 名字 | 地址 | 用途 |
| --- | --- | --- |
| `alice` 的持有者 | `0xA506ac7069937571DC56C5f8FDa53c4A729456c6` | fork 测试的「有 `.ai` 的用户」 |
| `binance` 的持有者 | `0x5E3fBbc8D260a63C9fe19CbBb0A9d5792C3375eA` | 同上，用于保留名的场景 |

## 怎么重新冻结

```bash
export BSC_RPC_URL=https://bsc-dataseed.bnbchain.org
python tools/freeze_fork_state.py
```

脚本会先断言字节码与 `SPEC 4` 一致，再写文件。不一致就直接中止，不会写出一份「错的期望值」。

## 冻结的边界与风险

**冻结的是「某一时刻的状态」，不是「主网的全部行为」。**

- ✅ 覆盖：字节码、`handleOf`、`ownerOfHandle`、`ownerOf`、`balanceOf`、`name`、`symbol`、
  以及「不归一化」的行为。
- ⚠️ 未覆盖：`.ai` 合约里其他未冻结的 `adminRegister` 注册的名字。
  如果某个测试需要别的 `.ai` 持有者，请用 `MockAiRegistry` 而不是往冻结文件里加槽位
  ——后者会让「离线 = 主网」这个前提越来越弱。
- ⚠️ `transferFrom` 的 Soulbound 选择器：离线层只断言「调用失败」，
  精确选择器 `0xa4420a95` 由 `ForkOnlineTest` 验证（需要真实字节码执行）。
