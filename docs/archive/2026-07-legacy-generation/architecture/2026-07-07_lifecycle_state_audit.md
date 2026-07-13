# 生命周期状态审计报告

> **日期:** 2026-07-07 | **状态:** LC-001 preview 清理已修复 (3684f9c)
> **审查范围:** 生成管线全生命周期 — preview生成 → asset保存 → DB持久化 → 文件缓存 → 资产查询

---

## 1. 当前状态模型

```
用户请求 POST /preview-test-points
 │
 ▼
preview_store.save_preview_snapshot()
 │   preview_id = "preview-{uuid}"
 │   → 写 web-ui/state/preview-test-points/{preview_id}.json
 │   → 无状态字段, 无 TTL
 │
 ▼
用户选择候选 POST /test-point-assets/save
 │   preview_id 传入
 │
 ▼
save_test_point_assets_service.execute()
 │
 ├── 幂等检查 (IDEM-001): 同 preview_id 已保存? → 返回已有
 ├── allocate_case_id()
 ├── build_point() × N
 ├── _build_asset_bundle() → {"status": "active"}  ← 硬编码,始终 "active"
 ├── DB 写入 (事务原子)
 │     test_points.status = "active"
 │     test_point_assets.status = "active"
 └── 文件写入 (cache)
       state/test-points/{project}/{case_id}.json

                    ↓

资产可查询 (status="active")
```

### 关键发现

```
不存在:
  - generation_status
  - task_status
  - job_status
  - sync_status
  - 任何中间状态 (CREATING/GENERATING/PERSISTING)

存在但不使用:
  - test_point_assets.status = "active" (创建后永不变)
  - test_points.status = "active" (创建后永不变)

存在但无限增长:
  - 71 个 preview 文件, 最老 11 天, 无过期清理
```

---

## 2. 异常场景模拟

### 场景 A: LLM 生成过程中服务重启

```
请求 → orchestrator 调用 LLM → LLM 返回中 → 服务重启

当前行为:
  - orchestrator 是外部服务, 独立生命周期
  - preview_store 不追踪"生成中"状态
  - 重启后: 已完成的 preview 文件保留, 未完成的请求丢失

风险: 🟡 中等
  - 用户不知道任务是否完成
  - 无恢复机制: 用户需重新发起请求
  - 不会重复生成 (IDEM-001 不适用, preview 还未保存)
```

### 场景 B: Preview 生成成功, 用户没有保存

```
preview 文件写入 → 用户关闭页面 → 从未调用 save

当前行为:
  - 71 个 preview 文件无限积累, 最老 11 天
  - 无过期/清理机制
  - 文件大小: 1KB ~ 49KB

风险: 🟡 中等
  - 磁盘空间缓慢增长 (71 个 × ~20KB ≈ 1.4MB, 当前可接受)
  - 无自动清理, 运维需手动删除
  - preview 数据永远无法被利用
```

### 场景 C: 保存资产过程中 DB 失败

```
save_service.execute()
  ├── DB 写入 → RuntimeError → rollback ✅ (DC-001)
  └── 返回 500

当前行为:
  - 用户看到 500 错误
  - 可以重试 (IDEM-001 不拦截: preview 未保存成功)
  - 无中间状态残留 (事务回滚)

风险: 🟢 低 (DC-001 已修复)
```

### 场景 D: DB 成功, 文件 cache 失败

```
save_service.execute()
  ├── DB 写入 ✅ → commit
  ├── 文件写入 → OSError("disk full")
  └── 返回 200 { "plan_path": "" }

当前行为:
  - 用户看到 200 + plan_path 为空
  - DB 数据完整, asset 可用
  - 列表页: sync_cache_from_db() 自动重建文件 ✅
  - 详情页: load_asset(DB) 优先, 可用 ✅

风险: 🟢 低 (自动恢复)
```

### 场景 E: 文件恢复过程中失败

```
sync_cache_from_db() 尝试重建文件
  ├── DB 查询 ✅
  └── 文件写入 → OSError

当前行为:
  - try/except 包裹, 跳过一个 asset, 继续下一个
  - 下次列表页加载时再试
  - 详情页通过 DB 直接读, 不受影响

风险: 🟢 低 (自动重试 + DB 读可用)
```

---

## 3. 状态一致性检查

| 场景 | API 返回 | DB 状态 | 文件状态 | 实际可用 | 一致? |
|------|---------|---------|---------|---------|------|
| 正常保存 | 200 | active | 存在 | ✅ | ✅ |
| DB 失败 | 500 | 无数据 | 不存在 | ❌ | ✅ |
| 文件失败 | 200 | active | 缺失 | ✅ (DB) | ⚠️ plan_path="" |
| IDEM-001 重复 | 200 | active | 存在 | ✅ | ✅ |
| Preview 未保存 | N/A | 无 | preview 文件 | ❌ | ✅ |
| sync_cache 重建 | N/A | active | 恢复中→存在 | ✅ | ✅ |

**唯一不一致:** 文件失败时返回 200 但 `plan_path=""`。DB 数据完整, 实际可用。用户不会感知到问题（详情页走 DB）。

---

## 4. 当前架构是否需要状态机

### 问题列表

| ID | 问题 | 等级 | 影响 | 建议 |
|----|------|------|------|------|
| LC-001 | 无 preview 过期清理 | 🟡 | 71 个文件累积, 无限增长 | 保留 7 天, 定时清理或按需清理 |
| LC-002 | status 始终 "active" | 🟢 | 无生命周期追踪, 但不影响功能 | 当前不需要, 有审核流程后再加 |
| LC-003 | 无法区分"生成中"和"已完成" | 🟢 | LLM 生成在 orchestrator 中, 不在本系统 | 审查者任务由前端状态管理 |
| LC-004 | 文件失败无 sync_status | 🟢 | 自动恢复已覆盖, 标记意义不大 | DC-006 可延迟或取消 |

### 方案比较

| | A: 保持无状态 | B: asset_status 字段 | C: generation_task 表 |
|------|------------|-------------------|---------------------|
| 复杂度 | 低 | 中 | 高 |
| 解决 LC-001 | ❌ | ❌ | ✅ |
| 解决 LC-002 | ❌ | ✅ | ✅ |
| 对当前系统影响 | 无 | 需 migration + 前端适配 | 需新表 + 新 API |
| 当前阶段收益 | — | 低 (无审核流程) | 低 (无异步生成) |
| 推荐 | ✅ 当前阶段 | 审核流程上线后 | 异步生成上线后 |

### 推荐: 方案 A (保持当前设计) + 一个轻量改进

**理由:**
1. 当前生成是同步的 (用户等待 LLM 返回) → 不需要中间状态
2. 保存是原子的 (DC-001 事务) → 不存在中间态
3. 文件失败自动恢复 → 不需要标记
4. 预览过期是唯一实际风险，但 71 个文件 ~1.4MB 对磁盘无压力

**唯一建议改进 (不影响当前架构):**

```python
# preview_store.py: 清理 7 天以上的旧 preview
def cleanup_expired_previews(max_age_days: int = 7) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
    deleted = 0
    for path in PREVIEW_ROOT.glob("*.json"):
        if path.stat().st_mtime < cutoff.timestamp():
            path.unlink()
            deleted += 1
    return deleted
```

可在列表页加载时或通过 cron 调用。这是纯清理逻辑, 不改变状态模型。

---

## 5. 结论

```
═══════════════════════════════════════════════
当前阶段: 不需要引入状态机
═══════════════════════════════════════════════
```

**理由:**
- 生成是同步的, 保存是原子的, 文件是可恢复的
- `status="active"` 虽无生命周期, 但当前无消费者需要区分 "draft/approved/archived"
- 唯一实践问题 (preview 文件累积) 用轻量清理解决, 无需状态机

**当以下条件满足时重新评估:**
1. 引入异步生成 (用户发起后离开页面, 稍后查看结果)
2. 引入审核流程 (approved/rejected 状态流转)
3. 引入多环境 (dev 环境的 preview 不应出现在 prod)
