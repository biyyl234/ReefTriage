"""
scripts/test_ml_predictor.py
============================
验证模型 C (ML 白化概率预测器):

  1. 加载 data/output/scored_segments.json (28 礁段)
  2. 训练逻辑回归模型 (含 2020/2024 历史 DHW 增强)
  3. 打印测试集评估指标 (AUC / accuracy / confusion matrix ...)
  4. 打印逻辑回归系数, 列出前 5 个最重要特征
  5. 打印 28 个礁段当前的 bleaching_probability

用法:
    .venv\\Scripts\\python.exe scripts\\test_ml_predictor.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List

# 把项目根目录加入 sys.path, 以便 import app.scoring
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.scoring import config
from app.scoring.ml_predictor import (
    build_training_data,
    predict_bleaching_probability,
    train_model,
)


def main() -> None:
    scored_path = ROOT / "data" / "output" / "scored_segments.json"
    with open(scored_path, encoding="utf-8") as f:
        segments: List[Dict] = json.load(f)
    print(f"[1] Loaded {len(segments)} segments from {scored_path.name}")

    # 2) 构建训练数据 (含历史 DHW 增强)
    X, y, feature_names = build_training_data(segments)
    print(f"[2] Training matrix: X={X.shape}, y={y.shape}, "
          f"positives={int(y.sum())} / {len(y)} "
          f"(threshold DHW>={config.BLEACHING_DHW_THRESHOLD})")

    # 3) 训练 + 评估
    model_dict = train_model(X, y)
    m = model_dict["metrics"]
    print("\n[3] Test-set metrics "
          f"(train={model_dict['train_size']}, test={model_dict['test_size']}):")
    print(f"    AUC       : {m['auc']}")
    print(f"    Accuracy  : {m['accuracy']:.4f}")
    print(f"    Precision : {m['precision']:.4f}")
    print(f"    Recall    : {m['recall']:.4f}")
    print(f"    F1        : {m['f1']:.4f}")
    print(f"    Confusion matrix [ [TN, FP], [FN, TP] ]: {m['confusion_matrix']}")

    # 4) 逻辑回归系数 (按绝对值排序, 前 5)
    coef = model_dict["coef"]
    ranked = sorted(coef.items(), key=lambda kv: abs(kv[1]), reverse=True)
    print("\n[4] Top-5 features by |coef| (standardized LR coefficients):")
    for name, c in ranked[:5]:
        direction = "↑ raises bleaching risk" if c > 0 else "↓ lowers bleaching risk"
        print(f"    {name:35s} coef={c:+.4f}  ({direction})")
    print(f"    intercept = {model_dict['intercept']:+.4f}")

    # 5) 对 28 个礁段预测白化概率
    probs = predict_bleaching_probability(segments, model_dict)
    print("\n[5] Bleaching probability per segment (current snapshot):")
    for seg, p in zip(segments, probs):
        flag = " *BLEACHED*" if seg["current_dhw"] >= config.BLEACHING_DHW_THRESHOLD else ""
        print(f"    {seg['segment_id']}  dhw={seg['current_dhw']:5.2f}  "
              f"p_bleach={p:.3f}{flag}")

    print("\nOK: ml_predictor smoke test passed.")


if __name__ == "__main__":
    main()
