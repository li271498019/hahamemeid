"""Procedural generator of original 16x16 'pixel agent' avatars (training data).

Every avatar is left-right symmetric. It is stored as
  * a 16x16 map of cell classes (bg / outline / shade / body / accent / white)
  * body hue  (0..5)   -> body + shade colors
  * accent    (0..6)   -> color used by the ACCENT class
No logos, no faces of real people, no frogs: only cute robot / creature heads.

Usage:  python gen_data.py --n 1000 --seed 1234 --out data
"""
import argparse
import json
import os

import numpy as np
from PIL import Image

from palette import (BG, OUTLINE, SHADE, BODY, ACCENT, WHITE, PALETTE_RGB,
                     N_BODY_HUES, N_ACCENTS, class_to_index)

S = 16


class Canvas:
    def __init__(self):
        self.g = np.zeros((S, S), np.uint8)

    def put(self, r, dx, cls):
        """Symmetric put: dx = distance from center (0 -> columns 7 and 8)."""
        if 0 <= r < S and 0 <= dx < 8:
            self.g[r, 7 - dx] = cls
            self.g[r, 8 + dx] = cls

    def get(self, r, dx):
        if 0 <= r < S and 0 <= dx < 8:
            return self.g[r, 7 - dx]
        return -1


# ---------------------------------------------------------------- head shapes
def head_profile(kind, rng):
    """Return (top_row, list of half widths per row)."""
    if kind == "square":
        W = rng.integers(5, 7); H = rng.integers(8, 11)
        prof = [W - 1] + [W] * (H - 2) + [W - 1]
    elif kind == "circle":
        prof = [3, 5, 6, 6, 6, 6, 6, 6, 5, 3] if rng.random() < .5 else [2, 4, 5, 5, 5, 5, 5, 5, 4, 2]
    elif kind == "tv":
        H = rng.integers(7, 9)
        prof = [6] + [7] * (H - 2) + [6]
    elif kind == "egg":
        prof = [2, 4, 5, 5, 5, 5, 5, 5, 5, 4, 3]
    elif kind == "dome":
        prof = [3, 5, 6, 6, 6, 6, 6, 6, 6]
    elif kind == "trapezoid":
        prof = [4, 4, 5, 5, 5, 6, 6, 6, 6, 5]
    elif kind == "ghost":
        prof = [3, 5, 6, 6, 6, 6, 6, 6, 6, 6]
    else:
        raise ValueError(kind)
    H = len(prof)
    bottom = 14  # last interior row (outline goes on row 15)
    top = bottom - H + 1
    return top, prof


HEADS = ["square", "circle", "tv", "egg", "dome", "trapezoid", "ghost"]
EYES = ["dot", "big", "visor", "glow", "happy", "sleepy", "cyclops", "screen", "tall"]
MOUTHS = ["smile", "open", "grill", "cat", "o", "flat", "fang", "none"]
TOPS = ["antenna", "double_antenna", "cat_ears", "bunny_ears", "bear_ears",
        "horns", "propeller", "tuft", "none"]


def make_avatar(rng):
    c = Canvas()
    head = HEADS[rng.integers(len(HEADS))]
    top, prof = head_profile(head, rng)
    H = len(prof)
    hw_mid = prof[H // 2]

    # ---- top accessory first (gets body/accent; outline added later)
    topk = TOPS[rng.integers(len(TOPS))]
    acc_pixels = []  # (r,dx,cls)
    t = top
    if topk == "antenna":
        h = rng.integers(2, 4)
        for i in range(1, h + 1):
            acc_pixels.append((t - i, 0, SHADE))
        acc_pixels += [(t - h - 1, 0, ACCENT), (t - h - 2, 0, ACCENT)]
    elif topk == "double_antenna":
        d = rng.integers(2, 4)
        acc_pixels += [(t - 1, d, SHADE), (t - 2, d + 1, SHADE), (t - 3, d + 1, ACCENT), (t - 3, d + 2, ACCENT)]
    elif topk == "cat_ears":
        d = min(prof[0], 5) - 1
        for i in range(3):
            for k in range(3 - i):
                acc_pixels.append((t - 1 - i, d - k, ACCENT if (i == 0 and k == 1) else BODY))
    elif topk == "bunny_ears":
        d = 2
        for i in range(1, 5):
            acc_pixels += [(t - i, d, BODY), (t - i, d + 1, ACCENT if 1 < i < 4 else BODY)]
            if i < 4:
                acc_pixels += [(t - i, d + 2, BODY)]
        acc_pixels = [(r, dx, BODY if dx != d + 1 else cl) for (r, dx, cl) in acc_pixels]
    elif topk == "bear_ears":
        d = min(prof[0] + 1, 6) - 1
        for (rr, dd) in [(1, d), (1, d - 1), (2, d), (2, d - 1)]:
            acc_pixels.append((t - rr + 1 if rr == 1 else t - 1, dd, BODY))
        acc_pixels += [(t - 1, d, BODY), (t - 1, d - 1, ACCENT), (t - 2, d, BODY), (t - 2, d - 1, BODY)]
    elif topk == "horns":
        d = min(prof[0], 5) - 1
        acc_pixels += [(t - 1, d, ACCENT), (t - 2, d + 1, ACCENT)]
    elif topk == "propeller":
        acc_pixels += [(t - 1, 0, SHADE), (t - 2, 0, ACCENT), (t - 2, 1, ACCENT), (t - 2, 2, ACCENT)]
    elif topk == "tuft":
        acc_pixels += [(t - 1, 0, BODY), (t - 1, 1, BODY), (t - 2, 1, BODY), (t - 2, 2, BODY)]

    # ---- head interior
    for i, hw in enumerate(prof):
        for dx in range(hw):
            c.put(top + i, dx, BODY)
    if head == "ghost":  # wavy bottom
        for dx in range(1, prof[-1], 2):
            c.put(14, dx, BG)

    # ---- shading
    shade = rng.integers(3)
    if shade == 1:  # bottom row(s)
        for dx in range(prof[-1]):
            if c.get(14, dx) == BODY:
                c.put(14, dx, SHADE)
        if head != "ghost":
            for dx in range(prof[-2] - 1, prof[-2]):
                c.put(13, dx, SHADE)
    elif shade == 2:  # side edges
        for i, hw in enumerate(prof):
            if i > 0:
                c.put(top + i, hw - 1, SHADE)
        for dx in range(prof[-1]):
            if c.get(14, dx) == BODY:
                c.put(14, dx, SHADE)

    for (r, dx, cl) in acc_pixels:
        if c.get(r, dx) == BG:
            c.put(r, dx, cl)

    # ---- face: eyes
    eyek = EYES[rng.integers(len(EYES))]
    er = top + max(2, int(round(H * 0.33)))
    ed = 2 if hw_mid <= 5 else rng.integers(2, 4)
    if eyek == "dot":
        c.put(er, ed, OUTLINE); c.put(er + 1, ed, OUTLINE)
    elif eyek == "big":
        for rr in (er, er + 1):
            for dd in (ed, ed + 1):
                c.put(rr, dd, WHITE)
        c.put(er + 1, ed, OUTLINE)
    elif eyek == "visor":
        for dx in range(hw_mid - 1):
            c.put(er, dx, OUTLINE); c.put(er + 1, dx, OUTLINE)
        c.put(er, ed, ACCENT); c.put(er, ed + 1, ACCENT)
    elif eyek == "glow":
        for rr in (er, er + 1):
            c.put(rr, ed, ACCENT); c.put(rr, ed + 1, ACCENT)
        c.put(er, ed + 1, WHITE)
    elif eyek == "happy":
        c.put(er, ed, OUTLINE); c.put(er + 1, ed - 1, OUTLINE); c.put(er + 1, ed + 1, OUTLINE)
    elif eyek == "sleepy":
        c.put(er + 1, ed, OUTLINE); c.put(er + 1, ed + 1, OUTLINE)
    elif eyek == "cyclops":
        for rr in range(er - 1, er + 2):
            c.put(rr, 0, WHITE); c.put(rr, 1, WHITE)
        c.put(er - 1, 1, BODY if c.get(er - 1, 1) == WHITE else c.get(er - 1, 1))
        c.put(er + 1, 1, BODY if c.get(er + 1, 1) == WHITE else c.get(er + 1, 1))
        c.put(er, 0, OUTLINE)
    elif eyek == "screen":
        for dx in range(1, hw_mid - 1):
            c.put(er - 1, dx, OUTLINE); c.put(er, dx, OUTLINE); c.put(er + 1, dx, OUTLINE)
        c.put(er - 1, 0, OUTLINE); c.put(er, 0, OUTLINE); c.put(er + 1, 0, OUTLINE)
        c.put(er, ed, WHITE); c.put(er - 1, ed, WHITE)
    elif eyek == "tall":
        for rr in (er - 1, er, er + 1):
            c.put(rr, ed, WHITE)
        c.put(er, ed, OUTLINE); c.put(er + 1, ed, OUTLINE)

    # cheeks
    mr = min(er + 3 + (1 if H >= 10 else 0), 13)
    if rng.random() < .5 and eyek not in ("screen", "visor"):
        c.put(mr - 1, ed + 1 if ed + 1 < hw_mid else ed, ACCENT)

    # ---- mouth
    mouthk = MOUTHS[rng.integers(len(MOUTHS))]
    if mouthk == "smile":
        c.put(mr, 0, OUTLINE); c.put(mr - 1, 1, OUTLINE)
    elif mouthk == "open":
        c.put(mr, 0, OUTLINE); c.put(mr, 1, OUTLINE); c.put(mr + 1, 0, ACCENT)
        if c.get(mr + 1, 1) != BG:
            c.put(mr + 1, 1, OUTLINE)
    elif mouthk == "grill":
        for dx in range(3):
            c.put(mr, dx, OUTLINE)
        c.put(mr, 1, WHITE)
        c.put(mr - 1, 2, OUTLINE)
    elif mouthk == "cat":
        c.put(mr, 1, OUTLINE); c.put(mr - 1, 0, OUTLINE)
    elif mouthk == "o":
        c.put(mr, 0, OUTLINE)
    elif mouthk == "flat":
        c.put(mr, 0, OUTLINE); c.put(mr, 1, OUTLINE)
    elif mouthk == "fang":
        c.put(mr, 0, OUTLINE); c.put(mr, 1, OUTLINE); c.put(mr + 1, 1, WHITE)

    # ---- side bolts (only when there is room)
    if hw_mid <= 5 and rng.random() < .4:
        c.put(er + 1, hw_mid + 1, ACCENT); c.put(er + 2, hw_mid + 1, ACCENT)

    # ---- outer outline around everything that is not background
    g = c.g
    obj = g != BG
    out = np.zeros_like(obj)
    out[1:, :] |= obj[:-1, :]; out[:-1, :] |= obj[1:, :]
    out[:, 1:] |= obj[:, :-1]; out[:, :-1] |= obj[:, 1:]
    g[out & ~obj] = OUTLINE

    body = int(rng.integers(N_BODY_HUES))
    acc = int(rng.integers(N_ACCENTS))
    while acc == body:
        acc = int(rng.integers(N_ACCENTS))
    # avoid look-alikes of famous characters (yellow + pointy ears / one-eye goggle)
    if body == 2 and (topk in ("cat_ears", "bunny_ears", "horns") or eyek == "cyclops"):
        body = int(rng.choice([0, 1, 3, 4, 5]))
        while acc == body:
            acc = int(rng.integers(N_ACCENTS))
    meta = dict(head=head, eyes=eyek, mouth=mouthk, top=topk, shade=int(shade))
    assert (g[:, :8] == g[:, 8:][:, ::-1]).all()
    return g.copy(), body, acc, meta


def to_rgb(g, body, acc):
    lut = np.array([PALETTE_RGB[class_to_index(k, body, acc)] for k in range(6)], np.uint8)
    return lut[g]


def grid_image(items, cols=8, scale=8, gap=2, bg=(40, 40, 48)):
    rows = (len(items) + cols - 1) // cols
    cell = S * scale
    W = cols * cell + (cols + 1) * gap
    Hh = rows * cell + (rows + 1) * gap
    im = Image.new("RGB", (W, Hh), bg)
    for i, rgb in enumerate(items):
        r, cc = divmod(i, cols)
        tile = Image.fromarray(rgb).resize((cell, cell), Image.NEAREST)
        im.paste(tile, (gap + cc * (cell + gap), gap + r * (cell + gap)))
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--out", default="data")
    ap.add_argument("--preview", default="preview-dataset.png")
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    os.makedirs(a.out, exist_ok=True)
    grids, bodies, accs, metas = [], [], [], []
    seen = set()
    while len(grids) < a.n:
        g, b, ac, m = make_avatar(rng)
        key = (g.tobytes(), b, ac)
        if key in seen:
            continue
        seen.add(key)
        grids.append(g); bodies.append(b); accs.append(ac); metas.append(m)
    np.savez_compressed(os.path.join(a.out, "dataset.npz"), grids=np.array(grids),
                        body=np.array(bodies), accent=np.array(accs))
    with open(os.path.join(a.out, "meta.json"), "w") as f:
        json.dump(metas, f)
    idx = rng.choice(a.n, 48, replace=False)
    grid_image([to_rgb(grids[i], bodies[i], accs[i]) for i in idx]).save(a.preview)
    print(f"generated {a.n} unique avatars -> {a.out}/dataset.npz ; preview -> {a.preview}")


if __name__ == "__main__":
    main()
