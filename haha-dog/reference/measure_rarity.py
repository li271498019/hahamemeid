"""Measure trait frequencies and the rarity tier distribution over N random seeds.
Uses a vectorized copy of model/infer_int.py (checked against it on the first 500 seeds).
Usage: python measure_rarity.py [N]
"""
import collections
import math
import os
import sys

import numpy as np

import hahadog_ref as R

W = R.WEIGHTS


def forward(seeds):
    s = seeds.astype(np.int64).reshape(-1, 8, 4).sum(2) - 510
    h = (s * 7) >> 5
    half = 1 << (W["SH"] - 1)
    for layer in W["layers"]:
        acc = h @ np.array(layer["W"], np.int64).T + np.array(layer["b"], np.int64)
        h = np.where(acc <= 0, 0, np.minimum(127, (acc * layer["M"] + half) >> W["SH"]))
    y = h @ np.array(W["W_out"], np.int64).T + np.array(W["b_out"], np.int64)
    cells = np.zeros((len(seeds), 128), np.int64)
    for k, v in W["const_cells"].items():
        cells[:, int(k)] = v
    P, C = np.array(W["P"], np.int64), np.array(W["C"], np.int64)
    for v, ci in enumerate(W["var_cells"]):
        sc = 2 * (y[:, 2 * v, None] * P[None, :, 0] + y[:, 2 * v + 1, None] * P[None, :, 1]) - C[None, :]
        allowed = np.array([(W["var_masks"][v] >> c) & 1 for c in range(11)], bool)
        cells[:, ci] = np.where(allowed[None, :], sc, -(1 << 62)).argmax(1)
    off, picks = 2 * len(W["var_cells"]), []
    for n in W["groups"]:
        picks.append(y[:, off:off + n].argmax(1))
        off += n
    return cells, np.stack(picks, 1)


def classify(cells):
    g = np.array(R.GROUP)[cells]
    out = []
    for cat in R.CATEGORIES:
        t = R.TEMPLATES[cat]
        sc = (g[:, None, t["cells"]] == np.array(t["table"])[None]).sum(2)
        out.append(sc.argmax(1))
    return out


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100_000
    rng = np.random.default_rng(20261128)
    seeds = [R.keccak256(rng.bytes(32)) for _ in range(n)]
    arr = np.frombuffer(b"".join(seeds), np.uint8).reshape(n, 32)
    cells, picks = forward(arr)
    for i in range(500):
        c, p = R.generate(seeds[i])
        assert list(cells[i]) == c and list(picks[i]) == p
    bg = [R.background_of(s) for s in seeds]
    style = np.array([b[0] for b in bg])
    head, eyes, mouth, neck = classify(cells)
    feats = dict(head=head, eyes=eyes, mouth=mouth, neck=neck, fur=picks[:, 0], style=style)
    names = dict(head=R.HEAD_NAMES, eyes=R.EYES_NAMES, mouth=R.MOUTH_NAMES, neck=R.NECK_NAMES,
                 fur=R.FUR_NAMES, style=R.STYLE_NAMES[:5])
    lines = ["# Measured over %d random seeds" % n, ""]
    for k, f in feats.items():
        freq = np.bincount(f, minlength=len(names[k])) / n
        suggested = [min(20, int(round(-2 * math.log2(max(x, 1e-4))))) for x in freq]
        lines.append("## %s" % k)
        lines.append("| option | share | points |")
        lines.append("|---|---:|---:|")
        for i, nm in enumerate(names[k]):
            lines.append("| %s | %.2f%% | %d |" % (nm, freq[i] * 100, R.POINTS[k][i]))
        if suggested != R.POINTS[k]:
            lines.append("(suggested from this run: %s)" % suggested)
        lines.append("")
    tiers = collections.Counter()
    scores = []
    for i in range(n):
        s, t = R.rarity(int(head[i]), int(eyes[i]), int(mouth[i]), int(neck[i]), int(picks[i, 0]), int(style[i]))
        tiers[t] += 1
        scores.append(s)
    lines.append("## tiers")
    lines.append("| tier | min score | share |")
    lines.append("|---|---:|---:|")
    for t in range(4):
        lines.append("| %s | %d | %.2f%% |" % (R.TIER_NAMES[t], R.TIER_MIN[t], tiers[t] / n * 100))
    lines.append("")
    lines.append("score percentiles 50/70/90/98: %s" % np.percentile(scores, [50, 70, 90, 98]).tolist())
    txt = "\n".join(lines)
    print(txt)
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "rarity-measured.md"), "w").write(txt + "\n")


if __name__ == "__main__":
    main()
