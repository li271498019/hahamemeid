# V1 索引器规格

给网站开发 C。只描述索引器和它的 HTTP API。不改网站页面、合约或测试。网站怎么分阶段接这个 API，见 `docs/website/V1-LAUNCH-REQUIREMENTS.md` 的「分期」。

链是 BNB Smart Chain 主网，chainId `56`。起点区块 **134834631**（`HahaNamePolicy` 的部署块）。扫到链头再减去确认深度。地址以 `docs/contracts/DEPLOYED.md` 为准。事件签名以 `src/` 为准。`docs/contracts/INDEXING.md` 第 7.3 节写了 `GameRegistered`，并且给 `RoundClaimed` 多写了 `player`。源码里没有这两个形状。以本文下面的签名为准。

不要把服务器 IP、数据库口令、RPC 密钥写进仓库。连接串放在服务器上的环境文件里，例如 `/etc/haha/indexer.env`，权限 `0600`。

## 要索引的合约

| 合约 | 地址 | 从哪一块开始有日志 |
| --- | --- | --- |
| HahaNamePolicy | `0x1F260aa05334f76A6E1d6Fbd416F4d07d6Bf3d96` | 134834631 |
| HahaMetadata | `0x790B670D664Ea0046b0F2D395C182AdD3C389aB4` | 无自定义事件 |
| HahaResolver | `0x85C2DbdFd81A14B958B360159e8710E6c15370D6` | 134834683 |
| HahaRegistry | `0x712Ca65E2F6F5436C846569949072C8941982987` | 134834708 |
| HahaRegistrar | `0x43426E37a31AafDaba851858e34B81DC300650F8` | 134834735 |
| HahaAgentIdentity | `0x54A70BF81B288d41013D7b57c2Db0922f1E1a4d4` | 134834759 |
| HahaPoints | `0xB2D023b8B5895835EFD71C1150BeAD7bD735DfAa` | 134834780 |
| HahaReputation | `0xf1A41B30d0c03fE178D3d76CBE6044E9D5Ce1800` | 134834803 |
| HahaMarketplace | `0xC7294DF776344A39726b4C1256Faf0e728c99835` | 134834824 |
| HahaDeployer | `0x3c7Bd1649ac03AfB65e6E10F949f45d764B6b601` | 无自定义事件 |

统一从 134834631 拉日志，按地址过滤上面十个合约。没有事件的两个合约会一直是空的，这是正常的。不要去索引整个币安 `.ai` 注册表。积分榜上的名字用下文的按需 `eth_call`。

积分模块的 `setEarner` 在 134837848（`REVIEW_GIVE`）、134837901（`REVIEW_RECEIVE`）、134837960（`ACTIVATE`）。起点已经盖住这三笔。

`tokenId` 等于 `uint256(namehash)`。`tld`：`0` 是 `.haha`，`1` 是 `.meme`。`aiId = keccak256(bytes(handleOf 返回的字符串))`，不要自己拼 `.ai`。`NameMinted.aiId` 为 `0x00…00` 且 `reservedMint = true` 时，那是管理员铸造，不要把这些行算进某个 `.ai` 的积分或铸造史。详见 `docs/contracts/INDEXING.md` 第 1 节。

## 事件

全部解码后写入原始日志。派生表只用其中标了「用于列表」的那些。`uint256` 在 JSON 里用十进制字符串，避免超过 `2^53`。地址用小写 `0x` 加 40 个十六进制字符。`bytes32` 用 `0x` 加 64 个十六进制字符。时间用 UTC 的 ISO-8601。

### HahaRegistrar

名字 NFT，同时是 ERC-721，所以还有 OpenZeppelin 的三个事件。

| 事件 | 用于列表 |
| --- | --- |
| `NameMinted(uint256 indexed tokenId, address indexed owner, uint8 tld, bytes32 indexed aiId, string label, bool reservedMint)` | 是。名字表 |
| `Transfer(address indexed from, address indexed to, uint256 indexed tokenId)` | 是。当前持有人；持有人变了则挂单变为陈旧 |
| `Approval(address indexed owner, address indexed approved, uint256 indexed tokenId)` | 只存原始日志 |
| `ApprovalForAll(address indexed owner, address indexed operator, bool approved)` | 只存原始日志 |

`Transfer` 的 topic0 与注册表那个 `Transfer(bytes32,address)` 不同。按合约地址加 topic0 过滤，不要混。

### HahaMarketplace

| 事件 | 用于列表 |
| --- | --- |
| `Listed(uint256 indexed tokenId, address indexed seller, uint256 price)` | 是。有效挂单 |
| `PriceUpdated(uint256 indexed tokenId, address indexed seller, uint256 oldPrice, uint256 newPrice)` | 是 |
| `Cancelled(uint256 indexed tokenId, address indexed seller)` | 是。撤掉挂单 |
| `StaleCleared(uint256 indexed tokenId, address indexed seller, address indexed currentOwner)` | 是。撤掉挂单 |
| `Sold(uint256 indexed tokenId, address indexed seller, address indexed buyer, uint256 price, uint256 fee, uint256 proceeds)` | 是。成交历史，并撤掉挂单 |
| `Withdrawn(address indexed account, uint256 amount)` | 只存原始日志 |

### HahaAgentIdentity

它也是 ERC-721。激活会铸出 agent NFT，转让名字时烧毁。

| 事件 | 用于列表 |
| --- | --- |
| `AgentActivated(uint256 indexed agentId, uint256 indexed nameTokenId, address indexed owner, bytes32 operatorAiId, uint64 generation, string agentURI)` | 是。广场、历代 |
| `URIUpdated(uint256 indexed agentId, string newURI, address indexed updatedBy)` | 是。更新 URI |
| `AgentReset(uint256 indexed nameTokenId, uint256 indexed agentId, address indexed previousOwner)` | 是。该 agent 不再活跃，评语留在这一代 |
| `AgentOperatorSet(uint256 indexed agentId, address indexed operator, bool allowed)` | 只存原始日志 |
| `Transfer(address indexed from, address indexed to, uint256 indexed tokenId)` | 是。`to` 是零地址表示烧毁，agent 不活跃 |
| `Approval`、`ApprovalForAll` | 只存原始日志 |

`generation` 从 1 起，只增不减。同一个 `nameTokenId` 的历代 agent 没有链上数组，只能重放 `AgentActivated` 和 `AgentReset`。

### HahaReputation

| 事件 | 用于列表 |
| --- | --- |
| `Rated(uint256 indexed agentId, bytes32 indexed aiId, address indexed rater, uint8 stars, string review, bool edited)` | 是。评语正文只在这里 |

`edited = true` 是修改同一 `(agentId, aiId)` 的旧评语，不是新的一条。存储里的 `getScore` 只留星数。展示评语必须用这个事件。

### HahaPoints

余额只认 `PointsChanged.newBalance`，不要用 `NameMinted` 或 `Rated` 自己加分。`Earned` 用来知道动作类型，它的 `newBalance` 应与同一交易里的 `PointsChanged` 一致。

| 事件 | 用于列表 |
| --- | --- |
| `PointsChanged(bytes32 indexed aiId, address indexed user, int256 delta, uint256 newBalance, bytes32 indexed reason)` | 是。积分榜 |
| `Earned(bytes32 indexed actionId, bytes32 indexed aiId, address indexed user, uint256 amount, bytes32 uniqueKey, uint256 newBalance)` | 只存原始日志。榜用 `PointsChanged` |
| `PointParamsUpdated(uint256 checkInPoints, uint256 mintReward, uint256 followPoints, uint256 retweetPoints, uint256 likePoints, uint256 commentPoints)` | 只存原始日志 |
| `SpenderUpdated(address indexed spender, bool allowed)` | 只存原始日志 |
| `EarnerUpdated(bytes32 indexed actionId, address indexed module, uint256 points, uint64 perUserDailyCap, uint256 globalDailyPoints, uint8 keyMode, bool requireName, bool enabled)` | 只存原始日志 |
| `SpenderBudgetUpdated(address indexed spender, uint256 perUserDailyPoints, uint256 globalDailyPoints)` | 只存原始日志 |
| `RoundOpened(uint256 indexed sessionId, bytes32 indexed gameId, bytes32 indexed aiId, address player, uint64 openDay)` | 只存原始日志 |
| `RoundClaimed(uint256 indexed sessionId, bytes32 indexed gameId, bytes32 indexed aiId, uint256 amount)` | 只存原始日志 |
| `GameUpdated(bytes32 indexed gameId, address indexed module, uint256 maxScorePerRound, uint256 perAiDailyPoints, uint256 globalDailyPoints, bool enabled)` | 只存原始日志 |

`reason` / `actionId` 是右填充的 `bytes32`。内置取值：`CHECKIN`、`MINT`、`FOLLOW`、`RETWEET`、`LIKE`、`COMMENT`、`REVIEW_GIVE`、`REVIEW_RECEIVE`、`ACTIVATE`。游戏发分时 `reason` 是那个游戏的 `gameId`，不是字符串 `GAME`。

`aiId` 全零的 `PointsChanged` 不要进入积分榜。

### HahaResolver

| 事件 | 用于列表 |
| --- | --- |
| `AddrChanged(bytes32 indexed node, address a)` | 只存原始日志。阶段 A 的单条解析仍走 RPC |
| `TextChanged(bytes32 indexed node, string indexed indexedKey, string key, string value)` | 只存原始日志 |
| `RecordsCleared(bytes32 indexed node)` | 是。转让后清空该 node 的解析缓存，若以后做解析列表 |
| `PrimaryNameSet(address indexed user, bytes32 indexed node, string fullName)` | 只存原始日志 |
| `PrimaryNameCleared(address indexed user, bytes32 indexed node)` | 只存原始日志 |

`RecordsCleared` 一次清掉地址覆盖、全部文本、以及「这个 node 是谁的主名」。清掉地址覆盖之后，解析回落到当前 NFT 持有人，不是 0。见 `docs/contracts/INDEXING.md` 第 3 节。V1 的六个列表不展示解析记录，但原始日志要留下，避免以后补表时再扫一遍。

### HahaRegistry

| 事件 | 用于列表 |
| --- | --- |
| `NewOwner(bytes32 indexed node, bytes32 indexed label, address owner)` | 只存原始日志。这里的 `node` 是 TLD node，不是名字自己的 node |
| `NewResolver(bytes32 indexed node, address resolver)` | 只存原始日志 |
| `Transfer(bytes32 indexed node, address owner)` | 只存原始日志。这是 EIP-137，不是 ERC-721 |

### HahaNamePolicy

| 事件 | 用于列表 |
| --- | --- |
| `ListsFrozen(uint256 bannedCount, uint256 reservedCount)` | 只存原始日志。部署时一次 |

## 数据库

推荐 **Postgres**，本机安装，只听 `127.0.0.1` 或 Unix 套接字，不要映射到公网。

理由：同步进程和 API 进程是两个 systemd 单元，同时一个写、一个读。Postgres 用事务做重组回滚：删掉受影响的原始日志，再重算派生表，API 不会读到一半。SQLite 在两个进程上写同一个文件容易锁死。若 C 坚持把同步和 API 放进同一个进程，SQLite 的 WAL 模式也能撑住 V1 的量，但默认不要选它。下面的表名按 Postgres 写。SQLite 把 `numeric` 换成 `TEXT`，把 `timestamptz` 换成整数 unix 秒。

### 原始与检查点

`raw_logs`

- `chain_id` smallint，固定 56
- `block_number` bigint
- `block_hash` bytea
- `block_time` timestamptz
- `tx_hash` bytea
- `tx_index` int
- `log_index` int
- `address` bytea
- `topic0` bytea
- `topics` jsonb
- `data` bytea
- 主键 `(chain_id, block_number, tx_index, log_index)`

`blocks`

- `block_number` 主键
- `hash`、`parent_hash`

`checkpoint` 只有一行：`safe_block`、`safe_hash`。只在派生表和这行一起提交之后更新。进程重启从 `safe_block + 1` 继续。

派生表只反映 `block_number <= safe_block` 的日志。API 不得读安全高度以上的行。做法是派生表写完就落在安全高度内，重组时整段重算。

### 派生表

`names`：每个 `token_id` 一行。字段 `token_id`、`label`、`tld`、`full_name`、`owner`、`mint_ai_id`、`reserved_mint`、`mint_block`、`mint_time`。来源 `NameMinted` 加 ERC-721 `Transfer` 更新 `owner`。

`listings`：当前仍有效的挂单，每个 `token_id` 至多一行。字段 `token_id`、`seller`、`price_wei`、`listed_block`、`listed_time`、`tx_hash`、`log_index`。

规则：

- `Listed` 插入。已有行则先删再插（不应发生，合约会 `AlreadyListed`）。
- `PriceUpdated` 改价，刷新时间和交易。
- `Cancelled`、`Sold`、`StaleCleared` 删除。
- 名字 ERC-721 `Transfer` 之后，若新持有人不是 `seller`，也删除。链上 `listings(tokenId)` 可能还留着旧卖家，直到有人 `clearStale`。页面不要展示这种陈旧单。删除后仍可在原始日志里看到。

`trades`：只追加 `Sold`。字段 `token_id`、`seller`、`buyer`、`price_wei`、`fee_wei`、`proceeds_wei`、`block_number`、`block_time`、`tx_hash`、`log_index`。主键含 `tx_hash + log_index`。

`agents`：每个 `agent_id` 一行。字段 `agent_id`、`name_token_id`、`owner`、`operator_ai_id`、`generation`、`agent_uri`、`active`、`activated_block`、`activated_time`、`reset_block`、`reset_time`、`stars_sum`、`stars_count`。

- `AgentActivated` 插入，`active = true`，星数从 0 开始。
- `URIUpdated` 改 `agent_uri`。
- `AgentReset` 或烧毁 `Transfer`：`active = false`，记下 reset 时间。不删行，历代评语还挂在这行上。
- `Rated`：若 `edited = false`，`stars_count += 1`，`stars_sum += stars`。若 `edited = true`，先减去该评分人上一次的星数再加新的。上一次星数存在 `reviews`。

`reviews`：一个 `(agent_id, rater_ai_id)` 一行，保存最新评语。字段 `agent_id`、`rater_ai_id`、`rater`、`stars`、`review`、`edited`、`block_number`、`block_time`、`tx_hash`、`log_index`。`Rated` 到来就 upsert。`edited` 反映最后一次事件。

`points`：一个 `ai_id` 一行，排除全零。字段 `ai_id`、`balance`、`last_user`、`last_reason`、`updated_block`、`updated_time`、`handle`。`balance` 直接写成 `PointsChanged.newBalance`。`handle` 用 `last_user` 调 `.ai` 注册表 `handleOf`。只有 `keccak256(bytes(handle))` 等于 `ai_id` 才写入。对不上或调用失败就留空，API 不显示一个假名字。不要在每次积分变动时都打 RPC：同一个 `last_user` 的 handle 缓存 1 小时。

## 同步

1. 读 `checkpoint`。没有则从 134834630 开始，第一块是 134834631。
2. 用 `eth_blockNumber` 得到头。安全高度 = 头 − **15**。BSC 出块大约 3 秒，15 块大约 45 秒，盖住常见短重组。不要把未确认的块写进派生表。
3. `eth_getLogs` 的区间最多 2000 块。遇到限流或「range too large」就把区间减半，最小 50 块。成功后再慢慢加回去，不超过 2000。
4. 拉到的日志和对应区块哈希放进同一个数据库事务：写 `blocks`、`raw_logs`、更新派生表、把 `checkpoint` 推进到本批的最后一块（不超过安全高度）。事务失败则整批重来。
5. 每秒对同一个 RPC 最多 5 次 `eth_getLogs` 或 `eth_getBlockByNumber`。收到 HTTP 429 或超时，指数退避，从 1 秒到 60 秒。连续失败 3 次就换备用 RPC。
6. 备用 RPC 从环境变量 `BSC_RPC_URLS` 读取，逗号分隔，按顺序轮换。仓库里只写公开端点作为例子，不写带密钥的 URL：`https://bsc-dataseed.binance.org`、`https://bsc-dataseed1.defibit.io`、`https://bsc.publicnode.com`。真正用哪几个由服务器上的 env 决定。

重组：

- 每推进一批，核对 `checkpoint.safe_hash` 是否仍是该块的链上哈希。
- 不一致时，从检查点往前比 `blocks.parent_hash`，找到最后一个还在链上的块 `N`。
- 一个事务里删掉 `block_number > N` 的 `raw_logs` 和 `blocks`，然后按剩余原始日志重算 `names`、`listings`、`trades`、`agents`、`reviews`、`points`。重算可以整表重建，V1 数据量用这个办法最不容易算错。
- 把 `checkpoint` 设为 `N`，再向前同步。
- API 在重算事务提交前仍读旧数据。不要先删表再慢慢填。

## HTTP API

进程只绑 `127.0.0.1` 的一个端口，建议 `8787`。nginx 把 `/api/` 反代过去。浏览器只访问同站的 `/api/...`，不跨域。

通用查询参数：

| 参数 | 含义 |
| --- | --- |
| `limit` | 默认 24，最小 1，最大 50。非法时 400 |
| `cursor` | 上一页的 `nextCursor`。省略表示第一页 |
| `sort` | 各接口自己的枚举。非法时 400，正文 `{"error":"invalid_sort"}` |

游标是不透明字符串，里面是排序键加主键，避免用页码时新插入的行把下一页挤乱。没有下一页时 `nextCursor` 为 `null`。

列表响应都是：

```json
{ "items": [], "nextCursor": null }
```

空列表是合法的 200，不是 404。前端见到 `items: []` 就显示空状态。

缓存：列表 `Cache-Control: public, max-age=5, stale-while-revalidate=30`。健康检查 `Cache-Control: no-store`。

### `GET /api/health`

```json
{
  "ok": true,
  "chainId": 56,
  "safeBlock": 134840000,
  "headBlock": 134840020,
  "lagBlocks": 20,
  "lastError": null
}
```

`ok` 为 true 的条件：进程能连上数据库，且 `lagBlocks <= 40`（大约两分钟）。否则 `ok: false`，HTTP 仍返回 200，方便监控区分「进程挂了」和「落后了」。进程挂了由 nginx 返回 502。

### `GET /api/v1/listings`

市场网格。只含 `listings` 表里的有效行，并带上 `names` 的 label。

`sort`：`listed_desc`（默认）、`price_asc`、`price_desc`。

可选 `tld`：`haha` 或 `meme`。可选 `q`：完整小写 label，精确匹配，不是模糊搜索。

```json
{
  "items": [
    {
      "tokenId": "123",
      "label": "abc",
      "tld": "haha",
      "fullName": "abc.haha",
      "seller": "0xabc…",
      "priceWei": "200000000000000000",
      "listedAt": "2026-11-21T08:00:00Z",
      "blockNumber": 134900000,
      "txHash": "0x…",
      "logIndex": 3
    }
  ],
  "nextCursor": null
}
```

`tld` 在 JSON 里用 `haha` / `meme`，不要用 0 / 1，避免页面再翻译一遍。库里仍存 0 / 1。

### `GET /api/v1/trades`

成交。`sort`：`time_desc`（默认）、`price_desc`。

可选 `fullName`：`abc.haha` 这种，只看这一个名字。

```json
{
  "items": [
    {
      "tokenId": "123",
      "label": "abc",
      "tld": "haha",
      "fullName": "abc.haha",
      "seller": "0x…",
      "buyer": "0x…",
      "priceWei": "200000000000000000",
      "feeWei": "2000000000000000",
      "proceedsWei": "198000000000000000",
      "tradedAt": "2026-11-21T09:00:00Z",
      "blockNumber": 134910000,
      "txHash": "0x…",
      "logIndex": 8
    }
  ],
  "nextCursor": null
}
```

### `GET /api/v1/agents`

agent 广场。默认只要 `active = true`。`sort`：`activated_desc`（默认）、`stars_desc`、`reviews_desc`。

`stars_desc` 按 `stars_sum / stars_count` 排，没有评价的平均分当作 0，排在有评价的后面。同分再按 `stars_count` 降序，再按 `agent_id` 升序。

```json
{
  "items": [
    {
      "agentId": "7",
      "tokenId": "123",
      "label": "abc",
      "tld": "haha",
      "fullName": "abc.haha",
      "owner": "0x…",
      "operatorAiId": "0x…",
      "generation": 1,
      "agentURI": "https://example.com/agent.json",
      "active": true,
      "starsSum": 5,
      "starsCount": 1,
      "activatedAt": "2026-11-21T08:10:00Z",
      "blockNumber": 134901000
    }
  ],
  "nextCursor": null
}
```

### `GET /api/v1/leaderboard/reputation`

信誉榜。只含 `active = true` 且 `stars_count >= minReviews` 的 agent。`minReviews` 默认 1，允许 1 到 20。

`sort` 只有 `stars_desc`（默认）。排序与广场的 `stars_desc` 相同。

条目字段与 `/api/v1/agents` 的单条相同，另加 `"rank": 1`。`rank` 从 1 起，跨页连续。

### `GET /api/v1/names/{fullName}/generations`

历代评语。`fullName` 形如 `abc.haha` 或 `abc.meme`，只允许小写 label 和这两个后缀。其它形状返回 400，`{"error":"invalid_name"}`。

名字从未铸出：404，`{"error":"not_found"}`。铸出过但没有 agent：200，`generations` 为空数组。

不分页。一个名字的代数和评语在 V1 很少。若某一代评语超过 100 条，该代只返回按时间倒序的前 100 条，并设 `"reviewsTruncated": true`。

```json
{
  "fullName": "abc.haha",
  "tokenId": "123",
  "generations": [
    {
      "generation": 2,
      "agentId": "9",
      "active": true,
      "owner": "0x…",
      "agentURI": "https://example.com/agent.json",
      "starsSum": 0,
      "starsCount": 0,
      "activatedAt": "2026-11-21T10:00:00Z",
      "resetAt": null,
      "reviews": []
    },
    {
      "generation": 1,
      "agentId": "4",
      "active": false,
      "owner": "0x…",
      "agentURI": "https://example.com/old.json",
      "starsSum": 5,
      "starsCount": 1,
      "activatedAt": "2026-11-21T08:00:00Z",
      "resetAt": "2026-11-21T09:30:00Z",
      "reviewsTruncated": false,
      "reviews": [
        {
          "rater": "0x…",
          "raterAiId": "0x…",
          "stars": 5,
          "review": "nice",
          "edited": false,
          "ratedAt": "2026-11-21T08:20:00Z",
          "txHash": "0x…"
        }
      ]
    }
  ]
}
```

代数从大到小，当前代在前。评语按 `ratedAt` 倒序。

### `GET /api/v1/leaderboard/points`

积分榜，按 `.ai` 的 `ai_id`，不是按钱包，也不是按单个名字。`sort` 只有 `balance_desc`。排除余额 0 和全零 `ai_id`。

```json
{
  "items": [
    {
      "rank": 1,
      "aiId": "0x…",
      "handle": "heyi",
      "balance": "30",
      "updatedAt": "2026-11-21T08:00:00Z"
    }
  ],
  "nextCursor": null
}
```

`handle` 未知时为 `null`。前端显示 `null` 时用缩短的 `aiId`，不要编一个 `.ai` 名字。`balance` 是十进制字符串。

## 部署

和网站在同一台机器上。不新增公网端口。

nginx，写在 `ddao.app` 和以后的 `haha.meme` 的 server 块里：

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8787/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

`proxy_pass` 末尾的斜杠会把 `/api/health` 转成上游的 `/health`，把 `/api/v1/listings` 转成 `/v1/listings`。进程内部路由不要再加一层 `/api`。对外 URL 仍是 `/api/v1/...` 和 `/api/health`。

`location /api/` 不要套用静态文件那条 7 天缓存。缓存只由 API 的 `Cache-Control` 决定。

两个 systemd 单元，工作目录不放密钥：

- `haha-indexer.service`：同步循环。`Restart=on-failure`，`RestartSec=5`。
- `haha-api.service`：HTTP。同样失败自启。

都使用 `EnvironmentFile=/etc/haha/indexer.env`。这个文件至少有 `DATABASE_URL` 和 `BSC_RPC_URLS`。不要把该文件提交到 git，也不要写进 `docs/`。

日志走 journald：`journalctl -u haha-indexer -u haha-api`。

监控：每分钟本机 `curl -fsS http://127.0.0.1:8787/health`。`ok` 不是 true，或 curl 失败，记一条错误日志。连续 5 分钟失败就需要人看。V1 不必接外部告警服务。另外看数据库磁盘，原始日志会一直涨。

测试站先接。`ddao.app` 的 `/api/` 指向同一进程即可，因为读的是主网，不是测试网。正式站的 nginx 在验收通过前不要把 `/api/` 指到一个空进程后就对外宣传列表已上线。

## 验收

在 `ddao.app` 上做。对照 BscScan，不对照 `mock.js`。

1. `GET /api/health` 的 `chainId` 是 56，`safeBlock` 大于 134834631，`lagBlocks` 不超过 40。重启两个服务后，`safeBlock` 不倒退，并继续往前走。
2. 选一笔真实 `Listed` 且之后没有 `Cancelled`、`Sold`、`StaleCleared`，持有人仍是卖家。它出现在 `/api/v1/listings`，`priceWei` 与合约 `listings(tokenId)` 一致。
3. 一笔 `Sold` 出现在 `/api/v1/trades`，`feeWei` 约为价格的 1%，并且该 `tokenId` 不再出现在 listings。
4. 名字转给别人之后，旧卖家的挂单从 listings 消失，即使还没有人调用 `clearStale`。
5. 一个激活过的 agent 出现在 `/api/v1/agents`。转让并 `AgentReset` 之后，`active` 为 false，广场默认列表里没有它。
6. 对这个名字请求 `/generations`，旧一代仍在，评语文本与该笔 `Rated` 的事件参数一致。再评一次后 `edited` 为 true，`starsCount` 不加。
7. 积分榜某一行的 `balance` 等于 `HahaPoints.balanceOf(aiId)`。`aiId` 全零不在榜上。`handle` 要么为 null，要么哈希回去等于 `aiId`。
8. 把安全高度附近的一块哈希改成假想重组（测试库上把 `blocks.hash` 改掉再启动）后，索引器回退到分叉前并重放，listings 与重放前的链一致。测完用正式库重新从检查点同步，不要把测试库接给网站。
9. 响应头含规定的 `Cache-Control`。`limit=100` 返回 400。
10. 仓库和发布目录里搜不到数据库 URL、RPC 密钥和服务器 IP。

## 工期（一个人，粗估）

这是写索引器本身，不含阶段 A 的页面。按一个熟悉这套合约的开发者估，大约 **6 个工作日**，公开 RPC 若整天限流再加 1 到 2 天。

| 天数 | 内容 |
| --- | --- |
| 1 | Postgres、原始日志、检查点、从 134834631 可恢复同步 |
| 1 | 15 块确认、重组回滚、限速和备用 RPC |
| 2 | 六张派生表：挂单、成交、广场、信誉榜、历代评语、积分榜 |
| 1 | 本文的 REST、游标、缓存头 |
| 1 | systemd、nginx `/api/`、健康检查，并在 `ddao.app` 做上面的验收 |

做完第 6 天的验收之后，才把 `HAHA_INDEXER_BASE` 设成 `/api`，再考虑把同一套发布到 `haha.meme`。
