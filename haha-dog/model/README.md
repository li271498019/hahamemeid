# 链上像素柴犬 · 生成模型训练包 (v6)

这个文件夹里是一套**完全自带**的 Python 程序：它会自己画出 1000 只柴犬当训练素材、拼成素材图、再切回数据、训练一个**很小的神经网络**（约 1 万个参数），然后把它变成 **int8 整数权重**，方便以后写进以太坊/BSC 智能合约里，在链上直接"算"出每一只狗。

> 背景（星空 / 月夜 / 故障 / 扫描线 / 放射光）**不训练**，以后由合约直接画。模型只负责画狗。

---

## 一、第一次使用（Windows 小白步骤）

1. **安装 Python 3.10 ~ 3.13**  
   打开 https://www.python.org/downloads/ 下载安装。安装第一页一定要勾选 **"Add python.exe to PATH"**。
2. **解压** `onchain-pixel-model.zip`，比如解压到 `D:\onchain-pixel-model`。
3. **打开命令行**：在这个文件夹的地址栏里输入 `cmd` 回车（会在当前文件夹打开黑色窗口）。
4. **安装依赖**（只需要一次，torch 比较大，约几百 MB，耐心等）：
   ```
   pip install -r requirements.txt
   ```
   如果下载很慢，可以用国内镜像：
   ```
   pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
   ```
5. **一键运行**：
   ```
   python run_all.py
   ```
   普通电脑 CPU 大约 **8～20 分钟**（我们测试机约 7.5 分钟）（不需要显卡）。窗口里会不断打印训练进度，最后出现 `ALL DONE` 就是成功了。

想先快速检查环境是否正常（1 分钟，效果很差，只是试跑）：
```
python run_all.py --fast
```

Mac / Linux 一样，只是把 `python` 换成 `python3`、`pip` 换成 `pip3`。

---

## 二、跑完以后看什么

| 文件 | 是什么 |
|---|---|
| `preview-dataset.png` | 程序画出来的训练素材样例 |
| `sheets/sheet_01.png` ~ `sheet_04.png` | 训练素材图（每张 250 只，16×16 一格，透明背景）；`sheets/preview/` 里是放大 4 倍、带橙色底的方便查看版 |
| `out/samples_float.png` | 训练好的模型随机画出来的狗 |
| `samples.png` | **用纯整数算法（和合约一模一样）** 随机画的 32 只狗 + 合约背景，这是最终效果预览 |
| `weights-int8.json` | int8 整数权重，给合约用 |
| `model-config.json` | 网络结构、调色板、种子→输入规则、背景、字节大小估算 |
| `test-vectors.json` + `test-vectors/` | 16 组测试向量（种子 → 每一层整数结果 → 像素），合约开发时用来逐位对照 |
| `training-report.md` | 训练日志、浮点 vs int8 一致率、质量统计 |

---

## 三、自己改素材再训练

素材图 `sheets/sheet_XX.png` 就是训练数据。你可以用任意像素画软件（Aseprite、Photoshop 等）修改里面的狗，然后：
```
python run_all.py --skip-gen
```
这样**不会重新生成素材**，直接切你的图来训练。注意：
- 只能用调色板里的颜色（见 `palette.py` / `model-config.json`），背景必须是透明。
- 狗必须左右对称（模型只画左半边，再镜像）。
- 切图程序 `slice_sheets.py` 发现不认识的颜色或不对称会报错并告诉你是第几格。

---

## 四、原理（简单说）

- 画布 24×24，狗是 16×16，放在下方居中，上方空间留给合约画背景。
- 模型只输出**左半边 16×8 = 128 格**，镜像成整张脸 → 参数少一半，而且一定对称。
- 每格是 11 种"格子类型"之一（空 / 描边 / 毛色 / 毛色阴影 / 白色斑纹 / 衣服 / 衣服阴影 / 配饰 / 发光 / 白 / 粉），具体颜色由模型另外选（毛色 7 种、衣服 8 种、配饰 6 种、发光 5 种）。所有颜色来自固定调色板。
- 有 29 格永远相同（直接查表），模型只需要算其余 99 格。
- 输入：tokenId 的 32 字节种子 → 8 个 int8 数（每 4 字节相加，近似正态分布）。
- 网络：`8 → 64 → 32 → 224`，ReLU，约 10,048 个参数，全部 int8，每层一个整数缩放（乘法 + 右移 24 位）。
- 训练方法：先训练一个 VAE（变分自编码器），再用"最优传输"把 1000 个随机种子一一配对到 1000 只素材狗上继续训练，让**任意随机种子**都能画出干净的狗；最后 30% 轮次用 int8 模拟（QAT）训练，保证量化后几乎不变。
- `infer_int.py` 是纯整数推理（只有加法、乘法、移位、比较），和以后 Solidity 合约的算法逐位一致。

## 五、文件说明

| 文件 | 作用 |
|---|---|
| `run_all.py` | 一键运行全部步骤 |
| `palette.py` | 固定调色板 |
| `dog.py` / `gen_data.py` | 柴犬模板与 1000 只素材生成（帽子/发型、耳朵、眼睛表情、嘴、项圈、颜色） |
| `make_sheets.py` / `slice_sheets.py` | 拼素材图 / 切素材图 |
| `model_def.py` / `train.py` | 网络定义与训练 |
| `sample_float.py` | 抽样预览和质量统计 |
| `quantize.py` | int8 量化 + 浮点/整数一致率 |
| `infer_int.py` | 纯整数推理（合约参考实现） |
| `backgrounds.py` / `render_svg.py` / `preview_bg.py` | 合约背景（5 种）与 SVG 渲染参考 |
| `export.py` | 导出测试向量、配置、预览 |

## 六、常见问题

- **`pip` 不是内部或外部命令**：安装 Python 时没勾 "Add to PATH"，重新安装并勾选，或用 `py -m pip install -r requirements.txt`、`py run_all.py`。
- **torch 装不上**：确认 Python 是 64 位且版本 3.10～3.13；或去 https://pytorch.org 按提示安装 CPU 版。
- **每次结果不完全一样**：随机初始化和电脑不同会导致训练结果略有差异，属正常。想要和预览完全一致的权重，直接用我们给的 `weights-int8.json`。
- **有显卡吗？** 不需要。
