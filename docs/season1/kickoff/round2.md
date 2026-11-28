# 第二轮任务

业务数字仍以 `00` 为准。本文件只分配修复，不改价格、天数或预算。

C #50 与 D #51 已在 `main` 的 `e531602`。下面给 C、D 的句子是当时的任务，不是还要再做一遍。当前要执行的顺序在 [../launch-runbook.md](../launch-runbook.md)。

## 给 D

共享 Merkle 向量已经写在 [fixtures/merkle-v1.json](fixtures/merkle-v1.json)。算法版本是 `haha-season1-merkle-v1`：叶是 `keccak256(keccak256(abi.encode(aiId, balance, uint8 tier)))`，配对按字节排序后 `keccak256(abi.encodePacked)`，奇数节点原样上提，不和自己配对。请只消费这份文件，改你测试基类里的树，使 1、2、3、5、20 叶的根和证明与文件一致。不要另外生成一套根。

另外两件仍是你的：

- `setDayRoot` 在快照块超过最近 256 个块后会读不到 `blockhash`。补 15 块可通过、257 块必须失败的测试，并在部署授权面板写明这个块数。不要写成分钟。
- 找错领取在 `END_TS` 之后、仍处于公示后的 7 天内，应能成功。补这一条时间测试。

合约里的事故退款逻辑本轮不改。

## 给 C

把 `season.html`、`season-checklist.html`、`js/season-status.js` 和 `season/fixtures/` 放进 `web/site/`。导航只改 `web/site/index.html` 里指向 `/season` 的那一个链接。不要改合约、索引器或 A 的发放页。夹具仍是测试样本，不要把它们说成线上接口。

## A 本轮自己做的

生产 Merkle 以上面的向量为准。索引补 `ValidatorSet` 和 `RewardSignerSet`，重组后按日志重放。签名前每次读链上 `validators(address)`，读失败就拒绝，不使用过期缓存。`handoff.json` 的模块地址仍是空，签名保持关闭。本机发放工具在 `tools/season1/ops_server.py`，只绑 `127.0.0.1`，私钥不进服务器。
