# Haha Dog keeper

`keeper.sh` 是 D 交付的原版（依赖 Foundry `cast`）。生产上跑的是 `keeper.py`：逻辑相同，区别只在安全和运维：

- 私钥不进命令行（`cast --private-key` 在 `ps` 里可见），只从 systemd 凭据文件读入进程内存；
- RPC 地址（含 key）不进日志；
- 检查间隔 4 秒（keeper.sh 默认 30 秒），避免错过 256 区块的存哈希窗口；
- 合约的 `processQueue` 谁都能调，换钱包只要改 `KEEPER_EXPECT_ADDRESS` 和凭据文件。

部署：`haha-dog-keeper.service`（线上原件）。`status.py` 是只读的队列状态查看脚本。`README-server.md` 是服务器上的原始说明。
