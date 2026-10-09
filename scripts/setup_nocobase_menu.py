"""
Setup NocoBase navigation menu with ReefTriage links.

This script creates Link-type menu items in NocoBase that open ReefTriage
pages in new browser tabs. Link type is used because NocoBase's iframe
block requires manual UI configuration (see README for details).

Usage:
    .venv\\Scripts\\python.exe scripts/setup_nocobase_menu.py
"""
import urllib.request
import json
import sys

BASE = "http://127.0.0.1:13000/api"
ADMIN_EMAIL = "admin@nocobase.com"
ADMIN_PASSWORD = "admin123"

# Menu items to create
MENU_ITEMS = [
    {
        "title": "ReefTriage 演示",
        "icon": "AppstoreOutlined",
        "href": "http://127.0.0.1:8000/admin-panel",
        "sort": 1,
    },
    {
        "title": "ReefTriage 地图",
        "icon": "EnvironmentOutlined",
        "href": "http://127.0.0.1:8000/",
        "sort": 2,
    },
]


def api_request(method, path, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    try:
        return json.loads(urllib.request.urlopen(req, timeout=15).read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode()}


def main():
    print("Logging in to NocoBase...")
    login = api_request("POST", "/auth:signIn", {
        "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
    })
    if "error" in login:
        print(f"Login failed: {login}")
        sys.exit(1)
    token = login["data"]["token"]
    print("Logged in.")

    # Get existing routes
    print("\nChecking existing routes...")
    existing = api_request("GET", "/desktopRoutes:list?pageSize=50", token=token)
    existing_titles = {r.get("title"): r.get("id") for r in existing.get("data", [])}

    for item in MENU_ITEMS:
        title = item["title"]
        if title in existing_titles:
            print(f"  Updating '{title}'...")
            route_id = existing_titles[title]
            result = api_request("POST", f"/desktopRoutes:update?filter[id]={route_id}", {
                "type": "link",
                "icon": item["icon"],
                "options": {"href": item["href"], "openInNewWindow": True},
                "sort": item["sort"],
            }, token=token)
        else:
            print(f"  Creating '{title}'...")
            result = api_request("POST", "/desktopRoutes:create", {
                "title": title,
                "type": "link",
                "icon": item["icon"],
                "options": {"href": item["href"], "openInNewWindow": True},
                "sort": item["sort"],
            }, token=token)

        if "error" in result:
            print(f"    Error: {result}")
        else:
            print(f"    OK")

    print("\n=== Final menu ===")
    final = api_request("GET", "/desktopRoutes:list?pageSize=20", token=token)
    for r in final.get("data", []):
        opts = r.get("options", {}) or {}
        print(f"  {r.get('title'):20s} -> {opts.get('href', 'N/A')}")

    print("\nDone! Refresh NocoBase admin to see the menu.")


if __name__ == "__main__":
    main()
