"""
app/scoring/optimizer.py
========================
预算约束整数规划优化器 (模型B).

在固定预算下选择一组礁段进行恢复投入, 使预期生态收益最大化.

数学模型 (0-1 整数规划):
    决策变量  x_i ∈ {0, 1}
    目标      max  Σ x_i · expected_gain_i · connectivity_amplifier_i
    约束      Σ x_i · cost_i               ≤ budget
              x_i ∈ {0, 1}

求解器使用 PuLP 自带的 CBC; 求解失败时回退到贪心算法 (按 边际收益/成本 比排序).
"""

from __future__ import annotations

import math
from typing import Dict, List, Any

import pulp

from . import config


# ---------------------------------------------------------------------------
# 数值安全工具
# ---------------------------------------------------------------------------

def _safe_float(value: Any, default: float = 0.0) -> float:
    """把任意字段转成 float, 把 None / NaN / Inf 都归约到 default."""
    if value is None:
        return default
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(v) or math.isinf(v):
        return default
    return v


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


# ---------------------------------------------------------------------------
# 成本与收益模型
# ---------------------------------------------------------------------------

def estimate_restoration_cost(segment: Dict,
                              unit_cost: float = config.DEFAULT_UNIT_COST) -> float:
    """估算单个礁段的恢复成本 (USD).

    cost = unit_cost × reef_area_km2 × (1 + mean_depth × 0.05)

    浅水便宜, 深水贵: 水深每增加 1 米, 成本上浮 5%.

    Parameters
    ----------
    segment : dict
        礁段记录, 需包含 ``reef_area_km2`` 与 ``mean_depth``.
    unit_cost : float
        单位面积基础成本 (USD/km²), 默认 :data:`config.DEFAULT_UNIT_COST`.

    Returns
    -------
    float
        恢复成本 (USD), 恒 >= 0.
    """
    area = _safe_float(segment.get("reef_area_km2"), 0.0)
    depth = _safe_float(segment.get("mean_depth"), 0.0)
    uc = _safe_float(unit_cost, config.DEFAULT_UNIT_COST)
    if uc <= 0:
        uc = config.DEFAULT_UNIT_COST
    cost = uc * area * (1.0 + depth * 0.05)
    return max(0.0, cost)


def get_segment_cost(segment: Dict,
                     unit_cost: float = config.DEFAULT_UNIT_COST
                     ) -> tuple:
    """返回单个礁段的实际恢复成本及成本来源。

    - 若 segment 中存在 ``restoration_plan.total_cost`` 且 > 0, 使用该实际保存成本
      (cost_source = "saved_plan")。
    - 否则回退到 :func:`estimate_restoration_cost` 的估算值
      (cost_source = "estimated")。

    Returns
    -------
    (float, str)
        (cost, cost_source)
    """
    plan = segment.get("restoration_plan") or {}
    saved = plan.get("total_cost")
    saved_cost = _safe_float(saved, 0.0)
    if saved_cost > 0:
        return saved_cost, "saved_plan"
    return estimate_restoration_cost(segment, unit_cost), "estimated"


def expected_gain(segment: Dict) -> float:
    """估算单位投入下的预期生态收益 (0-1).

    expected_gain = bleaching_probability × (1 - rhi_score/100) × recovery_rate

    - ``bleaching_probability`` 缺失时, 用 ``current_dhw / 8`` 作代理
      (DHW=8 时概率≈1).
    - ``recovery_rate`` 由连通性代理: ``connectivity_score/5 × 0.3 + 0.1``
      (连通性越好恢复越快, 取值范围 0.1 - 0.4).

    Returns
    -------
    float
        预期收益, 被截断到 [0, 1].
    """
    bp = segment.get("bleaching_probability", None)
    if bp is None:
        dhw = _safe_float(segment.get("current_dhw"), 0.0)
        bp = dhw / 8.0
    bp = _clamp(_safe_float(bp, 0.0), 0.0, 1.0)

    rhi = _safe_float(segment.get("rhi_score"), 50.0)
    rhi_term = 1.0 - _clamp(rhi, 0.0, 100.0) / 100.0

    conn = _clamp(_safe_float(segment.get("connectivity_score"), 3.0), 1.0, 5.0)
    recovery_rate = conn / 5.0 * 0.3 + 0.1

    g = bp * rhi_term * recovery_rate
    return _clamp(g, 0.0, 1.0)


def connectivity_amplifier(segment: Dict) -> float:
    """连通性放大系数: 高连通礁段恢复后向周边输出幼虫, 放大整体收益.

    amplifier = 1 + larval_output

    ``larval_output`` 缺失时用 ``connectivity_score/5`` 作代理.

    Returns
    -------
    float
        放大系数, 恒 >= 1.
    """
    lo = segment.get("larval_output", None)
    if lo is None:
        conn = _clamp(_safe_float(segment.get("connectivity_score"), 3.0), 1.0, 5.0)
        lo = conn / 5.0
    lo = _safe_float(lo, 0.0)
    if math.isinf(lo) or lo < 0:
        lo = 0.0
    return 1.0 + lo


# ---------------------------------------------------------------------------
# 贪心备选方案
# ---------------------------------------------------------------------------

def greedy_optimize(segments: List[Dict],
                    budget: float,
                    unit_cost: float = config.DEFAULT_UNIT_COST) -> Dict:
    """贪心 + 局部搜索备选: 按 边际收益/成本 比降序选择, 直到预算耗尽.

    返回结构与 :func:`optimize_budget` 一致, 便于上层无缝切换.
    """
    budget = _safe_float(budget, 0.0)
    items = []
    for seg in segments:
        cost, cost_src = get_segment_cost(seg, unit_cost)
        gain = expected_gain(seg)
        amp = connectivity_amplifier(seg)
        eff_gain = gain * amp
        ratio = (eff_gain / cost) if cost > 0 else 0.0
        items.append({
            "segment": seg,
            "segment_id": seg.get("segment_id", "?"),
            "name": seg.get("name", ""),
            "cost": cost,
            "cost_source": cost_src,
            "expected_gain": gain,
            "amplifier": amp,
            "score": eff_gain,
            "ratio": ratio,
        })

    # 按 性价比 降序
    items.sort(key=lambda x: x["ratio"], reverse=True)

    selected: List[Dict] = []
    spent = 0.0
    for it in items:
        if spent + it["cost"] <= budget:
            selected.append(it)
            spent += it["cost"]

    total_gain = sum(it["score"] for it in selected)
    return {
        "selected": [it["segment_id"] for it in selected],
        "total_cost": round(spent, 2),
        "total_gain": round(total_gain, 6),
        "budget_used_pct": round((spent / budget * 100.0) if budget > 0 else 0.0, 2),
        "details": [
            {
                "segment_id": it["segment_id"],
                "name": it["name"],
                "cost": round(it["cost"], 2),
                "cost_source": it["cost_source"],
                "expected_gain": round(it["expected_gain"], 6),
                "amplifier": round(it["amplifier"], 6),
                "score": round(it["score"], 6),
            }
            for it in selected
        ],
        "method": "greedy",
    }


# ---------------------------------------------------------------------------
# 主入口: PuLP 0-1 整数规划
# ---------------------------------------------------------------------------

def optimize_budget(segments: List[Dict],
                   budget: float,
                   unit_cost: float = config.DEFAULT_UNIT_COST) -> Dict:
    """在预算约束下用 0-1 整数规划选择最优礁段集合.

    Parameters
    ----------
    segments : list[dict]
        候选礁段列表.
    budget : float
        总预算 (USD).
    unit_cost : float
        单位面积成本, 默认 :data:`config.DEFAULT_UNIT_COST`.

    Returns
    -------
    dict
        ``selected`` / ``total_cost`` / ``total_gain`` / ``budget_used_pct`` /
        ``details``; 并附带 ``method`` 字段 (``"ip"`` 或 ``"greedy"``).
        若 PuLP 求解失败, 自动回退到 :func:`greedy_optimize`.
    """
    budget = _safe_float(budget, 0.0)
    n = len(segments)
    if n == 0 or budget <= 0:
        return {
            "selected": [],
            "total_cost": 0.0,
            "total_gain": 0.0,
            "budget_used_pct": 0.0,
            "details": [],
            "method": "ip",
        }

    # 预先计算 cost / gain / amplifier
    costs: List[float] = []
    cost_sources: List[str] = []
    gains: List[float] = []
    amps: List[float] = []
    eff_gains: List[float] = []
    for seg in segments:
        c, c_src = get_segment_cost(seg, unit_cost)
        g = expected_gain(seg)
        a = connectivity_amplifier(seg)
        costs.append(c)
        cost_sources.append(c_src)
        gains.append(g)
        amps.append(a)
        eff_gains.append(g * a)

    # 建立 PuLP 模型 (PuLP 4.x: 变量通过 prob.add_variable 创建)
    prob = pulp.LpProblem("ReefTriage_Budget", pulp.LpMaximize)
    x = [prob.add_variable(f"x_{i}", cat="Binary") for i in range(n)]

    # 目标: max Σ x_i * eff_gain_i
    prob += pulp.lpSum(x[i] * eff_gains[i] for i in range(n)), "TotalExpectedGain"

    # 约束: Σ x_i * cost_i <= budget
    prob += pulp.lpSum(x[i] * costs[i] for i in range(n)) <= budget, "Budget"

    # 求解 (CBC 是 PuLP 默认求解器; 4.x 无捆绑时会抛 PulpError -> 贪心回退)
    status_str = "Not Solved"
    try:
        stats = prob.solve()
        # LpSolveStats / 旧版 LpStatus 都尽量兼容
        status_str = getattr(stats, "status", None) or "Optimal"
        if not isinstance(status_str, str):
            status_str = str(status_str)
    except Exception:
        # 没有可用求解器 (如 PuLP 4.x 未捆绑 CBC) -> 贪心回退
        return greedy_optimize(segments, budget, unit_cost)

    selected_idx = []
    for i in range(n):
        try:
            v = x[i].value()
        except Exception:
            v = None
        if v is not None and v > 0.5:
            selected_idx.append(i)

    if not selected_idx:
        # 任何单项都装不下 (或数值异常) -> 贪心回退再试一次
        return greedy_optimize(segments, budget, unit_cost)

    total_cost = sum(costs[i] for i in selected_idx)
    total_gain = sum(eff_gains[i] for i in selected_idx)

    details = []
    for i in selected_idx:
        seg = segments[i]
        details.append({
            "segment_id": seg.get("segment_id", "?"),
            "name": seg.get("name", ""),
            "cost": round(costs[i], 2),
            "cost_source": cost_sources[i],
            "expected_gain": round(gains[i], 6),
            "amplifier": round(amps[i], 6),
            "score": round(eff_gains[i], 6),
        })

    return {
        "selected": [segments[i].get("segment_id", "?") for i in selected_idx],
        "total_cost": round(total_cost, 2),
        "total_gain": round(total_gain, 6),
        "budget_used_pct": round((total_cost / budget * 100.0) if budget > 0 else 0.0, 2),
        "details": details,
        "method": "ip",
        "solver_status": status_str,
    }
