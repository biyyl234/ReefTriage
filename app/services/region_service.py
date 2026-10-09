"""
app/services/region_service.py
==============================
Draw-and-Report 区域相交计算服务。

接收前端 leaflet-draw 绘制的几何图形 (多边形 / 矩形 / 圆形),
判断哪些礁段落在该区域内, 并聚合评分 / 决策分类 / 修复成本。

实现要点:
  * 礁段几何用其质心 (lat/lon, 来自 scored_segments.json) 代表;
  * 多边形 / 矩形用射线法 (ray-casting) 做点在多边形内判断;
  * 圆形用 haversine 距离判断质心到圆心是否 <= radius (米);
  * 不引入 shapely 等重依赖, 纯标准库实现。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from ..scoring.engine import engine


# ---------------------------------------------------------------------------
# 几何判断
# ---------------------------------------------------------------------------
def _point_in_ring(lon: float, lat: float, ring: List[List[float]]) -> bool:
    """射线法判断 (lon, lat) 是否在 ring 内。

    ring: [[lon, lat], ...] (GeoJSON Polygon exterior 顺序)。
    """
    n = len(ring)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        # 跨射线判断
        if ((yi > lat) != (yj > lat)):
            x_intersect = (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
            if lon < x_intersect:
                inside = not inside
        j = i
    return inside


def _haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """两点间大圆距离 (米)。"""
    R = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _geometry_contains(
    lon: float,
    lat: float,
    geom_type: str,
    coordinates: Any,
    circle_center: Optional[List[float]] = None,
    circle_radius_m: Optional[float] = None,
) -> bool:
    """统一入口: 判断质心是否在用户绘制几何内。"""
    if geom_type == "polygon" or geom_type == "rectangle":
        # coordinates: [[[lon,lat],...]] (GeoJSON Polygon) 或 [[lon,lat],...]
        if coordinates and isinstance(coordinates[0], list) and coordinates[0] and isinstance(coordinates[0][0], list):
            ring = coordinates[0]
        else:
            ring = coordinates
        return _point_in_ring(lon, lat, ring)

    if geom_type == "circle":
        if circle_center is None or circle_radius_m is None:
            return False
        c_lon, c_lat = circle_center[0], circle_center[1]
        return _haversine_m(lon, lat, c_lon, c_lat) <= float(circle_radius_m)

    return False


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------
def find_intersecting_segments(
    polygon_coords: Any,
    geom_type: str = "polygon",
    circle_center: Optional[List[float]] = None,
    circle_radius_m: Optional[float] = None,
) -> Dict[str, Any]:
    """查找与绘制区域相交 / 被其包含的礁段。

    Parameters
    ----------
    polygon_coords :
        多边形坐标, GeoJSON Polygon coordinates 形式 (嵌套列表)。
    geom_type :
        "polygon" | "rectangle" | "circle"。
    circle_center :
        circle 时的圆心 [lon, lat]。
    circle_radius_m :
        circle 时的半径 (米)。

    Returns
    -------
    dict  with keys: intersecting_segments, count, summary, segments
    """
    rows = engine.all_scored()

    hits: List[Dict[str, Any]] = []
    for row in rows:
        try:
            lon = float(row.get("lon"))
            lat = float(row.get("lat"))
        except (TypeError, ValueError):
            continue
        if not (isinstance(lon, float) and isinstance(lat, float)):
            continue
        if _geometry_contains(lon, lat, geom_type, polygon_coords, circle_center, circle_radius_m):
            hits.append(row)

    # ---- summary ----
    ids = [r["segment_id"] for r in hits]
    scores = [float(r.get("score", 0)) for r in hits]
    invest = sum(1 for r in hits if r.get("choice") == "invest")
    monitor = sum(1 for r in hits if r.get("choice") == "monitor")
    total_cost = 0.0
    for r in hits:
        plan = r.get("restoration_plan") or {}
        # 允许 restoration_plan.total_cost 或顶层 total_cost
        c = plan.get("total_cost") or r.get("total_cost") or 0
        try:
            total_cost += float(c)
        except (TypeError, ValueError):
            pass

    summary = {
        "avg_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
        "invest_count": invest,
        "monitor_count": monitor,
        "total_restoration_cost": round(total_cost, 2),
    }

    # 简要信息列表 (避免把整段 geometry 都返回)
    seg_brief = []
    for r in hits:
        plan = r.get("restoration_plan") or {}
        seg_brief.append({
            "segment_id": r.get("segment_id"),
            "name": r.get("name"),
            "name_zh": r.get("name_zh") or r.get("name"),
            "lat": r.get("lat"),
            "lon": r.get("lon"),
            "score": r.get("score"),
            "choice": r.get("choice"),
            "reef_area_km2": r.get("reef_area_km2"),
            "restoration_cost": plan.get("total_cost", 0),
        })

    return {
        "intersecting_segments": ids,
        "count": len(ids),
        "summary": summary,
        "segments": seg_brief,
    }
