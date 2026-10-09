"""
scripts/setup_nocobase_pages.py
===============================
通过 NocoBase REST API 创建 UI 页面 (礁段列表、详情、图表、概览)。

用法:
    .venv\\Scripts\\python.exe scripts/setup_nocobase_pages.py
"""

from __future__ import annotations
import json
import os
import sys
import urllib.request
import urllib.error
from typing import Any, Dict, Optional

NOCOBASE_URL = os.environ.get("NOCOBASE_URL", "http://127.0.0.1:13000").rstrip("/")
NOCOBASE_EMAIL = os.environ.get("NOCOBASE_EMAIL", "admin@nocobase.com")
NOCOBASE_PASSWORD = os.environ.get("NOCOBASE_PASSWORD", "admin123")


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


def get_token() -> str:
    resp = _request("POST", f"{NOCOBASE_URL}/api/auth:signIn",
                    {"email": NOCOBASE_EMAIL, "password": NOCOBASE_PASSWORD})
    return resp["data"]["token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def list_schemas(token: str) -> list:
    resp = _request("GET", f"{NOCOBASE_URL}/api/uiSchemas:list?pageSize=100",
                    headers=auth(token))
    return resp.get("data", [])


def create_schema(token: str, schema: dict) -> dict:
    return _request("POST", f"{NOCOBASE_URL}/api/uiSchemas:create",
                    data=schema, headers=auth(token))


def get_schema(token: str, name: str) -> Optional[dict]:
    resp = _request("GET",
                    f"{NOCOBASE_URL}/api/uiSchemas:list?filter[name]={name}&pageSize=1",
                    headers=auth(token))
    data = resp.get("data", [])
    return data[0] if data else None


def main():
    print("=" * 60)
    print("NocoBase 页面初始化")
    print("=" * 60)

    token = get_token()
    print("登录成功")

    # 列出已有 schema
    existing = list_schemas(token)
    existing_names = {s.get("name") for s in existing}
    print(f"已有 UI Schema: {len(existing)} 个")
    for s in existing:
        print(f"  - {s.get('name')} ({s.get('x-component', '?')})")

    # ---------------------------------------------------------------
    # 1. 礁段列表页 (Table)
    # ---------------------------------------------------------------
    if "reefs-list" not in existing_names:
        print("\n[1/4] 创建礁段列表页...")
        list_schema = {
            "name": "reefs-list",
            "type": "void",
            "x-component": "Page",
            "x-component-props": {},
            "title": "Reef Segments 礁段列表",
            "properties": {
                "card": {
                    "type": "void",
                    "x-component": "CardItem",
                    "x-component-props": {"title": "All Reef Segments"},
                    "properties": {
                        "actions": {
                            "type": "void",
                            "x-component": "ActionBar",
                            "x-initializer": "Table:configureActions",
                            "properties": {
                                "add": {
                                    "type": "void",
                                    "x-component": "Action",
                                    "x-component-props": {
                                        "type": "primary",
                                        "icon": "PlusOutlined",
                                        "title": "Add new",
                                    },
                                    "x-action": "create",
                                },
                                "filter": {
                                    "type": "void",
                                    "x-component": "FilterAction",
                                },
                            },
                        },
                        "table": {
                            "type": "array",
                            "x-component": "Table",
                            "x-use-component-props": "useTableProps",
                            "x-initializer": "Table:configureColumns",
                            "x-collection": "reefs",
                            "x-pagination": {"pageSize": 28},
                            "properties": {
                                "segment_id": {
                                    "type": "string",
                                    "x-component": "Table.Column",
                                    "x-collection-field": "reefs.segment_id",
                                    "x-component-props": {"width": 100},
                                    "properties": {
                                        "link": {
                                            "type": "void",
                                            "x-component": "Action.Link",
                                            "x-action": "view",
                                        },
                                    },
                                },
                                "name": {
                                    "type": "string",
                                    "x-component": "Table.Column",
                                    "x-collection-field": "reefs.name",
                                },
                                "score": {
                                    "type": "integer",
                                    "x-component": "Table.Column",
                                    "x-collection-field": "reefs.score",
                                    "x-component-props": {"sorter": True, "width": 80},
                                },
                                "choice": {
                                    "type": "string",
                                    "x-component": "Table.Column",
                                    "x-collection-field": "reefs.choice",
                                    "x-component-props": {"width": 120},
                                },
                                "laya_choice": {
                                    "type": "string",
                                    "x-component": "Table.Column",
                                    "x-collection-field": "reefs.laya_choice",
                                    "x-component-props": {"width": 120},
                                },
                                "current_dhw": {
                                    "type": "float",
                                    "x-component": "Table.Column",
                                    "x-collection-field": "reefs.current_dhw",
                                },
                                "connectivity_score": {
                                    "type": "float",
                                    "x-component": "Table.Column",
                                    "x-collection-field": "reefs.connectivity_score",
                                },
                                "rhi_score": {
                                    "type": "float",
                                    "x-component": "Table.Column",
                                    "x-collection-field": "reefs.rhi_score",
                                },
                                "manual_override": {
                                    "type": "boolean",
                                    "x-component": "Table.Column",
                                    "x-collection-field": "reefs.manual_override",
                                    "x-component-props": {"width": 100},
                                },
                                "actions": {
                                    "type": "void",
                                    "x-component": "Table.Column",
                                    "x-component-props": {"width": 120, "fixed": "right"},
                                    "properties": {
                                        "edit": {
                                            "type": "void",
                                            "x-component": "Action.Link",
                                            "x-action": "update",
                                            "x-component-props": {"title": "Edit"},
                                        },
                                        "delete": {
                                            "type": "void",
                                            "x-component": "Action.Link",
                                            "x-action": "destroy",
                                            "x-component-props": {"title": "Delete"},
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        }
        create_schema(token, list_schema)
        print("  礁段列表页创建成功")
    else:
        print("\n[1/4] 礁段列表页已存在, 跳过")

    # ---------------------------------------------------------------
    # 2. 统计概览页
    # ---------------------------------------------------------------
    if "dashboard" not in existing_names:
        print("[2/4] 创建统计概览页...")
        dashboard_schema = {
            "name": "dashboard",
            "type": "void",
            "x-component": "Page",
            "title": "Dashboard 统计概览",
            "properties": {
                "row1": {
                    "type": "void",
                    "x-component": "Grid.Row",
                    "properties": {
                        "col1": {
                            "type": "void",
                            "x-component": "Grid.Col",
                            "x-component-props": {"span": 8},
                            "properties": {
                                "total": {
                                    "type": "void",
                                    "x-component": "CardItem",
                                    "x-component-props": {"title": "Total Reefs 总礁段数"},
                                    "properties": {
                                        "stat": {
                                            "type": "void",
                                            "x-component": "Statistic",
                                            "x-collection": "reefs",
                                            "x-use-component-props": "useStatisticProps",
                                            "x-component-props": {
                                                "field": "segment_id",
                                                "statistic": "count",
                                            },
                                        },
                                    },
                                },
                            },
                        },
                        "col2": {
                            "type": "void",
                            "x-component": "Grid.Col",
                            "x-component-props": {"span": 8},
                            "properties": {
                                "invest": {
                                    "type": "void",
                                    "x-component": "CardItem",
                                    "x-component-props": {"title": "Invest 优先恢复"},
                                    "properties": {
                                        "stat": {
                                            "type": "void",
                                            "x-component": "Statistic",
                                            "x-collection": "reefs",
                                            "x-use-component-props": "useStatisticProps",
                                            "x-component-props": {
                                                "field": "segment_id",
                                                "statistic": "count",
                                                "filter": {"choice": {"$eq": "invest"}},
                                            },
                                        },
                                    },
                                },
                            },
                        },
                        "col3": {
                            "type": "void",
                            "x-component": "Grid.Col",
                            "x-component-props": {"span": 8},
                            "properties": {
                                "avg_score": {
                                    "type": "void",
                                    "x-component": "CardItem",
                                    "x-component-props": {"title": "Avg Score 平均分"},
                                    "properties": {
                                        "stat": {
                                            "type": "void",
                                            "x-component": "Statistic",
                                            "x-collection": "reefs",
                                            "x-use-component-props": "useStatisticProps",
                                            "x-component-props": {
                                                "field": "score",
                                                "statistic": "avg",
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
                "row2": {
                    "type": "void",
                    "x-component": "Grid.Row",
                    "properties": {
                        "col1": {
                            "type": "void",
                            "x-component": "Grid.Col",
                            "x-component-props": {"span": 12},
                            "properties": {
                                "chart_choice": {
                                    "type": "void",
                                    "x-component": "CardItem",
                                    "x-component-props": {"title": "Classification Distribution 分类分布"},
                                    "properties": {
                                        "chart": {
                                            "type": "void",
                                            "x-component": "Chart",
                                            "x-collection": "reefs",
                                            "x-use-component-props": "useChartProps",
                                            "x-component-props": {
                                                "type": "pie",
                                                "xField": "choice",
                                                "yField": "count",
                                                "seriesField": "choice",
                                            },
                                        },
                                    },
                                },
                            },
                        },
                        "col2": {
                            "type": "void",
                            "x-component": "Grid.Col",
                            "x-component-props": {"span": 12},
                            "properties": {
                                "chart_score": {
                                    "type": "void",
                                    "x-component": "CardItem",
                                    "x-component-props": {"title": "Score Distribution 分数分布"},
                                    "properties": {
                                        "chart": {
                                            "type": "void",
                                            "x-component": "Chart",
                                            "x-collection": "reefs",
                                            "x-use-component-props": "useChartProps",
                                            "x-component-props": {
                                                "type": "column",
                                                "xField": "score",
                                                "yField": "count",
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        }
        create_schema(token, dashboard_schema)
        print("  统计概览页创建成功")
    else:
        print("[2/4] 统计概览页已存在, 跳过")

    # ---------------------------------------------------------------
    # 3. 预算分配页 (链接到 ReefTriage priority API)
    # ---------------------------------------------------------------
    if "budget" not in existing_names:
        print("[3/4] 创建预算分配页...")
        budget_schema = {
            "name": "budget",
            "type": "void",
            "x-component": "Page",
            "title": "Budget Allocation 预算分配",
            "properties": {
                "card": {
                    "type": "void",
                    "x-component": "CardItem",
                    "x-component-props": {
                        "title": "Priority Reefs (Invest) 优先恢复名单",
                    },
                    "properties": {
                        "table": {
                            "type": "array",
                            "x-component": "Table",
                            "x-use-component-props": "useTableProps",
                            "x-collection": "reefs",
                            "x-pagination": {"pageSize": 28},
                            "x-component-props": {
                                "defaultFilter": {"choice": {"$eq": "invest"}},
                            },
                            "properties": {
                                "segment_id": {
                                    "type": "string",
                                    "x-component": "Table.Column",
                                    "x-collection-field": "reefs.segment_id",
                                },
                                "name": {
                                    "type": "string",
                                    "x-component": "Table.Column",
                                    "x-collection-field": "reefs.name",
                                },
                                "score": {
                                    "type": "integer",
                                    "x-component": "Table.Column",
                                    "x-collection-field": "reefs.score",
                                    "x-component-props": {"sorter": True},
                                },
                                "reef_area": {
                                    "type": "float",
                                    "x-component": "Table.Column",
                                    "x-collection-field": "reefs.reef_area",
                                },
                                "connectivity_score": {
                                    "type": "float",
                                    "x-component": "Table.Column",
                                    "x-collection-field": "reefs.connectivity_score",
                                },
                            },
                        },
                    },
                },
            },
        }
        create_schema(token, budget_schema)
        print("  预算分配页创建成功")
    else:
        print("[3/4] 预算分配页已存在, 跳过")

    # ---------------------------------------------------------------
    # 4. 菜单配置 (将页面加入导航)
    # ---------------------------------------------------------------
    print("[4/4] 配置菜单...")
    # NocoBase 菜单通过 uiSchemas 的特殊 x-route 配置自动生成
    # 页面创建后会自动出现在菜单中
    print("  菜单将自动包含以上页面")

    print("\n" + "=" * 60)
    print("页面初始化完成!")
    print("请刷新 http://127.0.0.1:13000/admin 查看页面")
    print("=" * 60)


if __name__ == "__main__":
    main()
