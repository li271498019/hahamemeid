"""Cut sprite sheets back into the training dataset.

Every pixel color is looked up in the fixed palette (palette.color_table()):
  transparent -> EMPTY, otherwise -> (cell class, color group, option).
Per dog we recover: 16x8 left-half class map (the right half must mirror it),
and the 4 color choices (fur, cloth, acc, glow); a choice that no pixel uses
is stored as -1 and ignored by the loss.
Usage: python slice_sheets.py --sheets sheets --out data/dataset.npz
"""
import argparse
import glob
import os

import numpy as np
from PIL import Image

from palette import color_table, EMPTY

TILE, COLS = 16, 16
GROUPS = ["fur", "cloth", "acc", "glow"]


def slice_tile(tile, table):
    cls = np.zeros((16, 16), np.uint8)
    picks = [-1, -1, -1, -1]
    for r in range(16):
        for c in range(16):
            px = tile[r, c]
            if px[3] == 0:
                cls[r, c] = EMPTY
                continue
            key = (int(px[0]), int(px[1]), int(px[2]))
            if key not in table:
                raise ValueError(f"unknown color {key} at {r},{c}")
            k, grp, opt = table[key]
            cls[r, c] = k
            if grp is not None:
                gi = GROUPS.index(grp)
                if picks[gi] not in (-1, opt):
                    raise ValueError(f"two different {grp} colors in one dog")
                picks[gi] = opt
    if not (cls[:, :8] == cls[:, 8:][:, ::-1]).all():
        raise ValueError("tile is not left-right symmetric")
    return cls[:, :8], picks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheets", default="sheets")
    ap.add_argument("--out", default=os.path.join("data", "dataset.npz"))
    a = ap.parse_args()
    table = color_table()
    halves, picks = [], []
    files = sorted(glob.glob(os.path.join(a.sheets, "sheet_*.png")))
    assert files, "no sheets found"
    for fn in files:
        im = np.array(Image.open(fn).convert("RGBA"))
        n = 0
        for r in range(im.shape[0] // TILE):
            for c in range(im.shape[1] // TILE):
                tile = im[r * TILE:(r + 1) * TILE, c * TILE:(c + 1) * TILE]
                if tile[..., 3].max() == 0:
                    continue  # empty slot
                try:
                    h, p = slice_tile(tile, table)
                except ValueError as e:
                    raise SystemExit(f"[slice] {fn} 第 {r + 1} 行 第 {c + 1} 列 (row {r + 1}, col {c + 1}): {e}")
                halves.append(h); picks.append(p); n += 1
        print(f"[slice] {fn}: {n} dogs")
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    np.savez_compressed(a.out, halves=np.array(halves), picks=np.array(picks, np.int64))
    lab = os.path.join(a.sheets, "labels.json")
    if os.path.exists(lab):
        import json, shutil
        labels = json.load(open(lab, encoding="utf-8"))
        assert len(labels) == len(halves), "labels.json does not match the sheets"
        shutil.copy(lab, os.path.join(os.path.dirname(a.out) or ".", "labels.json"))
    print(f"[slice] total {len(halves)} dogs -> {a.out}")


if __name__ == "__main__":
    main()
