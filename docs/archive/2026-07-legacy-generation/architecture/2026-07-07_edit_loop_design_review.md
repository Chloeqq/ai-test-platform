# 编辑闭环修复设计评审

> **日期:** 2026-07-07 | **状态:** ✅ 已实施 (c802738) — 方案 A, 2 文件 +34/-69 行

---

## 方案比较

### 方案 A: 前端发送 raw text → 后端编译 ✅ 推荐

**流程:**
```
前端: { steps_text, expected, intent_type, ... }
  ↓
PUT /api/test-point-assets/{id}
  ↓
后端: selected_candidates → build_point() → DSL steps → save
```

**复用已有机制:**
- `save_test_point_assets_service.execute()` 已支持 `selected_candidates` 参数
- `build_point()` 已能编译 candidate 为 DSL
- 无需新增编译逻辑

**数据一致性:** ✅ 编译逻辑集中在后端, 单点控制
**架构职责:** ✅ 前端负责展示和采集, 后端负责编译
**对现有代码影响:** 中。前端 payloadPoint() 需改, 后端 upsert 增加编译路径
**未来扩展:** ✅ AI 编辑、批量编辑均可复用同一编译路径

### 方案 B: 后端检测 candidate_step 重新编译 ❌ 不推荐

**流程:**
```
后端收到 incoming_points → 检测是否为 candidate_step → 重新编译
```

**致命缺陷:**
1. **无法区分用户编辑的 DSL 和 AI 生成的 candidate_step** — 如果用户写了正确的 `action: "input"` 步骤, 重新编译会覆盖
2. **脆弱的检测逻辑** — 依赖 `action == "candidate_step"` 的判断, 任何改动都可能导致检测失败
3. **用户编辑丢失** — 用户可能花了 10 分钟手动编写 DSL, 后端重新编译后全部丢失

### 方案 C: edit_mode 标记 ❌ 不推荐

**流程:**
```
前端: { edit_mode: "manual" | "recompile", points: [...] }
```

**过度设计:**
- 当前不存在 "手动编写 DSL" 的用户场景 — 所有用户编辑都是改 raw text
- 新增 API 字段增加维护负担
- AI 集成时可能选错模式
- YAGNI (You Aren't Gonna Need It)

---

## 推荐: 方案 A

### 为什么方案 A

1. **复用已有架构**: `build_point()` 已完整实现 candidate → DSL 编译
2. **最少改动**: 前端 payloadPoint() 改输出格式, 后端 upsert 增加编译路径
3. **架构清洁**: 编译逻辑始终在后端, 前端不知道 DSL 结构
4. **可测试**: 编译单元已有 46 个测试

### 后端改动 (facade_test_point_assets.py)

```python
# 当前:
if incoming_points:
    points = incoming_points  # 直接替换, 绕过编译

# 改为:
if incoming_points:
    points = incoming_points  # 保留 (用户可能手动编辑 DSL)
elif candidates_from_edit:    # 新: 前端发送 raw text candidates
    points = [build_point(c, index=i) for i, c in enumerate(candidates_from_edit)]
```

**关键: `incoming_points` 和 `candidates_from_edit` 互斥。** 前端发送 raw text 时用 `selected_candidates`, 发送 DSL 时用 `points`。

实际上更简单: `upsert_test_point_asset` 已经支持 `selected_candidates` 参数。前端只需:
1. 不再调用 `payloadPoint()` 生成 `action: "candidate_step"` points
2. 改为直接传 `selected_candidates` (raw text)
3. 后端已有编译路径, 无需修改

### 前端改动 (TestPointAssetEditPage.tsx)

1. **删除 `payloadPoint()`** 中的 `action: "candidate_step"` 硬编码
2. **传 `selected_candidates`** 而非预编译的 `points`
3. **删除 `LOGIN_INVOLVED_ELEMENT_ALIASES`** 硬编码
4. **删除 `page !== "login"`** 条件分支
5. **`involvedElementsText`** 直接传原始文本, 让后端 `resolve_involved_element_codes` 处理

---

## 硬编码消除方案

### 当前硬编码

```typescript
const LOGIN_INVOLVED_ELEMENT_ALIASES = {
  "用户名输入框": "username_input",  // ← 旧 element_code, 错误!
  ...
};

if (page !== "login") {  // ← 页面判断
    return rows;
}
// 只有 login 页用硬编码映射
```

### 修复: 全部删除

**前端不再做元素映射。** 发送原始中文元素名, 后端 `resolve_involved_element_codes(resolver)` 通过 `ElementResolver` 从 DB/alias_map 解析。

**已有后端能力:**
- `GET /api/page-objects/{page_code}` → 返回 elements (含 `aliases_json`, `element_name`)
- `ElementResolver(alias_map).resolve(chinese_name)` → element_code

前端已调 `getTestPointAsset()` 加载 asset 数据。asset 的 `involved_elements` 已是标准 element_code。编辑页的 `normalizeInvolvedElements` 应该信任后端, 不再自己做映射。

**前端只需:**
1. 展示已有 `involved_elements` (标准 code)
2. 用户可编辑为中文名或 code
3. 发送时不做转换 → 后端 ElementResolver 处理

---

## 修改范围

| 文件 | 改动 | 行数 |
|------|------|------|
| `TestPointAssetEditPage.tsx` | 删除 payloadPoint() candidate_step 硬编码; 删除 LOGIN_INVOLVED_ELEMENT_ALIASES; 删除 page==="login"; 修改 submitEditor 传 selected_candidates | ~30 行 |
| `facade_test_point_assets.py` | upsert 时若收到 raw candidates 则调用 build_point() 编译 | ~15 行 |

**仅 2 个文件, ~45 行。**

---

## 风险点

| 风险 | 等级 | 缓解 |
|------|------|------|
| 编辑后编译断言仍不符合预期 | 中 | quality_report 会展示编译结果 |
| 用户手动写的 DSL 被覆盖 | 低 | incoming_points 优先于编译 |
| 旧前端缓存 | 低 | API 响应不变, 前端版本更新即可 |

---

## 测试场景

| Case | 输入 | 预期 |
|------|------|------|
| 1 | 编辑 expected: "页面提示'请输入账号'" | 编译后生成 assert_text |
| 2 | 编辑 steps: "在用户名输入框输入admin" | 编译后生成 input 步骤 |
| 3 | 编辑后全为 candidate_step raw text | 编译后全部解析为 DSL |
| 4 | 发送已编译的 points | 保留, 不重新编译 |
| 5 | element 名为中文 | 后端 ElementResolver 解析 |
| 6 | element 名为 code | 直接使用 |

---

## 结论

```
推荐: 方案 A — 前端发送 raw text, 后端编译
改动: 2 文件, ~45 行
不推荐: B (检测不可靠), C (过度设计)
```
