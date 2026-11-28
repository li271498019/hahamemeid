"""Train the tiny on-chain decoder on the sliced sheets.

Phase 1 (VAE): an encoder (training only) maps each dog to a latent code;
                the decoder learns to redraw it. This organises the 8-D seed space.
Phase 2 (OT):  each round draws 1000 fresh seeds exactly like the contract does,
               matches them one-to-one to the 1000 dogs (Hungarian algorithm on
               likelihood) and trains on those pairs -> any seed lands on a clean,
               complete dog instead of a blend. The last 30% of rounds are
               quantization-aware (int8 weights + int8 activations).
Usage: python train.py --hidden 64,32 --vae_epochs 1500 --ot_rounds 200
"""
import argparse
import json
import os
import time

import numpy as np
import torch
import torch.nn.functional as F
from scipy.optimize import linear_sum_assignment

from model_def import (Decoder, Encoder, encode_input, pick_loss, irwin_hall_z,
                       N_CELLS, N_CLASSES, GROUP_SIZES)


def loglik_matrix(dec, z, cells, picks):
    """ll[m, n] = log p(dog n | seed z_m) for all pairs (one matmul)."""
    cl, pl = dec(z)
    lsm = F.log_softmax(cl, -1).reshape(len(z), -1)
    oh = F.one_hot(cells, N_CLASSES).float().reshape(len(cells), -1)
    ll = lsm @ oh.T
    off = 0
    for g, n in enumerate(GROUP_SIZES):
        lp = F.log_softmax(pl[:, off:off + n], -1); off += n
        t = picks[:, g]
        ohp = F.one_hot(t.clamp(min=0), n).float() * (t >= 0).float()[:, None]
        ll = ll + 4 * (lp @ ohp.T)
    return ll


def recon(dec, z, cells, picks):
    cl, pl = dec(z)
    r = F.cross_entropy(cl.reshape(-1, N_CLASSES), cells.reshape(-1), reduction="sum") / len(z)
    return r + 4 * pick_loss(pl, picks), cl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="out")
    ap.add_argument("--hidden", default="64,32", help="hidden layer sizes, e.g. 48 or 64,32")
    ap.add_argument("--vae_epochs", type=int, default=1500)
    ap.add_argument("--ot_rounds", type=int, default=200)
    ap.add_argument("--ot_epochs", type=int, default=10)
    ap.add_argument("--beta", type=float, default=1.0)
    ap.add_argument("--vae_weight", type=float, default=0.3)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    torch.manual_seed(a.seed)
    os.makedirs(a.out, exist_ok=True)
    d = np.load(os.path.join(a.data, "dataset.npz"))
    cells = torch.tensor(d["halves"].reshape(len(d["halves"]), -1), dtype=torch.long)
    picks = torch.tensor(d["picks"], dtype=torch.long)
    masks = torch.zeros(N_CELLS, N_CLASSES, dtype=torch.bool)
    masks[torch.arange(N_CELLS).repeat(len(cells)), cells.reshape(-1)] = True
    np.save(os.path.join(a.out, "cell_masks.npy"), masks.numpy())
    hidden = [int(v) for v in str(a.hidden).split(",")]
    dec, enc = Decoder(hidden, masks), Encoder()
    print(f"[train] decoder params: {dec.n_params()}  (variable cells: {dec.n_var}/128)", flush=True)
    x = encode_input(cells, picks)
    n, bs = len(cells), 250
    log, t0 = [], time.time()

    # ---------------- phase 1: VAE
    opt = torch.optim.Adam(list(enc.parameters()) + list(dec.parameters()), lr=3e-3)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, a.vae_epochs)
    for ep in range(a.vae_epochs):
        beta = a.beta * min(1.0, ep / (a.vae_epochs * 0.3))
        perm = torch.randperm(n)
        for i in range(0, n, bs):
            idx = perm[i:i + bs]
            mu, lv = enc(x[idx])
            z = mu + torch.randn_like(mu) * torch.exp(0.5 * lv)
            rec, _ = recon(dec, z, cells[idx], picks[idx])
            kl = (-0.5 * (1 + lv - mu ** 2 - lv.exp()).sum(1)).mean()
            loss = rec + beta * kl
            opt.zero_grad(); loss.backward(); opt.step()
        sched.step()
        if ep % 500 == 0 or ep == a.vae_epochs - 1:
            row = dict(phase="vae", epoch=ep, rec=round(rec.item(), 2), kl=round(kl.item(), 2), sec=round(time.time() - t0))
            log.append(row); print("[train]", row, flush=True)

    # ---------------- phase 2: optimal-transport matching on the contract's seed distribution
    opt = torch.optim.Adam(list(enc.parameters()) + list(dec.parameters()), lr=1e-3)
    qat_round = int(a.ot_rounds * 0.7)
    for rnd in range(a.ot_rounds):
        if rnd == qat_round:
            dec.qat = True
            for g in opt.param_groups:
                g["lr"] = 3e-4
        if dec.qat:
            dec.calibrate()
        z = irwin_hall_z(n)
        with torch.no_grad():
            ll = loglik_matrix(dec, z, cells, picks)
        r, c = linear_sum_assignment((-ll).numpy())
        zt, tc, tp = z[r], cells[c], picks[c]
        for _ in range(a.ot_epochs):
            perm = torch.randperm(n)
            for i in range(0, n, bs):
                idx = perm[i:i + bs]
                loss, _ = recon(dec, zt[idx], tc[idx], tp[idx])
                mu, lv = enc(x[idx])
                zz = mu + torch.randn_like(mu) * torch.exp(0.5 * lv)
                rec2, _ = recon(dec, zz, cells[idx], picks[idx])
                kl = (-0.5 * (1 + lv - mu ** 2 - lv.exp()).sum(1)).mean()
                loss = loss + a.vae_weight * (rec2 + a.beta * kl)
                opt.zero_grad(); loss.backward(); opt.step()
        if rnd % 20 == 0 or rnd == a.ot_rounds - 1:
            with torch.no_grad():
                pred = dec(zt)[0].argmax(-1)
            row = dict(phase="ot", round=rnd, matched_cell_acc=round((pred == tc).float().mean().item(), 4),
                       matched_exact=round((pred == tc).all(1).float().mean().item(), 3), qat=dec.qat,
                       sec=round(time.time() - t0))
            log.append(row); print("[train]", row, flush=True)
    dec.qat = False
    torch.save(dict(state=dec.state_dict(), hidden=hidden), os.path.join(a.out, "decoder.pt"))
    json.dump(dict(args=vars(a), params=dec.n_params(), n_var=dec.n_var, log=log),
              open(os.path.join(a.out, "train_log.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
