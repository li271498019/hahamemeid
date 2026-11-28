"""v3 'haha dog' palette + cell classes. Background is NOT part of the model:
class EMPTY = transparent; the contract draws the background rect itself.
Shades are computed in the contract: shade = rgb * 3 // 4.
"""
EMPTY, OUT, FUR, FUR_SH, MARK, CLOTH, CLOTH_SH, ACC, GLOW, WHITE, PINK = range(11)
N_CLASSES = 11
CLASS_NAMES = ["empty", "outline", "fur", "fur_shade", "mark", "cloth",
               "cloth_shade", "accessory", "glow", "white", "pink"]

INK = "#17131c"
WHITE_HEX = "#fbf7ee"
PINK_HEX = "#f08da0"
# fur variants: (name, fur, mark/cream, weight %)
FURS = [
    ("classic tan", "#e3954a", "#fbecd2", 40),
    ("red",         "#c9602d", "#f8e3c6", 16),
    ("black & tan", "#3b3443", "#efd7b0", 14),
    ("cream",       "#f1d9ad", "#fffaf0", 12),
    ("cyborg",      "#a7b0bb", "#e1e6ec", 8),
    ("hologram",    "#7fe3e0", "#d6fbf8", 6),
    ("gold",        "#f4b928", "#fff0b3", 4),
]
CLOTHS = ["#2a2733", "#e8423f", "#3f8ef0", "#ef68a8", "#8d5cf0", "#4cc36b", "#f2f0e8", "#ff9d2e"]
ACCS = ["#f2b62b", "#c3cad3", "#36313f", "#ff5148", "#3fe0f0", "#ff7cba"]
GLOWS = ["#ff3b3b", "#3fe9ff", "#7dff6a", "#ff5cc8", "#ffd23f"]
# background colors (contract only, warm & vivid)
BGS = ["#ff6f59", "#ff5d8f", "#ff9a3c", "#ffc93c", "#9be15d", "#e84a5f", "#b15de5", "#ff8fab"]


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def shade(c):
    return tuple(v * 3 // 4 for v in c)


def class_rgb(cls, p):
    """p: dict fur, cloth, acc, glow (indices). Returns rgb or None (transparent)."""
    if cls == EMPTY:
        return None
    if cls == OUT:
        return rgb(INK)
    if cls == WHITE:
        return rgb(WHITE_HEX)
    if cls == PINK:
        return rgb(PINK_HEX)
    if cls == FUR:
        return rgb(FURS[p["fur"]][1])
    if cls == FUR_SH:
        return shade(rgb(FURS[p["fur"]][1]))
    if cls == MARK:
        return rgb(FURS[p["fur"]][2])
    if cls == CLOTH:
        return rgb(CLOTHS[p["cloth"]])
    if cls == CLOTH_SH:
        return shade(rgb(CLOTHS[p["cloth"]]))
    if cls == ACC:
        return rgb(ACCS[p["acc"]])
    if cls == GLOW:
        return rgb(GLOWS[p["glow"]])
    raise ValueError(cls)


def color_table():
    """Every color a dog pixel can have -> (class, group, option).
    Used by slice_sheets.py; all entries are unique by construction."""
    t = {rgb(INK): (OUT, None, None), rgb(WHITE_HEX): (WHITE, None, None),
         rgb(PINK_HEX): (PINK, None, None)}
    for i, f in enumerate(FURS):
        t[rgb(f[1])] = (FUR, "fur", i)
        t[shade(rgb(f[1]))] = (FUR_SH, "fur", i)
        t[rgb(f[2])] = (MARK, "fur", i)
    for i, c in enumerate(CLOTHS):
        t[rgb(c)] = (CLOTH, "cloth", i)
        t[shade(rgb(c))] = (CLOTH_SH, "cloth", i)
    for i, c in enumerate(ACCS):
        t[rgb(c)] = (ACC, "acc", i)
    for i, c in enumerate(GLOWS):
        t[rgb(c)] = (GLOW, "glow", i)
    n = 3 + 3 * len(FURS) + 2 * len(CLOTHS) + len(ACCS) + len(GLOWS)
    assert len(t) == n, "palette colors must be unique"
    return t
