"""Write the Foundry fixtures used by test/hahadog/*.t.sol.

  test/hahadog/fixtures/model-vectors.json   16 model test vectors + N random keccak seeds
  test/hahadog/fixtures/token-uris.json      expected tokenURI hashes (generating, ready)

Usage: python gen_fixtures.py [N]
"""
import json
import os
import random
import sys

import hahadog_ref as R

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
OUT = os.path.join(ROOT, "test", "hahadog", "fixtures")


def h(b):
    return "0x" + b.hex()


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    os.makedirs(OUT, exist_ok=True)
    tv = json.load(open(os.path.join(ROOT, "haha-dog", "model", "test-vectors.json")))["vectors"]
    rnd = random.Random(8004)
    seeds = [bytes.fromhex(v["seed"][2:]) for v in tv]
    seeds += [R.keccak256(rnd.randbytes(32)) for _ in range(n)]
    d = dict(seeds=[], cells=[], picks=[], traits=[], svgHashes=[])
    for s in seeds:
        t = R.traits(s)
        d["seeds"].append(h(s))
        d["cells"].append(h(bytes(t["cells"])))
        d["picks"].append(sum(p << (8 * i) for i, p in enumerate(t["picks"])))
        packed = (t["style"] | t["color"] << 8 | t["head"] << 16 | t["eyes"] << 24 | t["mouth"] << 32
                  | t["neck"] << 40 | t["score"] << 48 | t["tier"] << 56)
        d["traits"].append(packed)
        d["svgHashes"].append(h(R.keccak256(R.svg_for(t).encode())))
    json.dump(d, open(os.path.join(OUT, "model-vectors.json"), "w"), indent=1)

    cases = []
    for i, s in enumerate(seeds[:12]):
        for state in (0, 1):
            if state != 1 and i > 1:
                continue
            uri = R.token_uri(i + 1, s, i % 3, state)
            cases.append(dict(tokenId=i + 1, seed=h(s), rerolls=i % 3, state=state, hash=h(R.keccak256(uri.encode()))))
    sample = R.token_uri(1, seeds[0], 0, 1)
    json.dump(dict(tokenIds=[c["tokenId"] for c in cases], seeds=[c["seed"] for c in cases],
                   rerolls=[c["rerolls"] for c in cases], states=[c["state"] for c in cases],
                   hashes=[c["hash"] for c in cases], sampleUri=sample),
              open(os.path.join(OUT, "token-uris.json"), "w"), indent=1)
    print("fixtures:", len(seeds), "model vectors,", len(cases), "tokenURI cases")


if __name__ == "__main__":
    main()
