# 文件生命周期治理审计报告

> **日期:** 2026-07-07 | **状态:** FILE-001 preview 清理已修复 (3684f9c)
> **审查范围:** `web-ui/state/` 全目录 — preview/test-points/generated-cases/runs

---

## 1. 当前设计

```
web-ui/state/
├── preview-test-points/    71 文件   420KB   预览快照
│     └── preview-{uuid}.json         (preview_store 管理)
│
├── test-points/             3 文件   320KB   测试点资产缓存
│     ├── {project}/{case_id}.json    (DB 事实源的文件缓存)
│     └── {project}/plans/{case_id}.json  (同资产的 plan 子文件)
│
├── generated-cases/       100 文件   452KB   生成用例状态
│     └── {case_id}.json              (用例生成的中间状态)
│
├── runs/                   71 目录    11MB   执行运行记录
│     └── {run_id}-artifacts/         (Allure 报告等)
│     └── {run_id}-videos/            (执行视频)
│
├── reporting/               0 文件     0B   报告缓存
└── default/                 0 文件     0B   默认项目
```

### 文件创建位置

| 文件类型 | 创建者 | 格式 | 关联 asset? | 清理机制 |
|---------|--------|------|------------|---------|
| preview | `preview_store.save_preview_snapshot()` | `preview-{uuid}.json` | ❌ 无关联 | ❌ 无 |
| test-point asset | `runtime.save_test_point_plan()` | `{case_id}.json` | ✅ case_id | ✅ sync_cache_from_db 可恢复 |
| test-point plan | `runtime.save_test_point_plan()` | `plans/{case_id}.json` | ✅ case_id | ✅ 同上 |
| generated-case | `save_case_state()` | `{case_id}.json` | ✅ case_id | ❌ 无 |
| run artifacts | `runtime_runs` | `{run_id}-artifacts/` | ❌ | ❌ 无 |

---

## 2. 问题列表

| ID | 问题 | 等级 | 当前状态 | 影响 | 建议 |
|----|------|------|---------|------|------|
| FILE-001 | preview 文件无限累积 | 🟡 | 71 个, 420KB | 磁盘缓慢增长; 7天+ 旧文件永不被使用 | 7 天过期清理 |
| FILE-002 | preview 无关联 asset 标识 | 🟢 | 无法知道已保存 | 已保存的 preview 无法标记或删除 | IDEM-001 已解决(幂等返回), 无需额外处理 |
| FILE-003 | runs 目录增长 | 🟡 | 71 目录, 11MB | 执行视频/截图持续增长 | 已有 Docker volume 挂载, 定期清理 |
| FILE-004 | generated-cases 无清理 | 🟢 | 100 文件, 452KB | 用例生成状态缓存, 可重建 | 可接受; 文件很小 |
| FILE-005 | test-points 目录文件重复 | 🟢 | plans/ 和根目录都有同名文件 | 同一个资产有两个缓存文件 | 这是设计: plan 是子文件, asset 是容器 |

---

## 3. 场景模拟

### 场景 A: 用户生成 preview 后 7 天没有保存

```
当前行为:
  - preview 文件保留在 preview-test-points/
  - 无任何机制标记或清理
  - 7 天后用户重新访问: 如果文件还在 → 可查看; 文件被删 → 404

7 天清理方案:
  - created_at 字段可判断年龄
  - expired = created_at + 7 days < now
  - 清理时机: 每次 save 时顺手清理, 或 cron

建议: 每次 save 成功时清理本 page 的过期 preview
```

### 场景 B: preview 已经生成 asset, 是否可以删除 preview

```
当前行为: 无关联, 无法知道 preview 是否已保存
IDEM-001 后: 可以通过 find_asset_id_by_preview_id 查到关联

建议: save 成功后删除对应 preview 文件 (已保存的不需要保留)
```

### 场景 C: 大量 preview 生成是否影响性能

```
当前: 71 个文件, 420KB → 无影响
极端: 1000 个文件 → glob 枚举慢 (O(n))
      但 preview_store 的文件访问是按 preview_id 精确查找, 不走 glob

结论: 当前规模无影响, 但加清理防止无限增长
```

---

## 4. 建议方案

### 轻量清理: 不需要新字段/新表/状态机

**清理 1: save 成功后删除对应 preview**

```python
# save_test_point_assets_service.py: execute() 末尾
if preview_id:
    try:
        preview_store.delete_preview_snapshot(preview_id)
    except Exception:
        pass  # 清理失败不阻断
```

收益: 已保存的 preview 立即清理, 不累积

**清理 2: 过期 preview 清理 (7 天)**

```python
# preview_store.py
def cleanup_expired_previews(max_age_days: int = 7) -> int:
    """清理超过 max_age_days 天的旧 preview 文件。"""
    import time
    cutoff = time.time() - max_age_days * 86400
    deleted = 0
    for path in PREVIEW_ROOT.glob("*.json"):
        if path.stat().st_mtime < cutoff:
            path.unlink(missing_ok=True)
            deleted += 1
    return deleted
```

触发时机: 每次 `save_test_point_assets` 调用时顺手执行

---

## 5. 结论

```
═══════════════════════════════════════════
当前文件治理: 可控, 磁盘占用小 (总计 ~12MB)
═══════════════════════════════════════════
```

**需要代码修改:** YES — 仅 `preview_store.py` 加 `delete_preview_snapshot()` + `cleanup_expired_previews()`, `save_service` 加清理调用。合计 ~20 行。

**不需要:** 新字段、新表、状态机、定时任务、后台线程。

**优先级:** 🟡 中 (不影响功能, 但 71→∞ 只是时间问题)
