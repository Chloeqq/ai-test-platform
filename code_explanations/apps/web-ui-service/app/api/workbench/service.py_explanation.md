# 📘 代码说明书
## 一句话概括
这是一个「自动化测试工作台（Workbench）的后端业务逻辑中枢」，负责管理测试用例、执行任务、门禁审批、失败分析、自我修复、重跑和人工评审等全流程操作——就像一个智能工厂的调度中心，既管图纸（用例）、又管产线（执行）、还管质检（门禁/评审）、甚至能自动修机器（自愈）。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `service.py` | 提供所有工作台核心业务能力的“服务总开关”，不直接处理 HTTP 请求（那是 API 层的事），而是被 FastAPI 路由调用，专注做「该干什么、怎么干、干得怎么样」的逻辑判断和协调工作。|

## 🔍 核心函数/类说明
- **`class WorkbenchService`**：整个工作台的「业务大脑」，封装了所有用户能用到的功能（比如查任务、跑用例、审批门禁、提交评审、修复失败等）。  
  - 输入：几乎都来自 FastAPI 接收到的请求参数（如 `case_id`, `run_id`, `payload`, `request`, `db` 等）  
  - 输出：统一返回结构化的字典，包含 `"item"`（主数据）和 `"summary"`（统计摘要），有时还有 `"calibration_sample"`（校准记录）等辅助信息  
  - 大白话解释：它不是搬砖工人，而是项目经理+质量总监+维修队长的合体——你告诉它“我要查第3次失败的用例”或“帮我修好这个报错并重跑”，它就去调各个部门（其他 service 模块）、查文件、读配置、写日志、做判断，最后给你一份清晰报告。

- **`_collect_execution_records_with_meta()`**：专门负责「翻箱倒柜找历史执行记录」的函数。  
  - 输入：可选 `limit`（最多找多少条）  
  - 输出：`(执行记录列表, 元数据字典)`，元数据里有总数量、时间范围、失败率等统计信息  
  - 大白话解释：就像档案室管理员，定期去 `artifacts/` 和 `*-artifacts/` 这些“仓库角落”，把所有测试运行留下的 JSON 报告、证据清单、执行日志等打包整理成整齐的清单，供上面的 `WorkbenchService.list_execution_tasks()` 使用。

- **`_build_execution_task_view(entry)`**：把原始执行记录（一堆杂乱字段）「翻译成人话」的翻译官。  
  - 输入：一条原始执行记录（比如从磁盘读出的 JSON 字典）  
  - 输出：标准化后的任务视图，含 `project_code`, `case_id`, `status`, `evidence_health`, `retry.enabled` 等易懂字段  
  - 大白话解释：原始数据像刚拍回来的监控录像（全是时间戳、路径、状态码），它负责加上字幕、打上标签、标出重点（比如“这个用例失败了，因为截图没加载出来，且已重试2次”），让前端能直接展示。

- **`_start_run()` / `_execute_run()`**：测试用例的「点火器」和「发动机」。  
  - 输入：项目名、用例ID、用例文件路径、来源（如 `web`, `rerun`）  
  - 输出：新生成的 `run_id` 和初始运行信息（如开始时间、状态为 `queued`）  
  - 大白话解释：`_start_run` 是按下“开始测试”按钮（创建任务、存入队列、记日志）；`_execute_run` 是真正启动 Python 进程去跑那个 `.yaml` 用例文件（调用 `subprocess.run` 执行命令）。它们配合 `workbench_runtime_service` 完成从排队→编译→运行→收结果的全过程。

- **`save_execution_gate_decision()`**：执行门禁（Execution Gate）的「人工审批柜台」。  
  - 输入：审批决定（`approve`/`reject`/`manual_review`）、备注、当前登录人信息（从 `request` 提取）  
  - 输出：审批记录 + 审批快照（含触发了哪些规则、证据链、风险评分等）  
  - 大白话解释：就像软件上线前的“闸口”，自动检查（如覆盖率够不够、关键用例是否通过）后若不满足，就卡住并弹窗请人审核。这个函数就是处理你点“通过”或“驳回”的动作——记录谁审的、为什么审、依据什么规则，并同步更新门禁状态。

- **`heal_run()`**：失败用例的「自动医生」。  
  - 输入：`run_id`（某次失败的运行ID）  
  - 输出：修复建议的 JSON 结果（如修改了哪行代码、替换了哪个选择器）  
  - 大白话解释：当测试因为页面元素变了而失败时，它会自动找到最近一次成功的 `suggestion.json`（AI 给的修复方案），调用 `apply_fix.py` 脚本尝试修改用例代码，相当于让 AI 自己“动手术”修 bug，而不是等人工介入。

- **`_safe_case_id()`**：用例ID 的「兜底安全员」。  
  - 输入：任意字符串（可能为空、带空格、格式错误）  
  - 输出：标准化后的用例ID（如 `"ATP-123"` → `"atp-123"`），若输入无效则返回默认值 `"atp-web-common-core-fn-ai-0001"`  
  - 大白话解释：就像身份证号录入系统，你随手输个 `" ATP_123 ! "`，它也能帮你去掉空格、转小写、统一格式，避免因格式问题导致后续查找失败。

## 🧩 调用关系与数据流转
```
FastAPI路由（如 /api/workbench/tasks）
        ↓
WorkbenchService.list_execution_tasks() 
        ↓ 调用
_collect_execution_records_with_meta() → 扫描 artifacts/ 目录 → 返回原始记录列表 + 元数据
        ↓ 循环处理每条记录
_build_execution_task_view() → 将原始记录“翻译”成标准任务视图（加 project_status、evidence_health 等）
        ↓ 过滤（按 project_code/status 等）→ 截取 limit 条
_build_execution_task_summary() → 统计这页数据的失败率、重试率等 → 返回 summary
        ↑
最终返回：{"items": [任务列表], "summary": {...}}

另一起点：
用户点击「审批门禁」→ FastAPI路由 → save_execution_gate_decision()
        ↓
require_authenticated_review_actor() → 验证登录身份 → 失败则记日志并抛错
        ↓ 成功
workbench_gate_service.upsert_execution_gate_decision() → 写入审批记录
        ↓
resolve_execution_gate_audit_snapshot() → 调用 find_run_item() 查当前运行详情 → 构建完整审计快照
        ↓
_append_execution_gate_history() → 把审批动作写进 history.json 日志文件

再一路：
用户点「修复并重跑」→ heal_and_rerun_case()
        ↓ 并行
heal_run() → 调用 _get_python_bin() + subprocess.run(apply_fix.py) → 得到修复结果
        ↓
rerun_case() → 调用 _start_run() → 创建新 run_id → 记录到 runtime_runs.json
        ↓
wait_run_terminal() → 定期调用 _find_run_item() 查询新 run_id 状态 → 直到完成或超时
```

## 💡 值得学习的写法
- **`_shim_callable()` 的“函数占位符”设计**：用它包裹所有对下游 service 的调用（如 `workbench_runtime_service.load_runtime_execution_record_from_artifacts`），既保留了真实函数的能力，又为未来做 A/B 测试、Mock 替换、埋点监控留好了钩子——就像给每个水管接口都预装了阀门和流量计，不用改主体逻辑就能随时切换水源或监测水流。
- **`_normalize_*` 系列函数的防御性编程**：所有输入都先 `str().strip()`，空值返回默认或空字典，避免 `AttributeError` 或 `KeyError`。比如 `_normalize_failure_entry_view()` 直接 `return {}` 而不是硬解包，让上游代码永远不必写 `if entry and "xxx" in entry`。
- **`_is_within()` 的路径安全校验**：用 `path.resolve().relative_to(root.resolve())` 判断文件是否在指定目录内，彻底防止路径遍历攻击（如 `../../../etc/passwd`），比简单字符串匹配更可靠。
- **`_parse_iso_datetime()` 的容错时间解析**：自动补 `Z` → `+00:00`、自动加 UTC 时区、自动转本地时区→UTC，让前后端传的时间字符串无论 `"2024-01-01T12:00:00Z"` 还是 `"2024-01-01T12:00:00"` 都能正确处理。
- **`heal_and_rerun_case()` 的“尽力而为”模式**：修复失败不影响重跑（`heal_ok=False` 但继续 rerun），符合真实运维场景——修不好？先重跑看是否偶发，别卡死流程。

## ⚠️ 需要注意的地方
- **`_sync_stage_a_workbench_state()` 和 `_sync_stage_b_workbench_gate()` 是空函数**：名字看着很重要（阶段A/B同步），但目前 `return None`。新手容易误以为这是关键同步逻辑，实际是预留桩，需确认是否已被废弃或待实现。
- **`_safe_case_id()` 的默认值 `"atp-web-common-core-fn-ai-0001"` 是硬编码**：如果项目中真出现空 case_id，所有相关记录都会归到这个“幽灵ID”下，导致统计失真。应考虑记录告警或抛异常，而非静默兜底。
- **`_collect_failure_entries_with_meta()` 中 `artifact_roots` 的路径拼接风险**：`constants.WEB_UI_RUNS_DIR.glob("*-artifacts")` 若目录名含特殊字符（如空格、括号），`glob` 可能漏匹配；且未对 `sorted()` 结果做存在性检查，若目录不存在会静默跳过。
- **`heal_run()` 中 `max(candidate_dirs, key=...)` 可能崩溃**：若 `candidate_dirs` 为空列表（`suggestion.json` 没找到），`max()` 会抛 `ValueError`，但外层没捕获，导致 500 错误。当前只靠前面的 `if not candidate_dirs: raise ...` 保护，但 `raise` 的 detail 文案是中文，不符合 API 错误码规范。
- **`WorkbenchService.get_execution_task()` 的性能隐患**：对全部执行记录做全量循环过滤（`for row in execution_rows:`），若 `execution_rows` 有上万条，每次查单个 task 都要遍历，应考虑建立 `run_id` → index 的缓存映射，或改用数据库查询替代文件扫描。