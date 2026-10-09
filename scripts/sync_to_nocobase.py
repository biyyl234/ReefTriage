"""
scripts/sync_to_nocobase.py
===========================
ReefTriage -> NocoBase 单向同步脚本。

从 ReefTriage /api/segments 拉取 28 个礁段数据，
通过 NocoBase REST API 写入/更新 reefs collection。

用法:
    .venv\\Scripts\\python.exe scripts/sync_to_nocobase.py

环境变量 (可选, 有默认值):
    REEFTRIAGE_URL   默认 http://127.0.0.1:8000
    NOCOBASE_URL     默认 http://127.0.0.1:13000
    NOCOBASE_EMAIL   默认 admin@nocobase.com
    NOCOBASE_PASSWORD 默认 admin123
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
REEFTRIAGE_URL = os.environ.get("REEFTRIAGE_URL", "http://127.0.0.1:8000")
NOCOBASE_URL = os.environ.get("NOCOBASE_URL", "http://127.0.0.1:13000").rstrip("/")
NOCOBASE_EMAIL = os.environ.get("NOCOBASE_EMAIL", "admin@nocobase.com")
NOCOBASE_PASSWORD = os.environ.get("NOCOBASE_PASSWORD", "admin123")

# ReefTriage JSON 字段 -> NocoBase reefs collection 字段
FIELD_MAP = {
    "segment_id": "segment_id",
    "name": "name",
    "name_zh": "name_zh",
    "lat": "lat",
    "lon": "lon",
    "current_dhw": "current_dhw",
    "max_dhw_5yr": "max_dhw_5yr",
    "mean_depth": "mean_depth",
    "distance_to_nearest_dive_site_km": "distance_to_dive_site",
    "connectivity_score": "connectivity_score",
    "rhi_score": "rhi_score",
    "reef_area_km2": "reef_area",
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
    """发送 HTTP 请求并返回 JSON 响应。"""
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
    """登录 NocoBase 获取 JWT token。"""
    resp = _request(
        "POST",
        f"{NOCOBASE_URL}/api/auth:signIn",
        {"email": NOCOBASE_EMAIL, "password": NOCOBASE_PASSWORD},
    )
    token = resp.get("data", {}).get("token")
    if not token:
        raise RuntimeError(f"登录失败, 响应: {resp}")
    return token


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 拉取 ReefTriage 数据
# ---------------------------------------------------------------------------
def fetch_reeftriage_segments() -> List[Dict[str, Any]]:
    resp = _request("GET", f"{REEFTRIAGE_URL}/api/segments")
    segments = resp.get("segments", [])
    print(f"[ReefTriage] 拉取到 {len(segments)} 个礁段")
    return segments


def map_segment(seg: Dict[str, Any]) -> Dict[str, Any]:
    """将 ReefTriage 礁段映射为 NocoBase reefs 记录。"""
    out: Dict[str, Any] = {}
    for src, dst in FIELD_MAP.items():
        val = seg.get(src)
        if val is not None:
            out[dst] = val
    out.setdefault("name_zh", None)
    out.setdefault("manual_override", False)
    return out


# ---------------------------------------------------------------------------
# 写入 NocoBase
# ---------------------------------------------------------------------------
def list_existing(token: str) -> Dict[str, int]:
    """获取已有记录的 segment_id -> id 映射 (用于判断 create 还是 update)。"""
    resp = _request(
        "GET",
        f"{NOCOBASE_URL}/api/reefs:list?pageSize=100",
        headers=auth_headers(token),
    )
    data = resp.get("data", [])
    mapping = {}
    for item in data:
        sid = item.get("segment_id")
        rid = item.get("id")
        if sid and rid:
            mapping[sid] = rid
    return mapping


def upsert_segment(token: str, record: Dict[str, Any],
                   existing_id: Optional[int] = None) -> str:
    """创建或更新一条 reefs 记录。"""
    sid = record["segment_id"]
    if existing_id:
        _request(
            "PATCH",
            f"{NOCOBASE_URL}/api/reefs:update?filterByTk={existing_id}",
            data=record,
            headers=auth_headers(token),
        )
        return "updated"
    else:
        _request(
            "POST",
            f"{NOCOBASE_URL}/api/reefs:create",
            data=record,
            headers=auth_headers(token),
        )
        return "created"


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("ReefTriage -> NocoBase 同步")
    print("=" * 60)

    # 1. 拉取 ReefTriage 数据
    segments = fetch_reeftriage_segments()
    if not segments:
        print("错误: 未从 ReefTriage 拉取到数据, 请确认 ReefTriage 已启动")
        sys.exit(1)

    # 2. 登录 NocoBase
    print(f"[NocoBase] 登录 {NOCOBASE_URL} ...")
    token = get_nocobase_token()
    print("[NocoBase] 登录成功")

    # 3. 获取已有记录
    existing = list_existing(token)
    print(f"[NocoBase] 已有 {len(existing)} 条记录")

    # 4. 逐条 upsert
    created = 0
    updated = 0
    skipped = 0
    for seg in segments:
        try:
            record = map_segment(seg)
            sid = record["segment_id"]
            eid = existing.get(sid)
            action = upsert_segment(token, record, eid)
            if action == "created":
                created += 1
            else:
                updated += 1
            print(f"  [{action}] {sid} {record.get('name', '')} score={record.get('score')}")
        except Exception as e:
            skipped += 1
            print(f"  [SKIP] {seg.get('segment_id')}: {e}")

    print("-" * 60)
    print(f"完成: 新建 {created}, 更新 {updated}, 跳过 {skipped}")
    print("=" * 60)


if __name__ == "__main__":
    main()
