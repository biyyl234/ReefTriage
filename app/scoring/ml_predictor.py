"""
app/scoring/ml_predictor.py
===========================
模型 C: ML 白化概率预测器 (Logistic Regression)。

用 scikit-learn 训练一个可解释的逻辑回归模型, 基于礁段多维特征预测白化概率。
标签以 DHW >= config.BLEACHING_DHW_THRESHOLD 作为白化代理 (supervised 伪标签)。

训练样本通过历史 CRW DHW 时间序列增强: 除当前礁段快照外, 再取
2020 / 2024 年 3-6 月白化峰值期的最大 DHW 替换 current_dhw, 形成
同一礁段在不同热压力情景下的多条样本, 缓解 28 礁段小样本问题。

模型经 StandardScaler 标准化后训练, 逻辑回归系数可直接展示给前端
(绝对值大小反映特征对白化风险的边际贡献, 正负反映方向)。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.exceptions import ConvergenceWarning
import warnings

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.scoring import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 12 维特征定义 (顺序即模型特征列顺序, 不得随意改动)
# ---------------------------------------------------------------------------
FEATURE_NAMES: List[str] = [
    "current_dhw",
    "max_dhw_5yr",
    "mean_depth",
    "reef_area_km2",
    "distance_to_nearest_dive_site_km",
    "dive_sites_within_5km",
    "connectivity_score",
    "larval_input",
    "larval_output",
    "rhi_score",
    "total_settlements",
    "current_sst",
]

# 历史 DHW 增强时段 (与 config.BACKTEST_PERIODS 对齐)
AUGMENT_PERIODS: List[Dict[str, int]] = [
    {"year": 2020, "month_start": 3, "month_end": 6},
    {"year": 2024, "month_start": 3, "month_end": 6},
]

# 模块级模型缓存 (懒加载, 训练一次后复用)
_model_cache: Optional[Dict[str, Any]] = None


def _safe_float(v: Any, default: float = 0.0) -> float:
    """把任意字段安全转成 float, 缺失/NaN 回退到 default。"""
    if v is None:
        return default
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if np.isnan(f):
        return default
    return f


def _feature_vector(segment: Dict[str, Any],
                    dhw_override: Optional[float] = None) -> np.ndarray:
    """
    从单个礁段字典提取 12 维特征向量。

    Parameters
    ----------
    segment : dict
        礁段记录 (scored_segments.json 中的一项)。
    dhw_override : float, optional
        若提供, 用该值替换 current_dhw (历史时段增强时使用)。
    """
    dhw = _safe_float(segment.get("current_dhw")) if dhw_override is None else _safe_float(dhw_override)
    values = [
        dhw,
        _safe_float(segment.get("max_dhw_5yr")),
        _safe_float(segment.get("mean_depth")),
        _safe_float(segment.get("reef_area_km2")),
        _safe_float(segment.get("distance_to_nearest_dive_site_km")),
        _safe_float(segment.get("dive_sites_within_5km")),
        _safe_float(segment.get("connectivity_score")),
        _safe_float(segment.get("larval_input")),
        _safe_float(segment.get("larval_output")),
        _safe_float(segment.get("rhi_score")),
        _safe_float(segment.get("total_settlements")),
        _safe_float(segment.get("current_sst")),
    ]
    return np.asarray(values, dtype=float)


def build_training_data(
    segments: List[Dict[str, Any]],
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """
    构建训练数据集。

    对每个礁段:
      1. 以当前快照生成 1 条样本 (current_dhw 来自 segment);
      2. 用 CRW 历史 DHW 提取 2020 / 2024 年 3-6 月最大 DHW,
         替换 current_dhw 后各生成 1 条增强样本。

    标签 y = 1 当且仅当该样本的 (替换后的) current_dhw >=
    config.BLEACHING_DHW_THRESHOLD, 否则 0。

    Returns
    -------
    X : np.ndarray, shape (n_samples, 12)
    y : np.ndarray, shape (n_samples,)
    feature_names : List[str]
    """
    rows: List[np.ndarray] = []
    labels: List[int] = []

    def _add(dhw_value: float, seg: Dict[str, Any]) -> None:
        rows.append(_feature_vector(seg, dhw_override=dhw_value))
        labels.append(1 if dhw_value >= config.BLEACHING_DHW_THRESHOLD else 0)

    # 1) 当前快照
    for seg in segments:
        _add(_safe_float(seg.get("current_dhw")), seg)

    # 2) 历史 DHW 增强 (延迟导入, 避免无 netCDF 环境下硬失败)
    try:
        from app.scoring.data_loader import extract_dhw_at_period
        for period in AUGMENT_PERIODS:
            dhw_map = extract_dhw_at_period(
                period["year"], period["month_start"], period["month_end"]
            )
            if not dhw_map:
                logger.warning(
                    "No DHW extracted for %d-%d..%d, skipping augmentation period",
                    period["year"], period["month_start"], period["month_end"],
                )
                continue
            for seg in segments:
                sid = seg["segment_id"]
                if sid in dhw_map:
                    _add(dhw_map[sid], seg)
            logger.info(
                "Augmented with %d period (%d segments)", period["year"], len(dhw_map)
            )
    except ImportError:
        logger.warning("data_loader not importable, skipping historical DHW augmentation")
    except Exception as e:  # netCDF 读取失败时不阻塞主流程
        logger.warning("Historical DHW augmentation failed: %s", e)

    X = np.vstack(rows)
    y = np.asarray(labels, dtype=int)
    logger.info("Built training matrix: X=%s, y=%s, positives=%d",
                X.shape, y.shape, int(y.sum()))
    return X, y, list(FEATURE_NAMES)


def train_model(X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
    """
    训练逻辑回归模型 (带 StandardScaler 管道)。

    Parameters
    ----------
    X : (n, 12) 特征矩阵
    y : (n,) 0/1 标签

    Returns
    -------
    dict with keys:
        model, scaler, feature_names, coef (dict), intercept, metrics
    """
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=config.ML_TEST_SIZE,
        random_state=config.ML_RANDOM_STATE,
        stratify=y if len(np.unique(y)) > 1 else None,
    )

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)

    clf = LogisticRegression(
        class_weight="balanced",
        max_iter=2000,
        random_state=config.ML_RANDOM_STATE,
        solver="lbfgs",
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        clf.fit(X_train_s, y_train)

    # 特征系数 (基于标准化后的特征, 可直接比较相对重要性)
    coef_dict = {
        name: float(coef) for name, coef in zip(FEATURE_NAMES, clf.coef_[0])
    }

    metrics = evaluate_model(
        {"model": clf, "scaler": scaler}, X_test, y_test
    )

    return {
        "model": clf,
        "scaler": scaler,
        "feature_names": list(FEATURE_NAMES),
        "coef": coef_dict,
        "intercept": float(clf.intercept_[0]),
        "metrics": metrics,
        "train_size": int(len(y_train)),
        "test_size": int(len(y_test)),
    }


def evaluate_model(
    model_dict: Dict[str, Any], X: np.ndarray, y: np.ndarray
) -> Dict[str, Any]:
    """
    在给定 (已划分好的) 测试集上计算分类指标。

    Returns
    -------
    dict: auc, accuracy, precision, recall, f1, confusion_matrix (2x2 list)
    """
    clf = model_dict["model"]
    scaler = model_dict["scaler"]
    X_s = scaler.transform(X)

    y_pred = clf.predict(X_s)
    y_proba = clf.predict_proba(X_s)[:, 1]

    # AUC 需要两类都出现; 若测试集只有一类则回退为 None
    try:
        auc = float(roc_auc_score(y, y_proba))
    except ValueError:
        auc = None

    cm = confusion_matrix(y, y_pred, labels=[0, 1])

    return {
        "auc": auc,
        "accuracy": float(accuracy_score(y, y_pred)),
        "precision": float(precision_score(y, y_pred, zero_division=0)),
        "recall": float(recall_score(y, y_pred, zero_division=0)),
        "f1": float(f1_score(y, y_pred, zero_division=0)),
        "confusion_matrix": cm.tolist(),
        "n_test": int(len(y)),
        "n_positive": int(y.sum()),
    }


def predict_bleaching_probability(
    segments: List[Dict[str, Any]], model_dict: Dict[str, Any]
) -> List[float]:
    """
    对每个礁段预测白化概率 (0-1)。使用当前快照的 current_dhw。

    Returns
    -------
    List[float] : 与 segments 等长的概率列表
    """
    if not segments:
        return []
    X = np.vstack([_feature_vector(s) for s in segments])
    X_s = model_dict["scaler"].transform(X)
    proba = model_dict["model"].predict_proba(X_s)[:, 1]
    return [float(p) for p in proba]


def get_or_train_model(segments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    懒加载模型: 进程内训练一次后缓存, 后续调用直接返回。

    若缓存为空, 则用 segments 构建训练数据并训练。
    """
    global _model_cache
    if _model_cache is None:
        X, y, names = build_training_data(segments)
        _model_cache = train_model(X, y)
        logger.info(
            "ML predictor trained: AUC=%s, accuracy=%.3f",
            _model_cache["metrics"]["auc"], _model_cache["metrics"]["accuracy"],
        )
    return _model_cache


def reset_cache() -> None:
    """清空模型缓存 (主要用于测试或强制重训)。"""
    global _model_cache
    _model_cache = None
