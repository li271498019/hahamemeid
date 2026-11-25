// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Script, console2} from "forge-std/Script.sol";
import {HahaValidation} from "src/HahaValidation.sol";

/// @title DeployValidation
/// @notice 部署 G13 验证注册表 HahaValidation。
///
/// @dev ## 用法
///
/// ```bash
/// # 1. 本地 dry-run（不广播）
/// forge script script/DeployValidation.s.sol:DeployValidation \
///     --rpc-url $BSC_RPC_URL \
///     --private-key $DEPLOYER_PK \
///     -vvv
///
/// # 2. 真正广播（测试网 chainId 97 或主网 chainId 56）
/// forge script script/DeployValidation.s.sol:DeployValidation \
///     --rpc-url $BSC_RPC_URL \
///     --private-key $DEPLOYER_PK \
///     --broadcast \
///     -vvv
/// ```
///
/// ## 环境变量
///
/// | 变量 | 必需 | 说明 |
/// | --- | --- | --- |
/// | `DEPLOYER_PK` | 是 | 部署钱包私钥 |
/// | `BSC_RPC_URL` | 是 | BSC RPC（测试网 97 或主网 56） |
/// | `VALIDATION_ADMIN` | 否 | 默认 0x083A…6Ef7（= HahaRegistrar 的 admin） |
/// | `VALIDATION_IDENTITY` | 否 | 默认主网 HahaAgentIdentity 0x54A7…a4d4 |
///
/// ## 说明
///
/// v1 验证合约构造参数只有两个：admin 与 identity。
///   - admin：合约管理员（= HahaRegistrar 的 admin），immutable，部署时写死。
///   - identity：HahaAgentIdentity 地址，用于 isAuthorized(owner/operator) 判断。
/// 部署后 validator 初始 = admin，管理员可调 setValidator 更换验证者。
contract DeployValidation is Script {
    address internal constant DEFAULT_ADMIN = 0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7;
    address internal constant DEFAULT_IDENTITY = 0x54A70BF81B288d41013D7b57c2Db0922f1E1a4d4;

    function run() external returns (HahaValidation validation) {
        address admin = vm.envOr("VALIDATION_ADMIN", DEFAULT_ADMIN);
        address identity = vm.envOr("VALIDATION_IDENTITY", DEFAULT_IDENTITY);

        vm.startBroadcast();
        validation = new HahaValidation(admin, identity);
        vm.stopBroadcast();

        console2.log("HahaValidation deployed at:", address(validation));
        console2.log("  admin   :", validation.admin());
        console2.log("  identity:", validation.getIdentityRegistry());
        console2.log("  validator:", validation.validator());
        console2.log("  DISPUTE_WINDOW:", validation.DISPUTE_WINDOW(), "seconds");
    }
}
