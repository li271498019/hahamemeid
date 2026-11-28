"""Hand-drawn 16x16 base busts (3/4 view, facing right). Original designs.

Legend: . bg  O outline  S skin  s skin-shade  H hair/fur  C cloth  c cloth-shade
        A accessory  G glow  W white
Each template also carries anchors used by trait drawing code.
"""
from palette import BG, OUT, SKIN, SKIN_SH, HAIR, CLOTH, CLOTH_SH, ACC, GLOW, WHITE

CH = {".": BG, "O": OUT, "S": SKIN, "s": SKIN_SH, "H": HAIR, "C": CLOTH,
      "c": CLOTH_SH, "A": ACC, "G": GLOW, "W": WHITE}

T = {}

# human / zombie / android / ghost share this head
T["human"] = dict(rows=[
    "................",
    "................",
    "................",
    "....OOOOOOO.....",
    "...OSSSSSSSO....",
    "...OSSSSSSSSO...",
    "...OSSSSSSSSO...",
    "...OSSSSSSSSO...",
    "..OOSSSWOSWOSO..",
    "..OSsSSSSSSSSO..",
    "...OsSSSSSSSSSO.",
    "...OSSSSSSSSSO..",
    "....OsSSSSOOSO..",
    ".....OsSSSSSO...",
    ".....OsSOOOO....",
    "....OsSSSO......",
], top=3, eye_row=8, eyes=(8, 11), mouth_row=12, mouth_end=11, ear=(9, 2),
    chain=(15, 5, 8), face_right=13, face_left=5)

T["ape"] = dict(rows=[
    "................",
    "................",
    "................",
    "....OOOOOOO.....",
    "...OHHHHHHHO....",
    "..OHHHHHHHHHO...",
    "..OHHHOOOOOOO...",
    "..OHHSSSSSSSSO..",
    ".OOHSSWOSSWOSO..",
    "OSOHSSSSSSSSSO..",
    "OsOHSSSSSSSSSSO.",
    ".OHHSSSSSOOSSSO.",
    "..OHHSSSSSSSSSO.",
    "...OHHSOOOOSSO..",
    "....OHHSSSSOO...",
    "....OHHHHHO.....",
], top=3, eye_row=8, eyes=(7, 11), mouth_row=11, mouth_end=10, ear=(9, 0),
    chain=(15, 6, 9), face_right=14, face_left=5)

T["dog"] = dict(rows=[
    "................",
    "................",
    "...OO....OO.....",
    "...OsO..OsSO....",
    "...OssOOOsSO....",
    "..OSSSSSSSSSO...",
    "..OSSSSSSSSSO...",
    "..OSSSSSSSSSO...",
    "..OSSSWOSSWOSO..",
    "..OSSSSSSSWWWOO.",
    "..OSSSSSWWWWWOOO",
    "..OsSSSSWWWWOOO.",
    "...OsSSSWWWWWO..",
    "....OsSSSWWWO...",
    ".....OsSSOOO....",
    ".....OsSSSO.....",
], top=4, eye_row=8, eyes=(7, 11), mouth_row=None, mouth_end=None, ear=None,
    chain=(15, 6, 9), face_right=15, face_left=4)

T["skull"] = dict(rows=[
    "................",
    "................",
    "................",
    "....OOOOOOO.....",
    "...OSSSSSSSO....",
    "..OSSSSSSSSSO...",
    "..OSSSSSSSSSO...",
    "..OSSSSSSSSSO...",
    "..OSSSOOSSOOSO..",
    "..OSSSOGSSOGSO..",
    "..OsSSSSSSSSSO..",
    "...OsSSSSOSSSO..",
    "....OSSSSSSSO...",
    "....OsOWOWOWO...",
    ".....OOsOsOsO...",
    ".....OsSO.OO....",
], top=3, eye_row=9, eyes=(7, 11), mouth_row=12, mouth_end=11, ear=None,
    chain=(15, 6, 8), face_right=13, face_left=4)

T["alien"] = dict(rows=[
    "................",
    "....OOOOOOO.....",
    "...OSSSSSSSO....",
    "..OSSSSSSSSSO...",
    "..OSSSSSSSSSO...",
    "..OSSSSSSSSSO...",
    "..OSSSSSSSSSO...",
    "..OsSSSOOSSOOO..",
    "..OsSSOOWSOOWO..",
    "..OsSSOOOSOOOO..",
    "...OsSSSSSSSSO..",
    "....OsSSSSSSO...",
    ".....OsSSOOSO...",
    "......OsSSSO....",
    "......OsSOO.....",
    ".....OssSO......",
], top=1, eye_row=8, eyes=(8, 12), mouth_row=12, mouth_end=10, ear=None,
    chain=(15, 6, 8), face_right=13, face_left=4)


def grid(name):
    import numpy as np
    rows = T[name]["rows"]
    assert len(rows) == 16 and all(len(r) == 16 for r in rows), name
    return np.array([[CH[ch] for ch in r] for r in rows], np.uint8)
