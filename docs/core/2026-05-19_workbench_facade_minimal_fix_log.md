# Workbench Facade 最小改动修复清单与问题留档（2026-05-19）

## 文档信息

- 日期：2026-05-19
- 目标文件：`apps/web-ui-service/app/api/workbench/facade.py`
- 目标：在不做大规模重构的前提下，以最小改动修复高风险问题，提升可维护性与稳定性。

## 最小改动修复清单（按优先级）

### P0（本周必须完成）

1. 合并并保留唯一 `save_case` 方法，消除重复定义覆盖风险。
2. 调整降级视图默认值，避免异常时展示“100% 通过率 + 低风险”。

### P1（建议同批完成）

3. 收敛关键路径的“吞错”逻辑，至少记录 warning 并附带必要上下文。
4. 为 `report_context` 的 git 子进程调用增加超时和统一降级日志。

### P2（可延后）

5. 优化 `_is_within` 的回退分支，避免字符串前缀匹配造成路径边界误判。
6. 降低 `facade.py` 与外部私有函数（`_xxx`）的耦合，逐步转为公共服务接口调用。

## 问题留档（问题 / 原因 / 解决方案）

### 1) 重复定义 `save_case` 被后定义覆盖

- 日期：2026-05-19
- 问题：
  - `WorkbenchFacade` 内存在两个同名 `save_case`，前者在运行时被后者静默覆盖，行为可读性与可维护性差。
- 原因：
  - 历史迭代引入新签名（支持 `db` 校验）时未删除旧方法，导致重复定义。
- 解决方案（最小改动）：
  - 删除旧版 `save_case`，保留带 `db: Session | None` 的版本。
  - 在保留版本中统一兼容旧调用方式（`db` 可选），避免路由层改动。

### 2) 降级返回语义过于“乐观”，可能误导质量判断

- 日期：2026-05-19
- 问题：
  - `dashboard_overview` 异常降级时返回 `pass_rate_24h=100.0`、`risk.level=低`，与“系统异常/数据不可用”语义冲突。
- 原因：
  - 当前降级模板将“无数据”与“健康”混用，未区分“不可用”状态。
- 解决方案（最小改动）：
  - 降级默认值改为中性值：`pass_rate_24h=0.0`、`risk.level=未知`（或 `中`，按产品约定）。
  - 保留 `degraded=true` 和 `degraded_reason`，前端据此提示“数据不可用，仅供参考”。

### 3) 多处宽泛异常捕获导致静默失败

- 日期：2026-05-19
- 问题：
  - 多处 `except Exception` 后直接 `pass` 或返回空对象，调用方难以分辨“真实空数据”与“异常降级”。
- 原因：
  - 为防接口中断采取了过宽松的兜底，但缺少统一可观测性策略。
- 解决方案（最小改动）：
  - 保留降级行为，但统一增加 `warning` 日志（含 request_id / 关键参数 / 原因摘要）。
  - 对读取类函数（如 JSON 文件加载）增加“读取失败标记”字段（例如 `_degraded`）或在上层记录一次聚合告警。

### 4) `report_context` 每次执行 git 子进程且无超时

- 日期：2026-05-19
- 问题：
  - 接口每次调用执行 3 次 `subprocess.run(git ...)`，在仓库/环境异常时可能拖慢请求。
- 原因：
  - 缺少超时控制与轻量缓存。
- 解决方案（最小改动）：
  - 为每次 `subprocess.run` 增加 `timeout`（建议 1~2 秒）。
  - 若超时/失败，记录一次 warning 并返回空字符串，不影响主响应结构。

### 5) `_is_within` 回退分支使用字符串前缀匹配

- 日期：2026-05-19
- 问题：
  - 回退逻辑 `startswith` 存在边界误判风险（如 `/a/b` 与 `/a/b2`）。
- 原因：
  - 兼容低版本路径判断时采用了过于粗糙的回退策略。
- 解决方案（最小改动）：
  - 回退逻辑改为 `os.path.commonpath([path, root]) == root`（先 `resolve` 再比较）。
  - 保留原有 try/except 结构，避免影响调用点。

### 6) 模块职责过重且对私有函数耦合高

- 日期：2026-05-19
- 问题：
  - `facade.py` 同时承载编排、持久化、脚本预览、报表聚合等职责，并直接 import 外部 `_xxx` 私有函数。
- 原因：
  - 迭代中功能不断叠加，未同步做边界收敛。
- 解决方案（最小改动）：
  - 第一阶段仅新增“替换清单”注释：优先将高频私有函数调用切到 service 公共入口。
  - 第二阶段再做逐步迁移，不在本次最小修复内进行大规模拆分。

## 验收建议（针对最小修复）

1. 运行与 `save_case`、dashboard、report_context 相关的现有测试。
2. 手工验证以下场景：
   - dashboard 异常降级时前端提示与数值是否符合“数据不可用”语义；
   - report_context 在 git 命令超时时是否仍能返回主体数据；
   - case 保存链路在有/无 `db` 参数时行为一致。
3. 检查日志中是否出现预期的降级 warning，并带有 request_id。

## Jira 风格可派工模板（2026-05-19）

> 使用方式：每个条目可直接创建为一个 Jira 任务（建议类型：Task/Bug，优先级见标题中的 P0/P1/P2）。

### [P0] WB-FACADE-01 合并 `save_case` 重复定义，消除方法覆盖

- 标题：
  - `[P0] workbench/facade: 合并 save_case 重复定义并保留唯一入口`
- 描述：
  - `WorkbenchFacade` 内存在两个同名 `save_case`，后定义覆盖前定义，造成行为可读性差且维护易误判。
  - 目标是在不改变业务语义的前提下，保留唯一实现并兼容现有调用（`db` 可选）。
- 影响范围：
  - `apps/web-ui-service/app/api/workbench/facade.py`
  - （验证）相关路由/调用方
- 预计改动行数：
  - 8–20 行
- 验收标准：
  - 代码中仅保留一个 `save_case` 定义。
  - `db=None` 与传入 `db` 两种调用方式均可正常执行。
  - case 不在 case center 时仍返回 404。
- 风险：
  - 低；主要是签名兼容风险。
- 回滚方案：
  - 回退该文件到本任务改动前版本；恢复双定义状态（仅应急，不建议长期保留）。
- 回归点：
  - 用例保存接口（正常/404）；
  - 现有调用方参数兼容性。

### [P0] WB-FACADE-02 修正 dashboard 降级语义，避免误导“健康态”

- 标题：
  - `[P0] dashboard: 调整降级默认值，区分“不可用”与“健康”`
- 描述：
  - 当前异常降级默认 `pass_rate_24h=100`、`risk.level=低`，会误导质量判断。
  - 目标是保留降级结构但改为中性/未知语义，明确数据不可用状态。
- 影响范围：
  - `apps/web-ui-service/app/api/workbench/facade.py`
  - （验证）dashboard 前端展示逻辑
- 预计改动行数：
  - 6–16 行
- 验收标准：
  - 异常降级时不再返回“100%通过 + 低风险”组合。
  - `degraded`、`degraded_reason` 字段继续稳定返回。
  - 正常路径指标计算不变。
- 风险：
  - 中；可能影响前端文案/阈值判断（若前端写死“低风险”）。
- 回滚方案：
  - 仅回滚 `_default_overview` 默认值调整。
- 回归点：
  - dashboard 正常加载；
  - 人工制造异常后的降级展示；
  - 依赖 risk/pass_rate 的前端组件。

### [P1] WB-FACADE-03 关键吞错点补齐 warning 日志（保留降级）

- 标题：
  - `[P1] observability: 收敛 facade 吞错点并增加统一 warning`
- 描述：
  - 多处 `except Exception` 后 `pass` 或空返回，难区分“空数据”与“异常降级”。
  - 目标是在不改变返回结构的前提下，补齐可观测性日志。
- 影响范围：
  - `apps/web-ui-service/app/api/workbench/facade.py`
- 预计改动行数：
  - 20–45 行
- 验收标准：
  - 既有降级路径不改变状态码与返回结构。
  - 关键吞错分支新增 warning（包含 request_id/关键参数/错误摘要）。
  - 日志可用于定位异常来源。
- 风险：
  - 低到中；日志量可能上升。
- 回滚方案：
  - 回滚本任务新增日志语句（不影响主逻辑）。
- 回归点：
  - 文件读取失败场景；
  - DB 回滚失败场景；
  - 接口响应是否保持兼容。

### [P1] WB-FACADE-04 为 `report_context` 的 git 命令增加超时与降级日志

- 标题：
  - `[P1] report_context: git 子进程增加 timeout 与失败降级`
- 描述：
  - `report_context` 每次执行 3 次 git 子进程且无 timeout，可能导致慢请求或阻塞。
  - 目标是增加超时保护并在失败时安全降级（返回空串，不影响主响应）。
- 影响范围：
  - `apps/web-ui-service/app/api/workbench/facade.py`
- 预计改动行数：
  - 10–25 行
- 验收标准：
  - 每个 `subprocess.run` 均带超时参数（建议 1–2 秒）。
  - 超时/失败时仍返回 200 且主体数据完整。
  - 新增 warning 日志可见失败原因。
- 风险：
  - 低；仅影响上下文字段完整度。
- 回滚方案：
  - 回滚 timeout 与降级处理，恢复原执行方式。
- 回归点：
  - 正常 git 环境下字段完整；
  - 模拟 git 超时/异常下接口稳定性。

### [P2] WB-FACADE-05 修正 `_is_within` 回退路径判断逻辑

- 标题：
  - `[P2] security-hardening: _is_within 回退分支改为 commonpath 判断`
- 描述：
  - 当前回退分支使用字符串前缀匹配，存在路径边界误判风险。
  - 目标是以最小改动提升路径校验稳健性。
- 影响范围：
  - `apps/web-ui-service/app/api/workbench/facade.py`
- 预计改动行数：
  - 4–12 行
- 验收标准：
  - 合法路径继续通过，越界路径继续拒绝。
  - 相似前缀路径（如 `/a/b` 与 `/a/b2`）判定正确。
- 风险：
  - 低；边界行为更严格。
- 回滚方案：
  - 回滚 `_is_within` 回退分支实现。
- 回归点：
  - `run_case` 相关路径校验；
  - case_path 合法/非法输入矩阵。

### [P2] WB-FACADE-06 私有函数耦合降级第一步（薄封装）

- 标题：
  - `[P2] maintainability: facade 对 service 私有函数耦合降级（第一阶段）`
- 描述：
  - `facade.py` 直接依赖大量外部 `_xxx` 私有函数，边界不清晰。
  - 本任务仅做第一阶段最小动作：新增 2–3 个公共薄封装入口并替换高频私有调用。
- 影响范围：
  - `apps/web-ui-service/app/api/workbench/facade.py`
  - `apps/web-ui-service/app/api/workbench/service.py`
- 预计改动行数：
  - 15–40 行
- 验收标准：
  - 选定调用点完成从私有函数到公共入口的替换。
  - 接口返回结构和行为不变。
  - 无新增循环依赖或导入错误。
- 风险：
  - 中；涉及模块边界调整，需防止行为漂移。
- 回滚方案：
  - 回滚该批替换点，恢复原私有函数调用。
- 回归点：
  - 被替换调用路径对应接口全量冒烟；
  - 导入与启动检查。

## 统一派工字段建议

- 组件：`web-ui-service`
- 模块：`workbench-api`
- 影响级别：
  - P0：生产风险 / 决策误导风险
  - P1：稳定性与可观测性
  - P2：安全边界与可维护性
- Definition of Done（建议）：
  - 代码评审通过；
  - 相关单测/集成测试通过；
  - 手工回归点逐项勾选；
  - 日志与降级语义符合预期；
  - 留档更新（本文件 + 变更记录）。

---

## 追加审查留档：`facade.py` 当前新增风险与修复方案（2026-05-19 16:58）

### 背景

- 审查范围：`apps/web-ui-service/app/api/workbench/facade.py`
- 审查方式：只读检查，未改动业务代码。
- 当前结论：文件可通过 Python 语法编译，但存在运行时未定义名称、路径安全、状态一致性和职责边界问题。

## 本次新增问题清单（按优先级）

### [P0] 1. `LOGGER` 未定义，dashboard 降级路径会二次失败

- 问题：
  - `dashboard_overview` 与 `dashboard_governance` 的多个 `except` 分支调用 `LOGGER.exception(...)`。
  - 当前文件只导入了 `logging`，但没有定义 `LOGGER`。
- 影响：
  - dashboard 正常路径不一定暴露问题。
  - 一旦 dashboard 内部异常，本应返回降级视图，实际可能抛出 `NameError`，导致接口 500。
- 最小修复方案：
  - 在 import 区域之后增加模块级 logger：
    - `LOGGER = logging.getLogger(__name__)`
  - 不改变现有 `LOGGER.exception(...)` 调用点。
- 验收标准：
  - `python3 -m py_compile apps/web-ui-service/app/api/workbench/facade.py` 通过。
  - 人工制造 dashboard 内部异常时，接口返回降级响应，而不是 `NameError`。
  - 日志中能看到对应 exception。
- 建议测试：
  - 新增或补充 dashboard 降级单测，mock 某个内部 service 抛异常。

### [P0] 2. `_find_run_item` 未定义，历史页快照解析存在运行时错误

- 问题：
  - `workbench_history(...)` 中传给 `resolve_run_governance_snapshot` 和 `resolve_run_failure_snapshot` 的 `find_run_item=_find_run_item` 未定义。
- 影响：
  - 当历史列表需要解析治理快照或失败快照时，可能触发 `NameError`。
  - 该问题属于运行时路径问题，静态编译不会发现。
- 最小修复方案：
  - 在 `WorkbenchFacade.workbench_history(...)` 内部定义局部 resolver，优先复用当前 service，再回退到运行态服务：
    - `self._service._find_run_item(run_id)`（若存在）
    - `workbench_runtime_service.find_run_item(...)`
  - 将两个 `find_run_item=_find_run_item` 替换为该局部 resolver。
- 更推荐的中期方案：
  - 在 `WorkbenchService` 暴露公共方法 `find_run_item(...)`，Facade 不直接访问 `_find_run_item` 私有方法。
- 验收标准：
  - 历史列表接口能正常返回。
  - 带 run_id 的历史记录能解析治理/失败快照。
  - 无 `NameError: _find_run_item is not defined`。

### [P0] 3. `run_case` 在路径校验前写文件，存在越界写入风险

- 问题：
  - `run_case(...)` 中，当 DB 用例存在 `script_code` 时，会先调用 `sync_generated_case_yaml_file(...)` 写入：
    - `case_for_run.source_ref`
    - `case_path`
  - 之后才检查 `case_path.exists()` 和 `_is_within(case_path, constants.ASSETS_CASES_ROOT)`。
- 影响：
  - 若请求传入异常 `case_path`，可能先写入文件，再被路径校验拒绝。
  - 这是安全边界与数据污染风险。
- 最小修复方案：
  - 将 `case_path` 解析后，先完成：
    - 是否存在或可创建的策略判断；
    - 是否位于 `ASSETS_CASES_ROOT` 下；
    - 若要同步 `source_ref`，也必须对 `source_ref` 做同等路径约束。
  - 通过校验后再调用 `sync_generated_case_yaml_file(...)`。
- 推荐约束：
  - `payload.case_path` 非空时，只允许相对路径或 `ASSETS_CASES_ROOT` 下的绝对路径。
  - `case_for_run.source_ref` 为空或越界时，不直接写入，最多记录 warning。
- 验收标准：
  - 合法 case path 正常运行。
  - 越界 case path 不产生文件写入。
  - `source_ref` 越界时不会写文件。

### [P0] 4. 删除测试点资产时混用 raw asset_id，存在路径穿越/误删风险

- 问题：
  - `delete_test_point_asset(...)` 同时把 `normalized_asset_id` 和 `raw_asset_id` 放入 `candidate_asset_ids`。
  - 后续用于拼接文件路径并执行 `unlink()` / `shutil.rmtree()`。
- 影响：
  - 如果 raw asset_id 含路径分隔符，可能逃出预期目录。
  - 该删除逻辑还会跨项目目录扫描删除，误删影响面较大。
- 最小修复方案：
  - 删除文件路径时只使用 `normalized_asset_id`。
  - 如果确实需要兼容历史 raw 文件名，必须：
    - 禁止 `/`、`\\`、`..`；
    - 拼接后使用 `_is_within(candidate_path, project_dir)` 校验；
    - 对 `versions` 目录同样做路径边界校验。
- 验收标准：
  - 正常 asset_id 可删除。
  - 包含 `../`、`/`、`\\` 的 asset_id 请求不会删除目标目录外文件。
  - 跨项目删除逻辑不会处理越界路径。

### [P1] 5. 文件态和数据库态缺少统一事务/补偿，容易半成功

- 问题：
  - `delete_test_point_asset(...)` 先删 JSON/YAML 文件，再删 DB case。
  - `batch_review_test_points(...)` 直接写 plan/asset JSON。
  - `generate_cases_from_test_point_assets(...)` 失败后尝试 rollback，但前面可能已追加 history 或生成了部分文件。
- 影响：
  - 中途失败会造成文件态、DB 态、history 态不一致。
- 最小修复方案：
  - 对高风险写操作引入“先校验、后执行、最后提交记录”的顺序。
  - 删除类操作先收集 target 清单，全部验证通过后再执行。
  - history 记录应在主操作成功后追加；失败记录使用单独 action，避免误判为成功。
- 中期方案：
  - 建立统一的 Workbench 写操作服务，封装：
    - dry-run target collection；
    - DB transaction；
    - file operation compensation；
    - history audit。
- 验收标准：
  - 模拟 DB 删除失败时，不应出现文件已删但 DB 仍在的不可恢复状态，或至少返回明确的 partial failure。
  - 操作历史能区分 success / failed / partial。

### [P1] 6. `facade.py` 职责过重，已不再是薄门面

- 问题：
  - 当前文件同时包含：测试点资产处理、页面对象绑定、脚本预览、用例生成、执行、报表、dashboard、清理逻辑。
  - 文件体量超过 4000 行，且直接导入多个 service 的私有函数。
- 影响：
  - 维护成本高，局部修改容易影响无关接口。
  - 单测难以聚焦，mock 范围过大。
- 分阶段修复方案：
  - 第一阶段：只修 P0 风险，不做大拆分。
  - 第二阶段：按领域迁移到专门 service：
    - `test_point_asset_facade_support`
    - `workbench_execution_facade_support`
    - `workbench_dashboard_facade_support`
    - `workbench_report_facade_support`
  - 第三阶段：Facade 仅保留参数标准化、权限/一致性校验、service 调用和响应拼装。
- 验收标准：
  - 单次迁移只覆盖一个领域。
  - 每次迁移后接口返回结构不变。
  - 私有函数导入数量逐步减少。

### [P2] 7. 多处全量扫描，数据量增长后会出现性能瓶颈

- 问题：
  - 测试点评审列表扫描状态目录。
  - 用例列表先加载全量 DB case，再内存过滤。
  - dashboard 加载全量 executions/cases。
- 影响：
  - 当前数据量小问题不明显；数据增长后接口会变慢。
- 修复方案：
  - DB 查询过滤尽量下推到 SQL。
  - 对状态文件索引增加轻量缓存或增量索引。
  - dashboard 限制时间窗口和最大执行记录数量。
- 验收标准：
  - 大数据量下接口耗时有明确上限。
  - 列表类接口分页前不再无条件加载全部对象。

## 推荐修复顺序

1. **第一批 P0：运行时 NameError**
   - 定义 `LOGGER`。
   - 修复 `workbench_history` 中 `_find_run_item` 未定义。
   - 风险低，收益高，建议最先完成。

2. **第二批 P0：路径安全**
   - 调整 `run_case` 写入前校验顺序。
   - 收紧 `delete_test_point_asset` 的 asset_id 路径拼接。
   - 需要补充安全边界测试。

3. **第三批 P1：一致性**
   - 写操作增加先校验后落盘。
   - history 写入区分成功/失败/部分成功。

4. **第四批 P1/P2：结构治理**
   - 按领域拆出 support/service。
   - 优先拆 dashboard/report 和 test point asset 两块。

5. **第五批 P2：性能优化**
   - 针对真实数据量做压测后再优化。

## 建议最小补丁清单

### Patch A：Logger 与历史页 resolver

- 文件：`apps/web-ui-service/app/api/workbench/facade.py`
- 改动：
  - 增加 `LOGGER = logging.getLogger(__name__)`。
  - 在 `workbench_history` 内增加局部 `find_run_item_for_history(run_id)`。
  - 替换两个 `find_run_item=_find_run_item`。
- 测试：
  - `python3 -m py_compile apps/web-ui-service/app/api/workbench/facade.py`
  - 历史页接口冒烟。
  - dashboard 降级冒烟。

### Patch B：`run_case` 写入前路径校验

- 文件：`apps/web-ui-service/app/api/workbench/facade.py`
- 改动：
  - 解析 `case_path` 后立即校验 `_is_within(case_path, constants.ASSETS_CASES_ROOT)`。
  - 对 `source_ref` 写入前增加路径校验。
  - 校验通过后再同步 YAML。
- 测试：
  - 合法 case path 正常执行。
  - 越界 case path 返回 400，且目标文件未被创建或覆盖。
  - source_ref 越界时不写入。

### Patch C：`delete_test_point_asset` 路径约束

- 文件：`apps/web-ui-service/app/api/workbench/facade.py`
- 改动：
  - 删除路径只使用安全 asset_id。
  - 若保留 raw 兼容，必须先做路径分隔符和 `_is_within` 校验。
  - `_remove_if_exists` 内部也增加 root 边界参数，作为最后防线。
- 测试：
  - 正常删除。
  - `../evil`、`a/b`、`a\\b` 均不会越界删除。
  - 不存在 asset 返回 404。

### Patch D：一致性与审计

- 文件：优先仍在 `facade.py`，后续下沉 service。
- 改动：
  - 删除/批量评审/生成链路统一记录成功、失败、部分成功。
  - 对文件和 DB 混合写操作增加 target 预检查。
- 测试：
  - 模拟 DB 失败、文件写失败、部分 asset 不存在。
  - history 中 action 与实际结果一致。

## 回归验证清单

1. 静态检查：
   - `python3 -m py_compile apps/web-ui-service/app/api/workbench/facade.py`
2. 重点接口冒烟：
   - workbench history
   - dashboard overview
   - dashboard governance
   - run case
   - delete test point asset
   - batch review test points
3. 安全边界：
   - 越界 `case_path`
   - 含路径分隔符的 `asset_id`
   - 不存在 run/case/asset
4. 数据一致性：
   - DB 删除失败时的返回与 history。
   - 文件删除失败时的返回与 history。
   - 批量操作部分成功时的 skipped/missing 明细。

## 不建议一次性做的事情

- 不建议在同一个 PR 中同时完成大规模拆分、路径安全修复、dashboard 改造和性能优化。
- 不建议继续在 `facade.py` 中堆叠新的业务规则。
- 不建议为了兼容历史 raw asset_id 而放宽路径约束；历史兼容必须以 `_is_within` 为底线。
