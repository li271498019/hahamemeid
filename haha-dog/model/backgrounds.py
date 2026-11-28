"""Contract-side SVG backgrounds for the 24x24 canvas (NOT part of the model).

Every style is defined on the 24x24 pixel grid with integer math only, so the
Solidity version can emit run-length <rect>s (shape-rendering="crispEdges").
Tones are derived from one seed-picked base color with integer math:
  dark = c*3/4, light = (c*3 + 255)/4 (25% toward white), night = c*5/8
"""
import numpy as np

from palette import rgb

GOLD = (242, 182, 43)
GOLD_D = (181, 128, 20)
INK = (23, 19, 28)
CYAN = (255, 242, 117)   # glitch bar A (warm yellow)
MAGENTA = (255, 63, 164)  # glitch bar B
STAR = (255, 248, 220)


def tones(c):
    c = np.array(c)
    return dict(base=tuple(c), dark=tuple(c * 3 // 4), light=tuple((c * 3 + 255) // 4),
                deep=tuple(c // 2), night=tuple(c * 5 // 8))


# head centre on the canvas (dog drawn at x=4..19, y=OY..OY+15; head ~ rows 1..14)
def head_center(oy):
    return 11.5, oy + 7.5


def bg_solid(t, rng, oy):
    return np.full((24, 24, 3), t["base"], np.uint8)


def bg_gradient(t, rng, oy):   # 4 bands, light at the bottom (sunset-ish)
    im = bg_solid(t, rng, oy)
    cols = [t["deep"], t["dark"], t["base"], t["light"]]
    for i, y0 in enumerate([0, 5, 10, 16]):
        im[y0:] = cols[i]
    return im


def bg_scanlines(t, rng, oy):
    im = bg_solid(t, rng, oy)
    im[1::2] = t["dark"]
    return im


def bg_grid(t, rng, oy):       # cyber grid, lines every 4 px, floor brighter
    im = bg_solid(t, rng, oy)
    im[:, 1::4] = t["dark"]
    im[1::4, :] = t["dark"]
    return im


def bg_halo(t, rng, oy):       # concentric ring behind the head
    im = bg_solid(t, rng, oy)
    cx, cy = head_center(oy)
    yy, xx = np.mgrid[0:24, 0:24]
    d2 = (xx - cx) ** 2 + (yy - cy) ** 2
    im[(d2 >= 10 ** 2) & (d2 < 11.2 ** 2)] = t["light"]      # main ring
    im[(d2 >= 12.4 ** 2) & (d2 < 13.4 ** 2)] = t["dark"]     # faint outer ring
    return im


def bg_sunburst(t, rng, oy):   # 16 alternating rays from the head centre
    im = bg_solid(t, rng, oy)
    cx, cy = head_center(oy)
    yy, xx = np.mgrid[0:24, 0:24]
    # integer-friendly: doubled coords so centre is on a pixel corner
    dx = 2 * xx + 1 - int(2 * cx); dy = 2 * yy + 1 - int(2 * cy)
    ax, ay = np.abs(dx), np.abs(dy)
    big, small = np.maximum(ax, ay), np.minimum(ax, ay)
    sub = (small * 12 > big * 5).astype(int)          # tan(22.5) ~ 5/12
    octant = (dx < 0) * 4 + (dy < 0) * 2 + (ax < ay)
    parity = (octant + sub + (((dx < 0) ^ (dy < 0)) & 1)) % 2
    im[parity == 1] = t["light"]
    return im


def _sparkle(im, x, y, c, big=False):
    for (a, b) in [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)] + ([(2, 0), (-2, 0), (0, 2), (0, -2)] if big else []):
        if 0 <= y + b < 24 and 0 <= x + a < 24:
            im[y + b, x + a] = c


STAR_SPOTS = [(2, 2, 1), (20, 3, 1), (5, 8, 0), (19, 9, 0), (12, 1, 0), (22, 13, 0), (1, 14, 0), (8, 4, 0), (15, 5, 0), (3, 19, 0), (21, 18, 0)]


def bg_stars(t, rng, oy):
    im = bg_solid(t, rng, oy)
    im[:] = t["night"]
    for (x, y, big) in STAR_SPOTS:
        if big:
            _sparkle(im, x, y, STAR, big=False)
        else:
            im[y, x] = STAR
    return im


def bg_moon(t, rng, oy):
    im = bg_solid(t, rng, oy)
    im[:] = t["night"]
    yy, xx = np.mgrid[0:24, 0:24]
    full = (xx - 18.5) ** 2 + (yy - 4.5) ** 2 < 3.6 ** 2
    bite = (xx - 20) ** 2 + (yy - 3.5) ** 2 < 3.2 ** 2
    im[full & ~bite] = STAR
    for (x, y) in [(3, 3), (8, 1), (12, 5), (1, 9), (22, 12), (6, 11)]:
        im[y, x] = STAR
    return im


def _coin(im, x, y):
    """5x5 smiley coin (our brand): gold disc, ink eyes + smile."""
    pat = [".GGG.",
           "GiGiG",
           "GGGGG",
           "GiiiG",
           ".GGG."]
    for r, line in enumerate(pat):
        for c, ch in enumerate(line):
            if ch != "." and 0 <= y + r < 24 and 0 <= x + c < 24:
                im[y + r, x + c] = GOLD if ch == "G" else GOLD_D


COIN_SPOTS = [(1, 2), (18, 1), (10, -2), (0, 10), (20, 9)]


def bg_coins(t, rng, oy):
    im = bg_solid(t, rng, oy)
    for (x, y) in COIN_SPOTS:
        _coin(im, x, y)
    return im


def bg_glitch(t, rng, oy):
    im = bg_scanlines(t, rng, oy)
    for (y, x0, x1, c) in [(2, 0, 9, CYAN), (3, 14, 24, MAGENTA), (7, 3, 6, MAGENTA),
                           (8, 18, 24, CYAN), (12, 0, 4, CYAN), (13, 20, 24, MAGENTA)]:
        im[y, x0:x1] = c
    return im


# night styles (stars, moon) look best on these base colors (indices into BGS)
NIGHT_BGS = [1, 5, 6]

STYLES = [  # name, fn, suggested rarity %
    ("scanlines", bg_scanlines, 30),
    ("sunburst", bg_sunburst, 25),
    ("stars", bg_stars, 20),
    ("moon", bg_moon, 15),
    ("glitch", bg_glitch, 10),
]


def to_svg_rects(im):
    """Run-length encode rows into <rect>s - exactly what the contract emits."""
    out = []
    for y in range(24):
        x = 0
        while x < 24:
            c = tuple(im[y, x]); x1 = x
            while x1 < 24 and tuple(im[y, x1]) == c:
                x1 += 1
            out.append('<rect x="%d" y="%d" width="%d" height="1" fill="#%02x%02x%02x"/>' % (x, y, x1 - x, *c))
            x = x1
    return out
