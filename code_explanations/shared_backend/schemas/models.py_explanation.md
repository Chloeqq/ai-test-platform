# 📘 代码说明书
## 一句话概括  
这是一个“测试用例的身份证和说明书”集合——用标准化的电子表格（但用 Python 写的）定义了测试流程中所有关键数据长什么样、能填什么、哪些字段是必须的，确保从需求分析、自动化生成到人工审核的每个环节都看的是同一份“说明书”，不会因为各写各的而对不上号。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `schemas/models.py` | 定义整套测试流水线（需求→解析→生成→审核）中所有角色之间传递数据的“统一话术本”：规定每个字段叫什么、允许填什么值、哪些必填、哪些可选、结构怎么嵌套。就像剧组的《人物小传+分镜脚本》合订本，导演、编剧、道具组都按它干活。 |

## 🔍 核心函数/类说明
- **`class TestPointV1(BaseModel)`**：作用——描述“一个最小可执行的测试动作单元”（比如“在登录页输入密码框里填‘123456’”）的完整档案。  
  - 输入：无（它本身不接收输入，而是被其他代码用来创建实例或校验数据）  
  - 输出：无（它是一个数据模板，不是函数，不返回值；但它能自动检查你给的数据是否合规）  
  - 大白话解释：就像快递面单——有收件人（`target`）、要干啥（`action`：填/点/等）、带什么货（`value`）、为啥要寄（`description`）、优先级（`priority`）、有没有风险要人工看看（`requires_review`）、甚至附上质检报告（`dependency_review`）。谁填错格式（比如把数字填进字符串字段），它当场就红灯报警。

- **`class TestPointPlanV1(BaseModel)`**：作用——装一整套测试用例的“文件夹”，比如一个登录功能的所有测试点打包成一个计划。  
  - 输入/输出：同上，是模板，不运行，只校验。  
  - 大白话解释：就像一个带封面的测试用例 Word 文档：封面写项目名（`project`）、用例编号（`case_id`）、所属页面（`page`），里面每一页是一个 `TestPointV1`（比如“输入错误密码→提示错误”、“输入正确密码→跳转首页”），还附带整体质量评语（`quality_gate`）和追溯总结（`traceability_summary`）。

- **`class DependencyReviewV1(BaseModel)`**：作用——专门记录“这个测试点依赖哪些页面元素？靠谱吗？”的质检小票。  
  - 输入/输出：模板，用于组织依赖相关的判断结果。  
  - 大白话解释：像外卖小哥的“取餐确认单”——写了“该订单涉及元素：用户名框、密码框、登录按钮（`involved_elements`）”，“系统自动匹配到这些元素（`matched_elements`）”，“但密码框匹配信心只有 60%（`confidence`），建议人工再瞅一眼（`requires_review=True`）”，“还发现没找到‘记住我’复选框（`missing_dependencies`）”。所有这些字段都强制要求类型和结构，避免口头说“好像少了个框”。

- **`class PageObjectV1(BaseModel)`**：作用——定义“网页上每个可操作区域怎么定位”的地图（比如“用户名框 = CSS 选择器 #username”）。  
  - 大白话解释：就像乐高说明书里的“零件定位图”——左边写零件名（`elements` 的 key，如 `"username_field"`），右边写怎么找到它（`PageElementMapping`：`selector="input#username"` + `type="css"`）。编译器（生成自动化脚本的模块）靠它把 `TestPointV1.target="username_field"` 翻译成真实浏览器操作。

- **`ALLOWED_ACTIONS: frozenset[str]`**：作用——列出所有被允许的“测试动作词汇表”，比如只能写 `"click"`，不能写 `"CLICK"` 或 `"tap"`。  
  - 输入：无；它是常量，供其他代码拿来比对用。  
  - 输出：无；它是一份只读词典。  
  - 大白话解释：像学校广播操口令标准录音——老师只能喊“伸展运动”“扩胸运动”，不能即兴改成“张开胳膊抖一抖”。这里确保所有模块（解析器、生成器、审核员）对“点击”这件事用同一个词，避免歧义。

## 🧩 调用关系与数据流转  
整个文件**不包含任何运行逻辑**（没有 `def` 函数、没有 `if` 判断、没有调用其他模块），它只是“静态蓝图”。所以没有传统意义上的“谁调用谁”，但它的数据会被其他模块按以下方式使用：

```
[需求文档/接口文档] 
       ↓ （被解析器读取 → 提炼成原始数据）
[解析器模块] → 创建 TestPointV1 实例（填入 action/value/target 等）→ 自动用 Pydantic 校验格式  
       ↓ （校验失败则报错，成功则继续）  
[归一化模块] → 补充 involved_elements / confidence / dependency_review 等字段 → 再次用 TestPointV1 校验  
       ↓  
[编译器模块] → 读取 TestPointV1.steps 和 PageObjectV1.elements → 绑定 selector → 生成 Playwright/Selenium 脚本  
       ↓  
[质量门禁模块] → 读取 TestPointPlanV1.quality_gate 和 QualityGateThresholds → 检查是否达标（如 confidence ≥ 0.3）  
       ↓  
[人工审核界面] → 展示 TestPointV1.dependency_review 和 warnings → 提醒“这个依赖匹配度低，请确认”
```

> ✅ 关键点：所有模块都**主动引用**这些类来创建实例或校验数据，Pydantic 在实例化时自动做类型检查、默认值填充、空值保护——就像用带防伪码的定制信封，塞错内容就封不上。

## 💡 值得学习的写法  
- **`Field(default_factory=list)`**：不用写 `[]`（避免可变默认参数陷阱），而是用工厂函数安全生成新空列表——像每次发快递都现场拆一个新信封，而不是大家共用一个旧信封（旧信封里可能混着别人的东西）。  
- **`frozenset` 替代 `set` 或 `list` 存词汇表**：`ALLOWED_ACTIONS` 不可修改、不可重复、查询极快（O(1)），且明确表达“这是固定词典，别想增删改”——像贴在墙上的《禁止行为清单》，白纸黑字，不接受商量。  
- **嵌套模型设计（如 `dependency_review: DependencyReviewV1`）**：把复杂质检信息封装成独立小模块，既保持 `TestPointV1` 主体清爽，又让质检部分可单独复用或单元测试——像汽车仪表盘：主界面只显示“发动机温度过高”，点进去才展开冷却液水位、风扇转速、传感器状态等子页面。  
- **`model_validator`（虽未在此文件使用但已导入）**：为未来预留“跨字段联动校验”能力（比如：“如果 `action='fill'`，则 `value` 必须非空”），这种校验无法靠单字段 `Field` 完成，需要模型级钩子——像机场安检：不仅查你有没有登机牌（单字段），还查登机牌日期和你的护照有效期是否匹配（跨字段）。

## ⚠️ 需要注意的地方  
- **`value: Any = None` 是双刃剑**：允许填任意类型（字符串/数字/字典/列表），方便灵活（比如填 `"abc"` 或 `{"x":1}`），但**失去类型安全**——如果后续代码假设 `value` 一定是字符串却收到字典，就会崩溃。💡 正确做法：尽量用具体类型（如 `value: str | int | None`），或加 `@field_validator` 做运行时约束。  
- **`steps: list[TestPointStepV1] | None = None` 中的 `| None` 易被忽略**：意味着 `steps` 字段可以是 `None` 或列表，但很多开发者会直接 `.append()` 导致 `AttributeError`。✅ 安全写法：`if tp.steps is None: tp.steps = []; tp.steps.append(...)` 或用 `default_factory=list`（像其他字段一样）。  
- **`Field(default="")` vs `= ""`**：看起来一样，但 `Field(default="")` 明确告诉 Pydantic “这是默认值，参与校验”，而裸写 `key: str = ""` 可能在某些高级场景（如 `exclude_unset=True`）行为不同——就像填表时写“默认填‘无’”（Field） vs “随手先写个‘无’”（裸赋值），前者是制度，后者是习惯。  
- **`Any` 类型泛滥风险**：`value: Any`、`metadata: dict[str, Any]` 虽灵活，但会让 IDE 失去智能提示、静态检查失效。⚠️ 如果 `metadata` 固定存 `{"author": "xxx", "reviewed_at": "2024-01-01"}`，就该定义 `metadata: TestPointMetadata` 类——好比快递单上“备注”栏，与其写“随便写”，不如印上“【寄件人】 【预计送达日】”两个固定格子。