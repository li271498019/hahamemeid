"""Freeze trait templates from the training generator (model/gen_data.py).

Each trait option is drawn alone on the base dog; cells are compared in groups
(fur/fur_shade/mark -> fur, cloth/cloth_shade -> cloth). Only cells where the
options of a category differ are kept. Output: trait-templates.json
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "model"))
import gen_data as G  # noqa: E402

GROUP = [0, 1, 2, 2, 2, 5, 5, 7, 8, 9, 10]
BASE_FORCED = dict(head="tuft", eyes="normal", mouth="smile", neck="none", ears="normal",
                   blush=False, fur=0, cloth=1, acc=1, glow=2)
CATS = {
    "head": [n for n, _ in G.HEAD],
    "eyes": [n for n, _ in G.EYES],
    "mouth": [n for n, _ in G.MOUTH],
    "neck": [n for n, _ in G.NECK] + ["hoodie"],
}


def draw(cat, name):
    f = dict(BASE_FORCED)
    if cat == "neck" and name == "hoodie":
        f["head"] = "hood"
        f["neck"] = "none"
    else:
        f[cat] = name
    g, _, t = G.make_dog(np.random.default_rng(0), f)
    return [GROUP[int(v)] for v in g.reshape(-1)]


def main():
    out = {}
    for cat, names in CATS.items():
        rows = [draw(cat, n) for n in names]
        if cat == "neck":
            rows = [r[120:] for r in rows]
            diff = [120 + c for c in range(8) if len({r[c] for r in rows}) > 1]
            table = [[r[c - 120] for c in diff] for r in rows]
        else:
            diff = [c for c in range(128) if len({r[c] for r in rows}) > 1]
            table = [[r[c] for c in diff] for r in rows]
        out[cat] = dict(options=names, cells=diff, table=table)
    json.dump(out, open(os.path.join(HERE, "trait-templates.json"), "w"), indent=1)
    for k, v in out.items():
        print(k, len(v["options"]), "options", len(v["cells"]), "cells")


if __name__ == "__main__":
    main()
