# 幂等性审计报告

> **日期:** 2026-07-07
> **审查范围:** 全链路 — 用户请求 → API → Service → Generator → Asset保存 → DB写入 → 文件缓存

---

## 1. 当前设计

### ID 链路图

```
用户请求 (无 request_id)
  │
  ▼
POST /api/workbench/preview-test-points
  │   payload: { project, page, requirement }
  ▼
preview_store.save_preview_snapshot()
  │   preview_id = "preview-{uuid4().hex[:16]}"    ← 唯一,但仅存储在 state/ 文件
  │   trace_id = 由 orchestrator 传入               ← 仅存储在 preview snapshot 中
  ▼
返回 { preview_id, test_intents }
  │
用户选择候选测试点
  │
  ▼
POST /api/workbench/test-point-assets/save
  │   payload: { project, page, preview_id, selected_candidates }
  │   无 request_id / trace_id / idempotency_key
  ▼
save_test_point_assets_service.execute()
  │
  ├── case_id 分配:
  │     requested_case_id = payload.case_id or find_existing_page_asset_for_upsert()
  │       └── 查: 文件 scan + test_cases DB
  │       └── ❌ 不查 test_point_assets 表！
  │     allocate_case_id()
  │       └── 查: *.yaml 文件 + existing_case_ids
  │       └── ❌ 不查 test_point_assets 表！
  │
  ├── DB 写入 (DC-001 修复后：原子事务):
  │     sync_test_points()  → test_points 表
  │       └── UPSERT ON (project_code, page_code, point_id)  ← 有唯一约束
  │     save_asset()        → test_point_assets 表
  │       └── UPSERT ON (project_code, asset_id)             ← 有唯一约束
  │     commit()
  │
  └── 文件写入 (cache):
        save_test_point_plan()  → state/test-points/{project}/{case_id}.json
```

### DB 唯一约束

| 表 | 唯一约束 |
|----|---------|
| `test_points` | `(project_code, page_code, point_id)` |
| `test_point_assets` | `(project_code, asset_id)` |

### 已存在的幂等保护

| 保护 | 位置 | 效果 |
|------|------|------|
| `upsert_point()` | `test_point_repository.py` | 重复 point_id 不会报错,更新已有记录 |
| `upsert()` (asset) | `test_point_asset_repository.py` | 重复 asset_id 不会报错,更新已有记录 |
| `find_existing_page_asset_for_upsert()` | `save_service.py` | 同 project+page → 复用已有 case_id |
| DB 唯一约束 | 两个表 | 阻止 INSERT 重复,但 UPSERT 绕过了 |

---

## 2. 发现问题

| ID | 问题 | 等级 | 影响 | 建议 |
|----|------|------|------|------|
| IDEM-001 | 无 request_id / idempotency_key | 🔴 | 无法识别重复请求;重试创建新资产 | 引入 `preview_id` 作为幂等键,保存前检查是否已保存 |
| IDEM-002 | `allocate_case_id` 不查 `test_point_assets` 表 | 🔴 | 文件缓存丢失时分配新 case_id,产生重复资产 | `collect_existing_case_ids` 增加 DB `test_point_assets` 查询 |
| IDEM-003 | 同一 preview_id 可被多次保存 | 🟡 | 同一份预览数据产生多个 asset 版本,last-write-wins | 保存前检查:该 preview_id 是否已保存过;若已存在返回已有 case_id |
| IDEM-004 | 无并发保护 | 🟡 | 两个请求同时保存同页面 → 竞争 case_id | 依赖 DB 唯一约束 + UPSERT (当前行为是 last-write-wins) |
| IDEM-005 | 场景 A (DB失败重试): 文件孤儿风险已修复 | ✅ | DC-001 事务保证 | 无需额外处理 |
| IDEM-006 | 场景 C (双 worker): 无分布式锁 | 🟢 | page_code 级竞争概率极低 | 可接受;DB 唯一约束兜底 |

---

## 3. 重试场景模拟

### 场景 A: DB 写入失败后重试

```
第1次: 文件写 ✅ → DB写 fail → rollback ✅ (DC-001)
第2次: allocate_case_id() → find_existing → 文件存在 → 复用 case_id ✅
       文件写 ✅ → DB写 ✅ → commit ✅
结果: ✅ 不会产生重复
```

### 场景 B: DB commit 成功后网络断开

```
第1次: DB commit ✅ → 网络断开 → 客户端 timeout
第2次: find_existing_page_asset_for_upsert() → 查文件 + test_cases DB 
       → ❌ 不查 test_point_assets → 未找到 → 分配新 case_id-0002
       → DB UPSERT → test_point_assets 有两条记录 (0001 + 0002)
结果: ❌ 产生重复资产
```

### 场景 C: 两个 worker 同时保存

```
Worker A: allocate_case_id() → 0001
Worker B: allocate_case_id() → 0001 (同一页面)
Worker A: upsert (0001, 27 points) → commit
Worker B: upsert (0001, 15 points) → commit  ← 覆盖 A 的 27 points
结果: ⚠️ A 的数据被 B 覆盖 (last-write-wins)
```

---

## 4. 幂等策略比较

| 策略 | 一致性 | 复杂度 | 对现有代码影响 | 推荐 |
|------|--------|--------|-------------|------|
| **A: 唯一约束** | 中 | 低 | 已存在,但只防 INSERT 不防 UPSERT 覆盖 | 已实施,不够 |
| **B: preview_id 幂等** | 高 | 低 | +20行: 保存前查 DB 是否已存在 | ✅ 推荐 |
| **C: 分布式锁** | 高 | 高 | 需要 Redis 锁, 改动大 | 过度设计 |
| **D: 任务状态机** | 高 | 中 | 需要新表 + 状态字段 | 未来可做 |

---

## 5. 推荐方案: preview_id 幂等键 (方案 B)

### 核心逻辑

```python
def execute(payload):
    preview_id = payload.preview_id
    
    if preview_id:
        existing = find_asset_by_preview_id(db, preview_id)
        if existing:
            return {"case_id": existing.asset_id, "status": "already_saved", ...}
    
    # 正常保存流程...
    save_asset(bundle, preview_id=preview_id)  # 存储 preview_id
```

### 为什么选方案 B

1. **preview_id 天然存在** — `save_preview_snapshot()` 已生成,贯穿 parser→preview→save 全链路
2. **实现简单** — 在 `test_point_assets` 查询是否已有同 `preview_id` 的资产
3. **解决 IDEM-001/003 两个问题** — 重试识别 + 防止重复保存
4. **不需要新表/新字段** — `preview_id` 已存在 `raw_payload.metadata.preview_id` 中

### 不选方案 A/C/D 的原因

- 方案 A (唯一约束): 已存在但不阻止 UPSERT 覆盖, 不解决重试识别
- 方案 C (分布式锁): 低频操作不需要, 引入 Redis 依赖过度
- 方案 D (状态机): 需要新表, 当前阶段不需要

---

## 6. 修改范围预估

### 需要修改的文件

| 文件 | 改动 | 行数 |
|------|------|------|
| `save_test_point_assets_service.py` | `execute()` 入口: `preview_id` 已保存检查 | +10 |
| `test_point_asset_store.py` | 新增 `find_asset_by_preview_id(db, preview_id)` 查询 | +15 |
| `repository.py` | `collect_existing_case_ids()` 增加 `test_point_assets` 表查询 | +10 |

### 需要修改的测试

| 测试 | 覆盖场景 |
|------|---------|
| `test_idempotent_save` (已有, 更新) | 同一 preview_id 保存两次 → 返回首次 case_id |
| `test_preview_id_blocks_duplicate` (新增) | 不同 preview_id 可创建不同资产 |
| `test_retry_after_db_failure_reuses_case_id` (新增) | DB 失败后重试复用 case_id |

---

## 7. 结论

```
═══════════════════════════════════════════════════════
是否可以进入代码修改阶段: YES
═══════════════════════════════════════════════════════
```

**前提条件:**
1. `find_asset_by_preview_id()` 查询 `test_point_assets.raw_payload->>'$.metadata.preview_id'`
2. 已保存的资产返回已有 `case_id` 而非报错（幂等返回）
3. `allocate_case_id` 增加 DB `test_point_assets` 表查询
4. 仅修改上述 3 个文件
