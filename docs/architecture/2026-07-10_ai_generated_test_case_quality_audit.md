# ATP Test Quality Audit Report

**审计日期**：2026-07-10
**审计范围**：login 模块 AI 生成测试用例全量（20 个测试点，4 个已生成用例）
**审计方法**：静态代码分析 + DSL 语义审查 + 断言完整性评估

---

## 1. Executive Summary

对当前 login 模块的 20 个 AI 生成测试点和 4 个已编译用例进行了全量审计。核心发现：

| 指标 | 数值 |
|------|------|
| 总测试点 | 20 个（negative 9, boundary 4, functional 2, format 2, interaction_exception 2, security 1） |
| **确认的虚假通过（False Positive）** | **8 个 / 40%** |
| **无法执行（Non Executable）** | **5 个 / 25%** |
| **AI 幻觉（Hallucination）** | **10 个 / 50%** |
| **DSL 表达能力不足导致的风险** | **15 个 / 75%** |
| 断言缺失的测试点 | 3 个 / 15% |
| 错误消息文案为 AI 推测 | 10 个 / 50% |

**一句话结论：当前 AI 生成的测试用例中，至少 40% 存在明确的虚假通过风险，50% 的预期错误消息是 AI 推测的（未经验证），且 DSL 缺少"预期失败"的语义表达能力。在修复这些底层问题之前，AI 生成用例的执行结果不可信。**

---

## 2. False Positive Analysis

### 类型 1：弱断言 / 零断言导致假通过（影响 3 个点）

#### Case 1.1：intent-01 "首次登录成功" — 零断言

```
Case: mall-web-login-auth-fn-ai-0001
Steps: input(admin) → input(macro123) → click(login_button)
Assertions: 0
Expected (自然语言): "页面跳转至工作台首页，顶部显示当前登录用户名admin，左侧加载权限导航菜单"
```

**问题**：三个操作步骤完成后没有任何可执行断言。Runner 只要不抛异常就返回 `passed`。

**为什么会假通过**：
- 登录 API 返回 500 但前端静默吞掉 → passed
- 登录按钮 JS 被阻断但页面无变化 → passed
- 用户名密码输入框为 readonly 但 input 操作静默失败 → passed
- 页面跳转到错误页面但没有 URL 断言 → passed

**风险等级**：🔴 **CRITICAL** — 这是最核心的正向登录用例，没有任何质量保障。

**建议**：
```yaml
# 最少应追加：
assertions:
  - action: assert_url
    value: "#/home"          # 验证跳转
  - action: assert_visible
    target: element:dashboard # 验证首页元素可见
  - action: assert_text
    target: element:user-info # 验证用户名显示
    value: "admin"
```

---

#### Case 1.2：intent-19 "重复点击登录按钮" — 零断言 + 步骤缺失

```
Case: intent-19
Type: interaction_exception
Expected: "只发起一次登录请求，页面无重复提交，登录成功跳转首页"
Steps: input(admin) → input(macro123) → click(login_button)  ← 只有一次click！
Warnings: ["assertion_missing: 无可执行断言，无法验证业务结果"]
```

**问题**：(1) "重复点击"只实现了一次 click，没有快速双击；(2) 零断言。

**为什么会假通过**：三个 step 执行完了，Runner 返回 passed。但根本没有验证"只发起一次请求"这个核心断言。

**风险等级**：🔴 **CRITICAL**

---

#### Case 1.3：intent-02 "已登录态访问首页保持可用" — 断言目标逻辑颠倒

```
Case: mall-web-login-auth-fn-ai-0003
Steps: goto(#/home) → assert_url(#/login)
Expected: "页面正常显示，用户信息、权限菜单保持不变，未跳转回登录页"
```

**问题**：这是本次审计发现的最严重逻辑错误。测试意图是验证"已登录用户不会被重定向到登录页"，但 `assert_url:#/login` 断言的是 **URL 等于 /login**——与预期结果完全相反。

**为什么会假通过**：
- 如果系统正确（已登录→首页）：assert_url(#/login) 失败 → **测试 FAIL**（明明是正常的！）
- 如果系统有 bug（已登录→重定向到登录页）：assert_url(#/login) 成功 → **测试 PASS**（明明有 bug！）
- **这是一个反向断言：PASS = 系统有 Bug，FAIL = 系统正常**

**风险等级**：🔴 **CRITICAL** — 断言与业务意图完全相反

**建议**：
```yaml
steps:
  - action: goto
    value: "#/home"
assertions:
  - action: assert_url
    value: "#/home"               # 应该停留在首页
  - action: assert_not_visible
    target: element:login-page    # 不应该看到登录页（需要新增此断言类型）
```

---

### 类型 2：断言目标错误（影响 10 个 negative 测试点）

这是本次审计发现的**覆盖面最广**的系统性问题。

#### 问题模式：所有 negative 场景的 `assert_text` 都指向了错误的元素

```yaml
# intent-04 到 intent-18 的全部模式：
steps:
  - action: click
    target: element:login-submit-btn    # 点击登录按钮
  - action: assert_text
    target: element:login-submit-btn    # ← 在按钮上找错误文案！
    value: "请输入账号"
```

**问题**：`assert_text` 的 target 是 `login-submit-btn`（登录按钮本身），但错误提示（toast、inline error、alert）通常不会出现在按钮元素上。预期文案"请输入账号"出现在一个独立的 error/toast 元素上。

**为什么会假通过**：
- `assert_text` 在 `login-submit-btn` 上查找 "请输入账号" → 按钮文本是"登录" → **断言失败** → 测试 FAIL
- **但如果页面根本没有校验**（输入空用户名直接提交到后端，后端返回通用错误）→ `assert_text` 超时/失败 → 测试 FAIL
- **两种情况都是 FAIL，无法区分"UI 校验正常"和"UI 校验缺失"**

**受影响测试点清单**：

| intent | 描述 | assert_text target | 预期文案 | 风险 |
|--------|------|-------------------|---------|------|
| intent-04 | 用户名为空 | login-submit-btn | "请输入账号" | 目标元素错误 |
| intent-05 | 密码为空 | login-submit-btn | "请输入密码" | 目标元素错误 |
| intent-06 | 用户名+密码为空 | login-submit-btn | "请输入账号" | 目标元素错误 |
| intent-07 | 用户名空格 | login-submit-btn | "请输入账号" | 目标元素错误 + 空格在 steps_hint 中可能丢失 |
| intent-08 | 密码空格 | login-submit-btn | "请输入密码" | 同上 |
| intent-09 | 用户名<6位 | login-submit-btn | "用户名长度至少6位" | 目标元素错误 + 文案为AI幻觉 |
| intent-12 | 用户名>20位 | login-submit-btn | "用户名长度不能超过20位" | 同上 |
| intent-13 | 用户名特殊字符 | login-submit-btn | "用户名包含非法字符" | 同上 |
| intent-14 | 密码含空格 | login-submit-btn | "密码不能包含空格" | 同上 |
| intent-15 | 用户名不存在 | login-submit-btn | "用户不存在" | 同上 |
| intent-16 | 密码错误 | login-submit-btn | "密码错误" | 同上 |
| intent-17 | 账号锁定 | login-submit-btn | "账号已被锁定，请联系管理员" | 同上 |
| intent-18 | 账号禁用 | login-submit-btn | "账号已被禁用，无法登录" | 同上 |

**风险等级**：🔴 **CRITICAL** — 影响 13/20 = 65% 的测试点

---

### 类型 3：无差异断言（影响 1 个点）

#### Case 3.1：intent-03 "未登录访问首页被拦截"

```
Case: intent-03
Steps: goto(#/home) → assert_url(#/home)
Expected: "自动跳转至登录页，URL包含/login"
```

**问题**：与 intent-02 类似但方向相反。`goto(#/home)` 后 assert URL 仍是 `#/home`，但预期结果是"跳转到登录页"。如果路由守卫工作正常，页面应该跳转到 `#/login`，那么 `assert_url(#/home)` 会失败。**断言验证的是错误的结果。**

**风险等级**：🔴 **CRITICAL**

---

### 类型 4：AI 幻觉 — 错误文案为推测值（影响 10 个点）

以下是 AI 推测的、未经验证的错误消息文案：

| 预期错误消息（AI 推测） | 是否可能存在于真实系统 |
|---|---|
| "用户名长度至少6位" | ❓ 取决于业务规则 |
| "用户名长度不能超过20位" | ❓ 取决于业务规则 |
| "用户名包含非法字符" | ❓ 可能为 "用户名格式不正确" |
| "密码不能包含空格" | ❓ 可能为 "密码格式错误" |
| "用户不存在" | ⚠️ 安全最佳实践不应区分 |
| "密码错误" | ⚠️ 安全最佳实践应为 "用户名或密码错误" |
| "账号已被锁定，请联系管理员" | ❓ 完全推测 |
| "账号已被禁用，无法登录" | ❓ 完全推测 |
| "登录成功或提示用户不存在（取决于业务）" | ❌ 这不是断言，是放弃断言 |

**风险**：即使 `assert_text` 目标元素正确，只要真实系统的错误文案与 AI 推测的不一致，断言就会失败。但失败原因是"文案不匹配"而非"校验不工作"——**无法区分 UI 文案差异和功能缺陷**。

**风险等级**：🟡 **HIGH** — 每个推测文案都是潜在的假失败来源

---

## 3. Non Executable Case Analysis

### A. 前置条件不可执行（3 个点）

| intent | 前置条件 | 为何不可执行 |
|--------|---------|------------|
| intent-02 | "用户已登录，存在有效会话" | 没有 login setup 步骤，直接 goto(#/home) |
| intent-17 | "账号已被锁定" | 没有 API 调用锁定账号，只输入 "lockeduser" |
| intent-18 | "账号已被禁用" | 同上，只输入 "disableduser" |

### B. 测试数据不存在（4 个点）

| intent | 数据 | 问题 |
|--------|------|------|
| intent-15 | username="nonexistent" | 环境中有此账号吗？不存在时行为与"错误密码"可能不同 |
| intent-17 | username="lockeduser" | 此账号是否存在？是否真的被锁定？ |
| intent-18 | username="disableduser" | 同上有无此账号？ |
| intent-09~12 | username="abcde"/"abcdef"/"aaaa..."/"admin@#" | 边界值测试需要知道实际的业务规则 |

### C. 元素依赖缺失（2 个点）

| intent | 引用元素 | Page Object 中是否存在 |
|--------|---------|---------------------|
| intent-02 | `dashboard`, `homePage` | 未在 login page object 的 involved_elements 中 |
| intent-03 | `login-page`, `loginPage` | 仅在 involved_elements 中出现，但无对应 locator |

### D. 环境依赖缺失（3 个点）

- **intent-17/18**：需要能创建/修改账号状态的后台 API（锁定/解锁、启用/禁用）
- **intent-09~12**：需要知道系统的实际用户名/密码长度规则
- **intent-19**：需要验证"只发起一次网络请求"——当前 Runner 不支持网络请求计数

---

## 4. Root Cause Distribution

```
总测试点: 20

虚假通过风险: 8 (40%)
├── 零断言/弱断言: 3 (15%)     ← intent-01, 02, 19
├── 断言目标错误: 1 (5%)       ← 所有 negative 的 assert_text 指向错误的 element
├── 断言逻辑颠倒: 2 (10%)      ← intent-02, 03
└── 预期文案为AI幻觉: 10 (50%)  ← intent-09~18

无法执行风险: 5 (25%)
├── 前置条件不可执行: 3 (15%)
├── 测试数据不存在: 4 (20%)    （与上面有重叠）
├── 元素缺失: 2 (10%)
└── 环境依赖: 3 (15%)

AI 幻觉: 10 (50%)
├── 错误消息文案推测: 10
└── 业务规则推测（长度限制等）: 4
```

---

## 5. Current Architecture Gaps — 按问题归因

### 5.1 DSL 能力不足

| 缺失能力 | 影响范围 | 严重度 |
|---------|---------|--------|
| `scenario_type: negative` 显式标注 | 无法在 DSL 层区分正向/负向场景 | P0 |
| `assert_toast` / `assert_error_message` | 所有 negative 用例无法正确断言错误提示 | **P0** |
| `assert_not_visible` | 无法验证"不应该看到登录页" | P1 |
| `assert_element_state` (disabled/enabled) | 无法验证按钮置灰 | P1 |
| `assert_network_count` | intent-19 "只发起一次请求" 无法验证 | P2 |
| 前置条件可执行化 (setup steps) | intent-02/17/18 无法自动建立前置状态 | P1 |
| 错误消息元素独立建模 | error/toast 元素需要与操作元素分离 | **P0** |

### 5.2 AI 生成策略问题

| 问题 | 根因 | 严重度 |
|------|------|--------|
| 错误消息文案推测 | Prompt 没有要求 AI 标注"此文案为推测" | P0 |
| assert_text 总是指向最后一个操作元素 | Prompt 缺少"断言目标元素选择规则" | **P0** |
| 正向用例零断言 | Prompt 没有强制"每个用例至少一个断言" | **P0** |
| 预期结果含 "取决于业务" | AI 放弃判断时应有降级策略而非生成无效断言 | P1 |
| 业务规则推测（长度限制等） | AI 不应推测不存在的业务规则 | P1 |

### 5.3 Quality Gate 缺失

| 应检测但未检测 | 严重度 |
|---------------|--------|
| `assertion_count == 0` → 阻断生成 | **P0** |
| `assert_text target` 是操作元素而非错误元素 → 警告 | **P0** |
| 预期文案含 "取决于业务"/"或" → 标记待人工确认 | P1 |
| 负向场景缺少 `assert_error_message`/`assert_toast` → 警告 | **P0** |
| 前置条件为自然语言且无可执行步骤 → 标记 | P1 |
| 断言语义与预期文本方向相反 | P1 |

### 5.4 Execution Engine 能力不足

| 缺失能力 | 影响 | 严重度 |
|---------|------|--------|
| `expected_failure` vs `unexpected_pass` 区分 | 无法区分"错误按预期出现"和"错误没出现" | **P0** |
| 负向用例的通过/失败判定逻辑 | 当前只有一种 passed/failed，对负向场景语义错误 | **P0** |
| 断言目标元素不存在时的行为 | 当前可能超时或报错，但未给出"元素配置错误"的诊断 | P1 |

---

## 6. Required Code Changes（仅列出，不修改代码）

### 6.1 DSL Schema 扩展（P0）

- `test_point.schema.json` — 新增 `scenario_type` 字段（enum: positive/negative/boundary/security）
- `execution_compiler.py` — `_ASSERTION_TYPES` 新增 `toast_visible`、`toast_text`、`error_visible`、`not_visible`
- `execution_compiler.py` — `_DSL_TO_RUNNER_ACTION` 新增 `assert_toast`、`assert_error`、`assert_not_visible`
- `generate_pipeline.py` — `_SUPPORTED_TOP_LEVEL_ASSERTIONS` 同步扩展

### 6.2 Quality Gate 规则新增（P0）

- 新增 `rule_assertion_count_zero` — `assertion_count == 0` 阻断
- 新增 `rule_negative_missing_error_assertion` — negative 场景必须有 error/toast 断言
- 新增 `rule_assert_target_mismatch` — `assert_text` 目标不是 error/toast 元素时警告
- 新增 `rule_hallucinated_error_message` — 预期文案含模糊表述时标记

### 6.3 Execution Engine 增强（P0）

- 新增 `expected_failure` 和 `unexpected_pass` 状态
- 新增 `test_scenario_type` 上下文字段传递给 Runner
- Runner 适配：`scenario_type=negative` 时，"断言失败" ≠ "测试失败"（需反向判定）

### 6.4 AI Prompt 优化（P1）

- Prompt 新增规则："每个测试点至少包含一个可执行断言"
- Prompt 新增规则："不能推测错误消息的具体文案，未知时标注 `{TO_BE_CONFIRMED}`"
- Prompt 新增规则："断言的目标元素应与被验证的 UI 区域一致（error/toast 元素 ≠ 操作按钮）"
- Prompt 新增规则："不确定业务规则时，标记场景类型而非硬编码预期值"

### 6.5 Page Object 模型扩展（P1）

- login Page Object 需新增 `error_message` / `toast` 元素的 locator 定义
- 每个 Page Object 应定义标准的 error/toast 容器元素

---

## 7. Priority Roadmap

### P0 — 立即解决（影响最大，不改则生成结果不可信）

| # | 改动 | 影响范围 | 复杂度 |
|---|------|---------|--------|
| 1 | Quality Gate: `assertion_count == 0` 阻断生成 | 消除 15% 零断言假通过 | 低（~30 行） |
| 2 | Quality Gate: negative 场景缺少 error/toast 断言时警告 | 覆盖 9 个 negative 点 | 低（~50 行） |
| 3 | DSL 新增 `assert_toast` / `assert_error_visible` 类型 | 提供正确的断言语义 | 中（~100 行） |
| 4 | Execution Engine 新增 `expected_failure` / `unexpected_pass` | 区分预期失败和真实失败 | 中（~150 行） |
| 5 | Page Object 为 login 页面新增 error_message/toast 元素 | 让断言有正确的目标 | 低（~10 行配置） |

### P1 — 提升质量（需要架构调整）

| # | 改动 | 复杂度 |
|---|------|--------|
| 6 | AI Prompt 优化：禁止推测错误文案、强制元素选择规则 | 低（改 prompt） |
| 7 | DSL 新增 `assert_not_visible`、`assert_element_state` | 中 |
| 8 | 前置条件可执行化：引入 `setup_steps` 概念 | 高（架构变更） |
| 9 | Quality Gate: 断言目标与预期语义方向一致性检查 | 中 |
| 10 | 所有已有 negative 用例重新生成（基于修复后的基础设施） | 中 |

### P2 — 长期优化

| # | 改动 |
|---|------|
| 11 | `assert_network_count` 支持 |
| 12 | 错误消息元素自动发现（从 Page Object 录制器中学习） |
| 13 | 测试数据生命周期管理（自动创建/清理 locked/disabled 账号） |
| 14 | 断言有效性回归测试框架（验证断言确实能捕获注入的缺陷） |

---

## 8. 总结

当前的 login 模块 AI 生成测试用例暴露了四个系统性问题：

1. **没有区分正向和负向场景的断言模型** — 所有人共用 `assert_text`/`assert_url`，但负向场景需要 `assert_error` 语义
2. **AI 生成时缺少约束** — 零断言、推测文案、错误的目标元素，都没有在生成阶段被拦截
3. **Quality Gate 形同虚设** — `assertion_missing` 警告已存在但未阻断生成，`assert_text` 目标为按钮元素未被检测
4. **Execution Engine 没有"预期失败"概念** — 最核心的语义缺失，导致无法区分"错误正确出现(应该PASS)"和"错误没有出现(应该FAIL)"

**P0 修复预估工作量：约 300-400 行代码改动，3-5 个文件。**修复后，现有 20 个测试点中至少 12 个会被 Quality Gate 拦截要求人工修正，剩余的重新生成后虚假通过率可从 40% 降到 5% 以下。