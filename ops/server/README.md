# 生产服务器配置（原样公开，已脱敏）

这里是 haha.meme 生产服务器（Ubuntu 24.04，单机）上与本项目有关的全部配置的原样副本，取自 2026-11-28 线上状态。
密钥、密码、Ankr key、服务器 IP 都不在这里：凡是需要的地方都用 `<...>` 占位，或给了 `.example` 文件。

## 目录

| 目录 | 线上位置 | 说明 |
| --- | --- | --- |
| `systemd/` | `/etc/systemd/system/haha-*.service|timer` | 全部自定义服务的线上原件 |
| `nginx/nginx.conf` | `/etc/nginx/nginx.conf` | 主配置 |
| `nginx/sites-available/haha.meme` | 同名 | 站点配置（静态站、`/api/`、`/mcp`、`/rpc/` 三级回退、签名校验、验证结果目录） |
| `nginx/conf.d/` | `/etc/nginx/conf.d/` | `/rpc/` 上游与分流、Cloudflare 真实 IP、限流 |
| `nginx/snippets/` | `/etc/nginx/snippets/` | `/rpc/` 公共参数、安全响应头 |
| `nginx/haha-rpc-secrets.conf.example` | `/etc/nginx/haha-rpc-secrets.conf`（root 0600） | 只含两个 Ankr key 的占位符；真文件只在服务器上 |
| `env/*.env.example` | `/etc/haha/*.env`（root 0600） | 只有变量名和占位值 |
| `../tools/` | `/root/` | `ankr_probe.py`（Ankr 节点探测）、`nginx_patch.py` / `nginx_manifest.py`（改 nginx 用的小工具） |
| `../records/` | `/opt/haha-season1/day-*`、`/opt/haha-validation/*.json`、`/opt/haha-mcp/data/` | 运行记录：第一季每日快照清单、每日运营报告、任务包、验证者状态、MCP 每日统计（客户端 IP 已删，只留个数） |

## 服务一览

| 服务 | 代码（本仓库） | 线上目录 | 运行用户 | 状态 |
| --- | --- | --- | --- | --- |
| haha-indexer（同步链上事件） | `indexer/syncer.py` | `/opt/haha-indexer` | haha | 运行中 |
| haha-api（`/api/` 只读接口） | `indexer/api.py` | `/opt/haha-indexer` | haha | 运行中 |
| haha-mcp（`/mcp`） | `MCP/` | `/opt/haha-mcp`（`dist/` 由 `npm run build` 生成） | haha | 运行中 |
| haha-sign-verify（第一季签名校验） | `tools/season1/signing/` | `/opt/haha-season1/signing` | root | 运行中 |
| haha-validator（G13 验证者） | `tools/validator-service.py` | `/opt/haha-validation` | root | 运行中 |
| haha-dog-keeper（Haha Dog 快照） | `haha-dog/keeper/keeper.py` | `/opt/haha-dog-keeper` | hahadog-keeper | 运行中（2026-11-28 起） |
| haha-agent-chat（站内 agent 对话后端） | `services/agent-chat/` | `/opt/haha-agent-chat` | haha | 已停用（站内已改用本地答案库） |
| haha-daily-ops（第一季每日 08:00 运营） | `tools/season1/admin/daily_ops.py` | `/opt/haha-season1/admin` | root | 见下 |

**每日 08:00（UTC+8）运营的实际触发方式：** systemd 的 `haha-daily-ops.timer` 目前是 *disabled*；每天的运营由运维从外部用 SSH 登录后执行 `daily_ops.py`（与 `haha-daily-ops.service` 的 ExecStart 相同）。服务器上没有 root/haha 的 crontab，`/etc/cron.d` 里只有系统自带的 certbot / e2scrub / sysstat。

## 数据库

PostgreSQL 16，库名 `haha_indexer`。表结构见 `indexer/schema.sql` 与 `indexer/migrations/`（按编号顺序执行）。不公开数据库导出：链上数据都可以用索引器从链上重放得到。

## 网站发布流程

1. 构建产物打成 tgz，解到 `/var/www/releases/<时间>-<名字>/`，写入 `.release`（提交 SHA）。
2. 留空 `agent-images/`，`chown -R www-data`。
3. 原子替换软链 `/var/www/haha.meme -> /var/www/releases/<新目录>`。
4. `nginx -t && systemctl reload nginx`，冒烟测试；出问题时把软链指回上一版即可回滚。

## 密钥在哪（只写位置，不写值）

| 用途 | 文件 |
| --- | --- |
| 部署者 / 管理员私钥（每日运营、验证者、keeper 付 gas） | `/etc/haha/admin-signer.env` |
| 第一季 EIP-712 签名私钥 | `/etc/haha/season1-signer.env` |
| 数据库密码、RPC（含 Ankr key） | `/etc/haha/indexer.env` |
| 两个 Ankr key（nginx `/rpc/`） | `/etc/nginx/haha-rpc-secrets.conf` |
| agent-chat 通道 key、数据库密码 | `/etc/haha/agent-chat.env` |
| TLS 证书 | `/etc/letsencrypt/`（certbot 管理） |
