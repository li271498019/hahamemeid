"""Open the Season 1 rewards switch (rewardsOpen = true) with the admin key.

This enables claimVerification / claimFinding / claimAccidentCredit.
It does NOT let anyone claim before the season starts: the contract
enforces block.timestamp >= START_TS and the per-day window, so a call
before 2026-11-24 08:00 Beijing reverts on the time check.
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

def read_rewards_open():
    data = "0x" + selector("rewardsOpen()").hex()
    out = eth_call(rpc, MODULE, data)
    return int(out, 16) == 1

before = read_rewards_open()
print("rewardsOpen before:", before)
if before:
    print("already open, nothing to do")
    sys.exit(0)

key, address = load_admin_key()
# setRewardsOpen(true): selector + uint256(1)
data = "0x" + selector("setRewardsOpen(bool)").hex() + (1).to_bytes(32, "big").hex()
print("sending setRewardsOpen(true)...")
tx_hash, receipt = send_and_confirm(key, ADMIN, MODULE, data)
print("tx hash:", tx_hash)
print("status:", receipt.get("status"))
after = read_rewards_open()
print("rewardsOpen after:", after)
if not after:
    raise SystemExit("FAILED: rewardsOpen is still false")
print("DONE: rewardsOpen is now true")
