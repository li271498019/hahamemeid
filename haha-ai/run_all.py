"""一键运行 / one command:   python run_all.py

步骤 steps:
  1. gen_data.py     生成 1000 只柴犬（透明背景）          -> data/generated.npz, preview-dataset.png
  2. make_sheets.py  拼成 4 张素材图 (每张 250 只, 16x16 一格) -> sheets/sheet_01..04.png
  3. slice_sheets.py 把素材图切回训练数据                     -> data/dataset.npz
  4. train.py        训练 (VAE + 最优传输 + int8 QAT)         -> out/decoder.pt
  5. sample_float.py 抽样看效果                               -> out/samples_float.png
  6. quantize.py     int8 量化                                -> weights-int8.json
  7. export.py       测试向量 / 配置 / 预览                    -> test-vectors.json, model-config.json, samples.png

常用参数:
  --skip-gen       不重新生成素材，直接用 sheets/ 里现有的图（你手动改过素材图时用）
  --hidden 64,32   隐藏层大小（默认 64,32 ≈ 1 万参数）
  --fast           快速试跑（训练轮数很少，效果差，只用来检查环境）
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def run(*args):
    cmd = [sys.executable] + list(args)
    print("\n>>> " + " ".join(args), flush=True)
    t = time.time()
    r = subprocess.run(cmd, cwd=HERE)
    if r.returncode != 0:
        print(f"\n[run_all] 失败 FAILED: {' '.join(args)}  (exit {r.returncode})")
        sys.exit(r.returncode)
    print(f"[run_all] ok ({time.time() - t:.0f}s)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-gen", action="store_true")
    ap.add_argument("--hidden", default="64,32")
    ap.add_argument("--fast", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    if not a.skip_gen:
        run("gen_data.py", "--n", "1000", "--seed", "2026")
        run("make_sheets.py")
    run("slice_sheets.py")
    tr = ["train.py", "--hidden", a.hidden, "--out", "out"]
    if a.fast:
        tr += ["--vae_epochs", "60", "--ot_rounds", "10"]
    else:
        tr += ["--vae_epochs", "1500", "--ot_rounds", "200"]
    run(*tr)
    run("sample_float.py", "out")
    run("quantize.py", "--run", "out", "--out", "weights-int8.json")
    run("export.py", "--run", "out", "--weights", "weights-int8.json")
    print(f"\n[run_all] 全部完成 ALL DONE in {(time.time() - t0) / 60:.1f} min")
    print("  看图: samples.png, out/samples_float.png, sheets/preview/")
    print("  给合约: weights-int8.json, model-config.json, test-vectors.json")


if __name__ == "__main__":
    main()
