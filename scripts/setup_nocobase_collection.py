"""
scripts/setup_nocobase_collection.py
====================================
通过 NocoBase REST API 创建 reefs collection 及其字段。

用法:
    .venv\\Scripts\\python.exe scripts/setup_nocobase_collection.py

环境变量:
    NOCOBASE_URL     默认 http://127.0.0.1:13000
    NOCOBASE_EMAIL   默认 admin@nocobase.com
    NOCOBASE_PASSWORD 默认 admin123
"""

from __future__ import annotations
import json
import os
import sys
import time
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

NOCOBASE_URL = os.environ.get("NOCOBASE_URL", "http://127.0.0.1:13000").rstrip("/")
NOCOBASE_EMAIL = os.environ.get("NOCOBASE_EMAIL", "admin@nocobase.com")
NOCOBASE_PASSWORD = os.environ.get("NOCOBASE_PASSWORD", "admin123")


def _request(method: str, url: str, data: Optional[dict] = None,
             headers: Optional[dict] = None, retries: int = 3) -> Any:
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    body = json.dumps(data).encode("utf-8") if data is not None else None
    for attempt in range(retries):
        req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            if e.code == 409:  # conflict = already exists
                return {"_exists": True, "_raw": raw}
            if attempt < retries - 1:
                time.sleep(2)
                continue
            raise RuntimeError(f"HTTP {e.code} {method} {url}: {raw[:500]}") from e
        except urllib.error.URLError as e:
            if attempt < retries - 1:
                time.sleep(3)
                continue
            raise RuntimeError(f"连接失败 {url}: {e}") from e


def get_token() -> str:
    resp = _request(
        "POST",
        f"{NOCOBASE_URL}/api/auth:signIn",
        {"email": NOCOBASE_EMAIL, "password": NOCOBASE_PASSWORD},
    )
    token = resp.get("data", {}).get("token")
    if not token:
        raise RuntimeError(f"登录失败: {resp}")
    return token


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Collection 定义
# ---------------------------------------------------------------------------
REEFS_FIELDS = [
    # 基础标识
    {"name": "segment_id", "type": "string", "interface": "input",
     "uiSchema": {"title": "Segment ID", "required": True},
     "unique": True},
    {"name": "name", "type": "string", "interface": "input",
     "uiSchema": {"title": "Name"}},
    {"name": "name_zh", "type": "string", "interface": "input",
     "uiSchema": {"title": "中文名"}},
    # 地理位置
    {"name": "lat", "type": "float", "interface": "inputNumber",
     "uiSchema": {"title": "纬度"}},
    {"name": "lon", "type": "float", "interface": "inputNumber",
     "uiSchema": {"title": "经度"}},
    # 环境特征
    {"name": "current_dhw", "type": "float", "interface": "inputNumber",
     "uiSchema": {"title": "当前 DHW"}},
    {"name": "max_dhw_5yr", "type": "float", "interface": "inputNumber",
     "uiSchema": {"title": "5年最大 DHW"}},
    {"name": "mean_depth", "type": "float", "interface": "inputNumber",
     "uiSchema": {"title": "平均深度 (m)"}},
    {"name": "distance_to_dive_site", "type": "float", "interface": "inputNumber",
     "uiSchema": {"title": "距潜点距离 (km)"}},
    # 生态评分
    {"name": "connectivity_score", "type": "float", "interface": "inputNumber",
     "uiSchema": {"title": "连通性评分 (1-5)"}},
    {"name": "rhi_score", "type": "float", "interface": "inputNumber",
     "uiSchema": {"title": "RHI 评分 (0-100)"}},
    {"name": "reef_area", "type": "float", "interface": "inputNumber",
     "uiSchema": {"title": "礁区面积 (km²)"}},
    # 评分结果
    {"name": "score", "type": "integer", "interface": "inputNumber",
     "uiSchema": {"title": "优先级评分 (0-100)"}},
    {"name": "choice", "type": "string", "interface": "select",
     "uiSchema": {"title": "分类", "enum": ["invest", "monitor", "deprioritize"],
                  "enumNames": {"invest": "Invest 优先恢复",
                                "monitor": "Monitor 观察",
                                "deprioritize": "Deprioritize 低优先级"}}},
    {"name": "laya_choice", "type": "string", "interface": "select",
     "uiSchema": {"title": "Laya 建议", "enum": ["invest", "monitor", "deprioritize", ""],
                  "enumNames": {"invest": "Invest", "monitor": "Monitor",
                                "deprioritize": "Deprioritize", "": "无"}}},
    {"name": "confidence", "type": "float", "interface": "inputNumber",
     "uiSchema": {"title": "置信度"}},
    {"name": "model", "type": "string", "interface": "input",
     "uiSchema": {"title": "模型"}},
    # 管理字段
    {"name": "manual_override", "type": "boolean", "interface": "checkbox",
     "uiSchema": {"title": "人工覆盖"}, "defaultValue": False},
]


def collection_exists(token: str, name: str) -> bool:
    try:
        resp = _request(
            "GET",
            f"{NOCOBASE_URL}/api/collections:get?filterByTk={name}",
            headers=auth(token),
        )
        return resp.get("data") is not None
    except Exception:
        return False


def create_collection(token: str):
    """创建 reefs collection (不含字段, 字段单独创建)。"""
    body = {
        "name": "reefs",
        "title": "Reef Segments 礁段管理",
        "sortable": False,
    }
    resp = _request(
        "POST",
        f"{NOCOBASE_URL}/api/collections:create",
        data=body,
        headers=auth(token),
    )
    if resp.get("_exists"):
        print("  collection 'reefs' 已存在")
    else:
        print("  collection 'reefs' 创建成功")


def create_field(token: str, field: dict):
    """为 reefs collection 创建一个字段。"""
    name = field["name"]
    resp = _request(
        "POST",
        f"{NOCOBASE_URL}/api/collections/reefs/fields:create",
        data=field,
        headers=auth(token),
    )
    if resp.get("_exists"):
        print(f"  字段 {name}: 已存在")
    else:
        print(f"  字段 {name}: 创建成功")


def main():
    print("=" * 60)
    print("NocoBase reefs Collection 初始化")
    print("=" * 60)

    # 等待 NocoBase 就绪
    print(f"连接 NocoBase: {NOCOBASE_URL}")
    for i in range(10):
        try:
            token = get_token()
            break
        except Exception as e:
            print(f"  等待 NocoBase 启动... ({i+1}/10) {e}")
            time.sleep(5)
    else:
        print("错误: 无法连接 NocoBase, 请确认服务已启动")
        sys.exit(1)
    print("登录成功")

    # 创建 collection
    print("\n[1/2] 创建 collection 'reefs' ...")
    if not collection_exists(token, "reefs"):
        create_collection(token)
    else:
        print("  collection 'reefs' 已存在")

    # 创建字段
    print(f"\n[2/2] 创建 {len(REEFS_FIELDS)} 个字段 ...")
    for field in REEFS_FIELDS:
        try:
            create_field(token, field)
        except Exception as e:
            print(f"  字段 {field['name']}: 失败 - {e}")

    print("\n" + "=" * 60)
    print("Collection 初始化完成!")
    print("接下来运行: python scripts/sync_to_nocobase.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
