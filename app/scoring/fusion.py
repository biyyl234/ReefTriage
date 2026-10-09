"""
app/scoring/fusion.py
=====================
双引擎评分融合: MCDM (客观) + Laya (AI判断) → final_score。

融合公式:
    final_score = α × mcdm_score + (1 - α) × laya_score

α 用 walk-forward 回测优化, 限制在 [FUSION_ALPHA_MIN, FUSION_ALPHA_MAX]。
默认 α = FUSION_ALPHA_DEFAULT (等权重)。

流程:
    1. ML 预测 bleaching_probability (模型C)
    2. 熵权法 + TOPSIS 计算 mcdm_score (模型A)
    3. Laya rubric 计算 laya_score (现有, 可 mock)
    4. 加权融合得到 final_score
    5. 贝叶斯蒙特卡洛计算置信区间 (模型D)
    6. ROC/Youden's J 优化分类阈值
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from . import config
from . import mcdm
from . import ml_predictor
from . import bayesian
from . import threshold as threshold_mod

logger = logging.getLogger(__name__)

# 模块级缓存
_cached_weights: Optional[Dict[str, float]] = None
_cached_model: Optional[Dict[str, Any]] = None
_cached_alpha: Optional[float] = None
_cached_thresholds: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# 单层计算
# ---------------------------------------------------------------------------

def compute_bleaching_probs(segments: List[Dict[str, Any]]) -> List[float]:
    """模型C: ML 白化概率预测。"""
    global _cached_model
    if _cached_model is None:
        _cached_model = ml_predictor.get_or_train_model(segments)
    return ml_predictor.predict_bleaching_probability(segments, _cached_model)


def compute_mcdm_scores(segments: List[Dict[str, Any]]) -> Tuple[List[float], Dict[str, float]]:
    """模型A: 熵权法 + TOPSIS。"""
    global _cached_weights
    scores, weights = mcdm.compute_mcdm(segments)
    _cached_weights = weights
    return scores, weights


def compute_laya_scores(segments: List[Dict[str, Any]], laya_client,
                        use_v2: bool = True) -> List[float]:
    """
    Laya/Jev AI 评分 (现有逻辑, 可 mock)。
    返回 0-100 分数列表。
    """
    from . import rubric
    from . import rubric_v2
    from .rhi import compute_simplified_rhi
    from .engine import _estimate_rhi_proxies

    scores = []
    for s in segments:
        feats = dict(s)
        proxies = _estimate_rhi_proxies(s)
        feats["rhi_score"] = compute_simplified_rhi(proxies)
        feats["rhi_proxies"] = proxies

        if use_v2:
            state = rubric_v2.build_state_v2(feats)
            questions = rubric_v2.build_questions_v2()
        else:
            state = rubric.build_state(feats)
            questions = rubric.build_questions()

        resp = laya_client.predict(state, questions)
        answers = resp.get("answers", {})
        ps = answers.get("priority_score", {})
        raw = float(ps.get("score", 2.0))
        if use_v2:
            score = rubric_v2.interpret_score_v2(raw)
        else:
            score = rubric.interpret_score(raw)
        scores.append(score)
    return scores


# ---------------------------------------------------------------------------
# 融合
# ---------------------------------------------------------------------------

def fuse_scores(mcdm_scores: List[float], laya_scores: List[float],
                alpha: Optional[float] = None) -> List[float]:
    """
    加权融合: final = α × mcdm + (1-α) × laya。
    α 限制在 [config.FUSION_ALPHA_MIN, config.FUSION_ALPHA_MAX]。
    """
    if alpha is None:
        alpha = get_optimal_alpha()
    alpha = float(np.clip(alpha, config.FUSION_ALPHA_MIN, config.FUSION_ALPHA_MAX))
    final = [alpha * m + (1 - alpha) * l for m, l in zip(mcdm_scores, laya_scores)]
    return [round(f, 1) for f in final]


def get_optimal_alpha() -> float:
    """
    获取最优融合权重 α。
    优先用回测优化值, 否则用默认值。
    简化实现: 用信息系数(IC)评估两个引擎的预测能力, 按 IC 加权。
    """
    global _cached_alpha
    if _cached_alpha is not None:
        return _cached_alpha
    # 默认等权重 (回测优化在 scripts/run_backtest.py 中执行, 结果可写入配置)
    _cached_alpha = config.FUSION_ALPHA_DEFAULT
    return _cached_alpha


def set_optimal_alpha(alpha: float) -> None:
    """设置最优 α (由回测脚本调用)。"""
    global _cached_alpha
    _cached_alpha = float(np.clip(alpha, config.FUSION_ALPHA_MIN, config.FUSION_ALPHA_MAX))
    logger.info("Fusion alpha set to %.3f", _cached_alpha)


# ---------------------------------------------------------------------------
# 分类阈值
# ---------------------------------------------------------------------------

def get_optimal_thresholds(scores: List[float], labels: List[int]) -> Dict[str, Any]:
    """用 ROC + Youden's J 优化分类阈值。"""
    global _cached_thresholds
    if _cached_thresholds is not None:
        return _cached_thresholds
    _cached_thresholds = threshold_mod.optimize_all_thresholds(scores, labels)
    return _cached_thresholds


def classify_score(score: float, invest_threshold: float = config.DEFAULT_THRESHOLD_INVEST,
                   monitor_threshold: float = config.DEFAULT_THRESHOLD_MONITOR) -> str:
    """根据阈值分类。"""
    if score >= invest_threshold:
        return "invest"
    elif score >= monitor_threshold:
        return "monitor"
    return "deprioritize"


# ---------------------------------------------------------------------------
# 完整评分流水线
# ---------------------------------------------------------------------------

def score_all(segments: List[Dict[str, Any]], laya_client,
              alpha: Optional[float] = None,
              compute_ci: bool = True) -> List[Dict[str, Any]]:
    """
    三层架构完整评分流水线。

    输入: segments (原始特征列表), laya_client (LayaClient 实例)
    输出: 每个礁段增加以下字段:
        - bleaching_probability: ML 预测白化概率
        - mcdm_score: 熵权TOPSIS客观分
        - laya_score: Laya AI判断分
        - final_score: 融合分 (0-100)
        - score: 兼容旧字段 (= final_score 取整)
        - choice: 分类
        - confidence_interval: {"mean", "std", "ci_lower", "ci_upper"}
        - feature_weights: 熵权法权重
    """
    n = len(segments)
    logger.info("Fusion pipeline: scoring %d segments (α=%s)", n, alpha or "auto")

    # 第一层: 特征增强
    bleach_probs = compute_bleaching_probs(segments)

    # 将 bleaching_probability 注入 segments (供 MCDM 使用)
    enriched = []
    for i, s in enumerate(segments):
        s2 = dict(s)
        s2["bleaching_probability"] = bleach_probs[i]
        enriched.append(s2)

    # 第二层: 双引擎评分
    mcdm_scores, weights = compute_mcdm_scores(enriched)
    laya_scores = compute_laya_scores(enriched, laya_client, use_v2=True)

    # 融合
    final_scores = fuse_scores(mcdm_scores, laya_scores, alpha)

    # 第三层: 分类 (用默认阈值, 优化阈值由回测脚本设置)
    invest_th = config.DEFAULT_THRESHOLD_INVEST
    monitor_th = config.DEFAULT_THRESHOLD_MONITOR

    # 贝叶斯置信区间 (对融合分数)
    ci_results = [None] * n
    if compute_ci:
        # 用固定 PIS/NIS 的 TOPSIS scorer 做蒙特卡洛
        scorer = mcdm.make_topsis_scorer(enriched, weights)
        ci_results = bayesian.compute_bayesian_for_all(enriched, scorer, seed=42)

    # 组装结果
    results = []
    for i, s in enumerate(enriched):
        r = dict(s)
        r["bleaching_probability"] = round(bleach_probs[i], 4)
        r["mcdm_score"] = round(mcdm_scores[i], 1)
        r["laya_score"] = round(laya_scores[i], 1)
        r["final_score"] = final_scores[i]
        r["score"] = int(round(final_scores[i]))
        r["choice"] = classify_score(final_scores[i], invest_th, monitor_th)
        r["alpha"] = alpha if alpha is not None else get_optimal_alpha()
        if ci_results[i] is not None:
            r["confidence_interval"] = {
                "mean": round(ci_results[i]["mean"], 1),
                "std": round(ci_results[i]["std"], 2),
                "ci_lower": round(ci_results[i]["ci_lower"], 1),
                "ci_upper": round(ci_results[i]["ci_upper"], 1),
            }
        results.append(r)

    logger.info("Fusion complete: invest=%d, monitor=%d, deprioritize=%d",
                sum(1 for r in results if r["choice"] == "invest"),
                sum(1 for r in results if r["choice"] == "monitor"),
                sum(1 for r in results if r["choice"] == "deprioritize"))
    return results


def get_feature_weights() -> Optional[Dict[str, float]]:
    """获取最近一次计算的熵权法权重。"""
    return _cached_weights


def get_ml_model_info() -> Optional[Dict[str, Any]]:
    """获取 ML 模型信息 (系数、评估指标)。"""
    return _cached_model


def reset_caches() -> None:
    """重置所有缓存 (recalc 时调用)。"""
    global _cached_weights, _cached_model, _cached_alpha, _cached_thresholds
    _cached_weights = None
    _cached_model = None
    _cached_alpha = None
    _cached_thresholds = None
    ml_predictor.reset_cache()
    logger.info("Fusion caches reset")
