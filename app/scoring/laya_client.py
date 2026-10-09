"""
app/scoring/laya_client.py
==========================
Laya REST API 客户端封装。

Laya 是 Jev 的开源平替 (非自回归 System-1 决策引擎), 以 HTTP 服务暴露:
  - GET  /health            -> 健康检查
  - POST /v1/systemone      -> 结构化决策 (state + questions -> answers)

参考:
  - 仓库: https://github.com/NandhaKishorM/laya
  - HTTP 服务: `laya-serve` (pip install laya[serve])
  - compose.http.yaml 中 curl 示例确认 endpoint 为 /v1/systemone
  - 请求示例: examples/docker/request.json

本模块:
  * 真实 API 调用逻辑完整保留
  * 服务不可用时自动降级到 mock 模式 (确定性加权公式), 保证前端可演示
  * 自动探测 endpoint: 先 /v1/systemone, 再 /predict, 再 /
"""

from __future__ import annotations
import time
import logging
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class LayaClient:
    """Laya HTTP 客户端, 支持单条 / 批量 / mock 降级。"""

    # 候选 prediction endpoint (按优先级探测)
    # /api/predict 是 Laya 本地控制台 (laya-rl-agent) 的实际端点;
    # /v1/systemone 和 /predict 是标准 laya-serve 的端点, 保留兼容.
    CANDIDATE_ENDPOINTS = ("/api/predict", "/v1/systemone", "/predict", "/")

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:5000",
        timeout: float = 10.0,
        max_retries: int = 2,
        api_key: Optional[str] = None,
        force_mock: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.api_key = api_key
        self.force_mock = force_mock

        self._endpoint: Optional[str] = None   # 探测到的可用 prediction endpoint
        self._available: Optional[bool] = None  # 缓存健康检查结果
        self._last_model: Optional[str] = None

    # ------------------------------------------------------------------ #
    # 健康检查 & endpoint 探测
    # ------------------------------------------------------------------ #
    def check_health(self) -> bool:
        """返回 Laya 服务是否可用。结果会缓存, force_mock 时直接 False。"""
        if self.force_mock:
            self._available = False
            return False
        try:
            # Laya 本地控制台用 /api/status; 标准 laya-serve 用 /health; 两者都试
            for hp in ("/api/status", "/health"):
                r = requests.get(f"{self.base_url}{hp}", timeout=self.timeout)
                if r.status_code == 200:
                    self._available = True
                    logger.info("Laya %s OK at %s", hp, self.base_url)
                    return True
            self._available = False
            return False
        except Exception as e:
            logger.info("Laya /health unreachable (%s) -> falling back to mock", e)
            self._available = False
            return False

    def _resolve_endpoint(self) -> Optional[str]:
        """探测可用的 prediction endpoint, 缓存结果。"""
        if self._endpoint is not None:
            return self._endpoint
        # 已确认不可用 -> 直接返回 None, 不再重复探测 (避免每次 10s 超时)
        if self._available is False:
            return None
        # 先探测 health, 不健康直接返回
        if not self.check_health():
            return None
        for ep in self.CANDIDATE_ENDPOINTS:
            try:
                # 用一个最小 questions 探活: noul 类型最轻量
                probe = {
                    "state": {"probe": True},
                    "questions": {
                        "ping": {"type": "noul", "instructions": "ping?"}
                    },
                }
                r = requests.post(
                    f"{self.base_url}{ep}",
                    json=probe,
                    timeout=self.timeout,
                    headers=self._auth_headers(),
                )
                if r.status_code == 200 and "answers" in r.text:
                    self._endpoint = ep
                    logger.info("Laya prediction endpoint resolved: %s", ep)
                    return ep
            except Exception as e:
                logger.info("Probe %s failed: %s", ep, e)
        logger.warning("No Laya prediction endpoint found; will use mock.")
        return None

    def _auth_headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    # ------------------------------------------------------------------ #
    # 请求 / 响应构造
    # ------------------------------------------------------------------ #
    @staticmethod
    def build_request(state: Dict[str, Any], questions: Dict[str, Any]) -> Dict[str, Any]:
        """构造发给 Laya 的 JSON body。"""
        return {"state": state, "questions": questions}

    @staticmethod
    def parse_response(resp_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        从 Laya 响应中提取结构化结果。
        返回: {"answers": {qname: {choice/score/noul/confidence}}, "model": str}
        """
        answers = resp_json.get("answers", {})
        out: Dict[str, Any] = {}
        for qname, a in answers.items():
            entry: Dict[str, Any] = {}
            if "choice" in a:
                entry["choice"] = a["choice"]
            if "score" in a:
                # score 是有序量表上的期望值 (0..N-1), 保留原值
                entry["score"] = a["score"]
            if "noul" in a:
                entry["noul"] = a["noul"]
            entry["confidence"] = a.get("confidence")
            if "probabilities" in a:
                entry["probabilities"] = a["probabilities"]
            out[qname] = entry
        routing = resp_json.get("routing") or {}
        model = routing.get("model") or resp_json.get("model") or "unknown"
        return {"answers": out, "model": model}

    # ------------------------------------------------------------------ #
    # 预测调用
    # ------------------------------------------------------------------ #
    def predict(
        self,
        state: Dict[str, Any],
        questions: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        单条 (或多 state 批量一次前向) 预测。
        真实服务不可用时走 mock。
        """
        ep = self._resolve_endpoint()
        if ep is None:
            return self._mock_predict(state, questions)

        body = self.build_request(state, questions)
        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                r = requests.post(
                    f"{self.base_url}{ep}",
                    json=body,
                    timeout=self.timeout,
                    headers=self._auth_headers(),
                )
                r.raise_for_status()
                parsed = self.parse_response(r.json())
                self._last_model = parsed.get("model")
                return parsed
            except Exception as e:
                last_err = e
                logger.warning(
                    "Laya predict attempt %d/%d failed: %s",
                    attempt + 1, self.max_retries + 1, e,
                )
                time.sleep(0.5 * (attempt + 1))
        # 真实调用彻底失败 -> mock 降级
        logger.warning("Laya predict failed (%s); using mock.", last_err)
        return self._mock_predict(state, questions)

    def batch_predict(
        self,
        states: List[Dict[str, Any]],
        questions: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        批量评分: 对多个 state 跑同一组 questions。
        真实 Laya 支持单 state 多 questions 一次前向; 多 state 此处循环调用
        (若后续 Laya 支持 batch state, 可在此合并为一次请求)。
        """
        return [self.predict(s, questions) for s in states]

    # ------------------------------------------------------------------ #
    # Mock 模式: 确定性加权公式
    # ------------------------------------------------------------------ #
    @staticmethod
    def _mock_predict(
        state: Dict[str, Any],
        questions: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Mock 评分: 基于输入特征的确定性加权公式。
        与 rubric 的判断原则对齐, 但不依赖 Laya 服务。
        """
        feats = state if isinstance(state, dict) else {}  # noqa: F841 (保留兼容)

        # 提取关键特征 (带安全默认值)
        # state 是 rubric.build_state 构造的嵌套结构; 把它铺平回扁平特征
        def _get(*path, default=None):
            cur: Any = state
            for p in path:
                if isinstance(cur, dict) and p in cur:
                    cur = cur[p]
                else:
                    return default
            return cur

        current_dhw = float(_get("thermal_stress", "current_dhw_cw", default=0.0) or 0.0)
        max_dhw_5yr = float(_get("thermal_stress", "max_dhw_5yr_cw", default=current_dhw) or current_dhw)
        mean_depth = float(_get("geography", "mean_depth_m", default=15.0) or 15.0)
        dist_dive = float(_get("geography", "distance_to_nearest_popular_dive_site_km", default=5.0) or 5.0)
        reef_area = float(_get("geography", "reef_area_km2", default=0.5) or 0.5)
        connectivity = float(_get("biophysical", "connectivity_score_1to5", default=3.0) or 3.0)
        rhi = float(_get("biophysical", "coralcore_rhi_0to100", default=50.0) or 50.0)
        hist_mort = _get("biophysical", "historical_bleaching_mortality_pct", default=None)
        if hist_mort is not None:
            try:
                hist_mort = float(hist_mort)
            except (TypeError, ValueError):
                hist_mort = None

        # --- 加权打分 (0-100) ---
        # 热压力: 当前 DHW (立即威胁) + 历史 5 年最大 DHW (脆弱性)
        #   高当前 DHW = 正在白化需立即干预; 高历史 DHW = 高价值脆弱礁应预先资助
        current_stress = min(100.0, current_dhw * 12.0)
        historical_vuln = min(100.0, max_dhw_5yr * 7.0)
        dhw_score = 0.6 * current_stress + 0.4 * historical_vuln
        # 水深: 浅 (<10m) 脆弱但易恢复 -> 中等偏好; 太深恢复难
        if mean_depth < 10:
            depth_score = 75.0
        elif mean_depth < 20:
            depth_score = 55.0
        else:
            depth_score = 35.0
        # 离潜点近 = 旅游价值高 (陡降, 0km=100, 10km=0)
        dive_score = max(0.0, 100.0 - dist_dive * 10.0)
        # 连通性好 = 恢复潜力高
        conn_score = connectivity / 5.0 * 100.0
        # RHI 中等最值得救 (太低=已崩, 太高=不用救)
        if 35 <= rhi <= 65:
            rhi_bonus = 100.0
        elif rhi > 65:
            rhi_bonus = 55.0
        else:
            rhi_bonus = 35.0
        # 礁体面积 (越大越有生态意义, 边际递减)
        area_score = min(100.0, reef_area * 50.0)

        score = (
            0.20 * dhw_score
            + 0.15 * depth_score
            + 0.20 * dive_score
            + 0.15 * conn_score
            + 0.20 * rhi_bonus
            + 0.10 * area_score
        )
        # 严重热压力 (DHW >= 8, NOAA 警告级别): 即使 RHI 偏低也需立即干预 (遮阳/浮毯)
        if current_dhw >= 8.0:
            score += 10.0
        # 历史死亡率极高且连通性差 -> 显著拉低
        if hist_mort is not None and hist_mort > 60 and connectivity < 2.5:
            score *= 0.5

        score = max(0.0, min(100.0, round(score, 1)))

        # --- 三分类 (阈值: invest>=60, monitor>=40) ---
        if score >= 60 and not (hist_mort is not None and hist_mort > 65):
            choice = "invest"
        elif score >= 40:
            choice = "monitor"
        else:
            choice = "deprioritize"

        confidence = 0.72 + 0.002 * abs(score - 50)  # 中段更"犹豫"
        confidence = round(min(0.95, confidence), 3)

        # 根据 questions 需要的 key 组织输出
        answers: Dict[str, Any] = {}
        for qname, qdef in questions.items():
            qtype = qdef.get("type")
            if qtype == "score":
                # Laya score 是有序量表 0..N-1; 这里把 0-100 映射到 0..4
                answers[qname] = {
                    "score": round(score / 100.0 * 4.0, 2),
                    "raw_score_0_100": score,
                    "confidence": confidence,
                }
            elif qtype == "choice":
                answers[qname] = {
                    "choice": choice,
                    "confidence": confidence,
                    "probabilities": {
                        "invest": 0.9 if choice == "invest" else 0.05,
                        "monitor": 0.9 if choice == "monitor" else 0.05,
                        "deprioritize": 0.9 if choice == "deprioritize" else 0.05,
                    },
                }
            elif qtype == "noul":
                answers[qname] = {"noul": confidence, "confidence": confidence}

        return {"answers": answers, "model": "mock-local", "routing": {"model": "mock"}}

    # ------------------------------------------------------------------ #
    @property
    def is_mock(self) -> bool:
        """当前是否处于 mock 模式 (服务不可用或 force_mock)。"""
        if self.force_mock:
            return True
        if self._available is None:
            return not self.check_health()
        return not self._available

    @property
    def last_model(self) -> Optional[str]:
        return self._last_model
