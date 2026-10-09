"""
Create NocoBase pages with embedded iframes for ReefTriage demo and admin panel.
"""
import urllib.request, json, sys

NOCO = "http://127.0.0.1:13000"

def req(method, url, data=None, token=None):
    hdrs = {"Content-Type": "application/json"}
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data else None
    r = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        print(f"  HTTP {e.code}: {raw[:300]}")
        return None

# Login
resp = req("POST", f"{NOCO}/api/auth:signIn", {"email":"admin@nocobase.com","password":"admin123"})
token = resp["data"]["token"]
print("Logged in")

def schema_exists(name):
    resp = req("GET", f"{NOCO}/api/uiSchemas:list?filter[name]={name}&pageSize=1", token=token)
    return len(resp.get("data", [])) > 0 if resp else False

def create_schema(schema):
    name = schema["name"]
    if schema_exists(name):
        print(f"  '{name}' already exists, skipping")
        return
    result = req("POST", f"{NOCO}/api/uiSchemas:create", data=schema, token=token)
    if result:
        print(f"  '{name}' created successfully")
    else:
        print(f"  '{name}' creation failed")

# ============================================================
# Page 1: ReefTriage Demo (iframe of main map)
# ============================================================
print("\n[1/2] Creating ReefTriage Demo page...")
demo_iframe = (
    '<iframe src="http://127.0.0.1:8000/" '
    'style="width:100%;height:800px;border:1px solid #ddd;border-radius:8px;" '
    'allow="fullscreen"></iframe>'
)
demo_schema = {
    "name": "reeftriage-demo",
    "type": "void",
    "x-component": "Page",
    "title": "ReefTriage 演示 (地图)",
    "properties": {
        "card": {
            "type": "void",
            "x-component": "CardItem",
            "x-component-props": {"title": "ReefTriage Leaflet 地图演示"},
            "properties": {
                "iframe": {
                    "type": "void",
                    "x-component": "Markdown",
                    "x-component-props": {"content": demo_iframe},
                },
            },
        },
    },
}
create_schema(demo_schema)

# ============================================================
# Page 2: Admin Panel (iframe of /admin-panel)
# ============================================================
print("\n[2/2] Creating Admin Panel page...")
admin_iframe = (
    '<iframe src="http://127.0.0.1:8000/admin-panel" '
    'style="width:100%;height:900px;border:1px solid #ddd;border-radius:8px;" '
    'allow="fullscreen"></iframe>'
)
admin_schema = {
    "name": "admin-panel",
    "type": "void",
    "x-component": "Page",
    "title": "管理面板 (API操控/服务状态)",
    "properties": {
        "card": {
            "type": "void",
            "x-component": "CardItem",
            "x-component-props": {"title": "统一管理面板 — 服务状态 / API操控 / 数据同步"},
            "properties": {
                "iframe": {
                    "type": "void",
                    "x-component": "Markdown",
                    "x-component-props": {"content": admin_iframe},
                },
            },
        },
    },
}
create_schema(admin_schema)

print("\n✅ Pages created!")
print("Note: If iframes don't render, the Markdown component may sanitize HTML.")
print("Manual fix: Enter UI Editor (pencil icon) > Add block > Markdown/HTML > paste iframe code.")
