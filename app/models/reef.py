"""
app/models/reef.py
==================
Pydantic 数据模型: 礁段特征、评分结果、API 响应。
"""

from __future__ import annotations
from typing import Optional, List, Literal, Dict, Any
from pydantic import BaseModel, Field


class ReefSegmentFeatures(BaseModel):
    """一个礁段的输入特征。"""
    segment_id: str
    name: str
    name_zh: Optional[str] = None
    lat: float
    lon: float
    current_dhw: float = 0.0
    max_dhw_5yr: float = 0.0
    mean_depth: float = 15.0
    distance_to_dive_site: float = 5.0
    connectivity_score: float = 3.0   # 1-5
    rhi_score: float = 50.0           # 0-100
    reef_area: float = 0.5            # km2
    historical_mortality: Optional[float] = None  # %


class ScoreResult(BaseModel):
    """单段评分结果。"""
    score: int = Field(description="0-100 恢复优先级")
    choice: Literal["invest", "monitor", "deprioritize"]
    confidence: float = 0.0
    model: str = "unknown"
    inputs_snapshot: Dict[str, Any] = Field(default_factory=dict)


class ReefSegment(ReefSegmentFeatures, ScoreResult):
    """完整礁段 (特征 + 评分)。"""
    pass


class PriorityItem(BaseModel):
    segment_id: str
    name: str
    name_zh: Optional[str] = None
    score: int
    choice: str
    lat: float
    lon: float
    cost_estimate: float = 15000.0


class PriorityResponse(BaseModel):
    budget: float
    unit_cost: float
    funded_count: int
    total_cost: float
    items: List[PriorityItem]


class HealthStatus(BaseModel):
    backend: str = "ok"
    laya_available: bool
    laya_mode: Literal["live", "mock"]
    laya_base_url: str
    segments_loaded: int
    fusion_enabled: bool = True


class StatsResponse(BaseModel):
    total_segments: int
    invest_count: int
    monitor_count: int
    deprioritize_count: int
    avg_score: float
    laya_mode: str
