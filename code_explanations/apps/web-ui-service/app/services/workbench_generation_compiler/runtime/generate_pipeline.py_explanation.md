# 📘 代码说明书
## 一句话概括
这是一个「AI测试用例生成流水线」的核心执行引擎，它把产品经理写的原始需求（比如“用户登录后能修改密码”），结合页面元素信息和业务规则，自动编译成可执行的、带详细步骤的测试用例 YAML 文件，并确保每一步都能在真实网页上跑得通。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `workbench_generation_compiler/runtime/generate_pipeline.py` | 整个测试用例生成流程的“总指挥台”：协调 AI 生成、页面元素匹配、质量校验、ID 分配、文件保存等环节，像一位严谨又细心的项目经理，确保从需求到可运行测试用例的每一步都合法、完整、可追溯。 |

## 🔍 核心函数/类说明
- **`run_generate_pipeline()`**：整个生成流程的“主开关”，所有工作都从这里开始。
  - 输入：一堆关键信息，包括原始需求文本（`effective_requirement`）、目标页面名（`normalized_page`）、项目名、AI 生成器（`run_orchestrator_generate`）、页面元素数据源（`resolve_page_object`）、校验规则（`ContractValidator`）、保存工具（`write_case_yaml`）等。
  - 输出：一个结构化结果字典，包含生成的用例 ID、YAML 文件路径、内容、状态等。
  - 大白话解释：就像你点外卖时按下一个“立即下单”按钮——它不自己做饭，但会立刻联系厨师（AI）、确认食材是否齐全（查数据库/YAML 页面元素）、检查菜谱格式对不对（校验合同）、给订单编号（分配 case_id）、打包好放进袋子里（写入 `.yaml` 文件）、最后告诉你“已出餐，单号是 ABC123”。中间任何一环出问题（比如没找到登录页的“密码显隐按钮”），它都会明确告诉你卡在哪一步、为什么失败。

- **`resolve_page_object(project, page, ...)`**：负责“找页面零件”的侦探，专门查找某个页面（如 `login`）上所有可用的按钮、输入框等交互元素。
  - 输入：项目名、页面名（如 `"mall"` 和 `"login"`），以及是否严格只用数据库（`strict_governance=True`）。
  - 输出：一个字典，形如 `{"page": "login", "elements": {"password_toggle": { ... }, "submit_btn": { ... }}}`，每个元素都包含它的定位方式（CSS 选择器）、角色（按钮/输入框）、显示名称（如“密码显隐开关”）、别名（如“eye_toggle”）等。
  - 大白话解释：就像装修前，师傅要先去仓库翻出“客厅灯开关”“厨房水龙头”这些零件的准确型号和安装说明书。这个函数就是去数据库里翻（优先），找不到就去老文件夹（YAML 资产）里找，确保后续 AI 写的“点击密码显隐按钮”这一步，真能在网页上找到对应的东西。

- **`_infer_element_aliases(...)`**：给页面元素起“小名”的翻译官。
  - 输入：一个页面元素的原始信息（比如 `element_code="pwd_eye"`、`locator_value="#password-visibility-toggle"`、`role="button"`）。
  - 输出：一串人类好记的别名列表，如 `["密码显隐", "eye_toggle", "密码可见性切换"]`。
  - 大白话解释：程序员可能叫它 `pwd_eye`，测试同学说“点那个眼睛图标”，产品文档写“密码明文切换”，前端代码里是 `#password-visibility-toggle` —— 这个函数就把所有这些说法统一收编，让 AI 生成的测试步骤哪怕写“点击密码显隐”，系统也能认出它指的是同一个按钮，大大提升容错性和协作效率。

- **`_element_display_name(...)`**：给页面元素起“正式中文名”的设计师。
  - 输入：同上，一个元素的原始字段。
  - 输出：一个友好、规范的中文显示名，如 `"密码显隐开关"` 或 `"用户名输入框"`。
  - 大白话解释：避免测试报告里出现冷冰冰的 `#login-form input[name='username']`，而是自动变成“用户名输入框”，让非技术人员一眼看懂，也方便后续做自动化执行时的日志输出（比如“正在点击【密码显隐开关】…”）。

- **`_scope_points_to_selected_intents(...)`** 和 **`_filter_requirement_spec_by_selected_intents(...)`**：两个“精准筛选器”，负责把大而全的 AI 输出，按用户勾选的意图（如只想要“修改密码”相关用例）精确裁剪。
  - 输入：AI 生成的一大堆测试点（`points`）和用户手动勾选的意图 ID 列表（`selected_intent_ids`）。
  - 输出：只保留与勾选意图匹配的测试点，同时清理掉需求规格中无关的部分。
  - 大白话解释：就像你让 AI 帮你写一份《用户旅程报告》，它洋洋洒洒写了登录、注册、修改密码、注销……但你其实只要“修改密码”这一节。这两个函数就是帮你把其他章节全部删掉，只留下精准匹配的那一部分，保证最终生成的用例不跑题、不冗余。

## 🧩 调用关系与数据流转
```
run_generate_pipeline(...)  
│  
├─▶ _extract_selected_intent_ids(...) → 得到用户勾选的意图ID列表（如 ["change_password"]）  
├─▶ _extract_candidate_snapshots(...) → 得到用户选中的“候选用例快照”（含标题、步骤、预期结果）  
│  
├─▶ run_orchestrator_generate(...) → 【AI大脑】输入需求+页面名 → 输出原始结果（含 requirement_spec, test_points, case）  
│      │  
│      └─▶ extract_quality_gate(...) → 从 requirement_spec 中抽取出“质量门禁”规则（如“必须覆盖3个核心场景”）  
│  
├─▶ _scope_points_to_selected_intents(...) + _filter_requirement_spec_by_selected_intents(...)  
│      → 用用户勾选的ID，精准过滤 test_points 和 requirement_spec  
│  
├─▶ _enrich_test_points_with_candidate_snapshots(...)  
│      → 把用户选中的“候选快照”里的标题、步骤、预期结果等，填充/覆盖到对应 test_point 上  
│  
├─▶ resolve_page_object(...) → 【找零件】→ 返回页面元素字典（{"elements": {...}}）  
│      │  
│      ├─▶ _resolve_page_object_from_db(...) → 查数据库（首选）  
│      └─▶ _resolve_page_object_from_assets(...) → 查 YAML 文件（备选，仅当 strict_governance=False）  
│  
├─▶ ContractValidator().validate_full(...) → 【质检员】用 requirement_spec + test_points + 页面元素 → 校验是否合法（如：步骤里写的元素名，页面里真有吗？）  
│  
├─▶ compile_execution_steps(...) → 【翻译官】把自然语言描述的 test_points（如“点击密码显隐按钮”）  
│      → 翻译成机器可执行的步骤列表（如 [{"action":"click", "target":"password_toggle", ...}]）  
│  
├─▶ allocate_case_id(...) → 【发工号】根据项目/页面/已有ID，生成唯一、合规的用例ID（如 "MALL-LOGIN-0042"）  
│  
├─▶ write_case_yaml(...) → 【装盒打包】把最终 case_yaml 字典写成磁盘上的 `MALL-LOGIN-0042.yaml` 文件  
│  
├─▶ save_case_state(...) → 【登记入库】把用例状态存进数据库或缓存  
│  
├─▶ save_test_point_plan(...) → 【归档蓝图】把原始测试点设计（含覆盖分析）存为独立文件  
│  
└─▶ append_history(...) → 【写日记】记录本次生成全过程（时间、操作、结果、错误），用于审计和调试  
```

## 💡 值得学习的写法
- **协议（Protocol）定义清晰职责**：`RunOrchestratorGenerate`、`ExtractQualityGate` 等不是具体实现，而是“接口契约”，让主流程 `run_generate_pipeline` 完全不依赖某个特定 AI 模型或存储方式，未来换模型、换数据库、换日志系统，只需提供符合协议的新函数即可，解耦极强。
- **“双源页面元素”治理策略**：优先查数据库（代表最新、受控的页面资产），失败才回退到 YAML（兼容历史遗留）。更妙的是 `strict_governance=True` 时直接禁止回退，强制团队把页面建模进数据库——这是用代码推动工程规范落地的典范。
- **智能别名与显示名推导**：通过正则匹配中文关键词（“密码显隐”“按钮”“输入框”）、角色映射、模糊归一化（忽略空格/大小写/标点），让系统能理解五花八门的人类表达，极大提升 AI 生成结果的鲁棒性。
- **错误分类与透传机制**：`_COMPILER_ERROR_CODES` 预定义了所有可能的编译错误码；`ExecutionCompilerError` 包含 `code`/`message`/`reason`/`stage` 四要素；最终统一转为 HTTP 异常时，既保留原始错误上下文，又按类型分流处理（质量门禁拦截、校验失败、上游服务异常），排查时一目了然。
- **防御式归一化工具链**：`_normalized_text()`、`_normalized_key()`、`_list_text()` 等小函数贯穿全文件，把 `None`/`""`/`"   "`/`["a", None, "b"]` 等各种脏数据一键转成干净字符串或列表，避免 `AttributeError` 或 `KeyError`，让主逻辑专注业务而非防错。

## ⚠️ 需要注意的地方
- **`resolve_page_object` 的 `strict_governance=True` 是默认值**：这意味着一旦某个页面（如 `"checkout"`）还没在数据库里建模，整个生成流程就会直接报错 `page_object_not_governed`，而不是悄悄用 YAML 文件顶替。上线前务必确认所有目标页面已在 DB 中完成建模，否则会大面积失败。
- **`_looks_like_password_toggle_element` 的判断逻辑很“重”**：它不仅看字段内容，还硬编码了大量中英文关键词（如 `"eye_toggle"`、`"ipath3"`、`"明文"`）。如果业务中新增了其他密码切换表述（如 `"show_pwd"`），这里不会自动识别，需要手动补充，否则会导致别名缺失、显示名不准。
- **`compile_execution_steps(...)` 的 intent_id 校验非常严格**：它要求编译后的每一步（除 `login` 步骤外）的 `intent_id` 必须与用户勾选的 `selected_intent_ids` 完全一致（不多不少）。如果 AI 生成了额外步骤，或漏掉了某个勾选意图，就会抛出 `execution_compiler_intent_coverage_failed` 错误。调试时需重点比对 `selected_intent_ids` 和 `compiled_intent_ids` 的差异。
- **`_normalize_candidate_snapshot` 对字段名假设较强**：它默认 `candidate` 字典里有 `intent_id`、`title`、`steps`、`expected_result` 等键。如果上游 AI 服务返回的结构稍有不同（如用 `expected` 代替 `expected_result`，或 `steps` 是字符串而非列表），可能导致字段丢失或类型错误，建议在此处加更健壮的 fallback。
- **`run_generate_pipeline` 参数极多（20+个）且部分必填**：调用时极易遗漏（如忘记传 `http_exception_cls` 或 `allocate_case_id`），导致运行时报 `NameError` 或 `TypeError`。强烈建议使用 `TypedDict` 或 Pydantic Model 封装参数，或在函数开头加 `assert` 校验关键参数是否存在。