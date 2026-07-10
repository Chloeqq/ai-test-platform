# ATP 测试分层策略：API + DB 测试优先的论证与实施建议

**日期**：2026-07-10
**背景**：AI 生成 UI 测试用例审计发现 40% 虚假通过率，核心原因是 UI 测试依赖太多"不确定的知识"。讨论是否应优先建设 API + DB 测试能力。
**相关文档**：
- `2026-07-10_ai_generated_test_case_quality_audit.md` — 审计报告
- `2026-07-10_target_architecture_review_and_gap_analysis.md` — 目标架构评审

---

## 一、核心判断

> **先做 API + DB 测试，是解决当前质量困境的最短路径。** API + DB 测试可以消除审计中约 70% 的虚假通过和无法执行问题。

原因：当前 ATP 的核心困境是 **UI 测试需要太多"不确定的知识"，而 AI 没有这些知识**。API + DB 测试天然绕过了这些问题：

---

## 二、对照审计发现：API 测试能消除多少问题？

| 审计发现 | 当前 UI 测试 | API + DB 测试 | 是否消除 |
|---------|-------------|---------------|---------|
| 断言目标元素错误（13/20 个测试点） | assert_text 指向 button 而非 toast | API response 是结构化 JSON，不需要找元素 | ✅ 完全消除 |
| 错误文案为 AI 推测（10/20） | "用户名长度至少6位" | `response.error_code = "VALIDATION_USERNAME_TOO_SHORT"` | ✅ 完全消除 |
| 零断言（3/20） | 没有断言，步骤跑完就 pass | API response status code 本身就是一个隐式断言 | ✅ 大幅减少 |
| 断言逻辑颠倒（2/20） | assert_url(#/login) 但预期是不跳转 | 直接断言 `response.status == 200` 或 `session.created == true` | ✅ 完全消除 |
| 前置条件不可执行 | "账号已被锁定"无法自动建立 | 可以调 API 锁定账号：`PUT /admin/users/lockeduser/lock` | ⚠️ 取决于 API 是否暴露 |
| 测试数据不存在 | lockeduser 账号是否真实存在 | 可以直接查 DB 确认：`SELECT * FROM users WHERE status='locked'` | ✅ 可自动发现 |

---

## 三、具体对比：同一个测试场景，两种实现

### 场景 1："错误密码登录"

```text
当前 UI 测试的问题链:
  1. AI 生成: assert_text(target=login-submit-btn, value="密码错误")
  2. 问题1: 错误文案在 toast 元素上，不在 button 上
  3. 问题2: "密码错误" 是 AI 推测的，真实系统可能返回 "用户名或密码错误"
  4. 问题3: 即使 toast 出现了，文本不匹配 → 断言失败 → 测试 FAIL
  5. 问题4: 这个 FAIL 无法区分"校验没做"和"文案不匹配"

API + DB 测试:
  步骤:
    1. 查 DB: 获取一个有效用户 (username, password)
    2. POST /api/login {username, password: "wrong_password"}
    3. assert response.status == 401
    4. assert response.body.error_code == "INVALID_CREDENTIALS"
    5. 查 DB: sessions 表中没有该用户的新 session
    6. 查 DB: login_attempts 表中新增了一条失败记录

  断言全部是精确的:
    - status 401 → 确定性值，来自 API Schema
    - error_code "INVALID_CREDENTIALS" → 来自 API Schema
    - sessions 表无新记录 → 确定性 SQL
    - login_attempts 有新记录 → 确定性 SQL

  没有推测，没有模糊匹配，没有元素定位问题。
```

### 场景 2："账号被锁定后无法登录"

```text
当前 UI 测试:
  步骤:
    1. input(lockeduser) → input(macro123) → click(login)
    2. assert_text(target=login-submit-btn, value="账号已被锁定，请联系管理员")
  
  问题:
    - lockeduser 账号是否存在且已锁定？
    - 锁定状态如何建立？（需要后台操作或 API）
    - 错误文案是什么？（AI 推测的）
    - 断言目标元素是什么？（AI 一律指向 button）

API + DB 测试:
  步骤:
    1. setup: PUT /api/admin/users/testuser/lock  ← 用 API 建立前置条件
    2. 查 DB: 确认 testuser.status = 'locked'
    3. POST /api/login {username: "testuser", password: "correct_password"}
    4. assert response.status == 403
    5. assert response.body.error_code == "ACCOUNT_LOCKED"
    6. 查 DB: sessions 表中没有新 session

  优势:
    - 前置条件通过 API 自动建立（可重复、可自动化）
    - 所有断言精确、可验证
    - 不依赖 UI 元素的存在或文案
```

---

## 四、架构层面：API 测试的价值是拿到"正确答案"

### 信息层次对比

```text
UI 层能给你的:
  "输入错误密码后，页面应该显示错误提示"
  → 什么文案？不知道（AI 推测）
  → 出现在哪里？不知道（AI 猜 button）
  → 错误码是什么？不知道（UI 层不暴露）

API 层能给你的:
  POST /login → 401 UNAUTHORIZED
  Response: {"error": "INVALID_CREDENTIALS", "message": "用户名或密码错误"}
  → status code: 401（确定性）
  → error_code: "INVALID_CREDENTIALS"（确定性，可机器验证）
  → message: "用户名或密码错误"（确定性，来自 API Schema 而非 AI 推测）

DB 层能给你的:
  SELECT * FROM sessions WHERE user_id = ? AND created_at > NOW() - 1min
  → 有记录 = 登录成功
  → 无记录 = 登录失败
  → 这是最可靠的"业务真相"
```

### 分层测试策略

```text
第 1 层（最可靠）：DB 断言 — 数据变化符合预期
第 2 层（可靠）：   API 断言 — 接口返回符合契约
第 3 层（不可靠）： UI 断言 — 前端展示符合设计
                     ↑
                     这一层最难，应该最薄
```

**先把 API + DB 层的测试做扎实，就有了一个"正确答案"的基准。然后再加 UI 测试时，UI 测试只需要验证一件事：API 的正确结果是否正确地展示在了 UI 上。**

---

## 五、实施路径

### 最小可行路径（2-3 周）

```text
Week 1: API Runner 基础能力
  ├── 新增 API Runner（发 HTTP 请求 + 断言 response）
  ├── 新增 DB Assertion（执行 SQL + 断言查询结果）
  └── 验证：login 模块 3 个场景（成功登录、错误密码、空用户名）

Week 2: API Schema 驱动的编译
  ├── Test Compiler 读取 OpenAPI Schema
  ├── 从 Schema 中提取 status code、error_code、response body schema
  └── 验证：Compiler 能自动为 negative 场景生成正确的 error_code 断言

Week 3: 对比验证
  ├── 同一个 Test Intent，分别生成 UI DSL 和 API DSL
  ├── 执行两种 DSL，对比结果
  └── 验证：API 测试的通过率 > 90%，UI 测试的通过率 < 60%
```

### 对目标架构的影响

目标架构不需要改动。它已经包含了 API 资产和 API Runner。需要调整的是**优先级**：

```text
原来的隐含假设:
  UI 测试是主力 → API 测试是辅助

调整后:
  API + DB 测试是主力 → 覆盖 80% 的业务逻辑验证
  UI 测试是补充 → 只验证"UI 是否正确展示了 API 的结果"
  
  具体分配:
    正向/负向/边界值 → API + DB 测试（精确断言）
    交互/UI行为 → UI 测试（元素状态、页面跳转、视觉反馈）
```

### 新架构中的落位

```text
当前路径（全是 UI 测试）:
  AI 推测 → 推测 → 推测 → 执行 → 失败 → 不知道为什么失败

建议路径（API 先，UI 后）:
  API Schema（确定性）→ 生成精确断言 → 执行 → 通过率 > 90%
                                            │
  UI 测试只做 API 做不到的事:                 │
    "错误文案出现在 toast 上了吗？" ←─────────┘ 对照 API 返回的 message
    "toast 3 秒后消失了吗？"
    "输入框变红了吗？"
```

---

## 六、总结

> **先做 API + DB 测试，不是因为 UI 测试不重要，而是因为 API + DB 测试能让你先用最小的代价拿到"正确的答案"。有了正确答案作为基准，UI 测试就从"猜测+验证"变成了"对照+确认"，难度和风险都大幅降低。**
>
> API + DB 测试消除了审计中约 70% 的问题（元素定位、文案推测、断言缺失、逻辑颠倒），剩下的 30%（交互行为、视觉反馈）才是 UI 测试真正应该关注的。
