"""
scripts/test_optimizer_threshold.py
==================================
验证 app/scoring/optimizer.py 与 app/scoring/threshold.py.

用法:
    .venv\\Scripts\\python.exe scripts/test_optimizer_threshold.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# 把项目根目录加入 sys.path, 以便 import app.*
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.scoring import config
from app.scoring.optimizer import (
    estimate_restoration_cost,
    expected_gain,
    connectivity_amplifier,
    optimize_budget,
    greedy_optimize,
)
from app.scoring.threshold import (
    compute_roc,
    optimal_threshold_youden,
    bootstrap_threshold_ci,
    optimize_all_thresholds,
)


def main() -> int:
    data_path = ROOT / "data" / "output" / "scored_segments.json"
    with open(data_path, encoding="utf-8") as f:
        segments = json.load(f)
    print(f"[load] {len(segments)} segments from {data_path.name}")

    # ------------------------------------------------------------------
    # 1. optimizer 单元抽查
    # ------------------------------------------------------------------
    print("\n=== optimizer 抽查 (前 3 段) ===")
    for seg in segments[:3]:
        c = estimate_restoration_cost(seg, config.DEFAULT_UNIT_COST)
        g = expected_gain(seg)
        a = connectivity_amplifier(seg)
        print(f"  {seg['segment_id']} {seg['name'][:24]:24s} "
              f"cost=${c:8.2f}  gain={g:.4f}  amp={a:.3f}  score={g*a:.4f}")

    # ------------------------------------------------------------------
    # 2. optimize_budget: budget=50000, unit_cost=5000
    # ------------------------------------------------------------------
    budget = 50000.0
    unit_cost = 5000.0
    print(f"\n=== optimize_budget (budget=${budget:,.0f}, unit_cost=${unit_cost:,.0f}) ===")
    result = optimize_budget(segments, budget=budget, unit_cost=unit_cost)
    print(f"  method          : {result['method']}")
    print(f"  solver_status   : {result.get('solver_status', '-')}")
    print(f"  selected count  : {len(result['selected'])}")
    print(f"  total_cost      : ${result['total_cost']:,.2f}")
    print(f"  total_gain      : {result['total_gain']:.4f}")
    print(f"  budget_used_pct : {result['budget_used_pct']}%")
    print(f"  selected ids    : {result['selected']}")
    print("  details:")
    for d in result["details"]:
        print(f"    - {d['segment_id']:4s} {d['name'][:26]:26s} "
              f"cost=${d['cost']:8.2f}  gain={d['expected_gain']:.4f} "
              f"amp={d['amplifier']:.3f}  score={d['score']:.4f}")

    # 对照: greedy
    greedy = greedy_optimize(segments, budget=budget, unit_cost=unit_cost)
    print(f"\n  [greedy 对照] selected={len(greedy['selected'])}  "
          f"cost=${greedy['total_cost']:,.2f}  gain={greedy['total_gain']:.4f}  "
          f"ids={greedy['selected']}")

    # 基本断言
    assert result["total_cost"] <= budget + 1e-6, "预算被突破!"
    assert len(result["selected"]) == len(result["details"])
    assert result["budget_used_pct"] <= 100.0

    # ------------------------------------------------------------------
    # 3. threshold: score 作为预测值, current_dhw >= 4 作为标签
    # ------------------------------------------------------------------
    scores = [s["score"] for s in segments]
    labels = [1 if s["current_dhw"] >= 4.0 else 0 for s in segments]
    print(f"\n=== threshold (positives={sum(labels)}/{len(labels)}) ===")

    roc = compute_roc(scores, labels)
    print(f"  AUC             : {roc['auc']:.4f}  (points={len(roc['fpr'])})")

    youden = optimal_threshold_youden(scores, labels)
    print(f"  Youden threshold: {youden['threshold']:.2f}")
    print(f"    J             : {youden['youden_j']:.4f}")
    print(f"    sensitivity   : {youden['sensitivity']:.4f}")
    print(f"    specificity   : {youden['specificity']:.4f}")

    ci = bootstrap_threshold_ci(scores, labels, n_bootstrap=config.BACKTEST_BOOTSTRAP_N)
    print(f"  bootstrap 95% CI: [{ci['ci_lower']:.2f}, {ci['ci_upper']:.2f}]  "
          f"mean={ci['mean']:.2f}  (n={len(ci['all_thresholds'])})")

    all_thr = optimize_all_thresholds(scores, labels)
    print(f"  invest  threshold: {all_thr['invest_threshold']['threshold']:.2f}")
    print(f"  monitor threshold: {all_thr['monitor_threshold']['threshold']:.2f}")

    # 基本断言
    assert 0.0 <= roc["auc"] <= 1.0 or roc["auc"] != roc["auc"]  # nan 也允许
    assert all_thr["invest_threshold"]["threshold"] > all_thr["monitor_threshold"]["threshold"] - 1e-6

    print("\n[OK] all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
