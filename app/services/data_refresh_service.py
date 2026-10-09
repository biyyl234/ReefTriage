"""
app/services/data_refresh_service.py
====================================
手动点击 "更新数据" 触发的实时数据接入流水线。

流程 (按用户选择的数据源):
    下载脚本 (scripts/download_*.py)
        -> scripts/compute_features.py   (计算 reef_features.csv)
        -> scripts/rescore_fusion.py     (清缓存, 用新特征重新融合评分, 写 scored_segments.json)
        -> scripts/run_scoring.py        (打印评分分布, 供日志确认)
    -> 进程内重载 engine 内存缓存, 使现有 API 立刻读到新分数。

设计要点:
- 所有脚本通过 subprocess 调用, 使用项目 .venv 解释器 (绝对路径), cwd=项目根目录。
- 不在本进程内 import 数据脚本, 避免环境污染 / 长时间下载阻塞事件循环。
- force=True 时, 先把该数据源已有的输出文件改名备份 (*.bak.<ts>),
  这样下载脚本自带的 "已存在则跳过" 逻辑会触发真实的重新下载 (非破坏性, 旧文件保留)。
- Copernicus 需要免费注册; 未检测到凭据时跳过并返回注册指引, 不自动登录。
- 不修改任何现有评分逻辑, 仅编排现有脚本 + 重载内存缓存。
"""

from __future__ import annotations

import os
import sys
import json
import shutil
import logging
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 项目根目录 (本文件位于 app/services/ 下, 上溯两级)
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)

# 项目 .venv 解释器 (绝对路径)。若不存在则回退到当前解释器。
VENV_PYTHON = r"C:\Users\biyyl234\Desktop\AI4Climatedemo\.venv\Scripts\python.exe"
if not os.path.exists(VENV_PYTHON):
    VENV_PYTHON = sys.executable

SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "scripts")
PROCESSED_DIR = os.path.join(PROJECT_ROOT, "data", "processed")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data", "output")


# ---------------------------------------------------------------------------
# 数据源注册表
# ---------------------------------------------------------------------------
# outputs: force 模式下需要先备份的产物文件 (绝对路径)。
# needs_auth: True 表示需要 Copernicus 注册凭据。
SOURCE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "crw": {
        "script": "download_crw.py",
        "label": "NOAA CRW 5km DHW/SST (ERDDAP, 免费免注册)",
        "needs_auth": False,
        "outputs": [
            os.path.join(PROCESSED_DIR, "crw_current.nc"),
            os.path.join(PROCESSED_DIR, "crw_history.nc"),
        ],
        "timeout": 600,
    },
    "bathymetry": {
        "script": "download_bathymetry.py",
        "label": "ETOPO 2022 水深 (ERDDAP, 免费免注册)",
        "needs_auth": False,
        "outputs": [
            os.path.join(PROCESSED_DIR, "depth.nc"),
        ],
        "timeout": 600,
    },
    "osm": {
        "script": "download_osm.py",
        "label": "OpenStreetMap 潜点 POI (Overpass, 免费免注册)",
        "needs_auth": False,
        "outputs": [
            os.path.join(PROCESSED_DIR, "dive_sites.geojson"),
        ],
        "timeout": 300,
    },
    "copernicus": {
        "script": "download_copernicus.py",
        "label": "Copernicus Marine 物理/生化 (需免费注册)",
        "needs_auth": True,
        "outputs": [],  # 写入 data/copernicus/
        "timeout": 900,
    },
}

DEFAULT_SOURCES: List[str] = ["crw", "bathymetry", "osm"]

# Copernicus 注册指引 (凭据缺失时返回给前端)
COPERNICUS_HINT = (
    "Copernicus Marine 需要免费注册后才能下载: "
    "1) 打开 https://data.marine.copernicus.eu/register 注册账号; "
    "2) 在本项目 .venv 环境运行 `copernicusmarine login` 并输入用户名密码; "
    "3) 重新点击 更新数据 并勾选 copernicus。"
)


# ---------------------------------------------------------------------------
# 凭据检测
# ---------------------------------------------------------------------------
def copernicus_credentials_present() -> bool:
    """检测 Copernicus Marine 是否已配置凭据 (环境变量或本地登录文件)。"""
    if os.environ.get("COPERNICUSMARINE_USERNAME") or os.environ.get(
        "COPERNICUSMARINE_PASSWORD"
    ):
        return True
    cred_file = os.path.expanduser(
        r"~\.copernicusmarine\.copernicusmarine-credentials"
    )
    return os.path.exists(cred_file)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _backup_outputs(paths: List[str], stamp: str) -> List[str]:
    """把已存在的产物文件改名为 <name>.bak.<stamp> (非破坏性备份)。
    返回完成的备份描述列表。"""
    backed = []
    for p in paths:
        if os.path.exists(p):
            bak = f"{p}.bak.{stamp}"
            try:
                shutil.move(p, bak)
                backed.append(os.path.basename(p) + f" -> {os.path.basename(bak)}")
            except Exception as e:  # pragma: no cover
                logger.warning("backup failed for %s: %s", p, e)
    return backed


def _run_script(script_name: str, timeout: int = 600) -> Dict[str, Any]:
    """用 .venv Python 在子进程中运行 scripts/<script_name>, 捕获输出。"""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    step: Dict[str, Any] = {
        "script": script_name,
        "started_at": _now_iso(),
    }
    if not os.path.exists(script_path):
        step.update(status="error", error=f"script not found: {script_path}")
        return step

    t0 = datetime.now()
    try:
        proc = subprocess.run(
            [VENV_PYTHON, script_path],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        dt = (datetime.now() - t0).total_seconds()
        step.update(
            status="ok" if proc.returncode == 0 else "error",
            returncode=proc.returncode,
            duration_s=round(dt, 1),
            # 截断超长输出, 保留尾部 (最关键的结果摘要通常在末尾)
            stdout=(proc.stdout or "")[-4000:],
            stderr=(proc.stderr or "")[-2000:],
        )
    except subprocess.TimeoutExpired as e:
        step.update(
            status="error",
            error=f"timeout after {timeout}s",
            stdout=(e.stdout or "")[-2000:] if isinstance(e.stdout, str) else "",
            stderr=(e.stderr or "")[-1000:] if isinstance(e.stderr, str) else "",
        )
    except Exception as e:
        step.update(status="error", error=str(e))
    step["finished_at"] = _now_iso()
    return step


def _reload_engine_cache() -> Dict[str, Any]:
    """流水线结束后, 在进程内重载评分引擎内存缓存,
    使 /api/segments 等现有接口立即读到新写入的 scored_segments.json。
    不改动评分逻辑, 仅重新读取 rescore_fusion.py 刚写好的缓存文件。"""
    try:
        from ..scoring import data_loader
        from ..scoring.engine import engine

        cache_path = data_loader.SCORED_JSON
        if not os.path.exists(cache_path):
            return {"reloaded": False, "reason": "scored_segments.json missing"}
        with open(cache_path, encoding="utf-8") as f:
            scored = json.load(f)
        engine._scored = scored  # type: ignore[attr-defined]
        engine._segments = [  # type: ignore[attr-defined]
            {k: v for k, v in s.items() if k != "score_details"} for s in scored
        ]
        return {"reloaded": True, "segments": len(scored)}
    except Exception as e:
        logger.warning("engine cache reload failed: %s", e)
        return {"reloaded": False, "reason": str(e)}


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
def run_refresh(sources: Optional[List[str]] = None, force: bool = True) -> Dict[str, Any]:
    """执行 数据拉取 -> 特征 -> 评分 完整流水线。

    :param sources: 要拉取的数据源 key 列表, 见 SOURCE_REGISTRY。
                    默认 ["crw", "bathymetry", "osm"]。
    :param force: True 时先备份已有产物文件, 强制重新下载。
    :return: 结构化执行日志 {status, steps, skipped, summary, hints, ...}
    """
    started = _now_iso()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if not sources:
        sources = list(DEFAULT_SOURCES)

    steps: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    hints: List[str] = []
    fatal = False

    # ---- 1. 逐数据源下载 ----
    for src in sources:
        key = (src or "").strip().lower()
        info = SOURCE_REGISTRY.get(key)
        if info is None:
            skipped.append({"source": src, "reason": f"unknown source '{src}' (忽略)"})
            continue

        # Copernicus 凭据检查
        if info["needs_auth"] and not copernicus_credentials_present():
            skipped.append({
                "source": key,
                "reason": "Copernicus 凭据未配置, 已跳过 (未尝试自动注册)",
            })
            hints.append(COPERNICUS_HINT)
            continue

        step: Dict[str, Any] = {
            "phase": "download",
            "source": key,
            "label": info["label"],
        }
        # force: 备份已有产物, 触发真实重下
        if force and info["outputs"]:
            backed = _backup_outputs(info["outputs"], stamp)
            if backed:
                step["backed_up"] = backed

        result = _run_script(info["script"], timeout=int(info["timeout"]))
        step.update(result)
        steps.append(step)
        if result.get("status") == "error":
            # 下载失败不立即中断, 让后续步骤日志完整; 但标记致命 (compute/score 仍会尝试,
            # 若缺文件会在对应步骤报错, 用户可在日志里看到根因)
            fatal = True

    # ---- 2. 计算特征 ----
    steps.append({
        "phase": "compute_features",
        "label": "计算礁段特征 (compute_features.py)",
        **_run_script("compute_features.py", timeout=600),
    })

    # ---- 3. 融合重评分 (清缓存, 用新特征重新评分) ----
    steps.append({
        "phase": "rescore",
        "label": "融合重评分 (rescore_fusion.py, 清缓存)",
        **_run_script("rescore_fusion.py", timeout=600),
    })

    # ---- 4. 打印评分分布 (run_scoring.py, 仅加载新缓存做确认) ----
    steps.append({
        "phase": "report",
        "label": "评分结果预览 (run_scoring.py)",
        **_run_script("run_scoring.py", timeout=300),
    })

    # ---- 5. 进程内重载引擎缓存, 使现有 API 立刻生效 ----
    reload_info = _reload_engine_cache()

    # ---- 汇总 ----
    n_ok = sum(1 for s in steps if s.get("status") == "ok")
    n_err = sum(1 for s in steps if s.get("status") == "error")

    # 整体状态以核心步骤为准:
    #   - rescore (融合重评分) 或 compute_features 失败 -> error (新分数没产生)
    #   - 仅下载/报告打印失败但评分成功 -> partial
    #   - 全部成功 -> ok
    def _step_status(phase):
        for s in steps:
            if s.get("phase") == phase:
                return s.get("status")
        return None

    rescore_st = _step_status("rescore")
    compute_st = _step_status("compute_features")
    if rescore_st == "error" or compute_st == "error":
        overall = "error"
    elif n_err > 0:
        overall = "partial"
    else:
        overall = "ok"

    if not copernicus_credentials_present() and "copernicus" in sources:
        hints.append(COPERNICUS_HINT)

    return {
        "status": overall,
        "started_at": started,
        "finished_at": _now_iso(),
        "requested_sources": sources,
        "force": force,
        "venv_python": VENV_PYTHON,
        "steps": steps,
        "skipped": skipped,
        "hints": hints,
        "engine_reload": reload_info,
        "summary": {
            "steps_ok": n_ok,
            "steps_error": n_err,
            "skipped_count": len(skipped),
        },
    }
