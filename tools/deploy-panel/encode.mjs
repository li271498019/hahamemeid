// 构造参数编码与 CREATE 地址预测。
// 与 script/Deploy.s.sol 的部署顺序、参数完全一致。
// 依赖全局 ethers（由 index.html 的 UMD 脚本注入）。

const abi = () => window.ethers.AbiCoder.defaultAbiCoder();

// 预测地址：deployer 从 baseNonce 起，按部署顺序 0..9 对应 10 个合约。
export function predictAddresses(deployer, baseNonce) {
  const addrs = [];
  for (let i = 0; i < 10; i++) {
    addrs.push(window.ethers.getCreateAddress({ from: deployer, nonce: BigInt(baseNonce) + BigInt(i) }));
  }
  return addrs;
}

// 编码构造参数，返回 creation code。
// 关键：所有参数一次性 abi.encode(types, values)，动态数组的 offset 才会正确。
export function encodeConstructor(step, predicted, fixedAddrs) {
  const c = abi();
  const resolveAddr = (r) => {
    if (typeof r === "number") return predicted[r];
    if (typeof r === "string") return fixedAddrs[r];
    return r;
  };

  const types = [];
  const values = [];
  for (const a of step.args) {
    switch (a.t) {
      case "addr":
        types.push("address");
        values.push(a.fixed !== undefined ? a.fixed : predicted[a.p]);
        break;
      case "b32arr": {
        types.push("bytes32[]");
        values.push(a.banned || a.reserved || []);
        break;
      }
      case "encode9": {
        // Registrar 构造参数是 bytes memory cfg，值是 abi.encode(9 addresses)
        types.push("bytes");
        values.push(
          c.encode(
            ["address", "address", "address", "address", "address", "address", "address", "address", "address"],
            a.refs.map(resolveAddr)
          )
        );
        break;
      }
      case "addrarr9": {
        types.push("address[9]");
        values.push(a.refs.map(resolveAddr));
        break;
      }
      default:
        throw new Error("unknown arg type: " + a.t);
    }
  }

  const argsHex = types.length === 0 ? "" : c.encode(types, values).slice(2);
  return {
    constructorArgs: "0x" + argsHex,
    bytecode: "0x" + step.contractInfo.bytecode + argsHex,
  };
}

// 部署后配置步骤（setEarner）参数编码。用合约 ABI 的 Interface.encodeFunctionData，
// 自动带上函数选择器。module 占位符替换为已部署地址。
export function encodeConfigCall(step, deployed, abiOf) {
  const iface = new window.ethers.Interface(abiOf);
  const [actionId, cfg] = step.args;
  const module = cfg.module === "{reputation}" ? deployed.reputation : deployed.identity;
  return iface.encodeFunctionData(step.method, [
    actionId,
    {
      module,
      points: cfg.points,
      perUserDailyCap: cfg.perUserDailyCap,
      globalDailyPoints: cfg.globalDailyPoints,
      keyMode: cfg.keyMode,
      requireName: cfg.requireName,
      enabled: cfg.enabled,
    },
  ]);
}
