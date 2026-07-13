# 质量闭环最终架构审计

> **日期:** 2026-07-07 | **角色:** 反方架构审查者
> **范围:** Requirement → AI → Structurer → Gate → Review → Execute 全链路

---

## A. Quality Gate 绕过路径检查

| 路径 | 经过编译器? | 经过 Gate? | 可绕过? |
|------|-----------|-----------|--------|
| `POST /test-point-assets/save` (AI生成) | ✅ `build_point` | ✅ quality_report | 否 |
| `PUT /test-point-assets/{id}` (编辑) | ✅ `_steps_from_candidate` | ✅ quality_report | 否 |
| `POST /test-point-assets` (upsert) | ✅ `_manual_point_from_candidate` | ✅ quality_report | 否 |
| 直接写文件 | N/A | ❌ | **理论路径, 无 API** |

**结论:** 所有 API 入口都经过编译器。无已知绕过路径。

---

## B. quality_report vs quality_gate 一致性

| 维度 | quality_report | quality_gate |
|------|---------------|-------------|
| 运行时机 | 保存后 (GET 详情页) | 生成用例时 |
| 输入 | asset metadata (plan.points) | case_yaml (编译后 DSL) |
| 规则数 | 3 (零断言/弱断言/requires_review) | 17 |
| 是否可能不一致 | ⚠️ 是 | ⚠️ 是 |

**分歧场景:** quality_report=PASS 但 quality_gate=FATAL — 当断言存在但 element_code 不匹配时。

**风险等级:** 🟡 中。quality_report 是"保存阶段质量指示器"，quality_gate 是"生成阶段质量门禁"。两者覆盖不同阶段，分歧是设计的必然——quality_gate 有更多信息（编译后的 DSL + page_object）。

**缓解:** P0-4 反方审查已记录此设计决策。不建议合并——它们是互补的。

---

## C. 编译器入口统一性

所有路径均指向同一编译器:

```
AI 生成路径:     save_service → build_point → structured_steps_from_candidate
编辑保存路径:    _manual_point_from_candidate → _steps_from_candidate → structured_steps_from_candidate
手动创建路径:    同上
```

✅ 编译器入口已统一。

---

## D. 剩余硬编码

| 位置 | 硬编码 | 风险 | 是否 Blocking? |
|------|--------|------|---------------|
| `resolver.py:32` | `_FALLBACK_LOGIN_PAGE_MAP` (37条映射) | 🟡 仅 DB+YAML 都失败时使用 | ❌ 生产不应触发 |
| `login_password_visibility.py:25` | `return "login"` | 🟢 Hook 的 page_code 属性 | ❌ Hook 注册表已解耦 |
| `constants.py` | `LOGIN_PASSWORD_*` (4个常量) | 🟢 Hook 内部使用, 已有 @deprecated | ❌ 标记为 Phase 3 移除 |
| `preview_store.py:122` | `_text(project) or "mall"` | 🟡 预览快照默认项目 | ❌ 快照存储不影响编译 |

**结论:** 无新增阻塞性硬编码。剩余的是已知的 @deprecated 标记或设计内常量（Hook 专属）。

---

## E. 重复质量判断逻辑

| 逻辑 | 位置1 | 位置2 | 重复? |
|------|-------|-------|------|
| 零断言检测 | `_build_quality_report` (view) | `_build_expected_assertions` (return count) | ⚠️ 是 |
| requires_review | `point_builder` (设置) | `_build_quality_report` (读取) | ✅ 复用 |
| Gate decision | `_build_quality_report` | `CaseQualityGate.evaluate()` | ⚠️ 不同阶段, 不同输入 |

**P0-4 已知:** `_build_quality_report` 在 view 层的评分逻辑与 domain 层 `CaseQualityGate` 重复概念。中期计划提取到 domain 层。

---

## F. AI 假成功风险

| 风险 | 现状 | 是否有保护? |
|------|------|-----------|
| 步骤全部生成但断言为 assert_url | ✅ P0-1 修复后不再发生 | negative/boundary 强制 assert_text |
| 编译器无法识别任何 assertion token | ✅ P0-2 修复 | requires_review=True + assertion_missing |
| 人工审核绕过 Gate | ✅ P1-2 修复 | 零断言点 HTTP 422 不可批准 |
| quality_report 显示 PASS 但实际不可执行 | ⚠️ element_code 不匹配时 | quality_gate 在生成阶段二次检查 |
| candidate_step 进入执行 | ✅ P0-5 修复 | 编译后不再生成 candidate_step |

---

## 最终裁决

```
═══════════════════════════════════════════════
可以进入下一阶段开发: YES
═══════════════════════════════════════════════
```

### 保留设计 (5)

1. ✅ 编译后 Gate + 保存后 quality_report 双重检查
2. ✅ PageHook 注册表模式 (可扩展)
3. ✅ STRONG_ASSERTION_REQUIRED_TYPES frozenset (数据驱动)
4. ✅ ElementResolver 统一元素解析
5. ✅ preview_id 幂等键

### 已知风险 (3, 均非 Blocking)

| 风险 | 等级 | 说明 |
|------|------|------|
| quality_report ≠ quality_gate | 🟡 | 不同阶段不同输入, 设计必然 |
| `_build_quality_report` 在 view 层 | 🟡 | 中期提取到 domain 层 |
| `_FALLBACK_LOGIN_PAGE_MAP` | 🟢 | 仅三重回退最后一层, 生产不触发 |

### P0/P1/P2 分类

| 等级 | 数量 | 状态 |
|------|------|------|
| P0 | 0 | ✅ 无阻塞问题 |
| P1 | 2 | 🟡 已知技术债务, 不阻塞 |
| P2 | 0 | ✅ |
