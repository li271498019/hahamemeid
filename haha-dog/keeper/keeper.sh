#!/usr/bin/env bash
# Haha Dog snapshot keeper. Stores due target block hashes via processQueue(MAX_STEPS).
# Needs Foundry's `cast`. Env: BSC_RPC_URL, HAHA_DOG_ADDRESS, KEEPER_PK; optional MAX_STEPS, INTERVAL.
set -euo pipefail

: "${BSC_RPC_URL:?set BSC_RPC_URL}"
: "${HAHA_DOG_ADDRESS:?set HAHA_DOG_ADDRESS}"
: "${KEEPER_PK:?set KEEPER_PK}"
MAX_STEPS="${MAX_STEPS:-100}"
INTERVAL="${INTERVAL:-30}"

while true; do
  head=$(cast call "$HAHA_DOG_ADDRESS" "queueHead()(uint256)" --rpc-url "$BSC_RPC_URL" 2>/dev/null || echo err)
  next=$(cast call "$HAHA_DOG_ADDRESS" "processQueue(uint256)(uint256)" "$MAX_STEPS" --rpc-url "$BSC_RPC_URL" 2>/dev/null || echo err)
  if [[ "$head" != err && "$next" != err && "$next" != "$head" ]]; then
    echo "$(date '+%F %T') queue $head -> $next"
    cast send "$HAHA_DOG_ADDRESS" "processQueue(uint256)" "$MAX_STEPS" \
      --rpc-url "$BSC_RPC_URL" --private-key "$KEEPER_PK" >/dev/null \
      && echo "$(date '+%F %T') sent" || echo "$(date '+%F %T') send failed"
  fi
  sleep "$INTERVAL"
done
