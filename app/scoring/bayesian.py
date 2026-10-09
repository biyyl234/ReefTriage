"""
app/scoring/bayesian.py
========================
贝叶斯不确定性量化 (Model D): 蒙特卡洛 (Monte Carlo) 置信区间。

原理
----
对评分函数 score_fn 输入的若干关键特征, 按 config.BAYESIAN_NOISE 给定的
相对标准差 σ_j 施加乘性高斯噪声:

    x_j^{(t)} = x_j · (1 + σ_j · ε),   ε ~ N(0, 1)

每次采样得到一个带噪 segment, 调用 score_fn 得到一个 0-100 分数。
重复 n_samples 次后, 用样本均值作为点估计, 用 2.5% / 97.5% 分位数作为
95% 置信区间。

score_fn 由调用方注入 (可以是 MCDM 得分, 也可以是融合后的 final_score),
本模块不假设具体评分模型, 仅负责扰动输入并统计输出分布。

仅依赖 numpy 与标准库。
"""

from __future__ import annotations

import copy
from typing import Callable, Dict, List

import numpy as np

from . import config


# score_fn 签名: 输入 segment dict, 输出 0-100 分数
ScoreFn = Callable[[Dict], float]


def _perturb_segment(segment: Dict, noise: Dict[str, float],
                     rng: np.random.Generator) -> Dict:
    """对 segment 深拷贝后, 对 noise 中声明的特征施加乘性高斯噪声。

    - 若原字段缺失或非数值, 跳过该字段 (保持原值)。
    - 噪声后的值若为 NaN/Inf, 回退为原值。
    - 对非负特征 (DHW、深度、面积、距离、概率等) 截断到 >= 0。
    """
    seg = copy.deepcopy(segment)
    for key, sigma in noise.items():
        v = seg.get(key, None)
        if v is None:
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(fv):
            continue
        eps = float(rng.normal(0.0, 1.0))
        noisy = fv * (1.0 + sigma * eps)
        if not np.isfinite(noisy):
            noisy = fv
        # 物理上非负的量 (DHW / 深度 / 面积 / 距离 / 概率) 截断
        if noisy < 0.0:
            noisy = 0.0
        # 概率类字段截断到 [0, 1]
        if key == "bleaching_probability" and noisy > 1.0:
            noisy = 1.0
        seg[key] = noisy
    return seg


def bayesian_score_distribution(
    segment: Dict,
    score_fn: ScoreFn,
    n_samples: int = config.BAYESIAN_N_SAMPLES,
    rng: np.random.Generator | None = None,
) -> Dict:
    """对单个礁段做蒙特卡洛采样, 返回评分分布统计。

    Parameters
    ----------
    segment : Dict
        礁段原始数据。
    score_fn : Callable[[Dict], float]
        评分函数, 输入一个 segment dict, 输出 0-100 分数。
    n_samples : int
        蒙特卡洛采样次数, 默认 config.BAYESIAN_N_SAMPLES。
    rng : np.random.Generator, optional
        随机数生成器; 不传则新建一个 (不可复现)。

    Returns
    -------
    Dict
        {
          "mean": float,        # 样本均值
          "std": float,         # 样本标准差 (ddof=1)
          "ci_lower": float,    # 2.5% 分位数
          "ci_upper": float,    # 97.5% 分位数
          "samples": List[float]
        }
    """
    if rng is None:
        rng = np.random.default_rng()

    noise = config.BAYESIAN_NOISE
    samples: List[float] = []
    for _ in range(int(n_samples)):
        perturbed = _perturb_segment(segment, noise, rng)
        s = float(score_fn(perturbed))
        if not np.isfinite(s):
            s = 0.0
        samples.append(s)

    arr = np.asarray(samples, dtype=float)
    mean = float(np.mean(arr))
    # n_samples < 2 时 ddof=1 会得 NaN, 防御
    if arr.size >= 2:
        std = float(np.std(arr, ddof=1))
    else:
        std = 0.0
    ci_lower = float(np.percentile(arr, 2.5))
    ci_upper = float(np.percentile(arr, 97.5))

    return {
        "mean": mean,
        "std": std,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "samples": samples,
    }


def compute_bayesian_for_all(
    segments: List[Dict],
    score_fn: ScoreFn,
    n_samples: int = config.BAYESIAN_N_SAMPLES,
    seed: int | None = None,
) -> List[Dict]:
    """对全部礁段批量做贝叶斯不确定性分析。

    Parameters
    ----------
    segments : List[Dict]
        礁段列表。
    score_fn : Callable[[Dict], float]
        评分函数。
    n_samples : int
        每个礁段的采样次数。
    seed : int, optional
        随机种子, 传入以保证可复现。

    Returns
    -------
    List[Dict]
        与 segments 等长, 每个元素为 :func:`bayesian_score_distribution` 的输出。
    """
    rng = np.random.default_rng(seed)
    results: List[Dict] = []
    for seg in segments:
        res = bayesian_score_distribution(seg, score_fn,
                                          n_samples=n_samples, rng=rng)
        results.append(res)
    return results
