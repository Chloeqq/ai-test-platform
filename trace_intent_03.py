"""Forensic trace: intent-03 "未登录访问首页被拦截跳转至登录页"

This case was flagged as "断言逻辑颠倒" in the audit:
  - steps_hint: assert_url:#/home
  - expected_result: "自动跳转至登录页，URL包含/login"
  - 断言验证的是 URL=#/home, 但预期结果是 URL=#/login
  - 断言方向与业务意图完全相反

Trace every step to find WHERE this inversion happened.
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
    render_execution_steps,
    compile_execution_steps,
    bind_targets,
)
from shared_backend.type_utils import str_value
from shared_backend.intent_mapping import resolve_explicit_step
from shared_backend.element_binding import build_element_alias_map

SEP = "─" * 70

tp_path = Path(__file__).resolve().parent / "web-ui" / "state" / "test-points" / "mall" / "mall-web-login-auth-fn-ai-0001.json"
with open(tp_path) as f:
    asset = json.load(f)

points = asset.get("plan", {}).get("points", [])
target_point = next((p for p in points if p.get("key") == "intent-03"), None)

if not target_point:
    print("intent-03 not found!")
    sys.exit(1)

print("═" * 70)
print("  FORENSIC TRACE: intent-03 未登录访问首页被拦截跳转至登录页")
print("  审计发现: 断言逻辑颠倒 — assert_url期望/login但断言检查的是#/home")
print("═" * 70)

# =============================================================================
# STEP 0: RAW — AI 原始输出
# =============================================================================
print(f"\n{'█' * 70}")
print(f"█  STEP 0: RAW — AI 原始输出")
print(f"{'█' * 70}")

print(f"\n  业务需求: {target_point.get('description', '')}")
print(f"  判断的场景类型: {target_point.get('point_type', '')}")
print(f"  AI 认为的预期结果: {target_point.get('expected_result', '')}")
print(f"  AI 推荐的操作步骤: {target_point.get('steps_hint', [])}")
print(f"  AI 输出的 structured steps:")
for i, s in enumerate(target_point.get("steps", [])):
    print(f"    [{i}] action={s.get('action')} | target={s.get('target')} | value={s.get('value')}")
    print(f"         raw_text: '{s.get('raw_text', '')}'")

candidate_snapshot = target_point.get("metadata", {}).get("candidate_snapshot", {})

# =============================================================================
# STEP 1: steps_hint → resolve_explicit_step（直接从 step_hint 解析）
# =============================================================================
print(f"\n{'█' * 70}")
print(f"█  STEP 1: resolve_explicit_step() — 解析 steps_hint ★ 关键")
print(f"{'█' * 70}")

steps_hint = target_point.get("steps_hint", [])
print(f"\n  原始 steps_hint: {steps_hint}")

# Load PageObject for alias_map
from app.repositories.page_object_repository import PageObjectRepository
from app.core.database import SessionLocal

db = SessionLocal()
try:
    repo = PageObjectRepository(db)
    all_pos = repo.list_all()
    login_po = None
    for po in all_pos:
        if po.page_code == "login":
            login_po = po
            break

    if login_po:
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
        alias_map = build_element_alias_map(po_dict)
        print(f"\n  PageObject '{login_po.page_code}' loaded, {len(alias_map)} aliases")
    else:
        po_dict = {"page_code": "login", "page_url": "", "elements": {}}
        alias_map = {}
        print("\n  ⚠️  No login PageObject in DB")
finally:
    db.close()

print()
for i, hint in enumerate(steps_hint):
    action, target, value = resolve_explicit_step(
        steps_hint=[hint],
        page="login",
        page_element_alias_map=alias_map,
    )
    print(f"  step_hint[{i}]: '{hint}'")
    print(f"    → action={action} | target={target} | value={value}")

# =============================================================================
# STEP 2: _build_direct_candidate_orchestrator_result 的解析过程
# =============================================================================
print(f"\n{'█' * 70}")
print(f"█  STEP 2: _build_direct_candidate_orchestrator_result — 构建 point")
print(f"{'█' * 70}")

print(f"\n  从 candidate_snapshot 提取:")
print(f"    steps_hint (原始字符串): {candidate_snapshot.get('steps_hint', [])}")
print(f"    steps (自然语言描述): {candidate_snapshot.get('steps', [])}")
print(f"    expected: '{candidate_snapshot.get('expected', '')}'")
print(f"    intent_type: '{candidate_snapshot.get('intent_type', '')}'")

# 模拟 _build_direct_candidate_orchestrator_result 的逻辑
print(f"\n  模拟解析过程:")
for i, hint in enumerate(candidate_snapshot.get("steps_hint", [])):
    action, target, value = resolve_explicit_step(
        steps_hint=[hint],
        page="login",
        page_element_alias_map=alias_map,
    )
    print(f"    hint[{i}]: '{hint}'")
    print(f"      → action='{action}', target='{target}', value='{value}'")

# =============================================================================
# STEP 3: 定位"断言逻辑颠倒"的精确位置
# =============================================================================
print(f"\n{'█' * 70}")
print(f"█  STEP 3: 定位断言逻辑颠倒的精确位置")
print(f"{'█' * 70}")

print(f"""
{SEP}
  业务意图 vs 可执行 DSL 的对比

  意图: "自动跳转至登录页"
  ──────────────────────────────────────────
  AI 看到的页面行为:
    goto #/home → 被路由守卫拦截 → 重定向到 #/login

  AI 生成的 steps_hint (原始):
    steps_hint: ["goto:#/home", "assert_url:#/home"]
                              ↑
                    为什么这里是 #/home 而不是 #/login？

  两个可能的解释:
    A) AI 认为：访问 #/home → URL 仍是 #/home（没有跳转）
       → 但预期结果说"跳转至登录页"
       → AI 自相矛盾

    B) AI 认为：assert_url:#/home 意思是"验证 URL 不是 #/home"
       → 但 assert_url 只能做正向匹配，不能做反向匹配
       → AI 不理解这个限制

  解析后的 structured steps (resolve_explicit_step 输出):
    [0] action=goto, target="", value="#/home"
    [1] action=assert_url, target="", value="#/home"
                                       ↑
    解析完全正确。字符串 "#/home" 被忠实地赋值给 value。

  问题不在解析阶段。
  问题在 AI 生成的时候就已经存在了。
  生成的 steps_hint 本身就是错的——assert_url 的值是 #/home，
  但业务意图期望的是 #/login。

  resolve_explicit_step 没有能力判断：
    "这个 assert_url 的值是否符合业务意图"

  它只做字符串切分。输入什么就输出什么。

  Compiler 也判断不了。
  因为 Compiler 不知道"业务意图"是什么。
  它只知道"语法是否正确"。
{SEP}
""")

# =============================================================================
# STEP 4: _candidate_requirement 和 _direct_candidate_requirement_lines
# =============================================================================
print(f"\n{'█' * 70}")
print(f"█  STEP 4: 追查 requirement 文本是怎么构建的")
print(f"{'█' * 70}")

# 从 generated case 的 state 中读取完整的 requirement 文本
case_path = Path(__file__).resolve().parent / "web-ui" / "state" / "generated-cases" / "mall" / "mall-web-login-auth-fn-ai-0003.json"
if case_path.exists():
    with open(case_path) as f:
        case_data = json.load(f)

    req = case_data.get("requirement", [])
    print(f"\n  generated case requirement ({len(req)} lines):")
    for line in req:
        print(f"    {line[:120]}")
        if "assert_url" in line:
            print(f"      ★ 这行包含了 assert_url 定义")

    plan = case_data.get("plan", {})
    plan_points = plan.get("points", [])
    for p in plan_points:
        if p.get("key") == "intent-03" or p.get("intent_id") == "intent-02":
            print(f"\n  plan point {p.get('key')}:")
            print(f"    expected_result: '{p.get('expected_result', '')}'")
            for j, s in enumerate(p.get("steps", [])):
                print(f"    step[{j}]: action={s.get('action')} target={s.get('target')} value={s.get('value')} raw_text='{s.get('raw_text', '')}'")
else:
    print(f"\n  Generated case JSON not found at {case_path}")

# =============================================================================
# STEP 5: 对比 assert_url 的解析结果和预期
# =============================================================================
print(f"\n{'█' * 70}")
print(f"█  STEP 5: 对比分析 — 谁造成了正确的语法但错误的语义")
print(f"{'█' * 70}")

print(f"""
{SEP}
  "未登录访问首页被拦截" 这个意图的完整故事：

  1. AI 生成阶段:
     需求理解: "未登录访问首页" → 应该被拦截, 跳转到登录页
     步骤设计: goto #/home → assert_url #/home
     ★ 这里的 assert_url #/home 可能是 AI 的推理：
       "访问后 URL 是 #/home（但业务说应该被拦截）"
       或者
       "assert_url 检查 URL 是否等于 #/home（如果等于说明没拦截）"
     ★ 无论哪种理解，steps_hint 都错了

  2. resolve_explicit_step 解析:
     "assert_url:#/home" → action="assert_url", value="#/home"
     ★ 解析正确。没有修改内容。

  3. compile_execution_steps 编译:
     assert_url 的 expected="#/home"
     ★ 编译正确。语义问题无法被语法检查发现。

  4. Runner 执行:
     访问 #/home → 路由守卫拦截 → URL 变成 #/login
     assert_url("#/home") → 当前 URL 是 #/login ≠ #/home → FAIL

     如果路由守卫不工作:
     访问 #/home → 直接显示首页 → URL 保持 #/home
     assert_url("#/home") → URL 是 #/home = #/home → PASS
     ★ 守卫不工作 → 测试 PASS → 假通过

  结论:
    这不是"编译过程搞坏了数据"。
    这是 AI 生成的 steps_hint 本身就是错的。
    编译管线忠实地编译了错误的数据。
    没有人检查过 "assert_url 的值是否符合业务意图"。
    因为语法检查不关心语义。
{SEP}
""")

print()
