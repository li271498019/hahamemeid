# haha-agent-chat（已停用）

站内 agent 对话的后端（Node.js + PostgreSQL）。2026-11-27 起站内 agent 页改为读本地答案库（`website/` 里的答案库，见 PR “伪 agent 上线”），本服务在服务器上已停用（`haha-agent-chat.service` 未运行），代码原样公开备查。
配置变量见 `ops/server/env/agent-chat.env.example`。`test-e2e.sh` 里的服务器地址已替换为 `<SERVER_IP>`。
