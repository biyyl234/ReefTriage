"""用优化后的 α 和阈值重新评分。"""
import sys, os
sys.path.insert(0, ".")

cache = "data/output/scored_segments.json"
if os.path.exists(cache):
    os.remove(cache)
    print("Cleared cache")

from app.scoring.engine import engine

segs = engine.all_scored()
print(f"Rescored: {len(segs)} segments (α=0.30, invest≥37.6, monitor≥30.0)")
print("\nTop 10:")
for r in segs[:10]:
    print(f"  {r['segment_id']} {r['name'][:30]:30s} score={r['score']:3d} "
          f"final={r.get('final_score','?'):5} mcdm={r.get('mcdm_score','?'):5} "
          f"laya={r.get('laya_score','?'):3} bleach={r.get('bleaching_probability','?'):.4f} "
          f"choice={r['choice']}")

inv = sum(1 for r in segs if r["choice"] == "invest")
mon = sum(1 for r in segs if r["choice"] == "monitor")
dep = sum(1 for r in segs if r["choice"] == "deprioritize")
print(f"\nDistribution: invest={inv}, monitor={mon}, deprioritize={dep}")
print(f"Mean score: {sum(r['score'] for r in segs)/len(segs):.1f}")
