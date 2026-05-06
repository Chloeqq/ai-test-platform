# 📘 代码说明书
## 一句话概括
这是一个「自动化测试运行管家」——它负责从用户点击“开始测试”那一刻起，到测试跑完、生成报告、整理证据、判断是否通过的**全流程调度与数据组装服务**。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `workbench_runtime_service.py` | 提供测试用例执行的生命周期管理能力：创建任务、启动子进程运行 pytest、收集日志/截图/视频/报告、融合多来源数据（内存+磁盘）、生成统一视图供前端展示。 |

## 🔍 核心函数/类说明
- **`start_run()`**：作用——用户点“运行”时的入口，像「餐厅下单员」：记下订单（run_id）、准备餐具（log/artifacts目录）、填单子（execution_record）、把单子塞进后厨（启动线程执行）。
  - 输入：项目名、用例ID、用例文件路径、来源（手动/自动）、存放日志和产物的根目录等。
  - 输出：一个结构化、带实时状态的「运行视图」（含 run_id、状态、路径、时间、执行记录等）。
  - 大白话解释：它不直接跑测试，而是**快速开个工单 + 启动后台厨师（子进程）去炒菜（跑测试）**，自己立刻返回一张带编号的取餐号（run_id）和菜单预览，让用户不用干等。

- **`execute_run()`**：作用——真正的「后厨大厨」，调用 `pytest` 执行测试，像「流水线工人」：拼命令、设环境变量、启动进程、实时记日志、跑完再生成 Allure 报告、最后更新状态。
  - 输入：`start_run()` 生成的 `job` 字典（含路径、ID、环境等）。
  - 输出：无返回值，但会通过 `update_job` / `update_runtime_run` 修改数据库/内存中的任务状态。
  - 大白话解释：它就是那个**撸起袖子真干活的人**——打开终端、敲命令、盯着输出、存截图、录视频、打包报告，最后在工单上盖章写“已做完，结果：成功/失败”。

- **`runtime_view_from_entry()`**：作用——「数据整容师」，把零散、格式不一的原始数据（内存里的 job、磁盘里的 execution_record.json、AI 分析结果、人工审批记录…）**融合成一份干净、统一、前端能直接渲染的「测试运行档案」**。
  - 输入：一个原始数据源（比如刚查出来的 job 或磁盘里读到的记录），以及一堆“加工工具”（如 `build_page_analysis_context`、`build_execution_gate` 等回调函数）。
  - 输出：一个字段齐全、逻辑自洽的字典（例如包含 `page`, `risk_summary`, `execution_gate`, `review_audit_timeline` 等）。
  - 大白话解释：就像把厨房小票、厨师笔记、质检报告、顾客评价、经理批注……全摊在桌上，**按固定模板抄写成一份标准体检报告**，让医生（前端）一眼看懂这个人（这次测试）到底怎么样。

- **`load_runtime_execution_record_from_artifacts()`**：作用——「磁盘侦探」，在测试产物文件夹里翻箱倒柜，找最靠谱的执行记录（`execution_record.json` 或通过 `evidence_manifest.json` 定位）。
  - 输入：产物目录路径（如 `runs/abc123-artifacts/`），以及几个用于清洗数据的回调函数（如 `normalize_evidence_manifest_payload`）。
  - 输出：从磁盘读出并清洗后的执行记录字典，找不到就返回空字典。
  - 大白话解释：测试跑完后，结果可能藏在好几个地方（直接生成的 JSON、或通过清单文件指向的 JSON）。这个函数就像**派个侦探去文件夹里按时间倒序翻找，找到最新、最完整的那张「成绩单」**。

- **`find_run_item()`**：作用——「寻人启事发布者」，根据 `run_id` 在内存（运行中列表）和持久化存储（job 数据库）里找对应的任务。
  - 输入：`run_id` 字符串，以及查找用的两个函数（`read_runtime_runs` 和 `get_job`）。
  - 输出：找到的任务视图（经过 `runtime_view_with_execution_record_preferred_fn` 加工），没找到返回 `None`。
  - 大白话解释：用户想查“abc123 这次跑得咋样？”，它先问内存：“还在跑吗？” → 没有就问数据库：“存档里有吗？” → 都没有才说“查无此人”。

## 🧩 调用关系与数据流转
```
用户触发运行
    ↓
start_run() 
    → 生成 job 字典 + 创建目录 + 调用 store_run_job() 存档 + append_runtime_run() 写入内存列表
    → 启动新线程，调用 execute_run(job)
        ↓
        execute_run()
            → build_run_command_fn() 拼出 pytest 命令和环境变量
            → subprocess.Popen() 执行命令，实时写 log
            → subprocess.run() 调用 allure 工具生成报告
            → load_runtime_execution_record_from_artifacts() 从产物目录读 execution_record
            → collect_failure_entries() + is_within() 找本次失败详情
            → update_job() 和 update_runtime_run() 更新状态和数据
        ↓
        （线程结束）

用户查询状态（如轮询 /api/runs/{id}）
    ↓
find_run_item(run_id)
    → 先遍历 read_runtime_runs()（内存中正在跑/刚结束的列表）
    → 没找到则调用 get_job()（查数据库）
    ↓
    → 将查到的原始数据传给 runtime_view_with_execution_record_preferred_fn()
        ↓
        runtime_view_with_execution_record_preferred_fn()
            → 先调用 runtime_view_from_entry_fn() 做基础融合
            → 再尝试用 load_runtime_execution_record_from_artifacts() 从磁盘捞最新 execution_record
            → 若捞到，用磁盘数据「覆盖增强」内存数据（优先级更高）
        ↓
        返回最终统一视图给前端
```

## 💡 值得学习的写法
- **高度可插拔的「策略模式」设计**：所有 `BuildXXX`、`LoadXXX`、`NormalizeXXX` 都是 `Callable` 类型别名，意味着它们不是硬编码的具体函数，而是**可随时被替换成不同实现的「插槽」**（比如换用另一个 AI 模型分析页面，只需传入新函数，不用改主逻辑）。
- **「数据优先级融合」逻辑清晰**：`runtime_view_with_execution_record_preferred()` 明确规定了「内存数据为底稿，磁盘产物为权威补充」，当磁盘有更完整/更新的数据时，自动合并覆盖关键字段（如 status、times、return_code），避免“内存过期”问题。
- **健壮的 JSON 解析 `extract_json_from_text()`**：不依赖完整 JSON，能从任意文本（如日志混杂输出）中智能截取最后一段 `{...}` 并解析，极大提升日志解析容错性。
- **`resolve_manifest_entries()` 的路径安全处理**：自动将相对路径转为绝对路径，并严格校验是否存在、是否为文件，防止路径遍历攻击或误读无效路径。
- **`wait_run_terminal()` 的优雅超时轮询**：用 `time.time()` + `sleep(0.5)` 实现非阻塞等待，既不卡主线程，又避免高频请求，还支持自定义超时。

## ⚠️ 需要注意的地方
- **`runtime_run_id()` 函数的隐式 fallback 风险**：它先从 `item["run_id"]` 取，再 fallback 到 `item["execution_record"]["run_id"]`。如果 `item` 结构异常（如 `execution_record` 是字符串而非 dict），会静默返回空字符串，导致后续 `find_run_item()` 查不到 —— **建议加日志或抛明确异常**。
- **`build_runtime_execution_record()` 中 `started_at or created_at` 的歧义**：当 `started_at` 为空时用 `created_at` 填充，但 `created_at` 是任务创建时间，而 `started_at` 应是进程真正启动时间。两者语义不同，**混用可能导致时间轴错乱（如排队耗时被算进执行耗时）**。
- **`execute_run()` 中 `popen_fn` 的 stdout 读取方式有死锁风险**：使用 `iter(process.stdout.readline, "")` 是安全的，但若 pytest 输出巨大且无换行，`readline()` 可能阻塞；更稳妥做法是用 `threading.Thread` 单独读取 stdout/stderr，或改用 `subprocess.run(..., timeout=...)`。
- **`normalize_case_id()` 调用未在本文件定义**：它来自 `shared_backend.case_ids`，但本文件未做 `try/except` 包裹。若该函数抛异常（如输入 None），会导致 `runtime_view_from_entry()` 整个流程崩溃 —— **所有外部依赖调用都应加防御性 try/catch**。
- **`is_within()` 函数未提供实现**：它是作为参数传入的，但调用方若传入一个有 bug 的实现（如未处理符号链接），可能导致 `collect_failure_entries()` 漏掉失败项 —— **关键路径的工具函数必须确保其契约（如路径合法性校验）被严格执行**。