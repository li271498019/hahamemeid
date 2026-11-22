# haha.meme API 文档 / API Reference

> 本文档为中英双语。中文在前，英文在后。
> This document is bilingual. Chinese first, English second.

- 基础地址 Base URL：`https://haha.meme/api`
- 无需鉴权 No auth
- 全部是 GET，返回 JSON All GET, JSON responses

---

# API 文档

## 概述

haha.meme 的公开 API 由链上索引器提供，只读。它返回索引器已经确认的数据：名字、挂单、成交、agent、信誉、评价、积分和全站统计。网站前端用的就是这套接口。共 14 个接口。

所有数据只覆盖已确认区块（`safeBlock` 之前），不会读到未确认的数据。接口不写链、不花 gas、不需要钱包、不需要鉴权。

## 通用规则

- 基础地址：`https://haha.meme/api`。索引器内部路由没有 `/api` 前缀，是 nginx 代理时去掉的。
- 全部是 GET。POST 返回 `405 {"error": "method_not_allowed"}`。未知路径返回 `404 {"error": "not_found"}`。
- `uint256`（tokenId、价格、积分）用十进制字符串表示，例如 `"1000000000000000000"`。
- 地址是小写 `0x` 开头，例如 `"0xe40a0c726fd2f990713ade7380c89800f4e8ac49"`。
- 时间是 UTC ISO-8601，带 `Z`，例如 `"2026-11-21T10:40:27Z"`。
- 分页：`limit` 默认 24，范围 1–50，超出范围返回 `400 {"error": "invalid_limit"}`。`cursor` 是不透明字符串，从上一页的 `nextCursor` 取；`nextCursor` 为 `null` 表示没有更多。`cursor` 非法返回 `400 {"error": "invalid_cursor"}`。
- 空列表返回 `200` 和 `"items": []`，不是 404。
- 缓存：列表接口 `Cache-Control: public, max-age=5, stale-while-revalidate=30`；名字接口 `max-age=2`；`/health` 是 `no-store`。
- `sort` 参数不在允许值里返回 `400 {"error": "invalid_sort"}`。

## 限流

nginx 按真实客户端 IP 限流（信任 Cloudflare 传来的 `CF-Connecting-IP`）。

- `/api/`（索引器接口）：每 IP 每分钟 60 次，突发 60 次。持续刷接口返回 HTTP `429`。
- `/rpc/`（链上代理）：每 IP 每分钟 120 次，突发 120 次。持续刷接口返回 HTTP `429`。

正常浏览永远碰不到上限：一次页面加载大约发起 10–20 次请求，数据看板每分钟刷新 2 次。收到 `429` 表示慢下来、一分钟后再试，限额会自动恢复。`429` 会出现在 nginx 访问日志里，便于监控。

## 接口

### 1. 健康检查 `GET /health`

索引器是否健康，`safeBlock` 和落后区块数。注意路径是 `/api/health`，不是 `/api/v1/health`。

无参数。

返回：

```json
{
  "ok": true,
  "chainId": 56,
  "safeBlock": 135053891,
  "headBlock": 135053897,
  "lagBlocks": 6,
  "lastError": null
}
```

- `ok`：`safeBlock` 存在且落后不超过 40 块时为 `true`。
- `chainId`：56（BNB Smart Chain 主网）。
- `safeBlock`：索引器已确认到的区块。
- `headBlock`：链上最新区块（可能为 `null`）。
- `lagBlocks`：`headBlock - safeBlock`（可能为 `null`）。
- `lastError`：最近的错误信息，无错误时为 `null`。

示例：

```bash
curl "https://haha.meme/api/health"
```

### 2. 挂单 `GET /v1/listings`

当前在售的挂单。

参数：

- `limit`：默认 24，1–50。
- `sort`：`listed_desc`（默认，按挂单时间倒序）、`price_asc`（价格升序）、`price_desc`（价格降序）。
- `tld`：`haha` 或 `meme`，只返回该后缀。
- `q`：完整小写 label 精确匹配，例如 `q=100`。
- `cursor`：翻页。

返回 `{"items": [...], "nextCursor": null}`，每条：

```json
{
  "tokenId": "45638555402845276256035622600195049773336184562353328036850768463344528991972",
  "label": "100",
  "tld": "haha",
  "fullName": "100.haha",
  "owner": "0xb70a19090ec0e0d3ddc0b9175855a0f8a5a9c7e6",
  "seller": "0xb70a19090ec0e0d3ddc0b9175855a0f8a5a9c7e6",
  "priceWei": "5000000000000000000",
  "listedAt": "2026-11-22T03:56:56Z",
  "blockNumber": 135010928,
  "txHash": "0x03cd207c73bc2b914cc36b6c98e0e9db89342bdd0b1de5f5a9236cd70d59dd68",
  "logIndex": 134
}
```

- `tokenId`、`priceWei` 是十进制字符串；`priceWei` 是挂单价（wei）。
- `owner` 是名字当前持有人，`seller` 是挂单人（通常相同）。
- `listedAt` 是挂单时间。

示例：

```bash
curl "https://haha.meme/api/v1/listings?sort=price_asc&limit=10"
curl "https://haha.meme/api/v1/listings?tld=haha&q=100"
```

### 3. 成交 `GET /v1/trades`

已成交的记录。

参数：

- `limit`：默认 24，1–50。
- `sort`：`time_desc`（默认，按成交时间倒序）、`price_desc`（价格降序）。
- `fullName`：完整名字精确匹配，例如 `fullName=eth.meme`。
- `cursor`：翻页。

返回 `{"items": [...], "nextCursor": null}`，每条：

```json
{
  "tokenId": "112795880771926957185220317260580333237292593424322340144671991331320700880776",
  "label": "eth",
  "tld": "meme",
  "fullName": "eth.meme",
  "seller": "0xe40a0c726fd2f990713ade7380c89800f4e8ac49",
  "buyer": "0x4382b3c643dcdd1cd9053099c4be27bc7f534f8d",
  "priceWei": "1000000000000000000",
  "feeWei": "10000000000000000",
  "proceedsWei": "990000000000000000",
  "tradedAt": "2026-11-22T09:00:00Z",
  "blockNumber": 135010000,
  "txHash": "0x0000000000000000000000000000000000000000000000000000000000000000",
  "logIndex": 0
}
```

- `feeWei` 是 1% 手续费，`proceedsWei` 是卖家实收（99%）。
- 成交为 0 时 `items` 为空数组。

示例：

```bash
curl "https://haha.meme/api/v1/trades?limit=10"
curl "https://haha.meme/api/v1/trades?fullName=eth.meme"
```

### 4. Agent 广场 `GET /v1/agents`

当前活跃的 agent（只返回 `active` 为 `true` 的）。

参数：

- `limit`：默认 24，1–50。
- `sort`：`activated_desc`（默认，按激活时间倒序）、`stars_desc`（按平均分降序）、`reviews_desc`（按评价数降序）。
- `cursor`：翻页。

返回 `{"items": [...], "nextCursor": null}`，每条：

```json
{
  "agentId": "1",
  "tokenId": "37842226382702054508022257179425071980608078361995167964553358493613992326712",
  "label": "tst1234",
  "tld": "haha",
  "fullName": "tst1234.haha",
  "owner": "0xe40a0c726fd2f990713ade7380c89800f4e8ac49",
  "operatorAiId": "0x17367f0410c1e90ee380b4a47be765a910dbf2be0db717b1da19e1d6f03670ed",
  "generation": 1,
  "agentURI": "https://haha.meme/agent.html?name=tst1234.haha",
  "active": true,
  "starsSum": 0,
  "starsCount": 0,
  "activatedAt": "2026-11-21T10:40:27Z",
  "blockNumber": 134872796
}
```

- `agentId`、`tokenId` 是十进制字符串；`generation` 是代数（首次激活为 1）。
- `operatorAiId` 是激活时操作人的 `.ai` 哈希（`0x` 32 字节），无操作人时为全零。
- `starsSum` / `starsCount` 是评分总和 / 评价数；平均分 = `starsSum / starsCount`。
- `agentURI` 是 agent 的介绍链接，可能为 `null`。

示例：

```bash
curl "https://haha.meme/api/v1/agents?sort=stars_desc&limit=10"
```

### 5. 信誉榜 `GET /v1/leaderboard/reputation`

按平均分排序的信誉榜，只含活跃 agent。

参数：

- `limit`：默认 24，1–50。
- `sort`：只有 `stars_desc`。
- `minReviews`：最少评价数，默认 1，范围 1–20。超出范围返回 `400 {"error": "invalid_minReviews"}`。
- `cursor`：翻页。

返回 `{"items": [...], "nextCursor": null}`，每条与 agent 相同，另加 `rank`（从 1 起，跨页连续）。

示例：

```bash
curl "https://haha.meme/api/v1/leaderboard/reputation?minReviews=1&limit=10"
```

### 6. 最新评价 `GET /v1/reviews/latest`

全站最新评价，按评价时间倒序。

参数：

- `limit`：默认 24，1–50。

返回 `{"items": [...], "nextCursor": null}`。注意这个接口没有翻页，`nextCursor` 恒为 `null`。每条：

```json
{
  "fullName": "eth.meme",
  "agentId": "24",
  "generation": 1,
  "rater": "0xe40a0c726fd2f990713ade7380c89800f4e8ac49",
  "raterAiId": "0x17367f0410c1e90ee380b4a47be765a910dbf2be0db717b1da19e1d6f03670ed",
  "raterAi": "hahameme.ai",
  "raterName": "tst1234.haha",
  "stars": 5,
  "review": "链上新身份",
  "edited": false,
  "ratedAt": "2026-11-22T01:33:16Z",
  "txHash": "0x44a4d8974d1fc6b1d8c0fb938c0ac9bf294c3cbd4b9b694083cfb5ecce7f6b1f"
}
```

- `raterAi` 是评价人的 `.ai`（带 `.ai` 后缀），无 `.ai` 时为 `null`。
- `raterName` 是评价人最早铸的 haha id，无时为 `null`。
- `review` 是评语原文（最长 140 字节），`edited` 表示是否改过。

示例：

```bash
curl "https://haha.meme/api/v1/reviews/latest?limit=5"
```

### 7. 历代 `GET /v1/names/{fullName}/generations`

一个名字的全部历代 agent 和每一代的评价。

路径参数：`fullName`，例如 `tst1234.haha`（小写字母数字 1–32 位 + `.haha` 或 `.meme`）。名字从未铸出返回 `404 {"error": "not_found"}`。

返回：

```json
{
  "fullName": "tst1234.haha",
  "tokenId": "37842226382702054508022257179425071980608078361995167964553358493613992326712",
  "generations": [
    {
      "generation": 1,
      "agentId": "1",
      "active": true,
      "owner": "0xe40a0c726fd2f990713ade7380c89800f4e8ac49",
      "agentURI": "https://haha.meme/agent.html?name=tst1234.haha",
      "starsSum": 0,
      "starsCount": 0,
      "activatedAt": "2026-11-21T10:40:27Z",
      "resetAt": null,
      "reviewsTruncated": false,
      "reviews": []
    }
  ]
}
```

- `generations` 按代数倒序（最新一代在前）。名字铸出过但从未激活时为 `[]`。
- 每代最多返回 100 条评价，超过时 `reviewsTruncated` 为 `true`。
- `resetAt` 是 agent 被销毁（转让）的时间，活跃代为 `null`。

示例：

```bash
curl "https://haha.meme/api/v1/names/tst1234.haha/generations"
```

### 8. 名字 `GET /v1/names/{fullName}`

查一个名字是否已铸、持有人和挂单。

路径参数：`fullName`，例如 `eth.meme`。格式不对返回 `400 {"error": "invalid_name"}`。

已铸返回：

```json
{
  "fullName": "eth.meme",
  "minted": true,
  "tokenId": "112795880771926957185220317260580333237292593424322340144671991331320700880776",
  "label": "eth",
  "tld": "meme",
  "owner": "0x051da872b39a1f1a7f6ab8b4c0a4a18f69b34749",
  "mintedAt": "2026-11-21T13:23:20Z",
  "listing": null
}
```

未铸返回 HTTP 200（不是 404），`minted` 为 `false`，其余为 `null`：

```json
{
  "fullName": "abc.haha",
  "minted": false,
  "tokenId": null,
  "label": "abc",
  "tld": "haha",
  "owner": null,
  "mintedAt": null,
  "listing": null
}
```

- `listing` 未挂单时为 `null`。用 `minted` 区分“没铸”和“接口挂了”。

示例：

```bash
curl "https://haha.meme/api/v1/names/eth.meme"
curl "https://haha.meme/api/v1/names/abc.haha"
```

### 9. 名下名字 `GET /v1/owners/{address}/names`

一个钱包地址名下的全部名字（最多 200 个，按铸造时间倒序）。

路径参数：`address`，`0x` + 40 位十六进制，例如 `0xe40a0c726fd2f990713ade7380c89800f4e8ac49`。格式不对返回 `400 {"error": "invalid_address"}`。

返回：

```json
{
  "owner": "0xe40a0c726fd2f990713ade7380c89800f4e8ac49",
  "items": [
    {
      "fullName": "tst1234.haha",
      "minted": true,
      "tokenId": "37842226382702054508022257179425071980608078361995167964553358493613992326712",
      "label": "tst1234",
      "tld": "haha",
      "owner": "0xe40a0c726fd2f990713ade7380c89800f4e8ac49",
      "mintedAt": "2026-11-21T09:20:28Z",
      "listing": null
    }
  ]
}
```

- 每条与第 8 节的名字形状相同。钱包没有名字时 `items` 为空数组。
- 这是钱包集成查名下 NFT 的入口。

示例：

```bash
curl "https://haha.meme/api/v1/owners/0xe40a0c726fd2f990713ade7380c89800f4e8ac49/names"
```

### 10. 积分榜 `GET /v1/leaderboard/points`

按积分排序的榜单。注意路径是 `/v1/leaderboard/points`，没有 `/v1/points` 这个接口。

参数：

- `limit`：默认 24，1–50。
- `sort`：只有 `balance_desc`。
- `cursor`：翻页。

返回 `{"items": [...], "nextCursor": null}`，每条：

```json
{
  "rank": 1,
  "aiId": "0x125d1c43a5d98fc53df5441690e3e712e696fa3eaca2da1c55334ece6b097aaf",
  "handle": "1122",
  "name": "cat.meme",
  "balance": "235",
  "updatedAt": "2026-11-22T04:01:39Z"
}
```

- 只含积分大于 0 的 `.ai`；`rank` 从 1 起，跨页连续。
- `handle` 是 `.ai` 的原始 handle（不带 `.ai` 后缀）。
- `name` 是该 `.ai` 最早铸的 haha id，无时为 `null`。
- `balance` 是积分余额（十进制字符串）。

示例：

```bash
curl "https://haha.meme/api/v1/leaderboard/points?limit=10"
```

### 11. 数据看板 `GET /v1/stats`

全站统计，一次返回，不分页。

无参数。

返回：

```json
{
  "participants": 327,
  "activeAgents": 28,
  "totalActivations": 28,
  "registered": {"haha": 366, "meme": 179, "total": 545},
  "threeDigit": {
    "total": 1000, "reserved": 0, "blacklisted": 0,
    "haha": {"minted": 87, "remaining": 913},
    "meme": {"minted": 24, "remaining": 976}
  },
  "threeLetter": {
    "total": 17576, "reserved": 2, "blacklisted": 7,
    "haha": {"minted": 34, "remaining": 17533},
    "meme": {"minted": 45, "remaining": 17522}
  },
  "latest": [
    {
      "fullName": "730.haha",
      "label": "730",
      "tld": "haha",
      "mintedAt": "2026-11-22T09:24:43Z",
      "blockNumber": 135054624
    }
  ],
  "market": {
    "listings": 11,
    "floorPriceWei": "1000000000000000000",
    "latestTradePriceWei": null,
    "volume24hWei": "0"
  },
  "safeBlock": 135053891
}
```

- `participants`：参与的 `.ai` 数（去重）。
- `activeAgents`：当前活跃 agent 数；`totalActivations`：累计激活数（含已销毁的代）。
- `threeDigit` / `threeLetter`：3 位纯数字 / 3 位纯字母的剩余，剩余 = 总量 − 已注册 − 保留 − 黑名单。纯数字总量 1000（保留 0、黑名单 0），纯字母总量 17576（保留 2、黑名单 7）。
- `latest`：最新 20 个铸造。
- `market.floorPriceWei` 无挂单时为 `null`；`latestTradePriceWei` 无成交时为 `null`；`volume24hWei` 是 24 小时成交量（wei 字符串）。
- `safeBlock`：这些数字覆盖到的区块。

示例：

```bash
curl "https://haha.meme/api/v1/stats"
```

### 12. 主名反查 `GET /v1/owners/{address}/primary`

输钱包地址，返回它的主名。这是钱包集成显示名字而不是地址的入口。

路径参数：`address`，`0x` + 40 位十六进制，例如 `0xe40a0c726fd2f990713ade7380c89800f4e8ac49`。格式不对不匹配这条路由，返回 `404`。

返回：

```json
{
  "owner": "0xe40a0c726fd2f990713ade7380c89800f4e8ac49",
  "primaryName": "tst1234.haha"
}
```

- `primaryName` 没有主名时为 `null`。
- 主名是直接读链上 `HahaResolver.primaryName` 的，永远是当前值；链上读失败返回 `502 {"error": "upstream_unavailable"}`。

示例：

```bash
curl "https://haha.meme/api/v1/owners/0xe40a0c726fd2f990713ade7380c89800f4e8ac49/primary"
```

### 13. NFT 图片 `GET /v1/names/{fullName}/image.svg`

一个名字的 NFT 图片，就是链上的 SVG。返回的不是 JSON，是 `image/svg+xml`。

路径参数：`fullName`，例如 `tst1234.haha`。名字从未铸出返回 `404 {"error": "not_found"}`。

图片由索引器在本地生成，用的是 `HahaMetadata.buildSvgOnly` 的逐字节一致的 Python 实现，和链上 SVG 完全一样。

示例：

```bash
curl "https://haha.meme/api/v1/names/tst1234.haha/image.svg"
```

缓存：`Cache-Control: public, max-age=14400, stale-while-revalidate=86400`。

### 14. NFT metadata `GET /v1/names/{fullName}/metadata`

一个名字的 NFT metadata，标准 tokenURI 风格的 JSON。返回 `application/json`。

路径参数：`fullName`，例如 `tst1234.haha`。名字从未铸出返回 `404`。

返回：

```json
{
  "name": "tst1234.haha",
  "description": "haha.meme agent identity for tst1234.haha",
  "image": "https://haha.meme/api/v1/names/tst1234.haha/image.svg",
  "attributes": [
    {"trait_type": "TLD", "value": "haha"},
    {"trait_type": "Length", "display_type": "number", "value": 7}
  ]
}
```

- 和链上 `HahaMetadata.buildJson` 的形状一样，只是 `image` 是指向上面的 `/image.svg` 接口的 HTTP 地址，而不是 data URI。
- 说清楚一点：这个接口**不能**让标准钱包自动显示 NFT，因为 `HahaRegistrar` 没有 `tokenURI`（V1 合约的限制，不可升级）。它只能供主动集成的开发者、钱包和市场用，显式调这个接口才能拿到名字和图片。

示例：

```bash
curl "https://haha.meme/api/v1/names/tst1234.haha/metadata"
```

## 错误

| HTTP | `error` | 说明 |
| --- | --- | --- |
| 400 | `invalid_limit` | `limit` 不是整数，或不在 1–50。 |
| 400 | `invalid_sort` | `sort` 不在允许值里。 |
| 400 | `invalid_cursor` | `cursor` 非法。 |
| 400 | `invalid_tld` | `tld` 不是 `haha` 或 `meme`。 |
| 400 | `invalid_name` | 名字格式不对（须为 1–32 位小写字母数字 + `.haha` / `.meme`）。 |
| 400 | `invalid_minReviews` | `minReviews` 不是整数，或不在 1–20。 |
| 400 | `invalid_address` | 地址不是 `0x` + 40 位十六进制。 |
| 404 | `not_found` | 路径不存在；或历代接口查了一个从未铸出的名字。 |
| 405 | `method_not_allowed` | 只支持 GET。 |
| 429 | — | 请求过多，等 `Retry-After` 后再试。 |
| 500 | `internal` | 服务器内部错误。 |

## 说明

之前计划中的两个接口已经上线：主名反查（第 12 节）和 NFT metadata（第 14 节）。还有一个限制要说清楚：metadata 接口**不能**让标准钱包自动显示 NFT，因为 `HahaRegistrar` 没有 `tokenURI`（V1 合约的限制，不可升级，改要重部署）。它只能供主动集成的开发者用，钱包和市场要显式调这个接口才能拿到图片。

## 链接

- 网站：https://haha.meme
- X：https://x.com/aihahameme
- Telegram：https://t.me/aihahameme
- 公开库：https://github.com/li271498019/hahamemeid
- 白皮书：[WHITEPAPER.md](WHITEPAPER.md)
- 工作原理：[HOW_IT_WORKS.md](HOW_IT_WORKS.md)
- 架构：[ARCHITECTURE.md](ARCHITECTURE.md)

---

# API Reference

## Overview

The haha.meme public API is served by the on-chain indexer. It is read-only and returns data the indexer has already confirmed: names, listings, trades, agents, reputation, reviews, points, and site-wide stats. The website frontend uses this same API. 14 endpoints in total.

All data covers confirmed blocks only (up to `safeBlock`). Nothing here reads unconfirmed data. The API does not write to the chain, costs no gas, needs no wallet, and needs no auth.

## Conventions

- Base URL: `https://haha.meme/api`. The indexer routes have no `/api` prefix; nginx strips it when proxying.
- All GET. POST returns `405 {"error": "method_not_allowed"}`. An unknown path returns `404 {"error": "not_found"}`.
- `uint256` values (tokenId, prices, points) are decimal strings, e.g. `"1000000000000000000"`.
- Addresses are lowercase `0x`, e.g. `"0xe40a0c726fd2f990713ade7380c89800f4e8ac49"`.
- Times are UTC ISO-8601 with `Z`, e.g. `"2026-11-21T10:40:27Z"`.
- Paging: `limit` defaults to 24, range 1–50; out of range returns `400 {"error": "invalid_limit"}`. `cursor` is an opaque string taken from the previous page's `nextCursor`; `nextCursor` of `null` means no more pages. An invalid `cursor` returns `400 {"error": "invalid_cursor"}`.
- An empty list returns `200` with `"items": []`, not 404.
- Caching: list endpoints `Cache-Control: public, max-age=5, stale-while-revalidate=30`; name endpoints `max-age=2`; `/health` is `no-store`.
- A `sort` value outside the allowed set returns `400 {"error": "invalid_sort"}`.

## Rate limits

nginx rate-limits per real client IP (Cloudflare's `CF-Connecting-IP` is trusted via nginx `real_ip`).

- `/api/` (indexer API): 60 requests/minute per IP, burst 60. Sustained floods get HTTP `429`.
- `/rpc/` (chain proxy): 120 requests/minute per IP, burst 120. Sustained floods get HTTP `429`.

Normal browsing never hits the limit: a page load makes about 10–20 calls, and the stats board refreshes twice a minute. A `429` means slow down and retry after a minute; the limit refills automatically. `429`s appear in the nginx access log for monitoring.

## Endpoints

### 1. Health `GET /health`

Whether the indexer is healthy, with `safeBlock` and lag in blocks. Note the path is `/api/health`, not `/api/v1/health`.

No parameters.

Response:

```json
{
  "ok": true,
  "chainId": 56,
  "safeBlock": 135053891,
  "headBlock": 135053897,
  "lagBlocks": 6,
  "lastError": null
}
```

- `ok`: `true` when `safeBlock` exists and lag is at most 40 blocks.
- `chainId`: 56 (BNB Smart Chain mainnet).
- `safeBlock`: the block the indexer has confirmed up to.
- `headBlock`: the latest chain block (may be `null`).
- `lagBlocks`: `headBlock - safeBlock` (may be `null`).
- `lastError`: the latest error message, or `null`.

Example:

```bash
curl "https://haha.meme/api/health"
```

### 2. Listings `GET /v1/listings`

Listings currently for sale.

Parameters:

- `limit`: default 24, 1–50.
- `sort`: `listed_desc` (default, newest listed first), `price_asc` (price ascending), `price_desc` (price descending).
- `tld`: `haha` or `meme`, to filter by suffix.
- `q`: exact match on the full lowercase label, e.g. `q=100`.
- `cursor`: paging.

Response `{"items": [...], "nextCursor": null}`, each item:

```json
{
  "tokenId": "45638555402845276256035622600195049773336184562353328036850768463344528991972",
  "label": "100",
  "tld": "haha",
  "fullName": "100.haha",
  "owner": "0xb70a19090ec0e0d3ddc0b9175855a0f8a5a9c7e6",
  "seller": "0xb70a19090ec0e0d3ddc0b9175855a0f8a5a9c7e6",
  "priceWei": "5000000000000000000",
  "listedAt": "2026-11-22T03:56:56Z",
  "blockNumber": 135010928,
  "txHash": "0x03cd207c73bc2b914cc36b6c98e0e9db89342bdd0b1de5f5a9236cd70d59dd68",
  "logIndex": 134
}
```

- `tokenId` and `priceWei` are decimal strings; `priceWei` is the listing price in wei.
- `owner` is the current name holder, `seller` is the lister (usually the same).
- `listedAt` is when the listing was created.

Examples:

```bash
curl "https://haha.meme/api/v1/listings?sort=price_asc&limit=10"
curl "https://haha.meme/api/v1/listings?tld=haha&q=100"
```

### 3. Trades `GET /v1/trades`

Completed trades.

Parameters:

- `limit`: default 24, 1–50.
- `sort`: `time_desc` (default, newest trade first), `price_desc` (price descending).
- `fullName`: exact full name match, e.g. `fullName=eth.meme`.
- `cursor`: paging.

Response `{"items": [...], "nextCursor": null}`, each item:

```json
{
  "tokenId": "112795880771926957185220317260580333237292593424322340144671991331320700880776",
  "label": "eth",
  "tld": "meme",
  "fullName": "eth.meme",
  "seller": "0xe40a0c726fd2f990713ade7380c89800f4e8ac49",
  "buyer": "0x4382b3c643dcdd1cd9053099c4be27bc7f534f8d",
  "priceWei": "1000000000000000000",
  "feeWei": "10000000000000000",
  "proceedsWei": "990000000000000000",
  "tradedAt": "2026-11-22T09:00:00Z",
  "blockNumber": 135010000,
  "txHash": "0x0000000000000000000000000000000000000000000000000000000000000000",
  "logIndex": 0
}
```

- `feeWei` is the 1% fee, `proceedsWei` is what the seller received (99%).
- When there are no trades yet, `items` is an empty array.

Examples:

```bash
curl "https://haha.meme/api/v1/trades?limit=10"
curl "https://haha.meme/api/v1/trades?fullName=eth.meme"
```

### 4. Agents `GET /v1/agents`

Currently active agents (only `active` ones are returned).

Parameters:

- `limit`: default 24, 1–50.
- `sort`: `activated_desc` (default, newest activation first), `stars_desc` (average rating descending), `reviews_desc` (review count descending).
- `cursor`: paging.

Response `{"items": [...], "nextCursor": null}`, each item:

```json
{
  "agentId": "1",
  "tokenId": "37842226382702054508022257179425071980608078361995167964553358493613992326712",
  "label": "tst1234",
  "tld": "haha",
  "fullName": "tst1234.haha",
  "owner": "0xe40a0c726fd2f990713ade7380c89800f4e8ac49",
  "operatorAiId": "0x17367f0410c1e90ee380b4a47be765a910dbf2be0db717b1da19e1d6f03670ed",
  "generation": 1,
  "agentURI": "https://haha.meme/agent.html?name=tst1234.haha",
  "active": true,
  "starsSum": 0,
  "starsCount": 0,
  "activatedAt": "2026-11-21T10:40:27Z",
  "blockNumber": 134872796
}
```

- `agentId` and `tokenId` are decimal strings; `generation` is the generation number (1 on first activation).
- `operatorAiId` is the `.ai` hash of the operator recorded at activation (32-byte `0x`), all zeros when there was no operator.
- `starsSum` / `starsCount` are the rating sum / review count; average = `starsSum / starsCount`.
- `agentURI` is the agent's introduction link, possibly `null`.

Example:

```bash
curl "https://haha.meme/api/v1/agents?sort=stars_desc&limit=10"
```

### 5. Reputation leaderboard `GET /v1/leaderboard/reputation`

The reputation board, sorted by average rating, active agents only.

Parameters:

- `limit`: default 24, 1–50.
- `sort`: only `stars_desc`.
- `minReviews`: minimum review count, default 1, range 1–20. Out of range returns `400 {"error": "invalid_minReviews"}`.
- `cursor`: paging.

Response `{"items": [...], "nextCursor": null}`. Each item is the same shape as an agent, plus `rank` (starting at 1, continuous across pages).

Example:

```bash
curl "https://haha.meme/api/v1/leaderboard/reputation?minReviews=1&limit=10"
```

### 6. Latest reviews `GET /v1/reviews/latest`

The newest reviews across the site, latest first.

Parameters:

- `limit`: default 24, 1–50.

Response `{"items": [...], "nextCursor": null}`. Note this endpoint has no paging; `nextCursor` is always `null`. Each item:

```json
{
  "fullName": "eth.meme",
  "agentId": "24",
  "generation": 1,
  "rater": "0xe40a0c726fd2f990713ade7380c89800f4e8ac49",
  "raterAiId": "0x17367f0410c1e90ee380b4a47be765a910dbf2be0db717b1da19e1d6f03670ed",
  "raterAi": "hahameme.ai",
  "raterName": "tst1234.haha",
  "stars": 5,
  "review": "链上新身份",
  "edited": false,
  "ratedAt": "2026-11-22T01:33:16Z",
  "txHash": "0x44a4d8974d1fc6b1d8c0fb938c0ac9bf294c3cbd4b9b694083cfb5ecce7f6b1f"
}
```

- `raterAi` is the rater's `.ai` (with the `.ai` suffix), `null` when they have none.
- `raterName` is the rater's earliest minted haha id, `null` when there is none.
- `review` is the review text (at most 140 bytes); `edited` says whether it was changed.

Example:

```bash
curl "https://haha.meme/api/v1/reviews/latest?limit=5"
```

### 7. Generations `GET /v1/names/{fullName}/generations`

All generations of one name, with each generation's reviews.

Path parameter: `fullName`, e.g. `tst1234.haha` (1–32 lowercase letters/digits + `.haha` or `.meme`). A name that was never minted returns `404 {"error": "not_found"}`.

Response:

```json
{
  "fullName": "tst1234.haha",
  "tokenId": "37842226382702054508022257179425071980608078361995167964553358493613992326712",
  "generations": [
    {
      "generation": 1,
      "agentId": "1",
      "active": true,
      "owner": "0xe40a0c726fd2f990713ade7380c89800f4e8ac49",
      "agentURI": "https://haha.meme/agent.html?name=tst1234.haha",
      "starsSum": 0,
      "starsCount": 0,
      "activatedAt": "2026-11-21T10:40:27Z",
      "resetAt": null,
      "reviewsTruncated": false,
      "reviews": []
    }
  ]
}
```

- `generations` is ordered by generation descending (newest first). A name that was minted but never activated returns `[]`.
- At most 100 reviews are returned per generation; `reviewsTruncated` is `true` when there are more.
- `resetAt` is when the agent was destroyed (on transfer); it is `null` for the active generation.

Example:

```bash
curl "https://haha.meme/api/v1/names/tst1234.haha/generations"
```

### 8. Name `GET /v1/names/{fullName}`

Whether one name is minted, who owns it, and its listing.

Path parameter: `fullName`, e.g. `eth.meme`. A bad format returns `400 {"error": "invalid_name"}`.

Minted, returns:

```json
{
  "fullName": "eth.meme",
  "minted": true,
  "tokenId": "112795880771926957185220317260580333237292593424322340144671991331320700880776",
  "label": "eth",
  "tld": "meme",
  "owner": "0x051da872b39a1f1a7f6ab8b4c0a4a18f69b34749",
  "mintedAt": "2026-11-21T13:23:20Z",
  "listing": null
}
```

Unminted, returns HTTP 200 (not 404) with `minted` `false` and the rest `null`:

```json
{
  "fullName": "abc.haha",
  "minted": false,
  "tokenId": null,
  "label": "abc",
  "tld": "haha",
  "owner": null,
  "mintedAt": null,
  "listing": null
}
```

- `listing` is `null` when the name is not listed. Use `minted` to tell "not minted" apart from "the API is down".

Example:

```bash
curl "https://haha.meme/api/v1/names/eth.meme"
curl "https://haha.meme/api/v1/names/abc.haha"
```

### 9. Names by owner `GET /v1/owners/{address}/names`

All names owned by one wallet address (at most 200, newest minted first).

Path parameter: `address`, `0x` + 40 hex characters, e.g. `0xe40a0c726fd2f990713ade7380c89800f4e8ac49`. A bad format returns `400 {"error": "invalid_address"}`.

Response:

```json
{
  "owner": "0xe40a0c726fd2f990713ade7380c89800f4e8ac49",
  "items": [
    {
      "fullName": "tst1234.haha",
      "minted": true,
      "tokenId": "37842226382702054508022257179425071980608078361995167964553358493613992326712",
      "label": "tst1234",
      "tld": "haha",
      "owner": "0xe40a0c726fd2f990713ade7380c89800f4e8ac49",
      "mintedAt": "2026-11-21T09:20:28Z",
      "listing": null
    }
  ]
}
```

- Each item has the same shape as the name endpoint in §8. A wallet with no names returns an empty `items` array.
- This is the entry point for a wallet integration to list a user's haha.meme NFTs.

Example:

```bash
curl "https://haha.meme/api/v1/owners/0xe40a0c726fd2f990713ade7380c89800f4e8ac49/names"
```

### 10. Points leaderboard `GET /v1/leaderboard/points`

The points board, sorted by balance. Note the path is `/v1/leaderboard/points`; there is no `/v1/points` endpoint.

Parameters:

- `limit`: default 24, 1–50.
- `sort`: only `balance_desc`.
- `cursor`: paging.

Response `{"items": [...], "nextCursor": null}`, each item:

```json
{
  "rank": 1,
  "aiId": "0x125d1c43a5d98fc53df5441690e3e712e696fa3eaca2da1c55334ece6b097aaf",
  "handle": "1122",
  "name": "cat.meme",
  "balance": "235",
  "updatedAt": "2026-11-22T04:01:39Z"
}
```

- Only `.ai` identities with a balance above 0 are included; `rank` starts at 1 and is continuous across pages.
- `handle` is the `.ai` handle without the `.ai` suffix.
- `name` is that `.ai`'s earliest minted haha id, `null` when there is none.
- `balance` is the points balance (decimal string).

Example:

```bash
curl "https://haha.meme/api/v1/leaderboard/points?limit=10"
```

### 11. Stats `GET /v1/stats`

Site-wide stats in one object, no paging.

No parameters.

Response:

```json
{
  "participants": 327,
  "activeAgents": 28,
  "totalActivations": 28,
  "registered": {"haha": 366, "meme": 179, "total": 545},
  "threeDigit": {
    "total": 1000, "reserved": 0, "blacklisted": 0,
    "haha": {"minted": 87, "remaining": 913},
    "meme": {"minted": 24, "remaining": 976}
  },
  "threeLetter": {
    "total": 17576, "reserved": 2, "blacklisted": 7,
    "haha": {"minted": 34, "remaining": 17533},
    "meme": {"minted": 45, "remaining": 17522}
  },
  "latest": [
    {
      "fullName": "730.haha",
      "label": "730",
      "tld": "haha",
      "mintedAt": "2026-11-22T09:24:43Z",
      "blockNumber": 135054624
    }
  ],
  "market": {
    "listings": 11,
    "floorPriceWei": "1000000000000000000",
    "latestTradePriceWei": null,
    "volume24hWei": "0"
  },
  "safeBlock": 135053891
}
```

- `participants`: the number of participating `.ai` identities (distinct).
- `activeAgents`: currently active agents; `totalActivations`: cumulative activations (including destroyed generations).
- `threeDigit` / `threeLetter`: remaining 3-digit numeric / 3-letter names, where remaining = total − registered − reserved − blacklisted. Numeric total is 1000 (reserved 0, blacklisted 0); letter total is 17576 (reserved 2, blacklisted 7).
- `latest`: the 20 most recent mints.
- `market.floorPriceWei` is `null` with no listings; `latestTradePriceWei` is `null` with no trades; `volume24hWei` is 24-hour volume in wei (string).
- `safeBlock`: the block these numbers cover.

Example:

```bash
curl "https://haha.meme/api/v1/stats"
```

### 12. Primary name `GET /v1/owners/{address}/primary`

Given a wallet address, return its primary name. This is the entry point for a wallet integration to display a name instead of an address.

Path parameter: `address`, `0x` + 40 hex characters, e.g. `0xe40a0c726fd2f990713ade7380c89800f4e8ac49`. A malformed address does not match this route and returns `404`.

Response:

```json
{
  "owner": "0xe40a0c726fd2f990713ade7380c89800f4e8ac49",
  "primaryName": "tst1234.haha"
}
```

- `primaryName` is `null` when the address has no primary name.
- The primary name is read directly from `HahaResolver.primaryName` on-chain, so it is always current; an on-chain read failure returns `502 {"error": "upstream_unavailable"}`.

Example:

```bash
curl "https://haha.meme/api/v1/owners/0xe40a0c726fd2f990713ade7380c89800f4e8ac49/primary"
```

### 13. NFT image `GET /v1/names/{fullName}/image.svg`

The NFT image for one name — the on-chain SVG. The response is not JSON; it is `image/svg+xml`.

Path parameter: `fullName`, e.g. `tst1234.haha`. A name that was never minted returns `404 {"error": "not_found"}`.

The image is generated locally by the indexer from a byte-identical Python port of `HahaMetadata.buildSvgOnly`, so it is exactly the on-chain SVG.

Example:

```bash
curl "https://haha.meme/api/v1/names/tst1234.haha/image.svg"
```

Cache: `Cache-Control: public, max-age=14400, stale-while-revalidate=86400`.

### 14. NFT metadata `GET /v1/names/{fullName}/metadata`

NFT metadata for one name, standard tokenURI-style JSON. Returns `application/json`.

Path parameter: `fullName`, e.g. `tst1234.haha`. A name that was never minted returns `404`.

Response:

```json
{
  "name": "tst1234.haha",
  "description": "haha.meme agent identity for tst1234.haha",
  "image": "https://haha.meme/api/v1/names/tst1234.haha/image.svg",
  "attributes": [
    {"trait_type": "TLD", "value": "haha"},
    {"trait_type": "Length", "display_type": "number", "value": 7}
  ]
}
```

- The shape matches the on-chain `HahaMetadata.buildJson`, except `image` is an HTTP URL pointing to the `/image.svg` endpoint above instead of a data URI.
- To be plain: this endpoint **cannot** make standard wallets display the NFT automatically, because `HahaRegistrar` has no `tokenURI` (a V1 contract limitation, immutable). It is only for developers, wallets, and marketplaces that integrate explicitly and call this endpoint directly to get the name and image.

Example:

```bash
curl "https://haha.meme/api/v1/names/tst1234.haha/metadata"
```

## Errors

| HTTP | `error` | Meaning |
| --- | --- | --- |
| 400 | `invalid_limit` | `limit` is not an integer, or outside 1–50. |
| 400 | `invalid_sort` | `sort` is not one of the allowed values. |
| 400 | `invalid_cursor` | `cursor` is invalid. |
| 400 | `invalid_tld` | `tld` is not `haha` or `meme`. |
| 400 | `invalid_name` | Bad name format (must be 1–32 lowercase letters/digits + `.haha` / `.meme`). |
| 400 | `invalid_minReviews` | `minReviews` is not an integer, or outside 1–20. |
| 400 | `invalid_address` | Address is not `0x` + 40 hex characters. |
| 404 | `not_found` | Path does not exist; or the generations endpoint was given a name that was never minted. |
| 405 | `method_not_allowed` | GET only. |
| 429 | — | Too many requests; wait for `Retry-After` and retry. |
| 500 | `internal` | Server error. |

## Note

The two previously planned endpoints are live now: primary-name reverse lookup (section 12) and NFT metadata (section 14). One limitation remains: the metadata endpoint **cannot** make standard wallets display the NFT automatically, because `HahaRegistrar` has no `tokenURI` (a V1 contract limitation, immutable — fixing it needs a redeploy). It is only for developers who integrate explicitly; wallets and marketplaces have to call this endpoint directly to get the image.

## Links

- Website: https://haha.meme
- X: https://x.com/aihahameme
- Telegram: https://t.me/aihahameme
- Public repo: https://github.com/li271498019/hahamemeid
- Whitepaper: [WHITEPAPER.md](WHITEPAPER.md)
- How it works: [HOW_IT_WORKS.md](HOW_IT_WORKS.md)
- Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
