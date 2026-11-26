# 部署脚本（deploy）

把 haha.meme 的各组件部署到服务器的脚本。**脚本里没有写死服务器 IP 和密钥**，用之前先 export：

```bash
export SERVER_IP=<你的服务器 IP>
```

## 脚本

| 脚本 | 作用 |
|---|---|
| `deploy-mcp-server.sh` | 部署 MCP Server 到服务器（Node.js + systemd + nginx） |
| `deploy-website.sh` | 部署网站到服务器（新发布目录 + 软链切换 + 检查） |

部署前先在本地备份，部署后 curl 核对关键改动。不要用 `tar -C <目录> .` 传文件（会把源目录权限还原到目标目录，导致 403）。
