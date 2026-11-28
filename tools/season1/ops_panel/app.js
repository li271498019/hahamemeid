/* Local ops page. The key stays in the wallet. This file never sends a nonce. */
var OPS_CHAIN = 56;
var OPS_ADMIN = "0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7";

function canSend(ctx) {
  if (!ctx || Number(ctx.chainId) !== OPS_CHAIN) return "wrong-chain";
  if (!ctx.account || ctx.account.toLowerCase() !== OPS_ADMIN.toLowerCase()) return "wrong-admin";
  if (!ctx.prepared) return "unknown-order";
  if (ctx.localStatus === "pending" || ctx.localStatus === "confirmed") return "already-sent";
  if (ctx.prepared.from.toLowerCase() !== OPS_ADMIN.toLowerCase()) return "wrong-admin";
  if (String(ctx.prepared.value) !== "0x0") return "bad-value";
  if (ctx.prepared.nonce !== undefined) return "nonce-must-not-be-set";
  return null;
}

function walletRequest(prepared) {
  var tx = {
    from: prepared.from,
    to: prepared.to,
    value: prepared.value,
    data: prepared.data,
    chainId: prepared.chainId
  };
  return tx;
}

if (typeof module !== "undefined") {
  module.exports = { canSend: canSend, walletRequest: walletRequest, OPS_CHAIN: OPS_CHAIN, OPS_ADMIN: OPS_ADMIN };
}
