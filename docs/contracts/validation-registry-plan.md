# G13 验证注册表（Validation Registry）— 实施计划（已冻结·审计修订版）

状态：**已冻结（2026-11-25，L 确认；审计修订版，2026-11-25 L 授权全面修订；EIP-712 修订，2026-11-25 L 已定）**。冻结后实施时不再改计划，改计划需 L 另行批准。
作者：C。日期：2026-11-25。顺序：按 L 在 2026-11-25 定下的落地顺序 **G4 → G9（已否决）→ G13**，G4 已于 2026-11-25 11:04 上线（PR #98，C 合并），G9 已于 2026-11-25 否决（L 决定不做假装兼容的包装），G13 是下一件。
分工：D 写合约，C 做索引器 + 前端 + skill.md + 验证者服务，L 批准部署并担任唯一验证者。B 已无法参与开发，不再等 B。

**v1 简化（2026-11-25，L 定下）**：v1 指定管理员（`0x083A…76Ef7`）为唯一验证者，中心化；不要奖励，L 自己做验证者；不要质押。质押、奖励、惩罚、多验证者全部移到 v2。争议在 v1 里有：就是验证者第二次复核（见 §5）。升级到 v2 须重新部署新合约（见 §10 第 3 条的说明）。

标准核对：2026-11-25 已对照 EIP-8004 标准原文（`ercs.ethereum.org/ERCS/erc-8004`，状态 Draft）逐字核对验证注册表一节，实质内容见 §2（不引行号，行号随页面更新会移动）。积分合约核对：v1 不用积分合约（无质押、无奖励、无惩罚），已通读 `HahaPoints.sol` 全文确认 v1 不调 `earn` / `spend` / `refund`；质押与激励的积分机制只在 v2 讨论时再用。

---

## 1. 目标

新部署一个验证合约 `HahaValidation`，实现 EIP-8004 标准 Validation Registry 的接口，让第三方能验证 agent 的声明是否真实。验证结果存在验证合约自己里，任何人都能查。

**范围边界（v1，L 已定）：**
- 只加新合约，不改任何现有合约（`HahaReputation`、`HahaAgentIdentity`、`HahaPoints`、`HahaRegistrar` 等一个字节都不动，不重部署）。
- **v1 指定管理员为唯一验证者，中心化。** 验证合约的管理员 = `HahaRegistrar` 的 admin，地址 `0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7`，`immutable`，部署时写死（与现有合约一致）。验证者地址初始为管理员，存为合约存储变量，管理员可调 `setValidator` 改（见 §4.1）。L 自己做验证者，验证程序跑在 L 的服务器上，用管理员密钥签名（密钥已在服务器上，第一季自动化在用）。
- **v1 不要奖励、不要质押、不要惩罚。** 质押、奖励、惩罚、多验证者全部移到 v2。争议在 v1 里就是验证者第二次复核（见 §5），不用第二验证者、不用质押。
- v1 只做两类验证：**接口可达**与**身份真实性**（见 §3）。完成任务能力已由 L 决定去除。
- 现有功能（铸名、激活、打分、挂单、第一季、G4 注册文件）全部正常运转。
- v1 不做验证者声誉排行、不做验证市场，以后另立计划。

---

## 2. 标准接口（EIP-8004 Validation Registry，逐字核对）

注：本计划不引标准行号——EIP-8004 是 Draft，页面更新会移动行号（2026-11-25 核对时行号已与上一版相差约 35 行）。D 按小节标题 + 函数签名定位标准原文；实质内容（签名、事件、返回值、MUST）已于 2026-11-25 逐字核对，与标准原文一致。

### 2.1 写接口

| 函数 | 签名（标准原文） | 规则 | 标准出处 |
|---|---|---|---|
| `validationRequest` | `validationRequest(address validatorAddress, uint256 agentId, string requestURI, bytes32 requestHash)` | MUST 由 agent 的 owner 或 operator 调；四个字段全部必填；`requestHash` 是对请求数据的承诺（`keccak256`），标识本次请求；同一 `requestHash` 再次调 → revert（G12，见 §3.4）；`requestHash` 由请求人按 §3.4 公式链下算好后传入，合约链上验算公式，不符 revert | Validation Registry → Validation Request 一节（签名、MUST 与 requestHash 定义） |
| `validationResponse` | `validationResponse(bytes32 requestHash, uint8 response, string responseURI, bytes32 responseHash, string tag)` | 只有 `requestHash` 与 `response` 必填，`responseURI` / `responseHash` / `tag` 可选；MUST 由请求里指定的 `validatorAddress` 调；`response` 为 0–100 的分数；可多次调用（更新结果） | Validation Registry → Validation Response 一节（签名、必填字段与 MUST、多次调用） |
| `initialize` / `getIdentityRegistry` | `initialize(address identityRegistry_)`；`getIdentityRegistry() returns (address)` | 部署时设 identityRegistry 地址（`HahaAgentIdentity`，`0x54A70BF81B288d41013D7b57c2Db0922f1E1a4d4`）并公开可查（与 Reputation Registry 相同模式） | Validation Registry 一节（initialize 与 getIdentityRegistry，定义见 Reputation Registry 一节） |

### 2.2 读接口

| 函数 | 签名（标准原文，含返回值） | 规则 | 标准出处 |
|---|---|---|---|
| `getValidationStatus` | `getValidationStatus(bytes32 requestHash) returns (address validatorAddress, uint256 agentId, uint8 response, bytes32 responseHash, string tag, uint256 lastUpdate)` | 查一次验证请求的状态，返回最新结果 | Validation Registry → Read Functions 一节 |
| `getSummary` | `getSummary(uint256 agentId, address[] validatorAddresses, string tag) returns (uint64 count, uint8 averageResponse)` | 按 agent 查验证汇总；agentId 必填，validatorAddresses 与 tag 为可选过滤（空数组 = 不过滤）；count 为符合过滤的请求数，averageResponse 为各请求最新结果的平均（整数除法） | Validation Registry → Read Functions 一节 |
| `getAgentValidations` | `getAgentValidations(uint256 agentId) returns (bytes32[] requestHashes)` | 查一个 agent 的全部验证请求哈希 | Validation Registry → Read Functions 一节 |
| `getValidatorRequests` | `getValidatorRequests(address validatorAddress) returns (bytes32[] requestHashes)` | 查一个验证者的全部验证请求哈希 | Validation Registry → Read Functions 一节 |

**注（G13 与标准的对照）：** 标准原文的 `getSummary` 只返回 `(count, averageResponse)`，不返回最新结果与请求哈希（标准 Validation Registry → Read Functions 一节）。最新结果与请求哈希通过 `getAgentValidations`（返回该 agent 的全部 requestHash，标准 Validation Registry → Read Functions 一节）+ `getValidationStatus`（按 requestHash 查最新结果，标准 Validation Registry → Read Functions 一节）取得。v1 只有一个验证者（管理员），调 `getSummary` 时 `validatorAddresses` 传空数组（不过滤）或 `[管理员地址]` 均可。D 按本表写合约，不得自创签名与返回值。

### 2.3 事件

| 事件 | 签名（含类型与 indexed） | 说明 | 标准出处 |
|---|---|---|---|
| `ValidationRequest` | `event ValidationRequest(address indexed validatorAddress, uint256 indexed agentId, string requestURI, bytes32 indexed requestHash)` | 发起验证请求时发 | Validation Registry → Validation Request 一节 |
| `ValidationResponse` | `event ValidationResponse(address indexed validatorAddress, uint256 indexed agentId, bytes32 indexed requestHash, uint8 response, string responseURI, bytes32 responseHash, string tag)` | 验证者提交结果时发（每次调用都发） | Validation Registry → Validation Response 一节 |
| `ValidationDisputed` | `event ValidationDisputed(bytes32 indexed requestHash, address indexed disputer)` | 任何人标记争议时发（v1 新增，非标准事件，须在文档里注明） | —（v1 新增） |

**注：** 索引器按本表签名解码，签错一个字段就解不出来。D 写合约时对照标准原文 Validation Registry → Validation Request / Validation Response 两节逐字确认；如标准原文的字段顺序或 indexed 与本表不同，以标准原文为准并在计划里注明。

### 2.4 标准里的 MUST 与留白

- `validationRequest` MUST 由 owner/operator 调（标准 Validation Registry → Validation Request 一节）；`validationResponse` MUST 由请求里指定的 validator 调（标准 Validation Registry → Validation Response 一节）。
- `response` 是 0–100 的分数（uint8）（标准 Validation Registry → Validation Response 一节）。
- 合约存储字段（标准 Validation Registry → Validation Response 一节，存储字段段）：`requestHash`、`validatorAddress`、`agentId`、`response`、`responseHash`、`lastUpdate`、`tag`。v1 另存 `firstResponseTime`（第一次 validationResponse 的区块时间，争议窗口起算点，之后不再变）与 `disputed`（是否已争议过，bool），见 §5.1。
- **激励与罚没不在标准范围内**：标准原文写明“Incentives and slashing related to validation are managed by the specific validation protocol and are outside the scope of this registry.”（标准 Validation Registry → Read Functions 一节之后，激励免责段）所以质押、奖励、惩罚的规则由我们自己定（见 §4、§5），不违反标准。
- 验证方法不限：标准举例有质押者重跑（stake-secured re-execution）、zkML、TEE、可信裁判等（标准 Validation Registry 一节开头，验证方法举例），v1 用“验证者实际去查”（见 §3）。

### 2.5 v1 新增函数（非标准，L 已定）

| 函数 | 签名 | 规则 |
|---|---|---|
| `dispute` | `dispute(bytes32 requestHash)` | 任何人可调；须已有验证结果（至少一次 validationResponse），且在第一次结果提交后 3 天内，且该请求未争议过，否则 revert；成功后发 `ValidationDisputed` 事件 |
| `setValidator` | `setValidator(address newValidator)` | 只有合约管理员能调；新地址不能为零地址 |
| `admin`（只读） | `admin() returns (address)` | 返回合约管理员地址（`public immutable` 变量自动生成读取接口，部署时写死为 HahaRegistrar 的 admin） |
| `validator`（只读） | `validator() returns (address)` | 返回当前验证者地址（`public` 存储变量） |

---

## 3. 两类验证（L 已定，只做这两类）

### 3.1 接口可达（`tag="endpoint-reachable"`）

- **查什么**：agent 注册文件里 `services[].endpoint` 的地址能不能连通。
- **怎么查（G6/G7）**：验证者先向 endpoint 发 HTTP GET（超时 10 秒）。若 GET 返回 405，改发 POST 空 JSON（`Content-Type: application/json`，body `{}`），供 MCP / A2A 类只接受 POST 的端点。
- **打分**：
  - 2xx / 3xx → 100 分；
  - 401 / 403 → 100 分（服务存在，需认证）；
  - 404 / 其他 4xx → 0 分；
  - 5xx → 0 分；
  - 连接失败 / 超时 / DNS 失败 → 0 分。
- 3xx 视为可达，验证者不需跟随跳转（3xx 响应本身即证明服务存在）。
- **证据**：`responseURI` 指向验证记录（请求方法、HTTP 状态码、响应时间、检查时间），`responseHash` 为记录的 keccak256。
- **客观性**：完全客观，全自动，无主观判断。
- **注册文件核对**：验证者还须核对请求文档里的 endpoint 在 agent 的注册文件里：服务取 agent 的 agentURI（从 `HahaAgentIdentity` 查），读注册文件，确认 endpoint 是其中一个 `services[].endpoint`；不在注册文件里 → 提交 0 分，证据写明“endpoint 未在注册文件中”。

### 3.2 身份真实性（`tag="identity-verified"`）

- **查什么**：agent 是否控制它声称的钱包（即 agent 的主人地址）。
- **怎么查**：agent 主人在请求文档里放签名字段：用主人钱包签一个挑战消息，挑战内容就是 `requestHash`。两种签名都认（2026-11-25 修订，L 已定）：EIP-191 个人签名（签名内容为 `requestHash` 的 32 字节原始值，不是十六进制字符串），或 EIP-712 typed data 签名（主类型 `IdentityChallenge`，字段 `agentId` (uint256)、`requestHash` (bytes32)；domain 是 name `HahaValidation`、version `1`、chainId 56、verifyingContract `0xAF9d2D3b6717469B21464baA12B022817841952b`）。验证者先试 EIP-191，恢复地址与主人不匹配时再试 EIP-712；文档带可选 `signatureType` 字段（`"eip191"`/`"eip712"`）时优先试对应的方式。任一匹配 → 100 分。**为什么加 EIP-712**：Binance Agent Wallet 的 sign-message 只支持 EIP-712，EIP-191 后端直接拒（错误 351817），用 BAW 签身份挑战必须用 EIP-712。验证者从请求文档取签名，恢复地址，与验证那一刻链上的 `HahaAgentIdentity.ownerOf(agentId)` 比较。
- **主人以验证时为准（R3）**：核对 `ownerOf(agentId)` 以验证者检查那一刻的链上主人为准；请求时与验证时主人不一致（如中间转让了），以验证时的为准。
- **打分**：签名有效且地址匹配 → 100 分；签名无效、地址不匹配、请求文档里没有签名、或请求文档不可读 → 0 分。
- **证据**：`responseURI` 指向验证记录（签名、恢复出的地址、主人地址、核对结果），`responseHash` 为记录的 keccak256。
- **客观性**：密码学验证，完全客观。

### 3.3 不做的验证（L 已定去除）

- **完成任务能力**：已去除。原因是任务本身若开放式则主观性强，验证者没法客观打分。v1 不做，以后若要做须先定义标准测试任务（有确定标准答案的那种）。

### 3.4 请求哈希与请求文档（v1 定义，G3/G4/G5）

- **requestHash 公式（G3）**：`requestHash = keccak256(abi.encodePacked(validatorAddress, agentId, requestURI))`。请求人在链下算好，调 `validationRequest` 时传入；合约链上用同一公式验算，不符则 revert。注：标准只要求 `requestHash` 是对请求数据的承诺（标准 Validation Registry → Validation Request 一节），未规定具体构造；v1 用参数哈希，合约可链上验证；请求文档的内容承诺由 `responseHash` 与证据覆盖。skill.md 写明此公式。
- **请求文档托管（G4）**：请求文档由 agent 主人托管在公开 URL（自己的服务器、haha.meme 提供的 `/validations/` 固定路径，或 IPFS），`requestURI` 支持 `https://` 与 `ipfs://`（验证服务经网关访问）。**身份真实性不能用 IPFS（2026-11-25 修订，L 已定）**：requestHash 由 requestURI 算出，文档里要放对 requestHash 的签名，IPFS 的 CID 又由文档内容决定，循环依赖，放不了。身份真实性用 haha.meme 提供的固定 https 地址：`https://haha.meme/validations/{名字}-{tag}-v{n}.json`（如 `https://haha.meme/validations/ha.haha-identity-v1.json`）。**上传接口（2026-11-25 上线，L 已定）**：没有自己服务器的 agent 主人调 `POST /v1/validations/upload`（索引器 API）自己传文档，服务端验签后自动发布到 `/var/www/validations/`，不用找 C 手动部署。请求体：`{agentId 或 fullName, tag, version, document, signature}`；服务端按 §3.4 公式算 requestHash，恢复签名地址（先 EIP-191 再 EIP-712，与验证者服务同一套逻辑），必须等于上传那一刻链上 `HahaAgentIdentity.ownerOf(agentId)`；文档须合法 JSON、≤64KB、`type` 与 `tag` 一致；任一步失败都拒绝、不写文件；成功返回 `{url, requestHash, agentId}`；每 agent 每天最多 10 次成功上传（超了 429）。接口可达可用 IPFS。
- **文档格式**：JSON，含字段：`type`（`"endpoint-reachable"` 或 `"identity-verified"`）、`endpoint`（接口可达时填，agent 注册文件里 `services[].endpoint` 的地址）、`signature`（身份真实性时填，EIP-191 或 EIP-712 签名，见 §3.2）、`signatureType`（可选，`"eip191"` 或 `"eip712"`，不填则两种都试）。
- **文档不可读**：请求文档不可达、超过 64KB（见 §6.2）、JSON 无效或缺字段 → 验证者提交 0 分，`responseURI` 指向的证据写明原因（如“请求文档无法读取”）。
- **重新验证（G12）**：同一 `requestHash` 再次调 `validationRequest` → revert。想重新验证须换新的 `requestURI`（文档里加时间戳 / nonce），得到新的 `requestHash`。

---

## 4. 验证者与激励（v1：管理员为唯一验证者，无质押、无奖励、无惩罚）

### 4.1 验证者地址（L 已定，R2）

- **合约管理员 = HahaRegistrar 的 admin**，地址 `0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7`，`immutable`，部署时写死（与现有合约一致，无代理、无 Ownable）。
- **v1 验证者 = 管理员** `0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7`，初始值即管理员地址，存为合约存储变量（`public`，可读）。
- **只有管理员能调 `setValidator(address)` 改验证者**；新地址不能为零地址。改验证者不需要重新部署合约——但这只能换一个单一验证者，不能变成多验证者（多验证者是 v2 的逻辑改动，须重新部署，见 §10 第 3 条）。
- **注意（改验证者会停服务）**：若管理员把验证者改成非管理员地址，验证服务（用管理员密钥签名）将无法再提交 `validationResponse`（须由新验证者地址调）。改验证者时，L 须同步更新验证服务的签名密钥为新验证者的密钥，否则验证停摆。v1 原则上不改验证者。
- `validationRequest` 里指定的 `validatorAddress` 必须等于合约存的验证者地址，否则 revert（v1 只认管理员）。
- `validationResponse` 只能由验证者地址调，否则 revert（标准 MUST）。

### 4.2 v1 无质押、无奖励、无惩罚（L 已定）

- **无质押**：验证者是管理员，L 自己做验证者，不用质押 200 积分。质押机制移到 v2。
- **无奖励**：L 自己做验证者，不要积分奖励。验证合约不调 `points.earn`，不登记为 earner。
- **无惩罚**：管理员不会罚自己。超时与虚假验证的惩罚移到 v2。
- **争议在 v1 里有，但很简单**：争议就是验证者第二次复核（见 §5），不用第二验证者、不用质押、不用奖励惩罚。
- **为什么这样设计**：v1 的目标是先把验证结果上链（让第三方能查到“L 验证过这个 agent”），不搞经济机制。经济机制（质押、奖励、惩罚）是 v2 的事，v2 须重新部署新合约（见 §10 第 3 条）。争议在 v1 里已有（见 §5），只是不用质押与奖励惩罚。

### 4.3 升级到 v2 须重新部署合约（回答 L 的问题）

**L 问：以后升级需要重新部署合约吗？答：看升级的是什么。**

- **改参数，不用重新部署**：验证者地址存在存储变量里，管理员调 `setValidator` 就能换，不用重新部署。但这只能换一个单一验证者。
- **加新功能，必须重新部署**：我们的合约全部不可升级（与现有 10 个合约一致，无代理、无 Ownable）。v2 要加质押、奖励、惩罚、第二验证者复验形式的争议、多验证者，都是新逻辑、新函数，现有合约加不进去，必须部署一个新验证合约（`HahaValidationV2`）。
- **迁移很干净**：v1 与 v2 是两个独立合约。v1 的验证记录留在 v1 合约上（可读），新验证走 v2 合约。网站、索引器、skill.md 改指新地址即可。不用迁移数据（验证记录是只追加的，历史记录不用搬）。
- **结论**：v1 先上，v2 重新部署是预期的、正常的。v1 的接口（`validationRequest` / `validationResponse` / 读接口）与 v2 相同，第三方按标准接口调，接口签名不变，但合约地址变了须更新地址（网站、索引器、skill.md 改指新地址，见 §4.3 迁移段）。

---

## 5. 争议流程（v1：验证者第二次复核，L 已定）

### 5.1 争议就是验证者第二次复核

- **争议的定义（L 已定）**：争议就是验证者对同一请求第二次复核。不是第二验证者，不用质押，不用奖励。
- **争议窗口（L 已定）**：验证结果提交后 **3 天内**可争议，过期不能争议。窗口自第一次 `validationResponse` 的时间起算（合约存 `firstResponseTime`，见 §2.4）。窗口自第一次结果起算，验证者后续更新结果不延长窗口。
- **窗口边界**：争议须在 `block.timestamp <= firstResponseTime + 3 天` 时提交，第 3 天整点仍可争议，超过则 revert。
- **最多争议一次（L 已定）**：每个请求最多争议一次。争议复核后，不可再对同一请求调 `dispute`（争议渠道已用完）。
- **前置条件**：该 `requestHash` 至少已有一次 `validationResponse`（有结果才能争议），否则 `dispute` revert。
- **流程**：
  1. 任何人可调验证合约的 `dispute(requestHash)`，标记一次验证结果有争议（发 `ValidationDisputed` 事件）。v1 争议不用质押。须在争议窗口内（第一次结果提交后 3 天内），过期 revert；同一请求已争议过，再调 `dispute` revert。
  2. 验证者（管理员）重新检查，调 `validationResponse` 再次提交结果（标准允许对同一 `requestHash` 多次调 `validationResponse`，标准 Validation Registry → Validation Response 一节）。
  3. 比较两次结果，**确实错了就改判，没错就维持原判**：
     - **第二次与第一次一样 → 维持原判，驳回上诉**。原验证结果继续有效。
     - **第二次与第一次不一样 → 改判**。新结果取代旧结果，成为该请求的当前验证结果。
- **读接口**：`getValidationStatus` / `getAgentValidations` 返回每次请求的最新结果（多次 `validationResponse` 里最后一次的）。历史结果保留在事件里，可查。验证者也可按标准多次调 `validationResponse` 更新结果；争议复核后，不可再对同一请求调 `dispute`（争议渠道已用完）。注意：“最终”指争议渠道已用完，不是指结果不可改——验证者仍可按标准再次调 `validationResponse` 更新结果，更新后的最新结果即为当前结果，但无人能再就此请求发起争议。

### 5.2 v1 争议的特点

- 不用第二验证者（v1 只有管理员一个验证者）。
- 不用质押（争议者不用押 200 分，验证者也不用押）。
- 不用奖励与惩罚（验证者是管理员，L 自己做验证者，不罚自己）。
- **免费争议滥用（R1，v1 接受风险）**：争议零成本，任何人都能调 `dispute` 逼验证者复核。v1 接受这个风险，理由有三：(1) 复核成本低——重跑一次检查，验证服务自动做，不用人手；(2) 同一 `requestHash` 最多争议一次，已限流，滥用者无法对同一请求反复争议；(3) 争议窗口 3 天，过期不能争议。若滥用严重（大量不同请求被恶意争议、拖住验证服务），v2 再加争议质押。

### 5.3 v2 的争议（以后再做）

- v2 多验证者时，争议可升级为第二验证者复验（争议者质押 200 分成为第二验证者，见 v1 前版本的讨论记录：结果一致驳回、争议者丢 50 分；结果不一致成立、验证者 A 丢 100 分、争议者拿 50 分奖励）。
- v2 须重新部署新合约。

---

## 6. 验证者服务（链下程序，跑在 L 的服务器上）

### 6.1 背景（L 已定）

- **v1 验证者就是管理员**，L 自己做验证者。验证程序部署在 L 的服务器上（Vultr，`<SERVER_IP>`），用管理员密钥签名，实时响应。
- 管理员密钥已在服务器上（`/etc/haha/admin-signer.env`，0600，root），第一季自动化在用，不用另写密钥。**v1 不需要新的验证者钱包私钥**，直接用管理员密钥。
- 不需要解决 `.ai` 私钥托管问题（v1 验证者是管理员，不是 `.ai` 持有人）。

### 6.2 服务设计（C 写，C 部署在服务器上）

- **程序**：Python 服务（`validator-service.py`），同时轮询验证合约的 `ValidationRequest` 与 `ValidationDisputed` 两个事件（G15，用 BSC RPC 轮询，每 30 秒查一次新事件）。服务用服务器已配置的 BSC RPC（与索引器同一组 BSC_RPC_URLS，见 `/etc/haha/indexer.env`），不直连公开节点。
- **流程**：
  1. 收到 `ValidationRequest`，检查 `validatorAddress` 是否等于当前验证者（不是当前验证者的请求忽略）；按 §3.4 公式验算 `requestHash`（链上已验过，服务侧复核）。服务每次发 `validationResponse` 前读链上当前验证者地址，确认与签名密钥对应地址一致，不一致则记日志并停发（等 L 更新密钥配置）。
  2. 拉 `requestURI` 指向的请求文档（G5）：只接受 `https://` 与 `ipfs://`（经网关）；超时 10 秒；最大 64KB；超限 / 拉取失败 / JSON 无效 / 缺字段 → 提交 0 分，证据写明原因。
  3. 按 §3 的方法检查：
     - 接口可达：先核对 endpoint 在注册文件里（取 agentURI 读注册文件），不在则 0 分；再 GET（超时 10 秒），GET 返回 405 则改 POST 空 JSON；按 §3.1 的打分表打分，记录请求方法、状态码与响应时间。
     - 身份真实性：从请求文档取签名，恢复地址，与验证那一刻链上的 `HahaAgentIdentity.ownerOf(agentId)` 比较（R3，以验证时为准）。签名恢复先试 EIP-191（eth_account 的 EIP-191 消息编码恢复地址），不匹配再试 EIP-712（`IdentityChallenge{agentId, requestHash}`，domain HahaValidation/1/56/主网合约地址，eth_account 的 `encode_typed_data` 恢复地址）；文档带 `signatureType` 字段时优先试对应的方式。任一匹配 → 100 分，否则 0 分。
  4. 收到 `ValidationDisputed`，重新检查（重跑第 2–3 步），调 `validationResponse` 提交新的验证结果（G15）。
  5. 调验证合约的 `validationResponse(requestHash, response, responseURI, responseHash, tag)` 提交结果（用管理员钱包签名，gas 固定 1 gwei，与第一季自动化一致）。
  6. 发交易加 nonce 冲突重试（G16）：发前取最新 nonce；遇 nonce 错误（nonce too low / already used / replacement underpriced）用新 nonce 重试最多 3 次，间隔 1s / 2s / 4s；合约 revert 不重试，记日志。
  7. 写日志（`/opt/haha-validation/validator.log`），记录每个请求的检查结果与交易哈希。
- **事件进度持久化**：服务把已处理的最新区块号存在 `/opt/haha-validation/state.json`，重启后从该区块继续轮询；首次运行从验证合约部署区块开始。避免重启后重复提交或漏事件。
- **日志轮转**：`/opt/haha-validation/validator.log` 用 logrotate 按周轮转，保留 4 周。
- **运行**：systemd 服务 `haha-validator.service`，开机自启，失败自动重启（`Restart=on-failure`，与第一季签名服务一致）。**注意**：不要用 `Restart=on-failure` + 短 `RestartSec` 造成无限重启循环（第一季 haha-daily-ops 曾重启 587 次的教训）；设 `RestartSec=60`，并监控重启次数。
- **宕机处理（G17，L 已定）**：验证服务宕机不发外部告警，写日志（`/opt/haha-validation/validator.log`），systemd 自动重启，尽快恢复启动。v1 无超时惩罚，请求一直挂着直到服务恢复后响应。
- **实时性要求（L 已定）**：v1 虽然无超时惩罚，但验证程序必须保证实时验证、不超时。轮询间隔 30 秒，收到请求后立即检查并提交结果，目标是在几分钟内完成验证（不是等 1 天）。
- **上传接口（2026-11-25 上线，L 已定）**：`POST /v1/validations/upload` 是索引器 API（`haha-api`）的一个路由，不是验证者服务的一部分。实现在 `indexer/api.py`（`h_validations_upload`），流程：由 agentId/fullName + tag + version 拼出目标 URL；按 §3.4 公式算 requestHash；用 eth_account 恢复签名（先 EIP-191 再 EIP-712，与验证者服务同一套逻辑）；恢复地址必须等于上传那一刻链上 `HahaAgentIdentity.ownerOf(agentId)`（读链上，不读库；`validator()` 与 `getIdentityRegistry()` 也从 HahaValidation 合约链上读）；文档检查（合法 JSON、≤64KB、`type` 与 `tag` 一致、identity-verified 含 `signature`、endpoint-reachable 含 `endpoint`）；全部通过才原子写文件（临时文件 + `os.replace`，chmod 644）到 `/var/www/validations/`（属主 haha:haha，755；nginx `location /validations/` 从该目录提供静态文件）。失败返回 400/403/404 带机器可读错误码；每 agent 每天最多 10 次成功上传（内存计数，超了 429）。`haha-api.service` 须加 `ReadWritePaths=/var/www/validations`（`ProtectSystem=strict` 下否则写不进去）。eth_account 须装在服务器系统 Python 上（`pip3 install --break-system-packages --ignore-installed typing-extensions eth-account`），上传处理函数懒加载，缺依赖时只影响上传端点（500 `upload_unavailable`），不影响整个 API。测试 30/30 通过（含 anvil 端到端：上传 → validationRequest → 验证者服务提交 100 分）。

---

## 7. 索引器接入（C 做）

### 7.1 事件解码

- `indexer/common.py`：加验证合约地址到 CONTRACTS，加 3 个事件到解码表（`ValidationRequest`、`ValidationResponse`、`ValidationDisputed`，topic0 用 keccak256 算，与合约事件签名逐字对齐，签名见 §2.3）。`ValidationDisputed` 是 v1 新增的非标准事件（见 §2.3），须在文档里注明。
- 只加新事件，现有事件不动（与 E14、G4 同样的只加不改原则）。

### 7.2 API（只读，新增）

| 接口 | 返回 | 说明 |
|---|---|---|
| `GET /v1/agents/{agentId}/validations` | 该 agent 的全部验证记录（请求 + 最新结果 + 验证者 + tag + 分数 + 争议状态） | 读索引器库（由事件同步），不调链上 RPC |
| `GET /v1/validations/{requestHash}` | 一次验证请求的详情（请求 + 最新结果 + 争议状态） | 同上 |

- 不加 POST（验证请求与结果走链上，不走 API）。
- 响应头：`Content-Type: application/json`，`Cache-Control: no-store`。
- **争议状态推导（G14）**：`GET /v1/validations/{requestHash}` 返回 `disputeStatus`、`disputeCount`（0 或 1）、`originalResponse`、`latestResponse`。推导规则（按事件顺序）：
  - 无 `ValidationDisputed` 事件 → `not_disputed`（未争议）；
  - 有争议事件且之后无 `validationResponse` → `disputed`（争议中）；
  - 有争议事件且之后有 `validationResponse`，且结果与争议前相同 → `upheld`（已复核-维持原判）；
  - 有争议事件且之后有 `validationResponse`，且结果与争议前不同 → `overturned`（已复核-改判）。
  - `originalResponse` 为争议前最后一次 `validationResponse` 的结果；`latestResponse` 为最新一次 `validationResponse` 的结果；无争议时两者相同。

### 7.3 代码位置

- 服务器 `/opt/haha-indexer/common.py`（加事件解码）与 `/opt/haha-indexer/api.py`（加两个 handler）。
- 私密库 `indexer/common.py` 与 `indexer/api.py` 一并提交（PR 里同步，与 G4、E14 同样的流程）。
- **公开库 indexer 的同步另待 L 决定**（E14 与 G4 的公开库同步也还待定，一并问 L）。

---

## 8. 网站接入（C 做）

### 8.1 agent 页（展示验证）

- `web/site/agent.html`：在 agent 信息区加一块“验证”，显示：
  - 验证记录列表（从 `GET /v1/agents/{agentId}/validations` 读）：每条显示 tag（接口可达 / 身份真实性）、分数（0 或 100）、验证者、验证时间（最新一次 validationResponse 的时间，即 lastUpdate）、证据链接（`responseURI`）、争议状态（未争议 / 争议中 / 已复核-维持原判 / 已复核-改判）。
  - 验证者显示（G18）：有 `.ai` 显示 `.ai`，没有 `.ai` 就写“管理员验证”（v1 验证者恒为管理员，管理员地址无 `.ai` 时显示“管理员验证”）。
  - 一行说明文字：“验证由 HahaValidation 提供，v1 验证者为项目管理员。验证结果由管理员实际检查得出，不代表项目方背书。”（中英双语，i18n key）。
  - 无验证记录时显示“暂无验证记录”（中英双语，i18n key `agent.noValidations`）。
- 需要的新 i18n key（中英文各一）：
  - `agent.validation`：中文“验证”，英文“Validation”。
  - `agent.validationNote`：中文说明文字，英文说明文字。
  - `agent.noValidations`：中文“暂无验证记录”，英文“No validations yet”。

### 8.2 不改的页面

- 评分入口、市场、第一季、scan 等页面不动（除 i18n 版本号外）。
- **注意：** 若 agent.html 加了新 i18n key，i18n.js 要升版本（v56 → v57），10 个 HTML 页的引用同步改（与 G4、E14 同样的流程）。

### 8.3 验证入口（v1 最小版）

- agent 页加一个“请求验证”按钮（仅 agent 主人可见，fail-closed：只有取到当前登录的 .ai 对应地址、且与该 agent 的持有人地址相同，才显示；取不到任一地址时隐藏）。
- 点击后复制一段 `validationRequest` 指令（skill.md 新定义的操作），用户把指令交给自己的 agent 去执行，指令里指定验证者地址为管理员地址（v1 只认管理员，改了请求会 revert，见 §4.1，用户不可改）。指令里含 `requestHash` 的计算公式（§3.4），agent 按公式链下算好 `requestHash` 再调 `validationRequest`；`requestURI` 为 agent 主人托管的公开 URL（§3.4）。指令第一步是先把请求文档（JSON，见 §3.4）放到公开 URL（自己的服务器或 IPFS），再算 `requestHash`、再调 `validationRequest`；文档没放好就调 `validationRequest`，验证者会判 0 分。
- 需要的新 i18n key：`agent.requestValidation`（中文“请求验证”，英文“Request validation”）。

---

## 9. skill.md 更新

- 在 skill.md 里加一节“验证注册表”，写明：
  - 验证合约地址（部署后填）。
  - 验证请求与验证结果的操作（`validationRequest` / `validationResponse` 的 selector 与参数）。
  - 争议操作 `dispute`（任何人可调）与管理员操作 `setValidator`（只有管理员能调）的 selector 与参数。
  - `requestHash` 与 §3.4 公式不符会 revert（链上验算）。
  - `requestHash` 计算公式（§3.4）：`keccak256(abi.encodePacked(validatorAddress, agentId, requestURI))`。
  - 请求文档格式与托管要求（§3.4）：JSON，agent 主人托管在公开 URL，支持 `https://` 与 `ipfs://`；身份真实性不能用 IPFS，必须用 haha.meme 提供的 `/validations/` 固定 https 地址（循环依赖，见 §3.4）。
  - 请求文档须先托管再调 `validationRequest`（§3.4）。
  - 两类验证的含义与检查方法（§3）；身份真实性两种签名都认（EIP-191 与 EIP-712，见 §3.2），Binance Agent Wallet 只支持 EIP-712。
  - v1 验证者为管理员，无质押、无奖励、无惩罚；争议就是验证者第二次复核（§5），争议窗口 3 天，每请求最多一次，复核后确实错了改判、没错维持原判。
  - 验证者服务由 C 部署并运行在服务器上（2026-11-25 L 改定，不再是 L 部署）。
- 按 L 的规则：版本号 v15 → v16，改“最后更新”日期，不写更新日志。
- **第 16 节 JSON 必须更新**：把验证合约地址、验证接口加进 §16 JSON（v1 无质押与激励参数，不加）。
- 同步更新两份部署脚本里的 skill.md 期望 sha256（`~/workspace/season-snapshot-v2-deploy.sh` 的 `EXPECTED_SKILL_SHA` 与 `~/workspace/security-fixes-deploy.sh` 的 `EXPECTED_SKILL_SHA256`）。

---

## 10. 冻结确认（2026-11-25，L 已确认全部 3 件）

1. **v1 方案确认**：管理员为唯一验证者，中心化；无质押、无奖励、无惩罚；争议就是验证者第二次复核（第二次与第一次一样维持原判、驳回上诉，不一样则改判），争议窗口 3 天，每个请求最多争议一次；只做接口可达与身份真实性两类验证。——**L 已确认。**
2. **升级路径确认**：以后加质押、奖励、惩罚、第二验证者复验形式的争议、多验证者须重新部署新合约（v2），v1 合约废弃（记录可读）。改验证者地址不用重新部署（调 `setValidator`）。——**L 已确认。**
3. **验证者服务部署**：C 写好程序后，L 在服务器上部署（用已有的管理员密钥，不用新写密钥），程序须保证实时验证、不超时。——**L 已确认。**

**审计修订（2026-11-25，L 授权）**：同日 L 授权全面修订，审计找出的 12 处错误（E1–E12）已修、18 处缺口（G1–G18）与 3 处设计风险（R1–R3）已补进计划，上述 3 件冻结决策不变。

---

## 11. 测试计划

### 11.1 合约测试（D 做，上主网前必须全过）

| # | 测试 | 通过标准 |
|---|---|---|
| T1 | 接口签名核对 | 标准接口（`validationRequest` / `validationResponse` / `getValidationStatus` / `getSummary` / `getAgentValidations` / `getValidatorRequests`）与 2 个标准事件（`ValidationRequest` / `ValidationResponse`）对照 EIP-8004 标准原文逐字核对，全部一致；v1 新增的 `dispute` / `setValidator` 与 `ValidationDisputed` 事件对照 §2.5 / §2.3 的定义核对 |
| T2 | 验证者限制 | 非管理员调 `validationResponse` → revert；`validationRequest` 里验证者地址不是管理员 → revert；管理员调 `setValidator` 可换验证者；非管理员调 `setValidator` → revert；换验证者后旧验证者调 `validationResponse` → revert、新验证者可调 |
| T3 | 验证请求 | agent 主人调 `validationRequest` 成功；agent 的 operator 调 `validationRequest` 成功；非主人、非 operator 调 → revert；传入的 `requestHash` 与 §3.4 公式不符 → revert；同一 `requestHash` 再次调 `validationRequest` → revert |
| T4 | 验证结果 | 管理员调 `validationResponse` 成功，分数 0–100；`response` 超过 100 → revert；对不存在的 `requestHash` 调 `validationResponse` → revert；同一请求多次回应 → 后一次覆盖前一次（标准允许） |
| T5 | 争议复核 | 任何人调 `dispute(requestHash)` 标记争议（结果提交后 3 天内），验证者再次调 `validationResponse` 提交相同结果 → 原判维持；提交不同结果 → 新结果取代旧结果；读接口返回最新结果；同一请求第二次调 `dispute` → revert；超过 3 天调 `dispute` → revert；对无验证结果的请求调 `dispute` → revert；`dispute` 可由任意第三方调（非 agent 主人、非验证者）；边界：`firstResponseTime + 3 天`整点调 `dispute` 成功；`+ 3 天 + 1 秒`调 `dispute` → revert |
| T6 | 读接口 | `getValidationStatus` 返回 `(validatorAddress, agentId, response, responseHash, tag, lastUpdate)`，与写入一致；`getSummary(agentId, [], tag)` 返回 `(count, averageResponse)`，count 为符合过滤的请求数，averageResponse 为各请求最新结果的平均（整数除法）；`getAgentValidations` 返回该 agent 的全部 requestHash；`getValidatorRequests` 返回该验证者的全部 requestHash；最新结果与请求哈希经 `getAgentValidations` + `getValidationStatus` 可取得 |

### 11.2 索引器、网站与验证者服务测试（C 做，上线前必须全过）

| # | 测试 | 通过标准 |
|---|---|---|
| T7 | 事件解码 | 服务器解码测试：验证的 3 个事件（签名见 §2.3，含 indexed）都能解出字段，现有事件不受影响 |
| T8 | API 返回 | `GET /v1/agents/{agentId}/validations` 返回 200，列表与链上一致；`GET /v1/validations/{requestHash}` 详情正确，含 `disputeStatus` / `disputeCount` / `originalResponse` / `latestResponse`，四种争议状态推导正确（未争议 / 争议中 / 已复核-维持原判 / 已复核-改判） |
| T9 | 网站展示 | agent 页验证块正常显示，说明文字中英双语都显示，不空白；验证者无 `.ai` 时显示“管理员验证”；“请求验证”按钮 fail-closed（非主人不显示） |
| T10 | 验证者服务 | 测试网跑验证服务：收到请求后几分钟内响应（轮询 30 秒 + 检查 + 交易确认）；接口可达检查正确（2xx、401、404、405 改 POST、5xx、超时各测一次）；身份真实性检查正确（签名有效/无效各测一次；EIP-712 签名有效/无效各测一次，EIP-191 回归测一次）；收到 `ValidationDisputed` 后重新检查并提交新结果；nonce 冲突重试 3 次成功；交易成功上链；请求文档拉取失败模式：文档不可达 / 超过 64KB / JSON 无效 → 提交 0 分并写明原因；`validatorAddress` 不是当前验证者的请求 → 服务忽略、不提交 |
| T11 | 现有功能回归 | 走一遍主链路：铸名、激活、打分、挂单、第一季申请入口显示，全部正常 |

### 11.3 上线后验证（部署后立即做）

| # | 验证 | 通过标准 |
|---|---|---|
| V1 | 线上取验证记录 | 线上 `GET /v1/agents/{agentId}/validations` 返回 200 |
| V2 | 线上 i18n 版本 | 线上 agent.html 引用的是新版 i18n.js（v57），新标签正常显示、不空白 |
| V3 | 验证者服务运行 | 服务器上 `haha-validator.service` 为 active，日志里有启动记录，无报错 |
| V4 | 线上现有功能 | 首页、市场、ERC-8004 页、第一季页均 200，关键内容正常显示 |
| V5 | 验证合约验证 | BscScan 上验证合约源码已验证，地址与 skill.md、网站文档一致 |

---

## 12. 部署步骤

### 12.1 备份（动手前）

- 备份服务器 `/opt/haha-indexer/common.py` 与 `/opt/haha-indexer/api.py`（复制一份带时间戳的 .bak，放同一目录）。
- 备份本地工作目录的 `web/site/js/i18n.js`、`web/site/agent.html`、`web/site/skill.md`（若改）。
- 记下备份位置。验证通过后删除备份（见 12.5）。

### 12.2 版本号

| 文件 | 改前 | 改后 | 同步改动 |
|---|---|---|---|
| `js/i18n.js` | v56 | v57 | 10 个 HTML 页的 `i18n.js?v=56` 引用全部改成 `?v=57`。**10 个页：index.html、market.html、erc8004.html、agent.html、earn.html、how.html、season.html、season-checklist.html、scan.html、api.html。** tasks.html、games.html 是纯跳转页，不加载 i18n.js，不在内。 |
| `web/site/skill.md` | v14 | v15 | 改“最后更新”日期；两份部署脚本的期望 sha256 同步更新 |
| `js/scan.js` | v6 | 不变 | G13 不改 scan.js |

- **push 前复查 HTML 版本号**（教训：PR #89 曾发了旧版 scan.html）。push 前 grep 核对 10 个 HTML 页的 i18n.js 引用全是 v57。

### 12.3 部署顺序

1. D 在测试网部署验证合约，跑 T1–T6，全部通过。
2. L 批准主网部署；D 部署主网，BscScan 验证源码，C 核对地址与接口。
3. L 在服务器上部署验证者服务（C 写好程序，用已有的管理员密钥），服务启动，做一次生产检查（服务正常轮询、无报错）。T10 已在测试网通过（开发阶段，见 §15 步骤 5），本步不重跑 T10。
4. C 更新服务器 `/opt/haha-indexer/common.py` 与 `api.py`，重启 `haha-api`（避开 08:00 运营窗口），curl 验证新接口返回正确（T7、T8）。
5. C 更新网站（从**当前线上发布目录** `cp -a` 建新发布目录，替换 i18n.js、agent.html 与 10 个 HTML 页的引用，翻软链），跑 T9、T11。
6. **清 Cloudflare 缓存（L 操作，按需）**：2026-11-25 L 定下，常规更新不再等 L 清缓存；只有关键修复才需要清，到时 C 直接跟 L 说。G13 不属于关键修复，部署后不主动要求清缓存。
7. curl 核对：线上 i18n.js 与 skill.md 的 md5 与仓库一致，agent.html 引用 i18n.js?v=57，首页、agent.html、season.html 均 200。
8. 做 §11.3 的上线后验证（V1–V5）。

### 12.4 GitHub（私密库）

- 分支 `c/g13-validation-registry`，提交信息“提交人C”格式，PR 注明提交人C，C 直接合并，合并后汇报写明是 C 合并的。
- **L 决定（2026-11-25）：PR 不加 review，由 C 直接完成合并、拉取、推送等全部工作。**
- PR 内容：D 的合约源码（`src/HahaValidation.sol`）、验证者服务程序（`tools/validator-service.py`）、i18n.js、agent.html、10 个 HTML 页的引用、skill.md、`indexer/common.py`、`indexer/api.py`、测试脚本。
- **合约源码放私密库 `src/`（与现有 10 个合约一致）。** 公开库是否同步，另待 L 决定。
- **不推公开库。** 公开库的同步另待 L 决定。

### 12.5 删备份

- 上线后验证（V1–V5）全部通过后，删除 12.1 的备份文件。
- 若任一验证失败，立刻回滚（见第 13 节），不删备份。

---

## 13. 风险与回滚

| 风险 | 影响 | 缓解 / 回滚 |
|---|---|---|
| 验证合约有 bug（如验证逻辑错、争议复核比较错） | 验证结果算错；合约不可升级，修要重部署新验证合约 | 测试网 T1–T6 全过才上主网；D 写完、C 复核、L 批准；若主网上发现 bug，部署新版验证合约（老合约废弃，网站切到新地址） |
| L 的验证者服务宕机 | 验证请求无人响应，agent 主人等不到结果 | systemd 自动重启（`RestartSec=60`，监控重启次数，避免第一季 587 次循环的教训）；写日志（`/opt/haha-validation/validator.log`），不发外部告警，尽快恢复启动；v1 无超时惩罚（管理员不会罚自己），请求一直挂着直到服务恢复后响应 |
| 争议者滥用免费争议 | 任何人零成本调 `dispute`，反复逼验证者复核，验证服务被拖住（v1 无质押，无法罚滥用者） | 争议窗口 3 天、每请求最多争议一次（§5）；滥用严重时 v2 再加争议质押（见 §5.2） |
| 验证者坚持错误结果 | v1 只有管理员一个验证者，争议复核也是管理员自己做，链上无人能强制改判 | 结果与证据全公开，人人可复查，错了大家都看得见；公平靠透明，不靠去中心化（v2 多验证者后靠机制制衡） |
| haha-api 重启导致 API 短暂不可用 | 重启期间（几秒）所有 /api/ 调用失败 | 重启是几秒的事，索引器一直在跑不丢数据；选在非 08:00 时段重启，重启后立即 curl 验证 |
| i18n.js 版本号漏改 | 新标签显示空白 | push 前 grep 复查；上线后 V2 验证；回滚：修正版本号重新发布 |
| 验证合约地址填错（skill.md/网站文档） | 第三方按错误地址调合约，失败 | 部署后 C 核对三处地址一致（合约部署记录、skill.md、网站文档）；V5 验证 BscScan 地址 |
| 新接口无专门监控 | 验证接口出问题（如 500 率升高）不能及时发现 | 与 G4 相同，v1 明确暂不补接口级告警；若以后第三方依赖加深，再补 |
| 验证者钱包私钥泄露（即管理员密钥泄露） | 管理员密钥控制全部 admin 功能（验证、第一季、积分、注册），泄露即全系统管理员权限失守；攻击者也能调 `setValidator`，改验证者地址不能止血 | 根本防线是密钥绝不泄露：只在服务器 `/etc/haha/admin-signer.env`（0600，root），不出服务器、不进 GitHub、不进聊天、不进备份；v1 没有单独的验证者密钥。若泄露，属于全系统安全事件，须按应急流程处理（立即评估影响、必要时停相关服务），不能只靠调 `setValidator` 解决。 |

**回滚原则：** 任一上线后验证（V1–V5）失败，立刻回滚到上一个发布目录（翻软链回旧版）并恢复 api.py/common.py 备份，重新做验证。不带病上线。**合约本身不可回滚**（已部署即存在）；若合约有 bug，部署新版验证合约并切网站与文档到新地址，老合约废弃。**验证者服务可随时停**（systemctl stop），停了只影响新验证请求，不影响现有功能。

---

## 14. 验收标准（全部满足才算完成）

- [ ] 验证合约在测试网 T1–T6 全部通过，主网已部署且 BscScan 验证通过。
- [ ] 验证合约地址已记录，skill.md、网站文档、API 里的地址一致。
- [ ] 链上验证请求→验证结果→争议复核全流程在主网可走（用测试 agent 验证）。
- [ ] 验证者服务在服务器上运行正常（T10 通过），用管理员密钥签名。
- [ ] 索引器能解码验证的 3 个事件，API 返回与链上一致。
- [ ] agent 页验证块正常显示，说明文字中英双语都显示，“请求验证”按钮 fail-closed。
- [ ] 主链路回归（T11）全部正常。
- [ ] skill.md 已更新为 v15，版本号与日期已改，无更新日志，§16 JSON 已同步。
- [ ] 线上验证 V1–V5 全部通过。
- [ ] 备份已删，PR 已合并到私密库 main（C 合并）。

---

## 15. 分工与顺序

| 步骤 | 做什么 | 谁 | 前置 |
|---|---|---|---|
| 0 | 冻结本文档（已完成：2026-11-25 L 确认 v1 方案；同日 L 授权全面修订，审计修订版已冻结） | L | — |
| 1 | D 写验证合约（Solidity），按 §2 的接口与返回值表写，逐字核对接口与事件签名 | D | 0 |
| 2 | D 在测试网部署，跑 T1–T6，C 复核测试结果 | D（C 复核） | 1 |
| 3 | L 批准主网部署 | L | 2 |
| 4 | D 部署主网，BscScan 验证源码，C 核对地址与接口 | D（C 核对） | 3 |
| 5 | C 写验证者服务程序，L 在服务器上部署（用已有的管理员密钥），服务启动，跑 T10 | C 写，L 部署 | 0（可与步骤 1 并行） |
| 6 | C 更新索引器（common.py 事件解码 + api.py 新接口），重启 haha-api，跑 T7–T8 | C | 4 |
| 7 | C 更新网站（agent 页验证块 + i18n.js v57），跑 T9、T11 | C | 6 |
| 8 | C 更新 skill.md 到 v15，同步两份部署脚本的期望 sha256 | C | 7 |
| 9 | 推私密库 PR（含合约源码、验证者服务程序、i18n.js、agent.html、10 个 HTML 页引用、skill.md、indexer/common.py、indexer/api.py），C 直接合并 | C | 7、8 |
| 10 | 部署上线，做 V1–V5 验证 | C | 9 |
| 11 | 验证通过后删备份，向 L 汇报 | C | 10 |

- D 写合约，C 复核测试结果与接口；C 做索引器、网站、skill.md、验证者服务程序；L 冻结计划、批准主网部署、在服务器上部署验证者服务、担任唯一验证者（v1 无 earner/spender 登记、无质押）。
- 每步做完先验证再往下走，任何一步失败就停下、保留现场、向 L 汇报，不硬闯。
- **C 与 D 并行：** 步骤 5（验证者服务程序）可在 D 写合约的同时做；步骤 7–9（C 的索引器与网站工作）可在 D 写合约的同时准备（事件解码表、API 骨架、网站文案），但正式接入须等主网地址确定（步骤 4 之后）。

---

## 16. 不在本计划内的事（以后另立计划）

- 完成任务能力验证（L 已定去除，v1 不做）。
- 验证者声誉排行（按验证准确率排行验证者）。
- 验证市场（agent 主人出价请人验证）。
- 第三轮仲裁（争议的争议）。
- NameWrapper（G15/G16）：下一件，按 G4→G9（已否决）→G13→NameWrapper 的顺序排在 G13 之后。
- 链上元数据 `getMetadata` / `setMetadata`、`setAgentWallet`（G2/G3）：不在 G13 里做。
- x402（G14）：不是合规必需，新功能，另议。
- 公开库 skill.md、合约源码与 indexer 的同步（待 L 决定）。

---

## 附录：L 已定的事项（2026-11-25）

1. 验证者：v1 指定管理员为唯一验证者，中心化；L 自己做验证者，不要奖励。
2. 超时与惩罚：v1 没有超时惩罚（管理员不会罚自己）。超时 1 天扣 100 分、质押 200 分全部移到 v2。**但验证程序须保证实时验证、不超时**（30 秒轮询，几分钟内完成验证）。
3. 验证类型：只做接口可达与身份真实性，完成任务能力去除。
4. 争议：争议就是验证者第二次复核，第二次与第一次一样就维持原判、驳回上诉，不一样则改判；争议窗口 3 天，每个请求最多争议一次；确实错了就改判，没错就维持原判（L 已定，见 §5）。第二验证者复验、质押、罚没、奖励移到 v2。
5. 升级：以后加质押、奖励、惩罚、第二验证者复验形式的争议、多验证者须重新部署新合约（v2）；改验证者地址不用重新部署（调 `setValidator`）。
6. G9 已否决：不做假装兼容的包装（2026-11-25，L 决定）。
7. `.ai` 私钥由币安托管，不能放服务器：v1 验证者是管理员（私钥在服务器上），没有这个问题；v2 多验证者时须用操作员热钱包设计。
8. 审计修订：2026-11-25 L 授权全面修订，审计找出的 12 处错误（E1–E12）已修、18 处缺口（G1–G18）与 3 处设计风险（R1–R3）已补进计划；冻结决策不变。验证合约的管理员 = HahaRegistrar 的 admin（immutable）；agent 页验证者无 `.ai` 时写“管理员验证”；验证服务宕机写日志、不发外部告警，systemd 自动重启、尽快恢复启动。
