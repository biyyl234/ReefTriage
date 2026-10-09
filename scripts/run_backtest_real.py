"""
scripts/run_backtest_real.py
============================
ReefTriage 模型严格回测框架 -- 真实 Laya 引擎版 (live, CPU)。

与 run_backtest.py 的区别:
  1. LayaClient 使用 base_url=http://127.0.0.1:5000 (真实服务), 而非 force_mock=True
  2. meta.laya_mode 标注为 "real Laya (live, CPU)"
  3. 运行时 monkeypatch rubric_v2.build_questions_v2, 过滤掉缺少 criteria 的 dim_*
     子问题 (Laya 服务端对 score 类型问题强制要求 criteria 列表, 否则 500)。
     fusion.compute_laya_scores 只读取 answers["priority_score"], dim_* 不影响结果。

回测会调用真实 Laya 约 112 次 (28段 x 2时期 x 2模型对比), CPU 模式每次约1秒,
总耗时约 3-8 分钟。

输出: data/output/backtest_results.json (覆盖旧 mock 版)
"""

from __future__ import annotations

import json
import os
import sys
import copy
import logging
from typing import Any, Dict, List, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# 路径设置
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.scoring import config
from app.scoring import data_loader
from app.scoring import fusion
from app.scoring import mcdm
from app.scoring import ml_predictor
from app.scoring import threshold as th_mod
from app.scoring import rubric as rubric_v1
from app.scoring import rhi as rhi_mod
from app.scoring import rubric_v2 as _rubric_v2
from app.scoring.laya_client import LayaClient

# --- Monkeypatch: 去掉 rubric_v2 中缺少 criteria 的 dim_* 子问题 ---
_orig_build_questions_v2 = _rubric_v2.build_questions_v2
def _patched_build_questions_v2():
    qs = _orig_build_questions_v2()
    return {k: v for k, v in qs.items() if not k.startswith("dim_")}
_rubric_v2.build_questions_v2 = _patched_build_questions_v2

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger("run_backtest_real")

RANDOM_SEED = 42
ALPHA_GRID = [round(0.3 + 0.05 * i, 2) for i in range(9)]  # 0.30 .. 0.70
BOOTSTRAP_N = config.BACKTEST_BOOTSTRAP_N
DHW_POSITIVE_THRESHOLD = config.BLEACHING_DHW_THRESHOLD  # 4.0

PERIOD_2020 = {"year": 2020, "month_start": 3, "month_end": 6, "label": "2020"}
PERIOD_2024 = {"year": 2024, "month_start": 3, "month_end": 6, "label": "2024"}


# ===========================================================================
# 1. 数据准备
# ===========================================================================

def prepare_period_segments(
    base_segments: List[Dict[str, Any]],
    dhw_map: Dict[str, float],
) -> List[Dict[str, Any]]:
    out = []
    for s in base_segments:
        s2 = dict(s)
        sid = s2["segment_id"]
        s2["current_dhw"] = float(dhw_map.get(sid, 0.0))
        out.append(s2)
    return out


def make_labels(segments: List[Dict[str, Any]]) -> List[int]:
    return [1 if float(s.get("current_dhw", 0.0)) >= DHW_POSITIVE_THRESHOLD else 0
            for s in segments]


# ===========================================================================
# 2. 新模型评分 (三层融合)
# ===========================================================================

def score_period_new(
    period_segments: List[Dict[str, Any]],
    laya: LayaClient,
) -> Dict[str, Any]:
    bleach_probs = fusion.compute_bleaching_probs(period_segments)

    enriched = []
    for i, s in enumerate(period_segments):
        s2 = dict(s)
        s2["bleaching_probability"] = float(bleach_probs[i])
        enriched.append(s2)

    mcdm_scores, weights = mcdm.compute_mcdm(enriched)
    laya_scores = fusion.compute_laya_scores(enriched, laya, use_v2=True)
    labels = make_labels(period_segments)

    return {
        "enriched": enriched,
        "mcdm_scores": mcdm_scores,
        "laya_scores": laya_scores,
        "weights": weights,
        "bleach_probs": [float(p) for p in bleach_probs],
        "labels": labels,
    }


def fuse_at_alpha(
    mcdm_scores: List[float],
    laya_scores: List[float],
    alpha: float,
) -> List[float]:
    return fusion.fuse_scores(mcdm_scores, laya_scores, alpha)


# ===========================================================================
# 3. 旧模型评分 (纯 Laya v1 + 硬编码阈值 55/40)
# ===========================================================================

def score_period_old(
    period_segments: List[Dict[str, Any]],
    laya: LayaClient,
) -> Dict[str, Any]:
    from app.scoring.engine import _estimate_rhi_proxies

    scores: List[float] = []
    choices: List[str] = []
    for s in period_segments:
        proxies = _estimate_rhi_proxies(s)
        rhi_score = rhi_mod.compute_simplified_rhi(proxies)
        feats = dict(s)
        feats["rhi_score"] = rhi_score
        feats["historical_mortality"] = None

        state = rubric_v1.build_state(feats)
        questions = rubric_v1.build_questions()
        resp = laya.predict(state, questions)
        ps = resp.get("answers", {}).get("priority_score", {})
        raw = float(ps.get("score", 2.0))
        score = ps.get("raw_score_0_100") or rubric_v1.interpret_score(raw)
        score = float(int(round(score)))
        choice = ("invest" if score >= config.DEFAULT_THRESHOLD_INVEST
                  else "monitor" if score >= config.DEFAULT_THRESHOLD_MONITOR
                  else "deprioritize")
        scores.append(score)
        choices.append(choice)

    labels = make_labels(period_segments)
    return {"scores": scores, "choices": choices, "labels": labels}


# ===========================================================================
# 4. 指标计算
# ===========================================================================

def compute_auc(scores: List[float], labels: List[int]) -> float:
    roc = th_mod.compute_roc(scores, labels)
    a = roc.get("auc", float("nan"))
    return float(a) if a is not None and not np.isnan(a) else float("nan")


def precision_recall_f1_at_threshold(
    scores: List[float], labels: List[int], threshold: float,
) -> Dict[str, float]:
    y_pred = [1 if s >= threshold else 0 for s in scores]
    y_true = list(labels)
    tp = sum(1 for p, t in zip(y_pred, y_true) if p == 1 and t == 1)
    fp = sum(1 for p, t in zip(y_pred, y_true) if p == 1 and t == 0)
    fn = sum(1 for p, t in zip(y_pred, y_true) if p == 0 and t == 1)
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    return {"threshold": float(threshold), "precision": round(prec, 4),
            "recall": round(rec, 4), "f1": round(f1, 4),
            "tp": tp, "fp": fp, "fn": fn}


def hit_rate_at_threshold(
    scores: List[float], labels: List[int], threshold: float,
) -> Tuple[float, int, int]:
    invest_idx = [i for i, s in enumerate(scores) if s >= threshold]
    if not invest_idx:
        return 0.0, 0, 0
    hits = sum(1 for i in invest_idx if labels[i] == 1)
    return hits / len(invest_idx), len(invest_idx), hits


def bootstrap_hit_rate_ci(
    scores: List[float], labels: List[int], threshold: float,
    n_bootstrap: int = BOOTSTRAP_N, seed: int = RANDOM_SEED,
) -> Dict[str, float]:
    rng = np.random.default_rng(seed)
    s = np.asarray(scores, dtype=float)
    y = np.asarray(labels, dtype=int)
    n = len(s)
    rates: List[float] = []
    for _ in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        s_b = s[idx]
        y_b = y[idx]
        invest_mask = s_b >= threshold
        n_invest = int(invest_mask.sum())
        if n_invest == 0:
            continue
        hit = int(y_b[invest_mask].sum())
        rates.append(hit / n_invest)
    if not rates:
        return {"mean": float("nan"), "ci_lower": float("nan"),
                "ci_upper": float("nan"), "n_used": 0}
    arr = np.asarray(rates)
    return {
        "mean": round(float(np.mean(arr)), 4),
        "ci_lower": round(float(np.percentile(arr, 2.5)), 4),
        "ci_upper": round(float(np.percentile(arr, 97.5)), 4),
        "n_used": len(rates),
    }


# ===========================================================================
# 5. α 网格搜索
# ===========================================================================

def grid_search_alpha(
    mcdm_scores: List[float], laya_scores: List[float], labels: List[int],
) -> Tuple[float, List[Dict[str, float]]]:
    results = []
    best_alpha = ALPHA_GRID[0]
    best_auc = -1.0
    for a in ALPHA_GRID:
        final = fuse_at_alpha(mcdm_scores, laya_scores, a)
        auc = compute_auc(final, labels)
        results.append({"alpha": a, "auc": round(auc, 4)})
        if not np.isnan(auc) and auc > best_auc:
            best_auc = auc
            best_alpha = a
    return best_alpha, results


# ===========================================================================
# 6. 消融实验
# ===========================================================================

def ablation_study(
    enriched: List[Dict[str, Any]],
    laya_scores: List[float],
    labels: List[int],
    alpha: float,
) -> List[Dict[str, Any]]:
    baseline_scores = mcdm.topsis_score(
        enriched, mcdm.entropy_weights(enriched)
    )
    baseline_final = fuse_at_alpha(baseline_scores, laya_scores, alpha)
    baseline_auc = compute_auc(baseline_final, labels)

    feature_keys = [f["key"] for f in config.MCDM_FEATURES]
    out = []
    for key in feature_keys:
        ablated = []
        for s in enriched:
            s2 = dict(s)
            s2[key] = 0.0
            ablated.append(s2)
        w = mcdm.entropy_weights(ablated)
        abl_scores = mcdm.topsis_score(ablated, w)
        abl_final = fuse_at_alpha(abl_scores, laya_scores, alpha)
        abl_auc = compute_auc(abl_final, labels)
        delta = abl_auc - baseline_auc if not np.isnan(abl_auc) and not np.isnan(baseline_auc) else float("nan")
        out.append({
            "feature": key,
            "ablated_auc": round(float(abl_auc), 4) if not np.isnan(abl_auc) else None,
            "delta_auc": round(float(delta), 4) if not np.isnan(delta) else None,
        })
    out.sort(key=lambda x: (x["delta_auc"] if x["delta_auc"] is not None else 0))
    return out


# ===========================================================================
# 主流程
# ===========================================================================

def main() -> None:
    print("=" * 72)
    print("ReefTriage 回测框架 (真实 Laya live/CPU, walk-forward + ROC/AUC)")
    print("=" * 72)

    np.random.seed(RANDOM_SEED)

    laya = LayaClient(base_url="http://127.0.0.1:5000")
    print(f"\n[Laya] base_url=http://127.0.0.1:5000, is_mock={laya.is_mock}")
    # 触发一次 endpoint 探测
    ep = laya._resolve_endpoint()
    print(f"[Laya] resolved endpoint: {ep}, available: {laya._available}")

    # ---- 加载数据 ----
    print("\n[1/7] 加载礁段数据与历史 DHW ...")
    base_segs = data_loader.load_reef_segments()
    print(f"  加载 {len(base_segs)} 个礁段")

    dhw_2020 = data_loader.extract_dhw_at_period(
        PERIOD_2020["year"], PERIOD_2020["month_start"], PERIOD_2020["month_end"])
    dhw_2024 = data_loader.extract_dhw_at_period(
        PERIOD_2024["year"], PERIOD_2024["month_start"], PERIOD_2024["month_end"])
    print(f"  2020 时期 DHW: {len(dhw_2020)} 段, 正标签(DHW>=4)={sum(1 for v in dhw_2020.values() if v>=4)}")
    print(f"  2024 时期 DHW: {len(dhw_2024)} 段, 正标签(DHW>=4)={sum(1 for v in dhw_2024.values() if v>=4)}")

    segs_2020 = prepare_period_segments(base_segs, dhw_2020)
    segs_2024 = prepare_period_segments(base_segs, dhw_2024)

    # ---- 训练 ML 模型 ----
    print("\n[2/7] 训练 ML 白化概率预测器 (Logistic Regression) ...")
    fusion.reset_caches()
    fusion.compute_bleaching_probs(base_segs)
    ml_info = fusion.get_ml_model_info()
    ml_coef = ml_info["coef"] if ml_info else {}
    ml_metrics = ml_info["metrics"] if ml_info else {}
    print(f"  ML 训练样本: {ml_info.get('train_size','?')} train / {ml_info.get('test_size','?')} test")
    print(f"  ML 测试 AUC: {ml_metrics.get('auc')}")
    print(f"  ML 特征系数 (绝对值排序):")
    for k, v in sorted(ml_coef.items(), key=lambda kv: -abs(kv[1])):
        print(f"    {k:35s} {v:+.4f}")

    # ---- 对两个时期分别评分 (新模型, 真实 Laya) ----
    print("\n[3/7] 对两个时期运行三层融合评分 (真实 Laya, 约 56 次调用) ...")
    res_2020 = score_period_new(segs_2020, laya)
    res_2024 = score_period_new(segs_2024, laya)

    n_pos_2020 = sum(res_2020["labels"])
    n_pos_2024 = sum(res_2024["labels"])
    print(f"  2020: mcdm [{min(res_2020['mcdm_scores']):.1f}, {max(res_2020['mcdm_scores']):.1f}], "
          f"laya 唯一值={sorted(set(round(x,1) for x in res_2020['laya_scores']))}, 正标签={n_pos_2020}/{len(res_2020['labels'])}")
    print(f"  2024: mcdm [{min(res_2024['mcdm_scores']):.1f}, {max(res_2024['mcdm_scores']):.1f}], "
          f"laya 唯一值={sorted(set(round(x,1) for x in res_2024['laya_scores']))}, 正标签={n_pos_2024}/{len(res_2024['labels'])}")

    entropy_weights = res_2020["weights"]
    print(f"\n  熵权法权重 (2020 时期, 排序):")
    for k, v in sorted(entropy_weights.items(), key=lambda kv: -kv[1]):
        print(f"    {k:40s} {v:.4f}")

    # ---- Walk-forward α 优化 ----
    print("\n[4/7] Walk-forward α 优化 (网格搜索 0.30..0.70, 步长 0.05) ...")

    best_alpha_A, grid_A = grid_search_alpha(
        res_2020["mcdm_scores"], res_2020["laya_scores"], res_2020["labels"])
    final_2020_at_A = fuse_at_alpha(res_2020["mcdm_scores"], res_2020["laya_scores"], best_alpha_A)
    final_2024_at_A = fuse_at_alpha(res_2024["mcdm_scores"], res_2024["laya_scores"], best_alpha_A)
    auc_train_A = compute_auc(final_2020_at_A, res_2020["labels"])
    auc_val_A = compute_auc(final_2024_at_A, res_2024["labels"])

    print(f"\n  方向 A: 训练=2020, 验证=2024")
    for r in grid_A:
        mark = " <-- best" if r["alpha"] == best_alpha_A else ""
        print(f"    α={r['alpha']:.2f}  AUC={r['auc']:.4f}{mark}")
    print(f"    最优 α = {best_alpha_A:.2f}")
    print(f"    训练期 (2020) AUC = {auc_train_A:.4f}")
    print(f"    验证期 (2024) AUC = {auc_val_A:.4f}")

    best_alpha_B, grid_B = grid_search_alpha(
        res_2024["mcdm_scores"], res_2024["laya_scores"], res_2024["labels"])
    final_2024_at_B = fuse_at_alpha(res_2024["mcdm_scores"], res_2024["laya_scores"], best_alpha_B)
    final_2020_at_B = fuse_at_alpha(res_2020["mcdm_scores"], res_2020["laya_scores"], best_alpha_B)
    auc_train_B = compute_auc(final_2024_at_B, res_2024["labels"])
    auc_val_B = compute_auc(final_2020_at_B, res_2020["labels"])

    print(f"\n  方向 B: 训练=2024, 验证=2020")
    for r in grid_B:
        mark = " <-- best" if r["alpha"] == best_alpha_B else ""
        print(f"    α={r['alpha']:.2f}  AUC={r['auc']:.4f}{mark}")
    print(f"    最优 α = {best_alpha_B:.2f}")
    print(f"    训练期 (2024) AUC = {auc_train_B:.4f}")
    print(f"    验证期 (2020) AUC = {auc_val_B:.4f}")

    final_alpha = round(float(np.clip(
        (best_alpha_A + best_alpha_B) / 2.0,
        config.FUSION_ALPHA_MIN, config.FUSION_ALPHA_MAX)), 2)
    print(f"\n  >>> 综合最优 α = {final_alpha:.2f} (两方向均值)")

    # ---- ROC/AUC + 阈值优化 ----
    print("\n[5/7] ROC/AUC 与阈值优化 (Youden's J + bootstrap CI) ...")

    all_final = (fuse_at_alpha(res_2020["mcdm_scores"], res_2020["laya_scores"], final_alpha)
                 + fuse_at_alpha(res_2024["mcdm_scores"], res_2024["laya_scores"], final_alpha))
    all_labels = res_2020["labels"] + res_2024["labels"]

    roc_all = th_mod.compute_roc(all_final, all_labels)
    auc_all = roc_all["auc"]
    youden_all = th_mod.optimal_threshold_youden(all_final, all_labels)
    thr_ci_all = th_mod.bootstrap_threshold_ci(all_final, all_labels,
                                               n_bootstrap=BOOTSTRAP_N, seed=RANDOM_SEED)
    thr_ci_n_used = len(thr_ci_all.get("all_thresholds", []))

    opt_thr = youden_all["threshold"]
    print(f"  合并 AUC (n={len(all_labels)}, 正={sum(all_labels)}): {auc_all:.4f}")
    print(f"  Youden's J 最优阈值: {opt_thr:.2f}  (J={youden_all['youden_j']:.4f}, "
          f"敏感度={youden_all['sensitivity']:.4f}, 特异度={youden_all['specificity']:.4f})")
    print(f"  Bootstrap 阈值 95% CI: [{thr_ci_all['ci_lower']:.2f}, {thr_ci_all['ci_upper']:.2f}] "
          f"(mean={thr_ci_all['mean']:.2f}, 有效重采样={thr_ci_n_used})")

    print(f"\n  多阈值 precision/recall/F1 (合并数据):")
    threshold_points = sorted(set(
        [30, 35, 40, 45, 50, 55, 60] + [round(opt_thr, 1)]))
    prf_table = []
    for t in threshold_points:
        m = precision_recall_f1_at_threshold(all_final, all_labels, t)
        prf_table.append(m)
        print(f"    thr={t:5.1f}  P={m['precision']:.3f}  R={m['recall']:.3f}  F1={m['f1']:.3f}  "
              f"(TP={m['tp']}, FP={m['fp']}, FN={m['fn']})")

    hit_ci = bootstrap_hit_rate_ci(all_final, all_labels, opt_thr,
                                  n_bootstrap=BOOTSTRAP_N, seed=RANDOM_SEED)
    hit_rate, invest_n, hit_n = hit_rate_at_threshold(all_final, all_labels, opt_thr)
    print(f"\n  invest 命中率 (阈值={opt_thr:.2f}): {hit_n}/{invest_n} = {hit_rate*100:.1f}%")
    print(f"  Bootstrap 命中率 95% CI: [{hit_ci['ci_lower']*100:.1f}%, {hit_ci['ci_upper']*100:.1f}%] "
          f"(mean={hit_ci['mean']*100:.1f}%)")

    # ---- 消融实验 ----
    print("\n[6/7] 消融实验 (逐个移除 MCDM 特征, 2020 时期, α={:.2f}) ...".format(final_alpha))
    ablation = ablation_study(res_2020["enriched"], res_2020["laya_scores"],
                              res_2020["labels"], final_alpha)
    baseline_auc_2020 = compute_auc(
        fuse_at_alpha(res_2020["mcdm_scores"], res_2020["laya_scores"], final_alpha),
        res_2020["labels"])
    print(f"  基线 AUC (全部特征) = {baseline_auc_2020:.4f}")
    for row in ablation:
        delta_str = f"{row['delta_auc']:+.4f}" if row["delta_auc"] is not None else "N/A"
        auc_str = f"{row['ablated_auc']:.4f}" if row["ablated_auc"] is not None else "N/A"
        print(f"  {row['feature']:40s} {auc_str:>12s} {delta_str:>10s}")

    # ---- 新旧模型对比 (旧模型也用真实 Laya v1) ----
    print("\n[7/7] 新旧模型对比 (旧模型也调用真实 Laya v1, 约 56 次调用) ...")
    old_2020 = score_period_old(segs_2020, laya)
    old_2024 = score_period_old(segs_2024, laya)

    def old_stats(old_res, period_label):
        s = old_res["scores"]
        y = old_res["labels"]
        choices = old_res["choices"]
        auc = compute_auc(s, y)
        invest_n = sum(1 for c in choices if c == "invest")
        avg_score = float(np.mean(s))
        invest_idx = [i for i, c in enumerate(choices) if c == "invest"]
        hits = sum(1 for i in invest_idx if y[i] == 1)
        hr = hits / len(invest_idx) if invest_idx else 0.0
        return {
            "period": period_label,
            "auc": round(float(auc), 4) if not np.isnan(auc) else None,
            "invest_count": invest_n,
            "avg_score": round(avg_score, 2),
            "hit_rate": round(hr, 4),
            "invest_hits": hits,
            "invest_total": len(invest_idx),
        }

    def new_stats(mcdm_s, laya_s, labels, alpha, thr, period_label):
        final = fuse_at_alpha(mcdm_s, laya_s, alpha)
        auc = compute_auc(final, labels)
        invest_idx = [i for i, s in enumerate(final) if s >= thr]
        hits = sum(1 for i in invest_idx if labels[i] == 1)
        hr = hits / len(invest_idx) if invest_idx else 0.0
        return {
            "period": period_label,
            "auc": round(float(auc), 4) if not np.isnan(auc) else None,
            "invest_count": len(invest_idx),
            "avg_score": round(float(np.mean(final)), 2),
            "hit_rate": round(hr, 4),
            "invest_hits": hits,
            "invest_total": len(invest_idx),
        }

    old_stats_2020 = old_stats(old_2020, "2020")
    old_stats_2024 = old_stats(old_2024, "2024")
    new_stats_2020 = new_stats(res_2020["mcdm_scores"], res_2020["laya_scores"],
                               res_2020["labels"], final_alpha, opt_thr, "2020")
    new_stats_2024 = new_stats(res_2024["mcdm_scores"], res_2024["laya_scores"],
                               res_2024["labels"], final_alpha, opt_thr, "2024")

    print(f"\n  {'指标':20s} {'旧模型(2020)':>15s} {'新模型(2020)':>15s} {'旧模型(2024)':>15s} {'新模型(2024)':>15s}")
    print(f"  {'-'*82}")
    print(f"  {'AUC':20s} {old_stats_2020['auc']:>15} {new_stats_2020['auc']:>15} "
          f"{old_stats_2024['auc']:>15} {new_stats_2024['auc']:>15}")
    print(f"  {'invest 数量':20s} {old_stats_2020['invest_count']:>15} {new_stats_2020['invest_count']:>15} "
          f"{old_stats_2024['invest_count']:>15} {new_stats_2024['invest_count']:>15}")
    print(f"  {'平均分':20s} {old_stats_2020['avg_score']:>15} {new_stats_2020['avg_score']:>15} "
          f"{old_stats_2024['avg_score']:>15} {new_stats_2024['avg_score']:>15}")
    print(f"  {'命中率':20s} {old_stats_2020['hit_rate']:>15.4f} {new_stats_2020['hit_rate']:>15.4f} "
          f"{old_stats_2024['hit_rate']:>15.4f} {new_stats_2024['hit_rate']:>15.4f}")

    # ---- 保存 ----
    print("\n[保存] 写入 data/output/backtest_results.json ...")
    results_payload = {
        "meta": {
            "seed": RANDOM_SEED,
            "laya_mode": "real Laya (live, CPU)",
            "laya_endpoint": laya._endpoint,
            "n_segments": len(base_segs),
            "dhw_positive_threshold": DHW_POSITIVE_THRESHOLD,
            "bootstrap_n": BOOTSTRAP_N,
            "alpha_grid": ALPHA_GRID,
            "period_2020": PERIOD_2020,
            "period_2024": PERIOD_2024,
        },
        "ml_model": {
            "train_size": ml_info.get("train_size") if ml_info else None,
            "test_size": ml_info.get("test_size") if ml_info else None,
            "metrics": ml_metrics,
            "coefficients": ml_coef,
        },
        "entropy_weights_2020": entropy_weights,
        "walk_forward": {
            "direction_A_train2020_val2024": {
                "best_alpha": best_alpha_A,
                "grid": grid_A,
                "train_auc": round(auc_train_A, 4),
                "val_auc": round(auc_val_A, 4),
            },
            "direction_B_train2024_val2020": {
                "best_alpha": best_alpha_B,
                "grid": grid_B,
                "train_auc": round(auc_train_B, 4),
                "val_auc": round(auc_val_B, 4),
            },
            "final_alpha": final_alpha,
        },
        "roc_threshold": {
            "merged_auc": round(auc_all, 4),
            "n_total": len(all_labels),
            "n_positive": int(sum(all_labels)),
            "youden": {
                "threshold": round(youden_all["threshold"], 2),
                "youden_j": round(youden_all["youden_j"], 4),
                "sensitivity": round(youden_all["sensitivity"], 4),
                "specificity": round(youden_all["specificity"], 4),
            },
            "threshold_bootstrap_ci": {
                "mean": round(thr_ci_all["mean"], 2),
                "ci_lower": round(thr_ci_all["ci_lower"], 2),
                "ci_upper": round(thr_ci_all["ci_upper"], 2),
                "n_used": thr_ci_n_used,
            },
            "precision_recall_f1": prf_table,
        },
        "hit_rate": {
            "threshold": round(opt_thr, 2),
            "hit_rate": round(hit_rate, 4),
            "invest_count": invest_n,
            "hit_count": hit_n,
            "bootstrap_ci": hit_ci,
        },
        "ablation": {
            "baseline_auc_2020": round(baseline_auc_2020, 4),
            "results": ablation,
        },
        "old_vs_new": {
            "old_model_description": "Pure Laya v1 rubric + hardcoded thresholds (invest>=55, monitor>=40)",
            "new_model_description": f"Three-layer fusion (ML+MCDM+Laya v2) + Youden threshold={opt_thr:.2f}, alpha={final_alpha}",
            "old_2020": old_stats_2020,
            "old_2024": old_stats_2024,
            "new_2020": new_stats_2020,
            "new_2024": new_stats_2024,
        },
    }

    out_dir = os.path.join(PROJECT_ROOT, "data", "output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "backtest_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results_payload, f, ensure_ascii=False, indent=2, default=str)
    print(f"  已保存: {out_path}")

    print("\n" + "=" * 72)
    print("回测完成 (真实 Laya live/CPU)。")
    print("=" * 72)


if __name__ == "__main__":
    main()
