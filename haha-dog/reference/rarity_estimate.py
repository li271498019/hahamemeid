"""Haha Dog rarity reference: seed (bytes32) -> traits + rarity tier.

Self-contained (only needs weights-int8.json, trait-templates.json and keccak.py
next to this file; pycryptodome is used for keccak if installed).
This is the exact spec the Haha Dog contracts implement on-chain
(haha-dog/reference/hahadog_ref.py on branch haha-dog).

  python rarity.py 0x<64 hex>        -> prints traits for one seed
  from rarity import traits; traits(bytes.fromhex("..."))
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    from Crypto.Hash import keccak as _k

    def keccak256(b):
        return _k.new(digest_bits=256, data=b).digest()
except ImportError:
    from keccak import keccak256  # noqa: F401

WEIGHTS = json.load(open(os.path.join(HERE, "weights-int8.json")))
TEMPLATES = json.load(open(os.path.join(HERE, "trait-templates.json")))
NIGHT_BG = [1, 5, 6]
STYLE_NAMES = ["Scanlines", "Sunburst", "Stars", "Moon", "Glitch", "Plain"]
STYLE_CUM = [30, 55, 75, 90, 100]
HEAD_NAMES = ["Beanie", "Cap", "Backwards Cap", "Headband", "Hood", "Headphones", "Tuft", "Spiky",
              "Mohawk", "Party Hat", "Propeller", "Crown", "Halo", "Third Eye"]
EYES_NAMES = ["Normal", "Shades", "Laser", "Visor", "Neon Specs", "Squint Smile", "Wide Stare",
              "Sleepy", "Angry", "Smug"]
MOUTH_NAMES = ["Smile", "Tongue", "Grin", "Laugh", "O Mouth", "Flat", "Bubblegum", "Bandana"]
NECK_NAMES = ["None", "Gold Chain", "Spiked Collar", "Bell Collar", "Hoodie"]
TIER_NAMES = ["Common", "Rare", "Epic", "Legendary"]
TIER_NAMES_ZH = ["普通", "稀有", "史诗", "传说"]
CATEGORIES = ["head", "eyes", "mouth", "neck"]
GROUP = [0, 1, 2, 2, 2, 5, 5, 7, 8, 9, 10]
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



def seed_to_z(seed: bytes):
    assert len(seed) == 32
    return [((seed[4 * i] + seed[4 * i + 1] + seed[4 * i + 2] + seed[4 * i + 3] - 510) * 7) >> 5 for i in range(8)]


def forward(w, z):
    SH = w["SH"]; half = 1 << (SH - 1)
    h = list(z)
    hidden_trace = []
    for l in w["layers"]:
        nh = []
        for j in range(len(l["W"])):
            acc = l["b"][j]
            row = l["W"][j]
            for i in range(len(h)):
                acc += row[i] * h[i]
            nh.append(0 if acc <= 0 else min(127, (acc * l["M"] + half) >> SH))
        h = nh
        hidden_trace.append(h)
    y = []
    for k in range(len(w["W_out"])):
        acc = w["b_out"][k]
        row = w["W_out"][k]
        for j in range(len(h)):
            acc += row[j] * h[j]
        y.append(acc)
    cells = [0] * 128
    for k, v in w["const_cells"].items():
        cells[int(k)] = v
    P, C = w["P"], w["C"]
    for v, ci in enumerate(w["var_cells"]):
        ya, yb, m = y[2 * v], y[2 * v + 1], w["var_masks"][v]
        best, bc = None, 0
        for c in range(11):
            if (m >> c) & 1:
                sc = 2 * (ya * P[c][0] + yb * P[c][1]) - C[c]
                if best is None or sc > best:
                    best, bc = sc, c
        cells[ci] = bc
    picks, off = [], 2 * len(w["var_cells"])
    for n in w["groups"]:
        best, bi = None, 0
        for k in range(n):
            if best is None or y[off + k] > best:
                best, bi = y[off + k], k
        picks.append(bi); off += n
    return dict(z=list(z), hidden=hidden_trace, cells=cells, picks=picks)


def infer_seed(w, seed: bytes):
    return forward(w, seed_to_z(seed))



def generate(seed):
    r = forward(WEIGHTS, seed_to_z(seed))
    return r["cells"], r["picks"]


def background_of(seed):
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


def traits(seed):
    assert len(seed) == 32
    cells, picks = generate(seed)
    style, color = background_of(seed)
    head, eyes, mouth, neck = classify(cells)
    score, tier = rarity(head, eyes, mouth, neck, picks[0], style)
    return dict(
        tier=TIER_NAMES[tier], tier_zh=TIER_NAMES_ZH[tier], score=score,
        fur=FUR_NAMES[picks[0]], headwear=HEAD_NAMES[head], eyes=EYES_NAMES[eyes],
        mouth=MOUTH_NAMES[mouth], neck=NECK_NAMES[neck], cloth=CLOTH_NAMES[picks[1]],
        accessory=ACC_NAMES[picks[2]], glow=GLOW_NAMES[picks[3]],
        background=STYLE_NAMES[style], background_color=BG_NAMES[color],
        raw=dict(cells=cells, picks=picks, style=style, color=color, head=head, eyes=eyes,
                 mouth=mouth, neck=neck, tier=tier),
    )


if __name__ == "__main__":
    a = sys.argv[1] if len(sys.argv) > 1 else "0x" + "00" * 32
    t = traits(bytes.fromhex(a[2:] if a.startswith("0x") else a))
    t.pop("raw")
    print(json.dumps(t, ensure_ascii=False, indent=1))
