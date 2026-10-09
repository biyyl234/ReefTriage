"""快速冒烟测试: 评分引擎 + API 路由。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scoring.engine import engine
rows = engine.all_scored()
rows.sort(key=lambda x: -x["score"])
print(f"Loaded {len(rows)} segments, mode={engine.laya_mode}")
for r in rows:
    print(f"  {r['segment_id']:4} {r['name']:14} score={r['score']:3} "
          f"choice={r['choice']:13} conf={r['confidence']}")

# 测试 API
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
print("\n--- /api/health ---")
print(c.get("/api/health").json())
print("\n--- /api/stats ---")
print(c.get("/api/stats").json())
print("\n--- /api/priority?budget=60000 ---")
p = c.get("/api/priority?budget=60000&unit_cost=15000").json()
print(f"funded={p['funded_count']} total_cost={p['total_cost']}")
print("\n--- /api/recalc ---")
print(c.post("/api/recalc").json()["recalculated"])
print("\nALL OK")
