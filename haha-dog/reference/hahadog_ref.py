"""Reference implementation of everything the Haha Dog contracts compute.

The Solidity contracts must match this file byte for byte:
  seed -> model (model/infer_int.py) -> cells + color picks
  seed -> background style + color
  cells + picks -> traits, rarity score, tier
  -> 24x24 SVG (run-length <rect>s) -> metadata JSON
"""
import base64
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "model"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

import infer_int  # noqa: E402
from backgrounds import STYLES as BG_FUNCS, tones  # noqa: E402

try:
    from Crypto.Hash import keccak as _k

    def keccak256(b):
        return _k.new(digest_bits=256, data=b).digest()
except ImportError:
    from keccak import keccak256  # noqa: F401

WEIGHTS = infer_int.load(os.path.join(HERE, "..", "model", "weights-int8.json"))
TEMPLATES = json.load(open(os.path.join(HERE, "trait-templates.json")))

INK = (0x17, 0x13, 0x1C)
WHITE = (0xFB, 0xF7, 0xEE)
PINK = (0xF0, 0x8D, 0xA0)
FUR = [(0xE3, 0x95, 0x4A), (0xC9, 0x60, 0x2D), (0x3B, 0x34, 0x43), (0xF1, 0xD9, 0xAD),
       (0xA7, 0xB0, 0xBB), (0x7F, 0xE3, 0xE0), (0xF4, 0xB9, 0x28)]
MARK = [(0xFB, 0xEC, 0xD2), (0xF8, 0xE3, 0xC6), (0xEF, 0xD7, 0xB0), (0xFF, 0xFA, 0xF0),
        (0xE1, 0xE6, 0xEC), (0xD6, 0xFB, 0xF8), (0xFF, 0xF0, 0xB3)]
CLOTH = [(0x2A, 0x27, 0x33), (0xE8, 0x42, 0x3F), (0x3F, 0x8E, 0xF0), (0xEF, 0x68, 0xA8),
         (0x8D, 0x5C, 0xF0), (0x4C, 0xC3, 0x6B), (0xF2, 0xF0, 0xE8), (0xFF, 0x9D, 0x2E)]
ACC = [(0xF2, 0xB6, 0x2B), (0xC3, 0xCA, 0xD3), (0x36, 0x31, 0x3F), (0xFF, 0x51, 0x48),
       (0x3F, 0xE0, 0xF0), (0xFF, 0x7C, 0xBA)]
GLOW = [(0xFF, 0x3B, 0x3B), (0x3F, 0xE9, 0xFF), (0x7D, 0xFF, 0x6A), (0xFF, 0x5C, 0xC8),
        (0xFF, 0xD2, 0x3F)]
BG = [(0xFF, 0x6F, 0x59), (0xFF, 0x5D, 0x8F), (0xFF, 0x9A, 0x3C), (0xFF, 0xC9, 0x3C),
      (0x9B, 0xE1, 0x5D), (0xE8, 0x4A, 0x5F), (0xB1, 0x5D, 0xE5), (0xFF, 0x8F, 0xAB)]
NIGHT_BG = [1, 5, 6]

FUR_NAMES = ["Classic Tan", "Red", "Black and Tan", "Cream", "Cyborg", "Hologram", "Gold"]
CLOTH_NAMES = ["Ink", "Red", "Blue", "Pink", "Purple", "Green", "White", "Orange"]
ACC_NAMES = ["Gold", "Silver", "Black", "Red", "Cyan", "Pink"]
GLOW_NAMES = ["Red", "Cyan", "Lime", "Magenta", "Yellow"]
BG_NAMES = ["Coral", "Rose", "Tangerine", "Sunflower", "Lime", "Crimson", "Violet", "Blush"]
STYLE_NAMES = ["Scanlines", "Sunburst", "Stars", "Moon", "Glitch", "Plain"]
STYLE_CUM = [30, 55, 75, 90, 100]
HEAD_NAMES = ["Beanie", "Cap", "Backwards Cap", "Headband", "Hood", "Headphones", "Tuft", "Spiky",
              "Mohawk", "Party Hat", "Propeller", "Crown", "Halo", "Third Eye"]
EYES_NAMES = ["Normal", "Shades", "Laser", "Visor", "Neon Specs", "Squint Smile", "Wide Stare",
              "Sleepy", "Angry", "Smug"]
MOUTH_NAMES = ["Smile", "Tongue", "Grin", "Laugh", "O Mouth", "Flat", "Bubblegum", "Bandana"]
NECK_NAMES = ["None", "Gold Chain", "Spiked Collar", "Bell Collar", "Hoodie"]
TIER_NAMES = ["Common", "Rare", "Epic", "Legendary"]
CATEGORIES = ["head", "eyes", "mouth", "neck"]
GROUP = [0, 1, 2, 2, 2, 5, 5, 7, 8, 9, 10]

# rarity points, frozen from measure_rarity.py (100k random seeds); see haha-dog/RARITY.md
POINTS = {
    "head": [7, 7, 7, 7, 7, 7, 8, 7, 7, 9, 9, 9, 9, 10],
    "eyes": [3, 5, 8, 7, 8, 11, 9, 9, 6, 8],
    "mouth": [1, 8, 20, 13, 20, 9, 15, 8],
    "neck": [1, 5, 10, 9, 7],
    "fur": [2, 6, 6, 7, 6, 8, 12],
    "style": [3, 4, 5, 5, 7],
}
TIER_MIN = [0, 30, 35, 40]
HEAD_CROWN, HEAD_HALO, FUR_GOLD = 11, 12, 6
EYES_LASER, EYES_VISOR, STYLE_GLITCH = 2, 3, 4

DESCRIPTION = ("Haha Dog is drawn on-chain by Haha AI, an on-chain AI large model: "
               "a 10,048-parameter int8 neural network that runs inside the smart contract "
               "and paints every dog from its seed. No server, no IPFS.")


def shade(c):
    return tuple(v * 3 // 4 for v in c)


def generate(seed: bytes):
    r = infer_int.infer_seed(WEIGHTS, seed)
    return r["cells"], r["picks"]


def background_of(seed: bytes):
    r = int.from_bytes(keccak256(seed), "big")
    roll = r % 100
    style = next(i for i, c in enumerate(STYLE_CUM) if roll < c)
    cr = r >> 128
    color = NIGHT_BG[cr % 3] if style in (2, 3) else cr % 8
    return style, color


def classify(cells):
    out = []
    for cat in CATEGORIES:
        t = TEMPLATES[cat]
        best, bi = -1, 0
        for i, row in enumerate(t["table"]):
            s = sum(1 for c, v in zip(t["cells"], row) if GROUP[cells[c]] == v)
            if s > best:
                best, bi = s, i
        out.append(bi)
    return out


def rarity(head, eyes, mouth, neck, fur, style):
    score = (POINTS["head"][head] + POINTS["eyes"][eyes] + POINTS["mouth"][mouth]
             + POINTS["neck"][neck] + POINTS["fur"][fur] + POINTS["style"][style])
    tier = 0
    for i, m in enumerate(TIER_MIN):
        if score >= m:
            tier = i
    if fur == FUR_GOLD and head in (HEAD_CROWN, HEAD_HALO):
        tier = 3
    elif eyes in (EYES_LASER, EYES_VISOR) and style == STYLE_GLITCH and tier < 2:
        tier = 2
    return score, tier


def traits(seed: bytes):
    cells, picks = generate(seed)
    style, color = background_of(seed)
    head, eyes, mouth, neck = classify(cells)
    score, tier = rarity(head, eyes, mouth, neck, picks[0], style)
    return dict(cells=cells, picks=picks, style=style, color=color, head=head, eyes=eyes,
                mouth=mouth, neck=neck, score=score, tier=tier)


def class_rgb(cls, picks):
    f, c, a, g = picks
    return [None, INK, FUR[f], shade(FUR[f]), MARK[f], CLOTH[c], shade(CLOTH[c]), ACC[a],
            GLOW[g], WHITE, PINK][cls]


STAR = (255, 248, 220)


def background_image(style, color):
    """24x24 rows of rgb tuples, via model/backgrounds.py (style 5 = plain)."""
    if style == 5:
        return [[BG[color]] * 24 for _ in range(24)]
    fn = BG_FUNCS[style][1]
    im = fn(tones(BG[color]), None, 6)
    return [[tuple(int(v) for v in im[y, x]) for x in range(24)] for y in range(24)]


def compose(cells, picks, style, color):
    im = background_image(style, color)
    for i in range(18):
        r = min(i, 15)
        y = 6 + i
        for c in range(16):
            cls = cells[r * 8 + (c if c < 8 else 15 - c)]
            if cls:
                im[y][4 + c] = class_rgb(cls, picks)
    return im


def to_svg(im):
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" shape-rendering="crispEdges">']
    for y in range(24):
        x = 0
        while x < 24:
            col, x1 = im[y][x], x
            while x1 < 24 and im[y][x1] == col:
                x1 += 1
            parts.append('<rect x="%d" y="%d" width="%d" height="1" fill="#%02x%02x%02x"/>' % (x, y, x1 - x, *col))
            x = x1
    return "".join(parts) + "</svg>"


BASE_SIL = [
    "........", "..OO....", ".OOOO...", ".OOOOO..", ".OOOOOOO", ".OOOOOOO", ".OOOOOOO", "OOOOOOOO",
    "OOOWWOOO", "OOOWWOOO", "OOOOOOOO", "OOOOOOOO", ".OOOOOOO", "..OOOOOO", "...OOOOO", "..OOOOOO",
]


def placeholder_cells():
    return [{".": 0, "O": 1, "W": 9}[ch] for row in BASE_SIL for ch in row]


def svg_for(t):
    return to_svg(compose(t["cells"], t["picks"], t["style"], t["color"]))


def b64(s):
    return base64.b64encode(s.encode()).decode()


def attr(k, v):
    return '{"trait_type":"%s","value":"%s"}' % (k, v)


def attr_num(k, v):
    return '{"trait_type":"%s","display_type":"number","value":%d}' % (k, v)


def token_json(token_id, seed, rerolls, state):
    """state: 0 generating (seed block not available), 1 ready."""
    name = "Haha Dog #%d" % token_id
    if state != 1:
        svg = to_svg(compose(placeholder_cells(), [0, 0, 0, 0], 0, 2))
        attrs = [attr("Status", "Generating"), attr_num("Rerolls", rerolls)]
    else:
        t = traits(seed)
        svg = svg_for(t)
        p = t["picks"]
        attrs = [attr("Rarity", TIER_NAMES[t["tier"]]), attr_num("Rarity Score", t["score"]),
                 attr("Fur", FUR_NAMES[p[0]]), attr("Headwear", HEAD_NAMES[t["head"]]),
                 attr("Eyes", EYES_NAMES[t["eyes"]]), attr("Mouth", MOUTH_NAMES[t["mouth"]]),
                 attr("Neck", NECK_NAMES[t["neck"]]), attr("Cloth", CLOTH_NAMES[p[1]]),
                 attr("Accessory", ACC_NAMES[p[2]]), attr("Glow", GLOW_NAMES[p[3]]),
                 attr("Background", STYLE_NAMES[t["style"]]), attr("Background Color", BG_NAMES[t["color"]]),
                 attr("Status", "Generated"), attr_num("Rerolls", rerolls)]
    return ('{"name":"%s","description":"%s","image":"data:image/svg+xml;base64,%s","attributes":[%s]}'
            % (name, DESCRIPTION, b64(svg), ",".join(attrs)))


def token_uri(token_id, seed, rerolls, state):
    return "data:application/json;base64," + b64(token_json(token_id, seed, rerolls, state))


def token_seed(block_hash: bytes, token_id: int, rerolls: int):
    """keccak256(abi.encode(blockhash(commitBlock + 4), tokenId, rerolls))."""
    return keccak256(block_hash + token_id.to_bytes(32, "big") + rerolls.to_bytes(32, "big"))


if __name__ == "__main__":
    s = bytes.fromhex(sys.argv[1][2:] if sys.argv[1:] and sys.argv[1].startswith("0x") else (sys.argv[1] if sys.argv[1:] else "00" * 32))
    t = traits(s)
    print({k: v for k, v in t.items() if k != "cells"})
    print(svg_for(t)[:200], "...")
