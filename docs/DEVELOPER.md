> 这是私有开发库里的开发索引，方便对照规格和测试。产品说明以仓库根目录的 README.md 为准。
> 文中「DEPLOYED.md 尚未创建」是 2026-11-20 的旧状态；主网回执现已写在 `docs/contracts/DEPLOYED.md`。
>
> 公开库是完整镜像，只排除密钥、密码和服务器 IP。第二轮补上的目录：
> - `ops/`：systemd、nginx 样例、环境变量名、第一季和验证者的运行记录
> - `docs/ops/`：索引器已知问题和 Haha Dog 网站三轮说明
> - `legacy/`：根目录旧版页面（`legacy/root-site/`）和 2026-11-27 网站备份

# haha.meme

haha.meme 是 BNB Smart Chain 上的 AI agent 身份协议。持有币安 `.ai` 名字的钱包可以免费铸造永久的 `.haha` 或 `.meme`。名字是可交易的 ERC-721。持有人可以设置解析记录、主名字、ERC-8004 agent 身份和链上积分。

网站域名是 `haha.meme`。阶段一已有合约实现、完整测试和部署脚本。**

第一季开工从 [`docs/season1/kickoff/README.md`](docs/season1/kickoff/README.md) 进入。文档还在 PR #45 上时，读分支 `cursor/season1-d-docs-a3d0`，不要只看 `main`。

> **状态（2026-11-20）**：合约、测试、部署脚本已交付，见下文「开发」一节。
> `docs/contracts/DEPLOYED.md` 尚未创建 —— 按规格要求，真正部署后才生成。

## 谁写什么

| 角色 | 负责 |
| --- | --- |
| D | 全部合约、单元 / 模糊 / 不变式 / BSC 主网 fork 测试、部署脚本、审计配合 |
| 文档维护方（bot） | 本仓库的规格、黑名单、保留名、SVG 资产；以后的网站 |
| owner | 产品决定。管理员是硬件钱包单签，见规格里的地址 |

D 不要在规格之外增加管理员函数。规格没写的阶段二功能只留挂钩，不要现在做。

## 怎么读

1. [`docs/contracts/SPEC.md`](docs/contracts/SPEC.md) 是编码依据。架构、每个合约的存储和函数、管理员权限、测试清单、部署核对、未决问题都在这里。
2. [`docs/contracts/blacklist-v2.md`](docs/contracts/blacklist-v2.md) 和 [`docs/contracts/reserved-names.md`](docs/contracts/reserved-names.md) 是名单源。
3. [`docs/contracts/SVG.md`](docs/contracts/SVG.md) 规定 `tokenURI` 如何在读取时拼出已批准的 SVG。
4. [`docs/CHANGELOG.md`](docs/CHANGELOG.md) 记录已经拍板的决定。改规格先改 CHANGELOG。

实现阶段新增的文档：

5. [`docs/contracts/QUESTIONS.md`](docs/contracts/QUESTIONS.md)：开工前提出的 11 条疑问与 owner 的裁决，含「裁决执行记录」表。
6. [`docs/contracts/AUDIT.md`](docs/contracts/AUDIT.md)：自审计报告。列出全部发现的问题（含两个真实 bug）、构建信息、遗留风险。
7. [`docs/contracts/SPEC-COVERAGE.md`](docs/contracts/SPEC-COVERAGE.md)：`SPEC 12` 测试清单逐项打勾，每条指向实际测试函数。
8. [`docs/contracts/INDEXING.md`](docs/contracts/INDEXING.md)：给索引器实现方的 7 条注意事项。
9. [`docs/contracts/DEPLOY.md`](docs/contracts/DEPLOY.md)：部署流程与故障排查。
10. [`docs/website/PLAN.md`](docs/website/PLAN.md) 是网站规划 v0.1。
11. [`docs/website/DEPLOY.md`](docs/website/DEPLOY.md) 是网站预览站的发布记录和上线步骤。

函数名、事件名、字段名用英文。说明文字用简体中文。

## 仓库布局

```text
README.md
docs/CHANGELOG.md
docs/website/PLAN.md
docs/website/DEPLOY.md          网站预览站的发布记录
docs/contracts/SPEC.md
docs/contracts/SVG.md
docs/contracts/blacklist-v2.md
docs/contracts/blacklist-v2.txt
docs/contracts/blacklist-v2.hashes.txt
docs/contracts/reserved-names.md
docs/contracts/reserved-names.hashes.txt
docs/contracts/QUESTIONS.md          开工前的疑问与裁决
docs/contracts/AUDIT.md              自审计报告
docs/contracts/SPEC-COVERAGE.md      SPEC 12 清单对照
docs/contracts/INDEXING.md           索引器注意事项
docs/contracts/DEPLOY.md             部署流程
assets/svg/                          已批准的 SVG 模板、生成器、样例和预览

src/                                 10 个合约
  HahaNamePolicy.sol
  HahaRegistry.sol
  HahaResolver.sol
  HahaRegistrar.sol
  HahaMetadata.sol
  HahaAgentIdentity.sol
  HahaReputation.sol
  HahaPoints.sol
  HahaMarketplace.sol
  HahaDeployer.sol
  interfaces/                        对外接口
  libraries/                         常量、namehash、.ai 身份判定、SVG 常量
script/Deploy.s.sol                  部署脚本
test/                                单元 / 模糊 / 不变式 / fork 测试
  fork/                              BSC 主网 .ai 注册表的冻结状态
tools/                               生成与复核脚本（纯 Python，无第三方依赖）
lib/                                 openzeppelin-contracts v5.1.0、forge-std v1.9.4
```

`docs/contracts/DEPLOYED.md` **在真正部署之前不存在**，由执行部署的人按 `DEPLOY.md` 第 6 节生成。

## 开发

### 环境

```bash
# Foundry v1.10.0（本文档基于该版本验证）
forge --version

# 依赖已提交在 lib/ 下，不要升级
forge build
```

`foundry.toml` 里 **`via_ir = true` 是硬约束**，不是偏好。关掉它 `HahaDeployer` 会编译失败
（solc 的非 via-ir 代码生成器处理不了当前的合约互相引用）。原因见 `CHANGELOG` 与
`src/HahaDeployer.sol` 顶部注释。

### 测试

```bash
forge test                    # 全部：259 passed, 0 failed, 10 skipped
forge test --match-contract RegistrarMintTest    # 只跑铸造
forge test --match-contract InvariantTest        # 只跑不变式（约 10 秒）
```

跳过的 10 条是**在线 fork 测试**，非 fork 环境自动 skip。要跑它们：

```bash
export BSC_RPC_URL=https://bsc-dataseed.bnbchain.org
forge test --match-contract ForkOnlineTest --fork-url $BSC_RPC_URL
```

### 独立复核（不依赖 forge）

```bash
python tools/check_hashes.py
```

复核黑名单/保留名的全部哈希、namehash 向量、SVG 片段的字节与 SHA-256、
三张样例的逐字节拼装、字号基线表。**这是第二条独立验证路径**，
用纯 Python keccak 实现，与 Solidity 测试互相印证。

### 再生生成物

改图或改名单之后：

```bash
python tools/gen_svg_literals.py   # assets/svg/*.svgpart → src/libraries/HahaSvg.sol
python tools/gen_test_lists.py     # *.hashes.txt → test/TestLists.sol
python tools/freeze_fork_state.py  # 重新冻结 .ai 的字节码与 storage（需要 RPC）
```

这些文件的头部都写了「不要手改」。测试会校验生成物与源文件一致。

### 部署

见 [`docs/contracts/DEPLOY.md`](docs/contracts/DEPLOY.md)。**先 dry-run，再广播。**

```bash
forge script script/Deploy.s.sol:Deploy \
    --rpc-url $BSC_RPC_URL \
    --private-key $DEPLOYER_PK \
    -vvv                       # 不加 --broadcast 就是 dry-run
```

## 阶段一合约

一套不可升级的合约同时服务 `.haha` 和 `.meme`：`HahaNamePolicy`、`HahaRegistry`、`HahaRegistrar`、`HahaResolver`、`HahaMetadata`、`HahaAgentIdentity`、`HahaReputation`、`HahaPoints`、`HahaMarketplace`，外加一次性的 `HahaDeployer`。

铸造免费、永久、不限量。调用者必须当时持有 `.ai`，并且这个 `.ai` 身份每小时最多铸一次（两个 TLD 合算）。铸出的 NFT 只给 `msg.sender`。详情和链上已核实的 `.ai` 接口在规格第 4 节。
