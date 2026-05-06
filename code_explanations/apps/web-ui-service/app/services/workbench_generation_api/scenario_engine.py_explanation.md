# 📘 代码说明书
## 一句话概括
这是一个“测试场景生成引擎”，它能根据用户输入的需求文档、测试意图等信息，自动分类出「正常流程」「异常情况」「边界条件」三类测试场景，并按不同组合策略（全量/配对/默认）批量生成带标签、带中文标识的测试用例草稿。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `scenario_engine.py` | 测试场景的智能分类器 + 组合生成器：把原始需求“翻译”成结构化、可执行的测试候选集，并统计覆盖情况 |

## 🔍 核心函数/类说明
- **`class ScenarioEngine`**：整个文件的主角，像一个「测试导演」——它不自己写用例，但负责统筹：看懂需求、判断场景类型、搭配候选用例、打上合适标签、检查有没有漏掉重要场景。
  - 输入：功能开关配置（`FeatureFlags`）、需求数据、组合模式、覆盖目标等  
  - 输出：一摞准备好的测试候选用例 + 一份“覆盖体检报告”（比如“缺了边界场景，覆盖率83%”）
  - 大白话解释：就像你让助理帮整理一份《用户登录功能》的测试清单，它会先读需求文档，发现里面提到了“密码输错”“网络断开”“密码刚好16位”这些关键词，就自动归类为「异常」「异常」「边界」；再根据你要求“尽量多测”（full）还是“快速过一遍”（pairwise），把基础用例和场景类型拼装成完整清单，并告诉你：“已覆盖3类中的2类，还差边界场景”。

- **`def scenario_from_intent(self, intent: dict[str, Any]) -> str`**：判断一个测试意图属于哪类场景（正常 / 异常 / 边界）的“智能分类器”。
  - 输入：一个测试意图字典（比如 `{"intent_type": "security", "title": "防止SQL注入"}`）
  - 输出：字符串 `"normal"` / `"abnormal"` / `"boundary"`
  - 大白话解释：就像看菜名猜口味——如果菜名叫“清蒸鲈鱼成功上桌”，就是「正常」；叫“鱼刺卡喉应急处理”，就是「异常」；叫“鱼刺最小可检测长度”，就是「边界」。它既看字段名（如 `intent_type`），也看标题/摘要里的关键词（比如“失败”“边界”“错误”），还能根据开关决定是“严格按人填的字段判”还是“AI自动扫文字猜”。

- **`def normalize_coverage_profile(self, value: str) -> list[str]`**：把用户乱写的“想覆盖哪些场景”转换成标准三选一列表（如把 `"正向+error+临界"` → `["normal", "abnormal", "boundary"]`）。
  - 输入：任意格式的字符串（支持逗号、加号、斜杠分隔，大小写不敏感，别名众多）
  - 输出：去重、标准化后的场景类型列表（只含 `"normal"`/`"abnormal"`/`"boundary"`）
  - 大白话解释：用户可能随手写 `"positive, boundary, invalid"` 或 `"happy/edge/error"`，这个函数就像个“翻译官+整理员”，统一转成系统能听懂的三种语言，并自动去重、补全（空输入就默认全都要）。

- **`def _decorate_candidate_for_scenario(self, candidate: dict, scenario: str, serial: int) -> dict`**：给一个基础测试候选“化妆+贴标签”，让它变成带场景标识的正式用例。
  - 输入：原始候选（如 `{"title": "登录"}`）、目标场景（如 `"abnormal"`）、序号（如 `3`）
  - 输出：加工后的新字典（如 `{"title": "登录（异常）", "summary": "...\n场景维度：abnormal", "tags": ["abnormal", "ai-generated"], "intent_type": "negative"}`）
  - 大白话解释：就像给素颜模特化妆拍照——在标题末尾加个（异常）小标牌；在描述里插入一行“场景维度：abnormal”；把“abnormal”加进标签列表；再把内部类型从 `"abnormal"` 映射成 `"negative"`（方便下游系统理解）。保证每个生成的用例一眼就能看出它是干啥的。

- **`def build_candidate_matrix(...)`**：整个引擎的“主控台”，调用所有零件，输出最终用例列表 + 覆盖分析报告。
  - 输入：预览数据（需求原文）、最多生成多少条、组合模式（full/pairwise/intent_based）、要覆盖哪些场景、候选提取器
  - 输出：元组 `(生成的用例列表, 覆盖分析字典)`
  - 大白话解释：这是“一键生成测试清单”的按钮。它先从需求里抠出基础用例（比如“登录”“注册”），再结合用户想要的场景类型（比如“必须覆盖正常+异常”），按指定方式（全量拼？轮着配？还是直接用原始意图？）组装成最终清单，并顺手算出：共计划生成多少条？实际生成多少条？漏了哪类场景？覆盖率多少？——就像Excel自动生成报表+红绿灯提示。

## 🧩 调用关系与数据流转
```
build_candidate_matrix() 
  ├─→ normalize_combination_mode()           # 把用户乱输的模式转成标准值（如 "PAIRWISE" → "pairwise"）
  ├─→ candidate_normalizer.extract_case_candidates_from_preview()  # 从需求文本中挖出基础候选用例（如"登录"）
  ├─→ 遍历 intents → scenario_from_intent()  # 对每个测试意图判断场景类型，汇总成 detected_input_scenarios
  ├─→ 若无候选 → 补一个默认基础用例
  ├─→ 根据 normalized_mode 分支：
  │    ├─ "full"：每个基础候选 × 每个覆盖场景 → 调用 _decorate_candidate_for_scenario()
  │    ├─ "pairwise"：基础候选和覆盖场景循环配对 → 调用 _decorate_candidate_for_scenario()
  │    └─ 其他：直接截取基础候选
  ├─→ candidate_normalizer.normalize_candidates()  # 对所有生成的候选做统一清洗（去重、补字段等）
  ├─→ 遍历 normalized_candidates → scenario_from_intent()  # 再次判断每个生成用例的实际场景，统计 covered_scenarios
  └─→ 计算 missing_scenarios / ratio / status 等 → 拼成 matrix_summary 字典
```

## 💡 值得学习的写法
- **别名映射表集中管理**：`_scenario_alias()` 和 `normalize_coverage_profile()` 中用多组 `in {...}` 判断同义词（如 `"normal"` 包含 `"positive"`/`"happy"`/`"smoke"`），比一堆 `if-elif` 更清晰易维护，新增别名只需改集合。
- **防御性字符串处理链**：`str(value or "").strip().lower()` 三连击，彻底避免 `None`/空格/大小写导致的判断失败，是 Python 数据清洗的黄金套路。
- **动态覆盖检查机制**：不是简单“生成完就结束”，而是生成后再次扫描每个用例的场景类型，反向验证是否真的覆盖了用户要求的 `coverage_profile`，并给出 `missing_scenarios` 和 `coverage_ratio` —— 这才是真正对用户负责的“交付反馈”。
- **组合策略解耦设计**：`full`/`pairwise`/`intent_based` 三种模式逻辑完全隔离在 `if-elif-else` 分支内，未来加新策略（如 `weighted`）只需新增一个分支，不影响其他逻辑。

## ⚠️ 需要注意的地方
- **`scenario_from_intent()` 的双重逻辑易混淆**：当 `scene_auto_classify_enabled` 为 `False` 时走“字段优先”（看 `scene_type`/`intent_type` 字段），为 `True` 时走“文本扫描”（搜标题/摘要关键词）。新手可能忽略开关影响，以为永远是AI识别，结果关了开关却没填对字段，导致全部判成 `"normal"`。
- **`_decorate_candidate_for_scenario()` 修改标题有副作用**：它会在原 `title` 后追加 `（中文标签）`，但如果用户标题里**已经包含括号内容**（如 `"登录（兼容IE）"`），就会变成 `"登录（兼容IE）（异常）"`，语义混乱。建议加更智能的插入逻辑（如只在末尾无括号时添加）。
- **`build_candidate_matrix()` 中 `max_cases` 截断位置不一致**：`full` 模式在两层循环里都检查 `len(candidates) >= max_cases`，而 `pairwise` 模式只控制总数不超，但未限制单场景数量——可能导致某类场景（如 `abnormal`）生成过多，挤占其他场景名额。
- **`intent.get("xxx") or ""` 风险**：若 `intent` 是 `None`，`intent.get("xxx")` 返回 `None`，`None or ""` 是 `""`，看似安全；但若 `intent` 是非字典类型（如字符串），`.get()` 会报错。代码中虽有 `isinstance(raw_intent, dict)` 保护，但上游若传入奇怪类型（如 `None`），仍可能崩在 `raw_intent.get(...)`。建议统一用 `getattr(raw_intent, "get", lambda k, d="": d)("xxx", "")` 或封装安全访问函数。