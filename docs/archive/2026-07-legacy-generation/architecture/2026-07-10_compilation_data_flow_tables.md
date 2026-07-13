# ATP 编译管线数据流表格

---

## 表1：编译全链路 — 每一步的输入、输出、用途

| 步骤 | 函数 | 读取的字段 | 输出的字段 | 用途 | 是否修改数据 |
|------|------|-----------|-----------|------|------------|
| 0 | AI 生成 | (用户需求) | steps_hint, expected, precondition | AI 理解需求，输出结构化测试意图 | — |
| 1 | `_manual_point_from_candidate()` | candidate 全部字段 | point(steps, expected_result, metadata) | 把 AI 候选转为持久化的测试点 | 否 |
| 2 | `_steps_from_candidate()` | candidate.steps, candidate.steps_hint, candidate.expected | structured_steps, steps_hint | 把自然语言步骤转为 DSL 步骤 | **是（重建）** |
| 3 | `structured_steps_from_candidate()` | steps(自然语言), expected, precondition, steps_hint | structured_steps, steps_hint, data | 核心：自然语言→DSL，含断言生成和前置条件 | **是（重建）** |
| 4 | `_build_expected_assertions()` | expected 文本 | assert_url / assert_text / assert_visible step | 从预期文本生成可执行断言 | 是（新增步骤） |
| 5 | `page_hook.setup_precondition()` | precondition 文本 | login step / setup step | 从前置条件文本生成前置步骤 | 是（新增步骤） |
| 6 | `normalize_test_points()` | point.intent_id, point.steps | normalized point(steps不变) | 格式校验 + 字段重命名 | 否 |
| 7 | `normalize_test_points_to_actions()` | step.action, step.target, step.value | action dict(type, target, value, assertion) | action 名称标准化 (assert_text→assert) | 否（只改名） |
| 8 | `build_execution_ir()` | action dicts | IR {version, steps} | 标准化中间表示 | 否 |
| 9 | `bind_targets()` | IR + page_object.elements | IR + selector, locator_type, role | 元素绑定：target → 实际 selector | 否（只追加） |
| 10 | `render_execution_steps()` | bound IR | runner steps (action=fill/click/assert_*) | 转为 Runner 可执行格式 | 否（只改名） |
| 11 | `_steps_hint_from_current_steps()` | point.steps(action, target, value) | steps_hint 文本列表 | **从 structured steps 反向生成 steps_hint 文本** | **是（覆盖 AI 原始）** |
| 12 | `_candidate_from_asset_point()` | point.steps, point.steps_hint, snapshot.steps_hint | merged_steps_hint | 合并保存 | **是（重建版覆盖原始）** |

---

## 表2：Compiler 需要的字段（最小集）

| 层级 | 字段 | 类型 | 必填 | 示例 |
|------|------|------|------|------|
| point | intent_id | string | ✅ | "intent-04" |
| point | steps | list[dict] | ✅ | [{action, target, value}, ...] |
| step | action | string | ✅ | "input" / "click" / "goto" / "assert_text" / "assert_url" / "assert_visible" / "assert_attribute" |
| step | target | string | ⚠️ | "element:login-username-input"（input/click/assert_text 时需要，goto/assert_url 不需要） |
| step | value | any | ⚠️ | "admin"（input 时需要，assert_text 可选，click/goto 不需要） |
| step | raw_text | string | 否 | "在用户名输入框输入admin"（仅用于 trace） |
| page_object | elements | dict | ✅ | {"login-submit-btn": {selector, locator_type, role}} |
| element | selector | string | ✅ | "button[type=submit]" |
| element | locator_type | string | ✅ | "css" |
| element | role | string | 否 | "button"（当前未使用，应使用） |

---

## 表3：Compiler **不需要**的字段

| 字段 | 当前是否传入 | 是否被使用 |
|------|------------|-----------|
| steps_hint | 是 | ❌ 不读 |
| expected_result | 是 | ❌ 不读（已在 structurer 中转成断言步骤） |
| precondition | 是 | ❌ 不读（已在 structurer 中转成 setup 步骤） |
| point_type | 是 | ❌ 不读 |
| description | 是 | ❌ 不读 |
| candidate_snapshot | 是 | ❌ 不读 |
| involved_elements | 是 | ⚠️ 仅 fallback 时用（steps 有 target 则不用） |

---

## 表4：数据流向 — 从 AI 生成到最终存储

| 阶段 | 存储位置 | 格式 | 内容 |
|------|---------|------|------|
| AI 原始输出 | metadata.candidate_snapshot | JSON 内嵌 | steps_hint(英文元素名), expected, precondition |
| 平台重建 | plan.points[i].steps_hint | JSON 内嵌 | steps_hint(中文元素名, 含平台新增的断言) |
| 结构化步骤 | plan.points[i].steps | JSON 数组 | [{action, target, value, raw_text}, ...] |
| 编译产物 | render_execution_steps() 输出 | list[dict] | [{action, target, selector, locator_type}, ...] |
| DB 存储 | test_point_assets.raw_payload | PostgreSQL JSONB | 整份 plan JSON（含以上所有） |
| 文件缓存 | web-ui/state/test-points/*.json | 文件 | 同 DB，可重建 |

---

## 表5：当前问题清单

| # | 问题 | 位置 | 影响 |
|---|------|------|------|
| 1 | steps_hint 被重建覆盖 AI 原始 | facade_helpers.py:1514 | AI 正确值丢失 |
| 2 | assert_text target 永远是 button | structurer.py:318 | 11 条断言目标错误 |
| 3 | assert_text value 全是 AI 推测 | structurer.py:324 | 值不可信 |
| 4 | assert_url value 被改为 #/home | structurer.py:350 | intent-03 断言值错误 |
| 5 | goto value 来自硬编码常量 | structurer.py:116 | "#/home" 不总是正确的页面 |
| 6 | steps_hint 参与编译循环 | steps_hint→structurer→steps→steps_hint | 每轮可能引入新错误 |

---

## 表6：修复后数据流 (Phase A)

| 步骤 | 数据源 | 说明 |
|------|--------|------|
| AI 生成 | candidate_snapshot.steps_hint | AI 原始，只读，不修改 |
| 结构化 | point.steps | 权威格式，编译/执行都从这里读 |
| 展示 | point.steps_hint | 降级为纯展示字段，从 candidate_snapshot 复制 |
| 保存 | snapshot 优先于重建 | 不覆盖 AI 原始 |
| 编译 | 只读 point.steps | 不读 steps_hint |