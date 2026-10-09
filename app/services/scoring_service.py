"""
app/services/scoring_service.py
================================
评分相关业务逻辑。

封装从 main.py 迁移的所有评分 / 模型 / 优化 / 连通性端点逻辑：
- 健康检查、统计、礁段列表与详情、更新
- 预算优先名单、整数规划优化
- 模型权重 / 对比 / ML 信息 / 回测
- 连通性矩阵读取
- 重新评分触发

本模块不做任何 HTTP 相关假设，便于单元测试与复用。
"""

from __future__ import annotations
import os
import json
import logging
from typing import Any, Dict, List, Optional

from ..scoring.engine import engine
from ..scoring import optimizer
from . import filter_service

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def segment_exists(segment_id: str) -> bool:
    """检查 segment_id 是否存在于 scored_segments。"""
    return any(s.get("segment_id") == segment_id for s in engine.all_scored())


# ---------------------------------------------------------------------------
# 健康 / 统计
# ---------------------------------------------------------------------------
def get_health() -> Dict[str, Any]:
    """返回后端健康状态字典 (供 HealthStatus 模型使用)。"""
    return engine.health()


def get_stats() -> Dict[str, Any]:
    """返回礁段统计: 总数 / 三类决策计数 / 平均分 / laya 模式。"""
    rows = engine.all_scored()
    invest = sum(1 for r in rows if r["choice"] == "invest")
    monitor = sum(1 for r in rows if r["choice"] == "monitor")
    deprior = sum(1 for r in rows if r["choice"] == "deprioritize")
    avg = round(sum(r["score"] for r in rows) / max(1, len(rows)), 1)
    return {
        "total_segments": len(rows),
        "invest_count": invest,
        "monitor_count": monitor,
        "deprioritize_count": deprior,
        "avg_score": avg,
        "laya_mode": engine.laya_mode,
    }


# ---------------------------------------------------------------------------
# 礁段列表 / 详情 / 更新
# ---------------------------------------------------------------------------
def list_segments(params: Dict[str, Any]) -> Dict[str, Any]:
    """按查询参数筛选礁段, 按 score 降序返回。

    params 键见 filter_service.filter_segments 文档。
    """
    rows = engine.all_scored()
    rows = filter_service.filter_segments(rows, params)
    rows.sort(key=lambda x: -x["score"])
    return {"segments": rows, "count": len(rows)}


def get_segment_detail(segment_id: str) -> Optional[Dict[str, Any]]:
    """返回单个礁段完整记录; 不存在返回 None。"""
    for r in engine.all_scored():
        if r.get("segment_id") == segment_id:
            return r
    return None


def update_segment(segment_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """更新礁段字段并持久化; 不存在返回 None。"""
    return engine.update_segment(segment_id, updates)


def get_filters_meta() -> Dict[str, Any]:
    """返回可用筛选选项与数值范围。"""
    rows = engine.all_scored()
    return filter_service.filters_meta(rows)


# ---------------------------------------------------------------------------
# 预算优先名单 / 整数规划
# ---------------------------------------------------------------------------
def get_priority(budget: float, unit_cost: float) -> Dict[str, Any]:
    """预算约束下的优先名单: 按 score 降序取 top N (旧版简单 top-N)。"""
    from ..models.reef import PriorityResponse, PriorityItem

    rows = engine.all_scored()
    rows.sort(key=lambda x: -x["score"])
    affordable = max(0, int(budget // unit_cost))
    chosen = rows[:affordable]
    items = [
        PriorityItem(
            segment_id=r["segment_id"],
            name=r["name"],
            name_zh=r.get("name_zh"),
            score=r["score"],
            choice=r["choice"],
            lat=r["lat"],
            lon=r["lon"],
            cost_estimate=unit_cost,
        )
        for r in chosen
    ]
    return PriorityResponse(
        budget=budget,
        unit_cost=unit_cost,
        funded_count=len(items),
        total_cost=len(items) * unit_cost,
        items=items,
    ).model_dump()


def optimize_budget(budget: float, unit_cost: float) -> Dict[str, Any]:
    """预算约束整数规划优化 (模型B)。"""
    rows = engine.all_scored()
    result = optimizer.optimize_budget(rows, budget, unit_cost)
    return {
        "budget": budget,
        "unit_cost": unit_cost,
        "method": result.get("method", "unknown"),
        "selected_count": len(result.get("selected", [])),
        "total_cost": result.get("total_cost", 0),
        "total_gain": result.get("total_gain", 0),
        "budget_used_pct": result.get("budget_used_pct", 0),
        "selected": result.get("details", []),
    }


# ---------------------------------------------------------------------------
# 模型信息
# ---------------------------------------------------------------------------
def get_model_weights() -> Dict[str, Any]:
    """返回熵权法特征权重 (模型A)。"""
    return engine.model_weights()


def get_model_compare() -> Dict[str, Any]:
    """新旧模型评分对比。"""
    return engine.model_compare()


def get_feature_contribution(segment_id: str) -> Optional[Dict[str, Any]]:
    """单个礁段的特征贡献度分解 (SHAP 风格瀑布, 供 /api/model/feature-contribution)。

    可解释性近似: TOPSIS 是相对距离法而非线性加权, 这里用"方向调整归一化值
    偏离中性 0.5"来近似每个特征对最终分的推拉作用。

    分解 (以中性基准 50 为起点):
      基准中性分            = 50
      特征 i 贡献            = α · w_i · (z_i - 0.5) · 100
          - z_i : 方向调整后极差归一化值 (0-1, 越大越优先), 跨全部 28 礁段拟合
          - w_i : 熵权法客观权重
          - 正贡献 = 该特征高于中性, 推高优先级; 负贡献 = 拉低优先级
      Laya AI 判断贡献       = (1-α) · (laya_score - 50)
      TOPSIS 非线性残差       = final_score - (50 + Σ特征 + Laya)
          吸收 TOPSIS 距离法与线性加权的偏差, 保证瀑布终点 = final_score
    """
    from ..scoring import config, mcdm

    rows = engine.all_scored()
    idx = next((i for i, r in enumerate(rows) if r.get("segment_id") == segment_id), None)
    if idx is None:
        return None

    # 跨全部礁段拟合归一化基准 + 熵权 (与 mcdm_score 计算口径一致)
    X, keys = mcdm._extract_matrix(rows)
    Z = mcdm._directional_minmax(X)
    weights = mcdm.entropy_weights(rows)

    target = rows[idx]
    z_row = Z[idx]

    alpha = float(target.get("alpha") or config.FUSION_ALPHA_DEFAULT)
    laya_score = float(target.get("laya_score", 50) or 50)
    mcdm_score = float(target.get("mcdm_score", 0) or 0)
    final_score = float(target.get("final_score", target.get("score", 0)) or 0)

    feat_meta = {f["key"]: f for f in config.MCDM_FEATURES}
    features = []
    feat_sum = 0.0
    for j, key in enumerate(keys):
        z = float(z_row[j])
        w = float(weights.get(key, 0.0))
        contrib = alpha * w * (z - 0.5) * 100.0
        meta = feat_meta.get(key, {})
        features.append({
            "key": key,
            "label": meta.get("label", key),
            "direction": meta.get("direction", "+"),
            "weight": round(w, 4),
            "norm_z": round(z, 3),
            "raw": target.get(key),
            "contribution": round(contrib, 2),
        })
        feat_sum += contrib

    laya_contrib = (1.0 - alpha) * (laya_score - 50.0)
    baseline = 50.0
    running = baseline + feat_sum + laya_contrib
    residual = final_score - running

    return {
        "segment_id": segment_id,
        "name": target.get("name"),
        "name_zh": target.get("name_zh") or target.get("name"),
        "choice": target.get("choice"),
        "mcdm_score": round(mcdm_score, 1),
        "laya_score": round(laya_score, 1),
        "final_score": round(final_score, 1),
        "score": target.get("score"),
        "alpha": alpha,
        "baseline": baseline,
        "features": features,
        "feature_sum": round(feat_sum, 2),
        "laya_contribution": round(laya_contrib, 2),
        "residual": round(residual, 2),
        "total": round(final_score, 1),
    }


def get_ml_info() -> Dict[str, Any]:
    """ML 白化预测器信息 (模型C)。"""
    return engine.ml_model_info()


def recalc() -> Dict[str, Any]:
    """触发重新评分。"""
    return engine.recalc()


# ---------------------------------------------------------------------------
# 连通性矩阵 / 回测 (文件读取)
# ---------------------------------------------------------------------------
def get_connectivity_matrix() -> Dict[str, Any]:
    """读取 28×28 幼虫连通性矩阵 CSV。"""
    import pandas as pd

    matrix_path = os.path.join(
        PROJECT_ROOT, "connectivity", "output", "connectivity_matrix.csv"
    )
    if not os.path.exists(matrix_path):
        return {"error": "connectivity matrix not found"}
    df = pd.read_csv(matrix_path)
    names = df["from_reef"].tolist()
    matrix = df.drop(columns=["from_reef"]).values.tolist()
    return {"nodes": names, "matrix": matrix}


def get_backtest() -> Any:
    """读取回测结果 JSON。"""
    bt_path = os.path.join(
        PROJECT_ROOT, "data", "output", "backtest_results.json"
    )
    if not os.path.exists(bt_path):
        return {"error": "backtest results not found"}
    with open(bt_path, encoding="utf-8") as f:
        return json.load(f)
