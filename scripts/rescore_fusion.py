"""清除缓存并重新评分 (融合引擎)。"""
import sys, os, json
sys.path.insert(0, ".")

# 备份并清除旧缓存 (用时间戳避免 Windows 上 rename 到已存在 .bak 时报错)
import time
cache = "data/output/scored_segments.json"
if os.path.exists(cache):
    bak = cache + ".bak." + time.strftime("%Y%m%d_%H%M%S")
    os.rename(cache, bak)
    print("Backed up old cache ->", bak)

from app.scoring.engine import engine

segs = engine.all_scored()
print(f"Rescored: {len(segs)} segments")
print("\nTop 5:")
for r in segs[:5]:
    print(f"  {r['segment_id']} {r['name']}: score={r['score']} "
          f"final={r.get('final_score')} mcdm={r.get('mcdm_score')} "
          f"laya={r.get('laya_score')} bleach={r.get('bleaching_probability')} "
          f"choice={r['choice']}")

inv = sum(1 for r in segs if r["choice"] == "invest")
mon = sum(1 for r in segs if r["choice"] == "monitor")
dep = sum(1 for r in segs if r["choice"] == "deprioritize")
print(f"\nDistribution: invest={inv}, monitor={mon}, deprioritize={dep}")

# 检查置信区间
r0 = segs[0]
if "confidence_interval" in r0:
    ci = r0["confidence_interval"]
    print(f"\nCI for {r0['segment_id']}: mean={ci['mean']} [{ci['ci_lower']}, {ci['ci_upper']}]")
else:
    print("\nNo confidence_interval field")

print(f"\nAlpha: {engine.model_compare()['alpha']}")
print(f"ML model: {engine.ml_model_info().get('status')}")
