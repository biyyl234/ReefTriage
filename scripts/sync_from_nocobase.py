"""
scripts/sync_from_nocobase.py
=============================
NocoBase -> ReefTriage 反向同步脚本。

从 NocoBase reefs collection 拉取数据，将有 manual_override 标记
或最近更新的记录回写到 ReefTriage PUT /api/segments/{id}。

用法:
    .venv\\Scripts\\python.exe scripts/sync_from_nocobase.py

环境变量 (可选, 有默认值):
    REEFTRIAGE_URL   默认 http://127.0.0.1:8000
    NOCOBASE_URL     默认 http://127.0.0.1:13000
    NOCOBASE_EMAIL   默认 admin@nocobase.com
    NOCOBASE_PASSWORD 默认 admin123
    SYNC_ALL         默认 "0" (仅同步 manual_override=true 的记录),
                     设为 "1" 同步所有记录
"""

from __future__ import annotations
import json
import os
import sys
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
REEFTRIAGE_URL = os.environ.get("REEFTRIAGE_URL", "http://127.0.0.1:8000").rstrip("/")
NOCOBASE_URL = os.environ.get("NOCOBASE_URL", "http://127.0.0.1:13000").rstrip("/")
NOCOBASE_EMAIL = os.environ.get("NOCOBASE_EMAIL", "admin@nocobase.com")
NOCOBASE_PASSWORD = os.environ.get("NOCOBASE_PASSWORD", "admin123")
SYNC_ALL = os.environ.get("SYNC_ALL", "0") == "1"

# NocoBase reefs 字段 -> ReefTriage JSON 字段 (反向映射)
REVERSE_FIELD_MAP = {
    "name": "name",
    "name_zh": "name_zh",
    "lat": "lat",
    "lon": "lon",
    "current_dhw": "current_dhw",
    "max_dhw_5yr": "max_dhw_5yr",
    "mean_depth": "mean_depth",
    "distance_to_dive_site": "distance_to_nearest_dive_site_km",
    "connectivity_score": "connectivity_score",
    "rhi_score": "rhi_score",
    "reef_area": "reef_area_km2",
    "score": "score",
    "choice": "choice",
    "laya_choice": "laya_choice",
    "confidence": "confidence",
    "model": "model",
    "manual_override": "manual_override",
}


# ---------------------------------------------------------------------------
# HTTP 工具
# ---------------------------------------------------------------------------
def _request(method: str, url: str, data: Optional[dict] = None,
             headers: Optional[dict] = None) -> Any:
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} {method} {url}: {raw[:500]}") from e


def get_nocobase_token() -> str:
    resp = _request(
        "POST",
        f"{NOCOBASE_URL}/api/auth:signIn",
        {"email": NOCOBASE_EMAIL, "password": NOCOBASE_PASSWORD},
    )
    token = resp.get("data", {}).get("token")
    if not token:
        raise RuntimeError(f"登录失败, 响应: {resp}")
    return token


# ---------------------------------------------------------------------------
# 拉取 NocoBase 数据
# ---------------------------------------------------------------------------
def fetch_nocobase_reefs(token: str) -> List[Dict[str, Any]]:
    resp = _request(
        "GET",
        f"{NOCOBASE_URL}/api/reefs:list?pageSize=100",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = resp.get("data", [])
    print(f"[NocoBase] 拉取到 {len(data)} 条 reefs 记录")
    return data


def map_to_reeftriage(record: Dict[str, Any]) -> Dict[str, Any]:
    """将 NocoBase 记录映射为 ReefTriage 更新字段。"""
    out: Dict[str, Any] = {}
    for src, dst in REVERSE_FIELD_MAP.items():
        val = record.get(src)
        if val is not None:
            out[dst] = val
    return out


# ---------------------------------------------------------------------------
# 回写 ReefTriage
# ---------------------------------------------------------------------------
def push_to_reeftriage(segment_id: str, updates: Dict[str, Any]) -> bool:
    """调用 ReefTriage PUT /api/segments/{id} 回写。"""
    try:
        _request(
            "PUT",
            f"{REEFTRIAGE_URL}/api/segments/{segment_id}",
            data=updates,
        )
        return True
    except Exception as e:
        print(f"    回写失败: {e}")
        return False


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("NocoBase -> ReefTriage 反向同步")
    print(f"模式: {'全部同步' if SYNC_ALL else '仅同步 manual_override=true'}")
    print("=" * 60)

    # 1. 登录 NocoBase
    print(f"[NocoBase] 登录 {NOCOBASE_URL} ...")
    token = get_nocobase_token()
    print("[NocoBase] 登录成功")

    # 2. 拉取 NocoBase 数据
    records = fetch_nocobase_reefs(token)
    if not records:
        print("NocoBase 中暂无 reefs 记录")
        sys.exit(0)

    # 3. 筛选需要同步的记录
    if SYNC_ALL:
        to_sync = records
    else:
        to_sync = [r for r in records if r.get("manual_override") is True]
    print(f"需要回写: {len(to_sync)} 条")

    # 4. 逐条回写
    success = 0
    failed = 0
    for record in to_sync:
        sid = record.get("segment_id")
        if not sid:
            print("  [SKIP] 记录缺少 segment_id")
            failed += 1
            continue
        updates = map_to_reeftriage(record)
        if not updates:
            print(f"  [SKIP] {sid}: 无可更新字段")
            continue
        print(f"  [SYNC] {sid} {record.get('name', '')} score={record.get('score')}")
        if push_to_reeftriage(sid, updates):
            success += 1
        else:
            failed += 1

    print("-" * 60)
    print(f"完成: 成功 {success}, 失败 {failed}")
    print("=" * 60)


if __name__ == "__main__":
    main()
