# 📘 代码说明书
## 一句话概括
这是一个测试工作台（Workbench）的「门面层」（Facade），像一个智能管家，把后台各种复杂服务（生成用例、执行测试、分析失败、管理资产等）统一包装成简单易用的接口，供前端（如网页）调用。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `facade.py` | 提供统一、简洁、健壮的 API 入口，屏蔽底层服务细节和错误处理逻辑，让上层调用者（如 FastAPI 路由）只需关心“要做什么”，不用操心“怎么做”和“出错了怎么办”。 |

## 🔍 核心函数/类说明
- **`class WorkbenchFacade`**：整个文件的主角，是一个“测试工作台总管家”。
  - 输入：可选传入一个 `WorkbenchService` 实例（相当于它的执行团队）；后续每个方法会接收具体业务参数（如 `case_id`, `project`, `payload` 等）和数据库连接 `db`。
  - 输出：返回结构清晰的字典（`dict[str, Any]`），通常是 `{ "item": ..., "items": [...], "message": ... }` 这样的格式，方便前端直接展示。
  - 大白话解释：它不自己干活，而是指挥各个专业部门（`workbench_asset_service`, `workbench_runtime_service`, `workbench_reporting_service` 等）去完成任务，并把各部门交上来的报告（可能是一份测试结果、一个用例列表、一个质量概览）整理好、加个封面（统一格式）、盖个章（加时间戳/请求ID），再递给前台。比如你跟管家说“我要查 mall 项目下第1页的测试用例”，它就去翻资产目录、过滤无效用例、分页、加详情链接，最后给你一份干净整齐的清单。

- **`_get_json(url: str, ...)`**：一个“稳重的快递员”。
  - 输入：一个 URL 地址（比如调用另一个微服务的地址），可选超时时间。
  - 输出：从该 URL 成功获取并解析后的 Python 字典（`dict`）。
  - 大白话解释：它负责安全地向外部系统（比如“编排器” orchestrator）发 HTTP 请求取数据。它自带“防身术”——如果对方服务器没响应（超时）、挂了（502）、返回乱码（不是 JSON）、或者返回错误码（4xx/5xx），它不会让整个程序崩溃，而是把错误信息记下来（打日志），然后转化成标准的 `HTTPException` 抛给上层，让前端能友好提示用户“服务暂时不可用”而不是看到一串报错。就像快递员发现收件人地址错误或家里没人，不会扔掉包裹，而是拍照留证，然后打电话告诉你。

- **`_safe_case_id(value: str)`** 和 **`_normalize_optional_project_code(value: Any)`**：两个“细心的登记员”。
  - 输入：任意值（字符串、None、数字等）。
  - 输出：清洗后的小写、去空格字符串（如 `"MALL-001 "` → `"mall-001"`），或空字符串。
  - 大白话解释：它们专门负责处理用户输入的 ID 和项目名。因为用户可能手误多打空格、大小写混用（`"Mall"` vs `"mall"`），或者根本没填（`None`）。这两个函数就像前台接待，先帮你把身份证号、公司名规整好、标准化，再交给后面的流程，避免后面因为格式问题找不到对应的数据。

- **`_manual_point_from_candidate(...)`** 和 **`_candidate_from_asset_point(...)`**：两个“翻译官”。
  - 输入：一个原始的候选测试点数据（可能是 AI 生成的、手工录入的、或是从旧文件读出来的）。
  - 输出：一个符合内部统一标准的、结构化的测试点字典（包含 `key`, `steps`, `expected_result`, `confidence` 等字段）。
  - 大白话解释：不同来源的数据长得都不一样（AI 给的叫 `intent_id`，老系统存的叫 `key`，手工填的叫 `title`）。这两个函数就是把五花八门的“方言”翻译成工作台内部通用的“普通话”，确保所有数据都能被后续的分析、执行、展示模块正确理解。比如把 `{"title": "登录", "steps": ["输入账号", "点击登录"]}` 翻译成标准格式，补全缺失的 `key`、`confidence` 等字段。

## 🧩 调用关系与数据流转
```
前端请求 (如 /api/workbench/cases?project=mall&page=1)
        ↓
WorkbenchFacade.list_cases() ← 主入口，管家接单
        ↓
├─ store.ensure_dirs() → 确保磁盘目录存在（如创建 ./test-points/mall/）
├─ workbench_case_consistency_service.load_case_center_case_ids(db) → 从数据库加载“官方认可的用例ID清单”
├─ workbench_asset_service.collect_case_items(...) → 去磁盘上扫描所有项目下的 .yaml 或 .json 测试用例文件
│        ↓
├─ workbench_case_consistency_service.filter_records_by_case_center(...) → 用“官方清单”过滤掉无效/过期的用例
│        ↓
└─ workbench_asset_service.build_cases_payload(...) → 把过滤后的用例列表，加上分页、详情链接、状态图标等，组装成最终返回给前端的 JSON 包

另一条路径：前端请求 /api/workbench/run
        ↓
WorkbenchFacade.run_case() ← 接单
        ↓
├─ _safe_case_id() → 规范化 case_id
├─ workbench_case_consistency_service.is_case_tracked() → 查数据库确认这个用例是合法的
├─ workbench_asset_service.resolve_case_yaml_path(...) → 找到这个用例对应的 .yaml 文件在磁盘上的位置
├─ workbench_runtime_service.start_run(...) → 创建一个“运行任务”，生成 run_id，写入运行队列
        ↓
        workbench_runtime_service.execute_run(...) → 真正执行！调用命令行启动测试框架
                ↓
                测试框架运行 → 生成 allure 报告、截图、日志 → 存入 ./web-ui-runs/ 目录
                        ↓
                        store.append_runtime_run(...) → 把这次运行的摘要（run_id, case_id, 开始时间...）记入运行历史
```

## 💡 值得学习的写法
- **“防御式编程”无处不在**：几乎所有函数开头都有 `_text()`、`_safe_case_id()`、`_normalize_optional_project_code()` 这类清洗函数，对任何可能为 `None`、空字符串、格式混乱的输入做预处理，极大提升了代码鲁棒性。
- **错误处理的“三层封装”**：`_get_json()` 是典型代表 —— 底层捕获原始异常（`HTTPError`, `URLError`），中间层统一记录带上下文的日志（`summarize_http_context`），最上层抛出语义明确的 `HTTPException`（状态码+用户友好的 `detail`）。这比裸抛 `Exception` 或只打日志强太多。
- **高阶函数注入（Dependency Injection）**：在 `run_case()` 等方法中，大量使用 `lambda` 将具体服务函数（如 `_build_runtime_execution_record`, `_runtime_view_from_entry`）作为参数传入底层服务（如 `workbench_runtime_service.start_run`）。这使得底层服务逻辑可以复用，而具体行为（比如用哪个函数来构建视图）由门面层灵活决定，解耦且便于测试。
- **“降级”（Degradation）设计**：`dashboard_overview()` 方法里，一旦数据库查询或计算出错，立刻 `except Exception:` 捕获，并返回一个精心构造的 `_default_overview(...)` —— 一个充满占位符但结构完整、前端能正常渲染的“兜底视图”。用户看到的是“暂无数据”，而不是一片空白或报错页面。

## ⚠️ 需要注意的地方
- **`store` 模块是关键状态中心**：`store`（来自 `app.api.workbench import constants, store`）负责管理所有磁盘上的临时文件（运行日志、历史记录、缺陷链接等）。它的 `FILE_LOCK` 是线程安全的关键。如果在其他地方绕过 `store` 直接读写 `constants.WEB_UI_RUNS_DIR` 等路径，会导致数据不一致或并发写入冲突。
- **`workbench_case_consistency_service` 是数据一致性守门员**：几乎所有涉及“查询/执行/删除用例”的操作，都会先调用 `is_case_tracked()` 或 `filter_records_by_case_center()`。这意味着：如果数据库里的 `case_center_case_ids` 没有及时更新（比如新用例没入库），即使磁盘上有这个 `.yaml` 文件，门面层也会认为它“不存在”，返回 404。务必保证数据库与磁盘资产的同步。
- **`_find_run_item` 函数未定义**：在 `get_run()` 和 `workbench_history()` 方法中，代码直接调用了 `_find_run_item(run_id)`，但这个函数在本文件中并未定义（它可能在 `workbench_runtime_service` 或其他地方）。这是一个潜在的 `NameError` 风险点，需要确认其来源并确保导入正确。
- **硬编码的路径和常量风险**：`constants.TEST_POINTS_ROOT`, `constants.REPO_ROOT` 等路径如果配置错误，会导致 `resolve_case_yaml_path()` 找不到文件，或 `is_within()` 判断失败（如 `case_path` 被拒绝），引发 400/404 错误。这些路径应通过 `get_settings()` 统一管理，而非散落在各处。