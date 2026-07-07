# 数据一致性反方审查报告

> **日期:** 2026-07-07
> **审查人:** 反方审查者（Claude）
> **审查对象:** `save_test_point_assets_service.py` Phase 2 持久化重构（commit `3e60e57`）
> **审查方法:** 模拟 100 次生成、网络随机失败、DB 随机不可用

---

## 问题清单

### P0 — 立即修复

| ID | 问题 | 严重等级 | 影响 | 修复方案 |
|----|------|---------|------|---------|
| DC-001 | `sync_test_points` 和 `save_asset` 不在同一事务 | 🔴 严重 | DB 部分写入：`test_points` 表有数据但 `test_point_assets` 表无数据，产生 DB 层孤儿 | 两处写入包裹在同一 DB 事务中，移除 `sync_test_points` 内部的 `self.db.commit()`，由调用方统一 commit |
| DC-002 | 文件写入失败无补偿机制 | 🔴 严重 | DB 已保存但文件未写入 → 文件读取路径返回空 → 用户看到成功但详情页报错 | DB 记录 `file_sync_status = "pending"`，后台任务或下次查询时自动调用 `sync_cache_from_db()` |

### P1 — 本周修复

| ID | 问题 | 严重等级 | 影响 | 修复方案 |
|----|------|---------|------|---------|
| DC-003 | 并发写入同一 case_id 时 last-write-wins | 🟡 中等 | 两次请求复用同一 case_id，后写入的覆盖先写入的，数据静默丢失 | 增加乐观锁（version 字段）或悲观锁（SELECT FOR UPDATE） |
| DC-004 | `sync_test_points` 逐条 upsert 无 savepoint | 🟡 中等 | 部分 point 写入成功（flushed），后续 point 失败导致整个 commit 失败，但已 flush 的数据可能已持久化 | SAVEPOINT 包裹循环，失败时回滚到保存点 |
| DC-005 | 重试时可能分配不同 case_id | 🟡 中等 | 首次文件写入成功但 DB 失败 → 文件孤儿 + 重试产生新 case_id → 重复资产 | 重试前优先查 DB 是否存在同 case_id；存在则更新而非新建 |

### P2 — 计划修复

| ID | 问题 | 严重等级 | 影响 | 修复方案 |
|----|------|---------|------|---------|
| DC-006 | 缺少 `file_sync_status` 字段 | 🟡 中等 | 运维无法快速识别哪些资产需要 `sync_cache_from_db()` 重建 | `test_point_assets` 表增加 `file_sync_status` 字段（`synced` / `pending`） |
| DC-007 | 文件失败时 `plan_path` 返回空字符串 | 🟢 低 | 调用方收到 `plan_path: ""` 但 `asset` 数据完整，UI 展示不一致 | DC-006 解决后自然修复 |

---

## 任务列表

### Task DC-001: 事务原子性（P0）

**当前状态:** ⬜ 待开始
**文件:** `save_test_point_assets_service.py`, `repository.py`
**变更:**
1. 删除 `repository.sync_test_points()` 内部的 `self.db.commit()`
2. `save_test_point_assets_service.execute()` 中包裹统一事务：
   ```python
   try:
       repository.sync_test_points(...)    # 仅 flush，不 commit
       test_point_asset_store.save_asset(...)  # 仅 flush，不 commit
       repository.db.commit()  # 一次性提交
   except Exception:
       repository.db.rollback()  # 全部回滚
       raise
   ```
3. 验证：测试 Case 2（DB 失败）仍然通过

### Task DC-002: 文件写入失败补偿（P0）

**当前状态:** ⬜ 待开始
**文件:** `save_test_point_assets_service.py`, `test_point_asset_store.py`
**变更:**
1. `save_asset()` 增加 `file_sync_status` 参数（默认 `"synced"`）
2. 文件写入失败时 `save_asset(file_sync_status="pending")` 覆写 DB 标记
3. 资产列表查询时展示同步状态（`sync_status` 字段）
4. 新增 `GET /api/workbench/test-point-assets/pending-sync` 端点或管理命令

### Task DC-003: 并发乐观锁（P1）

**当前状态:** ⬜ 待开始
**文件:** `test_point_asset_repository.py`, `save_test_point_assets_service.py`
**变更:**
1. `TestPointAsset` 表利用已有 `version` 字段做乐观锁
2. `upsert()` 增加 `expected_version` 参数
3. 版本冲突时返回冲突错误而非静默覆盖

### Task DC-004: SAVEPOINT 包裹（P1）

**当前状态:** ⬜ 待开始
**文件:** `repository.py`
**变更:**
1. `sync_test_points()` 循环前创建 SAVEPOINT
2. 异常时 ROLLBACK TO SAVEPOINT
3. 成功时 RELEASE SAVEPOINT

### Task DC-005: 重试去重（P1）

**当前状态:** ⬜ 待开始
**文件:** `save_test_point_assets_service.py`
**变更:**
1. `allocate_case_id()` 前先查 DB（非文件）是否存在同 page 资产
2. 存在则复用 `case_id` 并更新而非新建
3. 防止文件孤儿 + 新建 case_id 的重复资产

### Task DC-006: sync_status 字段（P2）

**当前状态:** ⬜ 待开始
**文件:** `test_point_asset.py` (model), `test_point_asset_store.py`
**变更:**
1. `test_point_assets` 表增加 `file_sync_status VARCHAR(20) DEFAULT 'synced'`
2. 资产列表 API 返回 `sync_status` 字段
3. 前端展示同步状态标签

### Task DC-007: plan_path 空值处理（P2）

**当前状态:** ⬜ 待开始
**文件:** `save_test_point_assets_service.py`
**变更:**
1. DC-006 完成后，返回的 `plan_path` 为空时附带 `sync_status = "pending"` 标记

---

## 验证标准

全部任务完成后需满足：

| 标准 | 验证方式 |
|------|---------|
| DB 双写原子性 | Mock DB 在 `save_asset` 时失败，验证 `test_points` 无残留 |
| 文件失败可恢复 | 故意填满磁盘，保存后验证 DB 标记 `pending`，调用 `sync_cache_from_db` 后文件恢复 |
| 并发安全 | 2 线程同时保存，验证最终数据是最后一次写入的完整版本 |
| 重试无重复 | 首次 DB 失败，重试后验证只有 1 条 asset 记录 |
| 无孤儿数据 | 100 次随机故障模拟后，统计文件数 = DB 记录数（允许 `pending` 差异） |

---

## DC-002 补充分析：Source of Truth 代码验证（2026-07-07）

### 逐项回答

**Q1: test_point_assets 是否保存完整测试资产内容？**

✅ 是。`test_point_asset.py` 模型：`raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)`。
`save_asset()`（`test_point_asset_store.py:63`）将完整 bundle（含 plan + 全部 points）写入 `raw_payload`。数据无损。

**Q2: sync_cache_from_db() 恢复文件时，数据来源是什么？**

✅ DB。代码（`test_point_asset_store.py:111`）：
```python
payload = row.raw_payload  # 从 DB 读取
path.write_text(json.dumps(payload, ...))  # 写入文件
```
数据流：`DB raw_payload → JSON string → state/*.json`。不依赖已有文件。

**Q3: 如果 state/*.json 完全删除，是否可以仅依靠 DB 恢复？**

✅ 是。
```python
# test_point_asset_store.py:111-135
for row in rows:                       # 遍历 DB 中所有资产
    payload = row.raw_payload          # 读 DB 完整数据
    path.write_text(json.dumps(...))    # 重建文件
```
执行：`sync_cache_from_db(db, project, project_dir)` 即可全量恢复。

**Q4: 如果 DB 删除，是否可以仅依靠文件恢复？**

✅ 是。
```python
# test_point_asset_store.py:138-155
for path in sorted(project_dir.glob("*.json")):  # 遍历所有文件
    bundle = json.loads(path.read_text())         # 读文件
    repo.upsert(**cols)                           # 写入 DB
```
执行：`backfill_from_dir(db, project, project_dir)` 即可全量恢复。

双向恢复能力已完整实现。

**Q5: 当前读取详情接口的数据来源是什么？**

DB 优先，文件回退。代码（`facade_test_point_assets.py:167-174`）：
```python
load_test_point_asset = lambda project, case_id: (
    test_point_asset_store.load_asset(db, ...)              # 1. DB 优先
    or workbench_asset_service.load_test_point_asset_with_root(...)  # 2. 文件回退
)
```
DB 有数据 → 返回 DB 数据。DB 无数据 → 返回文件数据。

**Q6: 当前列表接口的数据来源是什么？**

⚠️ **混合来源，存在 gap**。代码（`asset_views.py:234-243`）：
```python
# 枚举: 仅从文件
case_ids = set(file.stem for file in project_dir.glob("*.json"))

# 加载: 仅从文件
asset = _state_svc().load_test_point_asset(project, case_id)
```

列表枚举和加载都走文件，不查 DB。但 facade 在调用前执行 `sync_cache_from_db()` 保证 DB 资产都有对应文件（`facade_test_point_assets.py:148`）：
```python
test_point_asset_store.sync_cache_from_db(db, project=project, project_dir=...)
```

**正常路径：** `sync_cache_from_db()` 成功 → 文件齐全 → 列表完整 → DB 是事实源
**异常路径：** `sync_cache_from_db()` 失败（try/catch 吞异常，line 154）→ 只列有文件的资产 → DB 独有资产不可见

---

### 事实总结

| 维度 | DB (test_point_assets) | File (state/*.json) |
|------|----------------------|-----|
| 完整数据存储 | ✅ raw_payload JSON | ✅ 同内容 |
| 写入事务保证 | ✅ ACID | ❌ 无 |
| 列表枚举来源 | ❌ 不走 DB | ✅ 文件 glob |
| 详情加载来源 | ✅ 优先 | ✅ 回退 |
| DB→文件恢复 | - | ✅ sync_cache_from_db |
| 文件→DB 恢复 | ✅ backfill_from_dir | - |
| 恢复自动触发 | - | ✅ 每次列表页 |

---

### 结论

**DB 可以作为 source of truth，但有一个 gap 需修复：**

列表接口的文件枚举应并入 DB ID 列表，否则 `sync_cache_from_db` 失败时 DB 独有资产不可见。

**评级：** B（DB source of truth），gap 在 `asset_views.py:234` 的文件枚举。`sync_cache_from_db` 的 try/catch 兜底可以掩盖此问题，但不可靠。
