"""Quick look at float-model samples. Usage: python sample_float.py out_dir [temp]"""
import sys, numpy as np, torch
from model_def import Decoder, irwin_hall_z, GROUP_SIZES
from gen_data import render, grid_image
from palette import BGS, rgb


def load_decoder(out):
    ck = torch.load(f"{out}/decoder.pt")
    masks = torch.tensor(np.load(f"{out}/cell_masks.npy"))
    dec = Decoder(ck["hidden"], masks); dec.load_state_dict(ck["state"]); dec.eval()
    return dec


if __name__ == "__main__":
    out = sys.argv[1]; temp = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    dec = load_decoder(out)
    dec.qat = True   # view the int8-simulated model (what goes on-chain)
    z = irwin_hall_z(400, torch.Generator().manual_seed(123)) * temp
    with torch.no_grad():
        cl, pl = dec(z)
    cells = cl.argmax(-1).numpy().reshape(-1, 16, 8)
    picks = []; off = 0
    for n in GROUP_SIZES:
        picks.append(pl[:, off:off + n].argmax(1).numpy()); off += n
    picks = np.stack(picks, 1)
    train = np.load("data/dataset.npz")["halves"].reshape(-1, 128)
    ham = np.array([(train != c.reshape(1, -1)).sum(1).min() for c in cells])
    print("min-hamming to training set: mean %.2f median %d  <=3: %.2f  unique shapes %d/400" %
          (ham.mean(), np.median(ham), (ham <= 3).mean(), len({c.tobytes() for c in cells})))
    import json
    json.dump(dict(samples=400, latent_scale=temp, min_hamming_to_train_mean=round(float(ham.mean()), 2),
                   min_hamming_median=int(np.median(ham)), frac_near_copy_le3=round(float((ham <= 3).mean()), 3),
                   unique_shapes=len({c.tobytes() for c in cells})), open(f"{out}/quality.json", "w"), indent=1)
    items = [render(cells[i], dict(fur=picks[i, 0], cloth=picks[i, 1], acc=picks[i, 2], glow=picks[i, 3]),
                    rgb(BGS[i % len(BGS)])) for i in range(32)]
    grid_image(items, cols=8, scale=6).save(f"{out}/samples_float.png")
