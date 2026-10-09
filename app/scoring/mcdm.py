"""
app/scoring/mcdm.py
====================
多准则决策模型 (Model A): 熵权法 (Entropy Weight) + TOPSIS。

数学原理
--------
1. 数据矩阵 X ∈ R^{n×m}, n 个礁段, m 个评价特征。

2. 方向调整后的极差归一化:
   - 正向特征 (+):  z_ij = (x_ij - min_j) / (max_j - min_j)
   - 负向特征 (-):  z_ij = (max_j - x_ij) / (max_j - min_j)
   归一化后 z_ij ∈ [0, 1], 越大表示该礁段在该特征上越"优先"。

3. 熵权法计算客观权重:
   - 比重 p_ij = z_ij / Σ_i z_ij   (列归一化)
   - 信息熵 e_j = -k · Σ_i p_ij · ln(p_ij),  k = 1 / ln(n)
     约定 0 · ln(0) = 0。
   - 差异系数 g_j = 1 - e_j  (熵越小, 提供的信息量越大)
   - 权重 w_j = g_j / Σ_j g_j
   若某列全为 0 (例如缺失特征被填充为 0), 则该列无区分度, 权重为 0。

4. TOPSIS 接近度:
   - 加权归一化矩阵 v_ij = w_j · z_ij
   - 正理想解 V^+ = max_i v_ij (各列最大值, 即最优先)
   - 负理想解 V^- = min_i v_ij
   - D_i^+ = sqrt(Σ_j (v_ij - V_j^+)^2)
   - D_i^- = sqrt(Σ_j (v_ij - V_j^-)^2)
   - 接近度 C_i = D_i^- / (D_i^+ + D_i^-) ∈ [0, 1]
   - 映射到 0-100:  mcdm_score_i = 100 · C_i

仅依赖 numpy 与标准库。
"""

from __future__ import annotations

import math
from typing import Callable, Dict, List, Tuple

import numpy as np

from . import config


# 单段评分函数签名 (供贝叶斯蒙特卡洛调用)
SegmentScoreFn = Callable[[Dict], float]


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------

def _extract_matrix(segments: List[Dict]) -> Tuple[np.ndarray, List[str]]:
    """从 segments 中按 config.MCDM_FEATURES 顺序抽取数值矩阵。

    缺失字段 (如 bleaching_probability) 以 0 填充;
    非数值 / NaN / Inf 统一用该列均值 (无可用均值时为 0) 替换。

    Returns
    -------
    X : np.ndarray, shape (n, m)
    keys : List[str], 长度 m, 与列顺序对应
    """
    keys: List[str] = [f["key"] for f in config.MCDM_FEATURES]
    n = len(segments)
    m = len(keys)
    X = np.zeros((n, m), dtype=float)

    for j, key in enumerate(keys):
        col = np.zeros(n, dtype=float)
        for i, seg in enumerate(segments):
            v = seg.get(key, 0)
            if v is None:
                v = 0.0
            try:
                fv = float(v)
            except (TypeError, ValueError):
                fv = 0.0
            if not math.isfinite(fv):
                fv = 0.0
            col[i] = fv
        X[:, j] = col

    # 用列均值替换残留的 NaN/Inf (防御性)
    col_mean = np.nanmean(np.where(np.isfinite(X), X, np.nan), axis=0)
    col_mean = np.where(np.isfinite(col_mean), col_mean, 0.0)
    bad = ~np.isfinite(X)
    if bad.any():
        idx = np.where(bad)
        X[idx] = col_mean[idx[1]]

    return X, keys


def _directional_minmax(X: np.ndarray) -> np.ndarray:
    """按 config.MCDM_FEATURES 中 direction 做方向调整后的极差归一化。

    正向特征: z = (x - min) / (max - min)
    负向特征: z = (max - x) / (max - min)
    若 max == min (无区分度), 该列置 0。
    """
    directions = [f["direction"] for f in config.MCDM_FEATURES]
    n, m = X.shape
    Z = np.zeros_like(X)
    for j in range(m):
        col = X[:, j]
        cmin = float(np.min(col))
        cmax = float(np.max(col))
        rng = cmax - cmin
        if rng <= 0.0:
            Z[:, j] = 0.0
            continue
        if directions[j] == "+":
            Z[:, j] = (col - cmin) / rng
        else:  # "-"
            Z[:, j] = (cmax - col) / rng
    return Z


# ---------------------------------------------------------------------------
# 1. 熵权法
# ---------------------------------------------------------------------------

def entropy_weights(segments: List[Dict]) -> Dict[str, float]:
    """计算各 MCDM 特征的熵权法客观权重。

    Parameters
    ----------
    segments : List[Dict]
        礁段字典列表, 需包含 config.MCDM_FEATURES 中声明的字段;
        缺失字段 (如 bleaching_probability) 按 0 处理。

    Returns
    -------
    Dict[str, float]
        {feature_key: weight}, 权重和为 1 (全零列除外, 其权重为 0)。
    """
    X, keys = _extract_matrix(segments)
    Z = _directional_minmax(X)
    n, m = Z.shape

    weights = np.zeros(m, dtype=float)
    if n == 0:
        return {k: 0.0 for k in keys}

    k = 1.0 / math.log(n) if n > 1 else 1.0

    for j in range(m):
        col = Z[:, j]
        col_sum = float(np.sum(col))
        if col_sum <= 0.0:
            # 该列无区分度 (全 0), 信息熵最大, 权重为 0
            weights[j] = 0.0
            continue
        p = col / col_sum
        # 0 * ln(0) 约定为 0
        mask = p > 0.0
        entropy = -k * float(np.sum(p[mask] * np.log(p[mask])))
        # 数值防御
        if not math.isfinite(entropy):
            entropy = 1.0
        entropy = float(np.clip(entropy, 0.0, 1.0))
        weights[j] = 1.0 - entropy

    total = float(np.sum(weights))
    if total > 0.0:
        weights = weights / total
    else:
        # 所有列都无区分度时, 退化为等权 (防御)
        weights = np.full(m, 1.0 / m)

    return {keys[j]: float(weights[j]) for j in range(m)}


# ---------------------------------------------------------------------------
# 2. TOPSIS
# ---------------------------------------------------------------------------

def topsis_score(segments: List[Dict], weights: Dict[str, float]) -> List[float]:
    """基于给定权重计算每个礁段的 TOPSIS 接近度得分 (0-100)。

    Parameters
    ----------
    segments : List[Dict]
        礁段字典列表。
    weights : Dict[str, float]
        由 :func:`entropy_weights` 输出的特征权重。

    Returns
    -------
    List[float]
        长度 n, 每个元素 ∈ [0, 100], 越大越优先。
    """
    X, keys = _extract_matrix(segments)
    Z = _directional_minmax(X)
    n, m = Z.shape

    w = np.array([weights.get(k, 0.0) for k in keys], dtype=float)
    # 防御: 权重归一化
    wsum = float(np.sum(w))
    if wsum > 0.0:
        w = w / wsum

    V = Z * w[np.newaxis, :]

    # 正/负理想解: 方向调整后越大越优, 故 PIS=max, NIS=min
    v_pos = np.max(V, axis=0)
    v_neg = np.min(V, axis=0)

    diff_pos = V - v_pos[np.newaxis, :]
    diff_neg = V - v_neg[np.newaxis, :]
    d_pos = np.sqrt(np.sum(diff_pos * diff_pos, axis=1))
    d_neg = np.sqrt(np.sum(diff_neg * diff_neg, axis=1))

    denom = d_pos + d_neg
    # 防御: 若某礁段与 PIS/NIS 距离均为 0 (即等于理想解), 给满分
    closeness = np.where(denom > 0.0, d_neg / np.where(denom == 0, 1.0, denom), 0.0)
    closeness = np.where(denom == 0.0, 1.0, closeness)

    scores = 100.0 * closeness
    # 数值清理
    scores = np.where(np.isfinite(scores), scores, 0.0)
    scores = np.clip(scores, 0.0, 100.0)
    return [float(s) for s in scores]


# ---------------------------------------------------------------------------
# 3. 组合入口
# ---------------------------------------------------------------------------

def compute_mcdm(segments: List[Dict]) -> Tuple[List[float], Dict[str, float]]:
    """一键计算 MCDM 得分与熵权法权重。

    Returns
    -------
    (mcdm_scores, weights)
        mcdm_scores : List[float], 长度 n, ∈ [0, 100]
        weights     : Dict[str, float], {feature_key: weight}
    """
    weights = entropy_weights(segments)
    scores = topsis_score(segments, weights)
    return scores, weights


# ---------------------------------------------------------------------------
# 4. 闭包工厂 (供贝叶斯蒙特卡洛使用)
# ---------------------------------------------------------------------------

def make_topsis_scorer(segments: List[Dict],
                       weights: Dict[str, float]) -> SegmentScoreFn:
    """构造一个"固定 PIS/NIS"的单段评分闭包。

    TOPSIS 是相对方法: PIS (正理想解) 与 NIS (负理想解) 应由整个礁段
    集合决定。做蒙特卡洛扰动时, 我们希望扰动只来自单段自身的特征噪声,
    而不是每轮都重新拟合全数据集。本函数用全数据集拟合出:

      - 每列的方向调整极差归一化基准 (cmin, cmax)
      - 权重 w
      - 正/负理想解 v_pos, v_neg

    返回的闭包 score_fn(segment) 接受一个 (可能带噪的) segment dict,
    用同一套基准归一化后计算到固定 PIS/NIS 的距离, 返回 0-100 分数。

    Parameters
    ----------
    segments : List[Dict]
        用于拟合基准的全量礁段。
    weights : Dict[str, float]
        由 :func:`entropy_weights` 输出的权重。

    Returns
    -------
    Callable[[Dict], float]
        单段评分函数, 可直接传给 :func:`bayesian.bayesian_score_distribution`。
    """
    X, keys = _extract_matrix(segments)
    directions = [f["direction"] for f in config.MCDM_FEATURES]

    # 每列的全局 min/max (归一化基准)
    cmin = np.min(X, axis=0)
    cmax = np.max(X, axis=0)
    rng = cmax - cmin

    w = np.array([weights.get(k, 0.0) for k in keys], dtype=float)
    wsum = float(np.sum(w))
    if wsum > 0.0:
        w = w / wsum

    # 用全局基准拟合全数据集, 得到固定 PIS/NIS
    def _normalize_row(row: np.ndarray) -> np.ndarray:
        z = np.zeros_like(row)
        for j in range(len(row)):
            if rng[j] <= 0.0:
                z[j] = 0.0
                continue
            if directions[j] == "+":
                z[j] = (row[j] - cmin[j]) / rng[j]
            else:
                z[j] = (cmax[j] - row[j]) / rng[j]
        return z

    Z_full = np.zeros_like(X)
    for i in range(X.shape[0]):
        Z_full[i, :] = _normalize_row(X[i, :])
    V_full = Z_full * w[np.newaxis, :]
    v_pos = np.max(V_full, axis=0)
    v_neg = np.min(V_full, axis=0)

    def score_fn(segment: Dict) -> float:
        row = np.zeros(len(keys), dtype=float)
        for j, key in enumerate(keys):
            v = segment.get(key, 0)
            if v is None:
                v = 0.0
            try:
                fv = float(v)
            except (TypeError, ValueError):
                fv = 0.0
            if not math.isfinite(fv):
                fv = 0.0
            row[j] = fv
        z = _normalize_row(row)
        v = z * w
        d_pos = float(np.sqrt(np.sum((v - v_pos) ** 2)))
        d_neg = float(np.sqrt(np.sum((v - v_neg) ** 2)))
        denom = d_pos + d_neg
        if denom <= 0.0:
            c = 1.0
        else:
            c = d_neg / denom
        s = 100.0 * c
        if not math.isfinite(s):
            s = 0.0
        return float(max(0.0, min(100.0, s)))

    return score_fn
