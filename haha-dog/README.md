# Haha Dog

Haha AI, an on-chain AI large model. Haha Dog is a 10,000-piece ERC-721 collection on BNB Smart Chain whose
images are produced by a small neural network that lives entirely in contract bytecode. No server, no IPFS:
`tokenURI` runs the model, draws the SVG and computes traits and rarity inside an `eth_call`.

The frozen product spec is [SPEC.md](SPEC.md) (v1.0, Chinese). Rarity rules: [RARITY.md](RARITY.md).

## Hashes

| What | keccak256 |
|---|---|
| Model weights, `haha-dog/model/weights-int8.json` (raw file bytes) | `0x1d2239644b5273c4f1925c489d32900a564262bce6597f94a929489cfbe58078` |
| Packed on-chain blob, `HahaDogModel.modelData()` = `haha-dog/reference/model-data.bin` | `0x72f92c628a64bc0d5652d285c6789fa0f84cb462d328604cf3dcff224704f8da` |

`HahaDogModel.MODEL_DATA_HASH` returns the second value. The blob is derived deterministically from the
weights file by `haha-dog/reference/gen_solidity.py`; both hashes are asserted in
`test/hahadog/HahaDogModel.t.sol`.

## Deployed (BSC mainnet, chainId 56)

| Contract | Address |
|---|---|
| HahaDogModel | `0x3277990797Ed8B15B3674ee0C557011F5a1eCCC9` |
| HahaDogRenderer | `0xCA760D9D3E76DcDC7AC6bcc55D53346b8a2c107E` |
| HahaDog | `0x26f88A5db4925e9aFa35B1096FdD6DBa09f056c6` |
| HahaDogMarket | `0xD7F5502Bd7a52E17959bF4b7F1180f6e3611fd49` |

## Contracts

| Contract | Role | Constructor |
|---|---|---|
| `src/hahadog/HahaDogModel.sol` | int8 MLP 8 -> 64 -> 32 -> 224 (ReLU), prototype argmax per cell; seed -> 16x16 dog + colour picks | none |
| `src/hahadog/HahaDogRenderer.sol` | 5 backgrounds, SVG, trait detection, rarity, base64 JSON, "generating" image | `model` |
| `src/hahadog/HahaDog.sol` | ERC-721 + EIP-2981 (1%): mint, quota, randomness, hash snapshots, reroll | `renderer, aiRegistry, registrar, feeReceiver, blockHistory` |
| `src/hahadog/HahaDogMarket.sol` | Fixed-price market, 1% fee, pull withdrawals (mirrors `HahaMarketplace`) | `dog, feeReceiver` |

All four are immutable: no owner, no admin, no upgrade path, no pause.

## Mint

- Supply cap 10,000, free (gas only), open from deployment.
- Caller must hold a `.ai` name (`HahaAiIdentity.aiIdentityOf`, same check as the existing contracts).
- Quota per `.ai` identity: 1, or 2 if the caller also holds a haha id (`HahaRegistrar.balanceOf > 0`).
  Minted counts are stored only per `.ai` id (`.ai` is soulbound, one per person), so moving a haha id or
  the minted dogs never adds quota to the same `.ai`.

## Randomness and snapshots

- Mint or reroll at block `N` commits `(N, rerolls)`; the outcome is fixed at commit time.
- `seed = keccak256(abi.encode(blockhash(N + 4), tokenId, rerolls))`.
- No reveal step. Once block `N + 4` exists, `tokenURI` reads the hash and renders live. Before that it returns the
  "generating" image.
- Hash sources, in order: stored snapshot; `blockhash` (last 256 blocks); EIP-2935 history contract
  `0x0000F90827F1C53a10cb7A02335B175320002935` (last 8191 blocks).
- `snapshot(uint256[] tokenIds)` and `processQueue(uint256 maxSteps)` are public and free. They store due target
  hashes in `snapshots(blockNumber)` permanently. Every commit is queued; mint, reroll and transfer each
  process up to 3 queue entries automatically. A keeper (`keeper/keeper.sh`) is an ordinary caller that drains the
  queue; it stores nothing off-chain and decides nothing.
- If a target hash is out of every window and was never snapshotted, the token stays in "generating" (status 3)
  and the holder may reroll for free. There is no fallback image, fee, deposit or forfeiture.

`statusOf(tokenId)`: 0 none, 1 generating (target block not yet mined), 2 ready, 3 stalled (shown as generating).

### EIP-2935 on BSC

Checked over JSON-RPC on 2026-11-28 (BSC mainnet and testnet): `eth_getCode` at
`0x0000F90827F1C53a10cb7A02335B175320002935` returns the standard EIP-2935 history contract (ring buffer of
8191). `eth_call` with a 32-byte block number returned the real block hash 300 and 8,000 blocks back and reverted
8,200 blocks back. The deploy script passes this address as `blockHistory` by default; `address(0)` disables it.
Tests etch the same bytecode and fill its storage.

## Reroll

Holder only, unlimited, free. The previous image is discarded at commit and the new one appears at `N + 4`.

## Market

`list / updatePrice / cancel / clearStale / buy / withdraw`, 1% fee to the fee receiver, proceeds by pull.
Only ready tokens can be listed or bought, and a listing records the token's reroll count: a token rerolled after
listing cannot be bought and the listing can be cleared by anyone.

## Build and test

```bash
forge build --sizes
forge test                                   # whole repo, including the existing suite
forge test --match-path 'test/hahadog/*' -vv # Haha Dog only, prints gas
```

Reference implementation and generators (Python 3 + numpy):

```bash
python3 haha-dog/reference/gen_solidity.py   # rewrites HahaDogWeights.sol and HahaDogTables.sol
python3 haha-dog/reference/gen_fixtures.py   # rewrites test/hahadog/fixtures/*.json
```

Model and renderer outputs are checked bit for bit against the Python reference (316 seeds, 16 shipped SVG test
vectors, tokenURI fixtures).

## Deploy

See [DEPLOY.md](DEPLOY.md) (Chinese) and `script/DeployHahaDog.s.sol`.
