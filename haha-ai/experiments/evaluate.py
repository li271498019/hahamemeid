"""Quality check on NEW random seeds (combinations mostly never seen in training).

For a random code z, the procedural generator tells us the exact intended dog
(code_to_traits -> make_dog with all traits forced). We report how often the
network draws exactly that dog, and how many cells are off on average.
"""
import numpy as np
import torch

from latent import code_to_traits
from gen_data import make_dog
from palette import CLOTH, CLOTH_SH, ACC, GLOW
from model_def import GROUP_SIZES


def truth_for_code(zq, iv):
    f = code_to_traits(zq, iv)
    g, p, t = make_dog(np.random.default_rng(0), f)
    return g.reshape(-1), p


def decode_float(dec, zq):
    with torch.no_grad():
        cl, pl = dec(torch.tensor(np.asarray(zq), dtype=torch.float32) / 128.0)
    cells = cl.argmax(-1).numpy()
    picks, off = [], 0
    for n in GROUP_SIZES:
        picks.append(pl[:, off:off + n].argmax(1).numpy()); off += n
    return cells, np.stack(picks, 1)


def compare_to_truth(cells, picks, zqs, iv):
    exact, diff = [], []
    for c, pk, zq in zip(cells, picks, zqs):
        tg, tp = truth_for_code(zq, iv)
        ok = (c == tg).all()
        used = [True, np.isin(tg, [CLOTH, CLOTH_SH]).any(), (tg == ACC).any(), (tg == GLOW).any()]
        tpk = [tp["fur"], tp["cloth"], tp["acc"], tp["glow"]]
        ok_p = all((not u) or pk[i] == tpk[i] for i, u in enumerate(used))
        exact.append(ok and ok_p)
        diff.append(int((c != tg).sum()))
    return dict(seed_exact=round(float(np.mean(exact)), 3), seed_cells_off=round(float(np.mean(diff)), 2),
                seed_le2_off=round(float(np.mean(np.array(diff) <= 2)), 3))


def evaluate(dec, iv, n=400, float_mode=True, seed=777):
    rng = np.random.default_rng(seed)
    zqs = rng.integers(-128, 128, (n, 8))
    was = dec.qat
    dec.qat = not float_mode and was
    cells, picks = decode_float(dec, zqs)
    dec.qat = was
    return compare_to_truth(cells, picks, zqs, iv)
