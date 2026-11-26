# haha.meme 索引器 MCP Server 开发文档（v1）

> 状态：草稿，待 L 确认冻结。冻结后照此开发，不再改范围。
> 日期：2026-11-26（2026-11-26 修订：v1 改为 HTTP 远程托管版）

## 1. 目标

把 haha.meme 索引器的只读 API 包成一个 MCP Server，让任何 agent（Claude Desktop、Claude Code、Cursor、VS Code 等）不用写代码、不用安装，就能直接查询 haha.meme 的链上数据。

一句话：**数据更透明，用户不用写代码、不用安装，agent 直接问、直接答。**

## 2. 范围与边界

- **只做只读。** 只包装 GET 查询接口，不做任何写操作。
- **不碰交易。** 不铸造、不激活、不评分、不买卖、不签名、不动钱、不碰私钥。
- **不做推送。** MCP Server 不能主动给用户发消息、不能每次更新触达用户。触达用户仍走 X / Telegram / 邮件。
- **不改索引器。** 索引器 API 本身不动，MCP Server 只是一个薄壳，转手调现成的 API。

## 3. 已定决策

| 事项 | 决定 |
|---|---|
| 只读 / 写操作 | 只读，不做写操作 |
| 传输方式 | **HTTP 远程版（托管）**，不是 stdio 本地版 |
| 托管 | 我们自己的服务器（Vultr，167.179.82.12），与网站同一台 |
| 对外地址 | `https://haha.meme/mcp`（Streamable HTTP） |
| 用户安装 | **不用安装**：用户只在 agent 配置里贴一个网址，不用 Node.js、不用 npx、不用下载我们的包 |
| 代码放哪 | GitHub 公开库 `li271498019/hahamemeid`，目录 `MCP/`（不新建仓库） |
| 项目名 | `haha-meme-mcp` |
| npm / npx | **用户侧不用**。npm 只在我们服务器上用（部署时装依赖、编译），用户完全碰不到 |
| 语言 | TypeScript，Node.js 20+ |
| MCP SDK | `@modelcontextprotocol/sdk`（官方 SDK，与 order-flow-mcp 相同） |
| 工具数量 | 29 个，对应索引器全部 30 个 GET 接口（除 image.svg，见 §4） |
| 认证 | v1 不设 token（公开只读数据，与网站 API 相同）；nginx 限流防滥用 |
| 网站 | how.html 与 api.html 顶部放 MCP 接入地址与配置；api.html 现有内容全部保留，不删除 |
| 版本 | 语义版本（semver），见 §9 |

## 4. 工具清单（29 个，1:1 映射）

基准：线上索引器 `/opt/haha-indexer/api.py` 的 ROUTES（2026-11-26 核对，30 个 GET 接口）。每个接口对应一个 MCP 工具，名字、参数、返回与 API 保持一致。

### 4.1 第一季（10 个）

| 工具 | API | 主要参数 |
|---|---|---|
| `get_season_day` | `GET /v1/season1/days/{day}` | day（dayIndex，如 20783） |
| `get_season_leaderboard` | `GET /v1/season1/leaderboard/{day}` | day |
| `check_season_eligibility` | `GET /v1/season1/eligibility/{aiId}?day=` | aiId（0x…64 位），day |
| `get_season_proof` | `GET /v1/season1/proof/{aiId}?day=` | aiId，day |
| `get_season_order` | `GET /v1/season1/orders/{orderId}` | orderId |
| `list_season_orders` | `GET /v1/season1/orders?day=&status=&limit=&cursor=` | day（必填），status，limit，cursor |
| `get_season_verify` | `GET /v1/season1/verify/{aiId}?day=` | aiId，day |
| `list_season_findings` | `GET /v1/season1/findings` | 无 |
| `get_season_finding` | `GET /v1/season1/findings/{digest}` | digest（0x…64 位） |
| `get_season_taskpack` | `GET /v1/season1/taskpack/{day}` | day |

### 4.2 名字 / Agent / 市场 / 榜单（19 个）

| 工具 | API | 主要参数 |
|---|---|---|
| `get_health` | `GET /health` | 无（查服务是否正常） |
| `list_listings` | `GET /v1/listings` | limit，sort（listed_desc / price_asc / price_desc），tld，q，cursor |
| `list_trades` | `GET /v1/trades` | limit，cursor |
| `list_names` | `GET /v1/names` | limit，cursor |
| `list_events` | `GET /v1/events` | limit，cursor |
| `list_agents` | `GET /v1/agents` | limit，sort（activated_desc / stars_desc / reviews_desc），cursor |
| `get_agent_registration_by_name` | `GET /v1/agents/by-name/{name}/registration.json` | name（如 ha.haha） |
| `get_agent_registration_by_id` | `GET /v1/agents/{id}/registration.json` | agentId（数字） |
| `list_agent_validations` | `GET /v1/agents/{id}/validations` | agentId（数字） |
| `get_validation` | `GET /v1/validations/{requestHash}` | requestHash |
| `get_reputation_leaderboard` | `GET /v1/leaderboard/reputation` | limit，cursor |
| `list_name_generations` | `GET /v1/names/{name}/generations` | name |
| `get_name_metadata` | `GET /v1/names/{name}/metadata` | name |
| `get_name` | `GET /v1/names/{name}` | name（未铸造也返回 200，含 minted 字段） |
| `list_owner_names` | `GET /v1/owners/{address}/names` | address（0x…40 位） |
| `get_owner_primary` | `GET /v1/owners/{address}/primary` | address |
| `list_latest_reviews` | `GET /v1/reviews/latest` | limit，cursor |
| `get_points_leaderboard` | `GET /v1/leaderboard/points` | limit，cursor |
| `get_stats` | `GET /v1/stats` | 无（平台总数据） |

### 4.3 不包的接口

| 接口 | 原因 |
|---|---|
| `GET /v1/names/{name}/image.svg` | 二进制 SVG 图片，不是 JSON。`get_name` 返回里已含图片 URL，agent 需要时直接取 URL，不单独做工具 |
| `POST /v1/season1/findings/{digest}/report` | 写操作（提交找错），违反只读边界 |
| `POST /v1/season1/sign-verify` | 写操作（每日验证签名），独立签名服务，不进 MCP |
| `POST /v1/validations/upload` | 写操作（上传验证文档，需 agent 签名），不进 MCP |

## 5. 技术方案

- **结构**：`MCP/` 下 `src/index.ts`（入口，HTTP 传输）+ `src/tools.ts`（工具注册表）+ `src/api.ts`（调索引器 API 的客户端）。
- **运行方式**：服务器上 systemd 服务 `haha-mcp`，监听 `127.0.0.1:3333`（内网端口，不对外暴露）；nginx 把 `https://haha.meme/mcp` 反向代理到它（Streamable HTTP）。与 `haha-api`（127.0.0.1:8787）、`haha-sign-verify`（127.0.0.1:8788）同一套做法。
- **调 API 的地址**：服务器内网直接调索引器 `http://127.0.0.1:8787`（不走公网、不走 Cloudflare，少一跳）。可用环境变量 `HAHA_API_BASE` 覆盖（方便本地测试）。
- **限流**：nginx 对 `/mcp/` 做限流（防滥用），具体阈值实施时定。v1 不设 token。
- **不用登录、不用 API key**：索引器读接口是公开的，MCP Server 不处理任何认证。
- **返回**：直接返回 API 的 JSON，不二次加工、不编造、不省略。API 返回 404（如无资格、查无此名）时，工具返回明确的错误说明，不崩溃。
- **工具描述**：每个工具写一段给 LLM 看的描述（中文 + 英文，说明这工具是查什么的、什么时候用、参数是什么意思）。描述写得清楚，agent 才调得对。
- **依赖**：只用 `@modelcontextprotocol/sdk` + `zod`（参数校验）+ Node.js 自带 fetch。越少依赖越稳。
- **stdio 以后可加**：工具注册表与传输层是分开的，以后想加 stdio 本地版，加几行代码即可，工具不用动。v1 不做。

## 6. 可拓展性（以后加新功能、新接口，能拓展吗？能）

设计成这样，以后加接口就是加一行，不用动骨架：

- **工具注册表模式**：所有工具集中在 `src/tools.ts`，每个工具就是一条定义：名字、描述、参数格式、处理函数。处理函数只做一件事——调对应的 API 接口，把 JSON 返回。
- **加一个新接口 = 加一条工具定义**（约 10–20 行）。不用改传输层、不用改服务器骨架、不用动已有的工具。索引器上新接口 → MCP 加一个工具 → 发新版 → 更新 README / api.html，四步走完。
- **加新传输方式也不动工具**：工具注册表与传输层分开，std / HTTP 只是换个入口，工具原封不动。
- **版本规则保证不破坏老用户**：工具名一旦发布就不改名、不删除，只新增。加工具 = minor 版本号 +1（如 1.0 → 1.1）；修 bug = patch +1（如 1.0.0 → 1.0.1）。老用户的配置不用改（HTTP 版用户连配置都不用改，服务端一更新就自动用上新版）。

## 7. 仓库与发布（HTTP 版）

- **代码位置**：公开库 `li271498019/hahamemeid`，目录 `MCP/`（含 package.json、src/、README.md、测试）。不新建仓库。
- **部署到服务器**：从公开库拉 `MCP/` 代码到服务器 → `npm install`（装依赖，只在服务器上用）→ `npm run build` → 重启 systemd 服务 `haha-mcp`。与网站、索引器的部署流程同一套。
- **用户不用 npm / npx**：用户不下载包、不装 Node.js、不跑 npx。用户只在 agent 配置里贴一个网址。
- **用户接入方式**（网站与 README 用同一份）：
  - Claude Code：`claude mcp add --transport http haha-meme https://haha.meme/mcp`
  - Claude Desktop / Cursor / VS Code 等（配置文件里加）：
    ```json
    {
      "mcpServers": {
        "haha-meme": {
          "url": "https://haha.meme/mcp"
        }
      }
    }
    ```
  - 注：不同客户端的 HTTP 配置格式略有不同（有的要 `"type": "http"`），实施时按各客户端的实际格式逐一核对。

## 8. 网站改动

- **how.html（工作原理页）顶部**：加一个 MCP 区块，首屏可见：一句话介绍（agent 不用写代码、不用安装就能查 haha.meme 数据）+ 接入地址 `https://haha.meme/mcp` + 配置方法 + 指向 api.html 的链接。中英双语。
- **api.html 顶部**：加一个 MCP 区块，页面最上方：接入地址 + 各客户端配置方法 + 工具列表概要 + 指向 GitHub 公开库的链接。中英双语。
- **api.html 现有内容全部保留，不删除、不改动现有章节。** 只在顶部加 MCP 区块。
- **页尾、导航不变。** 不新增页面。

## 9. 测试与验收

- **单元测试**：工具的参数校验、API 返回 404 / 500 时的错误处理（不连真实 API，用假数据测）。
- **冒烟测试**：`npm run smoke`，对线上 API 跑一遍每个工具，确认每个工具都能返回真实数据（参考 order-flow-mcp 的 smoke 做法）。
- **MCP Inspector**：用官方 Inspector 连上 `https://haha.meme/mcp`，确认 29 个工具都能列出、都能调。
- **真机验收**：在 Claude Desktop（或 Claude Code）里接上 `https://haha.meme/mcp`，问三个问题验证：① “ha.haha 的信誉怎么样？”② “今天第一季谁有资格兑换？”③ “平台现在有多少个名字？”——三个都能答对才算通过。
- **验收标准**：29 个工具全部能调、返回与 API 一致、不编造数据、API 报错时不崩溃；服务器重启后服务能自己恢复。

## 10. 版本与更新

- **版本号**：从 `1.0.0` 开始，语义版本。
- **更新流程**：索引器加新接口 → MCP 加对应工具 → 升版本号 → 更新 README 与 api.html → 部署到服务器 → 告诉 L。HTTP 版用户不用做任何事，服务端一更新就自动用上新版。
- **更新触达**：MCP 本身不能推送消息。发新版后，在 X / Telegram 告诉用户；工具返回里可带一条版本号提示（用户下次调工具时能看到）。

## 11. 不做（明确排除，v1 不碰）

- 写操作（铸造、激活、评分、买卖、签名、上传）——全部不做。
- stdio 本地版——v1 不做（以后可加，工具不用动）。
- 认证 token——v1 不设（公开只读数据）；如果以后被滥用，再加。
- 支付、托管、x402——不做，与这个 Server 无关。
- agent 模板（让 agent 活起来的参考程序）——是另一个东西，不在这个文档里。
- 改索引器、改网站其他页面——不做，只动 how.html 与 api.html 的顶部。

## 12. 待 L 确认（冻结前请定）

1. 项目名 `haha-meme-mcp`，可以吗？
2. 公开库目录 `MCP/`，可以吗？（已按你说的定）
3. 对外地址 `https://haha.meme/mcp`，可以吗？
4. 工具清单 29 个（§4），有没有要加、要减的？
5. how.html 与 api.html 顶部的接入地址与配置，用 §7 那份，可以吗？
6. v1 不设 token、只用 nginx 限流，可以吗？
