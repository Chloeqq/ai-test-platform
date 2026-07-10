"""Forensic trace: exactly what happens to intent-04 during compilation.

Runs the real compilation pipeline step by step, printing the
before/after of every transformation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent / "apps" / "web-ui-service"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from shared_backend.execution_compiler import (
    normalize_test_points,
    normalize_test_points_to_actions,
    build_execution_ir,
    bind_targets,
    render_execution_steps,
    compile_execution_steps,
)
from shared_backend.type_utils import dict_value, str_value

SEP = "─" * 70

# Load the real test point data
tp_path = Path(__file__).resolve().parent / "web-ui" / "state" / "test-points" / "mall" / "mall-web-login-auth-fn-ai-0001.json"
with open(tp_path) as f:
    asset = json.load(f)

points = asset.get("plan", {}).get("points", [])

# Pick intent-04: "用户名为空点击登录提示请输入账号"
target_key = "intent-04"
target_point = next((p for p in points if p.get("key") == target_key), None)
if not target_point:
    print(f"Intent {target_key} not found!")
    sys.exit(1)


def print_dict(label: str, d: dict[str, Any], fields: list[str] | None = None):
    print(f"\n  [{label}]")
    if fields:
        for f in fields:
            print(f"    {f}: {d.get(f, '<missing>')}")
    else:
        for k, v in d.items():
            if k in ("metadata", "candidate_snapshot", "traceability", "dependency_review"):
                continue
            if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                print(f"    {k}: [{len(v)} items]")
            else:
                print(f"    {k}: {v}")


def print_steps(label: str, steps: list[dict[str, Any]]):
    print(f"\n  [{label}] ({len(steps)} steps)")
    for i, s in enumerate(steps):
        action = s.get("action", s.get("type", "?"))
        target = s.get("target", "")
        value = s.get("value", "")
        raw = str_value(s.get("raw_text") or s.get("meta", {}).get("raw_text", ""))
        assertion = s.get("assertion", "")
        role = s.get("role", "")
        selector = s.get("selector", "")
        locator_type = s.get("locator_type", "")
        intent_id = s.get("intent_id", "")
        print(f"    [{i}] action={action} | target={target} | value={value}")
        if raw:
            print(f"         raw_text: {raw[:80]}")
        if assertion:
            print(f"         assertion: {assertion}")
        if role:
            print(f"         role={role} | selector={selector} | locator_type={locator_type}")
        print()


# =====================================================================
# TRACE START
# =====================================================================
print()
print("═" * 70)
print("  FORENSIC TRACE: intent-04 用户名为空点击登录")
print("  追踪每一步对原始数据的修改")
print("═" * 70)

# ---- Step 0: RAW input ----
print(f"\n{'█' * 70}")
print("█  STEP 0: RAW — AI 原始输出（存在 state/test-points/ JSON 中）")
print(f"{'█' * 70}")

raw_steps = target_point.get("steps", [])
raw_steps_hint = target_point.get("steps_hint", [])
print(f"\n  AI 看到的业务需求: {target_point.get('description', '')}")
print(f"  AI 认为的预期结果: {target_point.get('expected_result', '')}")
print(f"  AI 判断的场景类型: {target_point.get('point_type', '')}")
print(f"  AI 推荐的操作步骤: {raw_steps_hint}")
print(f"\n  AI 输出的 structured steps ({len(raw_steps)} steps):")
for i, s in enumerate(raw_steps):
    print(f"    [{i}] action={s.get('action')} | target={s.get('target')} | value={s.get('value')}")
    print(f"         raw_text: {s.get('raw_text', '')}")

# ---- Step 1: normalize_test_points ----
print(f"\n{'█' * 70}")
print("█  STEP 1: normalize_test_points() — 格式规范化")
print(f"{'█' * 70}")
print("  做什么：把 point 里的字段标准化（key→intent_id, point_type→point_type, steps 保持不变）")
print("  谁改的？没有人改内容。只是字段重命名。")

normalized = normalize_test_points([target_point])
print(f"  → {len(normalized)} points after normalize")
for i, p in enumerate(normalized):
    print(f"    [{i}] intent_id={p.get('intent_id')} | point_type={p.get('point_type')} | action={p.get('action')}")
    print(f"         steps: {len(p.get('steps', []))} unchanged")
    # Show step details
    for j, s in enumerate(p.get("steps", [])):
        print(f"           step[{j}]: action={s.get('action')} target={s.get('target')} value={s.get('value')}")

# ---- Step 2: normalize_test_points_to_actions ----
print(f"\n{'█' * 70}")
print("█  STEP 2: normalize_test_points_to_actions() — 步骤映射为内部 action ★ 第一个修改点")
print(f"{'█' * 70}")
print("  做什么：把 step 中的 action 字符串映射为内部 DSL action 类型")
print("  ★ 这里可能引入问题：action 名映射是硬编码的")
print()

actions = normalize_test_points_to_actions(normalized)
for i, a in enumerate(actions):
    print(f"  action[{i}]:")
    print(f"    type: {a.get('type')}  ← 原始: input/click/assert_text 被映射为什么？")
    print(f"    target: {a.get('target')}")
    print(f"    value: {a.get('value')}")
    print(f"    assertion: {a.get('assertion')}")
    print(f"    intent_id: {a.get('intent_id')}")
    meta = a.get("meta", {})
    print(f"    raw_text: {meta.get('raw_text', '')}")
    print(f"    compiler_status: {meta.get('compiler_status', '')}")

# ---- Step 3: build_execution_ir ----
print(f"\n{'█' * 70}")
print("█  STEP 3: build_execution_ir() — 构建执行中间表示")
print(f"{'█' * 70}")
print("  做什么：标准化为 execution IR（统一字段名）")
print("  ★ 这里可能引入问题：validation 规则不够严格")
print()

ir = build_execution_ir(actions)
ir_steps = ir.get("steps", [])
print(f"  IR version: {ir.get('version')}")
print(f"  IR steps ({len(ir_steps)}):")
for i, s in enumerate(ir_steps):
    print(f"    [{i}] type={s.get('type')} target={s.get('target')} value={s.get('value')} assertion={s.get('assertion')}")
    meta = s.get("meta", {})
    print(f"         raw_text: {meta.get('raw_text', '')} | status: {meta.get('compiler_status', '')}")

# ---- Step 4: Load PageObject for binding ----
print(f"\n{'█' * 70}")
print("█  STEP 4: Load PageObject — 加载页面对象")
print(f"{'█' * 70}")

from app.repositories.page_object_repository import PageObjectRepository
from app.core.database import SessionLocal

db = SessionLocal()
try:
    repo = PageObjectRepository(db)
    # Find login page object
    all_pos = repo.list_all()
    login_po = None
    for po in all_pos:
        if po.page_code == "login":
            login_po = po
            break

    if login_po:
        print(f"  PageObject: {login_po.page_code} ({login_po.page_name})")
        print(f"  Elements ({len(login_po.elements)}):")
        for e in login_po.elements:
            print(f"    - {e.element_code}: name={e.element_name}, role={e.role}, business_type={e.business_type}")
            print(f"      locator: {e.locator_type}={e.locator_value}")

        po_dict = {
            "page_code": login_po.page_code,
            "page_url": login_po.page_url or "",
            "elements": {
                e.element_code: {
                    "element_code": e.element_code,
                    "element_name": e.element_name or "",
                    "locator_type": e.locator_type,
                    "locator_value": e.locator_value,
                    "role": e.role or "",
                    "business_type": e.business_type or "",
                }
                for e in login_po.elements
            }
        }
    else:
        print("  ⚠️  No login PageObject found!")
        po_dict = {"page_code": "login", "page_url": "", "elements": {}}
finally:
    db.close()

# ---- Step 5: bind_targets ----
print(f"\n{'█' * 70}")
print("█  STEP 5: bind_targets() — 元素绑定 ★★★ 最关键的一步")
print(f"{'█' * 70}")
print("  做什么：把 IR 中的 target（element_code）解析为实际的 selector/locator")
print("  ★★★ 这里是最可能引入篡改的地方：")
print("    1. target 匹配：element_code vs element_name vs 模糊匹配")
print("    2. role 不检查：assert_text 的目标 role=button 不会报错")
print("    3. 匹配失败时可能静默 fallback")
print()

bound = bind_targets(ir, po_dict)
bound_steps = bound.get("steps", [])
print(f"  Bound IR steps ({len(bound_steps)}):")
for i, s in enumerate(bound_steps):
    print(f"    [{i}] type={s.get('type')} | target={s.get('target')} | assertion={s.get('assertion')}")
    print(f"         selector={s.get('selector')} | locator_type={s.get('locator_type')} | role={s.get('role')}")
    meta = s.get("meta", {})
    print(f"         compiler_status: {meta.get('compiler_status')} | reason: {meta.get('compiler_reason', '')}")

# ---- Step 6: render_execution_steps ----
print(f"\n{'█' * 70}")
print("█  STEP 6: render_execution_steps() — 渲染为 Runner 可执行格式")
print(f"{'█' * 70}")
print("  做什么：把 IR 转为 Runner 期望的 action 格式")
print("  ★ 这里是最终产物")
print()

rendered = render_execution_steps(bound)
print(f"  Rendered steps ({len(rendered)}):")
for i, s in enumerate(rendered):
    print(f"    [{i}] action={s.get('action')} | target={s.get('target')} | selector={s.get('selector')} | role={s.get('role', '')}")
    trace = s.get("traceability", {})
    print(f"         raw_text: {trace.get('raw_text', '')}")
    print(f"         confidence: {trace.get('confidence', '')}")
    if s.get('action') == 'fill':
        print(f"         value: {s.get('value')}")

# ---- Step 7: Full pipeline for comparison ----
print(f"\n{'█' * 70}")
print("█  STEP 7: compile_execution_steps() — 全链路一次调用")
print(f"{'█' * 70}")
print("  做什么：上面 1-6 步一次跑完")
print()

full_result = compile_execution_steps(normalized, po_dict)
print(f"  Final result ({len(full_result)} steps):")
for i, s in enumerate(full_result):
    print(f"    [{i}] action={s.get('action')} | target={s.get('target')} | selector={s.get('selector')} | role={s.get('role', '')}")
    if s.get('action') == 'fill':
        print(f"         value={s.get('value')}")
    trace = s.get("traceability", {})
    print(f"         raw_text: {trace.get('raw_text', '')}")

# ---- SUMMARY ----
print(f"\n{'═' * 70}")
print("  FORENSIC SUMMARY — 数据在每个步骤的变化")
print(f"{'═' * 70}")
print()

print("  原始 AI 输出 (step 0):")
for s in raw_steps:
    print(f"    {s.get('action'):20s} target={s.get('target'):25s} value={s.get('value', ''):15s} raw_text='{s.get('raw_text', '')}'")

print()
print("  最终可执行 DSL (step 7):")
for s in full_result:
    print(f"    {s.get('action'):20s} target={s.get('target'):25s} selector={s.get('selector', ''):20s} role={s.get('role', '')}")

print()
print("  变化追踪:")
for i, (raw, final) in enumerate(zip(raw_steps, full_result)):
    changed = []
    if raw.get("target", "") != final.get("target", ""):
        changed.append(f"target: '{raw.get('target', '')}' → '{final.get('target', '')}'")
    if raw.get("action", "") != final.get("action", ""):
        changed.append(f"action: '{raw.get('action', '')}' → '{final.get('action', '')}'")
    if "_" in final.get("role", "") and raw.get("action", "").startswith("assert"):
        changed.append(f"role: {final.get('role', '')} (assert_text 的目标是 {final.get('role', '')} 类型元素)")

    if changed:
        print(f"    step[{i}]: {' | '.join(changed)}")
    else:
        print(f"    step[{i}]: 无变化")

print()
