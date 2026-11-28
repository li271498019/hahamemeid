# 共享 schema

A、C、D 都读这一份。字段名以本文件和 [fixtures/](fixtures/) 为准。业务数字以 [../00-parameters.md](../00-parameters.md) 为准。这里没有生产代码。

## 名称对齐

[../02-module-abi.md](../02-module-abi.md) 的事件清单写了 `MintConfirmed`，同一文件的状态机段落写的是 `FulfillmentAttested`。两处不能同时实现。开工只发 `FulfillmentAttested`，字段为 `orderId`、合约内算出的 `tokenId`、`recipient`、`mintTxHash`。不要再发 `MintConfirmed`。这只消除文档里的两个名字，不改退款、价格或预算。

事故事件以 [../12-accident.md](../12-accident.md) 为准，补进索引，虽然 `02` 的事件清单没有逐条再列。

## 读 API

实现者是 A。挂在现有 `indexer/api.py` 的 GET 表上。进程仍只绑 `127.0.0.1:8787`。公网路径多一个 nginx 前缀 `/api`。现有 `do_POST` 返回 405，赛季路由继续只提供 GET，不发交易。

| 公网 | 索引器内部 | 样本 |
| --- | --- | --- |
| `GET /api/v1/season1/days/{dayIndex}` | `GET /v1/season1/days/{dayIndex}` | [fixtures/day.json](fixtures/day.json)、[fixtures/day-mismatch.json](fixtures/day-mismatch.json) |
| `GET /api/v1/season1/eligibility/{aiId}?day=` | 同上，去掉 `/api` | [fixtures/eligibility.json](fixtures/eligibility.json) |
| `GET /api/v1/season1/orders?day=` | 同上 | [fixtures/orders.json](fixtures/orders.json) |
| `GET /api/v1/season1/orders/{orderId}` | 同上 | [fixtures/orders.json](fixtures/orders.json) 的单条，或 [fixtures/order-log-mismatch.json](fixtures/order-log-mismatch.json) |
| `GET /api/v1/season1/verify/{aiId}?day=` | 同上 | [fixtures/verify.json](fixtures/verify.json) |
| `GET /api/v1/season1/findings/{reportEvidenceHash}` | 同上 | [fixtures/finding.json](fixtures/finding.json) |

`eligibility.status` 只取 `none`、`reserved`、`boundary`、`excluded`。`reason` 只取 `balance`、`pending`、`fulfilled`、`below-cutoff`，或者 `null`。`balance` 来自快照重放。`balanceNow` 是当前余额，页面必须分成两行。

订单 `status` 只取 `Pending`、`Fulfilled`、`CreditOpen`、`AccidentRefunded`、`AccidentClosed`。`logCheck` 只取 `matched`、`mismatch`、`unknown`、`not-minted`。`logCheck = mismatch` 时页面写「已声明，日志未核对」，不得写「已发放」。`simError` 只取 `null`、`name-taken`、`name-check-failed`。空列表 HTTP 200，未知订单 HTTP 404，正文 `{"error":"not_found"}`，与现有 `api.py` 的 404 相同。

`verify.points` 未领是 0，领到是 30。没有 100 万或 1000 万的字段。`queue = global-cap` 表示全网 `100000` 用尽，`claimed` 仍为 false。

敏感 finding 只有 `withheld: true` 和 `reportEvidenceHash`。不要返回报告正文、盐或用户身份。

## 事件

D 的合约发出，A 的 `indexer/common.py` 用源码签名计算 topic0，与现有事件的做法相同。C 不解码日志。

赛季事件名见 [fixtures/events.json](fixtures/events.json)。发放是否成立，还要同一笔交易里的旧 `NameMinted` 与 `Transfer(from = 0, to = 订单 recipient, tokenId = 订单 namehash)`。回执的 `to` 是 Registrar，不是接收人。

索引器确认深度保持现有的 3。快照锁定用 15，只写在 day 对象的 `confirmationsRequired`。

## D 交给 A

D 提交计划新增的 `tools/deploy-panel/public/season1/handoff.json`。在 ABI 导出完成前，这个文件不存在。

```json
{
  "kind": "season1-handoff",
  "specCommit": "<实现所依据的 docs commit>",
  "compiler": "0.8.28",
  "viaIr": true,
  "bytecodeBytes": 0,
  "split": false,
  "abiPath": "tools/deploy-panel/public/season1/HahaSeason1.abi.json",
  "events": [],
  "anvil": {"chainId": 31337, "module": null},
  "mainnet": {"chainId": 56, "module": null}
}
```

`events` 的每一项是 `{"name","signature","topic0"}`。`mainnet.module` 在管理员实际部署前保持 `null`。A 不把 anvil 地址写进主网配置。

## A 交给 C

A 不另给一套字段。C 先读 `docs/season1/kickoff/fixtures/`。A 的 PR 必须附一张表：每个夹具 id、对应 GET、实际 JSON 是否同键。缺这张表，C 不把页面从夹具改到 `/api`。

## 失败

[fixtures/failures.json](fixtures/failures.json) 的每一条都要有测试：D 用 Foundry 覆盖 `where = chain`，A 用索引器测试覆盖 `indexer` 和 `api`。C 只展示其中 `empty-orders`、`unknown-order`、`day-root-mismatch`、`order-log-mismatch` 的文案，不实现判断。
