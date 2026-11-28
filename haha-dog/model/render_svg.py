"""Reference SVG renderer = what the contract's tokenURI will output.

Canvas 24x24, shape-rendering="crispEdges".
 1. background style (contract only, NOT the model): scanlines / sunburst /
    stars / moon / glitch, base color from palette.BGS (night styles use NIGHT_BGS)
 2. dog: 16x16 (left half from the model, right half mirrored) at x=4, y=6;
    dog row 15 repeated at y=22 and y=23 so the shoulders touch the bottom edge.
Rows are run-length encoded into <rect>s (one per same-color run).
"""
import numpy as np

from palette import class_rgb, BGS, rgb, EMPTY
from backgrounds import STYLES, tones, NIGHT_BGS

OX, OY, EXT = 4, 6, 2
STYLE_NAMES = [s[0] for s in STYLES]


def background(style, color_idx):
    fn = dict((s[0], s[1]) for s in STYLES)[style]
    return fn(tones(rgb(BGS[color_idx])), None, OY)


def dog_pixels(half_cells, picks):
    """Returns 16x16 list of rgb or None (transparent)."""
    half = np.array(half_cells).reshape(16, 8)
    g = np.concatenate([half, half[:, ::-1]], 1)
    p = dict(fur=picks[0], cloth=picks[1], acc=picks[2], glow=picks[3])
    return [[class_rgb(int(g[r, c]), p) for c in range(16)] for r in range(16)]


def compose_rgb(half_cells, picks, style="scanlines", color_idx=0):
    im = background(style, color_idx).copy()
    px = dog_pixels(half_cells, picks)
    rows = list(range(16)) + [15] * EXT
    for i, r in enumerate(rows):
        y = OY + i
        if y >= 24:
            break
        for c in range(16):
            if px[r][c] is not None:
                im[y, OX + c] = px[r][c]
    return im


def to_svg(im):
    rects = []
    for y in range(24):
        x = 0
        while x < 24:
            col = tuple(int(v) for v in im[y, x]); x1 = x
            while x1 < 24 and tuple(int(v) for v in im[y, x1]) == col:
                x1 += 1
            rects.append('<rect x="%d" y="%d" width="%d" height="1" fill="#%02x%02x%02x"/>' % (x, y, x1 - x, *col))
            x = x1
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" shape-rendering="crispEdges">'
            + "".join(rects) + "</svg>")


def render_svg(half_cells, picks, style="scanlines", color_idx=0):
    return to_svg(compose_rgb(half_cells, picks, style, color_idx))
