# haha.meme 索引器（Indexer）

haha.meme 的链下索引器：同步 BSC 主网上的合约事件，写进 Postgres，
再用一个只读 HTTP API 供主站 `/api/` 查询。只读链上数据，不签名、
不发交易、不持有任何私钥。

- 链：BSC 主网，chainId 56
- 起点区块：`134834631`（第一批合约部署块）
- 确认深度：`3` 块（`common.py` 的 `CONFIRMATIONS`）
- 索引的合约（11 个地址）：10 个核心合约（Policy、Metadata、Resolver、
  Registry、Registrar、AgentIdentity、Points、Reputation、Marketplace、
  Deployer）+ 第一季模块 HahaSeason1（`0x4B8a35bFe18750c2058fd01e7159728adD345C00`，
  部署块 135231506）。其中 Metadata 与 Deployer 没有自定义事件，不产生
  日志；`.ai` 注册表（`0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F`）不索引，
  只在解析 `.ai` 时按需读。
- 第一季模块地址由环境变量 `SEASON1_MODULE` 提供；不设或为零地址时，
  第一季事件不索引，第一季接口返回空。

## 文件一览

| 文件 | 作用 |
| --- | --- |
| `common.py` | 读环境文件、带限速/退避/轮换的 BSC JSON-RPC 客户端、keccak256、ABI 日志解码。事件签名以仓库 `src/` 为准，topic0 在导入时由签名现算。 |
| `syncer.py` | 同步循环：`eth_getLogs` 区间最多 2000 块，限流或 range too large 时减半（最小 50），成功后慢慢加回；每秒同一 RPC 最多 5 次；429/超时指数退避 1–60 秒，连续失败 3 次换备用 RPC。每批日志、区块头、派生表更新、`checkpoint` 在同一个事务里提交。每轮核对 `checkpoint.safe_hash`，不一致时沿 `parent_hash` 回退到最后一个在链上的块 N，一个事务删 `> N` 的原始日志并整表重算派生表。 |
| `api.py` | 只读 HTTP API，只绑 `127.0.0.1:8787`，内部路由不加 `/api` 前缀（nginx 会 strip）。见下文“接口”。 |
| `schema.sql` | 完整建表（含第一季的表）。全新安装只跑这一个文件。 |
| `migrations/` | 给已有库的增量迁移，按编号顺序跑。见下文“迁移”。 |
| `migrations-002.sql` | 单独放的增量迁移：`reviews_latest` 索引（`/v1/reviews/latest` 排序用）。 |
| `season1_read.py` | 第一季查询：天、资格、证明、订单、核验、找错、排行榜。`season1_read.py` 不做 RPC，只读库。 |
| `season1_store.py` | 第一季事件落库：`DayRootSet`、`Redeemed`、`VerificationClaimed`、`TaskPackSet`、`FindingCommitted` 等；收到 `DayRootSet` 后用 `season1_merkle.py` 重算当天的根，写 `recomputed_root`。 |
| `season1_merkle.py` | Merkle 根重算（与链上 `setDayRoot` 的根同一套算法，用于核对 `rootMatch`）。 |
| `season1_backfill.py` | 补回第一季模块日志（`SEASON1_MODULE` 配晚了、同步指针已过部署块时用）。不移动全局 checkpoint。跑之前先停索引器。 |
| `svg.py` | 名字 NFT 的 SVG 生成：与链上 `HahaMetadata.buildSvgOnly(label, tld)` 逐字节一致，供 `/v1/names/{name}/image.svg` 用。 |
| `setup_db.sh` | 全新安装建库脚本（有防呆，见下文）。 |
| `env.example` | 环境文件模板（只有占位符，没有真凭据）。 |
| `haha-indexer.service` / `haha-api.service` | systemd 单元。 |
| `tests/fixture_test.py` | 合成夹具测试（只用测试库 `haha_indexer_test`，见下文）。 |

## 数据表（`schema.sql`）

- 原始数据：`raw_logs`（全部事件原文）、`blocks`（区块头）、`checkpoint`（同步指针 id=1）。
- 派生表：`names`（名字 + 持有人 + 挂单）、`listings`、`trades`、`agents`、`reviews`、`points`（按 `.ai` 计的积分余额）、`handle_cache`（`.ai` handle 1 小时缓存）。
- 第一季：`season1_days`（每天的根、快照块、名额）、`season1_orders`（兑换订单）、`season1_entries`（入选名单 + Merkle proof）、`season1_task_packs`（任务包哈希）、`season1_verifications`（每日核验）、`season1_findings`（找错提交）、`season1_finding_reports`（找错报告正文）、`season1_validators`、`season1_reward_signer`。

## 接口（`api.py`）

分页：`limit` 默认 24、最大 50，游标分页（`nextCursor`），空列表返回 200。
除注明外全部是 GET，返回 JSON。

- `GET /health` — `{ok: true}`。
- `GET /v1/stats` — 总览：参与 `.ai` 数、各后缀注册数、3 位数字/字母剩余数、agent 总交互次数（`raw_logs` 里不同交易哈希数）、最新铸造、安全区块。
- `GET /v1/names` — 全部已铸名字，最新在前；`tld` 是整数（0=haha，1=meme）。
- `GET /v1/names/{fullName}` — 查一个名字；**未铸造也是 200**，`minted: false`。
- `GET /v1/names/{fullName}/generations` — 该名字的历代 agent。
- `GET /v1/names/{fullName}/image.svg` — 名字 NFT 图片（链上 SVG 的逐字节复刻）。
- `GET /v1/names/{fullName}/metadata` — 名字元数据。
- `GET /v1/owners/{address}/names` — 该地址当前持有的名字（最多 200 条，带仍有效的挂单）。
- `GET /v1/owners/{address}/primary` — 该地址的主名。
- `GET /v1/listings` / `GET /v1/trades` — 挂单 / 成交。
- `GET /v1/agents` — agent 列表；`GET /v1/leaderboard/reputation` — 信誉榜；`GET /v1/reviews/latest` — 最新评价；`GET /v1/leaderboard/points` — 积分榜。
- `GET /v1/events` — 全部已索引事件，最新在前。筛选：`contract=`（合约 key，如 `registrar`，或 0x 地址，或 `season1`）、`event=`（事件名，如 `NameMinted`）、`address=`（相关地址：日志自身的合约，或任一 topic 里带它的地址）。解不出来的日志也会返回，`event: null`、`args: {}`（只发生在 `common.py` 里没有定义的事件上；第一季的 14 个事件与验证的 3 个事件都已收录）。

第一季（`day` 是 dayIndex，如 20781）：

- `GET /v1/season1/days/{day}` — 当天的根（链上根 vs 重算根、`rootMatch`）、快照块、名额、是否开放。
- `GET /v1/season1/eligibility/{aiId}?day=` — 资格（reserved / boundary / excluded）与积分余额。
- `GET /v1/season1/proof/{aiId}?day=` — Merkle 证明（`balance`、`tier`、`root`、`proof`）；当天无入选记录返回 404。
- `GET /v1/season1/orders?day=` — 当天的全部订单（`day` 参数必填）。订单 `status` 是字符串（`Pending` / `Fulfilled` / `CreditOpen`）；`tld` 是整数（0=haha，1=meme）。
- `GET /v1/season1/orders/{orderId}` — 单个订单。
- `GET /v1/season1/verify/{aiId}?day=` — 每日核验结果（`verdict`: `Match` / `Discrepancy` / null）。
- `GET /v1/season1/findings` — 全部找错提交列表。
- `GET /v1/season1/findings/{reportEvidenceHash}` — 单个找错（未揭示的只返回 `{withheld: true}`）。
- `GET /v1/season1/taskpack/{day}` — 当天任务包原文（raw bytes，原样返回）。
- `GET /v1/season1/leaderboard/{day}` — 当天入选名单（含无效条目，`valid: false`）。
- `POST /v1/season1/findings/{reportEvidenceHash}/report` — 提交人公示自己的找错报告（body：`reportId`、`title`、`content`；服务器验 `keccak256(content) == reportEvidenceHash` 才入库；salt 绝不发送、绝不入库）。

标准注册文件与验证：

- `GET /v1/agents/by-name/{fullName}/registration.json` — 某名字当前活跃 agent 的标准注册文件（EIP-8004 registration-v1；名字不存在 `404 name_not_found`，无活跃 agent `404 no_active_agent`）。
- `GET /v1/agents/{agentId}/registration.json` — 某 agentId 的注册文件（已停用的也返回 200，`active: false`；不存在 `404 agent_not_found`）。
- `GET /v1/agents/{agentId}/validations` — 某 agent 的全部验证记录（未知 agentId 返回空列表）。
- `GET /v1/validations/{requestHash}` — 单条验证记录（不存在 `404 validation_not_found`）。
- `POST /v1/validations/upload` — 上传签好的验证请求文档（body：`agentId` 或 `fullName`、`tag`、`version`、`document`、`signature`）；接口先验签名（恢复出的地址须是链上 `ownerOf(agentId)`），通过后自动发布到 `https://haha.meme/validations/{名字}-{短标签}-v{n}.json`，返回 `{url, requestHash, agentId}`；每个 agent 每天最多成功上传 10 次。验证合约 `HahaValidation`（`0xAF9d2D3b6717469B21464baA12B022817841952b`，部署区块 135619015），V1 验证者为项目管理员。

注意：`POST /v1/season1/sign-verify`（每日核验签名）**不在这个仓库里**，
它是独立的签名服务（私钥只在签名服务器上），不在索引器里。

## 迁移（`migrations/`）

全新安装只跑 `schema.sql`（已含全部表，不用再跑迁移）。**已有库**按编号
顺序补迁移：

| 迁移 | 内容 |
| --- | --- |
| `migrations/001_name_indexes.sql` | `names` 的 `owner` / `label` 索引（只加索引，不改行、不停同步器，跑完重启 API 即可）。 |
| `migrations-002.sql`（单独文件） | `reviews` 的 `reviews_latest` 索引（`/v1/reviews/latest` 排序用）。 |
| `migrations/003_season1.sql` | 第一季的表（days / orders / verifications / findings / task_packs / entries / validators / reward_signer）。 |
| `migrations/004_season1_signers.sql` | 签名轮换表（validators / reward_signer）。 |
| `migrations/005_season1_proof.sql` | `season1_entries` 加 `proof` JSONB 列（Merkle 证明）。 |
| `migrations/006_season1_finding_reports.sql` | `season1_finding_reports` 表（找错报告公示）。 |

迁移必须用 `haha` 用户跑（`sudo -u haha`），不要用 postgres 超级用户。
超级用户建的表属主是 postgres，索引器（`haha` 用户）会报
`InsufficientPrivilege: must be owner of table ...` 然后反复重启。
如果已经用超级用户跑过，事后补一句：

```sql
ALTER TABLE <表名> OWNER TO haha;
```

示例（补 003 的表）：

```sh
set -a; . /etc/haha/indexer.env; set +a
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f /opt/haha-indexer/migrations/003_season1.sql
sudo systemctl restart haha-indexer haha-api
```

## 部署（服务器，全新安装）

```sh
# 1. Postgres 16，建角色与库（或用 setup_db.sh，见下文）
sudo -u postgres psql -c "CREATE USER haha WITH PASSWORD '<密码>'"
sudo -u postgres psql -c "CREATE DATABASE haha_indexer OWNER haha"
sudo -u postgres psql -c "CREATE DATABASE haha_indexer_test OWNER haha"

# 2. 代码
sudo mkdir -p /opt/haha-indexer
sudo cp -r . /opt/haha-indexer/
sudo chown -R haha:haha /opt/haha-indexer
sudo chmod 640 /opt/haha-indexer/*.py /opt/haha-indexer/*.sql

# 3. 环境文件（0600，只在服务器上，绝不进仓库）
#    cp env.example /etc/haha/indexer.env 再填真值
sudo mkdir -p /etc/haha
sudo cp env.example /etc/haha/indexer.env
sudo chown haha:haha /etc/haha/indexer.env
sudo chmod 0600 /etc/haha/indexer.env
#    indexer.env 里填：
#      DATABASE_URL=postgresql://haha:<密码>@127.0.0.1:5432/haha_indexer
#      BSC_RPC_URLS=https://bsc-dataseed.binance.org,https://bsc-dataseed1.defibit.io,https://bsc.publicnode.com
#      SEASON1_MODULE=0x4B8a35bFe18750c2058fd01e7159728adD345C00

# 4. 建表（用 haha 用户跑）
set -a; . /etc/haha/indexer.env; set +a
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f /opt/haha-indexer/schema.sql

# 5. systemd（haha-indexer 先起，haha-api 后起）
sudo cp haha-indexer.service haha-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now haha-indexer haha-api
journalctl -u haha-indexer -u haha-api -f

# 6. 健康检查
curl -fsS http://127.0.0.1:8787/health
curl -fsS http://127.0.0.1:8787/v1/stats | head -c 500
```

nginx（写在主站的 server 块里；`/api/` 不要套静态文件 7 天缓存）：

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8787/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

### `setup_db.sh`（建库脚本，有防呆）

只在全新安装时跑一次。默认行为：

- 库已存在就直接拒绝退出，不会动现有数据；要重建必须显式加 `--reset`。
- `--reset` 需要交互终端 + 两步确认（先打 `yes`，再输入库名 `haha_indexer`），
  而且先自动 `pg_dump` 备份到 `/var/backups/haha-indexer/`（每库只留最新 3 份），
  备份失败就停，不继续 DROP。
- 密码不走命令行传参（`ps` 看不到），只写进 0600 的 env 文件。
- 已有 `/etc/haha/indexer.env` 时保留其中的 `BSC_RPC_URLS`，只更新
  `DATABASE_URL`；全新安装才写默认的 3 个公开节点。

```sh
bash setup_db.sh --help      # 看说明
bash setup_db.sh --dry-run   # 只打印要做什么，不改任何东西
bash setup_db.sh             # 全新安装
bash setup_db.sh --reset     # 重建（危险：清库，有确认 + 先备份）
```

**不要在生产机上随手重跑这个脚本。** `--reset` 会踢掉连接、DROP 两个库、
轮换密码；恢复只能从区块 134834631 全量重同步。

## 本地开发

依赖只有 Python 3.12 标准库 + `psycopg2` + `pycryptodome`
（服务器上是 apt 的 `python3-psycopg2`、`python3-pycryptodome`，
后者以 `Cryptodome` 命名空间提供；本地 `Crypto` 也能用，代码里
两个都试）。上传接口（`POST /v1/validations/upload`）验签另需
`eth-account`（函数内惰性 import，不用上传接口时不用装）。

```sh
# 语法检查
python3 -m py_compile *.py
# 测试（只用测试库 haha_indexer_test，不碰生产库）
# tests/fixture_test.py：在测试库里搭一条完整链路（铸造、挂单、激活、
# 评分、转让、成交）并断言派生表状态
python3 tests/fixture_test.py
# 只同步一次（不常驻）
python3 syncer.py --once
# 只起 API（默认端口 8787）
python3 api.py
```

## 安全说明

- 这个仓库里**没有任何密钥**：没有私钥、没有 API key、没有数据库密码。
  密钥只存在服务器的 `/etc/haha/indexer.env`（0600）里，代码只读这个
  路径（`env.example` 是纯模板）。
- 索引器只读链上数据，不签名、不发交易；`sign-verify` 签名服务是独立
  的，不在这个仓库里。
- `setup_db.sh` 的 `--reset` 会清库，见上文。
