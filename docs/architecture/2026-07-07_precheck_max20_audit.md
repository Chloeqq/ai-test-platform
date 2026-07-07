# precheck max=20 限制审计与方案评审

日期：2026-07-07

## 背景

AI 解析可生成 28 个测试点，但前端限制最多选择 20 个，导致无法保存完整测试资产。

## 现状：限制全景图

```
selected_intents(28)
    │
    ▼
┌─ precheck_selected_intents_service.py:74 ──┐
│  if len(candidates) > 20  ← 【唯一瓶颈】   │
│  → 422 "max size 20"                       │
│  处理内容：纯本地校验循环，无LLM/DB/网络    │
└────────────────────────────────────────────┘
    │
    ▼
┌─ save_test_point_assets_service.py:125 ────┐
│  if len(candidates) > 200  ← MAX_CANDIDATES│
│  → structurer per candidate                │
│  → DB 事务写入                              │
└────────────────────────────────────────────┘
    │
    ▼
┌─ generate_case_service.py:175 ─────────────┐
│  if len(candidates) > 200  ← MAX_CANDIDATES│
│  → DSL 编译 per candidate                   │
│  → 用例生成                                 │
└────────────────────────────────────────────┘
```

**核心发现：precheck 的 20 是整个链路中唯一的小数字，所有下游服务都使用 200。**

## max=20 的历史原因

| 维度 | 结论 |
|------|------|
| 引入时间 | 2026-05-06，commit `80ce27c` "Refactor platform workflows and UI handling" |
| 引入方式 | 随文件首次创建时硬编码，无讨论、无测试依据、无 commit message 说明 |
| 是否因 LLM token 限制 | 否 — precheck 不调用 LLM |
| 是否因 structurer 性能 | 否 — precheck 不调用 structurer |
| 是否因 preview snapshot 大小 | 否 — precheck 只读 snapshot，不写入 |
| 是否因 DB 写入限制 | 否 — precheck 不写 DB（纯查询） |
| 是否因超时 | 否 — precheck 只做本地校验循环，无网络调用 |

**结论：`20` 是创建时随手设置的保守值，没有技术依据。**

## 提升到 50/200 的风险评估

| # | 环节 | 处理内容 | 28→50→200 风险 |
|---|------|---------|----------------|
| 1 | precheck | 逐 candidate 做元素名→code 映射 + 必填字段校验 | 安全 — 纯 Python 循环，O(n) 本地计算 |
| 2 | save (structurer) | 逐 candidate 调用 `build_point` → `structured_steps_from_candidate` → 自然语言→DSL 步骤 | 安全 — 已在现有代码中允许 200 |
| 3 | DB 写入 | `sync_test_points` + `save_asset` 同一事务 | 安全 — 200 条 JSON 事务，PG 完全承受 |
| 4 | generate_case | 逐 candidate 编译 DSL + 生成用例 | 安全 — 已用 `MAX_CANDIDATES=200` |

**不存在 LLM token 问题**：precheck 不调用 LLM。save 中的 structurer 也不调用 LLM（规则引擎）。只有上游 `requirement-parser-agent` 才调用 LLM，且它已成功解析 28 个 intent。

## 方案对比

### 方案 A：直接把 20 → 200（推荐）

```
precheck_selected_intents_service.py:
  if len(normalized_candidates) > 20  →  > _c.MAX_CANDIDATES

前端 AiGenerationPage.tsx:
  删除 MAX_GENERATE_SELECTED = 20
  删除 slice(0, MAX_GENERATE_SELECTED)
  删除 toggleCandidate 长度检查
  删除 checkbox disabled 逻辑
  更新 UI 文案（"选择前 20 条预校验"→"全选预校验"、X/20→X）
```

| 维度 | 评估 |
|------|------|
| 修改量 | 小：后端 1 行 + 前端 ~10 行删除 |
| 风险 | 极低：复用已验证的 `MAX_CANDIDATES=200` |
| MVP 原则 | 最小改动，对齐现有约束 |
| 一致性 | precheck/save/generate 三处统一为 `MAX_CANDIDATES=200` |

### 方案 B：配置化 MAX_SELECTED_INTENTS

| 维度 | 评估 |
|------|------|
| 修改量 | 中：新增配置项 + 环境变量 + 读取逻辑 |
| 风险 | 低 |
| MVP 原则 | 过度工程：当前没有多场景需要不同限制 |

### 方案 C：自动 batch 拆分

| 维度 | 评估 |
|------|------|
| 修改量 | 大：需要 batch 逻辑、分组合并、错误聚合、进度追踪 |
| 风险 | 高：引入新的状态管理复杂度，DB 事务需重新设计 |
| MVP 原则 | 严重过度工程：200 以内单个请求完全够用 |

## 推荐方案

**方案 A**，理由：

1. `20` 没有存在的技术理由 — 不是 LLM token、不是 timeout、不是 DB 限制、不是性能瓶颈
2. 对齐现有约束 — 所有下游服务已经用 `MAX_CANDIDATES=200`
3. 最小改动 — 后端 1 行替换，前端删除死代码
4. 零风险 — precheck 的循环体内没有任何 I/O，28→200 的 CPU 开销可忽略
5. 符合 MVP 原则 — 不引入新概念、新常量、新配置

## 涉及文件

| 文件 | 改动 |
|------|------|
| `apps/web-ui-service/app/services/workbench_generation_api/constants.py` | 无改动（`MAX_CANDIDATES=200` 已存在） |
| `apps/web-ui-service/app/services/workbench_generation_api/precheck_selected_intents_service.py:74` | `20` → `_c.MAX_CANDIDATES` |
| `apps/web-ui-service/frontend/src/pages/AiGenerationPage.tsx` | 删除 `MAX_GENERATE_SELECTED` 及所有引用 |

## 决定

- [ ] 方案 A：直接改 20→200
- [ ] 方案 B：配置化
- [ ] 方案 C：自动 batch
- [ ] 不实施
