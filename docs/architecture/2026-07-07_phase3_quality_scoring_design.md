# Phase 3: AI 测试资产质量评分与覆盖分析

> **日期:** 2026-07-07 | **状态:** ✅ MVP 已实施 (7f0a18a)

---

## 1. 当前能力分析

### 已有

| 能力 | 粒度 | 数据来源 |
|------|------|---------|
| `quality_report` | Asset 级 | `_build_quality_report(asset)` |
| `point_type` 分布 | Asset 级 | `plan.points[].point_type` |
| 断言质量 | Asset 级 | `quality_report.by_point_type` |
| 审核状态 | Point 级 | `point.review_status` |
| `requires_review` | Point 级 | `point.requires_review` |
| `confidence` | Asset + Point 级 | `asset.confidence`, `point.confidence` |
| 技术分布 | Asset 级 | `technique_distribution` |
| 覆盖率 | Asset 级 | `plan.coverage` |
| 追溯矩阵 | Asset 级 | `plan.metadata.coverage_matrix` |

### 缺失

| 能力 | 为什么需要 | 复杂度 |
|------|----------|--------|
| 项目级聚合 | 多资产质量对比 | 低 (纯计算) |
| 资产质量排名 | 优先修复低分资产 | 低 (纯排序) |
| Point 级质量分 | 定位具体问题点 | 低 (已有数据) |
| 质量趋势 | 追踪质量改进 | 中 (需要历史快照) |
| 执行反馈闭环 | 执行结果反哺质量 | 高 (需要执行数据) |

---

## 2. Phase 3 MVP 架构

```
项目 Dashboard
  │
  ├── 资产质量排名 (Asset Quality Ranking)
  │     └── quality_report.score 排序 + 按页面分组
  │
  ├── 资产质量详情 (Asset Quality Detail) ← 已有 quality_report
  │     └── 新增: point_level_quality 数组
  │
  ├── 覆盖矩阵 (Coverage Matrix) ← 已有 coverage_matrix
  │     └── 新增: 质量标注 (哪些 intent 零断言)
  │
  └── 项目质量摘要 (Project Quality Summary) ← 【新增】
        └── 聚合所有资产的 quality_report
```

### 核心新增: `project_quality_summary`

```python
def build_project_quality_summary(project: str) -> dict:
    """聚合项目中所有资产的质量数据。"""
    assets = list_all_assets(project)
    return {
        "total_assets": len(assets),
        "total_points": sum(a.point_count for a in assets),
        "avg_score": avg(a.quality_report.score),
        "decision_distribution": {
            "pass": count_by_decision("PASS"),
            "review": count_by_decision("REVIEW"),
            "reject": count_by_decision("REJECT"),
        },
        "by_page": {
            page: aggregate_for_page(page_assets)
            for page in unique_pages
        },
        "lowest_quality_assets": top_n_lowest(5),  # 优先修复
    }
```

### 核心新增: `point_level_quality`

```python
def build_point_quality(point: dict) -> dict:
    """单测试点质量评分，基于已有字段计算。"""
    steps = point.get("steps", [])
    assertions = [s for s in steps if s["action"].startswith("assert_")]
    return {
        "intent_id": point["intent_id"],
        "has_assertion": len(assertions) > 0,
        "assertion_strength": _classify_strength(assertions),
        "has_candidate_step": any(s["action"] == "candidate_step" for s in steps),
        "requires_review": point.get("requires_review", False),
        "review_status": point.get("review_status", "pending"),
    }
```

---

## 3. MVP 范围（3 项）

| # | 功能 | 数据来源 | 新增代码 |
|---|------|---------|---------|
| 1 | `point_level_quality` 数组 | 已有 plan.points | `asset_views.py` +30行 |
| 2 | `project_quality_summary` | 已有 quality_report × N | `asset_views.py` +40行 |
| 3 | 前端质量仪表板 | API 已有数据 | 前端页面 +80行 |

**不新增:** API 端点、DB 字段、状态机、Agent、规则。

### 不做的

| 功能 | 原因 |
|------|------|
| 质量趋势图 | 需要历史快照存储 |
| 执行反馈闭环 | 需要执行数据关联 |
| AI 质量建议 | 需要 LLM 集成 |
| 自动修复 | Repair Agent 已否决 |

---

## 4. 风险评估

| 风险 | 等级 | 缓解 |
|------|------|------|
| 纯计算, 不影响写入 | 🟢 | 无副作用 |
| quality_report 计算开销 | 🟢 | 资产数 < 100, 毫秒级 |
| 前端页面复杂度 | 🟡 | 复用已有组件模式 |

---

## 5. 结论

```
═══════════════════════════════════════════════
Phase 3 MVP: 3 项, ~150 行, 0 新基础设施
═══════════════════════════════════════════════
```

所有数据已在 asset/plan 中。新增的是聚合和展示，不动编译链、不动 Gate、不动状态模型。
