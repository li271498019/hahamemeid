"""Pack generated dogs into sprite sheets (the 'training material' images).

Sheet layout (fixed, no gaps): 16 x 16 tiles of 16x16 px = 256x256 px PNG (RGBA).
Tile i sits at column i % 16, row i // 16. Transparent pixels = empty cells.
Up to 256 dogs per sheet; 1000 dogs -> 4 sheets of 250.
Also writes 4x upscaled copies in sheets/preview/ for human viewing.
Usage: python make_sheets.py --data data --out sheets --per 250
"""
import argparse
import os

import numpy as np
from PIL import Image

from gen_data import full_rgba
from palette import FURS

TILE, COLS = 16, 16


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="sheets")
    ap.add_argument("--per", type=int, default=250)
    a = ap.parse_args()
    d = np.load(os.path.join(a.data, "generated.npz"))
    halves, picks = d["halves"], d["picks"]
    os.makedirs(os.path.join(a.out, "preview"), exist_ok=True)
    n = len(halves)
    k = 0
    for s in range(0, n, a.per):
        sheet = np.zeros((TILE * COLS, TILE * COLS, 4), np.uint8)
        for j, i in enumerate(range(s, min(s + a.per, n))):
            p = dict(fur=int(picks[i, 0]), cloth=int(picks[i, 1]), acc=int(picks[i, 2]), glow=int(picks[i, 3]))
            r, c = divmod(j, COLS)
            sheet[r * TILE:(r + 1) * TILE, c * TILE:(c + 1) * TILE] = full_rgba(halves[i], p)
        k += 1
        name = os.path.join(a.out, f"sheet_{k:02d}.png")
        Image.fromarray(sheet, "RGBA").save(name)
        big = Image.fromarray(sheet, "RGBA").resize((TILE * COLS * 4,) * 2, Image.NEAREST)
        bg = Image.new("RGBA", big.size, (255, 154, 60, 255))
        Image.alpha_composite(bg, big).convert("RGB").save(os.path.join(a.out, "preview", f"sheet_{k:02d}_x4.png"))
        print(f"[sheets] {name}: {min(s + a.per, n) - s} dogs")
    # trait labels in tile order (sheet k, tile j) -> used to build the structured seed code
    import json
    traits = json.load(open(os.path.join(a.data, "traits.json"), encoding="utf-8"))
    json.dump(traits, open(os.path.join(a.out, "labels.json"), "w", encoding="utf-8"), indent=0)
    with open(os.path.join(a.out, "LAYOUT.txt"), "w", encoding="utf-8") as f:
        f.write(f"tile=16x16 px, grid={COLS}x{COLS} tiles per sheet, no gaps, {a.per} dogs per sheet\n"
                f"tile i -> x=(i%{COLS})*16, y=(i//{COLS})*16 ; transparent = empty cell\n"
                f"labels.json: trait labels of every dog, in order (sheet 1 tiles 0..{a.per-1}, then sheet 2 ...)\n")


if __name__ == "__main__":
    main()
