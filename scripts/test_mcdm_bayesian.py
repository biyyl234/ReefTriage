"""
scripts/test_mcdm_bayesian.py
==============================
冒烟测试: 加载 scored_segments.json, 运行 MCDM (熵权法+TOPSIS) 与
贝叶斯蒙特卡洛不确定性分析, 打印关键结果。

用法:
    .venv\\Scripts\\python.exe scripts\\test_mcdm_bayesian.py
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

from app.scoring import bayesian, config, mcdm  # noqa: E402


DATA_PATH = ROOT / "data" / "output" / "scored_segments.json"


def main() -> None:
    # 1. 加载数据
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        segments: List[Dict] = json.load(f)
    print(f"[load] 礁段数量: {len(segments)}")

    # 2. MCDM: 权重 + TOPSIS 分数
    scores, weights = mcdm.compute_mcdm(segments)

    # 2a. 打印各特征权重 (按权重降序, 前 5)
    print("\n=== 熵权法权重 (按权重降序, 前 5) ===")
    sorted_w = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)
    label_map = {f["key"]: f["label"] for f in config.MCDM_FEATURES}
    for key, w in sorted_w[:5]:
        print(f"  {key:35s} ({label_map.get(key, ''):<20s}) w = {w:.4f}")
    print(f"  ... 共 {len(weights)} 个特征, 权重和 = {sum(weights.values()):.4f}")

    # 2b. 打印前 5 个礁段的 mcdm_score
    print("\n=== 前 5 个礁段的 MCDM 得分 ===")
    for i, seg in enumerate(segments[:5]):
        name = seg.get("name") or seg.get("segment_id") or f"R{i:02d}"
        print(f"  [{seg.get('segment_id', '?'):>3}] {name:<35s}  mcdm_score = {scores[i]:6.2f}")

    # 3. 贝叶斯不确定性: 用预先算好的权重 + 全数据集拟合的 PIS/NIS 构造单段评分闭包
    #    score_fn(segment) -> 0-100  (PIS/NIS 固定, 仅扰动单段特征)
    score_fn = mcdm.make_topsis_scorer(segments, weights)

    print("\n=== 贝叶斯不确定性 (蒙特卡洛) ===")
    print(f"  采样次数 n_samples = {config.BAYESIAN_N_SAMPLES}")
    print(f"  扰动特征数         = {len(config.BAYESIAN_NOISE)}")

    # 3a. 第一个礁段的完整统计
    first = segments[0]
    res0 = bayesian.bayesian_score_distribution(
        first, score_fn, n_samples=config.BAYESIAN_N_SAMPLES,
    )
    name0 = first.get("name") or first.get("segment_id")
    print(f"\n  第一个礁段: [{first.get('segment_id')}] {name0}")
    print(f"    点估计 (mean)   = {res0['mean']:.2f}")
    print(f"    标准差  (std)   = {res0['std']:.2f}")
    print(f"    95% CI  lower   = {res0['ci_lower']:.2f}")
    print(f"    95% CI  upper   = {res0['ci_upper']:.2f}")
    print(f"    样本数          = {len(res0['samples'])}")

    # 3b. 批量跑一遍全部礁段, 验证接口无报错
    all_res = bayesian.compute_bayesian_for_all(
        segments, score_fn, n_samples=min(200, config.BAYESIAN_N_SAMPLES),
        seed=42,
    )
    print(f"\n  批量 compute_bayesian_for_all 完成: {len(all_res)} 个礁段")
    print(f"    第一个 mean/std/CI = {all_res[0]['mean']:.2f} / "
          f"{all_res[0]['std']:.2f} / "
          f"[{all_res[0]['ci_lower']:.2f}, {all_res[0]['ci_upper']:.2f}]")

    print("\n[ok] 全部通过")


if __name__ == "__main__":
    main()
