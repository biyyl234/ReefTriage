"""
app/scoring/rubric.py
=====================
Jev / Laya 评分 Rubric 构造。

把一个礁段的特征打包成 Laya 的 state + questions。
Rubric 用英文写 (Laya 训练语料以英文为主), 注释用中文。

输入特征 (每个礁段):
  - current_dhw             当前热压力 (Degree Heating Weeks, °C·week)
  - max_dhw_5yr             近 5 年最大 DHW
  - mean_depth              平均水深 (m)
  - distance_to_dive_site   到最近热门潜点距离 (km)
  - connectivity_score      礁体连通性 (1-5)
  - rhi_score               CoralCore RHI (0-100)
  - reef_area               礁体面积 (km²)
  - historical_mortality    历史白化死亡率 (%, 可空/NaN)

输出:
  q1 priority_score  : score 类型, 0-100 恢复优先级
  q2 priority_class  : choice 类型, Invest / Monitor / Deprioritize
"""

from __future__ import annotations
from typing import Any, Dict


# 特征字段名常量, 避免拼写不一致
FEATURE_FIELDS = (
    "segment_id", "name", "lat", "lon",
    "current_dhw", "max_dhw_5yr", "mean_depth",
    "distance_to_dive_site", "connectivity_score",
    "rhi_score", "reef_area", "historical_mortality",
)


def build_state(features: Dict[str, Any]) -> Dict[str, Any]:
    """
    把礁段特征转成 Laya state。
    Laya 的 state 可以是任意 JSON 对象; 这里用英文键, 数值原样传入。
    """
    state: Dict[str, Any] = {
        "segment_id": features.get("segment_id", "unknown"),
        "reef_segment_name": features.get("name", "unnamed"),
        "thermal_stress": {
            "current_dhw_cw": features.get("current_dhw"),        # °C·weeks, NOAA CRW
            "max_dhw_5yr_cw": features.get("max_dhw_5yr"),
        },
        "geography": {
            "mean_depth_m": features.get("mean_depth"),
            "distance_to_nearest_popular_dive_site_km": features.get("distance_to_dive_site"),
            "reef_area_km2": features.get("reef_area"),
        },
        "biophysical": {
            "connectivity_score_1to5": features.get("connectivity_score_1to5", features.get("connectivity_score")),
            "coralcore_rhi_0to100": features.get("rhi_score"),
            "historical_bleaching_mortality_pct": features.get("historical_mortality"),
        },
    }
    return state


def build_questions() -> Dict[str, Any]:
    """
    构造发给 Laya 的 questions。两个问题一次前向传播。
    """
    return {
        "priority_score": {
            "type": "score",
            "instructions": (
                "You are a coral reef restoration prioritization analyst for the "
                "Semporna (Sabah, Malaysia) region. Given a reef segment's thermal "
                "stress, depth, tourism value (proxied by distance to the nearest "
                "popular dive site), larval connectivity, CoralCore Reef Health Index "
                "(RHI), reef area, and historical bleaching mortality, rate its "
                "RESTORATION PRIORITY on an ordinal scale where: "
                "0 = 'do not invest (deprioritize)', "
                "1 = 'monitor only, low priority', "
                "2 = 'medium priority, opportunistic investment', "
                "3 = 'high priority, invest this season', "
                "4 = 'critical priority, invest immediately'. "
                "The score must reflect the COST-EFFECTIVENESS of restoration, NOT "
                "just vulnerability. "
                "Heuristics: high current DHW (>4 °C·wk) and shallow water (<10 m) "
                "are vulnerable but also cheap and fast to restore; proximity to "
                "popular dive sites raises tourism co-benefits; high connectivity "
                "(4-5) means natural larval replenishment amplifies restoration "
                "returns; a mid-range RHI (40-70) signals a reef that is degraded "
                "but not yet dead and therefore responds best to intervention; "
                "extremely high historical mortality (>60%) combined with low "
                "connectivity (<2.5) means the reef is unlikely to recover even "
                "with funding — deprioritize it."
            ),
            "criteria": [
                "deprioritize: dead or unrecoverable, low return on investment",
                "monitor: stable or recovering naturally, no urgent intervention",
                "medium: degraded but recoverable, moderate cost-effectiveness",
                "high: threatened with high recovery potential and tourism value",
                "critical: immediate bleaching threat, high connectivity and tourism value",
            ],
        },
        "priority_class": {
            "type": "choice",
            "instructions": (
                "Classify this reef segment into one restoration action tier. "
                "Use the same cost-effectiveness logic as the priority score."
            ),
            "criteria": {
                "invest": (
                    "Fund active restoration this season: outplanting, coral nurseries, "
                    "shading during heat stress. High priority_score (>=3)."
                ),
                "monitor": (
                    "Do not fund active restoration yet; track with regular surveys. "
                    "Medium priority_score (1-2). Intervention may be triggered next season."
                ),
                "deprioritize": (
                    "Do not allocate restoration budget: extremely high past mortality "
                    "and/or low connectivity mean poor returns. Low priority_score (0)."
                ),
            },
        },
    }


def interpret_score(raw_score: float) -> int:
    """把 Laya 返回的有序 score (0..4) 映射到 0-100。"""
    # Laya score 是连续值, 0..4
    return max(0, min(100, int(round(raw_score / 4.0 * 100))))
