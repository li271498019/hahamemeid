"""int8 quantization (one scale per layer) -> weights-int8.json (integers only).

Integer math (identical in infer_int.py and the Solidity contract):
  z_q   = int8 seed code (real value z = z_q / 32)
  layer l (ReLU):  acc = W_l . h + b_l ;  h' = 0 if acc <= 0 else min(127, (acc*M_l + 2^(SH-1)) >> SH)
  output:          y = W_out . h + b_out                (int256 accumulator, no rescale)
  cells:  constant cells come from a table; each variable cell v uses y[2v], y[2v+1]:
          class = argmax over the cell's allowed classes c of  2*(y0*P[c][0] + y1*P[c][1]) - C[c]
  picks:  argmax of y[2*n_var + ...] per group (fur 7, cloth 8, acc 6, glow 5)
Usage: python quantize.py --run out
"""
import argparse
import json

import numpy as np
import torch

from model_def import irwin_hall_z, GROUP_SIZES
from sample_float import load_decoder

SH = 24
X_SCALE = 1.0 / 32.0


def quantize(dec):
    layers = []
    s_in = X_SCALE
    for i, l in enumerate(dec.hidden_layers):
        W = l.weight.detach().double().numpy(); b = l.bias.detach().double().numpy()
        s_w = np.abs(W).max() / 127.0
        s_out = float(dec.s_h[i])
        layers.append(dict(W=np.round(W / s_w).astype(np.int64).tolist(),
                           b=np.round(b / (s_in * s_w)).astype(np.int64).tolist(),
                           M=int(round(s_in * s_w / s_out * (1 << SH)))))
        s_in = s_out
    W = dec.out.weight.detach().double().numpy(); b = dec.out.bias.detach().double().numpy()
    s_w = np.abs(W).max() / 127.0
    s_y = s_in * s_w
    P = dec.proto.detach().double().numpy()
    s_p = np.abs(P).max() / 127.0
    masks = dec.cell_masks.numpy()
    var = dec.var_cells.numpy().tolist()
    const = {int(i): int(masks[i].argmax()) for i in range(128) if masks[i].sum() == 1}
    return dict(
        SH=SH, hidden=[len(l["b"]) for l in layers], layers=layers,
        W_out=np.round(W / s_w).astype(np.int64).tolist(), b_out=np.round(b / s_y).astype(np.int64).tolist(),
        P=np.round(P / s_p).astype(np.int64).tolist(),
        C=np.round((P * P).sum(1) / (s_y * s_p)).astype(np.int64).tolist(),
        var_cells=var,
        var_masks=[int(sum(1 << c for c in range(11) if masks[i, c])) for i in var],
        const_cells=const, groups=GROUP_SIZES)


def int_forward_np(w, zq):
    h = np.asarray(zq, dtype=np.int64)
    for l in w["layers"]:
        acc = h @ np.array(l["W"]).T + np.array(l["b"])
        h = np.where(acc <= 0, 0, np.minimum(127, (acc * l["M"] + (1 << (w["SH"] - 1))) >> w["SH"]))
    y = h @ np.array(w["W_out"]).T + np.array(w["b_out"])
    P, C = np.array(w["P"]), np.array(w["C"])
    nv = len(w["var_cells"])
    yc = y[:, :2 * nv].reshape(-1, nv, 2)
    sc = 2 * (yc[..., 0:1] * P[:, 0] + yc[..., 1:2] * P[:, 1]) - C          # B, nv, 11
    mask = np.array([[(m >> c) & 1 for c in range(11)] for m in w["var_masks"]], bool)
    sc = np.where(mask[None], sc, np.iinfo(np.int64).min)
    cells = np.zeros((len(y), 128), np.int64)
    for k, v in w["const_cells"].items():
        cells[:, int(k)] = v
    cells[:, w["var_cells"]] = sc.argmax(-1)
    picks, off = [], 2 * nv
    for n in w["groups"]:
        picks.append(y[:, off:off + n].argmax(1)); off += n
    return cells, np.stack(picks, 1)


def float_forward(dec, z):
    with torch.no_grad():
        cl, pl = dec(torch.tensor(z, dtype=torch.float32))
    picks, off = [], 0
    for n in GROUP_SIZES:
        picks.append(pl[:, off:off + n].argmax(1).numpy()); off += n
    return cl.argmax(-1).numpy(), np.stack(picks, 1)


def compare(dec, w, n=5000, seed=4242):
    z = irwin_hall_z(n, torch.Generator().manual_seed(seed)).numpy()
    zq = np.round(z * 32).astype(np.int64)
    cf, pf = float_forward(dec, z)
    ci, pi = int_forward_np(w, zq)
    return dict(cell_agreement=round(float((cf == ci).mean()), 5),
                dogs_identical=round(float(((cf == ci).all(1) & (pf == pi).all(1)).mean()), 4),
                pick_agreement=round(float((pf == pi).mean()), 5),
                mean_cells_differing=round(float((cf != ci).sum(1).mean()), 3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="out")
    ap.add_argument("--out", default="weights-int8.json")
    a = ap.parse_args()
    dec = load_decoder(a.run)
    w = quantize(dec)
    dec.qat = False
    w["float_vs_int8"] = compare(dec, w)          # plain float32 model vs integer model
    dec.qat = True
    w["qat_sim_vs_int8"] = compare(dec, w)        # float simulation of int8 (what was trained last) vs integer
    json.dump(w, open(a.out, "w"))
    print("[quantize] float32 vs int8:", w["float_vs_int8"])
    print("[quantize] QAT-sim vs int8:", w["qat_sim_vs_int8"])


if __name__ == "__main__":
    main()
