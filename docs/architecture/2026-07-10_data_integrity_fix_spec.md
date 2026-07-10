# ATP 数据完整性修复方案

**日期**：2026-07-10
**触发**：编译管线取证分析 — 发现多个环节覆盖了 AI 原始输出
**目标**：每一步明确输入/输出/校验规则，确保数据不被中间环节修改

---

## 原则

1. **AI 输出是原始事实，不可覆盖。** 平台只能在 AI 输出缺失或不明确的字段上补充，不能替换已有值。
2. **每一层只做自己该做的事。** 字符串解析只做切分，不做语义判断。编译只做语法检查，不做内容替换。
3. **不确定就标黄，不猜测。** 无法确定的值标记为 UNCERTAIN，不填入假设值。

---

## 修复点 1：禁止重建 steps_hint 覆盖 AI 原始输出

### 涉及文件
- `apps/web-ui-service/app/api/workbench/facade_helpers.py` — `_steps_hint_from_current_steps()` (line 1434)
- `apps/web-ui-service/app/api/workbench/facade_helpers.py` — `_candidate_from_asset_point()` (line 1488)

### 当前行为

```text
输入: point.steps = [{action: assert_url, value: "#/home", raw_text: "..."}]

_step_hint_from_current_steps() 处理:
  遍历 point.steps → action=assert_url → 读取 row.value → 拼接 "assert_url:#/home"
  输出: ["goto:#/home", "assert_url:#/home"]

_candidate_from_asset_point() line 1514:
  merged_steps_hint = list(current_steps_hint)  ← 重建版成为权威
  AI 原始输出被丢弃
```

### 修改后行为

```text
输入:
  point.steps  = [{action: assert_url, value: "#/home"}]
  snapshot.steps_hint = ['goto:#/home', 'assert_url:#/login']  ← AI 原始

修改后 _candidate_from_asset_point() line 1514:
  # 保存的优先于重建的
  saved_steps_hint = 从 snapshot 或 point 已有字段读取
  current_steps_hint = 从 point.steps 重建
  
  # 规则：saved 中有、current 中没有 → 追加 saved
  #       saved 和 current 都有 → 保留 saved（信任原始）
  #       saved 中没有、current 中有 → 追加 current
  
  merged = list(saved_steps_hint)  ← 保存的为基准
  for hint in current_steps_hint:
      if hint not in seen:         ← current 中新增的（如新加的步骤）
          merged.append(hint)
  
  # 不复原：不删除 saved 中已有的条目

输出:
  merged_steps_hint = ['goto:#/home', 'assert_url:#/login']
  ↑ AI 原始值被保留，没有被覆盖为 #/home
```

### 校验规则

```text
保存时执行以下检查：

1. 如果 snapshot.steps_hint 存在且非空
   → 它是 AI 原始输出，不可被 _steps_hint_from_current_steps() 覆盖
   → 合并时 snapshot 的值优先

2. 如果 snapshot.steps_hint 为空
   → 使用 _steps_hint_from_current_steps() 重建（兜底）

3. 如果 point.steps 和 snapshot.steps_hint 对同一 action 有不同值
   → 标黄，保留 snapshot 的值
   → warning: "steps_hint value divergence: saved='X', reconstructed='Y'"
```

---

## 修复点 2：断言目标不使用 `involved_codes[-1]`

### 涉及文件
- `apps/web-ui-service/app/services/workbench_generation_api/steps/structurer.py` — `_build_expected_assertions()` (line 282)
- `apps/web-ui-service/app/services/workbench_generation_api/steps/structurer.py` — `_build_click_step()` (line 238)

### 当前行为

```text
_build_expected_assertions():
  匹配到 ASSERT_TEXT_TOKENS → 
    target_code = involved_codes[-1]  ← 永远是最后一个元素
    例: involved_codes = ['login-username-input', 'login-password-input', 'login-submit-btn']
         target_code = 'login-submit-btn'  ← button

  assert_text 的目标永远是 button，因为 button 是操作序列的最后一个元素。
```

### 修改后行为

```text
_build_expected_assertions():
  匹配到 ASSERT_TEXT_TOKENS →
    1. 在 involved_codes 中查找 role=error/toast/text/label 的元素
    2. 如果有 → 使用该元素作为 target_code
    3. 如果没有 → target_code = ""，标记 RESOLVE_NEEDED
    4. 不使用 involved_codes[-1] 作为 fallback

  需要新增：element role 查找能力
    - structurer 接收 elements 字典（code → {role, name, locator, ...}）
    - 从 involved_codes 中筛选 role 匹配的元素

输出（修改后）:
  involved_codes = ['login-username-input', 'login-password-input', 'login-submit-btn']
  elements: {
    'login-username-input': {role: 'input'},
    'login-password-input': {role: 'input'},
    'login-submit-btn':     {role: 'button'},
  }
  
  → 查找 role in {error, toast, text, label} → 无匹配
  → target_code = ""
  → 标记 RESOLVE_NEEDED
  → 不生成 assert_text(login-submit-btn, ...) — 这是错的
```

### 校验规则

```text
生成 assert_text 时：
  1. target_code 必须非空
  2. 如果 elements 可用 → target_code 的 role 必须是 {text, label, error, toast}
  3. 如果 elements 不可用 → 标记 RESOLVE_NEEDED，不强制指定
  4. role=button/link/input 的元素不能作为 assert_text 的 target

生成 assert_visible 时：
  1. 同上，role 必须是 {container, text, image, button, link, ...} — 放宽
  2. 但不能是 {input, textarea}（这些元素的可见性通常不代表业务结果）
```

---

## 修复点 3：goto/assert_url 使用页面配置而非硬编码常量

### 涉及文件
- `apps/web-ui-service/app/services/workbench_generation_api/constants.py` — `GOTO_DEFAULT_ROUTE` (line 37), `ASSERT_URL_FALLBACK` (line 55)
- `apps/web-ui-service/app/services/workbench_generation_api/steps/structurer.py` — `_build_expected_assertions()` (line 329)

### 当前行为

```text
goto 步骤:
  route = page_config.default_route if page_config else GOTO_DEFAULT_ROUTE
  → 永远 "#/home"

assert_url 断言:
  url_fallback = page_config.login_url if page_config else ASSERT_URL_FALLBACK
  → page_config.login_url 可能是 "#/home"（从 page_url 推导）
  → 或被硬编码 "#/login"
```

### 修改后行为

```text
goto 步骤:
  输入: step_text = "直接访问首页URL"
       page_url = "http://host.docker.internal:5174/#/login" (从 PageObject 读取)
  
  处理:
    1. 优先从 step_text 中提取路由值（如 "goto:#/home" → "#/home"）
    2. 如果 step_text 是自然语言 → 从 page_url 提取路由部分
       "http://.../#/login" → "#/login"
    3. page_config.default_route 作为兜底
    4. 所有情况下标注来源: {FROM_AI} | {FROM_PAGE_URL} | {FROM_CONFIG} | {FALLBACK}

  输出: value = "#/home" 或 "#/login"，标注来源

assert_url 断言:
  输入: expected_text = "自动跳转至登录页，URL包含/login"
       page_url = "http://host.docker.internal:5174/#/login"
  
  处理:
    1. 从 expected_text 提取 URL 值
       正则: "URL包含(/[^\s，,。]*)" → "/login"
    2. 如果提取到 → value = "#/login"，标注 {FROM_EXPECTED_TEXT}
    3. 如果未提取到 → 用 page_url，标注 {FROM_PAGE_URL}
    4. ASSERT_URL_FALLBACK 仅作为最后兜底，标注 {FALLBACK}

  输出: value = "#/login"，标注 {FROM_EXPECTED_TEXT}
```

### 校验规则

```text
goto 步骤:
  1. value 必须是非空字符串
  2. value 来源必须标注（FROM_AI / FROM_PAGE_URL / FROM_CONFIG / FALLBACK）
  3. 如果来源是 FALLBACK → warning: "goto route uses hardcoded default, may not match test intent"

assert_url 步骤:
  1. value 必须是非空字符串
  2. value 来源必须标注
  3. 如果 value 包含 "home" 但 expected_text 包含 "login"/"登录"
     → warning: "assert_url value may not match expected redirect target"
```

---

## 修复点 4：expected_value 标注来源

### 涉及文件
- `apps/web-ui-service/app/services/workbench_generation_api/steps/structurer.py` — `_build_expected_assertions()` (line 316-328)
- `shared_backend/intent_mapping.py` — `resolve_explicit_step()`

### 当前行为

```text
assert_text 的 value:
  error_msg = extract_error_message(expected_text)
  → "请输入账号" (从 expected 文本提取)
  → 不标注这个值是从哪来的

解析 steps_hint 时:
  resolve_explicit_step("assert_text:login-submit-btn=请输入账号")
  → value = "请输入账号"
  → 不标注来源
```

### 修改后行为

```text
assert_text 的 value 标注来源:

  {FROM_EXPECTED_TEXT}: 从 expected 文本提取
    例: expected = "页面提示'请输入账号'，登录失败"
        → extract_error_message() → "请输入账号"
        → 标注 {FROM_EXPECTED_TEXT}
        → 这是 AI 推测的值，不可信

  {FROM_STEPS_HINT}: 从 steps_hint 解析得到
    例: steps_hint = "assert_text:login-submit-btn=请输入账号"
        → value = "请输入账号"
        → 标注 {FROM_STEPS_HINT}
        → 这也是 AI 推测的值

  {FROM_API_RESPONSE}: 从 API 实际响应获取（Phase 2）
    例: API response.body.message = "username不能为空"
        → value = "username不能为空"
        → 标注 {FROM_API_RESPONSE}
        → 这是确定值，可信

  当前 Phase 只有 FROM_EXPECTED_TEXT 和 FROM_STEPS_HINT。
  API Oracle 在 Phase 2 提供 FROM_API_RESPONSE。
```

### 校验规则

```text
value 来源检查:
  1. 如果来源是 FROM_EXPECTED_TEXT 或 FROM_STEPS_HINT
     → 标记 confidence=LOW
     → 标记为 "AI推测值，需API Oracle验证"
  
  2. 如果来源是 FROM_API_RESPONSE
     → 标记 confidence=HIGH
     → 标记为 "已验证"

  3. 同一个 assertion 的 value 如果同时有 FROM_EXPECTED_TEXT 和 FROM_STEPS_HINT
     → 两者不一致 → 标黄
     → warning: "conflicting expected values from different AI output paths"
```

---

## 数据传递契约

```text
┌─────────────────────────────────────────────────────────────────┐
│  数据传递规则                                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  规则 1: 只追加，不修改                                           │
│    下游只能在上游数据基础上追加新字段（如 selector, locator）。     │
│    不能修改上游已经设置的字段值（如 target, value）。               │
│                                                                  │
│  规则 2: 来源必须标注                                             │
│    每个值必须标注来源标签:                                         │
│      {AI_ORIGINAL}       — AI 原始输出，不可覆盖                  │
│      {PLATFORM_DEFAULT}  — 平台默认值，可能不准确                  │
│      {ELEMENT_RESOLVED}  — 元素解析结果，可信                     │
│      {API_VERIFIED}      — API Oracle 验证过的值，高可信           │
│                                                                  │
│  规则 3: 不确定就标黄                                              │
│    无法确定的值标记为 UNCERTAIN，携带 warning。                    │
│    不填入假设值。                                                 │
│                                                                  │
│  规则 4: 每层必校验                                                │
│    数据进入新函数时，检查上一步的来源标签。                         │
│    UNCERTAIN 值不能跳过校验直接使用。                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 实施顺序

```text
Phase A（1 天）：修复点 1 — 禁止重建覆盖
  文件: facade_helpers.py
  改动: _candidate_from_asset_point() 合并逻辑 + _steps_hint_from_current_steps() 降级
  验证: intent-03 的 steps_hint 保留 AI 原始 "#/login"

Phase B（1 天）：修复点 2 + 4 — 断言目标 + 来源标注
  文件: structurer.py
  改动: _build_expected_assertions() 增加 role 检查 + value 来源标注
  验证: assert_text 不再指向 button

Phase C（0.5 天）：修复点 3 — 页面配置
  文件: constants.py + structurer.py
  改动: 从 PageObject.page_url 读取，标注来源
  验证: goto/assert_url 值可追溯

Phase D（0.5 天）：回归测试
  验证: 24 条用例全部重新保存，steps_hint 与 snapshot 一致
  验证: 已有 116 个单元测试全部通过
```
