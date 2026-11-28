"""Open the Season 1 redemption switch (redeemOpen = true) with the admin key.

This enables applyFor for the current day. Day 20781 window runs until
2026-11-25 08:00 Beijing. L instructed this directly on 2026-11-24.
"""
import sys
sys.path.insert(0, "/opt/haha-season1/admin")
sys.path.insert(0, "/opt/haha-season1")
sys.path.insert(0, "/opt/haha-indexer")

from admin_tx import eth_call, load_admin_key, send_and_confirm, selector
from indexer.common import RpcClient, get_config
from tools.season1.mainnet import MODULE

ADMIN = "0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7"

rpc = RpcClient(get_config()["rpc_urls"])

def read_redeem_open():
    data = "0x" + selector("redeemOpen()").hex()
    out = eth_call(rpc, MODULE, data)
    return int(out, 16) == 1

before = read_redeem_open()
print("redeemOpen before:", before)
if before:
    print("already open, nothing to do")
    sys.exit(0)

key, address = load_admin_key()
# setRedeemOpen(true): selector + uint256(1)
data = "0x" + selector("setRedeemOpen(bool)").hex() + (1).to_bytes(32, "big").hex()
print("sending setRedeemOpen(true)...")
tx_hash, receipt = send_and_confirm(key, ADMIN, MODULE, data)
print("tx hash:", tx_hash)
print("status:", receipt.get("status"))
print("block:", receipt.get("blockNumber"))
after = read_redeem_open()
print("redeemOpen after:", after)
if not after:
    raise SystemExit("FAILED: redeemOpen is still false")
print("DONE: redeemOpen is now true")
