"""Procedural generator of ORIGINAL front-facing 16x16 shiba 'haha dogs'.

Left-right symmetric: we draw the left half (16 rows x 8 cols) and mirror it.
Background is NOT drawn (class EMPTY = transparent). The contract composes a
24x24 SVG: solid background chosen from the seed, dog placed bottom-center
(x offset 4, y offset 8), shoulders touching the bottom edge.

Each sample = 16x8 half map of cell classes + 4 color picks
(fur variant, cloth, accessory, glow).
Usage: python gen_data.py --n 16 --seed 7 --preview preview-dog-v4.png
"""
import argparse
import json
import os

import numpy as np
from PIL import Image

from palette import (EMPTY, OUT, FUR, FUR_SH, MARK, CLOTH, CLOTH_SH, ACC, GLOW,
                     WHITE, PINK, FURS, CLOTHS, ACCS, GLOWS, BGS, class_rgb, rgb)
from dog import BASE, CH, to_half, mirror

H, W = 16, 8
CANVAS, OX, OY = 24, 4, 8

# every dog gets headwear or a hairstyle; ears always stay visible
HEAD = [("beanie", 10), ("cap", 9), ("backwards_cap", 8), ("headband", 8),
        ("hood", 8), ("headphones", 9), ("tuft", 9), ("spiky", 9), ("mohawk", 8),
        ("party_hat", 5), ("propeller", 5), ("crown", 4), ("halo", 4), ("third_eye", 4)]
EARS = [("normal", 86), ("cyber", 14)]
EYES = [("normal", 22), ("shades", 12), ("laser", 8), ("visor", 7), ("neon_specs", 6),
        ("squint_smile", 10), ("wide_stare", 9), ("sleepy", 9), ("angry", 8), ("smug", 9)]
MOUTH = [("smile", 26), ("tongue", 16), ("grin", 9), ("laugh", 10), ("o_mouth", 8),
         ("flat", 9), ("bubblegum", 8), ("bandana", 6)]
NECK = [("none", 70), ("gold_chain", 15), ("spiked_collar", 10), ("bell_collar", 5)]

OVER = {
# hats sit BETWEEN the ears (rows 0-4, cols 5-10) and widen only below the ears (row 5+)
"beanie":        {0: "......OW", 1: ".....OCC", 2: ".....OCC", 3: ".....OCC", 4: ".....OCC", 5: "..OCcCcC", 6: "..OOOOOO"},
"cap":           {1: "......OO", 2: ".....OCC", 3: ".....OCC", 4: ".....OCC", 5: "..OOCCCC", 6: ".OCccccc", 7: "OOOOOOOO"},
"backwards_cap": {1: "......OO", 2: ".....OCC", 3: ".....OCC", 4: ".....OCC", 5: "..OCCCCC", 6: "..OOOOOA"},
"headband":      {5: "OCCCCCCC", 6: "OcccccAA"},
"hood":          {1: "......OO", 2: ".....OCC", 3: ".....OCC", 4: ".....OCC", 5: "OCCCCCCC", 6: "OCcOOOOO", 7: "OCO.....", 8: "OO......"},
"headphones":    {1: ".....OOO", 2: ".....OAA", 3: ".....OOO",
                  8: "OO......", 9: "AAO.....", 10: "AAO.....", 11: "AAO.....", 12: "OO......"},
"tuft":          {0: "....O.O.", 1: "....OOFO", 2: ".....OFF", 3: ".....OFF", 4: "......FF"},
"spiky":         {0: ".....O.O", 1: ".....OOC", 2: ".....OCC", 3: ".....OCC", 4: ".....OCC", 5: "..OOCCcc"},
"mohawk":        {0: "......OO", 1: "......OC", 2: "......OC", 3: "......OC", 4: "......OC", 5: ".......c"},
"party_hat":     {0: ".......W", 1: "......OO", 2: "......OC", 3: ".....OCA", 4: ".....OAC", 5: "....OCCA", 6: "....OOOO"},
"propeller":     {0: "....OAAG", 1: "......OO", 2: ".....OCC", 3: ".....OCC", 4: ".....OCC", 5: "..OCcCcC", 6: "..OOOOOO"},
"crown":         {0: ".....O.O", 1: ".....OAO", 2: ".....OAA", 3: ".....OAG"},
"halo":          {0: "....AAAA", 1: "........", 2: "......O.", 3: ".....OFO", 4: "......FF"},
"third_eye":     {1: "......O.", 2: ".....OFO", 3: ".....OFF", 4: "......OA", 5: "......AG", 6: "......OA"},
}


def pick(rng, opts):
    w = np.array([o[1] for o in opts], float)
    return opts[rng.choice(len(opts), p=w / w.sum())][0]


def draw(g, over):
    for r, line in over.items():
        for c, ch in enumerate(line):
            if ch != ".":
                g[r, c] = CH[ch]


def make_dog(rng, forced=None):
    forced = forced or {}
    g = to_half(BASE).copy()
    t, force = {}, {}
    # color choices are drawn first so trait rules can reference them
    c_cloth = forced.get("cloth", int(rng.integers(len(CLOTHS))))
    c_acc = forced.get("acc", int(rng.integers(len(ACCS))))
    c_glow = forced.get("glow", int(rng.integers(len(GLOWS))))
    blush_roll = forced.get("blush", bool(rng.random() < .3))
    fw = np.array([f[3] for f in FURS], float)
    fur = forced.get("fur", int(rng.choice(len(FURS), p=fw / fw.sum())))
    t["fur"] = FURS[fur][0]

    head = forced.get("head", pick(rng, HEAD))
    t["head"] = head
    draw(g, OVER[head])
    if head in ("crown", "halo"):
        force["acc"] = 0

    ears = "cyber" if FURS[fur][0] == "cyborg" else forced.get("ears", pick(rng, EARS))
    t["ears"] = ears
    if ears == "cyber":
        g[2, 2] = ACC; g[3, 2] = ACC
        g[2, 3] = GLOW; g[3, 3] = GLOW
        if g[3, 4] == PINK:
            g[3, 4] = GLOW
        force.setdefault("acc", 1)

    eyes = forced.get("eyes", pick(rng, EYES))
    t["eyes"] = eyes
    er, ec = 8, 3
    if eyes == "shades":
        draw(g, {7: "..OOOOOO", 8: ".OWOOOO.", 9: ".OOOOOO.", 10: "..OOOO.."})
    elif eyes == "laser":
        g[er, ec] = GLOW; g[er, ec + 1] = GLOW; g[er + 1, ec] = GLOW; g[er + 1, ec + 1] = WHITE
        g[er, 0] = GLOW; g[er, 1] = GLOW; g[er, 2] = GLOW; g[er + 1, 0] = GLOW
        force["glow"] = c_glow if c_glow in (0, 1) else 0     # lasers are red (or cyan)
    elif eyes == "visor":
        draw(g, {7: "OOOOOOOO", 8: "OAGGGGGG", 9: "OOOOOOOO"})
    elif eyes == "neon_specs":
        draw(g, {7: "..OOOO..", 8: ".OOGGOOO", 9: "..OGWO..", 10: "...OO..."})
    elif eyes == "squint_smile":   # ^^
        g[er, ec] = OUT; g[er, ec + 1] = OUT
        g[er + 1, ec] = FUR; g[er + 1, ec + 1] = FUR
        g[er + 1, ec - 1] = OUT; g[er + 1, ec + 2] = OUT
    elif eyes == "wide_stare":     # big white eyes, tiny pupils
        draw(g, {7: "..OOOO..", 8: ".OWWWO..", 9: ".OWOWO..", 10: "..OOO..."})
        g[8, 3] = WHITE; g[9, 3] = OUT; g[9, 2] = WHITE; g[8, 2] = WHITE; g[9, 4] = WHITE; g[8, 4] = WHITE
    elif eyes == "sleepy":
        g[er, ec] = FUR_SH; g[er, ec + 1] = FUR_SH
        g[er + 1, ec] = OUT; g[er + 1, ec + 1] = OUT; g[er + 1, ec - 1] = OUT
    elif eyes == "angry":
        g[6, 4] = OUT; g[6, 5] = FUR; g[7, 5] = OUT; g[7, 6] = OUT
        g[er, ec + 1] = OUT
    elif eyes == "smug":
        g[er - 1, ec] = OUT; g[er - 1, ec + 1] = OUT
        g[er, ec] = FUR_SH; g[er, ec + 1] = FUR_SH
        g[er + 1, ec] = OUT; g[er + 1, ec + 1] = WHITE

    mouth = forced.get("mouth", pick(rng, MOUTH))
    t["mouth"] = mouth
    if mouth == "tongue":
        g[13, 7] = PINK; g[14, 7] = PINK; g[14, 6] = OUT; g[15, 7] = OUT
    elif mouth == "grin":
        g[13, 7] = WHITE
    elif mouth == "laugh":
        draw(g, {12: ".OMMMOMO", 13: "..OMMOOO", 14: "...OOOPP"})
        g[13, 6] = OUT; g[13, 5] = MARK
    elif mouth == "o_mouth":
        g[12, 5] = MARK; g[13, 6] = OUT; g[13, 7] = PINK
    elif mouth == "flat":
        g[12, 5] = MARK; g[13, 6] = OUT; g[13, 5] = OUT; g[13, 7] = OUT
    elif mouth == "bubblegum":
        draw(g, {12: "......OO", 13: ".....OPP", 14: "....OPPW", 15: ".....OPP"})
    elif mouth == "bandana":
        draw(g, {10: "OCCCCCCC", 11: "OCCCCCCC", 12: ".OCCCCCC", 13: "..OcccCC", 14: "...OOcCC", 15: "....OOcc"})

    neck = forced.get("neck", pick(rng, NECK))
    if head == "hood":
        neck = "hoodie"
    t["neck"] = neck
    if neck == "gold_chain":
        draw(g, {15: "..OFAAAA"}); force.setdefault("acc", 0)
    elif neck == "spiked_collar":
        draw(g, {15: "..OOWOWO"})
    elif neck == "bell_collar":
        draw(g, {15: "..OCCCCA"}); force.setdefault("acc", 0)
    elif neck == "hoodie":
        draw(g, {15: "..OCCCWC"})

    t["blush"] = False
    if blush_roll and eyes not in ("visor", "shades") and mouth != "bandana":
        g[10, 2] = PINK; t["blush"] = True

    if FURS[fur][0] == "hologram":
        for r in range(1, H, 3):
            g[r][g[r] == FUR] = FUR_SH
            g[r][g[r] == MARK] = FUR

    p = dict(fur=fur, cloth=c_cloth, acc=c_acc, glow=c_glow)
    p.update(force)
    if FURS[fur][0] == "black & tan":      # keep dark fur readable
        if p["cloth"] == 0:
            p["cloth"] = 6
        if p["acc"] == 2:
            p["acc"] = 0
    return g, p, t


def render(half, p, bg):
    """24x24 composition exactly as the contract would draw it."""
    g = mirror(half)
    out = np.zeros((CANVAS, CANVAS, 3), np.uint8)
    out[:] = bg
    for r in range(16):
        for c in range(16):
            v = class_rgb(int(g[r, c]), p)
            if v:
                out[OY + r, OX + c] = v
    return out


def grid_image(items, cols=4, scale=10, gap=6, bg=(20, 20, 24)):
    rows = (len(items) + cols - 1) // cols
    cell = CANVAS * scale
    im = Image.new("RGB", (cols * cell + (cols + 1) * gap, rows * cell + (rows + 1) * gap), bg)
    for i, a in enumerate(items):
        r, c = divmod(i, cols)
        im.paste(Image.fromarray(a).resize((cell, cell), Image.NEAREST),
                 (gap + c * (cell + gap), gap + r * (cell + gap)))
    return im


def full_rgba(half, p):
    """16x16 RGBA tile; EMPTY cells are fully transparent."""
    g = mirror(half)
    out = np.zeros((16, 16, 4), np.uint8)
    for r in range(16):
        for c in range(16):
            v = class_rgb(int(g[r, c]), p)
            if v:
                out[r, c, :3] = v
                out[r, c, 3] = 255
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", default="data")
    ap.add_argument("--preview", default="preview-dataset.png")
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    os.makedirs(a.out, exist_ok=True)
    G, P, TR, seen = [], [], [], set()
    while len(G) < a.n:
        g, p, t = make_dog(rng)
        key = full_rgba(g, p).tobytes()          # dedupe on what you SEE
        if key in seen:
            continue
        seen.add(key); G.append(g); P.append(p); TR.append(t)
    np.savez_compressed(os.path.join(a.out, "generated.npz"), halves=np.array(G),
                        picks=np.array([[p["fur"], p["cloth"], p["acc"], p["glow"]] for p in P]))
    json.dump(TR, open(os.path.join(a.out, "traits.json"), "w"), indent=0)
    bg_rng = np.random.default_rng(a.seed + 1)
    items = [render(G[i], P[i], rgb(BGS[int(bg_rng.integers(len(BGS)))])) for i in range(min(a.n, 32))]
    grid_image(items, cols=8, scale=6).save(a.preview)
    print(f"[gen] {a.n} unique dogs -> {a.out}/generated.npz , traits.json , {a.preview}")


if __name__ == "__main__":
    main()
