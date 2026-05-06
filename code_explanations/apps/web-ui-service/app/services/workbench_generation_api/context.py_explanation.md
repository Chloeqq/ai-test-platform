# 📘 代码说明书
## 一句话概括
这是一个为“工作台（Workbench）自动化测试生成系统”准备的**上下文配置中心**——它像一个精心组装好的“工具箱+说明书+调度员”三合一包，把所有分散的服务、路径、时间、API 客户端、数据处理函数等全部打包好，让后续的生成、运行、评审、风险评估等流程能“即插即用”，不用每次重复找工具、配参数、查路径。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `workbench_generation_api/context.py` | 构建整个工作台系统运行所需的完整上下文环境，包含运行时（runtime）、生成（generation）和全局（core）三层能力，是系统启动和功能调用的“中央枢纽”。 |

## 🔍 核心函数/类说明
- **`build_workbench_runtime_context()`**：作用是**组装一个“运行时工具箱”**，把所有和“执行测试、读写文件、处理报告、等待结果”相关的函数和常量打包成一个结构清晰的对象（`WorkbenchRuntimeContext`）。  
  - 输入：无显式参数（内部自动读取配置、服务实例、路径等）  
  - 输出：一个冻结（不可修改）的 `WorkbenchRuntimeContext` 实例，里面全是可直接调用的函数和路径常量  
  - 大白话解释：就像你去厨房做饭，这个函数不是在炒菜，而是在**提前把刀、砧板、酱油、计时器、菜谱、冰箱位置、水龙头开关方式……全都按你习惯的方式摆好、贴好标签、装进一个带分格的收纳箱里**。后面任何人（比如“开始执行测试”的函数）只要拎起这个箱子，就能立刻找到需要的东西，不用再满厨房翻找。

- **`build_workbench_context(db: Session)`**：作用是**组装整个工作台系统的“总控台”**，把数据库连接、AI协调服务（Orchestrator）、特征开关、生成规则引擎、以及上面那个“运行时工具箱”全部整合成一个统一入口（`WorkbenchContext`）。  
  - 输入：一个 SQLAlchemy 的数据库会话 `db`（相当于一把打开数据库抽屉的钥匙）  
  - 输出：一个冻结的 `WorkbenchContext` 实例，是整个系统对外暴露的“万能遥控器”  
  - 大白话解释：这就像把厨房收纳箱（runtime）、冰箱里的食材库存（db）、智能菜谱AI（orchestrator）、调料使用指南（flags）、自动切菜机（scenario_engine）……全放进一个带触摸屏的智能料理台里。你点“生成新测试用例”，它就知道该调哪个AI、查哪张表、用哪个工具箱里的函数、存到哪个文件夹——**你只管发指令，它负责背后所有协作**。

- **`WorkbenchRuntimeContext`（dataclass）**：作用是**一个“只读的函数电话簿 + 路径地图 + 时间日历”合集**，它本身不干活，但让你能快速拨通任意服务、定位任意文件夹、获取当前时间。  
  - 输入：无（它是被构建出来的“成品”）  
  - 输出：无（它是一个容器，供别人调用其内部字段）  
  - 大白话解释：它就像你手机里的“快捷联系人”APP——没有“打电话”动作，但里面存了“王师傅（切菜）→ `build_surface_element_candidates`”、“李工（报告）→ `report_allure_refresh`”、“张经理（路径）→ `ALLURE_REPORT_ROOT`”……还自带“现在几点？→ `now_iso()`”。你点谁，就自动跳转到对应服务，**零记忆成本，所见即所得**。

- **`_run_orchestrator_risk()`（闭包函数）**：作用是**定制一个专用的“风险评估请求发送器”**，专门用来把测试需求、执行计划、失败记录等打包发给后端AI服务做风险打分。  
  - 输入：`requirement_spec`, `execution_plan`, `execution_record`, `failure_analysis`, `failure_triage`（都是字典格式的数据）  
  - 输出：AI服务返回的风险评估结果（字典）  
  - 大白话解释：就像你有个固定快递单模板（收件人是“风控AI部”，地址是`/risk/evaluate`），每次填好“要测什么”“怎么测”“测崩了几次”“上次怎么修的”这几栏，一按“发送”，它就自动帮你贴单、扫码、发走，并把回执（风险报告）拿回来交给你。

## 🧩 调用关系与数据流转
```
[FastAPI路由] 
    ↓（传入 db）
build_workbench_context(db) 
    ↓（组装）
├─→ WorkbenchContext（总控台）  
│   ├─→ db（数据库钥匙）  
│   ├─→ orchestrator_client（AI服务遥控器）  
│   ├─→ flags（功能开关面板）  
│   ├─→ runtime = build_workbench_runtime_context()  ← 这里触发下面整条链  
│   └─→ generation（生成逻辑遥控器）  
│        ↓（内部用到 runtime 的函数）  
│        └─→ runtime.build_requirement_spec_for_risk(...)  
│             ↓（调用）  
│             └─→ _run_orchestrator_risk(...) → 发HTTP请求到AI服务  
│  
└─→ build_workbench_runtime_context()  
     ↓（组装）  
     WorkbenchRuntimeContext（运行时工具箱）  
          ├─→ start_run(...) → 调用 workbench_runtime_service.start_run(...)  
          │      ↓（内部用到）  
          │      ├─→ build_runtime_execution_record(...)  
          │      ├─→ store_run_job(...)（内存缓存）  
          │      └─→ execute_run(...) → 调用 workbench_runtime_service.execute_run(...)  
          │             ↓（内部用到）  
          │             ├─→ build_run_command(...) → 拼出终端命令  
          │             ├─→ get_python_bin(...) → 找Python解释器  
          │             └─→ collect_failure_entries(...) → 调用 reporting_service...  
          │  
          ├─→ wait_run_terminal(...) → 轮询查“测试跑完没？”  
          │      ↓（内部用到）  
          │      └─→ find_run_item(...) → 先查内存缓存，再查磁盘JSON文件  
          │  
          └─→ evaluate_risk_report(...)  
                 ↓（内部用到）  
                 ├─→ find_run_item(...)  
                 ├─→ run_orchestrator_risk(...)（就是上面那个快递发送器）  
                 └─→ build_risk_report(...)（整理AI回执成易读报告）  
```

## 💡 值得学习的写法
- **函数式组装（Functional Composition）**：大量使用 `partial()` 把“通用函数 + 固定参数”提前打包成专用函数（如 `review_decisions_for_run_fn=partial(...)`），避免每次调用都重复传一堆相同参数，既安全又简洁，像预制菜包——主料+固定调料已配好，下锅即炒。
- **“别名代理”设计（`__getattr__` 动态转发）**：`WorkbenchRuntimeContext` 内部用 `__getattr__` 自动把 `_xxx` 形式的私有方法名映射到公开名（如 `_find_run_item` → `find_run_item`），既保持内部命名规范（加下划线表示“建议别直接用”），又对外提供干净接口，类似“前台接待员”——客户喊“找王经理”，她自动转接给后台叫“小王”的同事，客户无需知道真实工号。
- **内存+磁盘双缓存策略**：`run_jobs` 字典（内存）和 `RUNTIME_RUNS_FILE` JSON文件（磁盘）并存，`_get_job` 先查内存快，查不到再扫磁盘，兼顾速度与可靠性，像手机通讯录——常用联系人放内存（RAM），全部联系人存硬盘（ROM），开机秒开又不丢数据。
- **“兜底默认值”防御式编程**：所有字典参数都用 `if isinstance(x, dict) else {}` 防止空/错类型导致崩溃（如 `requirement_spec if isinstance(...) else {}`），就像汽车安全带——不一定每次都用上，但万一出事就是保命的。

## ⚠️ 需要注意的地方
- **`_is_within()` 函数的静默失败风险**：当 `Path.resolve()` 抛异常（比如路径含非法字符、权限不足）时，它直接返回 `False` 而非报错。如果业务逻辑依赖“必须在某个目录内”，这里可能悄悄跳过校验，变成安全隐患（比如用户上传恶意路径试图越权访问）。✅ 建议：至少加日志警告，或改用更健壮的路径校验库。
- **`run_jobs` 缓存无自动过期机制**：内存中的 `run_jobs` 字典靠 `threading.Lock` 保证线程安全，但没有 TTL（生存时间）清理，长期运行可能内存泄漏。虽然有 `_RUN_JOB_TTL_SECONDS` 常量，但代码里并未实际使用它来定期清理。✅ 建议：加个后台线程或定时任务，定期清理超时的 job。
- **`WorkbenchRuntimeContext` 的 `__getattr__` 是最后防线**：如果调用了一个根本不存在的属性（比如拼错成 `fin_run_item`），它不会立刻报错，而是走到 `raise AttributeError(name)`，但此时调用栈已很深，错误提示不够直观（显示在 `__getattr__` 而非原始调用行）。✅ 建议：在开发环境开启严格模式，或加个调试钩子打印“尝试访问未定义属性”。
- **环境变量解析脆弱**：`_RUN_JOB_TTL_SECONDS = int(str(os.getenv(...)) or "300")` 这行，如果 `os.getenv` 返回 `None`，`str(None)` 变成 `"None"`，`int("None")` 会直接崩溃。虽然后面有 `or "300"`，但 `str(None)` 不是空字符串，所以 `or` 不生效。✅ 正确写法应为 `os.getenv(...) or "300"` 再 `int()`。