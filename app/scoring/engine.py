"""
app/scoring/engine.py
=====================
评分引擎: 真实 28 个仙本那礁段 -> Laya/Rubric -> score + choice。

- 从 data/output/reef_features.csv + connectivity/output/reef_connectivity_features.csv 加载
- 用代理观测计算 CoralCore RHI
- 结果缓存到 data/output/scored_segments.json, 启动时直接加载
- POST /api/recalc 清缓存重算 (模拟新一周数据)
- 历史回测: backtest_period() 用指定时期 DHW 重算
"""

from __future__ import annotations
import os
import json
import time
import hashlib
import logging
from typing import Any, Dict, List, Optional

from .laya_client import LayaClient
from . import rubric
from .rhi import compute_simplified_rhi
from . import data_loader
from . import fusion

logger = logging.getLogger(__name__)

# 是否启用三层架构融合评分 (False = 旧版纯Laya, 向后兼容)
USE_FUSION = True


# ---------------------------------------------------------------------------
# 从可用特征推导 RHI 代理观测
# ---------------------------------------------------------------------------
def _estimate_rhi_proxies(s: Dict[str, Any]) -> Dict[str, float]:
    """
    用现有特征估算 8 个简化 RHI 参数 (0-100 量级)。
    这是无水下传感器数据下的代理估算, 仅用于 Demo。
    """
    max_dhw = float(s.get("max_dhw_5yr", 5.0) or 5.0)
    depth = float(s.get("mean_depth", 10.0) or 10.0)
    conn = float(s.get("connectivity_score", 0.2) or 0.2)  # 0-1
    settlements = float(s.get("total_settlements", 0) or 0)
    larval_in = float(s.get("larval_input", 0.0) or 0.0)
    area = float(s.get("reef_area_km2", 1.0) or 1.0)
    dist = float(s.get("distance_to_nearest_dive_site_km", 5.0) or 5.0)

    # 历史热压力越高, 活珊瑚覆盖越低
    coral_cover = max(5.0, min(70.0, 60.0 - max_dhw * 4.0))
    # 连通性好 + 沉降多 -> 鱼类生物量高
    fish_biomass = max(30.0, min(500.0, 80.0 + conn * 300.0 + settlements * 1.5))
    # 热压力高 -> 大型藻过度生长
    algal_overgrow = max(5.0, min(70.0, 15.0 + max_dhw * 3.0))
    # 水质: 近岸潜点略差, 远端略好
    water_quality = max(40.0, min(90.0, 70.0 - dist * 1.5))
    # 疾病率: 与历史 DHW 正相关
    disease_rate = max(2.0, min(60.0, 5.0 + max_dhw * 3.5))
    # 幼体补充: 沉降数 + 幼虫输入
    recruitment = max(0.5, min(25.0, 1.0 + settlements * 0.04 + larval_in * 2.0))
    # 结构复杂度: 浅水 + 大面积礁体略高
    structural_complexity = max(0.5, min(4.5, 1.5 + area * 1.2 + (1.0 if depth < 10 else 0.5)))
    # 热韧性: 历史压力越高, 适应越强 (但有阈值)
    thermal_resilience = max(20.0, min(90.0, 30.0 + max_dhw * 4.0))

    return {
        "coral_cover": coral_cover,
        "fish_biomass": fish_biomass,
        "algal_overgrow": algal_overgrow,
        "water_quality": water_quality,
        "disease_rate": disease_rate,
        "recruitment": recruitment,
        "structural_complexity": structural_complexity,
        "thermal_resilience": thermal_resilience,
    }


# ---------------------------------------------------------------------------
class ScoringEngine:
    def __init__(self, laya_base_url: str = "http://127.0.0.1:5000"):
        self.client = LayaClient(base_url=laya_base_url)
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._segments: List[Dict[str, Any]] = []
        self._scored: List[Dict[str, Any]] = []
        self._load_or_score()

    # ------------------------------------------------------------------ #
    def _load_or_score(self):
        """优先从 scored_segments.json 加载; 否则重新评分。"""
        if os.path.exists(data_loader.SCORED_JSON):
            try:
                with open(data_loader.SCORED_JSON, encoding="utf-8") as f:
                    self._scored = json.load(f)
                self._segments = [{k: v for k, v in s.items() if k != "score_details"}
                                  for s in self._scored]
                logger.info("Loaded %d scored segments from cache", len(self._scored))
                if len(self._scored) >= 20:
                    return
            except Exception as e:
                logger.warning("scored_segments.json unreadable: %s; rescoring", e)

        self._segments = data_loader.load_reef_segments()
        self._scored = self._score_all()
        self._save_cache()

    def _score_all(self) -> List[Dict[str, Any]]:
        """三层架构融合评分, 失败时回退到旧版纯Laya。"""
        if USE_FUSION:
            try:
                fusion.reset_caches()
                results = fusion.score_all(self._segments, self.client, compute_ci=True)
                # 补全旧字段兼容
                for r in results:
                    r.setdefault("laya_choice", "")
                    r.setdefault("confidence", 0.7)
                    r.setdefault("model", "fusion_v2")
                    r.setdefault("manual_override", False)
                    r.setdefault("name_zh", r.get("name", ""))
                logger.info("Fusion scoring succeeded for %d segments", len(results))
                return results
            except Exception as e:
                logger.warning("Fusion scoring failed (%s), falling back to Laya-only", e)

        # Fallback: 旧版逐段 Laya 评分
        out = []
        for s in self._segments:
            scored = self._score_one(s)
            out.append(scored)
        return out

    def _score_one(self, s: Dict[str, Any]) -> Dict[str, Any]:
        # 计算 RHI 代理
        proxies = _estimate_rhi_proxies(s)
        rhi = compute_simplified_rhi(proxies)

        # 构造给 Laya 的特征 (扁平 + 嵌套)
        feats = dict(s)
        feats["rhi_score"] = rhi
        feats["historical_mortality"] = None  # 无实测, 用 max_dhw 作为隐式信号

        state = rubric.build_state(feats)
        questions = rubric.build_questions()
        resp = self.client.predict(state, questions)

        answers = resp.get("answers", {})
        ps = answers.get("priority_score", {})
        pc = answers.get("priority_class", {})
        raw_score = ps.get("score", 2.0)
        score = ps.get("raw_score_0_100") or rubric.interpret_score(float(raw_score))
        score = int(round(score))
        # 最终分类以 score 透明阈值为准 (Laya choice 仅作原始建议展示):
        #   invest >= 55: 白化高峰期高优先级, 凉季极少触发
        #   monitor 40-54: 观察等待
        #   deprioritize < 40: 投入产出比低
        choice = "invest" if score >= 55 else ("monitor" if score >= 40 else "deprioritize")
        laya_choice = str(pc.get("choice", "")).lower().strip()
        if laya_choice not in ("invest", "monitor", "deprioritize"):
            laya_choice = ""
        confidence = float(ps.get("confidence", pc.get("confidence", 0.7)))

        result = dict(feats)
        result["rhi_proxies"] = proxies
        # rubric.build_state 读取 connectivity_score 字段, 这里覆盖为 1-5 缩放值
        result["connectivity_score"] = feats.get("connectivity_score_1to5", 3.0)
        result["score"] = score
        result["choice"] = choice
        result["laya_choice"] = laya_choice
        result["confidence"] = round(confidence, 3)
        result["model"] = resp.get("model", "unknown")
        return result

    def _save_cache(self):
        os.makedirs(os.path.dirname(data_loader.SCORED_JSON), exist_ok=True)
        with open(data_loader.SCORED_JSON, "w", encoding="utf-8") as f:
            json.dump(self._scored, f, ensure_ascii=False, indent=2, default=str)
        logger.info("Saved scored_segments.json (%d segments)", len(self._scored))

    # ------------------------------------------------------------------ #
    @property
    def segments(self) -> List[Dict[str, Any]]:
        return self._scored

    def all_scored(self) -> List[Dict[str, Any]]:
        return sorted(self._scored, key=lambda x: -x["score"])

    def recalc(self) -> Dict[str, Any]:
        """模拟新一周数据: 对 current_dhw 加小扰动, 清缓存重算。"""
        import random
        random.seed()
        for s in self._segments:
            delta = random.uniform(-0.3, 0.5)
            s["current_dhw"] = max(0.0, float(s.get("current_dhw", 0.0)) + delta)
        self._scored = self._score_all()
        self._save_cache()
        return {
            "recalculated": len(self._scored),
            "mode": "mock" if self.client.is_mock else "live",
            "top": sorted(
                [{"name": r["name"], "score": r["score"], "choice": r["choice"]}
                 for r in self._scored],
                key=lambda x: -x["score"],
            )[:5],
        }

    # ------------------------------------------------------------------ #
    # 历史回测
    # ------------------------------------------------------------------ #
    def backtest_period(self, year: int, month_start: int, month_end: int
                        ) -> Dict[str, Any]:
        """
        用指定历史时期的 DHW 替换 current_dhw, 重新评分, 返回分布统计。
        """
        dhw_map = data_loader.extract_dhw_at_period(year, month_start, month_end)
        if not dhw_map:
            return {"year": year, "error": "no DHW data for period"}

        results = []
        for s in self._segments:
            s2 = dict(s)
            sid = s2["segment_id"]
            s2["current_dhw"] = dhw_map.get(sid, 0.0)
            scored = self._score_one(s2)
            results.append(scored)

        invest = sum(1 for r in results if r["choice"] == "invest")
        monitor = sum(1 for r in results if r["choice"] == "monitor")
        deprioritize = sum(1 for r in results if r["choice"] == "deprioritize")
        avg = sum(r["score"] for r in results) / len(results)
        return {
            "year": year,
            "period": f"{year}-{month_start:02d}..{month_end:02d}",
            "n": len(results),
            "invest": invest,
            "monitor": monitor,
            "deprioritize": deprioritize,
            "invest_pct": round(invest / len(results) * 100, 1),
            "avg_score": round(avg, 1),
            "max_dhw": round(max(dhw_map.values()), 2),
            "mean_dhw": round(sum(dhw_map.values()) / len(dhw_map), 2),
            "results": [
                {"segment_id": r["segment_id"], "name": r["name"],
                 "dhw": r["current_dhw"], "score": r["score"], "choice": r["choice"]}
                for r in sorted(results, key=lambda x: -x["score"])
            ],
        }

    def update_segment(self, segment_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        更新指定礁段的字段并持久化到 scored_segments.json。
        当 score 或 choice 被修改时自动设置 manual_override=True，
        避免下次 recalc 覆盖人工修改。
        返回更新后的礁段字典；未找到返回 None。
        """
        target = None
        for s in self._scored:
            if s.get("segment_id") == segment_id:
                target = s
                break
        if target is None:
            return None

        # 评分相关字段被修改 -> 标记人工覆盖
        score_fields = {"score", "choice", "confidence"}
        if any(k in updates for k in score_fields):
            updates["manual_override"] = True

        for k, v in updates.items():
            if k == "segment_id":
                continue  # 主键不可改
            target[k] = v

        # 同步更新 _segments（去掉 score_details 的副本）
        for s in self._segments:
            if s.get("segment_id") == segment_id:
                for k, v in updates.items():
                    if k == "segment_id":
                        continue
                    s[k] = v
                break

        self._save_cache()
        logger.info("Updated segment %s: %s", segment_id, list(updates.keys()))
        return target

    # ------------------------------------------------------------------ #
    @property
    def laya_mode(self) -> str:
        return "mock" if self.client.is_mock else "live"

    def health(self) -> Dict[str, Any]:
        return {
            "laya_available": not self.client.is_mock,
            "laya_mode": self.laya_mode,
            "laya_base_url": self.client.base_url,
            "segments_loaded": len(self._scored),
            "fusion_enabled": USE_FUSION,
        }

    # ------------------------------------------------------------------ #
    # 三层架构模型信息 (供 API 使用)
    # ------------------------------------------------------------------ #
    def model_weights(self) -> Dict[str, Any]:
        """返回熵权法特征权重。"""
        w = fusion.get_feature_weights()
        if w is None:
            # 触发一次计算
            try:
                fusion.compute_mcdm_scores(self._segments)
                w = fusion.get_feature_weights()
            except Exception:
                w = {}
        return {"weights": w or {}, "method": "entropy_weight_topsis"}

    def model_compare(self) -> Dict[str, Any]:
        """新旧模型评分对比。"""
        old_scores = []
        new_scores = []
        for r in self._scored:
            old_scores.append(r.get("score", 0))
            new_scores.append(r.get("final_score", r.get("score", 0)))
        return {
            "n": len(self._scored),
            "old_model": {"mean": round(sum(old_scores)/max(1,len(old_scores)), 1),
                          "scores": old_scores},
            "new_model": {"mean": round(sum(new_scores)/max(1,len(new_scores)), 1),
                          "scores": new_scores},
            "alpha": fusion.get_optimal_alpha(),
        }

    def ml_model_info(self) -> Dict[str, Any]:
        """ML 白化预测器信息。未训练时自动触发训练。"""
        m = fusion.get_ml_model_info()
        if m is None:
            try:
                fusion.compute_bleaching_probs(self._segments)
                m = fusion.get_ml_model_info()
            except Exception as e:
                logger.warning("ML model training failed: %s", e)
                m = None
        if m is None:
            return {"status": "not_trained"}
        return {
            "status": "trained",
            "metrics": m.get("metrics", {}),
            "coef": m.get("coef", {}),
            "feature_names": m.get("feature_names", []),
        }


engine = ScoringEngine()
