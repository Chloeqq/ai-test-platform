# 📘 代码说明书
## 一句话概括
这是一个「测试意图翻译机」：把产品经理写的自然语言测试需求（比如“点击登录按钮”“输入用户名”），一步步翻译成浏览器能执行的自动化脚本（如 Playwright 代码），中间经过标准化、校验、绑定页面元素、生成可运行指令等完整流程。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `execution_compiler.py` | 测试用例的「编译中枢」——把原始测试点（test points）→ 标准化动作 → 中间表示（IR）→ 绑定真实页面元素 → 渲染成可执行步骤，甚至还能生成 Python 脚本 |

## 🔍 核心函数/类说明
- **`compile_execution_steps()`**：整个编译流程的「总开关」  
  - 输入：`test_points`（一串人话描述的测试点，如 `[{"intent_id": "login", "steps": [{"action": "input", "target": "username", "value": "admin"}]}]`） + `page_object`（页面上所有按钮/输入框的定位信息，类似地图）  
  - 输出：一个列表，每个元素是浏览器能直接执行的指令，例如 `{"action": "fill", "selector": "#username-input", "value": "admin"}`  
  - 大白话解释：就像把「去超市买牛奶」这个需求，拆解成「打开手机地图 → 搜索‘家乐福’ → 点击第一个结果 → 进店 → 直走5米 → 左转 → 拿起蓝色包装的牛奶」——它把模糊的人话，变成浏览器一步一步能干的精确动作。

- **`normalize_test_points()`**：给测试点做「体检和建档」  
  - 输入：原始 `test_points` 列表  
  - 输出：清洗后带编号、步骤、关联元素的结构化数据（补全缺失字段、校验必填项、统一格式）  
  - 大白话解释：检查每张「测试需求小纸条」有没有写清楚“想测什么”（`intent_id`）、有没有步骤（`steps`）、有没有提到涉及哪些页面元素（`involved_elements`）。不合格的直接打回重写，合格的贴上标签（`point_index`）放进档案柜。

- **`normalize_test_points_to_actions()`**：把「人话步骤」翻译成「标准动词」  
  - 输入：标准化后的测试点  
  - 输出：统一动作类型（如 `"input"`/`"click"`/`"assert"`）+ 明确目标（`target`）+ 补充参数（`value`/`assertion`）的列表  
  - 大白话解释：把各种说法归一化——“填入”“输入”“填写”都变成 `input`；“跳转到”“访问”“导航至”都变成 `navigate`；“检查是否可见”“验证显示”都变成 `assert` + `visible`。相当于给不同方言统一配上了普通话字典。

- **`build_execution_ir()`**：生成「中间语言」（IR）——测试的「通用身份证」  
  - 输入：标准化动作列表  
  - 输出：带版本号（`"execution-ir/v1"`）和统一字段的 `{"steps": [...]}` 结构  
  - 大白话解释：不依赖任何具体技术（Playwright/Selenium），只定义「要做什么」「对谁做」「怎么判断成功」。就像国际快递单，不管用顺丰还是DHL，单子上的收件人、物品、签收要求都是一样的。

- **`bind_targets()`**：给动作「配钥匙」——把抽象目标（如 `"username"`）匹配到真实页面元素（如 `css: #login-form input[name='username']`）  
  - 输入：IR + 页面对象（`page_object`，含所有元素的 selector 和别名）  
  - 输出：每个步骤都带上 `selector`、`locator_type` 等真实定位信息  
  - 大白话解释：你告诉它“点登录按钮”，它得知道这个按钮在网页里到底叫什么、长什么样、怎么找到它。这里会查元素地图（`page_object`），还支持别名（比如 `"user-field"` 自动映射到 `"username"`），像快递员拿着地址找门牌号。

- **`render_execution_steps()`**：生成「最终执行指令」——给浏览器看的「操作说明书」  
  - 输入：已绑定元素的 IR  
  - 输出：完全可执行的步骤列表（含 `action`、`selector`、`value`、`confidence` 等）  
  - 大白话解释：把「点登录按钮」真正变成「用 CSS 选择器 `#login-btn` 找到它，然后调用 `.click()` 方法」。还会检查有没有漏掉关键信息（比如 `input` 步骤没给值，就立刻报错提醒）。

- **`compile_playwright_python()`**：把指令「写成 Python 代码」——自动生成 Playwright 脚本  
  - 输入：IR + 页面对象  
  - 输出：一段可直接运行的 Python 函数（`def run_case(page): ...`）  
  - 大白话解释：不是只给指令，而是帮你把整套操作写成完整的 `.py` 文件，复制粘贴就能跑。比如 `page.locator('#username').fill('admin')` —— 就是程序员天天写的那种代码。

- **`PreviewTestPointsCompiler` 类**：旧版「需求预览编译器」（已弃用）  
  - 作用：接收 PRD/用户故事等多源输入，调用后台解析服务生成测试点初稿，并输出分析报告（Markdown）  
  - 大白话解释：像一个「测试需求助理」——你丢给它一份产品文档或 bug 描述，它自动读一遍，告诉你“这个需求大概要测哪些点？有哪些歧义？风险在哪？”，并生成带统计数字的分析报告（供人工复核）。

## 🧩 调用关系与数据流转
```
compile_execution_steps() 
    ↓ 接收 test_points + page_object
→ normalize_test_points() 
    ↓ 输出结构化测试点（带 intent_id、steps、involved_elements）
→ normalize_test_points_to_actions() 
    ↓ 输出标准化动作列表（统一 action 类型、target、value）
→ build_execution_ir() 
    ↓ 输出带版本号的中间表示 IR（{"version": "...", "steps": [...]})
→ bind_targets() 
    ↓ 查 page_object 地图，为每个 step 补上 selector/locator_type
→ render_execution_steps() 
    ↓ 校验完整性，生成最终可执行步骤（含 confidence、traceability）
→ [返回给调用方]
```
额外分支：
- `compile_playwright_python()` 可独立调用，走 `map_ir_to_selectors()` → 生成 Python 代码字符串  
- `PreviewTestPointsCompiler.compile_preview()` 是另一条路：走 `parse()` 远程服务 → 生成需求分析报告（非执行步骤）

## 💡 值得学习的写法
- **「多级 fallback」参数查找**：比如 `_resolve_metric_rule()` 会按顺序检查 `step.metric_rule` → `step.rule` → `point.metric_rule` → `fallback_value`，像查通讯录：先看当前联系人备注，没有就看群备注，再没有就用默认签名。避免硬编码，灵活又健壮。
- **「正则预编译 + 单次清理」**：`_LIST_PREFIX_RE` 和 `_SPACE_RE` 在文件顶部就 `re.compile()`，后续所有 `_normalized_text()` 都复用，避免反复编译正则的性能浪费——像提前印好印章，要用时直接盖。
- **「业务类型兼容性检查」**：`_is_business_type_allowed_for_action()` 严格限制「什么类型的元素能做什么事」（比如 `textarea` 可以 `input`，但 `button` 不可以），像交通规则：红灯停、绿灯行，防止误操作引发诡异错误。
- **「置信度钳位」**：`_clamp_confidence()` 强制把任意输入（0.5、123、-42）变成 `0.0~1.0` 区间，像给水龙头装限流阀，永远不超压也不断流。
- **「错误分类 + 上下文透传」**：`ExecutionCompilerError` 不仅存 `message`，还带 `code`（机器可读）、`reason`（人话原因）、`stage`（出错环节）、`to_detail()` 方法——像维修单：故障现象、零件编号、发生工序、建议处理方式，一目了然。

## ⚠️ 需要注意的地方
- **`target` 字段容易被忽略但极其关键**：几乎所有动作（`input`/`click`/`assert`）都强制要求 `target`，且 `bind_targets()` 会用它查页面元素。如果写成 `"target": "用户名"`（中文）而 `page_object` 里只有 `"username"`，就会报 `target not found`——务必确保 target 名称和页面对象里的 key 完全一致（推荐全英文、小写、下划线）。
- **`navigate` 和 `assert_url` 是特例**：它们不需要 `target`/`selector`，反而会清空这些字段。如果误给 `target: "home"`，绑定阶段不会报错，但渲染时会被忽略——容易让人困惑「为什么我的 target 消失了？」。
- **`input` 步骤的 `value` 必须显式提供**：即使想输空字符串，也得写 `"value": ""`，不能省略或写 `null`。否则 `render_execution_steps()` 会直接抛错，因为浏览器 `.fill("")` 和 `.fill()`（无参数）行为完全不同。
- **`assert_metric` 的字段命名易混淆**：它同时接受 `metric_rule`、`rule`、`assert_rule` 作为值来源，但最终输出字段叫 `metric_rule` 和 `rule`（两个同值字段）。新手可能以为要填两个东西，其实填一个就行，另一个是兼容旧字段的别名。
- **`PreviewTestPointsCompiler` 已废弃**：文档明确标注 `DEPRECATED`，新项目必须改用 `run_preview_pipeline`。继续用它会导致未来升级失败，且无法享受新功能（如多源输入融合、质量门禁增强）。
- **`compile_playwright_python()` 不做安全转义**：生成的 Python 字符串直接拼接 `selector` 和 `value`，如果 `selector` 含单引号（如 `"#btn[data-id='abc']"`）或 `value` 含 `'`，会导致语法错误。实际使用前需手动处理或加 `repr()` 包裹（代码里只做了基础 `replace("'", "\\'")`，不够鲁棒）。