# 训练报告 / Training report

- 结构 Architecture: 8 -> 64 -> 32 -> 224 (ReLU, int8)
- 参数量 Params: 10048
- 模型数据大小 Model data: ~10778 bytes (int8 weights 9728 B, biases 640 B @ 14 bit)
- 浮点 float32 vs int8 (5000 random seeds): {'cell_agreement': 0.95952, 'dogs_identical': 0.0136, 'pick_agreement': 0.9012, 'mean_cells_differing': 5.181}
- QAT 模拟 vs int8 (5000 random seeds): {'cell_agreement': 0.99717, 'dogs_identical': 0.704, 'pick_agreement': 0.9981, 'mean_cells_differing': 0.363}
- 说明：最后 30% 训练轮次是在 int8 模拟（QAT）下进行的，所以真正上链的是整数模型；float32 那一行只是参考。

## Training log
```
{"phase": "vae", "epoch": 0, "rec": 683.47, "kl": 33.66, "sec": 1}
{"phase": "vae", "epoch": 500, "rec": 17.2, "kl": 15.39, "sec": 28}
{"phase": "vae", "epoch": 1000, "rec": 11.88, "kl": 15.59, "sec": 55}
{"phase": "vae", "epoch": 1499, "rec": 10.71, "kl": 15.86, "sec": 83}
{"phase": "ot", "round": 0, "matched_cell_acc": 0.8983, "matched_exact": 0.003, "qat": false, "sec": 84}
{"phase": "ot", "round": 20, "matched_cell_acc": 0.9121, "matched_exact": 0.005, "qat": false, "sec": 100}
{"phase": "ot", "round": 40, "matched_cell_acc": 0.9179, "matched_exact": 0.005, "qat": false, "sec": 116}
{"phase": "ot", "round": 60, "matched_cell_acc": 0.9203, "matched_exact": 0.002, "qat": false, "sec": 131}
{"phase": "ot", "round": 80, "matched_cell_acc": 0.9212, "matched_exact": 0.002, "qat": false, "sec": 148}
{"phase": "ot", "round": 100, "matched_cell_acc": 0.9232, "matched_exact": 0.002, "qat": false, "sec": 163}
{"phase": "ot", "round": 120, "matched_cell_acc": 0.9231, "matched_exact": 0.001, "qat": false, "sec": 179}
{"phase": "ot", "round": 140, "matched_cell_acc": 0.9187, "matched_exact": 0.0, "qat": true, "sec": 195}
{"phase": "ot", "round": 160, "matched_cell_acc": 0.9167, "matched_exact": 0.003, "qat": true, "sec": 211}
{"phase": "ot", "round": 180, "matched_cell_acc": 0.9179, "matched_exact": 0.002, "qat": true, "sec": 228}
{"phase": "ot", "round": 199, "matched_cell_acc": 0.9215, "matched_exact": 0.001, "qat": true, "sec": 243}
```

## Sample quality
```
{
 "samples": 400,
 "latent_scale": 1.0,
 "min_hamming_to_train_mean": 6.95,
 "min_hamming_median": 6,
 "frac_near_copy_le3": 0.24,
 "unique_shapes": 397
}
```