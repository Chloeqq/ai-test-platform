# 📘 代码说明书
## 一句话概括  
这是一个“合同质检员”程序，专门检查自动化测试流程中各环节（需求、执行草稿、标准化测试点）之间的数据是否对得上、缺不缺、写得对不对，就像房产中介在签合同前逐条核对“面积、价格、产权人”是否一致、有没有漏填或矛盾。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `schemas/validator.py` | 提供一套完整的“跨层一致性检查工具”，确保从原始需求（RequirementSpec）→ 执行步骤草稿（ExecutionDraft）→ 最终标准化测试点（normalized points）→ 页面元素映射（page object）整个链条的数据结构合理、字段完整、引用有效、逻辑自洽。 |

## 🔍 核心函数/类说明
- **`class ValidationResult`**：一个“检查报告本”，用来记录检查过程中发现的问题（错误/警告）和最终是否通过。  
  - 输入：无（初始化时可设默认值）  
  - 输出：一个带 `.valid`（是否全通过）、`.errors`（错误列表）、`.warnings`（提醒列表）的对象  
  - 大白话解释：就像你去体检，医生不会只说“你合格”或“不合格”，而是给你一张报告单——上面写着“血压偏高（⚠️警告）”、“血糖超标（❌错误）”，最后盖个章：“本次体检未通过”。这个类就是那张可随时添内容、还能合并多张报告的电子版体检单。

- **`class ContractValidator`**：整个文件的主角，是那个拿着检查清单、挨个核对的“质检员”。它不干活（不生成测试用例），只负责“挑毛病”。  
  - 输入：各种中间产物（比如需求字典、步骤列表、页面元素字典）  
  - 输出：一个 `ValidationResult` 报告  
  - 大白话解释：就像装修验收师傅——他不管水电谁来装、瓷砖谁来贴，但他会带着《装修验收 checklist》站在新房里，一条条对照：开关有没有？插座够不够？地砖有没有空鼓？这里少个灯、那里多根线，他都记下来。这个类就是这位师傅 + 他的 checklist。

- **`def validate_requirement_spec()`（V1）**：检查“需求说明书”是否格式规范、关键信息齐全。  
  - 输入：一个叫 `spec` 的字典（比如 `{"page": "登录页", "test_intents": [{"intent_id": "login_001", "title": "用户能输入账号密码"}]}`）  
  - 输出：一份报告（比如：“✅ page 不为空；✅ intent_id 都有且不重复；⚠️ parse_confidence 是 'high'，不是数字，已忽略”）  
  - 大白话解释：相当于 HR 检查简历——姓名写了没？学历填了没？有没有两个“工作经验”写同一个公司？有没有 ID 号重复？它不关心你能力如何，只管“这简历能不能收”。

- **`def validate_execution_draft()`（V3）**：检查“执行步骤草稿”是否结构正确、每一步的“动作”是否合法、需要“点击哪个按钮”时有没有写清楚按钮代号。  
  - 输入：一个 `draft` 字典（含 `steps: [{"action": "click", "target": "btn_submit"}]`），外加一个允许的按钮代号集合（比如 `{"btn_submit", "input_username"}`）  
  - 输出：报告（比如：“✅ steps 是列表；⚠️ action 'hover' 在允许列表里；❌ target 'btn_login' 不在按钮库里！”）  
  - 大白话解释：就像导演看分镜脚本——镜头1：推近镜头拍手（✅），镜头2：演员要“摸鱼”（❌剧本没这动作！），镜头3：喊“开拍”但没写让谁说话（⚠️缺主语）。它确保脚本语法对、用词在词典里、关键信息不空。

- **`def validate_normalized_test_points()`（V4）**：检查最终整理好的“标准化测试点列表”是否每个点都填了必要字段（比如意图ID、动作、预期结果）。  
  - 输入：一个测试点列表（如 `[{"intent_id": "login_001", "action": "fill", "target": "input_pwd"}]`），`strict=True` 表示“必须全填”，`False` 表示“缺了也先记着，别拦着我跑”。  
  - 输出：报告（比如：“⚠️ 第0项缺 expected_result（填‘密码框应显示掩码’）；✅ intent_id+step_index 组合不重复”）  
  - 大白话解释：就像老师批改学生交的实验报告——标题写了没？步骤写了没？结论写了没？如果要求“必须写”，那就少一项打叉；如果只是“建议写”，那就画个圈提醒。

- **`def validate_intent_coverage()`（V5a）**：检查“需求里写的测试目标”和“实际生成的测试点”是否一一对应（不能有需求没覆盖，也不能有测试点凭空多出来）。  
  - 输入：需求字典 + 测试点列表  
  - 输出：报告（比如：“❌ 需求里有 intent_id 'logout_001'，但测试点里找不到；⚠️ 测试点里有 'debug_mode_on'，但需求里没提”）  
  - 大白话解释：就像对照菜谱做菜——菜谱说“放盐、放糖、放醋”，你做完端上来只有盐和糖，厨师长就会问：“醋呢？”；如果你还额外加了辣椒油，他也会问：“菜谱没写这个啊？”。它保证“做的=要做的”。

- **`def validate_element_resolution()`（V5b）**：检查测试点里写的“点击 btn_submit”、“输入 input_user”，这些按钮/输入框名，在真实的网页元素字典里是否存在。  
  - 输入：测试点列表 + 页面元素字典（如 `{"elements": {"btn_submit": {...}, "input_user": {...}}}`）  
  - 输出：报告（比如：“❌ 测试点第2步 target 'btn_login' 不在页面元素库里；⚠️ involved_elements 里的 'sidebar_nav' 也没找到”）  
  - 大白话解释：就像快递员送件——你下单写“送到 302 房”，他到楼下一查，发现这栋楼根本没有 302 房（❌严重问题）；或者你写“顺便把门口鞋架擦下”，但鞋架根本不在楼道里（⚠️小问题）。它确保所有“指名道姓”的操作对象真实存在。

- **`def validate_full()`**：质检员的“一键全检”按钮，自动按顺序运行 V4 → V5a → V5b（如果提供了对应数据），把所有报告合并成一份总报告。  
  - 输入：需求（可选）、测试点（必填）、页面元素（可选）、是否严格模式  
  - 输出：一份汇总报告  
  - 大白话解释：就像你把手机送去苹果售后——不用自己说“查电池、查屏幕、查充电口”，工程师按 SOP 全部过一遍，最后给你一张《综合检测报告》。

## 🧩 调用关系与数据流转  
```
validate_full()  
│  
├─→ validate_normalized_test_points()   ← 检查测试点本身填得全不全（V4）  
│      ↓  
│     （返回 ValidationResult A）  
│  
├─→ validate_intent_coverage()         ← 用 requirement_spec + normalized_points 比对需求和测试点（V5a）  
│      ↓  
│     （返回 ValidationResult B）  
│      ↓  
│     result.merge(B) → A.errors/warnings += B.errors/warnings, A.valid &= B.valid  
│  
└─→ validate_element_resolution()       ← 用 normalized_points + page_object 检查元素是否存在（V5b）  
       ↓  
      （返回 ValidationResult C）  
       ↓  
      result.merge(C) → A.errors/warnings += C.errors/warnings, A.valid &= C.valid  
       ↓  
      ← 返回最终合并后的 ValidationResult（A+B+C）
```  
💡 简单说：`validate_full` 是“总指挥”，它把三个专项检查（填表检查、需求对账、元素查户口）的结果“粘”在一起，形成最终成绩单。

## 💡 值得学习的写法  
- **`ValidationResult` 的 `merge()` 方法**：像乐高积木一样，能把多份检查报告无缝拼成一份，避免手动复制粘贴错误，也方便后续扩展新检查项。  
- **`frozenset` 定义 `ACTIONS_REQUIRING_TARGET`**：把一堆需要“目标”的动作（如 click/fill）存成不可变集合，查询快（O(1)）、安全（不会被误改）、语义清晰（一看就知道这是“需目标动作清单”）。  
- **`strict` 参数贯穿 V4/V5a/V5b**：同一套检查逻辑，通过一个开关就能切换“温柔提醒模式”和“严格卡死模式”，适配不同阶段（开发调试 vs 上线前终审）。  
- **用 `str(...).strip()` 统一处理字符串字段**：哪怕传进来是 `None`、数字、带空格字符串，都能安全转成干净字符串，避免 `AttributeError` 或隐藏空格导致校验失败。  
- **`seen_ids` / `seen_intent_step_pairs` 用 set 去重**：高效检测重复 ID 或重复组合（如 `("login_001", 0)`），比嵌套循环快得多，代码也更清爽。

## ⚠️ 需要注意的地方  
- **`validate_execution_draft()` 中的 `case` 和 `execution` 解包逻辑容易误解**：它假设 `draft` 可能是 `{case: {...}}` 或直接是 `{execution: {...}}`，所以做了两层判断。如果未来数据结构变化（比如加了 `root` 层），这里会静默失效，建议加日志或类型注释提醒。  
- **`validate_intent_coverage()` 对 `precondition` 和 `login` 动作的特殊跳过**：它认为这两类测试点“不对应具体需求意图”，但如果业务中新增了类似语义的动作（如 `setup_env`），容易被遗漏，需同步更新此处逻辑。  
- **`validate_element_resolution()` 中 `involved_elements` 的检查有 `strict` 分支**：对 `login`/`goto`/`assert_url` 这几个动作，即使 `involved_elements` 缺失也不报错——但若某天这些动作也需要关联元素（比如 `login` 要关联验证码图片），当前逻辑会漏检。  
- **所有函数都假设输入是 `dict` 或 `list`，但没做深层类型防护**：比如 `spec.get("test_intents")` 返回的是 `list`，但里面每个 `intent` 是否真是 `dict`？代码里做了 `isinstance(intent, dict)` 检查，但若嵌套更深（如 `intent.get("steps")[0].get("action")`），就不再检查了——属于“浅层防御”，深层数据异常可能抛原生异常而非友好提示。  
- **`ALLOWED_ACTIONS` 来自 `from .models import ALLOWED_ACTIONS`，但文件里没定义它**：这意味着 `ALLOWED_ACTIONS` 必须在 `models.py` 中正确定义为 `set` 或 `frozenset`，否则运行时会报错。新人接手时容易忽略这个隐式依赖。