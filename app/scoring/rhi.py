"""
app/scoring/rhi.py
==================
Reef Health Index (RHI) 计算模块。

包含两部分:
1. CoralCore RHI 复合公式的参考实现 (gitdeeper8/coralcore)
   - 8 个物理化学/生物参数, 权重由 PCA 留一站点交叉验证得到
   - RHI = sum(w_i * phi_i*)  phi_i* in [0,1]
2. 简化适配器: 在缺乏水下传感器 (PAM 荧光仪、SAMI-alk、水听器) 的情况下,
   用常见礁体代理观测 (珊瑚覆盖率、鱼类生物量、大型藻覆盖、疾病率等) 推算 RHI。
   简化实现, 明确标注, 仅用于 Demo。

参考:
- CoralCore README: https://github.com/gitdeeper8/coralcore
- RHI 阈值: >=0.80 HEALTHY, 0.50-0.79 STRESSED, <0.50 CRITICAL
"""

from __future__ import annotations
from typing import Dict, Any, Optional
import math


# ---------------------------------------------------------------------------
# CoralCore 官方权重 (来自 PCA + leave-one-site-out CV, n=47832 obs)
# ---------------------------------------------------------------------------
CORALCORE_WEIGHTS: Dict[str, float] = {
    "phi_ps":   0.21,  # Zooxanthellae Quantum Yield [0, 0.80]
    "g_ca":     0.19,  # Calcification Rate [mmol cm-2 day-1]
    "e_diss":   0.14,  # Wave Energy Dissipation [W m-2]
    "rho_skel": 0.12,  # Skeletal Bulk Density [g cm-3]
    "delta_ph": 0.11,  # Ocean Acidification Lag [pH units]
    "s_reef":   0.10,  # Acoustic Reef Signature [dB re 1uPa2/Hz]
    "k_s":      0.08,  # Surface Roughness Index [m]
    "t_thr":    0.05,  # Thermal Bleaching Threshold [degC]
}


def _norm(value: float, low: float, high: float) -> float:
    """把 value 线性归一化到 [0,1]; low=最差, high=最好。"""
    if high == low:
        return 0.5
    v = (value - low) / (high - low)
    return max(0.0, min(1.0, v))


def compute_coralcore_rhi(params: Dict[str, float]) -> float:
    """
    CoralCore 官方 8 参数 RHI 复合公式。

    Parameters
    ----------
    params : dict
        必须包含 8 个键: phi_ps, g_ca, e_diss, rho_skel,
        delta_ph, s_reef, k_s, t_thr。
        每个值已经是该参数的"健康度归一化值" phi_i* in [0,1]
        (调用方负责按各自 healthy/critical 阈值归一化)。

    Returns
    -------
    float : RHI in [0, 1]
    """
    score = 0.0
    missing = []
    for key, w in CORALCORE_WEIGHTS.items():
        v = params.get(key)
        if v is None:
            missing.append(key)
            continue
        v = max(0.0, min(1.0, float(v)))
        score += w * v
    # 若有缺失参数, 按已提供参数的权重占比重新归一, 避免得分系统性偏低
    if missing:
        known_w = sum(CORALCORE_WEIGHTS[k] for k in CORALCORE_WEIGHTS if k not in missing)
        if known_w > 0:
            score = score / known_w
    return round(score, 4)


def classify_rhi(rhi_01: float) -> str:
    """按 CoralCore 阈值分级。"""
    if rhi_01 >= 0.80:
        return "HEALTHY"
    if rhi_01 >= 0.50:
        return "STRESSED"
    return "CRITICAL"


# ---------------------------------------------------------------------------
# 简化 RHI 适配器 (无传感器时用代理观测)
# ---------------------------------------------------------------------------
# 8 个代理观测 (常见礁体监测指标), 与 CoralCore 8 参数做概念映射:
#   coral_cover     -> 珊瑚活覆盖率 (%)            [对应 phi_ps / g_ca 的综合表现]
#   fish_biomass    -> 鱼类生物量 (kg/ha)          [生态系统功能]
#   algal_overgrow  -> 大型藻覆盖率 (%)            [竞争退化指标, 反向]
#   water_quality   -> 水质评分 (0-100, 浊度/营养盐)
#   disease_rate    -> 疾病/白化死亡率 (%)         [反向]
#   recruitment     -> 幼体补充率 (ind/m2/yr)     [恢复潜力]
#   structural_complexity -> 结构复杂度 (0-5 分)   [对应 k_s 粗糙度]
#   thermal_resilience -> 热韧性 (0-100, 适应历史) [对应 t_thr]
#
# 这 8 项各归一化到 [0,1], 再用一套简化权重合成 0-100 的 RHI。
SIMPLIFIED_WEIGHTS: Dict[str, float] = {
    "coral_cover":          0.20,
    "fish_biomass":         0.15,
    "algal_overgrow":       0.15,   # 反向
    "water_quality":        0.10,
    "disease_rate":         0.15,   # 反向
    "recruitment":          0.10,
    "structural_complexity":0.08,
    "thermal_resilience":   0.07,
}


def compute_simplified_rhi(obs: Dict[str, Optional[float]]) -> float:
    """
    简化 RHI (0-100)。输入 8 项代理观测, 缺项用中性 0.5 并按权重归一。

    约定:
      coral_cover (%)         : 健康 60+, 差 <10
      fish_biomass (kg/ha)    : 健康 500+, 差 <50
      algal_overgrow (%)      : 健康 <10, 差 >60 (反向)
      water_quality (0-100)   : 直接
      disease_rate (%)        : 健康 <5, 差 >40 (反向)
      recruitment (ind/m2/yr) : 健康 20+, 差 <1
      structural_complexity (0-5): 直接 /5
      thermal_resilience (0-100): 直接
    """
    def pick(k: str, default: float) -> float:
        v = obs.get(k)
        return float(v) if v is not None and not (isinstance(v, float) and math.isnan(v)) else default

    pieces = {
        "coral_cover":           _norm(pick("coral_cover", 30.0),  10.0, 60.0),
        "fish_biomass":          _norm(pick("fish_biomass", 200.0), 50.0, 500.0),
        "algal_overgrow":        1.0 - _norm(pick("algal_overgrow", 30.0), 10.0, 60.0),
        "water_quality":         _norm(pick("water_quality", 60.0), 30.0, 90.0),
        "disease_rate":          1.0 - _norm(pick("disease_rate", 20.0), 5.0, 40.0),
        "recruitment":           _norm(pick("recruitment", 5.0),    1.0, 20.0),
        "structural_complexity": _norm(pick("structural_complexity", 2.5), 0.5, 4.5),
        "thermal_resilience":    _norm(pick("thermal_resilience", 50.0), 20.0, 90.0),
    }
    score01 = sum(SIMPLIFIED_WEIGHTS[k] * pieces[k] for k in SIMPLIFIED_WEIGHTS)
    return round(score01 * 100.0, 1)


if __name__ == "__main__":
    # 自检
    demo = {
        "coral_cover": 45, "fish_biomass": 320, "algal_overgrow": 18,
        "water_quality": 72, "disease_rate": 12, "recruitment": 8,
        "structural_complexity": 3.2, "thermal_resilience": 60,
    }
    print("Simplified RHI:", compute_simplified_rhi(demo))
    print("CoralCore RHI (all healthy):",
          compute_coralcore_rhi({k: 0.85 for k in CORALCORE_WEIGHTS}))
