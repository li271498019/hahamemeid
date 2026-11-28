# 第一季上线运行单

业务数字以 [00-parameters.md](00-parameters.md) 为准。页面和索引代码已经在 `6566d9e28de416ee7ac89c92646d23abbad49074`。本文件写的是还没做的补日志，不是再发一遍页面。兑换和领奖保持关闭。

## 用哪一个提交

线上发布目录已经是 `/var/www/releases/20261123-081321-season1-6566d9e`。不要把站点再切一次，也不要退回 `e531602`，也不要部署一个还会变的 `main`。

`6566d9e` 的索引器没有 `season1_backfill.py`。`syncer.py` 的 `run_once` 从 `checkpoint.safe_block + 1` 往后拉，地址表只在环境变量 `SEASON1_MODULE` 有值时才包含模块。C 报告的游标是 `135237213`。现在写入模块地址再重启，下一笔从 `135237214` 开始，不会回到部署块 `135231506`，因此会漏掉 `135233318` 的 `ValidatorSet` 和 `135233378` 的 `RewardSignerSet`。这不是「部署前没有事件」。模块已经部署并完成授权。不要清空生产库，也不要把 checkpoint 改小。改小会让重组路径清掉名字、挂牌和积分派生表。

补回放脚本在包含本文件的 PR 里。L 合并之后，只把那个 merge commit 的 `indexer/season1_backfill.py` 放到 `/opt/haha-indexer/`。站点发布目录保持 `6566d9e`。合并前不要把未合并的分支部署上去。

工作目录是该提交的仓库根，除非某条命令写了别的目录。

## 两类钱包

| 钱包 | 谁保管 | 要不要 BNB | 做什么 |
| --- | --- | --- | --- |
| 管理员 `0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7` | L | 要。后面的 `setDayRoot`、打开开关都由这笔交易付 gas | 逐笔在自己的钱包里签名 |
| 日奖签名 `0xbd02a475Cb374B1685e6BAae1CF1FbDc2deE5aaA` | 已经在 C 的服务器上 | 不要。它只做链下 EIP-712 | 私钥留在现有文件里 |

不要把 SSH 密码、管理员私钥或日奖私钥交给 A，也不要写进仓库、日志或聊天。

链上已经核对过、本文件不要求再发的交易：部署、`setSpender`、`setSpenderBudget(200, 4000)`、三笔 `setEarner`、`setValidator`、`setRewardSigner`。这些都是 L 已经签过的。C 没有链上权限，不能代签。

## 已经核对的地址

- 模块 `0x4B8a35bFe18750c2058fd01e7159728adD345C00`
- 部署块 `135231506`，哈希 `0xd0c1080ee303a2bcbb74cf64308c8beba7f4287b0ec86ffeac80d7c1156bcfa6`
- `redeemOpen` 和 `rewardsOpen` 都是 false
- 日奖地址在 `validators` 里是 true。管理员地址不是 validator
- `rewardSigner` 是管理员地址

`validators` 为 true 不会打开领奖，也不会让签名进程开始签名。

## 日奖文件

服务器上已有 `/etc/haha/season1-signer.env`，权限 `0600`。这不是本目录旧说明里的 `/etc/haha/season1-signer.key`。不要新建 key 文件，不要覆盖 `.env`，不要 `cat` 这个文件，不要把它拷进发布目录或 indexer.env。

变量名可以不是 `SEASON1_SIGNER_KEY`。检查命令只在内存里推导地址，对上 `0xbd02a475Cb374B1685e6BAae1CF1FbDc2deE5aaA` 才继续。对不上就退出，不打印文件内容。

## 顺序

每一步的成功判据没达到就停。不要因为模块和角色已经接上就打开功能。

1. 页面、`003` 的六张表和 `004` 的两张签名表已经在线上。不要删表，不要重跑全量索引。
2. L 合并本 PR。只把 merge commit 里的 `indexer/season1_backfill.py` 拷到 `/opt/haha-indexer/season1_backfill.py`。
3. 停 `haha-indexer`。先记下 `checkpoint.safe_block`。跑 `--dry-run`，再跑正式补回放。两遍之后 `safe_block` 必须和停机前相同。
4. 用下面的 SQL 把库里的行和链上回执逐笔比对。对上之后，才把 `SEASON1_MODULE` 写进 `/etc/haha/indexer.env` 并启动索引。启动之后的 health 只说明游标又追上了新块，不代替第 4 步。
5. 签名检查仍然要求 `signingEnabled` 为 false。今天不调用 `setDayRoot`。

## C：页面

站点保持 `/var/www/releases/20261123-081321-season1-6566d9e`。不要再切一次发布目录。

`/season` 应仍是规则页 HTML，正文含「不连接钱包」，不是目录列表。页面上的「本地夹具」只是样本，不是链上根。`/v1/season1/days/20781` 在根还是零时是 404，这只说明 `season1_days` 没有这一行，不能说明签名人表已经被补过。

## C：补回放

迁移已经做过。下面的命令只补模块合约自己的日志，起点是部署块 `135231506`，终点是停机时读到的 `checkpoint.safe_block`，不是写死的 `135237213`。它不修改 checkpoint，不碰其它业务表里的已有行。

```sh
sudo systemctl stop haha-indexer
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "SELECT safe_block, encode(safe_hash, 'hex') FROM checkpoint WHERE id = 1"
python3 /opt/haha-indexer/season1_backfill.py --dry-run
python3 /opt/haha-indexer/season1_backfill.py
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "SELECT safe_block FROM checkpoint WHERE id = 1"
```

`--dry-run` 不写库。它的 `chainLogs` 必须含下面两笔，地址都是 `0x4b8a35bfe18750c2058fd01e7159728add345c00`：

| 事件 | 块 | logIndex | 交易 |
| --- | --- | --- | --- |
| ValidatorSet | 135233318 | 218 | `0x3c10db324213a5e21625d71b0eb04058bb1fb78af9bfa9bbf6a5f64f9f2ad743` |
| RewardSignerSet | 135233378 | 251 | `0x21880599387bb198ffc3dc7a32beb67536f7c4a82e815e10b5be1a07d466b80f` |

部署交易 `0x13b3440e28e0e5ba596935420f5e097e7fc6bdc5026dbfc773488bb65b51b57b` 的收据是 0 条日志，所以不会出现在 `chainLogs` 里。正式命令成功时 `ok` 为 true，`missingAnchors` 为空，`undecoded` 为 0，`database.checkpoint` 等于停机前的 `safe_block`。`database.moduleRawLogs` 里的 `txHash` 和 `logIndex` 要和上表一致，并且和 `chainLogs` 的条数一致。多出来的模块日志也要留下，不能只保留这两笔。

对完再写环境并启动。不要把日奖私钥写进 indexer.env。

```
SEASON1_MODULE=0x4B8a35bFe18750c2058fd01e7159728adD345C00
```

```sh
sudo systemctl start haha-indexer
sudo systemctl restart haha-api
```

只读核对：

```sh
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 << 'SQL'
SELECT encode(account, 'hex'), allowed, block_number, log_index FROM season1_validators;
SELECT encode(account, 'hex'), block_number, log_index FROM season1_reward_signer;
SELECT block_number, log_index, encode(tx_hash, 'hex')
FROM raw_logs
WHERE address = '\x4b8a35bfe18750c2058fd01e7159728add345c00'
ORDER BY block_number, log_index;
SELECT count(*) AS days FROM season1_days;
SELECT count(*) AS orders FROM season1_orders;
SQL
```

`season1_validators` 应有 `bd02a475cb374b1685e6baae1cf1fbdc2dee5aaa`、allowed true、块 `135233318`、logIndex `218`。`season1_reward_signer` 应有 `083a467259f12602e9053bbae2b3fd5b62976ef7`、块 `135233378`、logIndex `251`。`season1_days` 和 `season1_orders` 现在可以是 0，因为还没有 `DayRootSet` 或 `Redeemed`。这不能用来解释签名人两张表也是 0。

health 的 lag 变小只表示从当前游标向前追上了。历史是否完整，只看上面的 `raw_logs` 和两张签名表。

索引进程的确认深度仍是 3。这和 `setDayRoot` 的 15 块确认不是同一件事。

成功判据：

```sh
curl -fsS http://127.0.0.1:8787/health
curl -sS -o /tmp/day.json -w '%{http_code}\n' http://127.0.0.1:8787/v1/season1/days/20781
```

health 的 `chainId` 是 56。day 的 HTTP 状态是 404，正文是 `{"error":"not_found"}`，不能是 `rootMatch: true`。公网对应路径是 `https://haha.meme/api/health` 和 `https://haha.meme/api/v1/season1/days/20781`。`/health` 不经过 nginx 的 `/api/` 反代，公网 404 是正常的。

日志只看进程输出，不要去读签名文件：

```sh
journalctl -u haha-indexer -u haha-api --since '10 min ago' | grep -E 'synced to|FATAL|batch failed|backfill'
```

## C：签名检查

在仓库根：

```sh
PYTHONPATH=. python3 -m tools.season1 signer-check \
  --signer-env /etc/haha/season1-signer.env \
  --indexer-env /etc/haha/indexer.env
```

成功判据：退出码 0，JSON 里 `address` 是 `0xbd02a475Cb374B1685e6BAae1CF1FbDc2deE5aaA`，`addressMatch` 和 `validator` 都是 true，`signingEnabled` 是 false。不要设置 `SEASON1_SIGNING`。

以后 L 明确允许日奖进程签名时，才在那个进程的环境里加 `SEASON1_SIGNING=on`，并带上 `SEASON1_MODULE` 为上面的地址、`SEASON1_CHAIN_ID=56`。缺任何一项、链上 `validators` 不是 true、或不在当天 UTC 窗口内，签名命令都会退出，不产生签名。这仍然不打开合约里的 `rewardsOpen`。

## 首日根

现在是 2026-11-23。第一天的界是 `1795478400`，也就是北京时间 2026-11-24 08:00。今天的块不能拿来做明天的根。不要改日期，也不要退到更早的块。

到了那个时间之后：

1. 取时间戳不晚于 `1795478400` 的最后一块。这就是快照块。
2. 等链头至少走到快照块加 15。确认不够就停，不换更早的块。
3. 再跑预检。`ok` 不是 true，或者 `remainingBlocks` 不是正数，就不签 `setDayRoot`。`remainingBlocks` 是还能等待的块数，不是分钟。合约在 `block.number >= snapshotBlock + 256` 时直接 `StaleSnapshot`。
4. 只有 L 的管理员钱包签这一笔。C 不签。

```sh
PYTHONPATH=. python3 - << 'PY'
from tools.season1.merkle import root_publish_precheck
head = int(input("head: "))
snap = int(input("snapshot: "))
print(root_publish_precheck(head, snap))
PY
```

根还是零、或者复算不一致时，申请页不生成指令，`redeemOpen` 保持 false。

## 回滚

补回放命令失败时自己回滚，库保持停机前的样子。不要 `TRUNCATE`，不要把 `checkpoint` 改小，不要把站点指回 `e531602`。

若正式补回放已经提交、但比对不符：停索引，只删模块地址 `4b8a35bfe18750c2058fd01e7159728add345c00` 在 `raw_logs` 里的行，并清空 `season1_validators` 和 `season1_reward_signer`。不要删 `names`、`listings`、`points` 或其它业务表。然后保持 `SEASON1_MODULE` 不设置，再启动原来的索引进程。不要发交易去改已经是 false 的开关，也不要再部署或再授权模块。
