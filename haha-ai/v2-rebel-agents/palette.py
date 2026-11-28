"""Fixed global palette (v2 'rebel agents') + cell classes.

The model outputs, for each of the 256 cells, one CLASS (what kind of pixel it
is) and, per image, a few COLOR PICKS (which skin / hair / cloth / accessory /
glow / background color). The contract maps class + picks -> palette color.
Shade colors are NOT stored: contract computes shade = color * 3 / 4 per channel.
"""
# ---- cell classes ----
BG, OUT, SKIN, SKIN_SH, HAIR, CLOTH, CLOTH_SH, ACC, GLOW, WHITE = range(10)
N_CLASSES = 10
CLASS_NAMES = ["bg", "outline", "skin", "skin_shade", "hair", "cloth",
               "cloth_shade", "accessory", "glow", "white"]

PALETTE = [
    "#141218",  # 0  outline / ink
    "#f1ede2",  # 1  white (eye whites, smoke, teeth)
    # backgrounds (muted, punk-ish)
    "#638596",  # 2  punk blue
    "#8a7ba6",  # 3  dusty purple
    "#6b978a",  # 4  muted teal
    "#b3878b",  # 5  dusty rose
    "#4a5068",  # 6  night slate
    # skins
    "#eac39d",  # 7  human light
    "#b57e55",  # 8  human medium
    "#6f4a33",  # 9  human dark
    "#a9b1ba",  # 10 metal (android)
    "#8fe6e2",  # 11 hologram cyan (AI ghost)
    "#9aa3ea",  # 12 alien periwinkle
    "#d9a25a",  # 13 tan fur (dog) / ape face
    "#e7e0c9",  # 14 bone (skull-bot)
    "#97ab8c",  # 15 zombie grey-green
    # hair / cloth / accessory colors
    "#2c2834",  # 16 black
    "#e5c65a",  # 17 blonde / gold-ish
    "#b9502e",  # 18 ginger / rust
    "#7a5637",  # 19 brown
    "#e8423f",  # 20 red (laser)
    "#f2b62b",  # 21 gold
    "#3fe0f0",  # 22 neon cyan
    "#ef68a8",  # 23 hot pink
    "#8d5cf0",  # 24 neon purple
    "#58c46a",  # 25 acid green (cloth/glow only, never skin)
]
BG_CHOICES = [2, 3, 4, 5, 6]
SKIN_CHOICES = [7, 8, 9, 10, 11, 12, 13, 14, 15]
HAIR_CHOICES = [16, 17, 18, 19, 1, 23, 22, 24]
CLOTH_CHOICES = [16, 20, 22, 23, 24, 25, 19, 6, 1]
ACC_CHOICES = [21, 10, 16, 20, 22, 23, 1]
GLOW_CHOICES = [20, 22, 25, 23, 21]


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


PALETTE_RGB = [hex_to_rgb(h) for h in PALETTE]


def shade(rgb):
    return tuple(c * 3 // 4 for c in rgb)


def class_rgb(cls, picks):
    """picks: dict with palette indices for bg, skin, hair, cloth, acc, glow."""
    P = PALETTE_RGB
    if cls == BG:
        return P[picks["bg"]]
    if cls == OUT:
        return P[0]
    if cls == WHITE:
        return P[1]
    if cls == SKIN:
        return P[picks["skin"]]
    if cls == SKIN_SH:
        return shade(P[picks["skin"]])
    if cls == HAIR:
        return P[picks["hair"]]
    if cls == CLOTH:
        return P[picks["cloth"]]
    if cls == CLOTH_SH:
        return shade(P[picks["cloth"]])
    if cls == ACC:
        return P[picks["acc"]]
    if cls == GLOW:
        return P[picks["glow"]]
    raise ValueError(cls)
