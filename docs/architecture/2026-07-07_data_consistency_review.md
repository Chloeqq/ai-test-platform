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
