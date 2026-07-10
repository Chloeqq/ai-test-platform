"""Full forensic trace for intent-03: trace the candidate flow end to end.

Two key questions:
1. Why does point.steps have value="#/home" when candidate_snapshot has "#/login"?
2. Where does the selected_candidate come from?

This traces the SAVE path backward to find the root cause.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent / "apps" / "web-ui-service"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from shared_backend.type_utils import str_value

TP_FILE = Path(__file__).resolve().parent / "web-ui" / "state" / "test-points" / "mall" / "mall-web-login-auth-fn-ai-0001.json"
PLAN_FILE = Path(__file__).resolve().parent / "web-ui" / "state" / "test-points" / "mall" / "plans" / "mall-web-login-auth-fn-ai-0001.json"

SEP = "─" * 70

print("═" * 70)
print("  FULL FORENSIC TRACE: intent-03 candidate flow")
print("═" * 70)

# =============================================================================
# Load both files
# =============================================================================
with open(TP_FILE) as f:
    tp = json.load(f)

with open(PLAN_FILE) as f:
    plan_doc = json.load(f)

# =============================================================================
# Part 1: Show the discrepancy
# =============================================================================
print(f"\n{'█' * 70}")
print("█  PART 1: THE DISCREPANCY — Two different steps_hint values")
print(f"{'█' * 70}")

tp_points = tp.get("plan", {}).get("points", [])
tp_03 = next((p for p in tp_points if p.get("key") == "intent-03"), {})

# The point-level steps_hint (what Code saves and uses)
point_hints = tp_03.get("steps_hint", [])
print("\n  1A. point.steps_hint (test-point JSON, authoritative):")
print(f"      {point_hints}")

# The candidate_snapshot (AI's original output, stored as metadata)
snapshot = tp_03.get("metadata", {}).get("candidate_snapshot", {})
snap_hints = snapshot.get("steps_hint", [])
print(f"\n  1B. metadata.candidate_snapshot.steps_hint (AI original):")
print(f"      {snap_hints}")

# The structured steps
structured = tp_03.get("steps", [])
print(f"\n  1C. point.steps (structured, what Code compiles):")
for i, s in enumerate(structured):
    print(f"      [{i}] action={s.get('action')} | target={s.get('target')} | value={s.get('value')}")

print(f"\n  1D. Are they the same?")
if point_hints == snap_hints:
    print(f"      ✅ YES — no discrepancy")
else:
    print(f"      ❌ NO — values differ!")
    for i, (ph, sh) in enumerate(zip(point_hints, snap_hints)):
        if ph != sh:
            print(f"          hint[{i}]: point='{ph}' ≠ snapshot='{sh}'")
    print(f"\n      point.steps_hint  = {point_hints}")
    print(f"      snapshot.steps_hint = {snap_hints}")

# =============================================================================
# Part 2: Trace the SAVE path
# =============================================================================
print(f"\n{'█' * 70}")
print("█  PART 2: TRACE THE SAVE PATH")
print(f"{'█' * 70}")

print(f"""
  保存调用链:

  facade.save_test_point_assets()
    → _enrich_test_points_with_candidate_snapshots()  [generate_pipeline_orchestrate]
    → 把 candidate_snapshot 存入 metadata

  关键代码 (generate_pipeline_orchestrate.py line 636-638):
    candidate_steps_hint = _list_text(candidate.get("steps_hint"))
    if candidate_steps_hint:
        point["steps_hint"] = candidate_steps_hint

  这里的 candidate 是哪来的？
    → selected_candidate (用户勾选的候选)
    → 来自 store（之前保存的候选数据）

  但 selected_candidate 的 steps_hint 可能 ≠ candidate_snapshot 的 steps_hint。
  selected_candidate 是用户确认/编辑后的版本。
  candidate_snapshot 是 AI 生成时的原始快照。

  如果用户在确认时修改了 steps_hint → selected_candidate 被改 → point.steps_hint 被改。
  但 candidate_snapshot（metadata 中的）保留了原始版本。

  或者：
  如果 selected_candidate 是从 _normalize_candidate_snapshot() 来的，
  而 _normalize_candidate_snapshot 只是字段重命名不修改内容，
  那么 steps_hint 应该和 candidate_snapshot 一致。

  如果不一致，说明 selected_candidate 来自另一个源。
""")

# =============================================================================
# Part 3: Check what selected_candidate was stored
# =============================================================================
print(f"{'█' * 70}")
print("█  PART 3: CHECK THE STORED selected_candidate")
print(f"{'█' * 70}")

# The plan document contains the full save metadata
plan_meta = plan_doc.get("metadata", {})
selected = plan_meta.get("selected_candidates", [])
print(f"\n  Plan stored at: {PLAN_FILE}")
print(f"  selected_candidates count: {len(selected)}")

for i, sc in enumerate(selected):
    if "03" in str(sc.get("intent_id", "")) or "02" in str(sc.get("intent_id", "")):
        print(f"\n  selected_candidate[{i}]: intent_id={sc.get('intent_id')}")
        print(f"    steps_hint: {sc.get('steps_hint', '')}")
        print(f"    expected:   {sc.get('expected', '')}")
        print(f"    involved_element_codes: {sc.get('involved_element_codes', '')}")

# Check all plan points for intent-03
plan_points = plan_doc.get("points", [])
for p in plan_points:
    if p.get("key") in ("intent-02", "intent-03"):
        print(f"\n  plan point {p.get('key')}:")
        print(f"    steps_hint: {p.get('steps_hint', [])}")
        for j, s in enumerate(p.get("steps", [])):
            print(f"    step[{j}]: {s}")

# =============================================================================
# Part 4: Check if plan document shows any editing history
# =============================================================================
print(f"\n{'█' * 70}")
print("█  PART 4: TRACE THE ACTUAL GENERATION FLOW")
print(f"{'█' * 70}")

# The plan JSON was saved by _build_direct_candidate_orchestrator_result
# Let's check what that function would have produced
raw_requirement = tp.get("plan", {}).get("requirement", [])

print(f"\n  The plan.requirement (input to generation):")
for line in raw_requirement:
    print(f"    {line[:200]}")

# Check if the requirement mentions assert_url
for line in raw_requirement:
    if "assert_url" in line:
        print(f"\n  ★ Found assert_url in requirement:")
        print(f"    {line}")
        # Extract the assert_url value
        import re
        match = re.search(r'assert_url[:\s]*#/(\w+)', line)
        if match:
            print(f"    → URL value: #/{match.group(1)}")

# =============================================================================
# Part 5: What does _steps_hint_from_current_steps produce?
# =============================================================================
print(f"\n{'█' * 70}")
print("█  PART 5: SIMULATE _steps_hint_from_current_steps")
print(f"{'█' * 70}")

from app.api.workbench.facade_helpers import _steps_hint_from_current_steps, _text, _text_list

# Take the ACTUAL stored point steps (from tp_03)
point_steps = tp_03.get("steps", [])
involved_elements = tp_03.get("involved_elements", [])

print(f"\n  Input point_steps:")
for s in point_steps:
    print(f"    action={s.get('action')} | target={s.get('target')} | value={s.get('value')}")

reconstructed = _steps_hint_from_current_steps(point_steps, involved_elements)
print(f"\n  Reconstructed steps_hint:")
for h in reconstructed:
    print(f"    {h}")

print(f"\n  Does this match the stored point.steps_hint?")
if reconstructed == point_hints:
    print(f"    ✅ YES — stored steps_hint was reconstructed from steps")
    print(f"    → _steps_hint_from_current_steps() IS the tampering function")
else:
    print(f"    ❌ NO — different source")
    print(f"    reconstructed: {reconstructed}")
    print(f"    stored:        {point_hints}")

# =============================================================================
# Part 6: Final verdict
# =============================================================================
print(f"\n{'█' * 70}")
print("█  PART 6: FINAL VERDICT")
print(f"{'█' * 70}")

print(f"""
{SEP}
  intent-03 "未登录访问首页被拦截" 的完整受损链：

  1. AI 生成时:
     candidate_snapshot.steps_hint = ['goto:#/home', 'assert_url:#/login']
     ↑ 这个是正确的！assert_url 的值是 #/login

  2. 用户确认保存时:
     facade_helpers._candidate_from_asset_point() 被调用
     → 读取 stored point.steps，其中 assert_url 的 value 是 "#/home"
     → _steps_hint_from_current_steps() 从 steps 反向重建:
       step[1]: action=assert_url, value="#/home" → 生成 "assert_url:#/home"
     → merged_steps_hint = list(current_steps_hint)  [line 1514]
     → 重建版成为权威版
     → 原 AI 输出的 "#/login" 被丢弃

  3. 下次读取时:
     point.steps_hint = ['goto:#/home', 'assert_url:#/home']
     ← 错误已经被永久写入 state JSON

  结论:
    _steps_hint_from_current_steps() [facade_helpers.py:1434-1485]
    在保存时从 structured steps 反向重建 steps_hint，
    用重建版覆盖 AI 原始输出 [line 1514]。

    如果 structured steps 中的 value 是错的，
    重建的 steps_hint 就是错的。
    这个错误会永久写入 state JSON，不可恢复。

  为什么 structured steps 的 value 是 "#/home"？
    → 需要进一步追溯到首次生成这个 test point 的时候
    → 首次生成时，selected_candidate 的 steps_hint 是什么？
    → 是用户编辑过？还是 selected_candidate 和 candidate_snapshot 不同源？
{SEP}
""")

print()
