"""
app/scoring/data_loader.py
==========================
加载真实数据: 礁段特征 CSV + 连通性 CSV + GeoJSON 几何 + CRW netCDF 历史 DHW。
"""

from __future__ import annotations
import os
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

FEATURES_CSV = os.path.join(PROJECT_ROOT, "data", "output", "reef_features.csv")
GEOJSON_PATH = os.path.join(PROJECT_ROOT, "data", "output", "reef_segments.geojson")
CONNECTIVITY_CSV = os.path.join(
    PROJECT_ROOT, "connectivity", "output", "reef_connectivity_features.csv"
)
CRW_NC = os.path.join(PROJECT_ROOT, "data", "processed", "crw_history.nc")
SCORED_JSON = os.path.join(PROJECT_ROOT, "data", "output", "scored_segments.json")


def load_features() -> pd.DataFrame:
    df = pd.read_csv(FEATURES_CSV)
    return df


def load_geojson() -> Dict[str, Any]:
    with open(GEOJSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_connectivity() -> pd.DataFrame:
    df = pd.read_csv(CONNECTIVITY_CSV)
    # reef_id 0-27 -> segment_id R01-R28
    df = df.copy()
    df["segment_id"] = df["reef_id"].apply(lambda i: f"R{int(i)+1:02d}")
    return df


def load_reef_segments() -> List[Dict[str, Any]]:
    """
    合并特征 + 连通性 + 几何, 返回 28 个礁段的字典列表。
    """
    feats = load_features()
    conn = load_connectivity()
    geo = load_geojson()

    # 连通性合并 (按 segment_id)
    conn_cols = ["segment_id", "larval_input", "larval_output",
                 "self_retention", "connectivity_score", "total_settlements"]
    df = feats.merge(conn[conn_cols], on="segment_id", how="left")

    # 几何合并
    geom_map = {f["properties"]["segment_id"]: f["geometry"]
                for f in geo["features"]}

    out: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        d = row.to_dict()
        sid = d["segment_id"]
        d["geometry"] = geom_map.get(sid)
        # 连通性评分原始是 0-1, 映射到 1-5 方便 rubric 使用
        cs = d.get("connectivity_score", 0.0) or 0.0
        d["connectivity_score_1to5"] = round(1.0 + float(cs) * 4.0, 2)
        out.append(d)
    logger.info("Loaded %d real reef segments", len(out))
    return out


# ---------------------------------------------------------------------------
# CRW netCDF 历史 DHW 提取
# ---------------------------------------------------------------------------
def _nearest_grid(lat: float, lon: float,
                  lats: np.ndarray, lons: np.ndarray) -> Tuple[int, int]:
    ilat = int(np.argmin(np.abs(lats - lat)))
    ilon = int(np.argmin(np.abs(lons - lon)))
    return ilat, ilon


def extract_dhw_at_period(
    year: int, month_start: int, month_end: int
) -> Dict[str, float]:
    """
    提取指定年份 month_start..month_end 期间, 每个礁段位置的最大 DHW。
    返回 {segment_id: max_dhw}
    """
    import netCDF4 as nc
    ds = nc.Dataset(CRW_NC)
    t = ds.variables["time"][:]
    lats = ds.variables["latitude"][:]
    lons = ds.variables["longitude"][:]
    dhw = ds.variables["CRW_DHW"][:]  # (time, lat, lon)
    dates = nc.num2date(t, ds.variables["time"].units)

    mask = np.array([
        d.year == year and month_start <= d.month <= month_end
        for d in dates
    ])
    if mask.sum() == 0:
        ds.close()
        return {}

    period_max = np.nanmax(dhw[mask], axis=0)  # (lat, lon)

    segs = load_reef_segments()
    out: Dict[str, float] = {}
    for s in segs:
        ilat, ilon = _nearest_grid(s["lat"], s["lon"], lats, lons)
        v = period_max[ilat, ilon]
        out[s["segment_id"]] = float(v) if not np.isnan(v) else 0.0
    ds.close()
    return out
