# G13 验证者服务 — 给 L 的部署说明

## 这是什么

验证者服务（`validator-service.py`）是跑在服务器上的 Python 程序，监听验证合约
`HahaValidation`（`0xAF9d2D3b6717469B21464baA12B022817841952b`，BSC 主网）发出的
`ValidationRequest` / `ValidationDisputed` 事件，自动检查并提交验证结果。
v1 唯一验证者就是管理员（`0x083A…76Ef7`），服务用服务器上已有的管理员密钥签名。

**部署是 C 的操作（2026-11-25 L 改定，不再是 L 部署）。** 下面每一步都在服务器（`<SERVER_IP>`）上做。
密钥不新写：直接用第一季自动化在用的 `/etc/haha/admin-signer.env`，
不用新建任何密钥文件，密钥不进聊天、不进 GitHub、不进备份。

## 部署步骤（服务器上，root）

```bash
# 1. 建目录
mkdir -p /opt/haha-validation
chmod 700 /opt/haha-validation

# 2. 放程序（把 validator-service.py 传到服务器）
#    本地传：scp validator-service.py root@<SERVER_IP>:/opt/haha-validation/
chmod 640 /opt/haha-validation/validator-service.py
chown root:root /opt/haha-validation/validator-service.py

# 3. 放 systemd 单元
#    scp haha-validator.service root@<SERVER_IP>:/etc/systemd/system/
chmod 644 /etc/systemd/system/haha-validator.service

# 4. 放 logrotate 配置
#    scp haha-validator.logrotate root@<SERVER_IP>:/etc/logrotate.d/haha-validator
chmod 644 /etc/logrotate.d/haha-validator

# 5. 启动
systemctl daemon-reload
systemctl enable haha-validator.service
systemctl start haha-validator.service
```

## 检查

```bash
# 状态（应为 active）
systemctl status haha-validator.service

# 日志（应有启动记录，随后每 30 秒轮询，无报错）
tail -f /opt/haha-validation/validator.log

# 进度（已处理的最新区块号，首次运行从部署块 135619015 开始）
cat /opt/haha-validation/state.json

# 重启次数（RestartSec=60，若短时间内重启很多次说明有问题，先看日志再处理）
systemctl show haha-validator.service -p NRestarts
```

## 停服务 / 重启

```bash
systemctl stop haha-validator.service      # 停：只影响新验证请求，现有功能不受影响
systemctl restart haha-validator.service   # 重启后从 state.json 的区块继续，不丢事件
```

## 出问题时

- 服务宕机：systemd 自动重启（`Restart=on-failure`，`RestartSec=60`），
  尽快恢复；v1 无外部告警、无超时惩罚，请求会一直挂着等服务恢复后响应。
- 日志里出现“签名密钥地址与链上验证者不一致，停发”：
  说明管理员用 `setValidator` 改了验证者地址，服务用的管理员密钥已不是
  当前验证者——停发是故意的，先不要重启，等 L 更新验证者密钥配置。
- 密钥文件 `/etc/haha/admin-signer.env` 绝不要改权限、不要复制、不要发出来。

## 服务行为要点（已按冻结计划 §6.2 实现，T10 测试通过，见 tools/g13-tests/t10_report.md）

- 每 30 秒轮询一次新事件，收到请求后几分钟内完成检查并提交结果。
- 只接受 `https://` 与 `ipfs://` 的请求文档，超时 10 秒，上限 64KB；
  拉不到 / 超限 / JSON 无效 / 缺字段 → 提交 0 分，证据写明原因。
- 接口可达：先核对 endpoint 在 agent 注册文件里（不在 → 0 分），
  再 GET（405 改 POST 空 JSON）；2xx/3xx/401/403 → 100，其余 → 0。
- 身份真实性：EIP-191 与 EIP-712 两种签名都认（2026-11-25 修订）。EIP-191 是对 `requestHash` 32 字节原始值的个人签名；EIP-712 是 `IdentityChallenge{agentId, requestHash}` typed data 签名，domain 是 name `HahaValidation`、version `1`、chainId 56、verifyingContract 主网合约地址。验证者先试 EIP-191，不匹配再试 EIP-712；文档带 `signatureType` 字段时优先试对应的方式。Binance Agent Wallet 只支持 EIP-712 签消息。
- 争议：收到 `ValidationDisputed` 后重新检查并提交新结果。
- gas 固定 1 gwei；nonce 冲突重试最多 3 次（间隔 1s/2s/4s）；合约 revert 不重试。
- 证据：`responseURI` 为自包含的 `data:application/json;base64,…` 记录
  （v1 无证据托管服务，见程序注释），`responseHash` 为该记录的 keccak256。
- 日志轮转：按周轮转，保留 4 周。
