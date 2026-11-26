# 工具与共享模块（tools/）

## season1/

第一季的共享 Python 模块。`services/season1-admin/` 和 `services/sign-verify/` 都依赖它（`from tools.season1...`），运行服务前把仓库根目录加进 `PYTHONPATH`。

| 模块 | 作用 |
|---|---|
| `constants.py` | 合约地址、管理员地址等常量（公开信息） |
| `mainnet.py` | 主网参数（chainId、模块名） |
| `merkle.py` | Merkle 树与证明生成 |
| `hashutil.py` | keccak256 等哈希工具 |
| `eip712.py` | EIP-712 签名 |
| `signer_env.py` | 从 env 文件读密钥并核对地址 |
| `sign_gate.py` | 签名前的检查门控 |
| `checker.py` | 资格检查 |
| `ops.py` / `ops_book.py` | 运营操作与台账 |

密钥一律从 env 文件读（`signer_env.py`），不写进代码。
