# ATP 编译管线完整调用链

**目的**：从 AI 生成到 DSL 执行，每一步的代码位置和调试入口
**追踪用例**：intent-04 "用户名为空点击登录"

---

## 调用链总览

```text
Part A: AI 生成层
  generate_pipeline.py::run_generate_pipeline()
    → generate_pipeline_orchestrate.py::_build_direct_candidate_orchestrator_result()
      → intent_mapping.py::resolve_explicit_step()
        解析 "assert_text:login-submit-btn=请输入账号" → {action, target, value}

Part B: Compiler 编译层
  execution_compiler.py::compile_execution_steps()
    → normalize_test_points()
    → normalize_test_points_to_actions()
    → build_execution_ir()
    → bind_targets()
    → render_execution_steps()

Part C: Runner 执行层（不在本次追踪范围）
  Playwright runner 读取 rendered_steps → 执行
```

---

## Part A：AI 生成层 — 从需求到 structured steps

### A-1：生成入口

```
文件: apps/web-ui-service/app/services/workbench_generation_compiler/runtime/generate_pipeline.py
函数: run_generate_pipeline()
行号: 搜索 "def run_generate_pipeline"
说明: 生成主入口。Path A（AI驱动）或 Path B（手动/治理）汇聚于此。
      调用 _build_direct_candidate_orchestrator_result 解析 candidate。
```

### A-2：candidate 解析

```
文件: apps/web-ui-service/app/services/workbench_generation_compiler/runtime/generate_pipeline_orchestrate.py
函数: _build_direct_candidate_orchestrator_result()
行号: 409-530
说明: 接收 selected_candidate（来自 AI 生成或 store），
      遍历 steps_hint 列表，对每条调用 resolve_explicit_step，
      构建 structured steps 数组。
```

### A-3：steps_hint 解析 ★ 核心篡改点

```
文件: shared_backend/intent_mapping.py
函数: resolve_explicit_step()
行号: 56-117
参数:
  steps_hint: list[str]         — 如 ["assert_text:login-submit-btn=请输入账号"]
  page: str                     — 页面名（如 "login"）
  target: Any = None            — 外部传入的 target（本次调用为 None）
  value: Any = None             — 外部传入的 value（本次调用为 None）
  page_element_alias_map: dict  — element alias → element_code 映射
返回: (action: str, target: str | None, value: Any)
```

### A-3-1：_normalize_action — action 名标准化

```
文件: shared_backend/intent_mapping.py
函数: _normalize_action()
行号: 10-32
输入: "assert_text" → 遍历规则 → 返回 "assert_text"
映射规则:
  "goto"/"open"/"navigate"    → "goto"
  "click"/"tap"/"press"       → "click"
  "input"/"fill"/"type"       → "input"
  "assert"/"assertvisible"    → "assert_visible"
  "asserttext"/"text"         → "assert_text"
  "assertattribute"           → "assert_attribute"
  "asserturl"/"url"           → "assert_url"
  "assertmetric"/"metric"     → "assert_metric"
  "wait"/"waitfor"            → "wait_for"
  "login"                     → "login"
```

### A-3-2：_split_payload — target 和 value 分离

```
文件: shared_backend/intent_mapping.py
函数: _split_payload()
行号: 35-43
输入: "login-submit-btn=请输入账号"
逻辑:
  for separator in ("=", "::", "=>", "|"):
    if separator in payload:
      切分 → (left, right)
  无分隔符 → (payload, "")
输出: ("login-submit-btn", "请输入账号")
★ 此函数不检查 left 是否是有效的 element_code。
★ 此函数不检查 right 是确定值还是推测值。
```

### A-3-3：_resolve_target_code — element 查找

```
文件: shared_backend/intent_mapping.py
函数: _resolve_target_code()
行号: 46-53
说明: 在 alias_map 中查找 target 对应的 element_code。
      调用了 shared_backend/element_binding.py::resolve_element_code()
```

### A-3-4：字符串切分主逻辑

```
文件: shared_backend/intent_mapping.py
行号: 82-117

if ":" in hint_text:                                    # line 82
    action_raw, payload = hint_text.split(":", 1)       # line 83
    hint_action = _normalize_action(action_raw)          # line 84

    if hint_action in {"click","wait_for",
        "assert_visible","assert_text",
        "assert_url","assert_metric"}:                  # line 110
        hint_target, hint_value = _split_payload(payload)# line 111

    elif hint_action == "input":                        # line 112
        hint_target, hint_value = _split_payload(payload)# line 113

    elif hint_action == "assert_attribute":              # line 100
        ...  # 特殊处理 attribute 语法

    elif hint_action in {"goto","login"}:                # line 85
        hint_value = _normalized_text(payload)           # line 86
```

---

## Part B：Compiler 编译层 — 从 steps 到 runner 格式

### B-0：编译入口

```
文件: shared_backend/execution_compiler.py
函数: compile_execution_steps()
行号: 878-895
参数:
  test_points: list[dict]  — normalized points（含 steps 数组）
  page_object: dict        — {elements: {code: {locator, role, ...}}}
返回: list[dict]           — runner 可执行步骤

内部调用链:
  normalize_test_points → normalize_test_points_to_actions
  → build_execution_ir → bind_targets → render_execution_steps
```

### B-1：normalize_test_points

```
文件: shared_backend/execution_compiler.py
函数: normalize_test_points()
行号: 150-201
输入: 原始 points（从 state JSON 加载）
输出: normalized points（字段标准化）

做的事:
  - key → intent_id
  - 提取 involved_elements
  - 提取 steps
  - 提取 point_type
★ 不修改 steps 内部内容
```

### B-2：normalize_test_points_to_actions

```
文件: shared_backend/execution_compiler.py
函数: normalize_test_points_to_actions()
行号: 313-472
输入: normalized points
输出: action 数组（每个 step 一个 action dict）

做的事（每条 step）:
  - 提取 action 字符串 → mapped_action（line 367）
  - 映射规则（line 369-405）:
      "fill"/"input"    → type="input"
      "click"           → type="click"
      "wait"/"wait_for"  → type="wait"
      "goto"/"navigate" → type="navigate"
      "assert_visible"  → type="assert", assertion="visible"
      "assert_text"     → type="assert", assertion="text"
      "assert_url"      → type="assert", assertion="url"
      "assert_attribute"→ type="assert", assertion="attribute"
      "assert_metric"   → type="assert_metric"
      "login"           → type="login"
      else              → raise ExecutionCompilerError("action not allowed")

  - target 校验（line 407-414）:
      需要 target 的动作: input, click, wait, assert, assert_metric
      不需要 target: goto, navigate, login, assert_url

  - value 校验（line 415-421）:
      input 必须有 value

  - assertion 校验（line 422-435）:
      assert 的 assertion 必须是 visible/text/url/attribute
      assert_attribute 必须有 attribute_name + value
      assert_metric 必须有 metric_rule

★ 不校验：
  - target 是否适合该 action 类型
  - value 的来源是否可靠
  - assertion 的 role 是否匹配 target
```

### B-3：build_execution_ir

```
文件: shared_backend/execution_compiler.py
函数: build_execution_ir()
行号: 474-587
输入: actions 数组
输出: execution IR（{"version": "execution-ir/v1", "steps": [...]}）

做的事:
  - 字段标准化（target, value, assertion, attribute, metric_rule...）
  - 再次校验（line 517-562）:
      必须有意 intent_id
      action_type 不能是 "unknown"
      input/click/wait/assert/assert_metric 必须有 target
      input 必须有 value
      assert 的 assertion 必须在 _ASSERTION_TYPES 内
      assert_attribute 必须有 attribute + value
      assert_metric 必须有 rule

★ 仍然不校验 role vs assertion_type
```

### B-4：bind_targets ★ 元素绑定

```
文件: shared_backend/execution_compiler.py
函数: bind_targets()
行号: 590-714
输入: IR + page_object（含 elements 字典）
输出: bound IR（每个 step 带上 selector, locator_type, role）

做的事:
  - 遍历 IR steps
  - 对每个 step 的 target，在 page_object.elements 中查找
  - 查找逻辑（line 640-690）:
      alias_map = build_element_alias_map(page_object)  ← 构建 alias 映射
      尝试匹配: element_code 精确匹配
                 通过 alias_map 匹配
      → 找到: step["selector"] = element["locator_value"]
              step["locator_type"] = element["locator_type"]
              step["role"] = element.get("role") or None
      → 未找到: raise ExecutionCompilerError("target not found")

★ 检查了什么：
  ✅ element 是否存在

★ 没检查什么：
  ❌ element.role 是否适合该 action 类型
     （assert_text + role=button → 不会报错）
  ❌ value 是否合理
```

### B-5：render_execution_steps

```
文件: shared_backend/execution_compiler.py
函数: render_execution_steps()
行号: 717-877
输入: bound IR
输出: runner 步骤数组（action="fill"/"click"/"assert_visible"/...）

做的事:
  - action 名映射（line 753-764）:
      type="input"         → action="fill"
      type="click"         → action="click"
      type="navigate"      → action="goto"
      type="login"         → action="login"
      type="wait"          → action="wait_for"
      type="assert"        → 根据 assertion 子类型映射:
        assertion="text"   → action="assert_text"
        assertion="url"    → action="assert_url"
        assertion="attribute"→ action="assert_attribute"
        assertion="visible" → action="assert_visible"
      type="assert_metric" → action="assert_metric"

  - 最终校验（line 745-771）:
      compiler_status 必须是 "resolved"
      需要 target 的动作必须有 selector + locator_type

★ 这是编译管线的最后一步。此后数据交给 Playwright Runner 执行。
```

---

## Part C：关键数据结构在每一步的形态

### C-1：AI 原始输出（steps_hint）

```python
# 位置: web-ui/state/test-points/mall/mall-web-login-auth-fn-ai-0001.json
# 路径: plan.points[3].steps_hint

[
  "input:用户名输入框",
  "input:密码输入框=macro123",
  "click:提交按钮",
  "assert_text:login-submit-btn=请输入账号"
]
```

### C-2：structured steps（_build_direct_candidate_orchestrator_result 输出）

```python
# 位置: generate_pipeline_orchestrate.py line 437-451
# 每条 steps_hint 被 resolve_explicit_step 解析为：

[
  {"action": "input",         "target": "element:login-username-input", "value": "",        "raw_text": "清空用户名输入框"},
  {"action": "input",         "target": "element:login-password-input", "value": "macro123","raw_text": "在密码输入框输入macro123"},
  {"action": "click",         "target": "element:login-submit-btn",     "value": None,      "raw_text": "点击登录按钮"},
  {"action": "assert_text",   "target": "element:login-submit-btn",     "value": "请输入账号","raw_text": "页面提示'请输入账号'，登录失败"}
]
```

### C-3：normalize_test_points_to_actions 输出

```python
# 位置: execution_compiler.py line 443-460
# 每条 step 转为 internal action dict：

[
  {"type": "input",   "target": "element:login-username-input", "value": "",        "assertion": None,     "intent_id": "intent-04", "meta": {"compiler_status": "resolved", ...}},
  {"type": "input",   "target": "element:login-password-input", "value": "macro123","assertion": None,     "intent_id": "intent-04", "meta": {"compiler_status": "resolved", ...}},
  {"type": "click",   "target": "element:login-submit-btn",     "value": None,      "assertion": None,     "intent_id": "intent-04", "meta": {"compiler_status": "resolved", ...}},
  {"type": "assert",  "target": "element:login-submit-btn",     "value": "请输入账号","assertion": "text",   "intent_id": "intent-04", "meta": {"compiler_status": "resolved", ...}}
]
```

### C-4：build_execution_ir 输出

```python
# 位置: execution_compiler.py line 563-586
# 字段名前缀去掉了 "element:"，结构标准化：

{
  "version": "execution-ir/v1",
  "steps": [
    {"type": "input",  "target": "login-username-input", "value": "",         "assertion": None,  "selector": "", "locator_type": "", "intent_id": "intent-04", ...},
    {"type": "input",  "target": "login-password-input", "value": "macro123", "assertion": None,  "selector": "", "locator_type": "", "intent_id": "intent-04", ...},
    {"type": "click",  "target": "login-submit-btn",     "value": None,       "assertion": None,  "selector": "", "locator_type": "", "intent_id": "intent-04", ...},
    {"type": "assert", "target": "login-submit-btn",     "value": "请输入账号","assertion": "text","selector": "", "locator_type": "", "intent_id": "intent-04", ...}
  ]
}
```

### C-5：bind_targets 输出

```python
# 位置: execution_compiler.py line 700-713
# 每个 step 被填充了 selector, locator_type, role：

{
  "version": "execution-ir/v1",
  "steps": [
    {"type": "input",  "target": "login-username-input", "value": "",         "selector": "input[name='username']",   "locator_type": "css", "role": "input",  ...},
    {"type": "input",  "target": "login-password-input", "value": "macro123", "selector": "input[type='password']",    "locator_type": "css", "role": "input",  ...},
    {"type": "click",  "target": "login-submit-btn",     "value": None,       "selector": "button[type='submit']",     "locator_type": "css", "role": "button", ...},
    {"type": "assert", "target": "login-submit-btn",     "value": "请输入账号","selector": "button[type='submit']",     "locator_type": "css", "role": "button", ...}
                         ↑                                                                                                                          ↑
                    target 是 button                                                                                                     role 也是 button
                    ★ assert_text 的目标是 button — 这里应该报错但没有
  ]
}
```

### C-6：render_execution_steps 最终输出

```python
# 位置: execution_compiler.py line 780-798
# 转为 Playwright Runner 可直接执行的格式：

[
  {"action": "fill",          "target": "login-username-input", "selector": "input[name='username']",   "locator_type": "css", "role": "input",  "value": "",         ...},
  {"action": "fill",          "target": "login-password-input", "selector": "input[type='password']",    "locator_type": "css", "role": "input",  "value": "macro123",...},
  {"action": "click",         "target": "login-submit-btn",     "selector": "button[type='submit']",     "locator_type": "css", "role": "button", ...},
  {"action": "assert_text",   "target": "login-submit-btn",     "selector": "button[type='submit']",     "locator_type": "css", "role": "button", ...}
]
★ 这个 assert_text 会去 button 元素上找 text "请输入账号"
★ button 的文本是 "登录"，断言必然失败
```

---

## Part D：调试入口

### 1. 追踪单个用例的完整链路

```bash
python3 trace_compilation.py
```

### 2. 在 resolve_explicit_step 中断点

```python
# 文件: shared_backend/intent_mapping.py, line 82
# 在这里插入:
print(f"[DEBUG] hint_text = {hint_text!r}")
print(f"[DEBUG] action_raw = {action_raw!r}, payload = {payload!r}")
print(f"[DEBUG] result = {(hint_action, hint_target, hint_value)}")
```

### 3. 在 bind_targets 中断点

```python
# 文件: shared_backend/execution_compiler.py, line 700-704
# 在这里插入:
if step.get("assertion") == "text" and element.get("role") in ("button", "link"):
    print(f"[WARNING] assert_text target {step['target']} has role={element['role']}")
    print(f"           This assertion will fail because button text ≠ error message")
```

### 4. 查看 PageObject 中所有 element 的 role

```python
# 在 bind_targets 之前执行:
for code, elem in page_object.get("elements", {}).items():
    print(f"  {code}: role={elem.get('role', '')}, business_type={elem.get('business_type', '')}")
```

---

## Part E：完整文件清单（按调用顺序）

```
Part A — 生成层:
  1. apps/web-ui-service/app/services/workbench_generation_compiler/runtime/generate_pipeline.py
     → run_generate_pipeline()
  2. apps/web-ui-service/app/services/workbench_generation_compiler/runtime/generate_pipeline_orchestrate.py
     → _build_direct_candidate_orchestrator_result()          [line 409]
     → _candidate_identity()                                  [line 508]
     → _normalize_candidate_snapshot()                         [line 478]
  3. shared_backend/intent_mapping.py
     → resolve_explicit_step()                                [line 56]  ★ 核心
     → _normalize_action()                                    [line 10]
     → _split_payload()                                       [line 35]
     → _resolve_target_code()                                 [line 46]
  4. shared_backend/element_binding.py
     → resolve_element_code()                                 [被 intent_mapping 调用]

Part B — 编译层:
  5. shared_backend/execution_compiler.py
     → compile_execution_steps()                              [line 878]  ★ 入口
     → normalize_test_points()                                [line 150]
     → normalize_test_points_to_actions()                     [line 313]
     → build_execution_ir()                                   [line 474]
     → bind_targets()                                         [line 590]  ★ 元素绑定
     → render_execution_steps()                               [line 717]  ★ 最终产物
     辅助:
     → _normalized_text()                                     [line 45]
     → _is_business_type_allowed_for_action()                 [line 282]
     → _DSL_ACTIONS                                           [line 13]
     → _ASSERTION_TYPES                                       [line 14]
     → _DSL_TO_RUNNER_ACTION                                  [line 15]

Part C — 共享工具:
  6. shared_backend/type_utils.py
     → str_value(), dict_value(), list_value()

  7. shared_backend/schemas/contracts.py
     → normalize_test_point_plan_v1()

  8. shared_backend/schemas/validator.py
     → ContractValidator
```

---

## Part F：调试建议

```text
1. 先看 AI 原始输出
   → 打开 web-ui/state/test-points/mall/mall-web-login-auth-fn-ai-0001.json
   → 搜索 "intent-04"
   → 看 steps_hint 和 steps 的差异

2. 再看 resolve_explicit_step 的解析结果
   → 在 intent_mapping.py:117 之前加 print
   → 验证 target 和 value 是否被正确解析

3. 然后看 bind_targets 的 role 匹配
   → 在 execution_compiler.py:704 加 print
   → 看每个 element 的 role 字段
   → 检查 assert_text 的 target 的 role 是否合理

4. 最后看 render_execution_steps 的最终产物
   → 对比原始 steps_hint 和最终 runner action
   → 确认哪些字段被修改了，哪些保留了
```
