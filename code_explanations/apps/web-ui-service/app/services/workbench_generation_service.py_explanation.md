# 📘 代码说明书
## 一句话概括
这是一个“自动化测试用例生成服务”的总控大脑——它不直接写代码或分析网页，而是像一位经验丰富的项目经理，协调需求理解、页面分析、测试点提取、用例编写、质量审核和结果归档等一整套流程，并为前端（如工作台界面）提供干净可用的响应。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `workbench_generation_service.py` | 测试用例自动生成服务的**顶层协调层**：接收用户输入（比如一个页面URL和一句话需求），调用底层各模块干活，检查质量是否过关，生成可读报告，并把最终用例和测试点存好；是 FastAPI 路由（`router`）背后真正干活的“指挥官”。 |

## 🔍 核心函数/类说明
- **`build_preview_response()`**：作用——生成“预览版”分析报告（不真正生成用例，只告诉你*可能*会测什么）。  
  - 输入：页面URL、需求文字、各种可选输入源（如PRD文档、接口定义等）。  
  - 输出：一个带测试点列表、质量门禁判断、置信度评分的 Markdown 风格分析结果。  
  - 大白话解释：就像你点外卖前先看“商家推荐菜+用户评价摘要”，它不给你做菜（不生成用例），但帮你快速判断“这家值不值得下单”——比如发现需求太模糊、页面打不开、或关键功能缺失，就提前亮红灯。
  
- **`build_generated_case_payload()`**：作用——真正执行“一键生成测试用例”的核心动作。  
  - 输入：同上，但明确要求“生成并保存”。  
  - 输出：一个包含新用例ID、YAML文件路径、测试点清单、质量门禁结果等完整信息的字典。  
  - 大白话解释：相当于你点了“确认下单”，它立刻联系厨房（`run_generate_pipeline`）、打包（写入`.yaml`文件）、贴标签（分配唯一用例编号）、存小票（记录历史）、再给你一张带二维码的取餐单（返回结构化结果）。

- **`_allocate_case_id()`**：作用——给新生成的测试用例分配一个独一无二、有规律的编号（如 `mall_home_search_FN_AI_001`）。  
  - 输入：用户想指定的编号（可选）、项目名、页面名、模块名、本地用例文件夹路径、已存在的编号列表。  
  - 输出：一个合法、不重复、符合命名规范的用例ID。  
  - 大白话解释：就像图书馆给每本书编索书号——先查有没有人抢注了你想起的名字（`requested_case_id`），没有就按“项目-页面-类型-来源-序号”规则自动编一个，还确保不会和硬盘里已有的 `.yaml` 文件重名。

- **`extract_quality_gate()` 和 `is_quality_gate_blocked()`**：作用——从任意嵌套结果中找出“质量门禁”决策，并判断是否应阻断流程。  
  - 输入：任意深度的字典（可能是成功结果、也可能是报错信息）。  
  - 输出：`extract_quality_gate` 返回门禁配置字典；`is_quality_gate_blocked` 返回 `(是否阻断, 门禁详情)` 元组。  
  - 大白话解释：像机场安检的X光机——不管行李包（数据）里套了几层袋子（嵌套字典），它都能一层层翻出来找“违禁品”（`quality_gate` 字段）；再看里面写的“禁止登机”还是“请开箱检查”，决定是直接拦下（`block`）还是放行（`allow`）。

- **`prepare_auto_run_page_context()`**：作用——为批量自动化运行（比如一次测10个页面）准备每个页面的“作战地图”。  
  - 输入：页面URL、需求文字、是否启用多源输入等。  
  - 输出：一个包含解析后的页面名、标准化URL、页面快照（`surface`）、操作步骤、页面对象路径等的上下文字典。  
  - 大白话解释：就像旅行团出发前，导游给每位游客发的“行程包”：里面有景点名字（`page`）、导航链接（`resolved_page_url`）、现场照片（`surface`）、游玩路线（`steps`）、纪念品店地址（`page_object_path`）……所有后续动作都基于这个包展开。

## 🧩 调用关系与数据流转
```
FastAPI Router（用户请求入口）
        ↓
build_preview_response() 或 build_generated_case_payload()   ← 用户选择“预览” or “生成”
        ↓（传参调用）
run_preview_pipeline() 或 run_generate_pipeline()            ← 底层执行引擎（真正干活的工人）
        ↓（返回结构化结果）
→ preview_store.save_preview_snapshot()                      ← 预览结果存档（临时快照）
→ write_case_yaml() + save_case_state()                      ← 生成结果落盘（写YAML + 记录状态）
→ save_test_point_plan()                                     ← 测试点单独存档（供评审用）
        ↓（中间处理）
_extract_quality_gate() → is_quality_gate_blocked()          ← 质量卡点检查（像闸机验票）
_allocate_case_id()                                          ← 分配唯一编号（贴条形码）
_normalize_generated_case_title()                            ← 清洗标题（去掉“测试意图：”等冗余前缀）
_prepare_auto_run_page_context()                             ← 批量场景下组装单页上下文
        ↓（结果汇总）
build_auto_run_summary()                                     ← 统计整批运行结果（多少通过/失败/需人工审）
```

## 💡 值得学习的写法
- **防御式参数清洗无处不在**：几乎所有函数开头都用 `_dict_value()` / `_list_value()` / `_strip_list_prefix()` 等小工具统一处理“可能为空、可能不是预期类型、可能带乱码前缀”的输入，避免后续 `AttributeError` 或 `KeyError`，让代码像有缓冲垫一样耐造。
- **“门禁穿透式提取”设计**：`extract_quality_gate()` 能递归钻进 `error → details → quality_gate` 多层嵌套，确保无论 pipeline 报错还是成功，质量决策都能被捞出来——类似“不管快递是签收成功还是被退回，都要查清签收单上写的‘本人拒收’还是‘家人代收’”。
- **用 `Callable[..., ...]` 类型别名代替硬编码函数签名**：在文件顶部集中声明 `BuildSystemRequirement = Callable[..., str]` 等，既让 IDE 能提示参数，又允许不同实现灵活替换（比如换一个更聪明的标题生成器），解耦程度高。
- **`_allocate_case_id()` 的双源去重逻辑**：既扫描磁盘上所有 `*.yaml` 文件提取已有ID，又兼容传入的内存中ID列表，防止“本地开发时没同步远程ID库”导致重复编号，细节很务实。

## ⚠️ 需要注意的地方
- **`_ensure_execution_steps()` 会直接 raise ValueError**：如果 pipeline 返回空的 `execution.steps`，它不尝试补救，而是果断报错中断。这意味着下游 `run_generate_pipeline` 必须保证至少返回一个有效步骤，否则整个生成流程会崩溃——调用方需确保该约束。
- **`safe_case_id` 和 `allocate_case_id` 易混淆**：前者是“安全转换字符串为合法ID”（如过滤非法字符），后者是“智能分配全新不重复ID”，名字相似但职责完全不同，误传可能导致编号混乱或冲突。
- **`persist_auto_run_fallback_case()` 中 `fallback_reason` 类型未校验**：函数签名里写 `fallback_reason: Any`，但实际存入 YAML 时若传入不可序列化的对象（如 `datetime` 或自定义类），会导致 `write_case_yaml` 失败——建议加 `str(fallback_reason)` 强制转字符串。
- **`build_auto_run_governance_context()` 里多次调用 `build_item_review_state()`**：先用基础数据生成初版评审状态，再结合 `risk_report` 生成终版，但两次调用参数差异仅在于是否传 `risk_report`。若未来逻辑变复杂，容易漏掉某次调用的参数更新，属于潜在维护风险点。