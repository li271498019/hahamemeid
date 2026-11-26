# 服务（services）

haha.meme 的后端服务。全部只读或管理员操作，**密钥一律从环境变量读，不写进代码、不进仓库**。

## 目录

| 目录 | 作用 |
|---|---|
| `validator/` | G13 验证服务：监听链上验证请求，管理员签发验证结果（0–100 分） |
| `sign-verify/` | 第一季每日验证签名服务：签发 VerifyAuth（EIP-712），每天 30 分 |
| `season1-admin/` | 第一季管理员自动化：每天 08:00 发任务包、发根、发放上一天的兑换 |

## 密钥怎么放

| 服务 | 环境变量 | 说明 |
|---|---|---|
| validator | `ADMIN_PRIVATE_KEY` | 管理员私钥（只在服务器 `/etc/haha/admin-signer.env`，0600） |
| sign-verify | `SEASON1_SIGNER_KEY` | 每日验证签名私钥（只在服务器 `/etc/haha/season1-signer.env`，0600） |
| season1-admin | `ADMIN_PRIVATE_KEY` | 同 validator |

**不要把这些变量的值写进任何文件、不要提交到 GitHub。**本地测试用 `.env`（已在 `.gitignore`），生产用 systemd 的 `EnvironmentFile`。

## 运行

各目录里有对应的 systemd 单元文件（`.service` / `.timer`），按里面的说明部署。
