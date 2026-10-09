"""
app/services/filter_service.py
==============================
空间筛选业务逻辑。

按 DHW / 水深 / 连通性 / 评分 / 白化概率 / 决策分类 / 分组 对礁段列表做筛选。
所有条件为 AND 关系；数值范围为闭区间 [min, max]；choice / group 支持逗号分隔多选。

main.py 只负责解析 query params 并把 dict 传进来，本模块不做任何 HTTP 相关假设，
便于单元测试与后续复用。
"""

from __future__ import annotations
from typing import Any, Dict, Iterable, List, Optional

# 决策分类 (与 scoring 引擎阈值输出一致)
CHOICES: List[str] = ["invest", "monitor", "deprioritize"]

# 分组 (按纬度划分)
#   Sipadan   : lat > 4.5
#   Tun Sakaran: 4.2 <= lat <= 4.5
#   East-West : lat < 4.2
GROUPS: List[str] = ["Sipadan", "Tun Sakaran", "East-West"]


# ---------------------------------------------------------------------------
# 字段取值辅助
# ---------------------------------------------------------------------------
def _f(v: Any) -> Optional[float]:
    """安全转 float；None / 非法值返回 None。"""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _conn_value(seg: Dict[str, Any]) -> Optional[float]:
    """连通性取值。

    评分引擎在 Laya-only 回退路径里会把 connectivity_score 覆盖为 1-5 缩放值；
    但 fusion 路径保留了原始 0-1 的 connectivity_score，并把 1-5 缩放值放在
    connectivity_score_1to5。这里优先采用 1-5 缩放值，使前端滑杆范围合理 (1-5)，
    回退到原始 connectivity_score。
    """
    scaled = _f(seg.get("connectivity_score_1to5"))
    if scaled is not None:
        return scaled
    return _f(seg.get("connectivity_score"))


def _score_value(seg: Dict[str, Any]) -> Optional[float]:
    """最终评分：优先 final_score (融合分)，回退 score。"""
    fs = _f(seg.get("final_score"))
    if fs is not None:
        return fs
    return _f(seg.get("score"))


def group_of(seg: Dict[str, Any]) -> str:
    """根据纬度把礁段划分到三个分组之一；缺纬度时回退到 East-West。"""
    lat = _f(seg.get("lat"))
    if lat is None:
        return "East-West"
    if lat > 4.5:
        return "Sipadan"
    if lat >= 4.2:
        return "Tun Sakaran"
    return "East-West"


# ---------------------------------------------------------------------------
# 条件判断
# ---------------------------------------------------------------------------
def _in_range(v: Optional[float], lo: Optional[float], hi: Optional[float]) -> bool:
    """闭区间 [lo, hi] 判定；v 为 None 时视为不满足 (仅当存在该维度筛选条件时)。"""
    if lo is None and hi is None:
        return True
    if v is None:
        return False
    if lo is not None and v < lo:
        return False
    if hi is not None and v > hi:
        return False
    return True


def _parse_multi(v: Any) -> set:
    """把 choice / group 参数解析为小写集合；支持逗号分隔字符串或列表。"""
    if v is None or v == "":
        return set()
    if isinstance(v, (list, tuple, set)):
        items: Iterable[str] = v
    else:
        items = str(v).split(",")
    return {str(x).strip().lower() for x in items if str(x).strip()}


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
def filter_segments(segments: List[Dict[str, Any]], params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    按查询参数筛选礁段。

    params 可包含 (值均为 float 或 None；choice/group 为逗号分隔字符串)：
      min_dhw, max_dhw                -> current_dhw
      min_depth, max_depth            -> mean_depth
      min_connectivity, max_connectivity -> 连通性 (1-5 缩放值)
      min_score, max_score            -> final_score 或 score
      bleaching_prob_min, max         -> bleaching_probability
      choice                          -> invest/monitor/deprioritize (逗号分隔多选)
      group                           -> Sipadan/Tun Sakaran/East-West (逗号分隔多选)

    所有条件 AND；数值闭区间；无参数时原样返回 (向后兼容)。
    """
    choice_set = _parse_multi(params.get("choice"))
    group_set = _parse_multi(params.get("group"))

    out: List[Dict[str, Any]] = []
    for seg in segments:
        # DHW
        if not _in_range(_f(seg.get("current_dhw")),
                         _f(params.get("min_dhw")), _f(params.get("max_dhw"))):
            continue
        # 水深
        if not _in_range(_f(seg.get("mean_depth")),
                         _f(params.get("min_depth")), _f(params.get("max_depth"))):
            continue
        # 连通性
        if not _in_range(_conn_value(seg),
                         _f(params.get("min_connectivity")),
                         _f(params.get("max_connectivity"))):
            continue
        # 评分
        if not _in_range(_score_value(seg),
                         _f(params.get("min_score")), _f(params.get("max_score"))):
            continue
        # 白化概率
        if not _in_range(_f(seg.get("bleaching_probability")),
                         _f(params.get("bleaching_prob_min")),
                         _f(params.get("bleaching_prob_max"))):
            continue
        # 决策分类 (多选, 空 = 不限制)
        if choice_set and str(seg.get("choice", "")).lower() not in choice_set:
            continue
        # 分组 (多选, 空 = 不限制)
        if group_set and group_of(seg).lower() not in group_set:
            continue
        out.append(seg)
    return out


def filters_meta(segments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """返回所有可用的筛选选项与数值范围 (从实际数据计算)。"""
    def _rng(value_fn) -> Dict[str, float]:
        vals = [v for v in (value_fn(s) for s in segments) if v is not None]
        if not vals:
            return {"min": 0, "max": 0}
        return {"min": round(min(vals), 3), "max": round(max(vals), 3)}

    return {
        "dhw_range": _rng(lambda s: _f(s.get("current_dhw"))),
        "depth_range": _rng(lambda s: _f(s.get("mean_depth"))),
        "connectivity_range": _rng(_conn_value),
        "score_range": _rng(_score_value),
        "bleaching_prob_range": _rng(lambda s: _f(s.get("bleaching_probability"))),
        "choices": list(CHOICES),
        "groups": list(GROUPS),
        "total_segments": len(segments),
    }
