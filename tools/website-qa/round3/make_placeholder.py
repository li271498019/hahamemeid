"""Builds site/assets/dog/unrendered.gif (+ static poster png) from the raw frames. Consecutive identical frames are
merged into one frame with a longer delay (the 10-frame holds become 900 ms). 4x nearest-neighbour upscale (96x96)."""
import sys, glob
from PIL import Image
src, outdir = sys.argv[1], sys.argv[2]
files = sorted(glob.glob(src + "/f*.rgb"))
S = 4
imgs, durs, prev = [], [], None
for f in files:
    raw = open(f, "rb").read()
    if raw == prev:
        durs[-1] += 90
        continue
    prev = raw
    im = Image.frombytes("RGB", (24, 24), raw).resize((24 * S, 24 * S), Image.NEAREST)
    imgs.append(im); durs.append(90)
print(len(files), "->", len(imgs), "frames")
imgs[0].save(outdir + "/unrendered.gif", save_all=True, append_images=imgs[1:], duration=durs, loop=0, optimize=True)
imgs[0].save(outdir + "/unrendered-static.png", optimize=True)
