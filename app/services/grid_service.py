"""
app/services/grid_service.py
============================
NOAA CRW 5km 网格热力图服务。

从 data/processed/crw_current.nc 读取最新时间步的 DHW / SST,
为每个有效海洋格点派生白化风险 (0-100) 与修复成本 (USD),
并支持在用户绘制的多边形 / 圆形区域内统计网格指标 + 礁段恢复建议。

缓存策略: netCDF 只读一次, 全部格点 + 派生指标常驻内存。
"""

from __future__ import annotations

import math
import os
import logging
from typing import Any, Dict, List, Optional

import netCDF4
import numpy as np

from ..scoring.engine import engine
from . import region_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
NC_PATH = os.path.join(PROJECT_ROOT, "data", "processed", "crw_current.nc")

CELL_AREA_KM2 = 25.0          # 5km x 5km 格点面积
DEFAULT_UNIT_COST = 160_000.0 # USD/km^2, 发展中国家常规修复成本
MAX_NEAREST_KM = 50.0         # 最近礁段超过此距离则用区域平均
DHW_EXTREME = 8.0             # 8 DHW = 极端白化 = 风险 100

# 模块级缓存
_grid_cache: Optional[List[Dict[str, Any]]] = None
_unit_cost_cache: Optional[float] = None   # 区域平均单位成本 (USD/km^2)


# ---------------------------------------------------------------------------
# 距离工具
# ---------------------------------------------------------------------------
def _haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    R = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _seg_unit_cost(seg: Dict[str, Any]) -> Optional[float]:
    """从礁段 restoration_plan.total_cost / reef_area_km2 得到单位成本 USD/km^2。
    无数据返回 None。"""
    plan = seg.get("restoration_plan") or {}
    total = plan.get("total_cost") or seg.get("total_cost")
    area = seg.get("reef_area_km2")
    try:
        total = float(total) if total is not None else None
        area = float(area) if area is not None else None
    except (TypeError, ValueError):
        return None
    if total and area and area > 0:
        return total / area
    return None


def _compute_region_avg_unit_cost(segments: List[Dict[str, Any]]) -> float:
    """所有礁段中能算出单位成本的取平均; 一个都没有则用默认值。"""
    vals = [c for c in (_seg_unit_cost(s) for s in segments) if c]
    if vals:
        return sum(vals) / len(vals)
    return DEFAULT_UNIT_COST


# ---------------------------------------------------------------------------
# 数据加载
# ---------------------------------------------------------------------------
def load_grid_data() -> List[Dict[str, Any]]:
    """读取 crw_current.nc 最后时间步, 返回所有有效海洋格点。

    每点: {lat, lon, dhw, sst, risk, cost}
      risk: min(100, dhw/8*100)
      cost: 该 5km 格点的修复总成本 USD = 单位成本 * 25 km^2
    """
    global _grid_cache
    if _grid_cache is not None:
        return _grid_cache

    if not os.path.exists(NC_PATH):
        logger.error("CRW netCDF not found: %s", NC_PATH)
        _grid_cache = []
        return _grid_cache

    segments = engine.all_scored()
    global _unit_cost_cache
    _unit_cost_cache = _compute_region_avg_unit_cost(segments)

    ds = netCDF4.Dataset(NC_PATH)
    try:
        lats = np.ma.filled(ds.variables["latitude"][:], np.nan).astype(float)
        lons = np.ma.filled(ds.variables["longitude"][:], np.nan).astype(float)
        # .filled(np.nan) 把 masked (陆地) 位置变成 NaN, 便于过滤
        dhw = np.ma.filled(ds.variables["CRW_DHW"][-1, :, :], np.nan).astype(float)
        sst = np.ma.filled(ds.variables["CRW_SST"][-1, :, :], np.nan).astype(float)
    finally:
        ds.close()

    # 礁段 (lat, lon, unit_cost)
    seg_list: List[Dict[str, Any]] = []
    for s in segments:
        try:
            lat = float(s.get("lat"))
            lon = float(s.get("lon"))
        except (TypeError, ValueError):
            continue
        seg_list.append({
            "lat": lat, "lon": lon,
            "unit_cost": _seg_unit_cost(s),
        })

    out: List[Dict[str, Any]] = []
    n_lat, n_lon = dhw.shape
    for i in range(n_lat):
        for j in range(n_lon):
            d = float(dhw[i, j])
            s = float(sst[i, j])
            # 跳过 masked->NaN (陆地) 或异常填充值
            if np.isnan(d) or np.isnan(s) or d < -100 or s < -100:
                continue
            lat = float(lats[i])
            lon = float(lons[j])
            risk = min(100.0, d / DHW_EXTREME * 100.0)

            # 找最近礁段
            unit_cost = None
            best_km = None
            for sg in seg_list:
                dist = _haversine_km(lon, lat, sg["lon"], sg["lat"])
                if best_km is None or dist < best_km:
                    best_km = dist
                    if sg["unit_cost"] is not None:
                        unit_cost = sg["unit_cost"]
            # 最近礁段 >50km 或无成本数据 -> 区域平均 / 默认
            if unit_cost is None or (best_km is not None and best_km > MAX_NEAREST_KM):
                unit_cost = _unit_cost_cache

            cost = unit_cost * CELL_AREA_KM2
            out.append({
                "lat": round(lat, 4),
                "lon": round(lon, 4),
                "dhw": round(d, 2),
                "sst": round(s, 2),
                "risk": round(risk, 1),
                "cost": round(cost, 0),
            })

    _grid_cache = out
    logger.info("Loaded %d valid ocean grid cells (avg unit cost $%.0f/km2)",
                len(out), _unit_cost_cache)
    return _grid_cache


def invalidate_cache() -> None:
    """数据刷新后调用以强制重读 netCDF。"""
    global _grid_cache
    _grid_cache = None


# ---------------------------------------------------------------------------
# 区域内统计
# ---------------------------------------------------------------------------
def grid_stats_in_polygon(
    polygon_coords: Any,
    geom_type: str = "polygon",
    circle_center: Optional[List[float]] = None,
    circle_radius_m: Optional[float] = None,
) -> Dict[str, Any]:
    """计算用户绘制区域内的网格统计 + 礁段建议。

    Returns
    -------
    {
      grid_stats: {grid_count, avg_dhw, max_dhw, high_risk_pct,
                   avg_cost_per_cell, total_cost},
      reef_segments: [...top scored...],
      recommendations: [top 3 优先恢复礁段]
    }
    """
    cells = load_grid_data()
    inside: List[Dict[str, Any]] = []
    for c in cells:
        if region_service._geometry_contains(
            c["lon"], c["lat"], geom_type, polygon_coords,
            circle_center, circle_radius_m,
        ):
            inside.append(c)

    if inside:
        dhws = [c["dhw"] for c in inside]
        costs = [c["cost"] for c in inside]
        high = sum(1 for c in inside if c["risk"] >= 50)
        grid_stats = {
            "grid_count": len(inside),
            "avg_dhw": round(sum(dhws) / len(dhws), 2),
            "max_dhw": round(max(dhws), 2),
            "high_risk_pct": round(high / len(inside) * 100, 1),
            "avg_cost_per_cell": round(sum(costs) / len(costs), 0),
            "total_cost": round(sum(costs), 0),
        }
    else:
        grid_stats = {
            "grid_count": 0, "avg_dhw": 0, "max_dhw": 0,
            "high_risk_pct": 0.0, "avg_cost_per_cell": 0, "total_cost": 0,
        }

    # 礁段相交 (复用现有服务), 按 score 降序
    seg_result = region_service.find_intersecting_segments(
        polygon_coords=polygon_coords,
        geom_type=geom_type,
        circle_center=circle_center,
        circle_radius_m=circle_radius_m,
    )
    segs = seg_result.get("segments", [])
    segs_sorted = sorted(segs, key=lambda r: -(r.get("score") or 0))
    recommendations = segs_sorted[:3]

    return {
        "grid_stats": grid_stats,
        "reef_segments": segs_sorted,
        "recommendations": recommendations,
    }
