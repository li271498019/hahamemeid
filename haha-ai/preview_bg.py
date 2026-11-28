"""Preview: v4 dogs on contract-drawn backgrounds, plus a layout comparison."""
import numpy as np
from PIL import Image
from gen_data import make_dog, grid_image
from dog import mirror
from palette import BGS, rgb, class_rgb
from backgrounds import STYLES, tones, NIGHT_BGS


def compose(half, p, bg_img, oy, extend):
    """Place dog at x=4, y=oy. If oy<8 the contract repeats the dog's last
    row downward so the shoulders still touch the bottom edge."""
    g = mirror(half)
    out = bg_img.copy()
    rows = list(range(16)) + [15] * extend
    for i, r in enumerate(rows):
        y = oy + i
        if y >= 24:
            break
        for c in range(16):
            v = class_rgb(int(g[r, c]), p)
            if v:
                out[y, 4 + c] = v
    return out


def main():
    rng = np.random.default_rng(3)
    dogs = [make_dog(rng) for _ in range(40)]
    OY, EXT = 6, 2
    items = []
    for i, (name, fn, _) in enumerate(STYLES):
        g, p, t = dogs[i]
        base = rgb(BGS[NIGHT_BGS[i % 3]]) if name in ('stars', 'moon') else rgb(BGS[i % len(BGS)])
        bgimg = fn(tones(base), rng, OY)
        items.append(compose(g, p, bgimg, OY, EXT))
    grid_image(items, cols=5, scale=10).save("preview-bg-v6.png")
    return
    # layout comparison: same dog, offsets 8 (bottom), 7, 6, 5 with body extension
    g, p, t = dogs[1]
    lay = []
    for oy in (8, 7, 6, 5):
        bgimg = STYLES[4][1](tones(rgb(BGS[0])), rng, oy)
        lay.append(compose(g, p, bgimg, oy, 8 - oy))
    grid_image(lay, cols=4, scale=10).save("preview-layout-v5.png")


if __name__ == "__main__":
    main()
