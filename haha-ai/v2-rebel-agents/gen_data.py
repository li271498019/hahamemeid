"""Procedural generator of ORIGINAL 16x16 'Rebel Agents' busts (training data).

3/4 view busts facing right, flat punk-style pixels, solid muted background.
Archetypes: human hacker, android, hologram AI, cyber ape, cyber dog,
zombie, alien, skull-bot.  Traits: hair / hats / hood / headphones / crown /
halo / cables / antenna / third-eye chip, shades / VR visor / laser eyes /
3D glasses / eye patch / cyber eye, cigarette / pipe / vape / bandana,
earring, gold chain, tee/jacket, rare glitch.

Each sample = 16x16 map of cell CLASSES + 6 color picks (palette indices).
Usage: python gen_data.py --n 1000 --seed 2026 --out data
"""
import argparse
import collections
import json
import os

import numpy as np
from PIL import Image

from palette import (BG, OUT, SKIN, SKIN_SH, HAIR, CLOTH, CLOTH_SH, ACC, GLOW,
                     WHITE, class_rgb, BG_CHOICES, HAIR_CHOICES,
                     CLOTH_CHOICES, ACC_CHOICES, GLOW_CHOICES)
from templates import T, grid, CH

S = 16

ARCHETYPES = [  # name, template, skin palette idx options, weight(%)
    ("human",    "human", [7, 8, 9], 44),
    ("android",  "human", [10],      14),
    ("ape",      "ape",   [13],      10),
    ("dog",      "dog",   [13, 10, 8], 8),
    ("zombie",   "human", [15],       8),
    ("hologram", "human", [11],       7),
    ("alien",    "alien", [12],       6),
    ("skull",    "skull", [14],       3),
]

# ------------------------------------------------------------ head overlays
# '.' = leave as is.  Drawn for the human head (top=3); shifted for others.
HEAD = {
"short": [
    "................",
    "................",
    "....OOOOOOO.....",
    "...OHHHHHHHO....",
    "..OHHHHHHHHHO...",
    "..OHHHHHHHHHO...",
    "..OHHHHH...HO...",
    "..OHHHO.........",
    "..OHH...........",
],
"mohawk": [
    ".....O.O.O......",
    "....OHOHOHO.....",
    "....OHHHHHO.....",
    "....OHHHHHO.....",
    "...OSHHHHHSO....",
    "......HHH.......",
],
"wild": [
    "...O.OO.OO......",
    "..OHOHHOHHO.....",
    ".OHHHHHHHHHOO...",
    ".OHHHHHHHHHHHO..",
    "OHHHHHHHHHHHHO..",
    "OHHHHHHHHHHHO...",
    "OHHHHHH...HHO...",
    "OHHHHO......O...",
    ".OHHO...........",
    ".OHHO...........",
    "..OO............",
],
"long": [
    "................",
    "................",
    "....OOOOOOO.....",
    "...OHHHHHHHO....",
    "..OHHHHHHHHHO...",
    "..OHHHHHHHHHHO..",
    ".OHHHHHH...HO...",
    ".OHHHHO.........",
    ".OHHHO..........",
    ".OHHHO..........",
    ".OHHHO..........",
    ".OHHHO..........",
    ".OHHHHO.........",
    "..OHHHO.........",
    "...OOO..........",
],
"spiky": [
    "..O..O..O.......",
    "..OO.OO.OOO.....",
    "..OHOOHOOHHO....",
    "..OHHHHHHHHHO...",
    "..OHHHHHHHHHO...",
    "..OHHHHHHHHHO...",
    "..OHHHH....HO...",
    "..OHHO..........",
],
"beanie": [
    "................",
    ".....OOOOO......",
    "...OOCCCCCOO....",
    "..OCCCCCCCCCO...",
    "..OCCCCCCCCCO...",
    "..OcccccccccO...",
    "..OOOOOOOOOOO...",
],
"cap": [
    "................",
    "................",
    "....OOOOOOO.....",
    "...OAAAAAAAO....",
    "..OAAAAAAAAAOOO.",
    "..OAAAAAAAAAAAAO",
    "..OOOOOOOOOOOOO.",
    "..OHHO..........",
],
"hood": [
    "....OOOOOOO.....",
    "...OCCCCCCCOO...",
    "..OCCCCCCCCCCO..",
    ".OCCCCCCCCCCCO..",
    ".OCCCcOOOOOOCO..",
    ".OCCcO......OO..",
    ".OCCcO..........",
    ".OCCcO..........",
    "OCCCcO..........",
    "OCCCcO..........",
    "OCCCcO..........",
    "OCCCcO..........",
    "OCCCCcO.........",
    "OCCCCCcO......O.",
    "OCCCCCCO....OCO.",
    "OCCCCCCCO..OCCCO",
],
"crown": [
    "....O.O.O.O.....",
    "....OAOAOAO.....",
    "....OAAGAAO.....",
],
"halo": [
    "...OAAAAAAO.....",
    "................",
],
"antenna": [
    "..G.............",
    "..O.............",
    "...O............",
],
"headphones": [
    "................",
    "................",
    ".....OOOOO......",
    "....OAAAAAO.....",
    "...OAO...OAO....",
    "..OAO...........",
    "..OAO...........",
    ".OAAAO..........",
    ".OAAAO..........",
    ".OAAAO..........",
    "..OOO...........",
],
"cables": [
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "..AO............",
    ".O..............",
    "O.AO............",
    "O.O.............",
    ".O..............",
    "O...............",
],
}
# hair that can go under headphones / halo / crown / antenna / cables
BASE_HAIR = ["short", "spiky", "long", "none"]

HEAD_SLOTS = {  # per template: (option, weight)
    "human": [("none", 7), ("short", 13), ("mohawk", 9), ("wild", 8), ("long", 8),
              ("spiky", 7), ("beanie", 9), ("cap", 8), ("hood", 11),
              ("headphones", 7), ("cables", 4), ("antenna", 3), ("crown", 1.5),
              ("halo", 2), ("thirdeye", 2.5)],
    "ape": [("none", 40), ("beanie", 12), ("cap", 12), ("headphones", 10),
            ("hood", 10), ("crown", 4), ("halo", 4), ("cables", 8)],
    "skull": [("none", 30), ("hood", 25), ("beanie", 10), ("headphones", 10),
              ("crown", 8), ("halo", 7), ("cables", 10)],
    "dog": [("none", 60), ("halo", 10), ("crown", 8), ("cables", 12), ("antenna", 10)],
    "alien": [("none", 55), ("thirdeye", 15), ("cables", 15), ("headphones", 15)],
}
EYE_SLOTS = {
    "human": [("normal", 40), ("shades", 14), ("visor", 10), ("laser", 7),
              ("3d", 6), ("patch", 6), ("cybereye", 9), ("angry", 8)],
    "ape": [("normal", 45), ("shades", 18), ("visor", 10), ("laser", 10), ("3d", 7), ("patch", 10)],
    "dog": [("normal", 55), ("shades", 15), ("laser", 15), ("3d", 7), ("visor", 8)],
    "skull": [("normal", 70), ("laser", 30)],
    "alien": [("normal", 80), ("laser", 20)],
}
MOUTH_SLOTS = {
    "human": [("none", 46), ("cigarette", 9), ("pipe", 5), ("vape", 6),
              ("bandana", 9), ("smile", 12), ("teeth", 10)],
    "ape": [("none", 50), ("cigarette", 20), ("pipe", 10), ("vape", 10), ("bandana", 10)],
    "skull": [("none", 60), ("cigarette", 25), ("vape", 15)],
    "alien": [("none", 70), ("cigarette", 15), ("vape", 15)],
    "dog": [("none", 100)],
}


def pick(rng, opts):
    names = [o[0] for o in opts]
    w = np.array([o[1] for o in opts], float)
    return names[rng.choice(len(names), p=w / w.sum())]


def overlay(g, rows, dy=0):
    for r, line in enumerate(rows):
        rr = r + dy
        if not 0 <= rr < S:
            continue
        for c, ch in enumerate(line):
            if ch != ".":
                g[rr, c] = CH[ch]


def put(g, r, c, v):
    if 0 <= r < S and 0 <= c < S:
        g[r, c] = v


def make_bust(rng):
    names = [a[0] for a in ARCHETYPES]
    w = np.array([a[3] for a in ARCHETYPES], float)
    a = ARCHETYPES[rng.choice(len(names), p=w / w.sum())]
    arch, tname, skins = a[0], a[1], a[2]
    A = T[tname]
    g = grid(tname)
    dy = A["top"] - 3
    traits = {"type": arch}
    force = {}

    # ---------------- archetype details
    if arch == "android":
        ear_r, ear_c = A["ear"]
        put(g, ear_r, ear_c + 1, ACC); put(g, ear_r - 1, ear_c + 1, OUT)
        put(g, 6, 5, SKIN_SH); put(g, 6, 6, SKIN_SH); put(g, 7, 5, SKIN_SH)
        put(g, 10, 6, GLOW); put(g, 11, 6, SKIN_SH); put(g, 11, 7, SKIN_SH)
    elif arch == "zombie":
        for (r, c) in [(5, 9), (6, 9), (6, 10), (10, 7), (11, 8), (5, 5)]:
            if rng.random() < .55 and g[r, c] == SKIN:
                g[r, c] = SKIN_SH
    elif arch == "hologram":
        for r in range(4, 16, 3):
            for c in range(S):
                if g[r, c] == SKIN:
                    g[r, c] = SKIN_SH
        for (r, c) in [(14, 5), (14, 7), (15, 4), (15, 6), (15, 8)]:
            put(g, r, c, BG)
        g[g == WHITE] = GLOW
    elif arch == "dog":
        g[g == WHITE] = np.where(np.arange(S)[None, :].repeat(S, 0)[g == WHITE] > 10, WHITE, WHITE)
        er, (b, f) = A["eye_row"], A["eyes"]
        put(g, er, b - 1, OUT); put(g, er, f - 1, OUT)  # dark dog eyes
        put(g, er - 1, b - 1, WHITE); put(g, er - 1, f - 1, WHITE)  # glints above

    # ---------------- head slot
    head = pick(rng, HEAD_SLOTS[tname])
    traits["head"] = head
    if head in ("headphones", "halo", "crown", "antenna", "cables") and tname == "human":
        base = BASE_HAIR[rng.integers(len(BASE_HAIR))]
        if head == "crown" and base == "long":
            base = "short"
        if base != "none":
            overlay(g, HEAD[base])
            traits["hair"] = base
    if head == "thirdeye":
        r = A["top"] + 3
        c = A["eyes"][0] + 1
        for (rr, cc) in [(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)]:
            put(g, rr, cc, ACC)
        put(g, r, c, GLOW)
    elif head != "none":
        rows = HEAD[head]
        if head == "crown":
            force["acc"] = 21
        if head == "halo":
            force["acc"] = 21
            rows = HEAD["halo"]
            rows = rows if dy >= 0 else rows
        overlay(g, rows, dy if tname != "dog" else (-1 if head in ("crown", "halo") else dy))
    # dog ears survive crown/halo by drawing crown above
    # ---------------- eyes
    eyes = pick(rng, EYE_SLOTS[tname])
    traits["eyes"] = eyes
    er = A["eye_row"]; b, f = A["eyes"]
    if eyes == "shades":
        for c in range(b - 2, f + 2):
            put(g, er, c, OUT); put(g, er - 1, c, OUT)
        put(g, er - 1, b - 1, WHITE); put(g, er - 1, f - 1, WHITE)
        if g[er, f - 2] == OUT and f - b >= 3:
            put(g, er, f - 2, SKIN if tname != "dog" else SKIN)
    elif eyes == "visor":
        for c in range(b - 2, min(A["face_right"] + 1, 16)):
            put(g, er - 1, c, ACC); put(g, er, c, ACC)
        for c in range(b - 1, f + 1):
            put(g, er, c, GLOW)
        put(g, er - 2, b - 2, OUT)
    elif eyes == "laser":
        for c in (b - 1, b, f - 1, f):
            put(g, er, c, GLOW)
        for c in range(f + 1, 16):
            put(g, er, c, GLOW)
        put(g, er + 1, 15, GLOW); put(g, er - 1, 15, GLOW)
        force.setdefault("glow", 20 if rng.random() < .7 else 22)
    elif eyes == "3d":
        for c in range(b - 2, f + 2):
            put(g, er - 1, c, WHITE)
        put(g, er, b - 1, GLOW); put(g, er, b, GLOW)
        put(g, er, f - 1, ACC); put(g, er, f, ACC)
        put(g, er, b + 1, WHITE); put(g, er, f + 1, WHITE); put(g, er, b - 2, WHITE)
        force["glow"] = 20; force["acc"] = 22
    elif eyes == "patch":
        for (r, c) in [(er, f - 1), (er, f), (er + 1, f - 1), (er + 1, f), (er - 1, f - 1), (er - 1, f)]:
            put(g, r, c, OUT)
        for k in range(1, 5):
            put(g, er - 1 - (k // 2), f - 1 - k, OUT)
    elif eyes == "cybereye":
        put(g, er, f - 1, GLOW); put(g, er, f, GLOW)
        put(g, er - 1, f - 1, ACC); put(g, er - 1, f, ACC); put(g, er + 1, f, ACC)
    elif eyes == "angry":
        put(g, er - 1, b - 1, OUT); put(g, er - 1, f, OUT)
        put(g, er - 2, b - 2, OUT); put(g, er - 1, f - 1, OUT)

    # ---------------- mouth
    mouth = pick(rng, MOUTH_SLOTS[tname])
    traits["mouth"] = mouth
    mr, me = A["mouth_row"], A["mouth_end"]
    if mouth == "cigarette":
        for c in range(me + 1, me + 4):
            put(g, mr, c, WHITE)
        put(g, mr, me + 4, GLOW)
        put(g, mr - 2, me + 4, WHITE); put(g, mr - 3, me + 5, WHITE); put(g, mr - 4, me + 4, WHITE)
        if "glow" not in force and rng.random() < .6:
            force["glow"] = 20
    elif mouth == "pipe":
        put(g, mr, me + 1, OUT); put(g, mr, me + 2, OUT); put(g, mr + 1, me + 2, OUT)
        put(g, mr, me + 3, OUT); put(g, mr - 1, me + 3, OUT); put(g, mr - 1, me + 4, OUT)
        put(g, mr, me + 4, OUT); put(g, mr - 1, me + 3, HAIR if False else ACC)
        put(g, mr - 3, me + 4, WHITE)
    elif mouth == "vape":
        for c in range(me + 1, me + 4):
            put(g, mr, c, ACC)
        put(g, mr, me + 4, GLOW)
        for (r, c) in [(mr - 1, me + 3), (mr - 1, me + 4), (mr - 2, me + 4), (mr - 2, me + 5), (mr - 1, me + 5)]:
            put(g, r, c, WHITE)
    elif mouth == "bandana":
        for r in range(mr - 2, mr + 2):
            for c in range(A["face_left"], 16):
                if g[r, c] in (SKIN, SKIN_SH) or (g[r, c] == OUT and c in (me, me - 1) and r == mr):
                    g[r, c] = CLOTH_SH if r == mr + 1 else CLOTH
        for c in range(A["face_left"], 16):
            if g[mr - 3, c] in (SKIN, SKIN_SH) and g[mr - 2, c] in (CLOTH, CLOTH_SH):
                pass
    elif mouth == "smile":
        put(g, mr - 1, me + 1, OUT)
    elif mouth == "teeth":
        put(g, mr + 1, me, WHITE)

    # ---------------- facial hair (humans / zombies / androids)
    if tname == "human" and mouth != "bandana" and arch != "hologram" and rng.random() < .22:
        kind = ["beard", "mustache", "goatee"][rng.integers(3)]
        traits["facial_hair"] = kind
        if kind == "mustache":
            for c in (me - 2, me - 1, me):
                put(g, mr - 1, c, HAIR)
        elif kind == "goatee":
            put(g, mr + 1, me - 1, HAIR); put(g, mr + 1, me - 2, HAIR); put(g, mr, me - 2, HAIR)
            put(g, mr - 1, me - 1, HAIR); put(g, mr - 1, me, HAIR)
        else:
            for r in range(mr - 2, 15):
                for c in range(4, 14):
                    if g[r, c] in (SKIN, SKIN_SH) and (r >= mr - 1 or c <= 6):
                        g[r, c] = HAIR
            put(g, mr, me - 1, OUT); put(g, mr, me, OUT)

    # ---------------- ear / neck
    if A["ear"] is not None and arch != "android" and head not in ("hood", "headphones", "long", "wild") \
            and traits.get("hair") not in ("long",) and rng.random() < .22:
        r, c = A["ear"]
        put(g, r + 1, c + 1, ACC); traits["earring"] = True
    clothes = "none"
    if False:
        clothes = "none"
        if clothes != "none":
            overlay(g, ["................"] * 14 + [
                "OOOOO......OOOO.",
                "OCCCCO.....CCCCO" if clothes == "tee" else "OCCCcOW...WcCCCO"])
            # keep neck skin
    traits["clothes"] = clothes
    if rng.random() < .12 and tname != "alien":
        r0, c0, c1 = A["chain"]
        for c in range(c0, c1 + 1):
            if g[r0, c] in (SKIN, SKIN_SH, OUT, CLOTH, CLOTH_SH, WHITE):
                g[r0, c] = ACC
        force.setdefault("acc", 21); traits["chain"] = True

    # ---------------- rare glitch
    if rng.random() < .03:
        r = int(rng.integers(5, 12))
        g[r:r + 2] = np.roll(g[r:r + 2], 1, axis=1)
        g[r + 2][g[r + 2] == BG] = GLOW
        traits["glitch"] = True

    picks = dict(
        bg=int(rng.choice(BG_CHOICES)),
        skin=int(rng.choice(skins)),
        hair=int(rng.choice(HAIR_CHOICES)),
        cloth=int(rng.choice(CLOTH_CHOICES)),
        acc=int(rng.choice(ACC_CHOICES)),
        glow=int(rng.choice(GLOW_CHOICES)),
    )
    if arch == "ape":
        picks["hair"] = int(rng.choice([19, 16, 18, 17]))
    picks.update(force)
    return g, picks, traits


def to_rgb(g, picks):
    lut = np.array([class_rgb(k, picks) for k in range(10)], np.uint8)
    return lut[g]


def grid_image(items, cols=8, scale=8, gap=3, bg=(24, 24, 28)):
    rows = (len(items) + cols - 1) // cols
    cell = S * scale
    im = Image.new("RGB", (cols * cell + (cols + 1) * gap, rows * cell + (rows + 1) * gap), bg)
    for i, rgb in enumerate(items):
        r, c = divmod(i, cols)
        im.paste(Image.fromarray(rgb).resize((cell, cell), Image.NEAREST),
                 (gap + c * (cell + gap), gap + r * (cell + gap)))
    return im


PICK_KEYS = ["bg", "skin", "hair", "cloth", "acc", "glow"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", default="data")
    ap.add_argument("--preview", default="preview-dataset-v2.png")
    ap.add_argument("--rares", default="preview-rares-v2.png")
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    os.makedirs(a.out, exist_ok=True)
    G, P, TR, seen = [], [], [], set()
    while len(G) < a.n:
        g, p, t = make_bust(rng)
        key = (g.tobytes(), tuple(p[k] for k in PICK_KEYS))
        if key in seen:
            continue
        seen.add(key); G.append(g); P.append(p); TR.append(t)
    np.savez_compressed(os.path.join(a.out, "dataset.npz"), grids=np.array(G),
                        picks=np.array([[p[k] for k in PICK_KEYS] for p in P]))
    json.dump(TR, open(os.path.join(a.out, "traits.json"), "w"))
    idx = rng.choice(a.n, 48, replace=False)
    grid_image([to_rgb(G[i], P[i]) for i in idx]).save(a.preview)
    # rares sheet: one of each rare thing
    want = [("type", "skull"), ("type", "alien"), ("type", "hologram"), ("head", "crown"),
            ("head", "halo"), ("eyes", "laser"), ("glitch", True), ("type", "ape"),
            ("head", "thirdeye"), ("type", "dog"), ("eyes", "3d"), ("type", "android")]
    used, rare = set(), []
    for k, v in want:
        for i, t in enumerate(TR):
            if t.get(k) == v and i not in used:
                used.add(i); rare.append(i); break
    grid_image([to_rgb(G[i], P[i]) for i in rare], cols=6).save(a.rares)
    # trait stats
    stats = collections.defaultdict(collections.Counter)
    for t in TR:
        for k, v in t.items():
            stats[k][str(v)] += 1
    json.dump({k: dict(v) for k, v in stats.items()}, open(os.path.join(a.out, "trait-stats.json"), "w"), indent=1)
    print(f"{a.n} unique busts -> {a.out}/dataset.npz ; {a.preview} ; {a.rares}")


if __name__ == "__main__":
    main()
