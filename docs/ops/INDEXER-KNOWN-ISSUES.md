> 说明：本文写于 2026-11-28，是交给 C 的索引器问题说明。其中“重组卡死”已由私密库 PR #129（迁移 008–010）修复并上线，其余条目按原文保留备查。

# 索引器问题说明（给 C）

范围：`/opt/haha-indexer`（线上已部署 Haha Dog 补丁后的版本）和仓库 `indexer/`。本文只读代码和数据库，没改任何东西。文中行号来自线上 `syncer.py`。补丁部署前的旧版本行号在括号里。

---

## 一、handle_reorg 的 TRUNCATE 会崩（需要修）

### 1. 位置和失败的 SQL
- 文件：`/opt/haha-indexer/syncer.py`
- 函数：`Syncer.handle_reorg(self, safe_block)`，第 296 行起（旧版第 292 行）
- 失败的语句：第 335 行（旧版第 329 行）

```python
for t in ("names", "listings", "trades", "agents", "reviews", "points",
          "season1_days", "season1_orders", "season1_verifications",
          "season1_findings", "season1_task_packs", "season1_entries",
          "season1_validators", "season1_reward_signer",
          "dogs", "dog_snapshots", "dog_listings", "dog_trades", "dog_withdrawals"):
    cur.execute("TRUNCATE %s" % t)          # 轮到 season1_findings 时报错
```

我在本地一个临时库里复现了，PostgreSQL 的报错是：

```
ERROR:  cannot truncate a table referenced in a foreign key constraint
DETAIL:  Table "season1_finding_reports" references "season1_findings".
HINT:  Truncate table "season1_finding_reports" at the same time, or use TRUNCATE ... CASCADE.
```

### 2. 涉及的外键
- `season1_finding_reports.report_evidence_hash REFERENCES season1_findings(report_evidence_hash)`
- 约束名：`season1_finding_reports_report_evidence_hash_fkey`
- 来源：`migrations/006_season1_finding_reports.sql` 和 `schema.sql`
- 我查过线上库：指向这些派生表的外键只有这一条，`dogs` 等狗相关表没有外键。

### 3. 什么时候触发
只要 `check_reorg()` 返回 False 就会进 `handle_reorg`。有两种情况：
- 检查点区块（`checkpoint.safe_block`）在链上的哈希，和库里存的 `safe_hash` 不一致，也就是真的发生了重组。
- 链上哈希和 `blocks` 表里存的哈希不一致。

`CONFIRMATIONS = 3`（11-21 为了速度从 15 降到 3），所以 BSC 偶发的 1–3 块重组是会被检测到的。线上 journal 从 11-22 到现在没有出现过 REORG，这个坑还没踩到过。外键是 11-24 加的，所以第一次真重组就会触发。

### 4. 影响：卡死，不是崩溃
- 失败发生在 `handle_reorg` 的事务里。`DELETE FROM raw_logs/blocks` 和前面几张表的 TRUNCATE 随事务一起回滚，**数据不会损坏**，检查点也没动。
- 异常被 `run_forever()` 的 `except Exception` 接住（`syncer.py` 约第 475 行）：回滚，打日志 `sync error: FeatureNotSupported(...) - retrying in 5s`，睡 5 秒再来。
- 下一轮 `check_reorg` 仍然返回 False，又进 `handle_reorg`，又同样失败。**无限循环，每 5 秒一次。**
- 进程不会退出，所以 systemd 的 `Restart=on-failure` 不会触发，也没有任何告警。
- 后果是同步停在重组前，API 继续返回旧数据（名字、市场、积分、第一季、Haha Dog 都不再更新），除非有人看 journal 才发现。

### 5. 为什么不能用 `TRUNCATE ... CASCADE`
`season1_finding_reports` 不是链上派生数据。它是用户通过 API `POST /v1/season1/findings/{hash}/report` 发布的报告原文，`api.py` 约第 1385–1430 行写入，`content` 就是报告正文，链上没有，重放 raw_logs 恢复不出来。

我在本地验证过：`TRUNCATE season1_findings CASCADE` 会输出 `truncate cascades to table "season1_finding_reports"`，然后报告表清零。一次重组就会永久删掉所有已发布的报告，线上现在有 3 条。所以 CASCADE 看着是一行修复，实际是丢数据。

### 6. 推荐修法（方案 A：去掉外键，改动最小）
这条外键没有保护价值：API 发布报告时已经先查 `season1_findings` 里有没有这个 hash，没有就返回 404。外键只是在重组重放时碍事。去掉以后，`handle_reorg` 的代码一行都不用改，报告表也不会被碰。

1. 新增 `migrations/008_drop_findings_fk.sql`，在线上用 haha 角色执行（`SET ROLE haha`）：
```sql
ALTER TABLE season1_finding_reports
  DROP CONSTRAINT IF EXISTS season1_finding_reports_report_evidence_hash_fkey;
```
2. `schema.sql` 里 `season1_finding_reports` 的建表语句去掉 `REFERENCES season1_findings(report_evidence_hash)`。`schema.sql` 每次启动都会执行，但它是 `CREATE TABLE IF NOT EXISTS`，改它只影响新库，老库要靠第 1 步的迁移。`006` 迁移不要改，历史文件保持原样。
3. 重放时，重组后重新出现的 finding 用的是同一个 `report_evidence_hash`，所以报告会自动重新对上。被重组掉的 finding 对应的报告会暂时成为孤儿行，对读取没有影响，因为 `season1_read.py` 用的是 LEFT JOIN。
4. 加一道保险（可选）：`handle_reorg` 开头检查有没有外键指向要清空的表，有就直接报清楚的错并告警，防止以后再加类似的表时同样踩坑：
```python
cur.execute("""SELECT conname FROM pg_constraint
               WHERE contype='f' AND confrelid::regclass::text = ANY(%s)""",
            (list(DERIVED_TABLES_TO_TRUNCATE),))
if cur.fetchall():
    raise RuntimeError("FK points into a derived table; reorg rebuild would fail")
```

### 7. 备选修法（方案 B：保留外键，重放前后备份报告）
如果一定要保留外键，可以把两张表一起清空，并在事务里先备份、重放后恢复：
```python
cur.execute("CREATE TEMP TABLE _keep_reports ON COMMIT DROP AS "
            "SELECT * FROM season1_finding_reports")
cur.execute("TRUNCATE season1_finding_reports, season1_findings, ...其余派生表...")  # 同一条语句列出两张表就不报错
# ... 现有的 raw_logs 重放 ...
cur.execute("""INSERT INTO season1_finding_reports
               SELECT r.* FROM _keep_reports r
               JOIN season1_findings f USING (report_evidence_hash)""")
```
缺点：被重组掉的 finding 对应的报告会被丢掉（用户需要重新发布）。以后每加一张引用派生表的离线表，都要记得改这里。所以我推荐方案 A。

### 8. 测试方法
不要在线上测。线上有备份 `pg_dump`，在 `/root/backup-r2-20261128-0444/db.dump`，恢复到临时库来测。

1. 恢复备份到临时库，指向它跑 `syncer`（`--env` 用临时环境文件）。
2. 先确认**修复前能复现**：`UPDATE checkpoint SET safe_hash = '\x00…00'` 制造"哈希不一致"，让 `check_reorg` 返回 False，`handle_reorg` 应该抛 `FeatureNotSupported`，journal 里无限重试。
3. 应用迁移 008，重复第 2 步，应满足：
   - 不报错，checkpoint 重新推进到安全高度。
   - `season1_finding_reports` 行数不变（现在是 3），`content` 不变。
   - `season1_findings` 重新出来，行数和之前一致（现在是 3）。
   - `dogs`、`dog_snapshots` 等重建后和重建前内容一致。`tests/dog_e2e.py` 已经有这个对比，里面的强制重组部分当时是先删外键才跑通的（见第 67 行的注释），修复后把那一步去掉。
4. 把这个流程固化成一个自动化测试：建临时库、跑 `schema.sql`、插入 finding 和 report、用假的 RPC（`chain_block` 返回不同哈希）调用 `handle_reorg`，断言不抛错且报告还在。

### 9. 一并建议：卡死要能被发现
- `run_forever` 在同一个异常连续出现 N 次（比如 20 次）后打 ERROR 并 `sys.exit(1)`，让 systemd 重启，也方便告警。
- 提供一个检查点落后量（`head - checkpoint.safe_block`）的健康检查接口或日志，超过阈值（比如 100 块）就告警。现在同步停了没有人会知道。

---

## 二、Haha Dog 开发中发现的其他问题

### 1. `dog_backfill.py` 要求表已存在
`dog_backfill.py` 直接 `TRUNCATE dogs ...`，不会建表。syncer 启动时才会跑 `schema.sql`。这次部署时第一次运行就报 `relation "dogs" does not exist`，我先手动应用了 `migrations/007_haha_dog.sql`（用 `SET ROLE haha`，保证表属于 haha），再重跑才成功。`INDEXER-PLAN.md` 里没写这一步，需要补。建议两个都做：
- 文档：在部署顺序里，第 4 步（backfill）前加一步"应用 007 迁移或用 haha 角色运行 `schema.sql`"。
- 代码：`dog_backfill.py` 的 `main()` 在 TRUNCATE 之前执行一次 `schema.sql`（都是 `IF NOT EXISTS`，可以重复跑）：
```python
with open(os.path.join(HERE, "schema.sql")) as f:
    cur.execute(f.read())
```
注意：用 postgres 超级用户直接跑 007 会让表属于 postgres，haha 写不进去，所以一定要用 haha 角色。007 里也可以补上 `ALTER TABLE ... OWNER TO haha`，就像 006 那样。

### 2. 授权（Approval）没有索引
`common.py` 里 HahaDog 只解码了三个事件：`Transfer`、`Committed`、`Snapshot`。`Approval(owner, approved, tokenId)` 和 `ApprovalForAll(owner, operator, approved)` 没有。

影响：`/v1/dog/listings` 只能用"卖家还是持有人、没重铸过"判断挂单是否过期，看不出**卖家后来撤销了对市场合约的授权**，这种挂单对买家不可买，但接口还显示它有效。目前网站在买之前会用链上 `getApproved` 复核，所以不会丢钱，只是列表里有"假挂单"。

建议：
- `common.py` 给 `dog` 加这两个事件（注意同样的 topic0 在 registrar 里已有定义，要按合约地址区分）。
- 新表 `dog_approvals(token_id PRIMARY KEY, approved BYTEA)` 和 `dog_operators(owner, operator, approved)`，`Transfer` 时清空该 token 的 approved（ERC-721 转移会清授权）。
- `/v1/dog/listings` 增加 `buyable` 字段：`approved == 市场合约` 或 `operator 授权为真`，过期判断和 floor/数量都用 `buyable`。
- 同样适用于重放：这两张表也要加进 `handle_reorg` 的 TRUNCATE 清单。

### 3. 狗 #18、#19 的 `check` 状态，链上是 status 3
线上现在这两只的 API 状态是 `check`，种子为空。链上 `dogOf(18)` 和 `dogOf(19)` 返回的状态字都是 `3`，种子是 0。

**status 3 的含义**（合约里的 `status` 取值）：
- 0 未铸造
- 1 出图中（在等目标区块 N+4）
- 2 已出图
- 3 出图中但哈希错过了，持有人可以免费重铸

种子 = `keccak256(abi.encode(blockhash(N+4), tokenId, 重铸次数))`，N 是提交区块。合约在 mint、reroll、transfer 或有人调用 snapshot 函数时把 N+4 的哈希存起来；原生 `blockhash` 只能回看 256 块，EIP-2935 能回看 8191 块（约 1 小时）。

这两只狗是同一笔交易在区块 136160282 铸造的（11:41:18 UTC+8），目标区块 136160286。到我检查时区块高度已经 136170388，差了约 10,100 块，**超过 8191 块的窗口**，而且期间没有任何人触发过 snapshot，所以哈希永远取不到了。

结论：
- 这是合约设计内的极端情况，不是索引器 bug，也不是丢数据。
- 不会自己好起来。**持有人需要免费重铸一次**（`reroll(tokenId)`），重铸后重新出图。持有人是同一个地址，owner `0xe40a…ac49`，两只都是他的。我的判断依据是链上状态字、网站文案和 skill.md 的说明；是否真的无法补救（比如 snapshot 函数是否还能救）我没有发交易验证，没有这个权限。
- 索引器改进：现在 `resolve_seeds` 取不到哈希时只能返回 `check`，让客户端去问链。建议对这类狗直接 `eth_call dogOf(tokenId)`，读出链上状态字，如果是 3 就存成 `stalled`，API 返回 `stalled`（对应网站的"出图中，可重铸"），不要让它长期停在含糊的 `check`。

### 4. 对 Ankr 的依赖（getLogs 与公共节点）
- `RpcClient.get_logs` 每批把 16 个合约地址放进同一个 `eth_getLogs` 过滤器（`common.py` 的 `log_addresses()`，HahaDog 补丁后增加了 4 个）。
- 我在服务器上用探针测过：两个 Ankr key 对多地址的 `getLogs`（20k 和 100k 块窗口）都正常，返回 54 条狗日志。
- 公共节点不行：官方 dataseed 对**所有** `eth_getLogs` 返回 `limit exceeded`（-32005），我本地测试里 publicnode 也拒绝多地址过滤器。
- `BSC_RPC_URLS` 里虽然列了 5 个节点（Ankr×2、publicnode、dataseed、defibit），但只有 Ankr 能承担 `getLogs`。如果两个 Ankr key 都限流或停服，索引器会停住（不会写错数据），公共节点救不了它。这是一个单点依赖，需要知道。
- 另一个新情况：今天起网站的 `/rpc/` 代理也用同一对 Ankr key（用户确认可以共用）。网站流量和索引器的轮询（约每 4–5 秒一批）现在共享 Ankr 的额度。我没测过 Ankr 免费档的具体上限，建议在 Ankr 控制台看一下用量并设置告警。
- 批量大小：Ankr 的批量 `eth_call` 上限是 100，超过 100 会返回 413 `Batch size too large`。站点 JS 目前不会超过。
- 回填窗口：`dog_backfill.py` 按 `range_blocks` 分段取日志，Ankr 窗口够大；如果以后换节点，要重新测一次。

### 5. 其他我注意到的
1. **重放时会长时间持锁。** `handle_reorg` 把所有 `raw_logs`（现在 5,603 条）在同一个事务里重放，`TRUNCATE` 带 ACCESS EXCLUSIVE 锁，期间 API 读这些表会被阻塞。现在量小没问题，`raw_logs` 变大后需要关注。
2. **重组误报的可能。** `check_reorg` 用当前选中的 RPC 返回的区块哈希对比。`BSC_RPC_URLS` 里有多个节点，如果某个节点短暂落后或在不同分叉上，可能误判成重组，触发整库重放。方案 A 修好后重放是安全的，只是代价大；建议只用同一类节点取这个哈希，或判断前复核一次。
3. **`Approval` 之外，狗的 `status` 在库里没有。** 库里存的是 `commit_block`、`rerolls`、`seed`，状态是 API 动态算的（`ready` / `generating` / `check`），所以第 3 点的 `stalled` 要么存表，要么 API 里额外读链。
4. **部署时我手动做了几件事**，下次部署记得：先应用 007 迁移（用 haha 角色）；root 用户做 `py_compile` 会在 `__pycache__` 里留下 root 属主的文件，我已经 `chown` 回 haha；部署前后都要 `stop`/`start` indexer，再 `restart` haha-api。
5. **测试覆盖。** 仓库里没有自动化的重组测试，`tests/dog_e2e.py` 里有一个强制重组的对比，但需要联网和临时库，当时为了跑通删掉了外键。方案 A 落地后，把这一步改成默认执行。

### 当前线上状态（供对照，2026-11-28 13:xx UTC+8）
- indexer 和 haha-api 都在运行，已同步到链上安全高度附近。
- 狗：已铸造 19，持有人 17，已有种子 17，挂单 0，成交 0，重铸 0。
- 与链上对比：19 只的持有人、提交区块、目标区块、重铸次数全部一致；17 个种子全部一致。
- 备份：`/root/backup-r2-20261128-0444`（含 `db.dump`、`nginx/`、`haha-indexer/`、`indexer.env`）。
