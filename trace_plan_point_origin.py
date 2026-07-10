"""Trace: how did plan point intent-03 get value="#/home" when selected_candidate has "#/login"?

The plan JSON stores BOTH selected_candidates (correct) and plan points (wrong).
This traces how the generation pipeline creates plan points from selected_candidates.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent / "apps" / "web-ui-service"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

TP_FILE = Path(__file__).resolve().parent / "web-ui" / "state" / "test-points" / "mall" / "mall-web-login-auth-fn-ai-0001.json"
PLAN_FILE = Path(__file__).resolve().parent / "web-ui" / "state" / "test-points" / "mall" / "plans" / "mall-web-login-auth-fn-ai-0001.json"

SEP = "─" * 70

with open(TP_FILE) as f:
    tp = json.load(f)
with open(PLAN_FILE) as f:
    plan_doc = json.load(f)

# =============================================================================
# PART 7: Compare ALL intent-03 data sources
# =============================================================================
print("═" * 70)
print("  PART 7: ALL intent-03 DATA SOURCES COMPARED")
print("═" * 70)

# Source 1: test-point JSON point
tp_points = tp.get("plan", {}).get("points", [])
tp_03 = next((p for p in tp_points if p.get("key") == "intent-03"), {})
print("\n  Source A: test-point point intent-03")
print(f"    steps_hint: {tp_03.get('steps_hint')}")
for s in tp_03.get("steps", []):
    print(f"    step: action={s.get('action')} value='{s.get('value')}' raw='{s.get('raw_text')}'")

# Source 2: test-point metadata.candidate_snapshot
snap = tp_03.get("metadata", {}).get("candidate_snapshot", {})
print(f"\n  Source B: test-point metadata.candidate_snapshot")
print(f"    steps_hint: {snap.get('steps_hint')}")
print(f"    expected: {snap.get('expected')}")

# Source 3: plan document selected_candidate
plan_meta = plan_doc.get("metadata", {})
selected = plan_meta.get("selected_candidates", [])
sc_03 = None
for s in selected:
    if "03" in str(s.get("intent_id", "")):
        sc_03 = s
        break
print(f"\n  Source C: plan metadata.selected_candidate (intent-03)")
if sc_03:
    print(f"    steps_hint: {sc_03.get('steps_hint')}")
    print(f"    expected: {sc_03.get('expected')}")

# Source 4: plan document plan point
plan_points = plan_doc.get("points", [])
pp_03 = next((p for p in plan_points if p.get("key") == "intent-03"), {})
print(f"\n  Source D: plan plan_point intent-03")
print(f"    steps_hint: {pp_03.get('steps_hint')}")
for s in pp_03.get("steps", []):
    print(f"    step: action={s.get('action')} value='{s.get('value')}' raw='{s.get('raw_text')}'")


# =============================================================================
# PART 8: Trace the generation flow — how plan point gets its steps
# =============================================================================
print(f"\n{'█' * 70}")
print("█  PART 8: GENERATION FLOW — selected_candidate → plan point")
print(f"{'█' * 70}")

print(f"""
  The generate pipeline (run_generate_pipeline) creates plan points
  in TWO possible paths:

  PATH A (LLM): selected_candidate=None → LLM generates requirement_spec
    → test points created from LLM output
    → steps_hint from LLM directly

  PATH B (manual): selected_candidate is non-empty
    → _build_direct_candidate_orchestrator_result()
    → steps_hint from candidate.get("steps_hint")

  For intent-03, the plan metadata says:
    origin: "selected_candidate_direct_compile"
    → This was Path B
""")

# Check the plan point's metadata to confirm
for p in plan_points:
    if p.get("key") == "intent-03":
        meta = p.get("metadata", {})
        traceability = meta.get("traceability", {})
        print(f"    Traceability: origin={traceability.get('origin')}")
        break

# =============================================================================
# PART 9: Simulate _build_direct_candidate_orchestrator_result
# =============================================================================
print(f"\n{'█' * 70}")
print("█  PART 9: SIMULATE — what should the plan point contain?")
print(f"{'█' * 70}")

# The selected_candidate (correct) should produce the plan point
# Let's resolve each steps_hint manually

from shared_backend.intent_mapping import resolve_explicit_step
from shared_backend.element_binding import build_element_alias_map

# Load PageObject for alias map
from app.repositories.page_object_repository import PageObjectRepository
from app.core.database import SessionLocal

alias_map = {}
db = SessionLocal()
try:
    repo = PageObjectRepository(db)
    all_pos = repo.list_all()
    for po in all_pos:
        if po.page_code == "login":
            po_dict = {
                "page_code": po.page_code,
                "page_url": po.page_url or "",
                "elements": {
                    e.element_code: {
                        "element_code": e.element_code,
                        "element_name": e.element_name or "",
                        "locator_type": e.locator_type,
                        "locator_value": e.locator_value,
                        "role": e.role or "",
                        "business_type": e.business_type or "",
                    }
                    for e in po.elements
                }
            }
            alias_map = build_element_alias_map(po_dict)
            break
finally:
    db.close()

if sc_03:
    hints = sc_03.get("steps_hint", [])
    print(f"\n  Using selected_candidate steps_hint: {hints}")
    print(f"\n  Resolving each hint:")
    for hint in hints:
        action, target, value = resolve_explicit_step(
            steps_hint=[hint],
            page="login",
            page_element_alias_map=alias_map if alias_map else None,
        )
        print(f"    '{hint}' → action={action}, target={target}, value={value}")

    print(f"\n  EXPECTED structured steps:")
    for hint in hints:
        action, target, value = resolve_explicit_step(
            steps_hint=[hint],
            page="login",
            page_element_alias_map=alias_map if alias_map else None,
        )
        print(f"    {{action: {action}, value: '{value}'}}")
else:
    print("  No selected_candidate found for intent-03")

# =============================================================================
# PART 10: Check if the plan point was created from a DIFFERENT candidate
# =============================================================================
print(f"\n{'█' * 70}")
print("█  PART 10: CHECK — was the plan point from a different candidate?")
print(f"{'█' * 70}")

# The plan metadata may show which candidates were used
raw_plan_keys = plan_meta.get("raw_plan_keys", [])
print(f"\n  Plan saved by: {plan_meta.get('saved_by', 'unknown')}")
print(f"  Plan origin: {plan_meta.get('origin', 'unknown')}")
print(f"  Selected intent IDs: {plan_meta.get('selected_intent_ids', [])}")

# Check ALL selected_candidates for any that might match
for idx, sc in enumerate(selected):
    if isinstance(sc, dict):
        intent_id = sc.get("intent_id", "")
        sh = sc.get("steps_hint", [])
        if isinstance(sh, str):
            sh = [sh]
        # Check if any hint contains assert_url
        assert_url_hints = [h for h in sh if "assert_url" in str(h)]
        if assert_url_hints:
            print(f"\n  selected_candidate[{idx}] intent_id={intent_id}")
            print(f"    steps_hint with assert_url: {assert_url_hints}")

# =============================================================================
# PART 11: Check if there's a version history showing the edit
# =============================================================================
print(f"\n{'█' * 70}")
print("█  PART 11: CHECK GENERATED CASE — does it preserve the correct value?")
print(f"{'█' * 70}")

# The generated case (0003) was for intent-02, but let's check it for reference
case_file = Path(__file__).resolve().parent / "web-ui" / "state" / "generated-cases" / "mall" / "mall-web-login-auth-fn-ai-0003.json"
if case_file.exists():
    with open(case_file) as f:
        case = json.load(f)
    case_points = case.get("plan", {}).get("points", [])
    for p in case_points:
        if p.get("key") in ("intent-02", "intent-03"):
            print(f"\n  generated case point {p.get('key')}:")
            print(f"    steps_hint: {p.get('steps_hint', [])}")
            for s in p.get("steps", []):
                print(f"    step: action={s.get('action')} value='{s.get('value')}' raw='{s.get('raw_text')}'")

# Also check the version history
versions_dir = Path(__file__).resolve().parent / "web-ui" / "state" / "generated-cases" / "mall" / "versions"
if versions_dir.exists():
    for version_dir in versions_dir.iterdir():
        if version_dir.is_dir() and "0003" in version_dir.name:
            versions = sorted(version_dir.iterdir())
            print(f"\n  Version history for {version_dir.name}: {len(versions)} versions")
            # Check the latest version
            if versions:
                latest = versions[-1]
                with open(latest) as f:
                    ver_data = json.load(f)
                ver_points = ver_data.get("plan", {}).get("points", [])
                for p in ver_points:
                    if p.get("key") in ("intent-02", "intent-03"):
                        print(f"\n  latest version point {p.get('key')}:")
                        print(f"    steps_hint: {p.get('steps_hint', [])}")
                        for s in p.get("steps", []):
                            print(f"    step: action={s.get('action')} value='{s.get('value')}' raw='{s.get('raw_text')}'")

print()
