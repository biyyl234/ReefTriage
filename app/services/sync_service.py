"""
app/services/sync_service.py
=============================
NocoBase 双向同步与服务状态探测业务逻辑。

封装从 main.py 迁移的：
- POST /api/sync-to-nocobase
- POST /api/sync-from-nocobase
- GET  /api/laya-status
- GET  /api/services-status
"""

from __future__ import annotations
import os
import sys
import socket
import logging
import subprocess
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)


# ---------------------------------------------------------------------------
# 同步脚本子进程执行
# ---------------------------------------------------------------------------
def _run_sync_script(script_name: str) -> Dict[str, Any]:
    """在子进程中运行同步脚本, 返回输出。"""
    script_path = os.path.join(PROJECT_ROOT, "scripts", script_name)
    python_exe = sys.executable
    try:
        result = subprocess.run(
            [python_exe, script_path],
            capture_output=True, text=True, timeout=120,
            cwd=PROJECT_ROOT,
        )
        return {
            "status": "ok" if result.returncode == 0 else "error",
            "returncode": result.returncode,
            "stdout": result.stdout[-2000:],
            "stderr": result.stderr[-1000:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "timeout (120s)"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def sync_to_nocobase() -> Dict[str, Any]:
    """触发 ReefTriage -> NocoBase 同步。"""
    logger.info("Sync to NocoBase triggered via API")
    return _run_sync_script("sync_to_nocobase.py")


def sync_from_nocobase() -> Dict[str, Any]:
    """触发 NocoBase -> ReefTriage 回写。"""
    logger.info("Sync from NocoBase triggered via API")
    return _run_sync_script("sync_from_nocobase.py")


# ---------------------------------------------------------------------------
# 服务状态探测
# ---------------------------------------------------------------------------
def get_laya_status() -> Dict[str, Any]:
    """检查 Laya/Jev 服务 (:5000) 状态。"""
    try:
        req = urllib.request.Request("http://127.0.0.1:5000/api/status")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = resp.read().decode("utf-8")
            return {"status": "ok", "detail": data[:500]}
    except urllib.error.HTTPError as e:
        return {"status": "ok", "detail": f"HTTP {e.code} (服务在线)"}
    except Exception as e:
        return {"status": "down", "detail": str(e)[:200]}


def _check_port(host: str, port: int, timeout: float = 1.0) -> bool:
    """检查 TCP 端口是否可连接。"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def get_services_status() -> Dict[str, Any]:
    """聚合所有服务状态: ReefTriage / Laya / PostgreSQL / NocoBase。
    端口检查并行执行, 最坏响应时间从 ~6s 降至 ~1s。
    """
    services: Dict[str, Any] = {}

    services["reeftriage"] = {"status": "ok", "port": 8000, "detail": "running"}

    # 并行检查三个外部服务端口
    ports_to_check = [("laya", 5000), ("postgres", 5432), ("nocobase", 13000)]
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(_check_port, "127.0.0.1", port): key
            for key, port in ports_to_check
        }
        results = {}
        for future in futures:
            key = futures[future]
            try:
                results[key] = future.result(timeout=1.5)
            except Exception:
                results[key] = False

    for key, port in ports_to_check:
        up = results.get(key, False)
        services[key] = {
            "status": "ok" if up else "down",
            "port": port,
            "detail": "running" if up else "not running",
        }

    return {
        "services": services,
        "timestamp": datetime.now().isoformat(),
    }
