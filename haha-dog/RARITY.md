# Haha Dog 稀有度规则 / Rarity tiers

参考实现：`rarity.py`（与合约链上算法逐位一致；已用 500 个随机种子与合约参考实现对照通过）。
网站可直接调用 `traits(seed)`，seed 为 32 字节（即合约 `seedOf(tokenId)` = keccak256(abi.encode(blockhash(N+4), tokenId, rerolls))）。

## 怎么算

1. 种子 → Haha AI 模型（int8 神经网络）算出 16×8 像素格 + 4 个配色（毛色/衣服/配饰/发光）。
2. 背景由 `keccak256(seed)` 决定：`r % 100` 落在 30/25/20/15/10 → 扫描线/放射光/星空/月夜/故障；
   颜色 `(r >> 128) % 8`（星空、月夜只用 Rose/Crimson/Violet 三种夜色）。
3. 头饰、眼睛、嘴、脖子：把像素格和训练素材里每个选项的模板逐格比较，取最相似的那个（最近模板）。
4. 分数 = 头饰 + 眼睛 + 嘴 + 脖子 + 毛色 + 背景样式 的点数（点数 ≈ -2·log2(出现概率)，越少见越高）。
5. 档位：

| 档位 | 中文 | 条件 | 实测占比（10 万随机种子） |
|---|---|---|---:|
| Common | 普通 | 分数 < 30 | 67.07% |
| Rare | 稀有 | 30 ≤ 分数 < 35 | 21.99% |
| Epic | 史诗 | 35 ≤ 分数 < 40 | 8.44% |
| Legendary | 传说（极品） | 分数 ≥ 40 | 2.50% |

特殊组合（覆盖分数档位）：
- **金毛 + 王冠或光环** → 直接 Legendary（"黄金国王"）。
- **激光眼或护目镜 + 故障背景** → 至少 Epic（"赛博故障"）。

目标是 70/20/8/2；因为分数是整数，最接近的门槛就是 30/35/40。

## 各特征实测占比与点数

## head
| option | share | points |
|---|---:|---:|
| Beanie | 9.57% | 7 |
| Cap | 10.09% | 7 |
| Backwards Cap | 7.95% | 7 |
| Headband | 8.13% | 7 |
| Hood | 9.09% | 7 |
| Headphones | 8.82% | 7 |
| Tuft | 6.93% | 8 |
| Spiky | 10.06% | 7 |
| Mohawk | 8.46% | 7 |
| Party Hat | 5.09% | 9 |
| Propeller | 4.95% | 9 |
| Crown | 3.95% | 9 |
| Halo | 3.87% | 9 |
| Third Eye | 3.04% | 10 |

## eyes
| option | share | points |
|---|---:|---:|
| Normal | 30.53% | 3 |
| Shades | 17.80% | 5 |
| Laser | 7.39% | 8 |
| Visor | 7.50% | 7 |
| Neon Specs | 7.24% | 8 |
| Squint Smile | 2.58% | 11 |
| Wide Stare | 5.05% | 9 |
| Sleepy | 3.93% | 9 |
| Angry | 11.16% | 6 |
| Smug | 6.81% | 8 |

## mouth
| option | share | points |
|---|---:|---:|
| Smile | 81.98% | 1 |
| Tongue | 6.99% | 8 |
| Grin | 0.00% | 20 |
| Laugh | 1.15% | 13 |
| O Mouth | 0.05% | 20 |
| Flat | 3.92% | 9 |
| Bubblegum | 0.54% | 15 |
| Bandana | 5.37% | 8 |

## neck
| option | share | points |
|---|---:|---:|
| None | 66.87% | 1 |
| Gold Chain | 17.50% | 5 |
| Spiked Collar | 2.92% | 10 |
| Bell Collar | 3.92% | 9 |
| Hoodie | 8.79% | 7 |

## fur
| option | share | points |
|---|---:|---:|
| Classic Tan | 48.20% | 2 |
| Red | 12.90% | 6 |
| Black and Tan | 11.38% | 6 |
| Cream | 7.53% | 7 |
| Cyborg | 12.53% | 6 |
| Hologram | 6.07% | 8 |
| Gold | 1.40% | 12 |

## style
| option | share | points |
|---|---:|---:|
| Scanlines | 30.11% | 3 |
| Sunburst | 25.00% | 4 |
| Stars | 20.07% | 5 |
| Moon | 14.92% | 5 |
| Glitch | 9.89% | 7 |


注意：
- 模型几乎不画 Grin（0%）和 O Mouth（0.05%），它们点数封顶 20，出现即很可能是 Legendary。
- 衣服、配饰、发光颜色作为属性展示，但不计入稀有度分数。
- "出图中"的 token 不参与稀有度：它们显示"出图中"占位图，没有特征。包括两种情况：目标块（铸造/重铸所在块 N 之后第 4 块）尚未出现；或目标块哈希已超出可读窗口（256 块，BSC 支持 EIP-2935 时为 8191 块）且未被快照。后一种情况持有人可免费重铸，重新得到一只狗；全程无押金、无费用（只付 gas）。
