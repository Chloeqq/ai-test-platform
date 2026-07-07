# Phase 4: Quality Gate 接入 Generate/Execute 阻断 — 反方审计

日期：2026-07-07

## 1. 当前链路图

```
Requirement → AI Parser → Intent → TestPointAsset → Structurer → Quality Report
                                                                      │
                                                                      ▼ (仅展示，不阻断)
┌─ Generate ──────────────────────────────────────────────────────┐
│  POST /test-point-assets/batch/generate-cases                   │
│  → batch_generate_cases_from_test_point_assets                  │
│  检查: review_status == "approved"                              │
│  缺少: quality_report.decision / zero_assertion_count           │
│  缺少: candidate_step / assertion_missing                       │
└────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─ Execute ───────────────────────────────────────────────────────┐
│  POST /api/workbench/run                → run_case              │
│  POST /api/workbench/runs/{id}/rerun    → rerun_case            │
│  检查: case_id 存在 + script_code 非空                          │
│  缺少: quality_report / review_status / 任何 Gate               │
└────────────────────────────────────────────────────────────────┘
```

## 2. 发现的绕过路径

### 2a. Generate Case — 主入口无 Quality Gate 阻断

- **文件**: `facade_test_point_assets.py:1196`
- **方法**: `generate_cases_from_test_point_assets`
- **当前行为**: 逐 point 过滤 `review_status == "approved"`，直接生成 case
- **风险**: `review=approved` 但 `quality_report.decision=REJECT` / `zero_assertion_count>0` 的 point 可生成
- **最小修复点**: line 1266 (point filter) 前插入 quality_report 检查

### 2b. Generate Case — 底層 Service 无 Gate

- **文件**: `generate_case_service.py:116`
- **方法**: `execute`
- **当前行为**: 直接遍历 candidates，无条件生成
- **风险**: 如果被其他入口调用（非 batch 路径），完全无 Gate
- **最小修复点**: line 213 (for candidate loop) 前插入 per-candidate 检查

### 2c. Execute — run_case 无 Gate

- **文件**: `facade_test_point_assets.py:1452`
- **方法**: `run_case`
- **当前行为**: 仅检查 `case_id` 存在 + `script_code` 非空
- **风险**: 质量不合格的 case 直接执行，无人拦截
- **最小修复点**: line 1494 (script_code check 之后) 插入 source_asset 质量检查

### 2d. Execute — rerun 无 Gate

- **文件**: `workbench_runs.py:59`
- **方法**: `rerun_case`
- **当前行为**: 直接重跑已存在的 run
- **风险**: 历史 case 重跑无任何 Gate
- **最小修复点**: 同上，查 source asset 的 quality_report

### 2e. Review Approve — Gate 不完整

- **文件**: `facade_test_point_assets.py:401`
- **方法**: `batch_review_test_points`
- **当前行为**: lines 440-451 仅检查 `assertion_missing`；不检查 `candidate_step`、steps 零断言、`quality_report.decision`
- **风险**: `candidate_step` 的 point 可被 approve → 生成 → 执行
- **最小修复点**: line 443 扩展检查条件

## 3. 实施设计

### 3.1 最终修改文件列表

| # | 文件 | 改动 | 行数 |
|---|------|------|------|
| 1 | `app/services/workbench_asset_views.py` | 新增 `get_quality_gate_violations()` + `enforce_quality_gate()` | ~40 |
| 2 | `app/api/workbench/facade_test_point_assets.py` | 3 处插入 enforcement 调用 | +15 |
| 3 | `tests/unit/test_quality_gate_enforcement.py` | 新增测试 | ~80 |
| 4 | `shared_backend/quality_gate/` | **无改动**（复用现有 `Decision`/`Severity` 枚举值语义） | 0 |

### 3.2 每个文件修改位置

**文件 1: `workbench_asset_views.py`**

在 `_build_quality_report` 之后新增两个函数：

| 函数 | 职责 |
|------|------|
| `get_quality_gate_violations(asset)` | 调用 `_build_quality_report`，返回 violation 列表 |
| `enforce_quality_gate(asset, *, action)` | 调用 `get_quality_gate_violations`，存在 block 级 violation 时抛 422 |

**文件 2: `facade_test_point_assets.py`**

| 行 | 方法 | 插入位置 | action | 条件 |
|----|------|---------|--------|------|
| ~1266 | `generate_cases_from_test_point_assets` | `approved_points = []` 之前，加载 asset 后 | `"generate"` | 始终 |
| ~1494 | `run_case` | `script_code` 非空检查之后 | `"execute"` | 仅当 `source_asset_id` 可追溯 |
| ~443 | `batch_review_test_points` | 现有 `assertion_missing` 检查处扩展 | `"approve"` | next_status=="approved" |

### 3.3 函数设计

**`get_quality_gate_violations(asset: dict) -> list[dict]`**

返回 violation 列表，每个 violation：

```python
{
    "code": str,        # "zero_assertion" | "unprocessed" | "quality_warning" | "candidate_step"
    "severity": str,    # "block" | "review"
    "message": str,     # 人类可读
    "intent_ids": [str], # 涉及的 point ID 列表（来自 per_point）
}
```

**Violation 判定规则**（不依赖单一 `decision` 字段，逐项检查）：

| # | 条件 | severity | code |
|---|------|----------|------|
| 1 | `zero_assertion_count > 0` | `block` | `zero_assertion` |
| 2 | `unprocessed_count > 0`（candidate_step + 无断言）| `block` | `unprocessed` |
| 3 | `quality_warnings` 非空 | `review` | `quality_warning` |
| 4 | `candidate_step_count > 0` 且 `unprocessed_count == 0` | `review` | `candidate_step` |

**`intent_ids` 来源**：从 `per_point` 中筛选对应问题类型的 point ID。

**`enforce_quality_gate(asset: dict, *, action: str) -> None`**：

```python
def enforce_quality_gate(asset: dict, *, action: str) -> None:
    """action ∈ {"generate", "execute", "approve"}"""
    violations = get_quality_gate_violations(asset)
    blocking = [v for v in violations if v["severity"] == "block"]
    if blocking and action in ("generate", "execute"):
        raise HTTPException(422, detail={
            "code": "quality_gate_blocked",
            "message": f"质量门禁阻断，无法{action}。",
            "violations": blocking,
        })
    if blocking and action == "approve":
        raise HTTPException(422, detail={
            "code": "quality_gate_approve_blocked",
            "message": "存在阻断项，无法批准。请先修复后再审核。",
            "violations": blocking,
        })
```

**Execute 追溯逻辑**（在 `run_case` 调用处）：

```python
# 仅当 case 可追溯到 source_asset 时才执行 Gate
source_asset_id = _source_identity_from_case(case_for_run)[0]
if source_asset_id:
    asset = workbench_asset_service.load_test_point_asset_with_root(
        project, source_asset_id, state_root=constants.TEST_POINTS_ROOT)
    if asset:
        enforce_quality_gate(asset, action="execute")
# source_asset_id 为空 → 跳过 Gate（旧 case 可能无此字段）
```

**Review approve 扩展**（在 `batch_review_test_points:441` 处扩展）：

现仅检查 `assertion_missing`，新增 candidate_step 检查：

```python
if next_status == "approved":
    # 现有：单 point assertion_missing 检查（保留）
    point_warnings = point.get("warnings", [])
    if any("assertion_missing" in str(w) for w in point_warnings):
        raise HTTPException(...)
    # 新增：point 级 candidate_step + 无断言检查
    psteps = point.get("steps", [])
    pactions = [str(s.get("action", "")) for s in psteps]
    if "candidate_step" in pactions and not any(
        a.startswith("assert_") for a in pactions
    ):
        raise HTTPException(422, detail={
            "code": "gate_reject_blocked",
            "message": f"测试点 {point_id} 存在未结构化步骤（candidate_step），不可批准。",
        })
```

### 3.4 API 行为变化

| Endpoint | 当前 | 修改后 |
|----------|------|--------|
| `POST /test-point-assets/batch/generate-cases` | 仅检查 review_status | + quality_report violations → 422 |
| `POST /api/workbench/run` | 仅检查 case_id + script_code | + 追溯 source_asset → quality_report → 422 |
| `POST /api/workbench/runs/{id}/rerun` | 无 Gate | 同 run_case |
| `POST /api/workbench/reviews` (approve) | 仅检查 assertion_missing | + candidate_step 检查 |

**新增 422 error codes**：

| code | 含义 | 触发条件 |
|------|------|---------|
| `quality_gate_blocked` | 存在 block 级 violation | Generate/Execute 时 |
| `quality_gate_approve_blocked` | Approve 时 point 有 candidate_step | Review approve 时 |

### 3.5 方案选择：A vs B

| | 方案 A: `workbench_asset_views.py` | 方案 B: `shared_backend/quality_gate/` |
|---|---|---|
| 依赖 | 无新增依赖 | 需 `_build_quality_report` 迁入 shared 或参数传入 |
| 修改范围 | 1 文件 | 2+ 文件 |
| 与现有 quality_gate 包的关系 | 独立（asset 级 vs case 级 Gate） | 需区分两个抽象层 |
| MVP 原则 | ✅ 最小 | ❌ 跨越模块边界 |

**选择方案 A**。理由：
- `_build_quality_report` 是 web-ui-service 专属函数（依赖 `plan.points` 结构），不应迁入 shared_backend
- `shared_backend/quality_gate/` 已有其职责（case 级 DSL 校验），asset 级 enforcement 是不同抽象层
- 方案 A 仅 1 个文件 +40 行，零跨模块依赖

### 3.6 测试用例设计

| # | 场景 | 输入 | 预期 |
|---|------|------|------|
| 1 | zero_assertion → generate blocked | asset with zero_assertion_count=1 | `enforce_quality_gate(action="generate")` 抛 422，code=`quality_gate_blocked` |
| 2 | unprocessed → generate blocked | asset with unprocessed_count=1 | 422 |
| 3 | PASS → generate allowed | asset with all violations empty | 不抛异常 |
| 4 | quality_warning → generate allowed, execute blocked | asset with quality_warnings | action="generate" pass, action="execute" 抛 422 |
| 5 | no source_asset → skip enforcement | case with no source_asset_id | 跳过 Gate，正常执行 |
| 6 | candidate_step → approve blocked | point with candidate_step, no assertion | batch_review 抛 422 |
| 7 | data_warning → approve allowed | point with data_warning only | approve 成功（data 不影响） |
| 8 | generate_cases with REJECT asset | 真实 asset 调用 batch generate | 返回 skipped，reason=`quality_gate_blocked` |
| 9 | violations 包含涉及的 intent_ids | multi-point asset | violations[].intent_ids 非空 |
| 10 | rerun_case with REJECT source_asset | rerun | 422 |

## 4. 修改影响范围评估

| 维度 | 影响 |
|------|------|
| 后端文件 | `workbench_asset_views.py` (+2 函数 ~40行) + `facade_test_point_assets.py` (+3 处调用 + 扩展 review 检查 ~20行) |
| API 影响 | Generate/Execute/Review 三个 endpoint 新增 422 错误码 |
| 测试补充 | `test_quality_gate_enforcement.py`（10 个用例） |
| 数据模型 | 无变更 |
| Structurer | 无变更 |
| Quality Report | 无变更（复用 `_build_quality_report`） |
| shared_backend | 无变更 |
| 前端 | 需展示新的 422 error code |

## 决定

- [ ] 实施 Phase 4
- [ ] 仅实施部分
- [ ] 暂不实施
