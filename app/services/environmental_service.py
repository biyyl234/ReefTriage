"""
app/services/environmental_service.py
======================================
环境数据读取业务逻辑。

封装从 main.py 迁移的环境 / 监测端点：
- GET /api/segments/{id}/environmental
- GET /api/segments/{id}/bleaching-monitoring
- GET /api/environmental/summary

数据来源: data/output/environmental/{id}.json,
         data/output/monitoring/{id}.json
"""

from __future__ import annotations
import os
import json
import logging
from typing import Any, Dict, Optional

from ..scoring.engine import engine
from . import scoring_service

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)
ENV_DIR = os.path.join(PROJECT_ROOT, "data", "output", "environmental")
MONITOR_DIR = os.path.join(PROJECT_ROOT, "data", "output", "monitoring")

os.makedirs(ENV_DIR, exist_ok=True)
os.makedirs(MONITOR_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def _read_json_file(path: str) -> Optional[dict]:
    """安全读取 JSON 文件; 不存在或解析失败返回 None。"""
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


# ---------------------------------------------------------------------------
# 单礁段环境 / 监测
# ---------------------------------------------------------------------------
def get_segment_environmental(segment_id: str) -> Dict[str, Any]:
    """返回该礁段的物理化学环境数据。

    若礁段不存在返回 {"__not_found__": True}; 若环境数据文件缺失则返回
    data_source=unavailable 的占位字典。
    """
    if not scoring_service.segment_exists(segment_id):
        return {"__not_found__": True}

    path = os.path.join(ENV_DIR, f"{segment_id}.json")
    data = _read_json_file(path)
    if data is None:
        return {
            "segment_id": segment_id,
            "data_source": "unavailable",
            "message": "Environmental data not available",
        }
    data.setdefault("segment_id", segment_id)
    data.setdefault("data_source", "unknown")
    return data


def get_bleaching_monitoring(segment_id: str) -> Dict[str, Any]:
    """返回该礁段的白化监测数据。

    若礁段不存在返回 {"__not_found__": True}; 若监测文件缺失则返回
    status=unavailable 的占位字典。
    """
    if not scoring_service.segment_exists(segment_id):
        return {"__not_found__": True}

    path = os.path.join(MONITOR_DIR, f"{segment_id}.json")
    data = _read_json_file(path)
    if data is None:
        return {"segment_id": segment_id, "status": "unavailable"}
    data.setdefault("segment_id", segment_id)
    data.setdefault("status", "ok")
    return data


# ---------------------------------------------------------------------------
# 区域环境摘要
# ---------------------------------------------------------------------------
def get_environmental_summary() -> Dict[str, Any]:
    """返回所有礁段的环境数据摘要 (宏观页面展示用)。"""
    rows = engine.all_scored()
    per_segment: List[Dict[str, Any]] = []
    sst_vals: List[float] = []
    dhw_max_vals: List[float] = []
    ph_vals: List[float] = []
    sources = set()

    for seg in rows:
        sid = seg.get("segment_id")
        path = os.path.join(ENV_DIR, f"{sid}.json")
        edata = _read_json_file(path)
        if edata is None:
            per_segment.append({
                "segment_id": sid,
                "data_source": "unavailable",
                "sst_mean": None,
                "dhw_max": None,
                "ph_mean": None,
            })
            continue

        src = edata.get("data_source", "unknown")
        sources.add(src)
        sst_mean = (edata.get("sst") or {}).get("mean")
        ph_mean = (edata.get("ph") or {}).get("mean")

        dhw_hist = edata.get("dhw_history") or []
        dhw_max = None
        if dhw_hist:
            try:
                dhw_max = max(float(h.get("dhw", 0)) for h in dhw_hist)
            except (TypeError, ValueError):
                dhw_max = None

        if sst_mean is not None:
            sst_vals.append(float(sst_mean))
        if dhw_max is not None:
            dhw_max_vals.append(float(dhw_max))
        if ph_mean is not None:
            ph_vals.append(float(ph_mean))

        per_segment.append({
            "segment_id": sid,
            "data_source": src,
            "sst_mean": sst_mean,
            "dhw_max": dhw_max,
            "ph_mean": ph_mean,
        })

    regional = {
        "avg_sst": round(sum(sst_vals) / len(sst_vals), 2) if sst_vals else None,
        "max_dhw": round(max(dhw_max_vals), 2) if dhw_max_vals else None,
        "min_ph": round(min(ph_vals), 3) if ph_vals else None,
        "data_sources": sorted(sources),
    }
    return {"segments": per_segment, "regional": regional, "count": len(per_segment)}
