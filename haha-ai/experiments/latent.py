"""Structured seed code: what each of the 8 seed numbers means.

The on-chain input is 8 bytes of the seed: z_q[i] = byte[i] - 128 (int8, -128..127),
i.e. z = z_q / 128 in [-1, 1).  During training every dog from the sheets is
given a code z that lies inside the intervals of ITS traits:

  dim 0 headwear (14)   dim 1 eyes (10)   dim 2 mouth (8)
  dim 3 neck x blush (8)  dim 4 fur (7)    dim 5 ears x glow color (10)
  dim 6 cloth color (8)   dim 7 accessory color (6)

Interval widths = how often the trait occurs in the training sheets, so the
trained network reproduces the same rarities on-chain. The network is NOT
told these rules at inference time - it simply learned them; the contract only
feeds the 8 numbers in. (Unlike "random seed -> random image" training, every
code points to exactly one combination, so nothing gets averaged.)
"""
import itertools
import json

import numpy as np

from palette import FURS

DIMS = [
    ("head", [("head", h) for h in ["tuft", "spiky", "mohawk", "party_hat", "crown", "halo", "third_eye",
                                    "headband", "headphones", "beanie", "propeller", "cap", "backwards_cap", "hood"]]),
    ("eyes", [("eyes", e) for e in ["normal", "squint_smile", "sleepy", "smug", "angry", "wide_stare",
                                    "neon_specs", "shades", "visor", "laser"]]),
    ("mouth", [("mouth", m) for m in ["smile", "grin", "o_mouth", "flat", "laugh", "tongue", "bubblegum", "bandana"]]),
    ("neck_blush", [(n, b) for n in ["none", "gold_chain", "bell_collar", "spiked_collar"] for b in [False, True]]),
    ("fur", [("fur", f[0]) for f in FURS]),
    ("ears_glow", [(e, g) for e in ["normal", "cyber"] for g in range(5)]),
    ("cloth", list(range(8))),
    ("acc", list(range(6))),
]
ZMIN, ZMAX = -128, 127        # 256 integer values per dim
MIN_WIDTH = 3


def allowed_options(lab, picks):
    """For one dog: per dim, the list of option indices whose code gives the SAME picture."""
    fur, head, ears, eyes, mouth, neck, blush = (lab["fur"], lab["head"], lab["ears"], lab["eyes"],
                                                lab["mouth"], lab["neck"], lab["blush"])
    cloth, acc, glow = int(picks[1]), int(picks[2]), int(picks[3])
    out = []
    out.append([[o[1] for o in DIMS[0][1]].index(head)])
    out.append([[o[1] for o in DIMS[1][1]].index(eyes)])
    out.append([[o[1] for o in DIMS[2][1]].index(mouth)])
    necks = ["none", "gold_chain", "bell_collar", "spiked_collar"] if head == "hood" else [neck]
    blushes = [False, True] if (eyes in ("visor", "shades") or mouth == "bandana") else [blush]
    out.append([i for i, (n, b) in enumerate(DIMS[3][1]) if n in necks and b in blushes])
    out.append([[o[1] for o in DIMS[4][1]].index(fur)])
    earss = ["normal", "cyber"] if fur == "cyborg" else [ears]
    if glow < 0:
        glows = list(range(5))
    elif eyes == "laser":
        glows = [1] if glow == 1 else [0, 2, 3, 4]
    else:
        glows = [glow]
    out.append([i for i, (e, g) in enumerate(DIMS[5][1]) if e in earss and g in glows])
    if cloth < 0:
        cl = list(range(8))
    elif fur == "black & tan" and cloth == 6:
        cl = [0, 6]
    else:
        cl = [cloth]
    out.append(cl)
    forced_acc = head in ("crown", "halo") or ears == "cyber" or neck in ("gold_chain", "bell_collar")
    if acc < 0 or forced_acc:
        ac = list(range(6))
    elif fur == "black & tan" and acc == 0:
        ac = [0, 2]
    else:
        ac = [acc]
    out.append(ac)
    return out


def compute_intervals(all_allowed):
    """Interval [lo, hi] (inclusive ints) per option, widths ~ trait frequency."""
    iv = []
    for d, (name, opts) in enumerate(DIMS):
        w = np.zeros(len(opts))
        for al in all_allowed:
            for o in al[d]:
                w[o] += 1.0 / len(al[d])
        w = w / w.sum()
        total = ZMAX - ZMIN + 1
        widths = np.maximum(MIN_WIDTH, np.round(w * total)).astype(int)
        while widths.sum() > total:
            widths[widths.argmax()] -= 1
        while widths.sum() < total:
            widths[widths.argmax()] += 1
        lo = ZMIN
        dim_iv = []
        for wd in widths:
            dim_iv.append((int(lo), int(lo + wd - 1))); lo += int(wd)
        iv.append(dim_iv)
    return iv


def sample_codes(all_allowed, iv, rng):
    """One random training code per dog (int8 values)."""
    n = len(all_allowed)
    z = np.zeros((n, 8), np.int64)
    for i, al in enumerate(all_allowed):
        for d in range(8):
            o = al[d][rng.integers(len(al[d]))]
            lo, hi = iv[d][o]
            z[i, d] = rng.integers(lo, hi + 1)
    return z


def code_to_traits(zq, iv):
    """Which option each dim falls into (for evaluation against the procedural generator)."""
    res = {}
    for d, (name, opts) in enumerate(DIMS):
        for o, (lo, hi) in enumerate(iv[d]):
            if lo <= zq[d] <= hi:
                res[name] = opts[o]
                break
    f = {}
    f["head"] = res["head"][1]; f["eyes"] = res["eyes"][1]; f["mouth"] = res["mouth"][1]
    f["neck"], f["blush"] = res["neck_blush"]
    f["fur"] = [x[0] for x in FURS].index(res["fur"][1])
    f["ears"], f["glow"] = res["ears_glow"]
    f["cloth"] = res["cloth"]; f["acc"] = res["acc"]
    return f
