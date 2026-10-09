"""
app/services/restoration_service.py
====================================
修复成本配置读写业务逻辑。

封装从 main.py 迁移的修复成本端点：
- GET  /api/segments/{id}/restoration-cost
- POST /api/segments/{id}/restoration-cost

数据持久化: scored_segments.json 的 restoration_plan 字段 (via engine.update_segment)。
"""

from __future__ import annotations
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from ..scoring.engine import engine
from . import scoring_service

logger = logging.getLogger(__name__)

# 修复成本默认配置 (无 restoration_plan 时返回)
DEFAULT_RESTORATION_PLAN: Dict[str, Any] = {
    "method": "coral_gardening",
    "area_m2": 1000,
    "survival_rate": 0.7,
    "coral_density": 50,
    "total_cost": 0,
    "cost_breakdown": {"materials": 0, "labor": 0, "equipment": 0,
                       "monitoring": 0, "maintenance": 0},
    "cost_per_coral": 0,
    "last_updated": None,
}


def get_restoration_cost(segment_id: str) -> Dict[str, Any]:
    """返回该礁段的修复成本配置。

    若礁段不存在返回 {"__not_found__": True}; 若无已保存 plan 则返回默认值。
    """
    rows = engine.all_scored()
    seg = next((r for r in rows if r.get("segment_id") == segment_id), None)
    if seg is None:
        return {"__not_found__": True}

    plan = seg.get("restoration_plan")
    out = dict(DEFAULT_RESTORATION_PLAN)
    if plan:
        out.update(plan)
    out["segment_id"] = segment_id
    return out


def save_restoration_cost(segment_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """保存修复成本配置到 scored_segments.json 的 restoration_plan 字段。

    payload 字段对应 RestorationCostInput 模型。
    若礁段不存在返回 {"__not_found__": True}。
    """
    if not scoring_service.segment_exists(segment_id):
        return {"__not_found__": True}

    plan = {
        "method": payload["method"],
        "area_m2": payload["area_m2"],
        "survival_rate": payload["survival_rate"],
        "coral_density": payload["coral_density"],
        "total_cost": payload["total_cost"],
        "cost_breakdown": payload["cost_breakdown"],
        "cost_per_coral": payload["cost_per_coral"],
        "last_updated": datetime.now().isoformat(timespec="seconds"),
    }
    result = engine.update_segment(segment_id, {"restoration_plan": plan})
    if result is None:
        return {"__not_found__": True}

    saved = dict(DEFAULT_RESTORATION_PLAN)
    saved.update(result.get("restoration_plan", {}))
    saved["segment_id"] = segment_id
    return {"status": "ok", "restoration_plan": saved}
