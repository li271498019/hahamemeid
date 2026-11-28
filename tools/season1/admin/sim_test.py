import sys, time
sys.path.insert(0, "/opt/haha-season1")
sys.path.insert(0, "/opt/haha-indexer")
sys.path.insert(0, "/opt/haha-season1/admin")
from admin_tx import (
    AdminTxError, encode_call, eth_call, load_admin_key, send_with_retry, _rpc,
)
from tools.season1.mainnet import MODULE
from tools.season1.constants import REGISTRAR
from tools.season1.ops import admin_mint_calldata

key, address = load_admin_key()
rpc = _rpc()
print("admin:", address, flush=True)

# --- Test 1: setTaskPack simulation x3 (day 20781, dummy hash). No broadcast.
# Must run as the admin, or setTaskPack reverts on auth.
print("\n== Test 1: setTaskPack eth_call simulation x3 (as admin) ==", flush=True)
test_hash = bytes.fromhex("11" * 32)
data = encode_call("setTaskPack(uint64,bytes32)", ["uint64", "bytes32"], [20781, test_hash])
for i in range(1, 4):
    try:
        eth_call(rpc, MODULE, data, "latest", from_address=address)
        print(f"  run {i}: simulation OK (no revert)", flush=True)
    except Exception as e:
        print(f"  run {i}: simulation FAILED: {str(e)[:120]}", flush=True)

# --- Test 2: adminMint simulation x3 (test label 'zz' .haha). No broadcast.
print("\n== Test 2: adminMint eth_call simulation x3 (as admin) ==", flush=True)
mint_data = admin_mint_calldata("zz", 0, address)
for i in range(1, 4):
    try:
        eth_call(rpc, REGISTRAR, mint_data, "latest", from_address=address)
        print(f"  run {i}: simulation OK (no revert)", flush=True)
    except Exception as e:
        print(f"  run {i}: simulation FAILED: {str(e)[:120]}", flush=True)

# --- Test 3: retry deadline already passed -> must raise immediately, no send.
print("\n== Test 3: send_with_retry with past deadline (must not send) ==", flush=True)
try:
    send_with_retry(key, address, MODULE, data, deadline=time.time() - 1)
    print("  FAIL: did not raise", flush=True)
except AdminTxError as e:
    print("  OK: raised immediately:", str(e)[:100], flush=True)

# --- Test 4: retry on a call that always fails simulation (stale setDayRoot).
# Should retry 3 times then raise, and never broadcast.
print("\n== Test 4: send_with_retry on stale setDayRoot (retry 3x then raise, no broadcast) ==", flush=True)
stale_root = "0x3bbde2f6e4a69e6c78741ef0f78f71ca5b8355753111e0d5897c94319a18c957"
stale_hash = "0xa28bbb3f52e08efa374979310f08bc0a9c256dce497e2f31b3e56bfed0ea25c9"
stale_data = encode_call(
    "setDayRoot(uint64,bytes32,uint64,bytes32,uint16,uint16)",
    ["uint64", "bytes32", "uint64", "bytes32", "uint16", "uint16"],
    [20780, bytes.fromhex(stale_root[2:]), 135171296, bytes.fromhex(stale_hash[2:]), 7, 0],
)
t0 = time.time()
try:
    send_with_retry(key, address, MODULE, stale_data, deadline=time.time() + 120)
    print("  FAIL: did not raise", flush=True)
except AdminTxError as e:
    print(f"  OK: raised after {time.time()-t0:.1f}s:", str(e)[:120], flush=True)

print("\nAll simulation tests done. Nothing was broadcast.", flush=True)
