# 📘 代码说明书
## 一句话概括
这是一个“网页操作指令翻译器”：它把人类写的、带语义的自动化测试步骤（比如“点击登录按钮”），根据页面结构定义（page object），精准翻译成浏览器能执行的具体定位器（如 CSS 选择器），就像「厨师按菜谱找调料柜里的瓶子」一样。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `mapping_engine.py` | 负责将抽象的测试步骤（IR，即中间表示）和页面元素定义（page object）匹配起来，生成带具体选择器的可执行指令 |

## 🔍 核心函数/类说明
- **`class PageObjectRegistry`**：相当于「网页元素地图册管理员」  
  - 输入：一个描述页面上所有按钮/输入框/标题等元素的字典（比如 `{"login_btn": {"selector": "#login-button", "type": "button"}}`）  
  - 输出：无直接返回值；内部建好一张“名字 ↔ 选择器”的速查表  
  - 大白话解释：它把开发或测试人员写的「页面元素说明书」（用名字描述元素）整理成一本翻页就能查到具体 CSS 选择器的小词典。支持嵌套写法（如 `"form.username"`），也自动处理空格、空字符串等脏数据，避免程序崩溃。

- **`class MappingEngine`**：相当于「指令翻译中心」  
  - 输入：页面元素地图册（`PageObjectRegistry` 实例） + 一条测试步骤（如 `{"action": "click", "target": "login_btn"}`）  
  - 输出：翻译后的步骤（如 `{"action": "click", "selector": "#login-button", "element_type": "button"}`）  
  - 大白话解释：它拿到一句“人话指令”（目标是 `login_btn`），查地图册找到对应的选择器，再把整条指令“翻译”成浏览器能听懂的“机器话”，还顺手校验格式是否合法（比如有没有漏写 `target`）。

- **`def map_ir_to_selectors()`**：相当于「一键翻译全家桶」  
  - 输入：整套测试流程（IR，含多个步骤）+ 页面元素说明书  
  - 输出：整套已翻译好的、带选择器的步骤列表  
  - 大白话解释：不用你一条条翻译，它帮你把整个测试脚本（比如 10 步操作）一次性全部转成浏览器能执行的版本，省时省力。

- **`def build_preview_payload()`**：相当于「需求信息整理员」  
  - 输入：任意杂乱的需求数据（可能来自前端表单、API 请求或对象实例）  
  - 输出：一个干净、字段统一、类型安全的字典（比如确保 `project` 是字符串，`input_sources` 是列表）  
  - 大白话解释：它不挑食——不管是 JSON 字典、Python 对象还是 None，都能温柔地从中“抠出”需要的字段，并填上默认值（比如没填项目名就设为空字符串），保证后续流程不会因为数据缺胳膊少腿而报错。

- **`_normalize_selector_list()`**：相当于「选择器清洁工」  
  - 输入：可能是字符串（`"#btn"`）、字符串列表（`["#btn", ".submit"]`）或乱七八糟的东西（`None`, `123`, `""`）  
  - 输出：一个干净的非空字符串列表（如 `["#btn"]`）  
  - 大白话解释：它专门对付用户输错的 selector——自动去掉空格、过滤空项、把数字转成字符串，让后面逻辑不用操心“脏数据”。

## 🧩 调用关系与数据流转
```
build_preview_payload(...)  
    ↓（提取并规整原始需求数据）  
map_ir_to_selectors(ir, page_object, ...)  
    ↓（创建翻译引擎）  
        → MappingEngine.__init__(page_object=...)  
            → PageObjectRegistry.__init__(page_object)  
                → PageObjectRegistry.register_entries(...)  
                    → _normalize_entry(...)  
                        → _normalize_selector_list(...)  
    ↓（开始翻译整份 IR）  
        → MappingEngine.map_ir(...)  
            → schema_validator.validate_ir(...)  ← 先校验整体结构  
            → for each step:  
                → MappingEngine.map_step(step)  
                    → schema_validator.validate_step(...)  ← 校验单步  
                    → PageObjectRegistry.resolve(target)  
                        → PageObjectRegistry._entries.get(...)  
                    → 构造 mapped dict（拼装 action + selector + value + ...）  
    ↓（返回翻译完成的 IR）  
→ 最终得到 { "steps": [ {...}, {...} ] }
```

## 💡 值得学习的写法
- ✅ **错误分类清晰，自带上下文**：自定义了 `IRValidationError`、`TargetNotFoundError` 等多种错误类型，每种都带 `code`（方便前端识别）、`message`（给人看）和 `detail`（给开发者调试用），像“错误身份证”一样结构化。
- ✅ **防御式数据清洗无处不在**：所有外部输入（`target`、`selector`、`page_object` 键名等）都经过 `.strip()`、`str() or ""`、`isinstance(..., Mapping)` 判断，不怕前端传 `null`、数字、空格甚至 `undefined`。
- ✅ **嵌套 page object 的智能展开**：支持 `"form": {"username": {"selector": "..."} }` 写法，并自动推导出 `target="form.username"`，比硬写一长串更易维护，且逻辑藏在 `_normalize_entry` 里不污染主流程。
- ✅ **dataclass + frozen=True 保安全**：`SelectorBinding` 用不可变数据类，确保一旦生成就不能被意外改写（比如防止某个函数偷偷改了 `selector`），提升可靠性。

## ⚠️ 需要注意的地方
- ⚠️ **`resolve()` 方法会抛异常，但没做重试或兜底**：如果 `target` 找不到（比如拼错名字），直接 `raise TargetNotFoundError` —— 调用方必须用 `try/except` 包裹，否则整个流程中断。新手容易忘记加错误处理。
- ⚠️ **`_normalize_selector_list()` 对非字符串/非列表输入直接返回空列表**：比如传入 `42` 或 `{"a":1}`，它默默返回 `[]`，然后触发 `selector_missing` 错误。表面友好，实则掩盖了原始数据类型问题，调试时可能困惑“我明明传了东西，怎么变没了？”。
- ⚠️ **`preserve_target=True` 是“额外赠送”，不是默认行为**：开启后会在输出里多加 `"target": "xxx"` 字段，但大多数下游（如浏览器执行器）并不需要它。若误开，可能造成冗余字段或 JSON 体积增大，建议只在调试或日志场景开启。
- ⚠️ **`build_preview_payload()` 中 `openapi_spec` 类型检查有坑**：它先用 `_payload_value(payload, "openapi_spec")` 取值，再判断是不是 `dict`，但如果 `openapi_spec` 是个字符串（比如 `"{}"`），就会跳过赋值变成 `None`，导致后续解析失败——这里应优先尝试 `json.loads()` 或明确文档约定类型。