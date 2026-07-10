# ATP 编译管线取证分析：谁篡改了 AI 生成的测试用例

**日期**：2026-07-10
**方法**：逐步骤追踪 intent-04 "用户名为空点击登录" 的完整编译过程
**工具**：`trace_compilation.py`（根目录，可复现）

---

## 一、取证结论

**Compiler 没有篡改数据。数据在进入 Compiler 之前就已经坏了。**

```text
编译管线的每一步都不修改 target 和 value：

  Step 0 (AI原始):      target=element:login-submit-btn   value=请输入账号
  Step 1 (normalize):   target=element:login-submit-btn   value=请输入账号  ← 未改
  Step 2 (to_actions):  target=element:login-submit-btn   value=请输入账号  ← 未改
  Step 3 (build_ir):    target=element:login-submit-btn   value=请输入账号  ← 未改

每一步都忠实地传递了原始数据。
问题不是"数据被改了"，而是"数据本来就有问题，但没有人检查过"。
```

---

## 二、"篡改"的真正源头：resolve_explicit_step()

**文件**：`shared_backend/intent_mapping.py:56-117`
**函数**：`resolve_explicit_step()`

### 具体解析过程

```text
输入: steps_hint = ["assert_text:login-submit-btn=请输入账号"]

Step 1: 按 ":" 切分 (line 82-83)
  "assert_text:login-submit-btn=请输入账号".split(":", 1)
  → action = "assert_text"
  → payload = "login-submit-btn=请输入账号"

Step 2: 标准化 action 名 (line 84)
  _normalize_action("assert_text") → "assert_text"

Step 3: 按 "=" 切分 (line 110-111 → _split_payload)
  遍历分隔符 ("=", "::", "=>", "|")
  "=" in "login-submit-btn=请输入账号" → True
  拆开: target="login-submit-btn", value="请输入账号"

最终返回: ("assert_text", "login-submit-btn", "请输入账号")
```

### 这个函数做了什么

```text
✅ 正确的事：
  - action 名标准化（"asserttext" → "assert_text"）
  - 字符串解析格式正确（":" / "=" / "::" / "=>" / "|"）

❌ 没做的事 — 也是问题所在：
  - 不检查 target="login-submit-btn" 在 PageObject 中是否存在
  - 不检查 login-submit-btn 的 role 是什么（button 不应是 assert_text 的目标）
  - 不检查 value="请输入账号" 是确定值还是 AI 推测值
  - 不检查这个断言能否验证它所宣称的业务行为
```

---

## 三、根因：沉默的共识

```text
AI 猜了 target → resolve_explicit_step 直接用了
AI 猜了 value → resolve_explicit_step 直接用了
normalize_test_points_to_actions → 直接传递
build_execution_ir → 直接传递
bind_targets → 检查 element 存在性但不检查 role
render_execution_steps → 直接渲染
Runner → 忠实执行

每一步都正确。每一步都没有做它应该做的事情。
这是一个"沉默的共识"——每一步都假设上一步给了正确的数据。

实际上：
  - resolve_explicit_step 只做字符串切分，不做语义校验
  - execution_compiler 只做语法编译，不做语义校验
  - bind_targets 只检查 element 存在性，不检查 role 匹配

整个编译链路中没有一道 Gate 问过：
  "assert_text 的 target 是 button，这合理吗？"
  "value 是 AI 推测的，可验证吗？"
```

---

## 四、各模块的责任边界

| 步骤 | 文件 | 函数 | 对数据做了什么 | 应该做但没做的 |
|------|------|------|--------------|-------------|
| AI 生成 | generate_pipeline_orchestrate | _build_direct_candidate_orchestrator_result | 调用 resolve_explicit_step 解析 steps_hint | 不校验解析结果 |
| 解析 | shared_backend/intent_mapping.py | resolve_explicit_step | 字符串切分 ":"/"=" → action/target/value | 不检查 target 是否适合该 action 类型 |
| 规范化 | execution_compiler.py | normalize_test_points | 字段重命名 | 不修改内容 |
| 动作映射 | execution_compiler.py | normalize_test_points_to_actions | action 名映射 (assert_text→assert) | 不检查 role vs assertion_type |
| IR 构建 | execution_compiler.py | build_execution_ir | 格式标准化 | 不区分确定值和推测值 |
| 元素绑定 | execution_compiler.py | bind_targets | 查找 element_code，填充 selector/locator | 只检查存在性，不检查 role |
| 渲染 | execution_compiler.py | render_execution_steps | 转为 Runner 格式 | 不验证语义 |

---

## 五、24 条用例的受损模式分类

基于取证分析，24 条 AI 生成用例的问题可以溯源到以下根因：

| 受损模式 | 案例数 | 受损步骤 | 根因 |
|---------|--------|---------|------|
| assert_text target=button | ~10 | resolve_explicit_step | step_hint 解析时未校验 role |
| expected_value 为 AI 推测 | ~10 | resolve_explicit_step | "=" 后直接取值为 value，不标记来源 |
| 零断言 | ~3 | AI 生成层 | AI 生成 steps_hint 时未包含断言 |
| 断言逻辑颠倒 | ~2 | AI 生成层 | AI 生成了语义相反的 assert_url |
| 步骤缺失 | ~2 | AI 生成层 | steps_hint 不完整 |

**结论**：80% 的问题在 enter Compiler 之前就已经存在了。Compiler 是无辜的。
