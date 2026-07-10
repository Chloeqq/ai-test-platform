# ATP 生成链路重构方案：从"事后 Gate"到"事中语义校验"

**日期**：2026-07-10
**触发条件**：AI 生成测试用例质量审计发现 40% 虚假通过率，Quality Gate 多轮修复无效

---

## 一、为什么 Quality Gate 修了多轮仍然无效？

### 当前架构的本质问题：Gate 是"事后检查"而非"事中约束"

看一下当前生成链路和 Quality Gate 的时序关系：

```text
                    Quality Gate 介入点
                          │
                          ▼
AI 生成 ──→ DSL 编译 ──→ Gate 检查 ──→ 通过/拦截
  │                                    │
  └── 问题已经注入 ─────────────────────┘
```

Gate 在**生成完成后**才介入。它只能做两件事：通过或拦截。但拦截一个已生成的有问题用例，代价是什么？用户看到的是"生成失败"，但没有得到"如何修正"的指导。于是实际行为往往是：降低 Gate 的严格度，让有问题的用例通过——这就是**Gate 形同虚设**的根本原因。

### 具体证据链

从审计结果追踪 ATP 的各个 Phase 做了什么的对应关系：

| Phase | 做了什么 | 为什么没解决此次审计发现的问题 |
|-------|---------|------------------------------|
| Phase 4.1 Generate Gate | 生成前检查 assertion + candidate_step 完整性 | 只检查"有没有"，不检查"对不对"。intent-04 有 `assert_text`，Gate 放行。但它没有检查 `assert_text` 的 target 是不是错误元素 |
| Phase 4.2 Review Gate | approve 前检查 assertion + candidate_step | 同上——形式检查，非语义检查 |
| Phase 4.3 Execute Gate | run_case 前追溯 source_asset 检查质量 | 只检查 source_asset 是否存在，不检查断言是否可执行 |
| Phase 5.1 Quality Snapshot | 每次 asset 保存后追加 JSONL | 事后记录，不影响生成质量 |
| Phase 5.2 Dashboard API | 展示质量数据 | 可视化问题，不解决问题 |
| Phase 5.3 Quality Dashboard Frontend | 前端仪表盘 | 同上 |

**结论：四个 Phase 的 Gate 都是"形式检查"（有没有、存不存在），没有一个做"语义检查"（对不对、合不合理）。**

### 用审计中的具体案例说明

以 intent-04 "账号为空点击登录" 为例，追踪它如何穿越所有 Gate：

```text
intent-04 穿越 ATP 全链路：

Phase 4.1 Generate Gate:
  检查: "有 assertion 吗？" → 有 assert_text ✓
  检查: "有 candidate_step 吗？" → 有 ✓
  结果: 放行 ← Gate 工作正常，但没发现断言目标是错的

Phase 4.2 Review Gate:
  检查: "有 assertion 吗？" → 有 ✓
  结果: 放行 ← 同上

Phase 4.3 Execute Gate:
  检查: "source_asset 存在吗？" → 存在 ✓
  结果: 放行 ← 同上

Runner 执行:
  assert_text(target=login-submit-btn, value="请输入账号")
  → 按钮文本是 "登录"，不是 "请输入账号"
  → 断言失败
  → 测试 FAIL

但问题是：这个 FAIL 意味着什么？
  ├── 前端校验正常工作，只是错误文案出现在 toast 而非按钮上 → 假失败
  ├── 前端校验根本没做 → 真失败
  └── 无法区分 ← 这才是核心问题
```

**所有 Gate 都在检查"有没有穿衣服"，没有 Gate 检查"衣服是否穿对了"。**

---

## 二、根因分析：五个架构层面的断层

### 断层 1：AI 输出的是"意图"，DSL 需要的是"指令"

```text
AI 输出的:                          DSL 需要的:
"页面提示'请输入账号'"              assert_toast(target=error-toast, value="请输入账号")
                                    OR
                                    assert_text(target=inline-error-username, value="请输入账号")

"密码从明文变为密文显示"             assert_attribute(target=password-input, attr=type, value="password")

"页面正常显示，未跳转回登录页"        assert_url(value="#/home")
                                    AND assert_not_visible(target=login-page)
```

AI 生成的是自然语言描述（人类可以理解），但 DSL 需要的是精确的元素引用和断言类型。**当前架构中，从"意图"到"指令"的翻译由 AI 自己完成，没有任何中间层的校验或转换。**

### 断层 2：Gate 的检查维度与真实失败模式不匹配

```text
Gate 检查的维度:                    测试真实失败的原因:
─────────────────────────────────────────────────────────
assertion_count > 0        ←→      断言类型不对（用了 assert_text 而非 assert_toast）
                                    断言目标错误（指向按钮而非错误元素）
                                    断言值错误（AI 推测的文案）
                                    断言语义相反（应该 assert_not_visible 而非 assert_visible）

candidate_step 存在        ←→      步骤缺失（只有一次 click 而非快速双击）
                                    步骤顺序错误（前置条件未建立就执行）

source_asset 存在          ←→      前置条件不可执行（"用户已登录" 但没有登录步骤）
                                    测试数据不存在（lockeduser 账号未创建）
                                    元素不存在（dashboard 不在 Page Object 中）
```

Gate 在 1 楼查房，问题全在 3 楼。

### 断层 3：AI 生成和 DSL 编译之间的"语义鸿沟"无人填补

```text
当前链路的实际数据流：

AI Prompt
  ↓
AI 输出 (requirement 文本 + steps_hint)
  ↓
_normalize_test_point_plan_v1()  ← 只做格式规范化，不做语义校验
  ↓
compile_execution_steps()        ← 只做语法编译，不做语义校验
  ↓
Execution IR                     ← 此时错误已经固化为 DSL
  ↓
Runner                           ← 忠实地执行错误的指令
  ↓
结果: FAIL 或 False Positive
```

**缺失的环节**：在 `_normalize` 和 `compile` 之间，没有一个 **Semantic Validator** 来检查：
- 断言类型是否匹配场景类型（negative → 应有 error/toast 断言）
- 断言目标元素是否合理（assert_text 的目标不应该是 button）
- 预期值是否是 AI 推测的（含"取决于业务"等模糊表述）
- 前置条件是否可自动建立

### 断层 4：DSL 的设计假设是"人工编写"，不是"AI 生成"

```text
DSL V1.1 的设计假设:                 AI 生成的实际行为:
─────────────────────────────────────────────────────────
人工知道错误消息的确切文案           AI 推测文案
人工知道错误出现在哪个元素上         AI 一律指向最后一个操作元素
人工会区分正向/负向断言类型          AI 全部用 assert_text/assert_url
人工会建立前置条件                   AI 把前置条件写成自然语言
人工会写足够的断言                   AI 可能零断言
```

DSL V1.1 的 6 条铁律是为**人工编写的用例**设计的——它假设写用例的人知道正确答案。但当输入来自 AI 时，"正确答案"本身就是不确定的。**DSL 缺少"不确定性标注"机制**——无法表达"这个断言值我不确定，执行时请模糊匹配或跳过并记录"。

### 断层 5：生成链路缺少"可执行性反馈闭环"

```text
当前:
  AI 生成 → Gate(通过/拦截) → 结束

应该有:
  AI 生成 → Semantic Validator → 反馈给 AI → AI 修正 → 再验证 → Gate → 结束
                                  │
                                  └── 如果AI无法修正 → 标记为"需人工介入"并给出具体原因
```

Gate 是单向阀门，不是双向对话。一个真正有效的质量体系应该让 AI 从 Gate 的拦截中学到"为什么被拦"，然后修正。当前架构做不到这一点。

---

## 三、生成链路重构方案

### 3.1 目标架构

```text
┌─────────────────────────────────────────────────────────────────┐
│                     Generation Pipeline V2                        │
│                                                                   │
│  Phase A: Intent Structuring                                     │
│  ┌──────────┐    ┌──────────────┐    ┌────────────────────┐     │
│  │ AI 生成   │───→│ Intent       │───→│ StructuredIntent    │     │
│  │ raw text  │    │ Classifier   │    │ {type, target,      │     │
│  │          │    │              │    │  expected_behavior,  │     │
│  │          │    │ 分类意图类型  │    │  confidence}         │     │
│  └──────────┘    └──────────────┘    └────────┬───────────┘     │
│                                                │                  │
│  Phase B: Semantic Resolution              ←── 新的核心环节      │
│  ┌─────────────────────────────────────────────▼──────────────┐ │
│  │  Semantic Validator (语义校验器)                             │ │
│  │                                                              │ │
│  │  Rule 1: 断言类型 → 场景类型匹配检查                          │ │
│  │    negative → 必须有 error/toast/not_visible 之一             │ │
│  │    functional → 必须有 visible/text/url 之一                  │ │
│  │                                                              │ │
│  │  Rule 2: 断言目标 → 元素角色匹配检查                          │ │
│  │    assert_text 的目标必须是 text/label/error/toast 元素       │ │
│  │    assert_click 的目标必须是 button/link 元素                 │ │
│  │                                                              │ │
│  │  Rule 3: 预期值 → 置信度评估                                  │ │
│  │    精确文案 → HIGH confidence → 精确匹配                      │ │
│  │    模糊表述 → LOW confidence → 标记 {TO_BE_VERIFIED}          │ │
│  │    "取决于业务" → ZERO confidence → 阻断，需人工指定           │ │
│  │                                                              │ │
│  │  Rule 4: 前置条件 → 可执行性检查                              │ │
│  │    有对应 setup API/步骤 → 自动注入                            │ │
│  │    无对应 setup → 标记为 manual_precondition                   │ │
│  │                                                              │ │
│  │  Rule 5: 元素引用 → Page Object 存在性检查                    │ │
│  │    有 locator → 生成 DSL 步骤                                 │ │
│  │    无 locator → 标记为 missing_element                        │ │
│  └──────────────────────────┬───────────────────────────────────┘ │
│                              │                                     │
│  Phase C: Feedback Loop     │    ← 新的关键能力                   │
│  ┌──────────────────────────▼───────────────────────────────────┐ │
│  │  Validation Result:                                           │ │
│  │                                                              │ │
│  │  ALL_PASS → 进入 Phase D (编译)                               │ │
│  │                                                              │ │
│  │  FIXABLE → 返回 AI 修正:                                      │ │
│  │    "intent-04: assert_text 的目标 login-submit-btn 是按钮,    │ │
│  │     错误提示通常出现在 toast 或 inline-error 元素上。          │ │
│  │     请将断言目标改为 error-toast 元素, 或将断言类型改为       │ │
│  │     assert_toast。当前可用错误元素: [error-toast,              │ │
│  │     inline-error-username]"                                   │ │
│  │                                                              │ │
│  │  BLOCKED → 标记需人工介入:                                     │ │
│  │    "intent-17: 前置条件'账号已被锁定'无法自动建立。            │ │
│  │     需要: (1) 提供锁定账号的 API, 或 (2) 手动创建测试账号"     │ │
│  └──────────────────────────┬───────────────────────────────────┘ │
│                              │                                     │
│  Phase D: DSL Compilation   │                                     │
│  ┌──────────────────────────▼───────────────────────────────────┐ │
│  │  compile_execution_steps()  ← 保持现有逻辑                     │ │
│  │  resolve_page_object()                                        │ │
│  │  ContractValidator                                            │ │
│  └──────────────────────────┬───────────────────────────────────┘ │
│                              │                                     │
│  Phase E: Execution Adapter │    ← 新增                           │
│  ┌──────────────────────────▼───────────────────────────────────┐ │
│  │  根据 scenario_type 调整执行模式:                              │ │
│  │                                                              │ │
│  │  scenario_type=positive:                                      │ │
│  │    所有断言通过 → PASS                                        │ │
│  │    任一断言失败 → FAIL                                        │ │
│  │                                                              │ │
│  │  scenario_type=negative:                                      │ │
│  │    错误断言通过(错误正确出现) → PASS                           │ │
│  │    错误断言失败(错误未出现) → UNEXPECTED_PASS (最危险)         │ │
│  │    步骤本身抛异常(非断言) → FAIL                               │ │
│  │                                                              │ │
│  │  scenario_type=boundary:                                      │ │
│  │    边界值被正确拒绝 → PASS (expected_failure)                  │ │
│  │    边界值被错误接受 → FAIL (unexpected_pass)                   │ │
│  └──────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 核心新增组件

#### 3.2.1 Intent Classifier（意图分类器）

```python
# 新增文件: app/services/generation_semantic/intent_classifier.py

class StructuredIntent:
    """从 AI 原始输出中提取的结构化意图"""
    scenario_type: Literal["positive", "negative", "boundary", "security", "interaction"]
    expected_behavior: Literal["success", "error_shown", "blocked", "redirected", "no_change"]
    target_assertion_type: Literal["assert_toast", "assert_error", "assert_not_visible", 
                                    "assert_visible", "assert_text", "assert_url"]
    confidence: float  # 0.0 ~ 1.0
    uncertain_fields: list[str]  # 哪些字段是 AI 推测的
```

这个组件不做"检查"，而是做"理解"——把 AI 的自然语言输出映射到结构化的测试意图模型。这是 Semantic Validator 能工作的前提。

#### 3.2.2 Semantic Validator（语义校验器）

```python
# 新增文件: app/services/generation_semantic/semantic_validator.py

class SemanticValidator:
    """5 条规则，每条对应一个审计发现的失败模式"""
    
    def validate(self, intent: StructuredIntent, page_object: PageObject) -> ValidationResult:
        results = [
            self._rule_assertion_scenario_match(intent),      # 断言类型 vs 场景类型
            self._rule_target_role_match(intent, page_object), # 断言目标 vs 元素角色
            self._rule_expected_value_confidence(intent),      # 预期值 vs 置信度
            self._rule_precondition_executable(intent),        # 前置条件 vs 可执行性
            self._rule_element_exists(intent, page_object),    # 元素 vs Page Object
        ]
        return self._merge(results)
```

每条规则返回三种结果之一：
- `PASS` — 进入下一阶段
- `FIXABLE(guidance)` — 可自动修复，携带给 AI 的修正指引
- `BLOCKED(reason)` — 不可自动修复，标记需人工介入

#### 3.2.3 Feedback Loop（反馈闭环）

这是重构的核心价值——让 AI 从校验结果中学习并修正：

```python
# 新增文件: app/services/generation_semantic/feedback_loop.py

class GenerationFeedbackLoop:
    """最多 3 轮修正，超出则标记 BLOCKED"""
    MAX_RETRIES = 3
    
    def run(self, raw_ai_output, page_object) -> FinalResult:
        for round in range(self.MAX_RETRIES):
            intent = self.classifier.classify(raw_ai_output)
            result = self.validator.validate(intent, page_object)
            
            if result.is_pass():
                return self._compile(intent)
            
            if result.is_fixable():
                # 把修正指引反馈给 AI
                raw_ai_output = self._ai_fix(raw_ai_output, result.guidance)
                continue
            
            if result.is_blocked():
                return FinalResult(status="needs_human", reason=result.reason)
        
        return FinalResult(status="needs_human", reason="max_retries_exceeded")
```

#### 3.2.4 Element Role Registry（元素角色注册表）

这是修复"断言目标总是按钮"问题的关键：

```python
# 新增: Page Object 中的元素角色标注
# 现有 Page Element 模型增加 role 字段

class ElementRole(str, Enum):
    INPUT = "input"           # 输入框
    BUTTON = "button"         # 按钮
    TOGGLE = "toggle"         # 切换开关
    TEXT = "text"             # 文本展示
    LABEL = "label"           # 标签
    ERROR = "error"           # 错误提示
    TOAST = "toast"           # Toast 消息
    CONTAINER = "container"   # 容器
    NAVIGATION = "navigation" # 导航

# 断言 → 目标元素角色映射规则:
ASSERTION_TARGET_ROLE_MAP = {
    "assert_text": {ElementRole.TEXT, ElementRole.LABEL, ElementRole.ERROR, ElementRole.TOAST},
    "assert_toast": {ElementRole.TOAST},
    "assert_error": {ElementRole.ERROR},
    "assert_visible": {ElementRole.BUTTON, ElementRole.TEXT, ElementRole.CONTAINER, ...},
    "assert_not_visible": {ElementRole.ERROR, ElementRole.TOAST, ElementRole.CONTAINER, ...},
    "assert_url": set(),  # 不需要目标元素
    "assert_element_state": {ElementRole.BUTTON, ElementRole.INPUT},
}
```

---

### 3.3 实施优先级

```text
P0 (1-2周) — 消除 80% 的虚假通过
├── 1. Element Role Registry（元素角色注册）
│     给 login 模块的 4 个元素标注 role
│     改动: PageElement 模型 +1 字段，login page object +4 行配置
│
├── 2. Semantic Validator Rule 1+2（断言类型/目标校验）
│     5 条规则只先实现最关键的 2 条
│     改动: ~200 行新代码
│
├── 3. Execution Adapter（区分 expected_failure vs unexpected_pass）
│     改动: ~100 行
│
└── 4. Page Object 补充 error_message 元素
      改动: ~10 行配置

P1 (2-4周) — 反馈闭环
├── 5. Intent Classifier
├── 6. Feedback Loop（AI 修正循环）
└── 7. Semantic Validator Rule 3+4+5

P2 (长期) — 智能化
├── 8. 错误元素自动发现（从录制器中学习）
├── 9. 前置条件自动 setup（集成测试数据工厂）
└── 10. 断言有效性回归测试（Mutation Testing）
```

---

## 四、总结

> **Quality Gate 修了多轮仍然无效的根本原因：所有 Gate 都是"形式检查"（有没有），没有"语义检查"（对不对）。这就像一个安检门只检查"你带了证件吗"但不检查"证件是不是你的"。**

重构的核心思路只有一句话：

**把 Quality Gate 从"事后拦截器"变成"事中翻译器"——不只是告诉 AI "你错了"，而是告诉 AI "哪里错了、为什么错、应该怎么改"。**

新增的四个关键组件：
1. **Intent Classifier** — 理解 AI 的意图
2. **Semantic Validator** — 用 5 条语义规则检查
3. **Feedback Loop** — 让 AI 修正自己的错误
4. **Element Role Registry** — 让断言知道该找什么元素
