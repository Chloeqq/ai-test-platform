# ATP v3.2 反方架构审计报告（终审）

**审计角色**：反方架构审计专家（不优化，只攻击）
**审计对象**：ATP v3.2 完整交付（Sprint 1 + Sprint 2 + Phase 3 集成）
**审计日期**：2026-07-10
**原则**：证明这个方案会失败
**相关文档**：
- `2026-07-10_atp_mvp_v3_frozen_spec.md` — v3.2 冻结版
- `2026-07-10_adversarial_architecture_audit.md` — 初版反方审计
- `2026-07-10_mvp_redesign_committee_decision.md` — 委员会决议

---

## 1. 核心价值审计

### 1.1 ATP 是否真的解决了 UI 自动化虚假通过问题？

**没有。它只是换了一个地方报告问题。**

```text
之前的问题：
  UI 测试 PASS → 不知道是真的通过还是假通过

ATP 的做法：
  跑 API 测试 → 对比 UI → 报告 "API返回X，UI断言Y，不一致"

问题转移了，没有解决：
  之前：QA 不知道 UI 测试是否可靠
  现在：QA 收到一份 Layer Comparator 报告，写着 "需人工判断"
  
  QA 仍然需要人工判断。
  ATP 没有减少人工工作量，只是给人工判断提供了更多上下文。
```

**如果 ATP 的价值是"提供更多上下文"，那它的竞品是 Allure Report + 截图 + 日志——这些也是上下文。**

### 1.2 是否只是增加了一层报告？

**是的。从 Demo 输出来看，本质上就是：**

```text
  Step 1: 展示审计数据（静态JSON）
  Step 2: 执行 API 测试（curl 也能做）
  Step 3: 对比差异（人眼也能做）
  Step 4: 打印报告

  去掉 "ATP" 品牌，这就是一个脚本：
    curl POST /admin/login → 拿到 response
    diff <API结果> <UI断言> → 标记差异
    echo "需要人工判断"
```

**差异化在哪？Postman + diff 命令也能做同样的事。**

### 1.3 如果 API、UI、Spec 三者都有错误，ATP 是否还能发现？

**不能。这是 Oracle 悖论的核心。**

```text
场景：被测系统有一个 Bug — 登录逻辑完全不工作，但：
  - API 返回 200 + 空 body（后端未处理异常，框架默认返回 200）
  - UI 显示空白页（前端未处理异常，框架默认渲染空壳）
  - Spec 写错了（需求文档说"正确密码应登录"，但没说错误密码怎么办）

ATP 的行为：
  - API 测试：200 → PASS（断言通过）
  - UI 测试：空白页 → 断言取决于写的是什么（可能 PASS 或 FAIL）
  - Layer Comparator：API PASS + UI ? → 报告无 divergences 或 "需人工判断"
  
  → Bug 完全没有被发现。
  → 三层全部错误，Comparator 检测不到。
```

---

## 2. Oracle 悖论审计

### 2.1 API Oracle 如果本身错误怎么办？

```text
v3.2 已经意识到了这个问题，把 "Assertion Calibrator" 改成了 "Layer Comparator"。

但改名不解决实际问题：
  - Comparator 说 "intent_ui: API返回X, UI断言Y, 不一致"
  - 人看了之后：到底是 API 错了还是 UI 错了？
  - Comparator 回答不了。

  最终还是要人去判断。
  而"人去判断"这个问题，在 ATP 出现之前就存在。
  ATP 没有让"人去判断"变得更容易——只是把信息换了个格式展示。
```

### 2.2 DB 数据如果错误怎么办？

```text
当前 DB 断言：
  SELECT 1 FROM sessions WHERE user_id = ...

如果 sessions 表本身没有数据（因为后端根本没写 session 逻辑）：
  → DB 断言返回 "not_exists"
  → Comparator 报告 "DB 无记录"

但这能说明什么？
  - 后端没写 session？→ 后端 Bug
  - session 表名不对？→ ATP 配置错误
  - 数据库连接到了错误的实例？→ 环境问题

Comparator 回答不了。又是 "需人工判断"。
```

### 2.3 谁验证 Oracle？

```text
ATP 的架构中，没有任何一层验证 Oracle 本身。

  selftest 只验证"HTTP 客户端能发请求"，不验证"被测系统返回了正确结果"。

  没有：
    - API 契约验证（response schema 是否符合 OpenAPI）
    - 数据一致性验证（API 返回的 user_id 在 DB 中确实存在）
    - 交叉验证（两个独立 API 返回的同一数据是否一致）

  所以 Oracle 是"信任被测系统不会全错"。
  但真实 Bug 经常就是"被测系统全错了"。
```

---

## 3. Layer Comparator 审计

### 3.1 三层比较是否能够判断真实原因？

**不能。它只能枚举可能原因，不能缩小范围。**

```text
当前 Comparator 输出：
  possible_causes: [
    "A) AI 推测了错误文案",
    "B) 被测系统 UI 文案确实为 XXX",
    "C) 被测系统 UI 文案已变更"
  ]

  三个可能原因覆盖了所有可能性。
  但哪一个是真的？Comparator 不知道。

  这意味着：Comparator 的判断没有信息量。
  A/B/C 全列出来 = 什么都没说。
```

### 3.2 是否存在大量只能输出"需要人工判断"的情况？

**是的。当前 100% 的 divergences 都标记为 `requires_human: True`。**

```text
  Demo 中 3/5 条案例有 divergences → 全部标记 "需人工判断"
  API 测试中 0 条自动判定

  ATP 的自动化判定率 = 0%。
  100% 的 divergences 需要人来看。

  如果 100% 需要人来看，ATP 的增量价值是什么？
```

### 3.3 如果不能判断，ATP 的价值在哪里？

```text
当前的答案是 "ATP 提供了结构化的问题描述"。

但：
  - Allure Report 提供结构化报告
  - Postman 提供请求/响应对比
  - Grafana 提供趋势分析

  这些工具都是免费的。

  ATP 的付费理由是什么？
```

---

## 4. UIEvidence 接入审计

### 4.1 外部 UI 测试结果提供什么证据？

**当前只提供：case_id + status + assertions(target, type, expected, actual)**

```text
  UI 测试说 "assert_text(login-submit-btn, '请输入账号') → FAIL"
  
  ATP 看到：target=login-submit-btn, expected=请输入账号, actual=登录
  
  Comparator 说：目标可能是错的（button vs error元素）

  但 Comparator 不知道：
    - 这个 button 当前在页面上是否可见？
    - 这个 button 的文本是否就是 "登录"？
    - 页面上是否有 toast 元素？
    - toast 元素的内容是什么？
    - 被测系统是否真的触发了校验逻辑？

  没有这些信息，Comparator 的判断就是猜。
```

### 4.2 只有 pass/fail 是否足够？

**不够。严重不够。**

```text
  UI 测试 PASS 可能意味着：
    A) 断言正确，业务正确
    B) 断言碰巧匹配（假通过）
    C) 断言被跳过
    D) 超时后默认为 PASS

  ATP 收到的只是一个 "passed" 字符串。
  无法区分 A/B/C/D。

  这意味着：即使 Comparator 说 "aligned"，
  也可能是假通过 — 只是 ATP 不知道而已。
```

### 4.3 缺少 DOM、截图、trace 是否导致误判？

**是的。**

```text
  真实 UI 测试失败分析需要：
    - DOM snapshot（定位为什么找不到元素）
    - 截图（确认页面状态）
    - trace（确认操作序列）
    - 网络日志（确认 API 调用是否发出）

  ATP 只有：{type: "assert_text", target: "btn", expected: "x", actual: "y"}

  这就好比医生只看体温就说"你生病了"。
  没有其他诊断数据，判断的准确性期望值很低。
```

---

## 5. AI TestIntent 审计

### 5.1 Requirement Parser 生成错误 intent 怎么办？

```text
当前 Mock 模式：关键词匹配 "错误/失败/拒绝" → negative

输入："用户输入错误密码后，点击忘记密码链接重置密码"
  → Mock 分类：negative（因为有"错误"）
  → 实际意图：positive（测试忘记密码流程）

输入："验证码错误时不允许登录"
  → Mock 分类：negative
  → 但验证码功能可能根本不存在

  AI 分类错误 → Intent 错误 → API 测试验证了错误的场景
  → 整个链路输出的是正确回答错误问题的结果
```

### 5.2 人工 Review 是否掩盖 AI 错误？

```text
当前设计中，Requirement Parser → TestIntent → Human Review。

但在 Demo 和 API 端点中，没有 Human Review 环节。
直接 Parser → Runner。

如果没有人工 Review：
  - AI 错误不会被拦截
  - Layer Comparator 基于错误的 Intent 做对比
  - 整个报告的基础就是错的

如果有人工 Review：
  - 每次都要人看一遍
  - 和人工写测试用例的工作量差不多
  - ATP 的价值再次被削弱
```

---

## 6. 工程落地审计

### 6.1 接入真实 UI Runner 后是否需要修改现有测试平台？

```text
当前 ATP 跑 API 测试 — 独立链路，不影响现有平台。

但要接入真实 UI 测试结果：
  1. Playwright 跑完 → 产生结果 JSON
  2. 结果 JSON 需要包含 intent_name（目前没有）
  3. 需要改造现有 UI 测试框架，在每个 test case 中注入 intent_name
  4. 或者写一个 post-processor 做匹配

  无论哪种方式，都需要修改现有测试基础设施。
  "不改已有代码"的承诺到此为止。
```

### 6.2 数据链路是否闭环？

```text
当前链路：

  Requirement → Parser → Intent → API Runner → Result
                                              ↓
  Playwright 测试（独立运行）→ 结果 JSON ──────┘
                                              ↓
                                     Layer Comparator
                                              ↓
                                         Report

断点：API 测试和 UI 测试是两个独立流程，没有人保证它们测的是同一件事。
      Parser 生成的 Intent 和 UI 测试的 Intent 来自不同来源。
      匹配全靠名字和 scenario type（脆弱）。
```

---

## 7. Demo 可信度审计

### 7.1 24 条历史数据是否具有代表性？

**具有代表性——但代表的是"ATP UI 测试生成的质量差"，不是"AI 自动化测试行业的普遍问题"。**

```text
24 条案例全部来自 ATP 自己的 UI 生成链路。
生成质量差 ← ATP 的 Prompt/Compiler/Gate 的问题。

不能据此推论"所有 AI 自动化测试都有 40% 假通过"。
ATP 的审计数据证明的是 ATP v2.x 的质量问题，不是行业问题。
```

### 7.2 是否存在为了证明 ATP 有价值而选择样本的问题？

**是的。**

```text
Demo 中的 5 条代表性案例：
  - 3 条是"零断言"（极端案例，任何平台都会发现）
  - 2 条是"断言目标错误"（需要 Element Role 才能检测，但 ATP 当前没有）

  没有包含的案例类型：
  - "断言完全正确，但被测系统有 Bug 导致假失败" → 这种 ATP 检测不到
  - "API 结果错误，UI 断言正确" → ATP 会报告 API divergence，但真正的问题是 API
  - "三层全部正确" → ATP 没有增加价值

  选择的样本偏向于"ATP 擅长的场景"。
```

---

## 8. 最终判定

### A. 当前设计最大 3 个致命问题

1. **Oracle 没有验证机制**
   - API 结果可能全错，DB 数据可能是空的，Spec 可能写错了
   - 三层全错时 ATP 检测不到任何问题
   - Comparator 标记 "aligned" — 这是最可怕的误判

2. **100% 判定需要人工**
   - `requires_human: True` 是所有 divergences 的默认值
   - ATP 没有任何自动判定能力
   - 价值退化为一层结构化报告
   - 竞品是 Allure/Postman/Grafana — 全部免费

3. **UIEvidence 信息不足**
   - 只有 pass/fail + 断言文本
   - 没有 DOM/screenshot/trace/网络日志
   - Comparator 在信息严重不足的情况下做判断
   - 准确率不可预期

### B. 必须修复的问题

- API Oracle 需要 Spec 交叉验证（不能假设 API 正确）
- `requires_human: True` 不能是 100% — 需要在部分场景下给出确定性判断
- UI Evidence 至少需要 DOM snapshot

### C. 可以接受的问题

- Requirement Parser 基于关键词（Mock 模式正确率约 80%，可接受）
- Demo 样本选择偏差（Demo 本身就是展示最佳案例，不是论文）
- 场景匹配依赖 intent_name/scenario（工程可优化）

### D. 是否允许进入真实系统接入阶段？

**不允许。**

原因：
1. 致命问题 1（Oracle 无验证）和 2（100%需人工）在当前阶段无法通过增加代码解决。它们需要架构层面的修正——增加 Oracle 交叉验证和自动判定规则。
2. 当前进入真实系统接入，用户的第一反应会是"这不就是一个报告工具吗"，然后放弃使用。产品在达到"至少能自动判定 30% 的 divergences"之前，不应该接真实用户。
