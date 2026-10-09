"""
app/services/report_service.py
==============================
ReefTriage 报告生成服务。

- generate_segment_report(segment_id): 单礁段完整报告
- generate_region_report(segment_ids): 多礁段汇总报告

数据来源:
- scored_segments.json (via engine.all_scored())
- data/output/environmental/{id}.json
- data/output/monitoring/{id}.json
"""

from __future__ import annotations
import os
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..scoring.engine import engine
from ..scoring import fusion

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)
ENV_DIR = os.path.join(PROJECT_ROOT, "data", "output", "environmental")
MONITOR_DIR = os.path.join(PROJECT_ROOT, "data", "output", "monitoring")


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def _read_json(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read %s: %s", path, e)
        return None


def _find_segment(segment_id: str) -> Optional[Dict[str, Any]]:
    for s in engine.all_scored():
        if s.get("segment_id") == segment_id:
            return s
    return None


def _to_float(v: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# 推荐语规则生成
# ---------------------------------------------------------------------------
def _build_recommendation(choice: str,
                          bleaching_probability: Optional[float],
                          rhi_score: Optional[float],
                          dhw_max: Optional[float]) -> Dict[str, str]:
    """
    根据 choice + 白化概率 + RHI 生成中英双语建议。
    """
    p = bleaching_probability if bleaching_probability is not None else 0.0
    rhi = rhi_score if rhi_score is not None else 0.0

    p_level = "high" if p >= 0.6 else ("medium" if p >= 0.35 else "low")
    rhi_level = "low" if rhi < 50 else ("medium" if rhi < 70 else "high")

    # 中文
    zh_p = {
        "high": "白化概率较高",
        "medium": "白化概率中等",
        "low": "白化概率较低",
    }[p_level]
    zh_rhi = {
        "low": "生态健康状况较差, 恢复窗口期有限",
        "medium": "生态健康状况中等, 恢复潜力尚可",
        "high": "生态健康状况良好, 恢复潜力较高",
    }[rhi_level]

    if choice == "invest":
        zh = (f"建议优先投入恢复行动。{zh_p} ({p*100:.0f}%), "
              f"{zh_rhi}。建议立即启动珊瑚育苗/移植工程, "
              f"并加强热季监测, 优先保障幼体补充连通性。")
    elif choice == "monitor":
        zh = (f"建议加强监测, 暂不投入大规模恢复。{zh_p} ({p*100:.0f}%), "
              f"{zh_rhi}。建议每季度复查白化覆盖度与 DHW 演变, "
              f"若热压力持续上升则升级为优先投入。")
    else:
        zh = (f"建议降级处置, 资源优先分配给更高优先级礁段。"
              f"{zh_p} ({p*100:.0f}%), {zh_rhi}。"
              f"可作为对照礁进行长期观测, 暂不安排主动恢复工程。")

    # English
    en_p = {
        "high": "high bleaching probability",
        "medium": "moderate bleaching probability",
        "low": "low bleaching probability",
    }[p_level]
    en_rhi = {
        "low": "ecological health is poor, recovery window is limited",
        "medium": "ecological health is moderate, recovery potential is fair",
        "high": "ecological health is good, recovery potential is high",
    }[rhi_level]

    if choice == "invest":
        en = (f"Recommend PRIORITIZED restoration action. "
              f"{en_p} ({p*100:.0f}%); {en_rhi}. "
              f"Initiate coral gardening/outplanting immediately and intensify "
              f"thermal-season monitoring; prioritize larval connectivity.")
    elif choice == "monitor":
        en = (f"Recommend MONITORING, defer large-scale restoration. "
              f"{en_p} ({p*100:.0f}%); {en_rhi}. "
              f"Re-survey bleaching cover and DHW quarterly; escalate to "
              f"invest if thermal stress keeps rising.")
    else:
        en = (f"Recommend DEPRIORITIZE; reallocate budget to higher-priority reefs. "
              f"{en_p} ({p*100:.0f}%); {en_rhi}. "
              f"Use as a long-term reference reef; no active restoration for now.")

    return {"zh": zh, "en": en,
            "choice_zh": {"invest": "优先投入", "monitor": "加强监测",
                          "deprioritize": "降级处置"}.get(choice, "—"),
            "choice_en": {"invest": "Invest", "monitor": "Monitor",
                          "deprioritize": "Deprioritize"}.get(choice, "—")}


# ---------------------------------------------------------------------------
# 单礁段报告
# ---------------------------------------------------------------------------
def generate_segment_report(segment_id: str) -> Optional[Dict[str, Any]]:
    seg = _find_segment(segment_id)
    if seg is None:
        return None

    env = _read_json(os.path.join(ENV_DIR, f"{segment_id}.json")) or {}
    mon = _read_json(os.path.join(MONITOR_DIR, f"{segment_id}.json")) or {}

    # --- basic_info ---
    basic_info = {
        "lat": _to_float(seg.get("lat")),
        "lon": _to_float(seg.get("lon")),
        "mean_depth": _to_float(seg.get("mean_depth")),
        "reef_area": _to_float(seg.get("reef_area_km2")),
        "group": env.get("group") or seg.get("group"),
    }

    # --- scoring ---
    ci = seg.get("confidence_interval") or {}
    ci_lower = _to_float(ci.get("ci_lower"))
    ci_upper = _to_float(ci.get("ci_upper"))
    # 触发权重计算 (若缓存未命中), 复用 engine 的回退逻辑
    try:
        feature_weights = (engine.model_weights() or {}).get("weights", {}) or {}
    except Exception as e:
        logger.warning("feature_weights unavailable: %s", e)
        feature_weights = {}

    scoring = {
        "final_score": _to_float(seg.get("final_score"), _to_float(seg.get("score"), 0.0)),
        "choice": seg.get("choice", "monitor"),
        "mcdm_score": _to_float(seg.get("mcdm_score")),
        "laya_score": _to_float(seg.get("laya_score")),
        "bleaching_probability": _to_float(seg.get("bleaching_probability")),
        "confidence_interval": [ci_lower, ci_upper] if ci_lower is not None and ci_upper is not None else None,
        "alpha": _to_float(seg.get("alpha")),
        "feature_weights": feature_weights,
        "model": seg.get("model"),
        "manual_override": bool(seg.get("manual_override", False)),
    }

    # --- environment ---
    sst = env.get("sst") or {}
    dhw_hist = env.get("dhw_history") or []
    dhw_max = _to_float(env.get("dhw_max_observed"))
    if dhw_max is None and dhw_hist:
        try:
            dhw_max = max(float(h.get("dhw", 0)) for h in dhw_hist)
        except (TypeError, ValueError):
            dhw_max = None

    environment = {
        "sst_mean": _to_float(sst.get("mean")),
        "sst_monthly": sst.get("monthly"),
        "dhw_max": dhw_max,
        "dhw_history": dhw_hist,
        "ph": _to_float((env.get("ph") or {}).get("mean")),
        "do": _to_float((env.get("do") or {}).get("mean")),
        "salinity": _to_float((env.get("salinity") or {}).get("mean")),
        "chlorophyll": _to_float((env.get("chlorophyll") or {}).get("mean")),
        "data_source": env.get("data_source", "unavailable"),
        "period": env.get("period"),
    }

    # --- monitoring ---
    monitoring = {
        "rhi_score": _to_float(mon.get("rhi_score")) or _to_float(seg.get("rhi_score")),
        "rhi_components": mon.get("rhi_components") or {},
        "rhi_weights": mon.get("rhi_weights") or {},
        "cover_trend": mon.get("cover_trend") or [],
        "cover_trend_note": mon.get("cover_trend_note"),
        "bleaching_events": mon.get("bleaching_events") or [],
        "data_source": mon.get("data_source", "unavailable"),
    }

    # --- restoration ---
    plan = seg.get("restoration_plan") or {}
    restoration = {
        "method": plan.get("method", "coral_gardening"),
        "area_m2": _to_float(plan.get("area_m2"), 0.0),
        "total_cost": _to_float(plan.get("total_cost"), 0.0),
        "cost_per_coral": _to_float(plan.get("cost_per_coral"), 0.0),
        "survival_rate": _to_float(plan.get("survival_rate"), 0.0),
        "coral_density": _to_float(plan.get("coral_density"), 0.0),
        "cost_breakdown": plan.get("cost_breakdown") or {},
        "last_updated": plan.get("last_updated"),
    }

    # --- recommendation ---
    rec = _build_recommendation(
        scoring["choice"],
        scoring["bleaching_probability"],
        monitoring["rhi_score"],
        environment["dhw_max"],
    )

    return {
        "segment_id": segment_id,
        "name": seg.get("name", segment_id),
        "name_zh": seg.get("name_zh") or seg.get("name", segment_id),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "basic_info": basic_info,
        "scoring": scoring,
        "environment": environment,
        "monitoring": monitoring,
        "restoration": restoration,
        "recommendation": rec["en"],
        "recommendation_zh": rec["zh"],
        "choice_label": {"en": rec["choice_en"], "zh": rec["choice_zh"]},
    }


# ---------------------------------------------------------------------------
# 区域汇总报告
# ---------------------------------------------------------------------------
def generate_region_report(segment_ids: List[str]) -> Dict[str, Any]:
    reports = []
    invest = monitor = deprior = 0
    score_sum = 0.0
    bleach_sum = 0.0
    cost_sum = 0.0
    rhi_sum = 0.0
    rhi_n = 0
    valid_ids: List[str] = []

    for sid in segment_ids:
        rep = generate_segment_report(sid)
        if rep is None:
            logger.warning("Region report: segment %s not found, skipped", sid)
            continue
        valid_ids.append(sid)
        choice = rep["scoring"]["choice"]
        if choice == "invest":
            invest += 1
        elif choice == "monitor":
            monitor += 1
        else:
            deprior += 1

        score_sum += float(rep["scoring"]["final_score"] or 0)
        if rep["scoring"]["bleaching_probability"] is not None:
            bleach_sum += float(rep["scoring"]["bleaching_probability"])
        cost_sum += float(rep["restoration"]["total_cost"] or 0)
        if rep["monitoring"]["rhi_score"] is not None:
            rhi_sum += float(rep["monitoring"]["rhi_score"])
            rhi_n += 1

        # 简要摘要 (去掉大数组)
        brief = {
            "segment_id": sid,
            "name": rep["name"],
            "name_zh": rep["name_zh"],
            "final_score": rep["scoring"]["final_score"],
            "choice": choice,
            "bleaching_probability": rep["scoring"]["bleaching_probability"],
            "rhi_score": rep["monitoring"]["rhi_score"],
            "total_restoration_cost": rep["restoration"]["total_cost"],
            "recommendation_zh": rep["recommendation_zh"],
            "recommendation": rep["recommendation"],
        }
        reports.append(brief)

    n = len(valid_ids)
    summary = {
        "count": n,
        "invest_count": invest,
        "monitor_count": monitor,
        "deprioritize_count": deprior,
        "avg_score": round(score_sum / n, 1) if n else None,
        "avg_bleaching_prob": round(bleach_sum / n, 3) if n else None,
        "total_restoration_cost": round(cost_sum, 2),
        "avg_rhi": round(rhi_sum / rhi_n, 1) if rhi_n else None,
    }

    # 区域级建议
    if n == 0:
        region_rec = {"en": "No valid segments selected.",
                      "zh": "未选择有效礁段。"}
    else:
        invest_pct = invest / n
        if invest_pct >= 0.4:
            region_rec = {
                "en": (f"Region-wide: {invest}/{n} reefs flagged as INVEST "
                       f"({invest_pct*100:.0f}%). Prioritize regional restoration "
                       f"funding and coordinated monitoring during thermal season."),
                "zh": (f"区域整体: {invest}/{n} 个礁段标记为优先投入 "
                       f"({invest_pct*100:.0f}%)。建议统筹区域恢复资金, "
                       f"并在热季开展协同监测。"),
            }
        elif monitor >= invest:
            region_rec = {
                "en": (f"Region-wide: {monitor}/{n} reefs require monitoring. "
                       f"Maintain quarterly surveillance; reserve restoration budget "
                       f"for reefs crossing the invest threshold."),
                "zh": (f"区域整体: {monitor}/{n} 个礁段需加强监测。"
                       f"保持季度巡查; 将恢复预算留给跨过投入阈值的礁段。"),
            }
        else:
            region_rec = {
                "en": (f"Region-wide: mixed status. {invest} invest, {monitor} monitor, "
                       f"{deprior} deprioritize. Use connectivity analysis to cluster "
                       f"restoration for maximum larval gain."),
                "zh": (f"区域整体: 状态混合 — 优先投入 {invest}、监测 {monitor}、"
                       f"降级 {deprior}。建议结合连通性分析分组恢复, 最大化幼体增益。"),
            }

    return {
        "segment_ids": valid_ids,
        "summary": summary,
        "segments": reports,
        "recommendation": region_rec["en"],
        "recommendation_zh": region_rec["zh"],
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
