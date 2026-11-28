"""Base front-facing shiba ('haha dog') template, LEFT HALF only (cols 0..7).
Columns 8..15 are the mirror image, so the model only generates 16x8 = 128 cells.
Legend: . empty O outline F fur f fur-shade M mark(cream) W white P pink
        C cloth c cloth-shade A accessory G glow
"""
import numpy as np
from palette import EMPTY, OUT, FUR, FUR_SH, MARK, CLOTH, CLOTH_SH, ACC, GLOW, WHITE, PINK

CH = {".": EMPTY, "O": OUT, "F": FUR, "f": FUR_SH, "M": MARK, "C": CLOTH,
      "c": CLOTH_SH, "A": ACC, "G": GLOW, "W": WHITE, "P": PINK}

BASE = [
    "........",  # 0
    "..OO....",  # 1  ear tip
    ".OFPO...",  # 2
    ".OFPPO..",  # 3
    ".OFFFFOO",  # 4  head top
    ".OFFFFFf",  # 5  forehead
    ".OFFMMFF",  # 6  cream eyebrow spots
    "OFFFFFFF",  # 7
    "OFFOOFFF",  # 8  eye
    "OFFOWFFM",  # 9  eye + glint, muzzle bridge
    "OMMFFFMM",  # 10 cream cheeks
    "OMMMMMMO",  # 11 nose
    ".OMMMOMO",  # 12 nose + mouth
    "..OMMMOM",  # 13 mouth
    "...OOOOO",  # 14 chin
    "..OFFMMM",  # 15 shoulders + cream chest
]
EYE = (8, 3)  # top-left cell of the 2x2 eye (left half coords)


def to_half(rows):
    return np.array([[CH[ch] for ch in r] for r in rows], np.uint8)


def mirror(half):
    return np.concatenate([half, half[:, ::-1]], axis=1)
