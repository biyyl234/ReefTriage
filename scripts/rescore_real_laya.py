"""
scripts/rescore_real_laya.py
============================
用真实 Laya 引擎重新评分 28 个礁段 (live 模式)。

前置: data/output/scored_segments.json 已删除 (或重命名为 .bak.real_laya),
     引擎初始化时会走 fusion.score_all -> 28 次真实 Laya /api/predict 调用。

注意 (2026-10-04 排查):
  rubric_v2.build_questions_v2() 生成的 5 个 dim_* 子问题缺少 'criteria' 字段,
  Laya 服务端对 score 类型问题强制要求 criteria 列表, 否则返回 500:
    "a score question takes 'criteria' as a list of level descriptions"
  fusion.compute_laya_scores 实际只读取 answers["priority_score"], dim_* 子问题
  不影响最终 laya_score, 因此这里在运行时打补丁, 把 dim_* 子问题过滤掉,
  只保留 priority_score + priority_class。
  不修改 app/scoring/ 下的任何源文件, 仅在本脚本运行时 monkeypatch。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Monkeypatch rubric_v2 BEFORE importing engine (engine.py has module-level ScoringEngine()) ---
from app.scoring import rubric_v2 as _rubric_v2

_orig_build_questions_v2 = _rubric_v2.build_questions_v2

def _patched_build_questions_v2():
    qs = _orig_build_questions_v2()
    # 去掉缺少 criteria 的 dim_* 子问题, 只保留 priority_score / priority_class
    return {k: v for k, v in qs.items() if not k.startswith("dim_")}

_rubric_v2.build_questions_v2 = _patched_build_questions_v2

from app.scoring.engine import ScoringEngine

engine = ScoringEngine(laya_base_url="http://127.0.0.1:5000")
rows = engine.all_scored()

print(f"Mode: {engine.laya_mode}")
print(f"Laya endpoint resolved: {engine.client._endpoint}")
print(f"Laya last model: {engine.client.last_model}")
print()
for r in rows[:5]:
    print(f"{r['segment_id']} {r['name'][:25]:25s} score={r['score']} choice={r['choice']} "
          f"mcdm={r.get('mcdm_score')} laya={r.get('laya_score')}")

invest = sum(1 for r in rows if r['choice'] == 'invest')
monitor = sum(1 for r in rows if r['choice'] == 'monitor')
deprior = sum(1 for r in rows if r['choice'] == 'deprioritize')
avg = sum(r['score'] for r in rows) / len(rows)

laya_vals = sorted(set(round(r.get('laya_score', -1), 1) for r in rows))
print(f"\nDistribution: invest={invest} monitor={monitor} deprior={deprior} avg={avg:.1f}")
print(f"laya_score unique values ({len(laya_vals)}): {laya_vals}")
