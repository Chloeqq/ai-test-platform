# 📘 代码说明书
## 一句话概括
这是一个「自动化测试失败分析报告服务」的核心逻辑文件，专门负责从本地测试产物（截图、日志、分析文件等）中**自动扫描、整理、标准化并汇总所有失败用例的证据和元数据**，为前端报表、质量看板和人工复盘提供干净、结构化、可筛选的数据。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `workbench_reporting_service.py` | 整个测试失败分析报告系统的“数据厨房”：不生成网页，也不处理HTTP请求，只专注做一件事——把散落在磁盘各处的原始失败证据（如 `analysis.txt`、`evidence_manifest.json`、`failed.png` 等）清洗、对齐、归类、打标签，变成前端能直接渲染的 JSON 数据。 |

## 🔍 核心函数/类说明
- **`collect_failure_entries_with_meta()`**：作用——**“全盘扫楼式”收集失败证据**，是整个文件的“心脏函数”。它会扫描指定目录（如 `./artifacts/`），按时间倒序查找所有 `evidence_manifest.json` 和兼容模式下的 `analysis.txt`，把每个失败用例的截图、HTML、视频、分析结论、建议等打包成一条标准记录，并统计扫描健康度（比如多少条用了规范 manifest，多少条是“凑合用”的旧格式）。  
  - 输入：一堆路径（`artifact_roots`）、日志器、以及多个“工具函数”（比如怎么读分析文件、怎么解析 manifest、怎么标准化 case_id）  
  - 输出：一个最多 200 条的失败记录列表 `entries` + 一份扫描质量报告 `meta`（含 warning 提示、manifest 占比、健康状态等）  
  - 大白话解释：就像一个细心的质检员，拿着清单（manifest）挨个房间（case 目录）检查：有清单就按清单找证据（截图、视频、分析报告）；没清单就退而求其次，只找最基础的 `analysis.txt`。最后交给你两样东西：① 200 个最新失败案例的“证据包”（带链接、带时间、带分析）；② 一张“本次检查靠谱程度打分表”（比如“95% 案例有规范清单，很健康 ✅”或“还有 12 个案例没清单，建议补上 ⚠️”）。

- **`parse_analysis_file()`**：作用——**把人类可读的分析文本（`analysis.txt`）翻译成机器能懂的字典**。  
  - 输入：一个 `Path`（比如 `./artifacts/case-123/analysis.txt`）  
  - 输出：一个结构化的 `dict`，包含 `summary`、`failure_source`、`risk_level`、`requires_manual_review` 等字段  
  - 大白话解释：就像把一份手写的故障诊断小纸条（内容是：“Summary: 页面按钮点不动；Failure Source: page_object；Requires Manual Review: Yes”）逐行读完，填进一张标准电子表格里。它还聪明地支持两种格式：一种是冒号分隔的键值对（适合人写），另一种是结尾的 JSON 块（适合程序生成），两者都认。

- **`normalize_failure_analysis_view()`**：作用——**给每条失败分析“统一美颜滤镜”**，确保所有字段类型安全、空值合理、置信度在 0~1 之间、是否需要人工复审有明确判断。  
  - 输入：原始分析字典（可能缺字段、类型错、数值越界）  
  - 输出：一个“熨平过”的、前端可直接用的分析字典  
  - 大白话解释：就像把不同厂家送来的零件（有的螺丝长、有的螺帽松、有的没标型号）统一拧紧、贴标、装进标准包装盒。例如：把 `"requires_manual_review": "true"`、`"1"`、`"Yes"` 都转成 `True`；把 `"confidence": "95%"` 或 `"abc"` 转成 `0.0`；再根据置信度自动决定“这个结论够不够稳，要不要拉人来看”。

- **`build_report_overview()`**：作用——**生成首页总览卡片数据**（总运行数、通过率、高风险数、健康分等）+ 最近 20 个失败案例摘要。  
  - 输入：多个数据采集函数（执行记录、失败项、缺陷链接、分析标准化函数）  
  - 输出：一个嵌套字典，含 `summary`（数字指标）、`recent_failures`（案例列表）、`execution_meta`（执行元数据）  
  - 大白话解释：就像日报主编，从“失败证据库”和“执行记录库”里取数据，快速算出：今天跑了 100 次，过了 92 次（92%），但有 5 个高风险失败，健康分 86 分 → 再挑出最新 20 个失败，每条只留 case_id、标题、简要原因、是否已关联缺陷，塞进首页瀑布流。

- **`build_report_failures()`**：作用——**支持高级筛选的“失败案例明细页”数据生成器**（按 case_id、关键词、是否已关联缺陷过滤）。  
  - 输入：筛选条件（case_id/keyword/defect_status）+ 同上的一套数据函数  
  - 输出：最多 80 条详细失败记录 `items` + 本次扫描的 `evidence_meta`（同上）  
  - 大白话解释：就像数据库的“高级搜索”，你输入“case-456”就只看这一个用例的所有失败；输入“登录”就搜标题/原因/缺陷号里含“登录”的；选“未关联缺陷”就只显示还没填 Jira 的条目。每条返回完整证据路径（截图在哪、视频在哪、分析原文在哪）。

- **`resolve_run_failure_snapshot()`**：作用——**根据 run_id 快速定位某次运行的最新失败详情**（用于点击某次运行 → 跳转到它的失败快照）。  
  - 输入：run_id 字符串 + 查找函数 `find_run_item` + 规范化函数等  
  - 输出：该 run 下最新失败的标准化视图（含 analysis、suggestion、截图路径等）  
  - 大白话解释：就像查快递单号——你输入 `run-789`，它先去“运行总台账”里找到这条记录，如果台账里已经缓存了最新失败，直接返回；如果没有，就去它的 artifacts 目录里现场扫描一次，找出第一个失败案例并打包好给你。

## 🧩 调用关系与数据流转
```
[前端请求] 
    ↓ （如 /api/report/overview）
build_report_overview() 
    ↓ 调用
collect_execution_records_with_meta() → 返回 [run_entries, execution_meta_raw] 
    ↓ 传入
normalize_execution_meta(execution_meta_raw) → 返回 execution_meta（含 readiness_score）
    ↓ 同时调用
collect_failure_entries() 
    ↓ 实际委托给
collect_failure_entries_with_meta() → 返回 [entries, evidence_meta_raw] 
    ↓ 传入
normalize_failure_evidence_meta(evidence_meta_raw) → 返回 evidence_meta
    ↓ entries 中每个 item["analysis"] 经过
normalize_failure_analysis_view() → 标准化分析字段
    ↓ 同时关联缺陷
read_defect_items() → 构建 defect_map → 注入到 recent_failures["defects"]

→ 最终组装成 { summary, recent_failures, execution_meta }

其他流程类似：
- /api/report/failures?case_id=xxx → build_report_failures() → collect_failure_entries_with_meta() → ... 
- /api/run/xxx/failure → resolve_run_failure_snapshot() → find_run_item() → (cache or scan) → normalize_failure_entry_view()
- /api/report/performance → build_report_performance() → collect_execution_records_with_meta() → 解析 duration
```

## 💡 值得学习的写法
- **“函数即配置”设计**：所有 I/O 操作（读文件、查数据库、调命令）都通过参数传入可替换的函数（如 `ReadDefectItems`, `RunCommand`），让核心逻辑完全脱离具体环境（本地文件？S3？API？），单元测试时只需 mock 这些函数，干净又灵活。
- **双模容错扫描**：`collect_failure_entries_with_meta()` 同时支持 `manifest-first`（严格模式，优先用规范清单）和 `compat_scan`（兼容模式，fallback 到 `analysis.txt`），并通过 `meta` 返回清晰的占比和健康建议，既保向后兼容，又引导团队逐步迁移到规范流程。
- **“最后一段 JSON”智能提取**：`_parse_last_json_object()` 在 `analysis.txt` 末尾尝试提取 JSON 块，让 AI 生成的分析报告（常以 JSON 结尾）能被无缝解析，无需修改旧的文本解析逻辑，巧妙兼顾人写和机生。
- **置信度安全钳制**：`ClampConfidence` 类型提示 + `clamp_confidence()` 函数（虽未定义在此文件，但被多处调用）暗示存在统一的置信度归一化逻辑，避免 `1.5` 或 `-0.2` 这类非法值污染下游判断。
- **健康分（readiness_score）量化设计**：`normalize_execution_meta()` 中用加权公式（`manifest_first_ratio * 0.55 + ...`）将抽象的“流程规范度”转化为 0~1 的数字，并映射到 `ready/caution/blocked` 三级状态，让质量改进目标可衡量、可追踪。

## ⚠️ 需要注意的地方
- **`collect_failure_entries_with_meta()` 的 `artifact_roots` 必须是绝对路径且存在**：函数内部用 `artifact_root.exists()` 做守门，如果传入相对路径或不存在的路径，会静默跳过，导致“找不到失败项”却无报错，排查时容易忽略此处。
- **`parse_analysis_file()` 对 `analysis.txt` 格式强依赖**：它假设每行是 `Key: Value` 形式，且关键字段名（如 `"Failure Source"`）必须完全匹配 `key_map`。如果测试框架输出的字段名变了（如 `"Failure Source"` → `"Root Cause"`），该函数就无法提取，需同步更新 `key_map`。
- **`normalize_failure_analysis_view()` 的 `requires_manual_review` 是“推断”出来的**：它综合 `failure_source` 是否为空、置信度是否低于阈值等多个条件自动判断，**不是原始数据字段**。如果业务规则变化（如“所有 page_object 都要人工看”），必须改这里，而非上游数据源。
- **`ensure_allure_snapshot()` 的快照清理逻辑有竞态风险**：它用 `shutil.rmtree(stale)` 删除旧快照，但若多个进程同时调用（如并发刷新报告），可能因目录正被读取而失败（`ignore_errors=True` 会吞掉错误），导致磁盘空间缓慢增长。
- **`list_defect_items()` 和 `load_defect_items()` 的 `case_id` 归一化时机易混淆**：`list_defect_items(case_id="CASE-123", ...)` 会先归一化 `case_id`，再筛选；但 `load_defect_items()` 传入空字符串，会返回全部缺陷。若误用 `list_defect_items("", ...)` 期望全量，实际会归一化成空字符串导致筛选结果为空，应直接用 `load_defect_items()`。