# 📘 代码说明书
## 一句话概括
这是一个「测试用例一致性守门员」服务：它帮系统自动检查、过滤和清理那些**不在正式用例库里的测试记录和报告文件**，确保只有被认可的用例（比如在测试管理平台里登记过的）才能留下，其他杂乱的、过时的或无效的测试数据会被悄悄移除。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `workbench_case_consistency_service.py` | 提供一整套「用例白名单过滤 + 无关测试产物清理」的功能，像一位细心的档案管理员，只保留合规的测试资料，清理掉所有“黑户”测试项及其生成的文件。 |

## 🔍 核心函数/类说明
- **`normalize_business_case_id(value: Any) -> str`**：把各种五花八门的用例 ID（比如 `"CASE-123 "`、`None`、`123`、`"case_123"`）统一变成标准小写、干净、合法的格式（如 `"case-123"`），如果根本不像用例 ID 就返回空字符串。
  - 输入：任意类型的数据（字符串、数字、None、甚至字典等）
  - 输出：标准化后的用例 ID 字符串（合法时）或空字符串（不合法/无法识别时）
  - 大白话解释：就像身份证号录入系统——你手写“京A12345”、打字“京a12345 ”、甚至糊了半张纸的复印件，它都能帮你擦干净、转成统一格式 `"jia12345"`；但如果交来一张“苹果手机截图”，它就默默说：“这不算身份证，不要”。

- **`load_case_center_case_ids(db: Session) -> set[str] \| None`**：从数据库里把所有「已在测试中心正式登记」的用例 ID 全部捞出来，整理成一个去重的集合（比如 `{"case-001", "case-002", "bug-456"}`）。
  - 输入：SQLAlchemy 数据库会话（相当于一把打开数据库抽屉的钥匙）
  - 输出：合法用例 ID 的集合（成功时）或 `None`（查库失败时，比如数据库断了）
  - 大白话解释：去公司人事系统导出一份「已转正员工花名册」，用来当后续筛选的权威名单；万一系统崩了导不出来，就先不筛，放行所有。

- **`is_case_tracked(case_id: Any, *, case_center_case_ids: set[str] \| None) -> bool`**：快速判断某个用例 ID 是否在「正规军名单」里。
  - 输入：待查的用例 ID（任意格式）+ 已加载的白名单（可能为 `None`）
  - 输出：`True`（是正规军）或 `False`（是临时工/黑户/格式错误）
  - 大白话解释：保安大叔看一眼你工牌上的编号，再对照手里的花名册——有名字？放行 ✅；没名字 or 工牌糊了？拦下 ❌；花名册丢了？那今天全放行（宽松模式）。

- **`filter_records_by_case_center(...)`**：用白名单对一批测试记录（比如 API 返回的 JSON 列表）做「安检式过滤」——只留下 ID 在名单里的记录，其余扔进“待审核区”并统计谁被拦下了。
  - 输入：原始记录列表 + 白名单 + 如何从每条记录里取 ID 的方法（默认找 `"case_id"` 字段）
  - 输出：✅ 过滤后的干净记录列表 + 📊 一份安检报告（放行多少、拦截多少、拦截了哪些 ID）
  - 大白话解释：快递分拣站——扫描每个包裹上的单号，只把单号在「今日允许派送区域清单」里的包裹装车，其余贴上“暂存”标签并记下单号，方便后面复盘。

- **`cleanup_execution_report_files(...)`**：专门打扫「测试执行报告文件」——删除那些用例 ID 不在白名单里的 `.report.json` 和配套的 `.md` 报告文件，连带清理孤零零的 `.md`（没有对应 `.json` 的“孤儿报告”）。
  - 输入：报告文件存放目录路径 + 白名单
  - 输出：清理动作报告（删了哪些文件、哪些用例 ID 被清掉了、共删几个）
  - 大白话解释：整理书房——先把所有书按书脊上的编号查一遍「官方推荐书单」，不在单子上的书（比如野鸡出版社的《三天速成量子力学》）连书带读书笔记一起扔掉；连笔记都没编号的“流浪笔记”，也顺手清了。

- **`cleanup_allure_artifacts(...)`** 和 **`cleanup_execution_task_artifacts(...)`**：批量清理 Allure 测试报告生成器（类似测试界的PPT制作工具）和自动化任务运行器产生的临时文件夹/文件，确保磁盘不被垃圾占满。
  - 输入：各个产物存放目录路径（如 allure-results、allure-report、快照文件夹等）
  - 输出：清理报告（删了哪些路径、共删几个）
  - 大白话解释：定期大扫除——清空“草稿箱”（allure-results）、“废稿堆”（allure-snapshots”）、甚至可选清空“终稿展示厅”（allure-report），再把空抽屉重新摆整齐（自动创建空目录）。

## 🧩 调用关系与数据流转
```
[主流程入口，比如 FastAPI 接口或定时任务]
        ↓
load_case_center_case_ids() → 得到白名单 set[str] 或 None  
        ↓（传给下游所有函数作为核心参数）
        ├─→ is_case_tracked()           # 单个 ID 快速校验（轻量级）
        ├─→ filter_records_by_case_center()  # 批量过滤内存中的记录（JSON 列表）
        └─→ cleanup_execution_report_files() # 批量清理磁盘上的报告文件（JSON/MD）
                ↓（内部还会调用 normalize_business_case_id 解析文件名或文件内容）
                ↓（发现孤儿 .md 文件时，也会调用它解析文件名）

cleanup_allure_artifacts() 和 cleanup_execution_task_artifacts()
        ↓（各自独立调用 _cleanup_directory_contents() 这个通用清空文件夹工具）
        ↓（_cleanup_directory_contents() 是纯路径操作，不涉及用例 ID 逻辑）
```

> 💡 小提示：所有「清理类函数」都不依赖数据库白名单就能运行（比如白名单为 `None` 时，它们只是跳过业务过滤，但仍会执行基础清空动作），所以即使测试中心暂时连不上，系统也能安全地做磁盘维护。

## 💡 值得学习的写法
- **`case_id_resolver: RecordCaseIdResolver | None = None` 默认 lambda**：用 `lambda row: row.get(case_id_key)` 作为兜底提取器，让函数既支持固定字段名（`"case_id"`），又能被用户自定义逻辑覆盖（比如从嵌套 `row["metadata"]["test_id"]` 取值），灵活又不破坏默认体验。
- **`removed_case_ids: set[str] = set()` → `sorted(removed_case_ids)`**：用 `set` 自动去重 + `sorted` 保证输出顺序稳定，方便日志比对和前端展示，细节很贴心。
- **双保险解析 report_case_id**：先从文件名猜（快），失败再读文件内容（慢但准），兼顾性能与鲁棒性，像快递员先看面单，面单模糊再拆开看内件单。
- **`shutil.rmtree(..., ignore_errors=True)` + `unlink(missing_ok=True)`**：清理文件时不怕“目标已消失”，避免因竞态条件（比如另一进程刚删了它）导致整个清理流程崩溃，稳如老狗。
- **所有函数都返回结构化字典报告**（含 `enforced: bool`, `removed_count` 等字段）：下游无论是打印日志、存数据库还是返回给前端，都有一致、可解析的反馈，不用再手动拼字符串。

## ⚠️ 需要注意的地方
- **`normalize_business_case_id("")` 或 `None` 会返回空字符串**：如果上游传入空值（比如数据库字段为 NULL），它不会报错而是静默吞掉——这虽安全，但可能掩盖数据质量问题（比如本该有 ID 却为空），建议在关键入口加日志告警。
- **`filter_records_by_case_center()` 中 `row[case_id_key] = normalized_case_id` 会修改原始 record**：如果传入的是共享的、不可变的数据源（比如全局缓存里的 dict），这里会意外污染原数据！应改为 `row = {**record, case_id_key: normalized_case_id}` 深拷贝更安全。
- **`cleanup_execution_report_files()` 对 `.md` 孤儿文件的清理逻辑较复杂**：它先扫一遍 `.report.json`，再单独扫 `.report.md` 找孤儿，但若存在 `xxx.report.md` 和 `xxx.report.json` 同时存在却 ID 不匹配的情况，当前逻辑会漏删（因为只按文件名前缀匹配，未校验内容）。实际中虽少见，但属于逻辑盲区。
- **`cleanup_allure_artifacts()` 的 `clear_report_root` 参数命名易误解**：它控制的是是否清空 `allure_report_root` 目录，但变量名 `clear_report_root` 看起来像“是否启用清理功能”，其实它是「要不要连报告展厅一起清」的开关——建议改名如 `clear_allure_report_dir` 更直白。
- **无异常重试机制**：所有数据库查询、文件读写失败都直接返回 `None` 或空结果（如 `load_case_center_case_ids`），上层需自行处理降级逻辑（比如用缓存白名单），否则可能导致大面积放行（宽松模式）却不通知运维。