"""Reference INTEGER inference = exactly what the Solidity contract computes.
Pure Python ints (arbitrary precision, like int256); no floats anywhere.

seed (bytes32) -> z_q: for i in 0..7: s = b[4i]+b[4i+1]+b[4i+2]+b[4i+3] - 510 ; z_q[i] = (s*7) >> 5
  (b[j] = byte j of the seed, big-endian: uint8(uint256(seed) >> (8*(31-j))); '>>' floors)
hidden layer l:  acc = sum_i W[j][i]*h[i] + b[j]
                 h'[j] = 0 if acc <= 0 else min(127, (acc*M + 2^(SH-1)) >> SH)
output:          y[k] = sum_j W_out[k][j]*h[j] + b_out[k]
cells (16x8 left half, row-major): const_cells from table; variable cell v (index var_cells[v]):
                 class = argmax over c with bit c set in var_masks[v] of 2*(y[2v]*P[c][0]+y[2v+1]*P[c][1]) - C[c]
picks:           argmax over y[2*n_var + ...] groups fur(7) cloth(8) acc(6) glow(5)
ties -> lowest index (scan with strict '>').
Usage: python infer_int.py weights-int8.json [seed_hex]
"""
import json
import sys


def load(path="weights-int8.json"):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def seed_to_z(seed: bytes):
    assert len(seed) == 32
    return [((seed[4 * i] + seed[4 * i + 1] + seed[4 * i + 2] + seed[4 * i + 3] - 510) * 7) >> 5 for i in range(8)]


def forward(w, z):
    SH = w["SH"]; half = 1 << (SH - 1)
    h = list(z)
    hidden_trace = []
    for l in w["layers"]:
        nh = []
        for j in range(len(l["W"])):
            acc = l["b"][j]
            row = l["W"][j]
            for i in range(len(h)):
                acc += row[i] * h[i]
            nh.append(0 if acc <= 0 else min(127, (acc * l["M"] + half) >> SH))
        h = nh
        hidden_trace.append(h)
    y = []
    for k in range(len(w["W_out"])):
        acc = w["b_out"][k]
        row = w["W_out"][k]
        for j in range(len(h)):
            acc += row[j] * h[j]
        y.append(acc)
    cells = [0] * 128
    for k, v in w["const_cells"].items():
        cells[int(k)] = v
    P, C = w["P"], w["C"]
    for v, ci in enumerate(w["var_cells"]):
        ya, yb, m = y[2 * v], y[2 * v + 1], w["var_masks"][v]
        best, bc = None, 0
        for c in range(11):
            if (m >> c) & 1:
                sc = 2 * (ya * P[c][0] + yb * P[c][1]) - C[c]
                if best is None or sc > best:
                    best, bc = sc, c
        cells[ci] = bc
    picks, off = [], 2 * len(w["var_cells"])
    for n in w["groups"]:
        best, bi = None, 0
        for k in range(n):
            if best is None or y[off + k] > best:
                best, bi = y[off + k], k
        picks.append(bi); off += n
    return dict(z=list(z), hidden=hidden_trace, cells=cells, picks=picks)


def infer_seed(w, seed: bytes):
    return forward(w, seed_to_z(seed))


if __name__ == "__main__":
    w = load(sys.argv[1] if len(sys.argv) > 1 else "weights-int8.json")
    seed = bytes.fromhex(sys.argv[2]) if len(sys.argv) > 2 else bytes(range(32))
    r = infer_seed(w, seed)
    print("z_q:", r["z"]); print("picks (fur, cloth, acc, glow):", r["picks"])
    for row in range(16):
        print("".join("0123456789A"[c] for c in r["cells"][row * 8:(row + 1) * 8]))
