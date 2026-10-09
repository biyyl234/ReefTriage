"""
app/services/metadata_service.py
=================================
静态数据层元数据服务。

返回 ReefTriage 系统使用的所有数据层 / 模型方法学元数据,
供 GET /api/metadata 与前端 metadata.html / micro.html 数据来源标签使用。

元数据为硬编码静态字典, 不访问数据库。
"""

from __future__ import annotations
from typing import Dict, List


LAYERS: List[Dict] = [
    {
        "id": "noaa_crw_dhw",
        "name": "NOAA Coral Reef Watch DHW / SST",
        "name_zh": "NOAA 珊瑚礁观测网 度热周 / 海表温度",
        "description": (
            "Degree Heating Week (DHW) 5km 卫星产品, 衡量珊瑚热压力累积; "
            "同时提供逐日海表温度 SST, 用于白化概率、热压力诊断与历史回溯。"
        ),
        "description_zh": (
            "度热周 (DHW) 5km 卫星产品, 衡量珊瑚热压力累积; "
            "同时提供逐日海表温度 SST, 用于白化概率、热压力诊断与历史回溯。"
        ),
        "source": "NOAA Coral Reef Watch v3.1 (5km Daily Virtual Station)",
        "source_url": "https://coralreefwatch.noaa.gov/",
        "time_range": "2020-01 to 2025-12",
        "spatial_resolution": "5 km",
        "temporal_resolution": "daily",
        "variables": ["DHW", "SST", "SST_anomaly", "BAA"],
        "uncertainty": "±0.5°C for SST; DHW derived from SST anomaly above bleaching threshold",
        "citation": (
            "NOAA Coral Reef Watch (2024). 5km Satellite Coral Bleaching "
            "Monitoring Products, Version 3.1. NOAA/NESDIS."
        ),
        "license": "Public Domain (NOAA/U.S. Government work)",
        "used_for": ["bleaching_probability", "thermal_stress", "dhw_history", "baa_level"],
    },
    {
        "id": "etopo_depth",
        "name": "ETOPO Bathymetry",
        "name_zh": "ETOPO 全球水深地形",
        "description": (
            "ETOPO 1-arc-second 全球地形/水深数据, 提供礁段平均水深 (mean_depth), "
            "用于珊瑚光照、波浪衰减与修复可行性评估。"
        ),
        "description_zh": (
            "ETOPO 1 弧秒全球地形/水深数据, 提供礁段平均水深 (mean_depth), "
            "用于珊瑚光照、波浪衰减与修复可行性评估。"
        ),
        "source": "NOAA National Centers for Environmental Information — ETOPO 2022",
        "source_url": "https://www.ncei.noaa.gov/products/etopo-global-relief-model",
        "time_range": "static (2022 release)",
        "spatial_resolution": "1 arc-second (~30 m)",
        "temporal_resolution": "static",
        "variables": ["depth", "mean_depth", "slope"],
        "uncertainty": "±10 m over shelf; higher uncertainty in steep reef slopes",
        "citation": (
            "NOAA NCEI (2022). ETOPO 2022 1 Arc-Minute Global Relief Model. "
            "NOAA Technical Memorandum NESDIS NGDC."
        ),
        "license": "Public Domain (NOAA)",
        "used_for": ["depth_feature", "restoration_feasibility", "light_attenuation"],
    },
    {
        "id": "osm_dive_sites",
        "name": "OpenStreetMap Dive Sites",
        "name_zh": "OpenStreetMap 潜点数据",
        "description": (
            "OpenStreetMap 上由社区标注的潜水点 (tourism=diving), "
            "用于计算每个礁段到最近潜点的距离 distance_to_nearest_dive_site_km, "
            "作为人为压力与旅游可达性代理变量。"
        ),
        "description_zh": (
            "OpenStreetMap 上由社区标注的潜水点 (tourism=diving), "
            "用于计算每个礁段到最近潜点的距离 distance_to_nearest_dive_site_km, "
            "作为人为压力与旅游可达性代理变量。"
        ),
        "source": "OpenStreetMap contributors (Overpass API)",
        "source_url": "https://www.openstreetmap.org/",
        "time_range": "as of 2025-06 snapshot",
        "spatial_resolution": "point features (~10 m)",
        "temporal_resolution": "static snapshot",
        "variables": ["distance_to_dive_site", "dive_site_density"],
        "uncertainty": "depends on OSM community mapping density; Semporna area well-covered",
        "citation": (
            "OpenStreetMap contributors (2025). Semporna dive sites layer, "
            "retrieved via Overpass API."
        ),
        "license": "Open Database License (ODbL)",
        "used_for": ["anthropogenic_pressure", "tourism_access", "distance_to_dive_site"],
    },
    {
        "id": "hycom_currents",
        "name": "HYCOM Ocean Currents",
        "name_zh": "HYCOM 混合坐标海洋模式 海流",
        "description": (
            "HYbrid Coordinate Ocean Model (HYCOM) 再分析海流场, "
            "提供表层流速/流向; 当前演示版本采用文献气候态值, "
            "生产环境可切换至 HYCOM Global 1/12° 实时再分析。"
        ),
        "description_zh": (
            "HYbrid Coordinate Ocean Model (HYCOM) 再分析海流场, "
            "提供表层流速/流向; 当前演示版本采用文献气候态值, "
            "生产环境可切换至 HYCOM Global 1/12° 实时再分析。"
        ),
        "source": "HYCOM Consortium — Global Forecast / Reanalysis (demo: literature climatology)",
        "source_url": "https://www.hycom.org/",
        "time_range": "demo: 2020–2024 climatology; HYCOM real-time available",
        "spatial_resolution": "1/12° (~8 km)",
        "temporal_resolution": "3-hourly",
        "variables": ["u_current", "v_current", "speed", "direction"],
        "uncertainty": "demo uses literature-anchored values; HYCOM ±0.1 m/s in coastal zones",
        "citation": (
            "Chassignet, E.P. et al. (2007). The HYCOM (HYbrid Coordinate Ocean Model) "
            "data assimilative system. J. Marine Systems, 65, 60–83."
        ),
        "license": "U.S. Government / HYCOM Consortium (free for research)",
        "used_for": ["current_speed", "larval_dispersal", "connectivity_input"],
    },
    {
        "id": "copernicus_phy_bgc",
        "name": "Copernicus Marine Physics & Biogeochemistry",
        "name_zh": "哥白尼海洋局 物理与生化产品",
        "description": (
            "Copernicus Marine Service GLOBAL_ANALYSIS_FORECAST_PHY_001_024 与 "
            "GLOBAL_ANALYSIS_FORECAST_BGC_001_029 产品, 提供 pH、溶解氧、盐度、叶绿素等。"
            "当前演示因需 CMEMS 账号, 使用热带西太平洋文献气候态值替代。"
        ),
        "description_zh": (
            "Copernicus Marine Service 全球分析预报物理/生化产品, "
            "提供 pH、溶解氧、盐度、叶绿素等。"
            "当前演示因需 CMEMS 账号, 使用热带西太平洋文献气候态值替代。"
        ),
        "source": "EU Copernicus Marine Service (Mercator Ocean)",
        "source_url": "https://marine.copernicus.eu/",
        "time_range": "demo: literature climatology; CMEMS 1993–present reanalysis",
        "spatial_resolution": "1/12° PHY; 1/4° BGC",
        "temporal_resolution": "daily (PHY); monthly (BGC)",
        "variables": ["pH", "DO", "salinity", "chlorophyll_a", "aragonite_saturation"],
        "uncertainty": "demo values are literature-anchored; CMEMS PHY ±0.05 pH, ±0.1 PSU",
        "citation": (
            "Copernicus Marine Service (2024). Global Ocean Physics and "
            "Biogeochemical Analysis & Forecast products."
        ),
        "license": "EU Copernicus — free for registered users (attribution required)",
        "used_for": ["water_quality", "ocean_acidification", "primary_production"],
    },
    {
        "id": "coralcore_rhi",
        "name": "CoralCore Reef Health Index (8-dimension)",
        "name_zh": "CoralCore 珊瑚礁健康指数 8 分量",
        "description": (
            "8 分量综合礁体健康指数: 珊瑚覆盖、大型藻类、鱼类多样性、结构复杂度、"
            "水质、白化抗性、恢复轨迹、人为影响。当前版本为基于文献的模拟值, "
            "生产环境接入礁体监测采样数据。"
        ),
        "description_zh": (
            "8 分量综合礁体健康指数: 珊瑚覆盖、大型藻类、鱼类多样性、结构复杂度、"
            "水质、白化抗性、恢复轨迹、人为影响。当前版本为基于文献的模拟值, "
            "生产环境接入礁体监测采样数据。"
        ),
        "source": "CoralCore RHI framework (literature-anchored demo)",
        "source_url": "https://allencoralatlas.org/",
        "time_range": "demo: 2024–2025 simulated",
        "spatial_resolution": "reef segment (28 polygons)",
        "temporal_resolution": "annual (demo)",
        "variables": [
            "coral_cover", "macroalgae", "fish_diversity", "structural_complexity",
            "water_quality", "bleaching_resistance", "recovery_trajectory",
            "anthropogenic_impact",
        ],
        "uncertainty": "±10 index points (demo simulated); production via field surveys",
        "citation": (
            "Allen Coral Atlas (2021). Global Reef Health Monitoring; "
            "RHI framework adapted from McClanahan et al. (2015) Aichi targets."
        ),
        "license": "Demo/simulated — literature-anchored",
        "used_for": ["rhi_score", "health_assessment", "monitoring_panel"],
    },
    {
        "id": "coral_bleaching_images",
        "name": "Coral Bleaching Reference Image Set (4 classes)",
        "name_zh": "珊瑚白化参考图像集 (4 级)",
        "description": (
            "4 张参考图像 (healthy / mild / moderate / severe), "
            "用于端侧 HSV 颜色分析器比对与 Reef Lab 白化监测面板展示。"
            "演示期素材来自公开图库, 生产环境应替换为 CoralNet / Allen Coral Atlas "
            "授权图像 (见 img/coral/SOURCES.md)。"
        ),
        "description_zh": (
            "4 张参考图像 (健康 / 轻度 / 中度 / 重度), "
            "用于端侧 HSV 颜色分析器比对与 Reef Lab 白化监测面板展示。"
            "演示期素材来自公开图库, 生产环境应替换为 CoralNet / Allen Coral Atlas "
            "授权图像 (见 img/coral/SOURCES.md)。"
        ),
        "source": "Public web (demo) — recommended: CoralNet / Allen Coral Atlas / Wikimedia",
        "source_url": "https://coralnet.ucsd.edu/",
        "time_range": "static reference set",
        "spatial_resolution": "n/a (illustrative photos)",
        "temporal_resolution": "n/a",
        "variables": ["healthy", "mild", "moderate", "severe"],
        "uncertainty": "illustrative only; production requires CC-BY/CC0 licensed imagery",
        "citation": "See app/frontend/img/coral/SOURCES.md for per-image attribution.",
        "license": "Demo — replace with explicitly licensed imagery before production",
        "used_for": ["bleaching_classification", "hsv_analyzer", "monitoring_panel"],
    },
    {
        "id": "connectivity_matrix",
        "name": "Larval Connectivity Matrix",
        "name_zh": "幼虫连通性矩阵",
        "description": (
            "28×28 礁段间幼虫扩散概率矩阵 (connectivity_matrix.csv), "
            "由 HYCOM 海流场 + 幼虫行为模型驱动, 用于连通性网络图与预算优化放大器。"
        ),
        "description_zh": (
            "28×28 礁段间幼虫扩散概率矩阵 (connectivity_matrix.csv), "
            "由 HYCOM 海流场 + 幼虫行为模型驱动, 用于连通性网络图与预算优化放大器。"
        ),
        "source": "ReefTriage larval dispersal model (HYCOM-forced)",
        "source_url": "https://github.com/reeftriage/connectivity",
        "time_range": "2024 climatology",
        "spatial_resolution": "reef-segment pair (28 nodes)",
        "temporal_resolution": "annual / breeding-season integrated",
        "variables": ["from_reef", "to_reef", "probability", "larval_duration"],
        "uncertainty": "model ±20% on probability; sensitive to larval PLD assumptions",
        "citation": (
            "Treml, E.A. et al. (2012). Reproductive output and connectivity of "
            "coral populations across ocean basins. Current Biology, 22, 2113–2119."
        ),
        "license": "ReefTriage internal model output",
        "used_for": ["connectivity_network", "budget_optimization", "restoration_priority"],
    },
    {
        "id": "reef_segments_geojson",
        "name": "Reef Segment Boundaries (28 polygons)",
        "name_zh": "礁段边界多边形 (28 段)",
        "description": (
            "28 个仙本那礁段的多边形矢量边界 (reef_segments.geojson), "
            "作为空间聚合、地图渲染与统计单元。"
        ),
        "description_zh": (
            "28 个仙本那礁段的多边形矢量边界 (reef_segments.geojson), "
            "作为空间聚合、地图渲染与统计单元。"
        ),
        "source": "ReefTriage segmentation (Semporna archipelago)",
        "source_url": "https://data.apps.fao.org/",
        "time_range": "2025 base segmentation",
        "spatial_resolution": "polygons (~0.5–5 km² each)",
        "temporal_resolution": "static",
        "variables": ["segment_id", "name", "name_zh", "geometry", "reef_area_km2"],
        "uncertainty": "segment boundaries delineated from satellite + local dive survey",
        "citation": (
            "ReefTriage (2025). Semporna Reef Segment Boundaries v1.0; "
            "basemap from GEBCO / satellite imagery."
        ),
        "license": "ReefTriage internal",
        "used_for": ["map_rendering", "spatial_aggregation", "zonal_statistics"],
    },
    {
        "id": "scoring_model",
        "name": "Three-layer Scoring Model (ML + MCDM + Laya)",
        "name_zh": "三层评分模型 (ML + MCDM + Laya 融合)",
        "description": (
            "非数据层, 方法学记录: 模型A 熵权 MCDM 加权, 模型B 整数规划预算优化, "
            "模型C ML 白化概率预测, 最终由 Laya 仲裁融合输出优先级与置信度。"
        ),
        "description_zh": (
            "非数据层, 方法学记录: 模型A 熵权 MCDM 加权, 模型B 整数规划预算优化, "
            "模型C ML 白化概率预测, 最终由 Laya 仲裁融合输出优先级与置信度。"
        ),
        "source": "ReefTriage scoring engine (app/scoring/)",
        "source_url": "/static/model.html",
        "time_range": "v1.1.0 (2025)",
        "spatial_resolution": "28 reef segments",
        "temporal_resolution": "weekly recalc",
        "variables": ["entropy_weights", "ml_bleaching_prob", "mcdm_score", "laya_fusion"],
        "uncertainty": "see /api/model/ml-info and /api/model/backtest",
        "citation": (
            "ReefTriage (2025). Three-layer scoring: Entropy-MCDM + Integer-Programming "
            "Budget Optimization + Bayesian/ML bleaching predictor, fused via Laya arbitrator."
        ),
        "license": "ReefTriage internal",
        "used_for": ["priority_scoring", "budget_allocation", "backtest"],
    },
]


def get_metadata() -> Dict:
    """返回全部数据层元数据字典。"""
    return {
        "layers": LAYERS,
        "total_layers": len(LAYERS),
    }


def get_layer_by_id(layer_id: str) -> Dict | None:
    """按 id 查找单个数据层 (供 micro.html 标签弹窗使用)。"""
    for layer in LAYERS:
        if layer["id"] == layer_id:
            return layer
    return None
