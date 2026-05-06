# 📘 代码说明书
## 一句话概括
这是一个「测试点资产管家」——专门负责管理、解析、汇总和展示网页自动化测试用例（Test Point）的完整生命周期数据的服务模块，把散落的 YAML 用例、AI 生成计划、运行记录、页面信息等「拼图」自动组装成清晰、可筛选、可决策的测试资产视图。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `workbench_asset_service.py` | 测试点资产的「中央大脑」：统一加载、标准化、关联、计算并输出测试资产的结构化摘要（如语义类型、技术构成、覆盖率、是否可回归等），支撑前端工作台（Workbench）展示与筛选。 |

## 🔍 核心函数/类说明
- **`load_test_point_asset()`**：作用——从磁盘加载一个测试点资产（含 YAML 原始内容 + AI 计划 + 运行快照等所有信息）  
  - 输入：项目名（如 `"mall"`）、用例 ID（如 `"product-search-001"`）  
  - 输出：一个大字典，包含标题、页面、需求、测试点数量、AI 语义分析结果、覆盖率矩阵、是否需要人工复核等全部字段  
  - 大白话解释：就像「翻档案柜找一份完整案卷」——它不只找 `.json` 状态文件，还会顺藤摸瓜找到对应的 `.yaml` 用例、`plans/xxx.json` 生成计划、甚至关联的页面对象文件，把所有碎片拼成一份「带注释的完整报告」。

- **`build_test_point_asset_semantic_summary()`**：作用——给测试点资产打上「页面语义标签」（比如是「商品列表页」还是「下单表单页」？核心目标是「浏览」还是「提交」？）  
  - 输入：当前页面名（如 `"product"`）、标准化后的测试计划（含所有测试点）、页面标准化函数、置信度修正函数  
  - 输出：一个含 `page_type`（list/form/unknown）、`business_domain`（product/order/aftersales）、`primary_goal`（browse_list/edit_form 等）、`confidence`（0.0~1.0）等字段的摘要  
  - 大白话解释：就像「AI 浏览器助理」——看到一堆点击、输入、断言操作后，自动判断：“哦，这明显是在操作一个商品搜索列表页，主要目标是让用户搜完能看结果”，并给出 82% 的把握程度；如果拿不准，就提醒“需要人看看”。

- **`build_test_point_asset_coverage_matrix()`**：作用——生成「测试点覆盖关系矩阵」，回答“每个测试点链接了哪些需求/意图？哪些已覆盖？哪些漏了？”  
  - 输入：测试点资产数据、最近一次运行快照（含实际执行结果）  
  - 输出：一个结构化表格（`rows` 列表），每行代表一类覆盖状态（如 `covered`/`orphan`/`gap`），含关联的需求 ID、测试点 KEY、缺失项提示等  
  - 大白话解释：就像「测试点-需求对账单」——左边列测试点（如 `product-search-001-point-01`），右边列它该覆盖的需求（如 `REQ-123`），再标出：✅ 已验证、⚠️ 需求变了但没更新、❌ 完全没连需求。还自动合并同类项，避免一页显示 50 行重复。

- **`upsert_test_point_asset_snapshot()`**：作用——「保存或更新」一份测试点资产的最终快照（即 `.json` 状态文件）  
  - 输入：项目名、用例 ID、页面名、需求文本、标准化后的 AI 计划、计划文件路径等  
  - 输出：写入磁盘的资产字典（同 `load_test_point_asset` 的输出格式）  
  - 大白话解释：就像「自动归档员」——每次 AI 生成新计划、或人工修改后，它会把所有信息（原始 YAML + AI 分析 + 页面类型 + 覆盖率 + 关联文件路径）打包成一个 `.json` 文件存好，并自动升级版本号、保留历史版本（在 `versions/` 目录下），确保随时可回溯。

- **`build_test_point_asset_selection_summary()`**：作用——决定这个测试点资产「能不能进回归测试」（即是否 `ready_for_regression`）  
  - 输入：完整的追溯性摘要（含覆盖率、门禁决策、风险评估、语义分析等）  
  - 输出：`{"selection_state": "ready"|"needs_review"|"blocked", "reasons": [...]}`  
  - 大白话解释：就像「测试准入质检员」——它综合所有条件：门禁是否放行？覆盖率是否达标？AI 语义是否可信？有没有 design_only（仅设计未执行）的点？只要有一项不满足，就标记为「需人工审核」或「被拦截」，并清楚列出原因（如“执行门禁阻断”、“页面语义仍需复核”），让工程师一眼知道卡在哪。

## 🧩 调用关系与数据流转
```
[前端请求] 
    ↓（如：获取测试资产列表）
build_cases_payload() 
    → collect_case_items() → 扫描 project/ 目录下的 .json 和 ai_cases_root/*.yaml，生成基础用例卡片列表
    → paginate_case_items() → 按页码/关键词/聚焦用例ID分页

    ↓（如：查看某个资产详情）
build_test_point_asset_detail() 
    → load_test_point_asset() → 加载 asset.json + plans/xxx.json + 关联文件 → 得到完整资产数据
        → latest_run_snapshot_for_case() → 从 runtime 数据中找最新一次运行记录
            → build_test_point_asset_traceability_summary() → 综合资产+运行数据，生成追溯摘要
                → build_test_point_asset_coverage_matrix() → 计算覆盖矩阵
                → build_test_point_asset_semantic_summary() → 计算语义标签
                → build_test_point_asset_technique_summary() → 计算技术构成（precondition/input/assertion 等数量）
    → build_selection_summary() → 基于追溯摘要判断是否 ready_for_regression
    → build_coverage_summary() → 统计整个列表的覆盖率分布

    ↓（如：保存 YAML 用例）
build_saved_case_payload() 
    → write_case_yaml() → 把 YAML 文本写入磁盘
    → save_case_state() → 生成初始状态（含 derived points、version=1）
        → upsert_test_point_asset_snapshot() → 创建/更新 asset.json（含 plan、summary、references）

    ↓（如：AI 生成测试点计划）
save_test_point_plan() 
    → normalize_test_point_plan_payload() → 标准化 AI 输出（补字段、转格式）
    → upsert_test_point_asset_snapshot() → 同上，存为最新快照
```

## 💡 值得学习的写法
- **「柔性容错」设计无处不在**：所有 `_dict_value()` / `_list_value()` / `_int_value()` / `_float_value()` 辅助函数，都把 `None`/`str`/`int`/`list` 等各种乱七八糟输入，安全转成预期类型（空则给默认值），避免 `AttributeError` 或 `KeyError` 中断流程，像给代码穿了防弹衣。
- **「多源去重合并」逻辑优雅**：`merge_reference_items()` 用 `(kind, path, case_id)` 三元组当唯一键，自动合并来自 YAML、AI 计划、页面对象等不同来源的引用，避免同一份文件被重复计入，且保留首次出现的顺序。
- **「语义推导」层层递进**：`_derive_asset_title()` 不死守 `asset.title`，而是按优先级尝试：AI 计划里的 title → 元数据里的 `asset_title` → 候选行里的 `title/summary/description` → 最后 fallback 到用例 ID，像一位耐心的图书管理员，总能找到最合适的书名。
- **「动态决策门禁」可插拔**：`build_test_point_asset_gate_context()` 和 `build_execution_gate()` 把门禁逻辑解耦，允许不同项目用不同规则（如电商严控，后台系统宽松），只需替换函数参数，无需改主干逻辑。

## ⚠️ 需要注意的地方
- **`_safe_case_id()` 是双刃剑**：它把空/非法 ID 强制转成 `"atp-web-common-core-fn-ai-0001"`，虽防崩，但也可能掩盖真实 ID 错误（如传入 `" "` 或 `"null"`），调试时要留意日志里是否频繁出现这个兜底 ID。
- **YAML 解析失败直接抛 HTTP 400**：`read_case_yaml()` 和 `build_saved_case_payload()` 中，若 YAML 格式错误或根节点不是字典，会立即 `raise HTTPException`。这意味着前端上传坏 YAML 会直接报错，但服务端不会记录详细错误位置（如第几行），建议后续加行号提示。
- **时间戳依赖系统本地时区**：`datetime.fromtimestamp(..., tz=UTC)` 用于读取文件修改时间，但 `path.stat().st_mtime` 是系统本地时间戳，若服务器时区非 UTC，可能导致 `updated_at` 时间错乱（应统一用 `path.stat().st_mtime_ns` + `timezone.utc` 更稳妥）。
- **`latest_run_snapshot_for_case()` 的性能隐患**：它会遍历 `runtime_jobs`（内存列表）+ `runtime_runs_file`（JSON 数组文件）全部运行记录做匹配，若运行记录达万级，可能变慢。生产环境建议加索引（如按 `project+case_id` 预建哈希表）或改用数据库查询。