"""
app/scoring/threshold.py
========================
分类阈值优化: 基于 ROC / Youden's J 自动确定 invest / monitor / deprioritize 切分点.

输入是礁段综合分 (0-100) 与代理标签 (例如 ``current_dhw >= 4`` 视为白化/需投入).
输出一组阈值, 使高风险召回率与假阳性率达到最佳折中, 并用 bootstrap 给出阈值置信区间.
"""

from __future__ import annotations

import math
from typing import List, Dict, Any

import numpy as np
from sklearn.metrics import roc_curve, auc

from . import config


# ---------------------------------------------------------------------------
# 数值安全工具
# ---------------------------------------------------------------------------

def _clean_arrays(scores: List[float], labels: List[int]):
    """清洗 scores/labels, 丢弃 NaN/Inf 与长度不一致项.

    Returns
    -------
    (np.ndarray, np.ndarray)
        已清洗的 scores (float) 与 labels (int, 0/1).
    """
    s = np.asarray(scores, dtype=float)
    y = np.asarray(labels, dtype=int)
    if s.shape[0] != y.shape[0]:
        m = min(s.shape[0], y.shape[0])
        s, y = s[:m], y[:m]
    mask = np.isfinite(s) & np.isfinite(y)
    s, y = s[mask], y[mask].astype(int)
    # 只保留 0/1 标签
    keep = (y == 0) | (y == 1)
    return s[keep], y[keep]


# ---------------------------------------------------------------------------
# ROC 基础
# ---------------------------------------------------------------------------

def compute_roc(scores: List[float], labels: List[int]) -> Dict:
    """计算 ROC 曲线与 AUC.

    Parameters
    ----------
    scores : list[float]
        预测分数 (0-100 或任意连续值, 越大越倾向正类).
    labels : list[int]
        真实标签, 1 = 白化/需投入, 0 = 否.

    Returns
    -------
    dict
        ``fpr`` / ``tpr`` / ``thresholds`` / ``auc``.
        若正/负类缺失导致 ROC 不可算, 返回空数组与 ``auc=float('nan')``.
    """
    s, y = _clean_arrays(scores, labels)
    if s.size < 2 or np.unique(y).size < 2:
        return {"fpr": [], "tpr": [], "thresholds": [], "auc": float("nan")}

    fpr, tpr, thr = roc_curve(y, s)
    auroc = auc(fpr, tpr)
    return {
        "fpr": fpr.tolist(),
        "tpr": tpr.tolist(),
        "thresholds": thr.tolist(),
        "auc": float(auroc),
    }


# ---------------------------------------------------------------------------
# Youden's J 最优阈值
# ---------------------------------------------------------------------------

def optimal_threshold_youden(scores: List[float], labels: List[int]) -> Dict:
    """用 Youden's J = TPR - FPR 最大化选择最优阈值.

    Returns
    -------
    dict
        ``threshold`` / ``youden_j`` / ``sensitivity`` (TPR) / ``specificity`` (1-FPR).
        若样本不足, 返回默认阈值 (50) 与 ``nan`` 指标.
    """
    s, y = _clean_arrays(scores, labels)
    if s.size < 2 or np.unique(y).size < 2:
        return {
            "threshold": float(config.DEFAULT_THRESHOLD_INVEST),
            "youden_j": float("nan"),
            "sensitivity": float("nan"),
            "specificity": float("nan"),
        }

    fpr, tpr, thr = roc_curve(y, s)
    j = tpr - fpr
    idx = int(np.argmax(j))
    return {
        "threshold": float(thr[idx]),
        "youden_j": float(j[idx]),
        "sensitivity": float(tpr[idx]),
        "specificity": float(1.0 - fpr[idx]),
    }


# ---------------------------------------------------------------------------
# Bootstrap 置信区间
# ---------------------------------------------------------------------------

def bootstrap_threshold_ci(scores: List[float],
                           labels: List[int],
                           n_bootstrap: int = config.BACKTEST_BOOTSTRAP_N,
                           seed: int = 42) -> Dict:
    """对最优阈值做 bootstrap, 给出 95% 置信区间.

    每次有放回采样 n 个样本, 在该样本上重新求 Youden's J 最优阈值.

    Returns
    -------
    dict
        ``mean`` / ``ci_lower`` (2.5%) / ``ci_upper`` (97.5%) / ``all_thresholds``.
        若某次 bootstrap 中正负类缺失, 该次结果被丢弃.
    """
    s, y = _clean_arrays(scores, labels)
    n = s.size
    if n < 2:
        return {"mean": float("nan"), "ci_lower": float("nan"),
                "ci_upper": float("nan"), "all_thresholds": []}

    rng = np.random.default_rng(seed)
    collected: List[float] = []
    n_bootstrap = max(1, int(n_bootstrap))

    for _ in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        s_b = s[idx]
        y_b = y[idx]
        if np.unique(y_b).size < 2:
            continue
        try:
            fpr_b, tpr_b, thr_b = roc_curve(y_b, s_b)
            j_b = tpr_b - fpr_b
            collected.append(float(thr_b[int(np.argmax(j_b))]))
        except Exception:
            continue

    if not collected:
        return {"mean": float("nan"), "ci_lower": float("nan"),
                "ci_upper": float("nan"), "all_thresholds": []}

    arr = np.asarray(collected, dtype=float)
    return {
        "mean": float(np.mean(arr)),
        "ci_lower": float(np.percentile(arr, 2.5)),
        "ci_upper": float(np.percentile(arr, 97.5)),
        "all_thresholds": collected,
    }


# ---------------------------------------------------------------------------
# 双阈值联合优化
# ---------------------------------------------------------------------------

def optimize_all_thresholds(scores: List[float], labels: List[int]) -> Dict:
    """同时优化 invest 与 monitor/deprioritize 两个阈值.

    - ``invest_threshold``: 用 Youden's J 在 (高风险 vs 其他) 上求最佳切点.
    - ``monitor_threshold``: 介于 invest 与低风险之间的过渡切点,
      取分数中位数 (若中位数高于 invest 阈值则下调到 invest - 5,
      保证 invest > monitor 单调).

    Returns
    -------
    dict
        ``invest_threshold`` / ``monitor_threshold``, 各自为 dict.
    """
    s, _ = _clean_arrays(scores, labels)
    invest = optimal_threshold_youden(scores, labels)

    if s.size == 0:
        monitor_val = float(config.DEFAULT_THRESHOLD_MONITOR)
    else:
        med = float(np.median(s))
        invest_val = invest.get("threshold", float(config.DEFAULT_THRESHOLD_INVEST))
        # 保证 invest > monitor 的三段式单调
        monitor_val = min(med, invest_val - 5.0)

    return {
        "invest_threshold": invest,
        "monitor_threshold": {
            "threshold": round(monitor_val, 2),
            "note": "median of scores, constrained below invest threshold",
        },
    }
