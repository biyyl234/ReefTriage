"""
app/scoring/config.py
=====================
评分模型共享配置: 特征定义、融合参数、阈值、成本模型。

所有模型模块从这里读取常量, 避免硬编码分散。
"""

from __future__ import annotations
from typing import List, Dict

# ---------------------------------------------------------------------------
# 特征定义
# ---------------------------------------------------------------------------

# 用于 MCDM 熵权法 + TOPSIS 的特征 (12维 + bleaching_probability)
# direction: + = 越大越优先 (如热压力、脆弱性), - = 越小越优先 (如水深、距离)
MCDM_FEATURES: List[Dict] = [
    {"key": "current_dhw",            "label": "当前热压力 DHW",       "direction": "+"},
    {"key": "max_dhw_5yr",            "label": "5年最大 DHW",          "direction": "+"},
    {"key": "mean_depth",             "label": "平均水深 (m)",         "direction": "-"},
    {"key": "reef_area_km2",          "label": "礁区面积 (km²)",       "direction": "+"},
    {"key": "distance_to_nearest_dive_site_km", "label": "距潜点距离 (km)", "direction": "-"},
    {"key": "dive_sites_within_5km",  "label": "5km内潜点数",          "direction": "+"},
    {"key": "connectivity_score",     "label": "连通性评分 (1-5)",     "direction": "+"},
    {"key": "larval_input",           "label": "幼虫输入",             "direction": "+"},
    {"key": "larval_output",          "label": "幼虫输出",             "direction": "+"},
    {"key": "rhi_score",              "label": "RHI 健康指数",         "direction": "-"},
    {"key": "total_settlements",      "label": "总沉降量",             "direction": "+"},
    {"key": "bleaching_probability",  "label": "白化概率 (ML预测)",    "direction": "+"},
]

# 贝叶斯不确定性: 各特征的噪声分布 (相对标准差)
BAYESIAN_NOISE: Dict[str, float] = {
    "mean_depth": 0.15,              # 水深估计误差 ±15%
    "rhi_score": 0.20,               # RHI 代理误差 ±20%
    "connectivity_score": 0.10,      # 连通性误差 ±10%
    "reef_area_km2": 0.10,           # 面积估计 ±10%
    "distance_to_nearest_dive_site_km": 0.05,
    "current_dhw": 0.05,             # DHW 观测误差 ±5%
    "max_dhw_5yr": 0.05,
    "bleaching_probability": 0.15,   # ML 预测不确定性
}

BAYESIAN_N_SAMPLES = 1000          # 蒙特卡洛采样次数

# ---------------------------------------------------------------------------
# 融合参数 (经 walk-forward 回测优化, 见 docs/model_optimization_report.md)
# ---------------------------------------------------------------------------
FUSION_ALPHA_MIN = 0.3             # α 下限 (防过拟合)
FUSION_ALPHA_MAX = 0.7             # α 上限
FUSION_ALPHA_DEFAULT = 0.30        # 回测最优 α (2020↔2024 walk-forward 一致)

# final_score = α × mcdm_score + (1-α) × laya_score

# ---------------------------------------------------------------------------
# 分类阈值 (经 ROC/Youden's J 优化, bootstrap 95% CI [37.4, 37.9])
# ---------------------------------------------------------------------------
DEFAULT_THRESHOLD_INVEST = 37.6
DEFAULT_THRESHOLD_MONITOR = 30.0

# ---------------------------------------------------------------------------
# 预算优化成本模型
# ---------------------------------------------------------------------------
# 每段礁恢复成本 = 基础成本 × 面积 × 深度系数
RESTORATION_BASE_COST = 5000       # 每 km² 基础成本 (USD)
RESTORATION_DEPTH_FACTOR = 1.2     # 每米深度成本系数
DEFAULT_UNIT_COST = 5000           # 默认单位成本 (前端滑块)

# ---------------------------------------------------------------------------
# ML 白化预测器
# ---------------------------------------------------------------------------
BLEACHING_DHW_THRESHOLD = 4.0      # DHW≥4 作为白化代理标签
ML_TEST_SIZE = 0.3                 # 训练/测试划分
ML_RANDOM_STATE = 42

# ---------------------------------------------------------------------------
# 回测
# ---------------------------------------------------------------------------
BACKTEST_BOOTSTRAP_N = 1000        # bootstrap 次数
BACKTEST_PERIODS = [
    {"year": 2020, "month_start": 3, "month_end": 6, "label": "2020 白化峰值"},
    {"year": 2024, "month_start": 3, "month_end": 6, "label": "2024 白化峰值"},
]
