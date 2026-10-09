"""
app/main.py
===========
ReefTriage / ReefPulse FastAPI 后端。

启动:
    python -m uvicorn app.main:app --reload --port 8000
或:
    run.bat

本文件只保留: import、app 实例、中间件、Pydantic 请求模型、路由定义。
所有业务逻辑已迁移到 app/services/ 目录下的对应 service 模块。
"""

from __future__ import annotations
import os
import logging
from typing import Optional, List

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse, JSONResponse, RedirectResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .scoring.engine import engine
from .models.reef import (
    HealthStatus, StatsResponse, PriorityResponse,
)
from .services import (
    filter_service,
    scoring_service,
    environmental_service,
    restoration_service,
    sync_service,
    report_service,
    metadata_service,
    region_service,
    data_refresh_service,
    grid_service,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reeftriage")

app = FastAPI(
    title="ReefTriage API",
    description="仙本那珊瑚礁恢复优先级实时三角系统",
    version="1.1.0",
)

# CORS: 允许本地前端开发
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """添加 CSP 头, 允许 NocoBase (:13000) 通过 iframe 嵌入。"""
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "frame-ancestors 'self' http://127.0.0.1:13000 http://localhost:13000"
    )
    response.headers["X-Frame-Options"] = "ALLOW-FROM http://127.0.0.1:13000"
    return response


FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
ADMIN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "admin")


# ---------------------------------------------------------------------------
# Pydantic 请求模型
# ---------------------------------------------------------------------------
class SegmentUpdate(BaseModel):
    """NocoBase 回写的礁段更新字段 (全部可选)。"""
    name: Optional[str] = None
    name_zh: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    current_dhw: Optional[float] = None
    max_dhw_5yr: Optional[float] = None
    mean_depth: Optional[float] = None
    distance_to_nearest_dive_site_km: Optional[float] = None
    connectivity_score: Optional[float] = None
    rhi_score: Optional[float] = None
    reef_area_km2: Optional[float] = None
    score: Optional[int] = None
    choice: Optional[str] = None
    laya_choice: Optional[str] = None
    confidence: Optional[float] = None
    model: Optional[str] = None
    manual_override: Optional[bool] = None


class RestorationCostInput(BaseModel):
    """POST /api/segments/{id}/restoration-cost 请求体。"""
    method: str = "coral_gardening"
    area_m2: float = 1000
    survival_rate: float = 0.7
    coral_density: float = 50
    total_cost: float = 0
    cost_breakdown: dict = {}
    cost_per_coral: float = 0.0


class RegionIntersectRequest(BaseModel):
    """POST /api/region/intersect 请求体。

    type: polygon | rectangle | circle
    polygon / rectangle: coordinates 为 GeoJSON Polygon coordinates ([[[lon,lat],...]]).
    circle: center=[lon,lat], radius=米.
    """
    type: str = "polygon"
    coordinates: Optional[List[List[List[float]]]] = None
    center: Optional[List[float]] = None
    radius: Optional[float] = None


class DataRefreshRequest(BaseModel):
    """POST /api/data-refresh 请求体: 手动触发数据拉取->处理->评分流水线。"""
    sources: Optional[List[str]] = None  # None -> 默认 ["crw","bathymetry","osm"]
    force: bool = True                   # 备份旧产物并强制重新下载


# ---------------------------------------------------------------------------
# 页面 / 静态文件路由
# ---------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
def root():
    """根路径重定向到综合管理系统 admin.html。"""
    return RedirectResponse(url="/static/admin.html")


@app.get("/admin-panel", include_in_schema=False)
def admin_panel():
    """统一管理面板 (供 NocoBase iframe 嵌入)。"""
    return FileResponse(os.path.join(ADMIN_DIR, "panel.html"))


# ---------------------------------------------------------------------------
# API 端点: 健康 / 统计
# ---------------------------------------------------------------------------
@app.get("/api/health", response_model=HealthStatus)
def api_health():
    h = scoring_service.get_health()
    return HealthStatus(**h)


@app.get("/api/stats", response_model=StatsResponse)
def api_stats():
    s = scoring_service.get_stats()
    return StatsResponse(**s)


# ---------------------------------------------------------------------------
# API 端点: 礁段列表 / 筛选 / 详情 / 更新
# ---------------------------------------------------------------------------
@app.get("/api/segments/filters")
def api_segments_filters():
    """返回可用的筛选选项与数值范围 (从实际礁段数据计算)。"""
    return scoring_service.get_filters_meta()


@app.get("/api/segments")
def api_segments(
    min_dhw: Optional[float] = Query(None, description="按 current_dhw 下限"),
    max_dhw: Optional[float] = Query(None, description="按 current_dhw 上限"),
    min_depth: Optional[float] = Query(None, description="按 mean_depth 下限"),
    max_depth: Optional[float] = Query(None, description="按 mean_depth 上限"),
    min_connectivity: Optional[float] = Query(None, description="按连通性 (1-5) 下限"),
    max_connectivity: Optional[float] = Query(None, description="按连通性 (1-5) 上限"),
    min_score: Optional[float] = Query(None, description="按 final_score/score 下限"),
    max_score: Optional[float] = Query(None, description="按 final_score/score 上限"),
    bleaching_prob_min: Optional[float] = Query(None, description="按 bleaching_probability 下限"),
    bleaching_prob_max: Optional[float] = Query(None, description="按 bleaching_probability 上限"),
    choice: Optional[str] = Query(None, description="决策分类, 逗号分隔多选: invest,monitor,deprioritize"),
    group: Optional[str] = Query(None, description="礁段分组, 逗号分隔: Sipadan,Tun Sakaran,East-West"),
):
    """所有礁段列表 (含特征和评分), 按 score 降序。"""
    params = {
        "min_dhw": min_dhw, "max_dhw": max_dhw,
        "min_depth": min_depth, "max_depth": max_depth,
        "min_connectivity": min_connectivity, "max_connectivity": max_connectivity,
        "min_score": min_score, "max_score": max_score,
        "bleaching_prob_min": bleaching_prob_min,
        "bleaching_prob_max": bleaching_prob_max,
        "choice": choice, "group": group,
    }
    return scoring_service.list_segments(params)


@app.get("/api/segments/{segment_id}")
def api_segment_detail(segment_id: str):
    seg = scoring_service.get_segment_detail(segment_id)
    if seg is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return seg


@app.put("/api/segments/{segment_id}")
def api_update_segment(segment_id: str, payload: SegmentUpdate):
    """NocoBase 回写端点: 更新礁段字段并持久化。"""
    updates = {k: v for k, v in payload.dict().items() if v is not None}
    if not updates:
        return JSONResponse({"error": "no fields to update"}, status_code=400)
    result = scoring_service.update_segment(segment_id, updates)
    if result is None:
        return JSONResponse({"error": "segment not found"}, status_code=404)
    return {"status": "ok", "segment": result}


# ---------------------------------------------------------------------------
# API 端点: 环境 / 监测
# ---------------------------------------------------------------------------
@app.get("/api/segments/{segment_id}/environmental")
def api_segment_environmental(segment_id: str):
    """返回该礁段的物理化学环境数据。"""
    data = environmental_service.get_segment_environmental(segment_id)
    if data.get("__not_found__"):
        return JSONResponse({"error": "segment not found"}, status_code=404)
    return data


@app.get("/api/segments/{segment_id}/bleaching-monitoring")
def api_bleaching_monitoring(segment_id: str):
    """返回白化监测数据。"""
    data = environmental_service.get_bleaching_monitoring(segment_id)
    if data.get("__not_found__"):
        return JSONResponse({"error": "segment not found"}, status_code=404)
    return data


@app.get("/api/environmental/summary")
def api_environmental_summary():
    """返回所有礁段的环境数据摘要 (宏观页面展示用)。"""
    return environmental_service.get_environmental_summary()


# ---------------------------------------------------------------------------
# API 端点: 修复成本
# ---------------------------------------------------------------------------
@app.get("/api/segments/{segment_id}/restoration-cost")
def api_get_restoration_cost(segment_id: str):
    """返回该礁段的修复成本配置。"""
    result = restoration_service.get_restoration_cost(segment_id)
    if result.get("__not_found__"):
        return JSONResponse({"error": "segment not found"}, status_code=404)
    return result


@app.post("/api/segments/{segment_id}/restoration-cost")
def api_save_restoration_cost(segment_id: str, payload: RestorationCostInput):
    """保存修复成本配置到 scored_segments.json。"""
    result = restoration_service.save_restoration_cost(segment_id, payload.dict())
    if result.get("__not_found__"):
        return JSONResponse({"error": "segment not found"}, status_code=404)
    return result


# ---------------------------------------------------------------------------
# API 端点: 报告
# ---------------------------------------------------------------------------
@app.get("/api/segments/{segment_id}/report")
def api_segment_report(segment_id: str):
    """返回单个礁段的完整报告数据 (供 report.html 渲染)。"""
    report = report_service.generate_segment_report(segment_id)
    if report is None:
        return JSONResponse({"error": "segment not found"}, status_code=404)
    return report


@app.get("/api/region/report")
def api_region_report(segment_ids: str = Query("", description="逗号分隔的礁段 ID, 如 R01,R02,R03")):
    """返回多礁段汇总报告。"""
    ids = [s.strip() for s in (segment_ids or "").split(",") if s.strip()]
    if not ids:
        return JSONResponse(
            {"error": "segment_ids query param required (e.g. ?segment_ids=R01,R02)"},
            status_code=400,
        )
    return report_service.generate_region_report(ids)


# ---------------------------------------------------------------------------
# API 端点: 区域绘制相交
# ---------------------------------------------------------------------------
@app.post("/api/region/intersect")
def api_region_intersect(payload: RegionIntersectRequest):
    """根据用户绘制的几何图形, 返回与之相交 / 包含的礁段及汇总统计。"""
    gtype = (payload.type or "polygon").lower()
    if gtype == "circle":
        if not payload.center or payload.radius is None:
            return JSONResponse(
                {"error": "circle type requires 'center' [lon,lat] and 'radius' (m)"},
                status_code=400,
            )
        return region_service.find_intersecting_segments(
            polygon_coords=None,
            geom_type="circle",
            circle_center=payload.center,
            circle_radius_m=float(payload.radius),
        )
    # polygon / rectangle
    if not payload.coordinates:
        return JSONResponse(
            {"error": "polygon/rectangle requires 'coordinates' [[[lon,lat],...]]"},
            status_code=400,
        )
    return region_service.find_intersecting_segments(
        polygon_coords=payload.coordinates,
        geom_type=gtype,
    )


# ---------------------------------------------------------------------------
# API 端点: CRW 5km 网格热力图
# ---------------------------------------------------------------------------
@app.get("/api/grid-data")
def api_grid_data():
    """返回全部有效海洋格点 (lat/lon/dhw/sst/risk/cost), 供前端渲染热力图。"""
    cells = grid_service.load_grid_data()
    return {"count": len(cells), "cells": cells}


@app.post("/api/region/grid-stats")
def api_region_grid_stats(payload: RegionIntersectRequest):
    """用户绘制区域内的网格统计 + 礁段恢复建议。

    请求体与 /api/region/intersect 相同:
      polygon/rectangle: {type, coordinates: [[[lon,lat],...]]}
      circle:            {type:'circle', center:[lon,lat], radius:米}
    """
    gtype = (payload.type or "polygon").lower()
    if gtype == "circle":
        if not payload.center or payload.radius is None:
            return JSONResponse(
                {"error": "circle type requires 'center' [lon,lat] and 'radius' (m)"},
                status_code=400,
            )
        return grid_service.grid_stats_in_polygon(
            polygon_coords=None,
            geom_type="circle",
            circle_center=payload.center,
            circle_radius_m=float(payload.radius),
        )
    if not payload.coordinates:
        return JSONResponse(
            {"error": "polygon/rectangle requires 'coordinates' [[[lon,lat],...]]"},
            status_code=400,
        )
    return grid_service.grid_stats_in_polygon(
        polygon_coords=payload.coordinates,
        geom_type=gtype,
    )


# ---------------------------------------------------------------------------
# API 端点: 预算优先名单 / 优化
# ---------------------------------------------------------------------------
@app.get("/api/priority", response_model=PriorityResponse)
def api_priority(
    budget: float = Query(50000.0, description="总预算 (USD)"),
    unit_cost: float = Query(15000.0, description="每段礁恢复成本 (USD)"),
):
    """预算约束下的优先名单: 按 score 降序取 top N。"""
    data = scoring_service.get_priority(budget, unit_cost)
    return PriorityResponse(**data)


@app.get("/api/optimize")
def api_optimize(
    budget: float = Query(50000.0, description="总预算 (USD)"),
    unit_cost: float = Query(5000.0, description="单位恢复成本 (USD/km²)"),
):
    """预算约束整数规划优化 (模型B)。"""
    return scoring_service.optimize_budget(budget, unit_cost)


# ---------------------------------------------------------------------------
# API 端点: 三层架构模型
# ---------------------------------------------------------------------------
@app.get("/api/model/weights")
def api_model_weights():
    """返回熵权法特征权重 (模型A)。"""
    return scoring_service.get_model_weights()


@app.get("/api/model/compare")
def api_model_compare():
    """新旧模型评分对比。"""
    return scoring_service.get_model_compare()


@app.get("/api/model/feature-contribution")
def api_model_feature_contribution(
    segment_id: str = Query(..., description="礁段 ID, 如 R01"),
):
    """单个礁段的特征贡献度分解 (SHAP 风格瀑布, 供 model.html 贡献度面板)。"""
    result = scoring_service.get_feature_contribution(segment_id)
    if result is None:
        return JSONResponse({"error": "segment not found"}, status_code=404)
    return result


@app.get("/api/model/ml-info")
def api_ml_info():
    """ML 白化预测器信息 (模型C)。"""
    return scoring_service.get_ml_info()


@app.get("/api/model/connectivity")
def api_connectivity():
    """返回28个礁段的幼虫连通性矩阵。"""
    return scoring_service.get_connectivity_matrix()


@app.get("/api/model/backtest")
def api_backtest():
    """返回回测结果。"""
    return scoring_service.get_backtest()


@app.post("/api/recalc")
def api_recalc():
    """触发重新评分。"""
    result = scoring_service.recalc()
    return {"status": "ok", **result}


# ---------------------------------------------------------------------------
# API 端点: 手动数据刷新 (拉取 -> 处理 -> 评分)
# ---------------------------------------------------------------------------
@app.post("/api/data-refresh")
def api_data_refresh(payload: DataRefreshRequest):
    """手动点击 "更新数据" 后执行完整数据接入流水线。

    Body: {"sources": ["crw","bathymetry","osm","copernicus"], "force": true}
    - sources 可缺省, 默认免费免注册的 crw + bathymetry + osm。
    - copernicus 需要免费注册; 未配置凭据时自动跳过并返回注册指引。
    返回逐步骤执行日志 (stdout/stderr 已截断)。
    """
    result = data_refresh_service.run_refresh(
        sources=payload.sources, force=payload.force
    )
    return result


# ---------------------------------------------------------------------------
# API 端点: 数据层元数据
# ---------------------------------------------------------------------------
@app.get("/api/metadata")
def api_metadata():
    """返回所有数据层的来源 / 分辨率 / 引用 / 许可证等元数据。"""
    return metadata_service.get_metadata()


# ---------------------------------------------------------------------------
# API 端点: NocoBase 同步 / 服务状态
# ---------------------------------------------------------------------------
@app.post("/api/sync-to-nocobase")
def api_sync_to_nocobase():
    """触发 ReefTriage -> NocoBase 同步。"""
    return sync_service.sync_to_nocobase()


@app.post("/api/sync-from-nocobase")
def api_sync_from_nocobase():
    """触发 NocoBase -> ReefTriage 回写。"""
    return sync_service.sync_from_nocobase()


@app.get("/api/laya-status")
def api_laya_status():
    """检查 Laya/Jev 服务 (:5000) 状态。"""
    return sync_service.get_laya_status()


@app.get("/api/services-status")
def api_services_status():
    """聚合所有服务状态: ReefTriage / Laya / PostgreSQL / NocoBase。"""
    return sync_service.get_services_status()


# ---------------------------------------------------------------------------
# 静态文件挂载 (必须放在最后, 避免吞掉 API 路由)
# ---------------------------------------------------------------------------
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
