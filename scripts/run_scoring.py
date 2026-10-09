"""运行评分 + 回测, 输出结果。"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scoring.engine import engine

print(f"Loaded {len(engine.segments)} segments, mode={engine.laya_mode}")
rows = engine.all_scored()
print(f"\n{'ID':4} {'Name':32} {'DHW':>5} {'max5y':>5} {'RHI':>5} {'score':>5} {'choice':>13}")
for r in rows:
    rhi = float(r.get('rhi_score') or 0.0)
    print(f"{r['segment_id']:4} {r['name'][:30]:32} {r['current_dhw']:5.2f} "
          f"{r['max_dhw_5yr']:5.2f} {rhi:5.1f} {r['score']:5d} {r['choice']:13}")

invest = sum(1 for r in rows if r['choice']=='invest')
monitor = sum(1 for r in rows if r['choice']=='monitor')
deprior = sum(1 for r in rows if r['choice']=='deprioritize')
avg = sum(r['score'] for r in rows)/len(rows)
print(f"\nDistribution: invest={invest} monitor={monitor} deprior={deprior} avg={avg:.1f}")
