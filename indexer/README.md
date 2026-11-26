# haha.meme V1 索引器

按 `docs/website/V1-INDEXER-SPEC.md`（PR #9，main `756638f9`）实现。
链 BSC 主网 chainId 56，起点区块 134834631，确认深度 3 块。
同步 8 个有事件的合约（Policy、Resolver、Registry、Registrar、
AgentIdentity、Points、Reputation、Marketplace），Metadata 与 Deployer
无自定义事件，不索引 `.ai` 注册表。

## 组成

- `common.py` — env、带限速/退避/轮换的 BSC JSON-RPC 客户端、
  keccak256、ABI 日志解码。事件签名以仓库 `src/` 为准，topic0 在
  导入时由签名现算。
- `schema.sql` — Postgres：`raw_logs`、`blocks`、`checkpoint`、
  派生表 `names`、`listings`、`trades`、`agents`、`reviews`、`points`，
  以及内部的 `handle_cache`（`.ai` handle 1 小时缓存）。
- `syncer.py` — 同步循环：`eth_getLogs` 区间最多 2000 块，限流或
  range too large 时减半（最小 50），成功后慢慢加回；每秒同一 RPC
  最多 5 次；429/超时指数退避 1–60 秒，连续失败 3 次换备用 RPC。
  每批日志、区块头、派生表更新、`checkpoint` 在同一个事务里提交。
  每轮核对 `checkpoint.safe_hash`，不一致时沿 `parent_hash` 回退到
  最后一个在链上的块 N，一个事务删 `> N` 的原始日志并整表重算派生表。
- `api.py` — HTTP API，只绑 `127.0.0.1:8787`，内部路由不加 `/api`
  前缀（nginx 会 strip）：`/health`、`/v1/listings`、`/v1/trades`、
  `/v1/agents`、`/v1/leaderboard/reputation`、
  `/v1/names/{fullName}`（精确查一个名字，未铸造也是 200，`minted:false`）、
  `/v1/names/{fullName}/generations`、`/v1/owners/{address}/names`
  （该地址当前持有的名字，最多 200 条，带上仍有效的挂单）、
  `/v1/leaderboard/points`。
  游标分页，limit 默认 24、最大 50，空列表 200。
  名字查询走 `names.full_name` 唯一索引；按持有人查询走 `names_owner`。

## 部署（服务器）

```sh
# 代码
/opt/haha-indexer/          # common.py syncer.py api.py schema.sql
# 环境（0600，只在服务器上，绝不进仓库）
/etc/haha/indexer.env       # DATABASE_URL + BSC_RPC_URLS
# systemd
/etc/systemd/system/haha-indexer.service
/etc/systemd/system/haha-api.service
systemctl enable --now haha-indexer haha-api
journalctl -u haha-indexer -u haha-api -f
curl -fsS http://127.0.0.1:8787/health
```

已有库补索引（不改行、不停同步器，跑完只重启 API）：

```sh
set -a
. /etc/haha/indexer.env
set +a
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f /opt/haha-indexer/migrations/001_name_indexes.sql
sudo systemctl restart haha-api
curl -fsS "http://127.0.0.1:8787/v1/names/tst1234.haha"
```

nginx（写在 `ddao.app` / `haha.meme` 的 server 块里，`/api/` 不要套
静态文件 7 天缓存）：

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8787/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

## 本地开发

依赖只有 Python 3.12 标准库 + `psycopg2` + `pycryptodome`
（服务器上是 apt 的 `python3-psycopg2`、`python3-pycryptodome`，
后者以 `Cryptodome` 命名空间提供；本地 `Crypto` 也能用，代码里
两个都试）。
