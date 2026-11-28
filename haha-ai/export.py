"""Export everything the contract developer needs + the human-facing previews.

Writes: model-config.json, test-vectors.json, test-vectors/*.png + *.svg,
        samples.png (random seeds on the warm contract backgrounds),
        training-report.md
All dog pictures here come from the INTEGER path (infer_int.py), i.e. exactly
what the contract will draw.
Usage: python export.py --run out
"""
import argparse
import json
import os

import numpy as np
from PIL import Image

import infer_int
from palette import (PINK_HEX, INK, WHITE_HEX, FURS, CLOTHS, ACCS, GLOWS, BGS, CLASS_NAMES)
from backgrounds import STYLES, NIGHT_BGS
from render_svg import compose_rgb, to_svg, OX, OY, EXT
from gen_data import grid_image


def seeds(n, salt):
    rng = np.random.default_rng(salt)
    return [bytes(rng.integers(0, 256, 32, dtype=np.uint8)) for _ in range(n)]


def bg_for(seed):
    """Preview-only background choice (the contract will use keccak256(seed) bytes)."""
    style = STYLES[seed[31] % len(STYLES)][0]
    col = NIGHT_BGS[seed[30] % len(NIGHT_BGS)] if style in ("stars", "moon") else seed[30] % len(BGS)
    return style, col


def weight_bytes(w):
    def bits(v):
        m = max(abs(int(x)) for x in v) if len(v) else 0
        return max(8, int(np.ceil(np.log2(m + 1))) + 1)
    rep = {}
    n_w = sum(len(l["W"]) * len(l["W"][0]) for l in w["layers"]) + len(w["W_out"]) * len(w["W_out"][0])
    rep["weights_int8_bytes"] = n_w
    b_all = [x for l in w["layers"] for x in l["b"]] + w["b_out"]
    bb = bits(b_all)
    rep["bias_bits"] = bb
    rep["bias_bytes"] = len(b_all) * int(np.ceil(bb / 8))
    rep["prototype_bytes"] = 22 + 11 * int(np.ceil(bits(w["C"]) / 8))
    rep["cell_tables_bytes"] = len(w["var_cells"]) * 3 + len(w["const_cells"]) * 2
    rep["total_model_data_bytes"] = sum(v for k, v in rep.items() if k.endswith("_bytes"))
    rep["params"] = n_w + len(b_all)
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", default="weights-int8.json")
    ap.add_argument("--run", default="out")
    a = ap.parse_args()
    w = infer_int.load(a.weights)
    os.makedirs("test-vectors", exist_ok=True)

    # ---- test vectors (integer path, with hidden activations for debugging)
    tv = []
    special = [bytes(32), bytes([255] * 32), bytes(range(32)), bytes([128] * 32)]
    for i, s in enumerate(special + seeds(12, 2026)):
        r = infer_int.infer_seed(w, s)
        style, col = bg_for(s)
        im = compose_rgb(r["cells"], r["picks"], style, col)
        Image.fromarray(im).resize((240, 240), Image.NEAREST).save(f"test-vectors/tv_{i:02d}.png")
        svg = to_svg(im)
        open(f"test-vectors/tv_{i:02d}.svg", "w").write(svg)
        tv.append(dict(id=i, seed="0x" + s.hex(), z_q=r["z"], hidden=r["hidden"], picks=r["picks"],
                       cells_half_16x8="".join("0123456789A"[c] for c in r["cells"]),
                       background=dict(style=style, color_index=col), svg_bytes=len(svg)))
    json.dump(dict(note="cells_half_16x8: 128 chars, row-major, left half; class letters 0-9,A = "
                        + ", ".join(f"{i}:{n}" for i, n in enumerate(CLASS_NAMES)), vectors=tv),
              open("test-vectors.json", "w"), indent=1)

    # ---- samples.png : 32 random seeds (integer path) on warm backgrounds
    items = []
    for s in seeds(32, 77):
        r = infer_int.infer_seed(w, s)
        style, col = bg_for(s)
        items.append(compose_rgb(r["cells"], r["picks"], style, col))
    grid_image(items, cols=8, scale=10).save("samples.png")

    # ---- model-config.json
    sizes = weight_bytes(w)
    cfg = dict(
        architecture=dict(input="8 x int8 seed code", hidden=w["hidden"], activation="ReLU",
                          output=f"{2 * len(w['var_cells'])} cell coords + 26 color logits",
                          cells="16x8 left half, mirrored to 16x16"),
        seed_to_z="for i in 0..7: s = b[4i]+b[4i+1]+b[4i+2]+b[4i+3] - 510 ; z_q = (s*7) >> 5  (b = seed bytes, big-endian)",
        integer_math="see infer_int.py / quantize.py header",
        classes=CLASS_NAMES,
        palette=dict(outline=INK, white=WHITE_HEX, pink=PINK_HEX,
                     fur=[dict(name=f[0], fur=f[1], mark=f[2]) for f in FURS],
                     cloth=CLOTHS, acc=ACCS, glow=GLOWS, shade_rule="shade = rgb*3//4 per channel"),
        layout=dict(canvas=24, dog_x=OX, dog_y=OY, repeat_last_row=EXT,
                    svg='<svg viewBox="0 0 24 24" shape-rendering="crispEdges">, bg rects then dog rects'),
        backgrounds=dict(styles=[dict(name=s[0], suggested_rarity_pct=s[2]) for s in STYLES],
                         colors=BGS, night_colors_idx=NIGHT_BGS,
                         note="contract-only; see backgrounds.py"),
        sizes=sizes, float_vs_int8=w.get("float_vs_int8"), qat_sim_vs_int8=w.get("qat_sim_vs_int8"))
    json.dump(cfg, open("model-config.json", "w"), indent=1)

    # ---- training report
    log = json.load(open(os.path.join(a.run, "train_log.json")))
    lines = ["# 训练报告 / Training report", "",
             f"- 结构 Architecture: 8 -> {' -> '.join(map(str, w['hidden']))} -> {len(w['W_out'])} (ReLU, int8)",
             f"- 参数量 Params: {sizes['params']}",
             f"- 模型数据大小 Model data: ~{sizes['total_model_data_bytes']} bytes "
             f"(int8 weights {sizes['weights_int8_bytes']} B, biases {sizes['bias_bytes']} B @ {sizes['bias_bits']} bit)",
             f"- 浮点 float32 vs int8 (5000 random seeds): {w.get('float_vs_int8')}",
             f"- QAT 模拟 vs int8 (5000 random seeds): {w.get('qat_sim_vs_int8')}",
             "- 说明：最后 30% 训练轮次是在 int8 模拟（QAT）下进行的，所以真正上链的是整数模型；float32 那一行只是参考。", "",
             "## Training log", "```"] + [json.dumps(r) for r in log["log"]] + ["```"]
    if os.path.exists(os.path.join(a.run, "quality.json")):
        lines += ["", "## Sample quality", "```", open(os.path.join(a.run, "quality.json")).read(), "```"]
    open("training-report.md", "w", encoding="utf-8").write("\n".join(lines))
    print("[export] model-config.json, test-vectors.json (+pngs/svgs), samples.png, training-report.md")
    print("[export] sizes:", sizes)


if __name__ == "__main__":
    main()
