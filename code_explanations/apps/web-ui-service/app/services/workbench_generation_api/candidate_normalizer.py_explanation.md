# 📘 代码说明书
## 一句话概括  
这是一个“测试点清洁工”：它把原始、杂乱、带格式/注释/元数据的测试用例草稿（比如从需求文档或AI生成结果里捞出来的），自动清洗、标准化、去噪、补全，并整理成干净、统一、可直接用于测试工作的结构化数据。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `candidate_normalizer.py` | 负责对“候选测试点”（raw test candidates）进行清洗、过滤、标准化和组装，是测试用例生成流水线中关键的“质检+美容”环节 |

## 🔍 核心函数/类说明
- **`class CandidateNormalizer`**：整个文件的主角，像一个「测试点整理机器人」，它不自己生成测试点，而是专门负责把别人（比如AI模型或前端表单）交来的“毛坯测试点”打磨成“精装交付版”。它需要一个 `FeatureFlags`（功能开关）来决定哪些清洗规则要启用。
  - 输入：`FeatureFlags` 实例（控制是否开启去噪、过滤等高级功能）
  - 输出：无（但它的方法会返回清洗后的数据）
  - 大白话解释：就像你请了个细心的助理，你把一堆写满备注、标题、链接、乱码、重复项的测试草稿甩给她，她会自动删掉水印、跳过“【功能描述】”这种标题行、忽略网址和JSON片段、合并重复步骤、补全空缺字段（比如没标题就用摘要顶上），最后交给你一份清爽、规范、能直接打印或导入测试管理系统的清单。

- **`_normalize_candidate_text(self, value: str) -> str`**：给任意文本做“基础美容”的小工具。
  - 输入：一段原始文本（可能是 None、带空格、带编号、带引号、超长的字符串）
  - 输出：最多200个字符、首尾空格清空、多余空格压成一个、去掉常见列表前缀（如 `1. `、`• `、`【模块】`）、去掉首尾引号/反引号/单双引号
  - 大白话解释：就像手机相册里的“一键美颜”——不管照片是歪的、暗的、有水印，它先裁掉边角、调亮、磨皮，再限制最大尺寸（200字），确保每段文字都“站得直、穿得整、不过胖”。

- **`_looks_like_heading_only_text(self, value: str) -> bool`**：判断一段文字是不是“光杆标题”，比如 `【页面】`、`功能：`、`测试点`、`优先级：` 这种只有分类名、没有实质内容的“占位符”。
  - 输入：一段文本
  - 输出：`True`（是标题党）或 `False`（有干货）
  - 大白话解释：就像图书管理员看到一张纸只写着“第3章：登录功能”，但下面全是空白——她会说：“这不算一页书，是目录页，扔掉！” 这个函数就是干这个的，防止空标题污染最终测试清单。

- **`_looks_like_metadata_noise_text(self, value: str) -> bool`**：判断一段文字是不是“系统噪音”，比如 `[page_url] https://...`、`"user_story": {`、`source":"xxx"`、`entities:` 这类开发/配置用的元信息，对测试人员毫无意义。
  - 输入：一段文本
  - 输出：`True`（是噪音）或 `False`（是人话）
  - 大白话解释：就像你在菜市场买菜，摊主递给你一张小票，上面除了“西红柿 2斤”还印着“POS机号：8899”、“收银员：张三”、“时间戳：202405201423”——你只关心“西红柿”，其余全是干扰信息。这个函数就是帮你撕掉那些无关小字。

- **`_normalize_candidate_steps(self, value: Any, *, filter_enabled: bool) -> list[str]`**：专门处理“操作步骤”字段，支持多种输入格式（字符串、字典、甚至奇怪类型），并按需过滤噪音。
  - 输入：步骤原始数据（可能是 `["点击登录按钮", {"summary": "输入用户名"}]` 或其他格式）+ 是否开启过滤开关
  - 输出：清洗后、去重、截断的纯字符串步骤列表（如 `["点击登录按钮", "输入用户名"]`）
  - 大白话解释：就像你让助理整理会议记录，有人口头说“点一下按钮”，有人发微信说“{action: 'click', target: 'login-btn'}”，还有人写了“1. 点击登录按钮；2. 输入账号密码”——她会统一转成“点击登录按钮”“输入账号密码”两条干净句子，并且如果开了“去噪模式”，还会把“【步骤开始】”这种废话删掉。

- **`normalize_candidates(self, raw_candidates: list[dict[str, Any]]) -> list[dict[str, Any]]`**：整个类的“核心发动机”，对一整批候选测试点执行全流程清洗。
  - 输入：原始候选测试点列表（每个是字典，含 title、steps、precondition 等字段）
  - 输出：清洗、过滤、补全、去重后的标准测试点列表（字段齐全、内容干净、逻辑自洽）
  - 大白话解释：这是助理的“全自动整理流水线”——她逐个检查每个测试点：  
    ✅ 先把所有文字字段（标题、摘要、前置条件…）用 `_normalize_candidate_text` 美容一遍；  
    ✅ 如果开启了过滤（`filter_enabled=True`），就用 `_looks_like_heading_only_text` 和 `_looks_like_metadata_noise_text` 把标题/摘要/前置条件/预期结果里的“标题党”和“系统噪音”清空；  
    ✅ 步骤、元素、标签等列表字段，全部走 `_normalize_candidate_steps` 或类似逻辑，去噪、去重、限长；  
    ✅ 如果标题为空，就用摘要/第一步/预期结果“救场”；如果摘要也空，就用标题“救场”；确保每个测试点至少有个“脸面”；  
    ✅ 最后检查：如果连标题、摘要、步骤、预期结果全都没了 → 直接淘汰！  
    → 最终交出一份“人人有标题、条条有内容、绝不重复、没有废话”的优质测试点清单。

- **`build_candidate_requirement(self, base_requirement: str, candidate: dict[str, Any]) -> str`**：把一个清洗好的测试点，格式化成一段人类可读、带结构的提示语（常用于喂给大模型生成更详细用例）。
  - 输入：基础需求描述（如“用户能成功登录”）+ 一个已清洗的测试点字典
  - 输出：一段用中文分段写的、带编号和冒号的清晰文本（例如 `"测试点ID：TP-001\n测试点标题：登录失败时提示正确错误信息\n..."`）
  - 大白话解释：就像助理把整理好的测试点，写成一封给程序员/测试工程师的“工作邮件”：开头写清楚ID和标题，中间分段说明意图、类型、步骤、预期结果，结尾加一句“请严格按这个点来写，别跑题！”——方便后续交给AI或人工深化。

- **`extract_case_candidates_from_preview(self, preview_payload: dict[str, Any], *, max_cases: int) -> list[dict[str, Any]]`**：从上游（比如前端传来的预览数据包）里“挖矿”，提取出原始测试点草稿，再立刻交给 `normalize_candidates` 处理。
  - 输入：一个嵌套很深的预览数据字典（可能来自API响应）+ 最多取多少个测试点
  - 输出：清洗后、数量不超过 `max_cases` 的测试点列表
  - 大白话解释：就像助理接到一个“需求压缩包”（`preview_payload`），她先一层层拆开（找 `item → requirement_spec → test_intents`），把里面散落的测试意图一个个捡出来，临时拼成标准字典（补默认值如 `intent_type="functional"`、`priority="P1"`），然后立刻塞进自己的“清洗流水线”（调用 `normalize_candidates`），最后掐着数量上限（比如最多10个）交差。相当于“现场收料 + 立即加工 + 限量发货”。

## 🧩 调用关系与数据流转  
```
extract_case_candidates_from_preview() 
    ↓（从 preview_payload 挖出原始 intent 列表，拼成 candidates）
normalize_candidates() 
    ↓（对每个 raw_candidate 循环处理）
        ├─ _normalize_candidate_text() × 多次（处理 title/summary/precondition/expected 等字段）
        ├─ _looks_like_heading_only_text()（判断 title/summary 是否为空标题）
        ├─ _looks_like_metadata_noise_text()（判断 precondition/expected/steps 等是否为噪音）
        ├─ _normalize_candidate_steps()（处理 steps 字段）
        └─ ...（其他字段同理）
    ↓（组装成标准化字典，加入 normalized 列表）
    → 返回清洗后 candidates 列表

build_candidate_requirement() 
    ↓（独立使用，通常在 normalize_candidates 之后调用）
        → 读取 candidate 中各字段（title, steps, expected...）
        → 拼接成格式化字符串（带换行和编号）
        → 返回可读提示文本
```

## 💡 值得学习的写法
- **“防御式取值”链式处理**：如 `str(intent.get("expected") or intent.get("expected_result") or intent.get("expect_result") or "").strip()` —— 用 `or` 链兼容多个历史字段名，避免因字段名变更导致崩溃，像“备胎机制”，总有兜底。
- **“空值即 False”哲学贯穿始终**：所有 `value or ""`、`if not text:`、`if filter_enabled and ...:` 都默认把 `None`/空字符串/空列表当作“无效”，无需额外 `is None` 判断，代码更简洁健壮。
- **“补全逻辑”人性化设计**：当 `title` 为空时，自动用 `summary` 或 `steps[0]` 或 `expected` 补上；当 `summary` 为空时，又用 `title` 补——确保每个测试点至少有一个“门面”，避免下游因空字段报错。
- **“限长+截断”双重保险**：`_normalize_candidate_text()` 先用正则压缩空格，再 `.strip("`'\" ")` 去首尾标点，最后 `[:200]` 强制截断，三步防超长，保护下游存储和展示。
- **“开关驱动”架构**：所有高级过滤（去标题、去噪音）都受 `self._flags.testpoint_filter_enabled()` 控制，上线/灰度/调试时只需改一个开关，不用动业务逻辑，非常灵活。

## ⚠️ 需要注意的地方
- **⚠️ 正则表达式易误伤**：`_looks_like_heading_only_text()` 中的 `re.match(r"^【[^】]{1,24}】$", text)` 会把合法短标题如 `【订单】` 当作噪音过滤掉（因为匹配了 `【...】` 格式）。如果业务中真有这种简短但有效的标题，需要调整正则或加白名单。
- **⚠️ `steps_hint` 和 `steps` 的处理不对称**：`steps_hint` 是简单遍历 + 去重，而 `steps` 会走 `_normalize_candidate_steps()`（含去噪）。如果 `steps_hint` 里混入了 `[page_url]` 这类噪音，不会被过滤——容易漏掉，建议统一走去噪逻辑。
- **⚠️ `involved_element_codes` 不经过噪音过滤**：代码中对 `involved_element_codes` 只做了基础清洗（`_normalize_candidate_text`），但没像 `involved_elements` 那样加 `not self._looks_like_metadata_noise_text(element)` 判断——如果元素Code字段里混入了 `source":"xxx"` 这类噪音，会被保留。
- **⚠️ `build_candidate_requirement()` 的硬编码上限**：`for index, hint_row in enumerate(hint_rows[:10], start=1):` 和 `for index, step in enumerate(step_rows[:10], start=1):` 强制最多显示10条，但未提供配置项。如果某测试点真有20步，会静默截断，可能丢失关键信息。
- **⚠️ `extract_case_candidates_from_preview()` 的字段 fallback 风险**：当 `intent.get("steps")` 不是 list 时，会 fallback 到 `intent.get("steps_summary")` 并包装成 `[...]`，但如果 `steps_summary` 是长段落（含换行/标点），直接 `strip()` 后变成单条，可能破坏步骤粒度——建议增加简单分句逻辑（如按 `。？！\n` 分割）。