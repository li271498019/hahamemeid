# 部署指南（DEPLOY.md）

这份文档让你从零把 haha.meme 的整套系统跑起来：**网站、索引器、MCP Server、后端服务**。照着做就行。

> 安全底线：**私钥、密码、服务器 IP、RPC 密钥不要写进仓库。**所有密钥都放服务器的环境变量文件（`/etc/haha/*.env`，0600），代码只读环境变量。部署脚本里的服务器 IP 用 `SERVER_IP` 环境变量传入。

## 0. 准备

- 一台 Ubuntu 24.04 服务器（2 核 4G 够用），一个域名（已指向服务器）
- 服务器上装：Node.js 22 LTS、Python 3.12、PostgreSQL 16、nginx、git
- 本地装：git、Node.js 22、Python 3.12

```bash
# 服务器：装 Node.js 22（Ubuntu apt 只有 Node 18，太旧）
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs postgresql nginx git python3-pip
```

## 1. 合约（不用部署，已在主网）

12 个合约已部署在 BSC 主网（chainId 56），全部 BscScan 开源验证、不可升级。地址见 [README.md](README.md) 的合约表。**任何人都能在 BscScan 上核对源码与链上字节码是否一致。**

想自己重新部署：`src/` + `foundry.toml`，用 Foundry（`forge build` 需 `via_ir=true`）。

## 2. 索引器（indexer/）

索引器把链上事件同步进 Postgres，对外提供 REST API（网站、scan、MCP 都调它）。

```bash
# 服务器
sudo useradd -r -s /bin/false haha
sudo mkdir -p /opt/haha-indexer
# 把 indexer/ 拷到 /opt/haha-indexer
cd /opt/haha-indexer
pip install -r requirements.txt

# 建库（密码自己定，只放 env 文件）
sudo -u postgres createdb haha_indexer
sudo -u postgres psql -c "CREATE USER haha WITH PASSWORD '<自己定>';"
sudo -u postgres psql -c "GRANT ALL ON DATABASE haha_indexer TO haha;"

# 环境变量（0600，只在服务器上）
sudo mkdir -p /etc/haha
sudo cp indexer/env.example /etc/haha/indexer.env   # 照模板填真实值
sudo chmod 0600 /etc/haha/indexer.env

# 初始化表结构（不要随手重跑 setup_db.sh，会清空库）
sudo -u haha psql "$DATABASE_URL" -f schema.sql
for f in migrations/*.sql; do sudo -u haha psql "$DATABASE_URL" -f "$f"; done

# 启动（systemd 单元在 indexer/ 里有模板）
sudo systemctl enable --now haha-indexer haha-api
```

API 默认监听 `127.0.0.1:8787`，nginx 用 `/api/` 反代。索引从区块 134834631 开始同步，全量同步需要一段时间。

**验证**：`curl http://127.0.0.1:8787/v1/stats` 应返回平台统计；再对照 [haha.meme/scan.html](https://haha.meme/scan.html) 的数字是否一致。

## 3. 网站（website/）

纯静态站，无构建、无框架、不接钱包。

```bash
# 把 website/ 拷到发布目录，用软链切换（不要直接覆盖线上目录）
sudo mkdir -p /var/www/releases
sudo cp -a website /var/www/releases/<时间戳>-website/
sudo ln -sfn /var/www/releases/<时间戳>-website/ /var/www/haha.meme
sudo chown -R root:www-data /var/www/releases/<时间戳>-website/
sudo chmod 755 /var/www/releases/<时间戳>-website/
```

nginx 配置要点：干净地址落到对应 html；`/api/` 反代到索引器 `127.0.0.1:8787`；`/rpc/` 反代到公开 BSC 节点；`/mcp/` 反代到 MCP Server `127.0.0.1:3333`。`deploy/` 里有参考脚本。

**验证**：打开网站，首页数据条的数字应与索引器 `/v1/stats` 一致；`skill.md` 的版本号应与仓库一致。

## 4. MCP Server（MCP/）

只读查询接口，供 agent 直接查数据。

```bash
cd MCP
npm install
npm run build
# 部署脚本见 deploy/deploy-mcp-server.sh（先 export SERVER_IP）
```

systemd 单元与 nginx 配置见 `MCP/`。默认 `HAHA_API_BASE=http://127.0.0.1:8787`。

**验证**：`curl https://<你的域名>/mcp/health` 返回 ok；`GET /mcp/stats` 返回聚合统计（不含原始 IP）。

## 5. 后端服务（services/）

| 服务 | 作用 | 密钥 |
|---|---|---|
| `services/validator/` | G13 验证：监听验证请求，签发结果 | 管理员私钥 |
| `services/sign-verify/` | 第一季每日验证签名 | 每日验证签名私钥 |
| `services/season1-admin/` | 第一季每天 08:00 自动化 | 管理员私钥 |

密钥的放法（以管理员私钥为例）：

```bash
# 只在服务器上建文件，0600，不进仓库
sudo sh -c 'echo "ADMIN_PRIVATE_KEY=0x<你的私钥>" > /etc/haha/admin-signer.env'
sudo chmod 0600 /etc/haha/admin-signer.env
```

各服务的 `.env.example` 列了它需要的变量。服务代码用 `tools/season1/` 共享模块（仓库里已有），运行前把仓库根目录加进 `PYTHONPATH`：

```bash
export PYTHONPATH=/opt/haha-meme   # 仓库根目录
```

systemd 单元文件在各服务目录里。

**验证**：`systemctl status haha-validator haha-sign-verify` 均为 active；日志里没有报错。

## 6. 怎么验证这套部署是真的

- **合约**：BscScan 上查 12 个地址，源码已验证，与 `src/` 一致。
- **网站**：把 `website/` 的文件与线上 `https://haha.meme/` 的页面逐一对照，内容一致。
- **索引器**：`/v1/stats` 的数字与 BscScan 的链上事件数对得上。
- **MCP**：`https://<域名>/mcp` 能连上，29 个工具都能调通。
- **第一季**：`GET /v1/season1/days/{day}` 的根与链上 `HahaSeason1.dayRoot()` 一致。

## 7. 常见坑

- 不要用 `tar -C <目录> .` 传文件：`.` 会把源目录权限还原到目标目录，导致 403。
- 不要随手重跑索引器的 `setup_db.sh`：会清空生产库并轮换数据库密码。
- 部署脚本必须幂等：失败重试不要重复执行已成功的建目录、翻软链步骤。
- `muse.write` 会静默删掉个别全角符号和空格：写精确文案用 Python 写文件并逐字校验。
