"""快速测试融合引擎。"""
import sys
sys.path.insert(0, ".")

from app.scoring import data_loader, fusion
from app.scoring.laya_client import LayaClient

segs = data_loader.load_reef_segments()
print(f"Loaded {len(segs)} segments")

client = LayaClient()
mode = "mock" if client.is_mock else "live"
print(f"Laya mode: {mode}")

results = fusion.score_all(segs, client, compute_ci=False)
print(f"Scored {len(results)} segments")
print("\nTop 5:")
for r in sorted(results, key=lambda x: -x["final_score"])[:5]:
    print(f"  {r['segment_id']} {r['name']}: final={r['final_score']} "
          f"mcdm={r['mcdm_score']} laya={r['laya_score']} "
          f"bleach={r['bleaching_probability']} choice={r['choice']}")

print(f"\nWeights: {fusion.get_feature_weights()}")
print(f"Alpha: {fusion.get_optimal_alpha()}")

# 统计
invest = sum(1 for r in results if r["choice"] == "invest")
monitor = sum(1 for r in results if r["choice"] == "monitor")
deprior = sum(1 for r in results if r["choice"] == "deprioritize")
print(f"\nDistribution: invest={invest}, monitor={monitor}, deprioritize={deprior}")
