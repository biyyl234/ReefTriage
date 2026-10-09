"""
app/scoring/rubric_v2.py
========================
Laya / Jev 评分 Rubric v2 —— 结构化分维度判断标准。

本文件**不修改** v1 的 app/scoring/rubric.py，而是把原来一段长 instructions
拆成 5 个显式维度，便于：
  1) Laya 按维度分别打分，减少 instruction following 的歧义；
  2) 后续用规则/MCDM 复算每个维度的子分，与 Laya 输出做对照；
  3) 维度权重可调，做敏感性分析。

五个维度:
  - thermal_stress       热压力      (current_dhw, max_dhw_5yr, bleaching_probability)
  - vulnerability        脆弱性      (mean_depth, rhi_score, historical_mortality)
  - recovery_potential   恢复潜力    (connectivity_score, larval_input, recruitment)
  - tourism_value        旅游价值    (distance_to_dive_site, dive_sites_within_5km, reef_area)
  - cost_effectiveness   成本效益    (综合以上 + 恢复成本代理)

设计原则:
  - 评分方向统一为 "越高 = 越值得优先恢复投资" (优先级高)。
    注意这与"脆弱性越高越差"相反 —— 本系统评的是**恢复投资优先级**,
    不是生态系统健康分。因此"易恢复 + 高连通 + 高旅游价值 = 高分"。
  - 每个维度内部用 0..4 的有序刻度 (与 v1 一致), interpret_score_v2 仍映射到 0..100。
  - 字段名做了别名兼容 (v1 用 distance_to_dive_site, 真实数据用
    distance_to_nearest_dive_site_km), 取数时按候选名回退。
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

# 复用 v1 的向后兼容函数, 不在本文件重复实现同名逻辑
from app.scoring.rubric import interpret_score as interpret_score_v1


# ---------------------------------------------------------------------------
# 维度定义: 每个维度显式列出输入特征、评分方向、高分/低分判据、建议权重
# ---------------------------------------------------------------------------

#: 建议权重 (总和 = 1.0)。cost_effectiveness 是综合维度, 权重稍低,
#: 因为它本身由前四个维度派生; 保留它是为了让 Laya 显式做"投资回报"权衡。
DIMENSION_WEIGHTS: Dict[str, float] = {
    "thermal_stress": 0.20,
    "vulnerability": 0.20,
    "recovery_potential": 0.25,
    "tourism_value": 0.15,
    "cost_effectiveness": 0.20,
}


#: 每个维度的元数据: 输入特征列表 + 中英文说明 + 高分/低分判据
#: 这是给人看的"判断标准", 也会被 build_questions_v2 转成 Laya instructions。
DIMENSION_SPEC: Dict[str, Dict[str, Any]] = {
    "thermal_stress": {
        "label": "Thermal stress exposure",
        "label_zh": "热压力暴露",
        "features": [
            "current_dhw",          # 当前 DHW (°C·week), NOAA CRW
            "max_dhw_5yr",          # 近 5 年最大 DHW
            "bleaching_probability",# 未来 12 个月白化概率 (0..1, 由模型预测, 可空)
        ],
        "high_score_rule": (
            "Current DHW in 2..6 °C·wk (active but sub-lethal heat stress, "
            "so restoration outplants will face stress but reef is not yet dead), "
            "AND max_dhw_5yr < 8 (not chronically cooked). "
            "High bleaching_probability (>0.6) WITH moderate current DHW means "
            "'invest before/while stress is happening'."
        ),
        "low_score_rule": (
            "current_dhw == 0 and max_dhw_5yr < 2 (no heat threat — monitor only) "
            "OR current_dhw > 10 / max_dhw_5yr > 12 (reef already cooked, "
            "restoration outplants will die next summer — deprioritize)."
        ),
        "notes_zh": (
            "热压力不是越高越好: 极端长期高热 (>10 DHW) 的礁即使投钱也活不下来; "
            "温和但正在发生的热压力 (2-6 DHW) 才是'趁现在干预'的窗口。"
        ),
    },
    "vulnerability": {
        "label": "Biophysical vulnerability / degradation state",
        "label_zh": "生物物理脆弱性 / 退化状态",
        "features": [
            "mean_depth",           # 平均水深 (m)
            "rhi_score",            # CoralCore RHI 0..100
            "historical_mortality", # 历史白化死亡率 %, 可空
        ],
        "high_score_rule": (
            "Shallow reef (mean_depth 2..10 m, cheap and fast to outplant) "
            "AND RHI in 35..70 (degraded but not dead — responds to intervention) "
            "AND historical_mortality < 50% (not a graveyard)."
        ),
        "low_score_rule": (
            "mean_depth > 20 m (expensive, logistically hard to outplant) "
            "OR RHI < 20 (already dead reef, low cover) "
            "OR historical_mortality > 60% combined with low connectivity."
        ),
        "notes_zh": (
            "浅水区恢复成本低、生长快; RHI 中段 (35-70) 是'退化但可逆'的甜点区; "
            "RHI 极高 (>85) 说明礁很健康, 不需要恢复投资; RHI 极低说明已死, 投了也白投。"
        ),
    },
    "recovery_potential": {
        "label": "Recovery potential via connectivity",
        "label_zh": "连通性 / 自然补充恢复潜力",
        "features": [
            "connectivity_score",  # 1..5 连通性综合分
            "larval_input",        # 外部幼体输入 (归一化 0..1)
            "recruitment",         # 补充量 (来自 rhi_proxies, 0..1 或计数)
        ],
        "high_score_rule": (
            "connectivity_score >= 3.5 AND larval_input > 0.3 "
            "(nearby healthy reefs will supply larvae, restoration outplants "
            "will be 'topped up' by natural replenishment — high return)."
        ),
        "low_score_rule": (
            "connectivity_score < 2.0 AND larval_input == 0 "
            "(isolated reef, self-seeding only, restoration must bear all "
            "recruitment burden — low return unless tourism value is extreme)."
        ),
        "notes_zh": (
            "连通性是恢复投资回报的放大器: 高连通意味着人工恢复的珊瑚会被自然补充加速; "
            "孤立礁即使投钱, 长期也要持续人工维护。"
        ),
    },
    "tourism_value": {
        "label": "Tourism / dive economic value",
        "label_zh": "旅游 / 潜水经济价值",
        "features": [
            "distance_to_dive_site",     # 到最近热门潜点距离 (km)
            "dive_sites_within_5km",      # 5 km 内潜点数
            "reef_area",                  # 礁体面积 km²
        ],
        "high_score_rule": (
            "distance_to_dive_site < 1 km AND dive_sites_within_5km >= 3 "
            "(already on the dive trail, tourists will see restored coral quickly, "
            "high political/economic co-benefit) AND reef_area > 0.5 km²."
        ),
        "low_score_rule": (
            "distance_to_dive_site > 10 km AND dive_sites_within_5km == 0 "
            "remote reef with no dive operator visibility — low co-benefit."
        ),
        "notes_zh": (
            "仙本那是潜水旅游经济, 恢复靠近热门潜点的礁有直接经济回报和政治支持; "
            "偏远无人潜点的生态价值仍在, 但旅游协同效益低。"
        ),
    },
    "cost_effectiveness": {
        "label": "Overall cost-effectiveness of restoration investment",
        "label_zh": "恢复投资综合成本效益",
        "features": [
            # 本维度是综合维度, 不引入新原始字段, 而是要求 Laya
            # 综合前四个维度 + 一个粗恢复成本代理 (深度/可达性/连通性) 做权衡。
            "derived_from: thermal_stress",
            "derived_from: vulnerability",
            "derived_from: recovery_potential",
            "derived_from: tourism_value",
            "restoration_cost_proxy",  # 可空; 浅 + 近潜点 + 大礁 = 成本低
        ],
        "high_score_rule": (
            "Reef is (a) currently threatened but not cooked, (b) shallow and "
            "degraded-but-alive, (c) well-connected, (d) on the dive trail. "
            "Restoration money buys measurable, visible, self-sustaining recovery. "
            "This is the 'invest this season' tier."
        ),
        "low_score_rule": (
            "Reef is either already dead/cooked, or isolated, or too remote to "
            "show return. Restoration budget here has low expected ROI — "
            "deprioritize and spend elsewhere."
        ),
        "notes_zh": (
            "这是最终决策维度: 不是问'礁有多惨', 而是问'这笔恢复预算花在这, "
            "一个季度后能看到多少可测量的恢复 + 旅游回报 + 自然补充'。"
        ),
    },
}


# ---------------------------------------------------------------------------
# 字段别名: 真实数据字段名 vs rubric 内部标准名
# ---------------------------------------------------------------------------

#: 标准名 -> 候选原始字段名 (按优先级回退)
_FIELD_ALIASES: Dict[str, List[str]] = {
    "segment_id": ["segment_id"],
    "name": ["name", "reef_segment_name", "name_zh"],
    "lat": ["lat"],
    "lon": ["lon"],
    "current_dhw": ["current_dhw"],
    "max_dhw_5yr": ["max_dhw_5yr"],
    "mean_depth": ["mean_depth"],
    "reef_area": ["reef_area", "reef_area_km2"],
    "distance_to_dive_site": [
        "distance_to_dive_site",
        "distance_to_nearest_dive_site_km",
    ],
    "dive_sites_within_5km": ["dive_sites_within_5km"],
    "connectivity_score": [
        "connectivity_score",
        "connectivity_score_1to5",
    ],
    "larval_input": ["larval_input"],
    "recruitment": ["recruitment"],
    "rhi_score": ["rhi_score"],
    "historical_mortality": ["historical_mortality"],
    "bleaching_probability": ["bleaching_probability"],
}


def _pick(features: Dict[str, Any], standard_name: str) -> Any:
    """按别名表从 features 里取第一个非 None 值。"""
    for key in _FIELD_ALIASES.get(standard_name, [standard_name]):
        val = features.get(key)
        if val is not None:
            return val
    return None


# ---------------------------------------------------------------------------
# bleaching_probability 与 confidence_interval 的本地启发式估算
# ---------------------------------------------------------------------------

def _estimate_bleaching_probability(
    current_dhw: Optional[float],
    max_dhw_5yr: Optional[float],
) -> Tuple[Optional[float], Optional[Tuple[float, float]]]:
    """
    基于 NOAA CRW 经验阈值的粗白化概率启发式估算。

    NOAA CRW 白化预警等级:
      - DHW < 4   : 警戒 Watch, 白化概率低
      - DHW 4..8  : 警告 Warning, 概率中等
      - DHW 8..12 : Alert Level 1, 大概率白化
      - DHW > 12  : Alert Level 2, 大面积白化/死亡

    如果外部模型已经给出 bleaching_probability, build_state_v2 会优先用外部值,
    这里只做兜底。返回 (prob, (low, high))。
    """
    if current_dhw is None:
        return None, None

    # 以当前 DHW 为主, 近 5 年最大 DHW 作为调制项
    base: float
    if current_dhw < 2:
        base = 0.05
    elif current_dhw < 4:
        base = 0.20
    elif current_dhw < 8:
        base = 0.55
    elif current_dhw < 12:
        base = 0.80
    else:
        base = 0.95

    # 近 5 年如果反复高热, 礁可能已经适应/死亡, 概率略调
    if max_dhw_5yr is not None and max_dhw_5yr > 12:
        base = max(0.0, base - 0.20)  # 已经死过一轮, 当前再白化概率反而低
    elif max_dhw_5yr is not None and max_dhw_5yr < 2:
        base = min(1.0, base + 0.10)  # 历史平静, 这次突然热,  unprepared

    prob = round(max(0.0, min(1.0, base)), 3)
    # 95% 置信区间粗估 ±0.15
    low = round(max(0.0, prob - 0.15), 3)
    high = round(min(1.0, prob + 0.15), 3)
    return prob, (low, high)


# ---------------------------------------------------------------------------
# build_state_v2: 结构化 state, 按维度组织
# ---------------------------------------------------------------------------

def build_state_v2(features: Dict[str, Any]) -> Dict[str, Any]:
    """
    把礁段特征转成 Laya state (v2 结构化版)。

    返回结构:
      {
        "segment_id": ...,
        "reef_segment_name": ...,
        "location": {lat, lon},
        "dimensions": {
          "thermal_stress":     {current_dhw, max_dhw_5yr, bleaching_probability, confidence_interval},
          "vulnerability":      {mean_depth, rhi_score, historical_mortality_pct},
          "recovery_potential":  {connectivity_score, larval_input, recruitment},
          "tourism_value":      {distance_to_dive_site_km, dive_sites_within_5km, reef_area_km2},
          "cost_effectiveness": {restoration_cost_proxy_note},
        },
        "dimension_weights": {...},
      }
    """
    current_dhw = _pick(features, "current_dhw")
    max_dhw_5yr = _pick(features, "max_dhw_5yr")
    bleaching_prob_ext = _pick(features, "bleaching_probability")

    if bleaching_prob_ext is not None:
        bleaching_prob = float(bleaching_prob_ext)
        # 外部模型给了概率, 给一个较窄的置信区间
        ci: Tuple[float, float] = (
            round(max(0.0, bleaching_prob - 0.10), 3),
            round(min(1.0, bleaching_prob + 0.10), 3),
        )
    else:
        bleaching_prob, ci = _estimate_bleaching_probability(current_dhw, max_dhw_5yr)

    # 恢复成本代理: 浅 + 近潜点 + 大礁 => 成本低 (数值越大越省)
    mean_depth = _pick(features, "mean_depth")
    dist_dive = _pick(features, "distance_to_dive_site")
    reef_area = _pick(features, "reef_area")
    cost_proxy = _estimate_cost_proxy(mean_depth, dist_dive, reef_area)

    state: Dict[str, Any] = {
        "segment_id": _pick(features, "segment_id") or "unknown",
        "reef_segment_name": _pick(features, "name") or "unnamed",
        "location": {
            "lat": _pick(features, "lat"),
            "lon": _pick(features, "lon"),
        },
        "dimensions": {
            "thermal_stress": {
                "current_dhw_cw": current_dhw,
                "max_dhw_5yr_cw": max_dhw_5yr,
                "bleaching_probability": bleaching_prob,
                "confidence_interval": {
                    "low": ci[0] if ci else None,
                    "high": ci[1] if ci else None,
                },
            },
            "vulnerability": {
                "mean_depth_m": mean_depth,
                "rhi_score_0to100": _pick(features, "rhi_score"),
                "historical_mortality_pct": _pick(features, "historical_mortality"),
            },
            "recovery_potential": {
                "connectivity_score_1to5": _pick(features, "connectivity_score"),
                "larval_input": _pick(features, "larval_input"),
                "recruitment": _pick(features, "recruitment"),
            },
            "tourism_value": {
                "distance_to_dive_site_km": dist_dive,
                "dive_sites_within_5km": _pick(features, "dive_sites_within_5km"),
                "reef_area_km2": reef_area,
            },
            "cost_effectiveness": {
                # 粗成本代理 (0..1, 越高越省/越划算), 给 Laya 做参考
                "restoration_cost_proxy_0to1": cost_proxy,
                "note": (
                    "Synthesize the four dimensions above. High score means "
                    "restoration money buys visible, self-sustaining recovery."
                ),
            },
        },
        "dimension_weights": dict(DIMENSION_WEIGHTS),
    }
    return state


def _estimate_cost_proxy(
    mean_depth: Optional[float],
    distance_to_dive: Optional[float],
    reef_area: Optional[float],
) -> Optional[float]:
    """
    粗恢复成本代理: 0..1, 越高 = 恢复越便宜/越划算。

    子项:
      - 深度: 5 m 最省, >25 m 最贵
      - 可达性: 靠近潜点 => 船程/潜水作业便宜
      - 礁面积: 略大 => 单位固定成本摊薄
    """
    if mean_depth is None and distance_to_dive is None and reef_area is None:
        return None

    parts: List[float] = []
    if mean_depth is not None:
        # 5m -> 1.0; 25m -> 0.0; 线性
        d_score = max(0.0, min(1.0, (25.0 - float(mean_depth)) / 20.0))
        parts.append(d_score)
    if distance_to_dive is not None:
        # 0 km -> 1.0; 10 km -> 0.0
        a_score = max(0.0, min(1.0, 1.0 - float(distance_to_dive) / 10.0))
        parts.append(a_score)
    if reef_area is not None:
        # 0.2 km² -> 0.0; 2 km² -> 1.0
        r_score = max(0.0, min(1.0, (float(reef_area) - 0.2) / 1.8))
        parts.append(r_score)

    if not parts:
        return None
    return round(sum(parts) / len(parts), 3)


# ---------------------------------------------------------------------------
# build_questions_v2: 每维度一个子问题 + 一个综合总分问题
# ---------------------------------------------------------------------------

def _dimension_instruction(dim_key: str, spec: Dict[str, Any]) -> str:
    """把 DIMENSION_SPEC 里的规则拼成一段给 Laya 的英文 instructions。"""
    return (
        f"Dimension: {spec['label']}. "
        f"Score this reef segment on an ordinal scale 0..4 where "
        f"0 = very low restoration priority on this dimension, "
        f"4 = very high restoration priority on this dimension. "
        f"HIGH score if: {spec['high_score_rule']} "
        f"LOW score if: {spec['low_score_rule']} "
        f"Use only the features provided under dimensions.{dim_key} in the state."
    )


def build_questions_v2() -> Dict[str, Any]:
    """
    v2 问题结构: 5 个维度子问题 + 1 个综合问题。

    Laya 一次前向传播返回 6 个分数; 调用方按 dimension_weights 加权得到总分,
    再用 interpret_score_v2 映射到 0..100。

    同时保留 priority_class 二选一问题, 与 v1 的 invest/monitor/deprioritize 对齐。
    """
    questions: Dict[str, Any] = {}

    # 每个维度一个 score 子问题
    for dim_key, spec in DIMENSION_SPEC.items():
        questions[f"dim_{dim_key}"] = {
            "type": "score",
            "scale": [0, 4],
            "dimension": dim_key,
            "label": spec["label"],
            "instructions": _dimension_instruction(dim_key, spec),
        }

    # 综合总分问题: 要求 Laya 综合 5 个维度给出最终优先级
    questions["priority_score"] = {
        "type": "score",
        "scale": [0, 4],
        "dimension": "composite",
        "instructions": (
            "You are a coral reef restoration prioritization analyst for the "
            "Semporna (Sabah, Malaysia) region. Using the five dimension "
            "sub-scores (thermal_stress, vulnerability, recovery_potential, "
            "tourism_value, cost_effectiveness) and the weights provided in "
            "state.dimension_weights, output the OVERALL restoration priority "
            "on a 0..4 ordinal scale: "
            "0 = deprioritize (dead/cooked or isolated, low ROI), "
            "1 = monitor only, "
            "2 = medium, opportunistic investment, "
            "3 = high, invest this season, "
            "4 = critical, invest immediately. "
            "Remember: this scores COST-EFFECTIVENESS of restoration, not just "
            "ecological health. A healthy reef (RHI>85) that is already "
            "recovering naturally should score LOW because restoration money "
            "is better spent on a degraded-but-recoverable, well-connected, "
            "shallow reef near popular dive sites."
        ),
        "criteria": [
            "deprioritize: dead/cooked/isolated, low ROI",
            "monitor: stable or naturally recovering, no urgent intervention",
            "medium: degraded but recoverable, moderate cost-effectiveness",
            "high: threatened, high recovery potential and tourism value",
            "critical: immediate bleaching threat, high connectivity and tourism value",
        ],
    }

    # 分类问题, 与 v1 对齐
    questions["priority_class"] = {
        "type": "choice",
        "instructions": (
            "Classify this reef segment into one restoration action tier. "
            "Use the same cost-effectiveness logic as the overall priority_score."
        ),
        "criteria": {
            "invest": (
                "Fund active restoration this season (outplanting, nurseries, "
                "shading). Overall priority_score >= 3."
            ),
            "monitor": (
                "Do not fund active restoration yet; track with surveys. "
                "priority_score in 1..2."
            ),
            "deprioritize": (
                "Do not allocate restoration budget. priority_score == 0 "
                "(very high past mortality + low connectivity, or cooked reef)."
            ),
        },
    }

    return questions


# ---------------------------------------------------------------------------
# interpret_score_v2: 与 v1 兼容的 0..100 映射
# ---------------------------------------------------------------------------

def interpret_score_v2(raw_score: float) -> int:
    """
    把 Laya 返回的 0..4 有序 score 映射到 0..100。

    与 v1 的 interpret_score 完全一致: round(raw / 4 * 100), clip [0, 100]。
    保留 v2 命名是为了让调用方显式选择用哪一版; 结果数值向后兼容。
    """
    if raw_score is None:
        return 0
    try:
        v = float(raw_score)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, int(round(v / 4.0 * 100))))


#: 向后兼容别名 (re-export v1 的 interpret_score)
interpret_score = interpret_score_v1


# ---------------------------------------------------------------------------
# 便捷: 规则复算子分 (可选, 用于与 Laya 输出做对照)
# ---------------------------------------------------------------------------

def local_dimension_scores(state: Dict[str, Any]) -> Dict[str, float]:
    """
    用本地启发式规则算每个维度的 0..4 子分。

    这不是 Laya 输出, 而是一个"规则基线", 用于:
      - 回测时对照 Laya 评分与规则评分的一致性;
      - 缺省 Laya 服务时兜底。

    返回 {dim_key: 0..4 float}。
    """
    dims = state.get("dimensions", {})
    out: Dict[str, float] = {}

    # thermal_stress
    ts = dims.get("thermal_stress", {})
    out["thermal_stress"] = _rule_thermal_stress(
        ts.get("current_dhw_cw"), ts.get("max_dhw_5yr_cw"),
    )

    # vulnerability
    vu = dims.get("vulnerability", {})
    out["vulnerability"] = _rule_vulnerability(
        vu.get("mean_depth_m"),
        vu.get("rhi_score_0to100"),
        vu.get("historical_mortality_pct"),
    )

    # recovery_potential
    rp = dims.get("recovery_potential", {})
    out["recovery_potential"] = _rule_recovery_potential(
        rp.get("connectivity_score_1to5"), rp.get("larval_input"),
    )

    # tourism_value
    tv = dims.get("tourism_value", {})
    out["tourism_value"] = _rule_tourism_value(
        tv.get("distance_to_dive_site_km"),
        tv.get("dive_sites_within_5km"),
    )

    # cost_effectiveness: 用 cost_proxy + 前四维加权粗算
    ce = dims.get("cost_effectiveness", {})
    proxy = ce.get("restoration_cost_proxy_0to1")
    out["cost_effectiveness"] = _rule_cost_effectiveness(out, proxy)

    return out


def _rule_thermal_stress(current_dhw: Optional[float],
                         max_dhw: Optional[float]) -> float:
    if current_dhw is None:
        return 2.0  # 缺省中性
    if current_dhw >= 10 or (max_dhw is not None and max_dhw > 12):
        return 0.5   # 已经烤死
    if current_dhw >= 4:
        return 3.5   # 正在热, 紧急
    if current_dhw >= 2:
        return 2.5   # 温和热压力
    if max_dhw is not None and max_dhw < 2:
        return 1.0   # 长期无热威胁
    return 1.5


def _rule_vulnerability(depth: Optional[float],
                        rhi: Optional[float],
                        mort: Optional[float]) -> float:
    score = 2.0
    if depth is not None:
        if 2 <= depth <= 10:
            score += 1.0
        elif depth > 20:
            score -= 1.0
    if rhi is not None:
        if 35 <= rhi <= 70:
            score += 1.0   # 退化但可逆甜点
        elif rhi > 85:
            score -= 1.0   # 太健康, 不需要恢复
        elif rhi < 20:
            score -= 1.0   # 已死
    if mort is not None and mort > 60:
        score -= 1.0
    return max(0.0, min(4.0, score))


def _rule_recovery_potential(conn: Optional[float],
                             larval: Optional[float]) -> float:
    score = 2.0
    if conn is not None:
        if conn >= 3.5:
            score += 1.5
        elif conn < 2.0:
            score -= 1.0
    if larval is not None:
        if larval > 0.3:
            score += 0.5
        elif larval == 0:
            score -= 0.5
    return max(0.0, min(4.0, score))


def _rule_tourism_value(dist: Optional[float],
                        n_dive: Optional[float]) -> float:
    score = 2.0
    if dist is not None:
        if dist < 1:
            score += 1.5
        elif dist > 10:
            score -= 1.5
    if n_dive is not None:
        if n_dive >= 3:
            score += 0.5
        elif n_dive == 0:
            score -= 0.5
    return max(0.0, min(4.0, score))


def _rule_cost_effectiveness(dim_scores: Dict[str, float],
                             proxy: Optional[float]) -> float:
    # 加权综合前四维 + 成本代理
    base = (
        DIMENSION_WEIGHTS["thermal_stress"] * dim_scores["thermal_stress"]
        + DIMENSION_WEIGHTS["vulnerability"] * dim_scores["vulnerability"]
        + DIMENSION_WEIGHTS["recovery_potential"] * dim_scores["recovery_potential"]
        + DIMENSION_WEIGHTS["tourism_value"] * dim_scores["tourism_value"]
    ) / 0.80  # 归一化到 0..4
    if proxy is not None:
        # proxy 0..1 => 0..4 调制
        base = 0.7 * base + 0.3 * (proxy * 4.0)
    return max(0.0, min(4.0, base))
