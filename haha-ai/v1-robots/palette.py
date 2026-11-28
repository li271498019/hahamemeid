"""Fixed global 16-color palette (hard-coded in the contract too) and cell classes.

Each of the 16x16 cells holds one of 6 *classes*; the actual color is
looked up from the class plus two per-image choices (body hue, accent color).
"""
# ---- cell classes (ordinal order matters for the model, see README) ----
BG, OUTLINE, SHADE, BODY, ACCENT, WHITE = range(6)
N_CLASSES = 6

PALETTE = [
    "#0b0b10",  # 0  background (near black, matches haha.meme)
    "#2e2a45",  # 1  outline / pupils / mouth
    "#f7f3e8",  # 2  white (eyes, teeth)
    "#ff7eb6", "#c4508a",  # 3,4   pink   main, shade
    "#ffa24c", "#cc6b26",  # 5,6   orange
    "#ffd84a", "#c79b1f",  # 7,8   yellow
    "#5fe3a1", "#2aa56c",  # 9,10  mint
    "#5cc8ff", "#2b86c7",  # 11,12 sky
    "#b98cff", "#7d52cc",  # 13,14 purple
    "#ff4d5e",             # 15 red (accent only)
]
HUE_NAMES = ["pink", "orange", "yellow", "mint", "sky", "purple"]
N_BODY_HUES = 6
N_ACCENTS = 7  # 0..5 = main color of a hue, 6 = red


def class_to_index(cls, body_hue, accent):
    if cls == BG:
        return 0
    if cls == OUTLINE:
        return 1
    if cls == WHITE:
        return 2
    if cls == BODY:
        return 3 + 2 * body_hue
    if cls == SHADE:
        return 4 + 2 * body_hue
    # ACCENT
    return 15 if accent == 6 else 3 + 2 * accent


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


PALETTE_RGB = [hex_to_rgb(h) for h in PALETTE]
