# 平台规则沉淀（当前代码现状）

这份文档只记录当前平台已经落地的硬规则，用作后续 Dify、后端编排、前端提示词和校验逻辑的统一依据。

## 1. 总原则

- 只接受显式信息，不做通用兜底猜测。
- 页面、元素、步骤、断言都必须可追踪。
- LLM 可以生成候选，但最终必须通过平台契约校验。
- 规则优先级高于“看起来合理”的推断。

## 2. 当前主链

`需求 -> requirement_spec -> test_intents -> test_points -> execution IR -> page object 绑定 -> 可执行代码`

对应实现主要在：

- `apps/ai-orchestrator/src/services/requirement_parse_support.py`
- `apps/ai-orchestrator/src/services/requirement_testpoint_support.py`
- `shared_backend/intent_mapping.py`
- `shared_backend/execution_compiler.py`
- `shared_backend/element_binding.py`
- `shared_backend/schemas/models.py`
- `shared_backend/schemas/validator.py`

## 3. 需求解析规则

- `page` 不能为空。
- `requirement` 不能为空，除非同时提供了多源输入。
- `source` 只能是平台允许的来源值。
- `test_intents` 是需求解析后的核心输出，不接受空结果作为正常态。
- `design_input` 不能为空。
- `parse_confidence` 低于阈值时要进入阻断或降级。
- `high ambiguity` 存在时可以阻断。
- `coverage_gap_ratio` 超阈值时要阻断。

### 来源相关阈值

当前代码对不同来源使用不同门槛：

- `prd_text`
- `openapi_spec`
- `git_diff`
- `user_story`
- `defect_ticket`
- `mixed`

这些来源的 `min_test_intents`、`min_parse_confidence`、`max_coverage_gap_ratio` 都可能不同。

## 4. 测试点规则

- `intent_id` 必须存在。
- `expected_result` 是标准字段，不能丢。
- `involved_elements` 是 canonical 元素列表。
- `steps` 必须是结构化步骤，不能只给自然语言。
- `steps_hint` 必须显式存在，不能靠标题反推。

### 显式步骤映射

`shared_backend/intent_mapping.py` 当前只允许显式映射：

- `goto` 需要显式 route
- `login` 允许直接登录动作
- `click` 需要显式 target
- `wait_for` 需要显式 target
- `assert_visible` 需要显式 target
- `assert_text` 需要显式 target
- `assert_url` 需要显式 url
- `input` 需要显式 target 和 value

禁止行为：

- 不允许从标题自动猜步骤
- 不允许没有 `target` 的点击类步骤
- 不允许没有 `value` 的输入类步骤
- 不允许把模糊语句当成可执行步骤

## 5. 页面对象规则

- 页面对象必须先存在于 DB 或 YAML 资产中。
- 页面对象找不到时，测试点不能假装可生成。
- 元素映射来自：
  - `element_code`
  - `selector`
  - `element_name`
  - `aliases`
- 元素别名解析必须命中明确的代码，不做模糊补全。

### 未知元素处理

- 未注册到 Page Object 的元素要进入 `unknown_elements`。
- 只要关键元素未知，就应阻断或标记 `block`。
- `页面对象不可用` 不能被通用兜底绕过。

## 6. 执行编译规则

`shared_backend/execution_compiler.py` 会把测试点转成可执行 IR。

### 允许的动作

- `input`
- `click`
- `wait`
- `navigate`
- `assert`
- `login`

### 关键约束

- `input / click / wait / assert` 一般都需要 `target`
- `assert_url` 例外，不需要 `target`
- `login` 例外，不需要 `target`
- `input` 必须有 `value`
- `assert` 的断言类型只能是 `visible / text / url`
- 动作类型不在白名单内就直接失败

## 7. 用例命名规则

`shared_backend/case_rules.py` 里的现有约束：

- `case_id` 必须符合平台标准格式
- `page_code / module_code / case_type / source` 必须命中字典
- `case_title` 不能为空
- `case_title` 不能只是编码或英文短横线拼接
- `case_title` 应使用中文描述
- `case_title` 不应混入明显英文单词
- `case_title` 至少应包含 4 段语义

## 8. 质量门禁规则

`RequirementTestPointSupport` 当前会根据质量门禁阻断：

- `test_intents` 数量不足
- `parse_confidence` 过低
- 高歧义存在
- 覆盖缺口比例过高
- `design_input` 为空
- `page` 为空

## 9. 对 Dify 的接入要求

如果把这条链路放进 Dify，节点输出也要遵守这些规则：

- 节点 1 输出标准化测试点时，必须给出明确 `target`
- 节点 2 输出 DSL 时，不能丢失 `target / value / assertion`
- 节点 3 输出代码时，只能消费已经结构化的 DSL
- 任何一步缺少显式映射，都应该返回 block，而不是猜测补齐

## 10. 不允许的实现

- 不允许通用兜底规则替代显式映射
- 不允许依赖标题、描述、模糊相似度自动补 target
- 不允许页面对象缺失时继续生成“看似可执行”的步骤
- 不允许把失败静默吞掉后输出正常结果

## 11. 维护原则

- 新规则优先落到 shared_backend 或 orchestrator 的公共层
- 只在一个地方定义，避免 web-ui-service 和 ai-orchestrator 各写一套
- 文档更新必须跟代码校验保持同步
- 若规则变更，应优先更新测试，再更新提示词/工作流
