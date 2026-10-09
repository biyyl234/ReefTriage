"""
scripts/test_rubric_v2.py
=========================
冒烟测试: 验证 rubric_v2 能正常加载 scored_segments.json 的第一个礁段,
构造结构化 state, 并与 v1 向后兼容。

运行:
    .venv\\Scripts\\python.exe scripts\\test_rubric_v2.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# 让脚本能从项目根 import app.*
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.scoring import rubric_v2  # noqa: E402
from app.scoring.rubric import interpret_score as interpret_score_v1  # noqa: E402


def main() -> int:
    data_path = PROJECT_ROOT / "data" / "output" / "scored_segments.json"
    if not data_path.exists():
        print(f"[FAIL] 找不到数据文件: {data_path}")
        return 1

    with data_path.open("r", encoding="utf-8") as f:
        segments = json.load(f)

    if not segments:
        print("[FAIL] scored_segments.json 为空")
        return 1

    first = segments[0]
    print(f"[INFO] 加载第一个礁段: {first.get('segment_id')} - {first.get('name')}")
    print()

    # 1) build_state_v2
    state = rubric_v2.build_state_v2(first)
    print("=== build_state_v2 结构化 state ===")
    print(json.dumps(state, indent=2, ensure_ascii=False))
    print()

    # 基本断言
    assert "dimensions" in state, "state 缺少 dimensions"
    for dim in ("thermal_stress", "vulnerability", "recovery_potential",
                "tourism_value", "cost_effectiveness"):
        assert dim in state["dimensions"], f"缺少维度 {dim}"
    ts = state["dimensions"]["thermal_stress"]
    assert "bleaching_probability" in ts, "thermal_stress 缺少 bleaching_probability"
    assert "confidence_interval" in ts, "thermal_stress 缺少 confidence_interval"
    assert state["dimension_weights"], "dimension_weights 为空"
    print("[OK] build_state_v2 结构断言通过")
    print()

    # 2) build_questions_v2
    questions = rubric_v2.build_questions_v2()
    print(f"=== build_questions_v2: 共 {len(questions)} 个问题 ===")
    for qid, q in questions.items():
        print(f"  - {qid}: type={q.get('type')}")
    expected = {
        "dim_thermal_stress", "dim_vulnerability", "dim_recovery_potential",
        "dim_tourism_value", "dim_cost_effectiveness",
        "priority_score", "priority_class",
    }
    assert expected.issubset(questions.keys()), f"问题集合不完整: 缺 {expected - set(questions.keys())}"
    print("[OK] build_questions_v2 包含 5 个维度子问题 + priority_score + priority_class")
    print()

    # 3) interpret_score_v2 与 v1 兼容
    for raw in (0.0, 1.0, 2.0, 3.0, 4.0, 2.5):
        v2 = rubric_v2.interpret_score_v2(raw)
        v1 = interpret_score_v1(raw)
        assert v2 == v1, f"interpret 不一致 raw={raw}: v2={v2} v1={v1}"
    print("[OK] interpret_score_v2 与 v1 interpret_score 在 0..4 输入下映射一致")
    print(f"       示例: raw=2.5 -> {rubric_v2.interpret_score_v2(2.5)} / 100")
    print()

    # 4) 规则复算子分 (可选基线)
    rule_scores = rubric_v2.local_dimension_scores(state)
    print("=== local_dimension_scores 规则基线分 (0..4) ===")
    for k, v in rule_scores.items():
        print(f"  - {k:22s}: {v:.2f}")
    print()

    # 5) 权重和校验
    w_sum = sum(rubric_v2.DIMENSION_WEIGHTS.values())
    print(f"=== 维度权重和: {w_sum:.2f} (应=1.0) ===")
    assert abs(w_sum - 1.0) < 1e-6, f"权重和不等于 1: {w_sum}"
    print()

    print("[PASS] 全部冒烟测试通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
