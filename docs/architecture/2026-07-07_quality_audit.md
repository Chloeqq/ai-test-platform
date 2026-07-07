# AI 测试资产质量审计报告

> **日期:** 2026-07-07
> **审查范围:** `mall-web-login-auth-fn-ai-0001` (27 个测试点，完整生成链路)
> **质量门禁:** 17 条规则 (RULE_001 ~ RULE_017)

---

## 1. 当前质量链路

```
Requirement (requirement.yaml)
  │  业务目标 + 关键流程 + 验收点
  ▼
Requirement Parser (orchestrator AI)
  │  识别 intent: functional/negative/boundary/security/format/interaction_exception
  ▼
Intent Store (preview_store)
  │  27 intent_ids: intent-01 ~ intent-27
  ▼
Test Point Generator (save_service → build_point → structured_steps_from_candidate)
  │  DSL V1.1 steps + steps_hint + data + involved_elements
  ▼
Quality Gate (17 rules)
  │  ⚠️ 审核状态: 4 approved, 23 pending (但有质量问题的点被 approved)
  ▼
Test Case Generator (generate_case_service → orchestrator AI)
  │  编译为可执行 DSL → 写入 test_cases.script_code
  ▼
Execution Runner (web-playwright-python)
  │  执行 + Allure 报告
  ▼
Result
```

---

## 2. 问题清单

| ID | 问题 | 等级 | 影响范围 | 证据 | 建议 |
|----|------|------|---------|------|------|
| Q-001 | 23/27 测试点使用弱断言 `assert_url:#/login` | 🔴 P0 | 全部 negative/boundary 场景 | 23个点只检查 URL 停留,不检查错误文案 | 编译层修复: assert_text 替代 assert_url |
| Q-002 | intent-01 零断言已通过审核 | 🔴 P0 | 最核心的 happy path | approved 但 steps=[input,input,click], 无 assertion | 质量门禁必须拦截, 审核流程需严格化 |
| Q-003 | intent-02 零断言已通过审核 | 🔴 P0 | 登录态保持场景 | approved 但无断言验证 | 同上 |
| Q-004 | 5 个 candidate_step 占位符 | 🟡 P1 | 3 个测试点 | "输入URL并访问"/"点击退出按钮" 不可执行 | AI 无法映射到页面元素时降级,需人工替换 |
| Q-005 | 4 个已审核点绕过质量门禁 | 🟡 P1 | RULE_003/008 失效 | approved 点中有弱断言/零断言 | 审核流程应展示 gate 决策, 审批时需说明理由 |
| Q-006 | element_code 映射缺失 | 🟡 P1 | 24/27 点 | `username_input` vs `login-username-input` 不一致 | 已在编译层使用 element_binding,需重新保存资产 |
| Q-007 | 11 个 input step 的 value=null | 🟡 P1 | boundary 场景 | 实际值只在 raw_text 中描述, 不可执行 | 需要从 steps_hint 回填具体值 |
| Q-008 | 23 个点 pending_review | 🟢 P2 | 这些点无法生成用例 | 需人工审核后才能进入 generate 流程 | 按类型分批审核 |

---

## 3. 质量门禁有效性审计

### 规则覆盖矩阵

| Rule | 名称 | 是否应拦截当前资产? | 实际是否拦截? |
|------|------|-------------------|-------------|
| RULE_003 | NEGATIVE_WEAK_ASSERTION | ✅ 应拦截 23 个 weak 点 | ❌ 审核绕过 |
| RULE_008 | MISSING_ASSERTION | ✅ 应拦截 3 个零断言点 | ❌ 审核绕过 |
| RULE_006 | UNKNOWN_ELEMENT | ✅ 应拦截 24 个旧 element_code | ❌ 数据是编译前的,gate 在编译后 |
| RULE_012 | TITLE_STEP_MISMATCH | ⚠️ 部分拦截 | - |
| RULE_016 | AI_HALLUCINATION | ✅ 应拦截 candidate_step | 待验证 |

**结论:** 质量门禁规则是有效的（RULE_003/008/006 都能命中问题），但审核流程允许人工绕过 gate 决策。4 个 approved 点中没有一个符合质量标准。

---

## 4. Requirement Traceability Matrix

```
Requirement: "平台用户身份验证登录功能"
  │
  ├── 验收点: 正常登录 → intent-01 (functional) APPROVED ⚠️ NO ASSERT
  ├── 验收点: 刷新保持登录 → intent-02 (functional) APPROVED ⚠️ NO ASSERT
  ├── 验收点: 空账号提示 → intent-04 (negative) APPROVED ⚠️ NO ASSERT
  ├── 验收点: 空密码提示 → intent-05 (negative) PENDING
  ├── 验收点: 错误账号 → intent-06~09 (negative) PENDING
  ├── 验收点: 错误密码 → intent-10~14 (negative) PENDING
  ├── 验收点: 账号锁定 → intent-15~20 (boundary) PENDING
  ├── 验收点: 密码可见性 → intent-26/27 (functional) APPROVED ⚠️ NO ASSERT
  ├── 验收点: 未登录拦截 → intent-03 (security) PENDING
  ├── 验收点: 退出登录 → intent-24/25 (functional) PENDING ⚠️ CANDIDATE_STEP
  └── 格式校验 → intent-21~23 (format) PENDING

映射完整度: 27/27 ✅ (每个验收点都有测试点)
可追溯性: 27/27 ✅ (每个测试点都有 unique source_id)
```

---

## 5. AI 幻觉风险评估

| 风险 | 当前状态 | 实际发现 |
|------|---------|---------|
| 虚构 API | 无 API schema 约束 | ❓ 无 API 相关测试点 |
| 虚构页面元素 | RULE_006 应拦截 | 24 个点使用旧 element_code |
| 无法执行步骤 | candidate_step | 5 个占位符 |
| 重复 case | IDEM-001 幂等 | 无重复 |
| 数据不一致 | RULE_001/002/010 应拦截 | 待编译后验证 |

---

## 6. 推荐改进路线

### 🔴 立即修复

1. **Q-001**: 编译层修复 — `structurer.py` 中 `_build_expected_assertions` 对 negative/boundary 场景应生成 `assert_text` 而非 `assert_url`
2. **Q-002/003**: 重新审核 intent-01/02 — 补 assertion 后重新生成
3. **Q-005**: 审核流程 — 审批时必须展示 gate 决策结果, 不能绕过

### 🟡 短期优化

4. **Q-004**: candidate_step 人工替换为可执行步骤
5. **Q-006**: 重新保存资产，使用 element_naming 规范 code
6. **Q-007**: boundary 场景的输入值从 steps_hint 回填

### 🟢 长期演进

7. 质量门禁评分制 — gate_score < 阈值时阻止进入执行
8. AI 幻觉自动检测 — RULE_016 增强 element 存在性交叉验证
