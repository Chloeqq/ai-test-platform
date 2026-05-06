# 📘 代码说明书
## 一句话概括
这是一个“智能检查员”，专门在用户点击「生成自动化脚本」前，快速扫描他们选中的测试意图（比如“登录”“下单”），逐条检查是否缺关键信息、元素名写对没、页面结构能否识别，最后给出红黄绿灯式的反馈（阻塞/警告/通过）。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `workbench_generation_api/precheck_selected_intents_service.py` | 提供「预检服务」：接收用户选择的测试意图列表，检查它们是否具备自动生成脚本的条件，并返回每条意图的问题清单和整体健康报告 |

## 🔍 核心函数/类说明
- **`class PrecheckSelectedIntentsService`**：整个预检流程的“指挥中心”，把一堆零散检查步骤组织成有条理的流水线。  
  - 输入：初始化时传入一个 `WorkbenchContext`（相当于工作台的“身份证+工具包”，里面装着项目配置、页面规范、元素映射表等）；执行时传入 `payload`（用户从前端发来的原始数据，像字典一样包含 `page`、`selected_intent_ids` 等字段）。  
  - 输出：一个结构化结果字典，含两大部分：`items`（每条意图的详细检查结果）和 `summary`（整体统计，比如共15条，3条阻塞、5条警告）。  
  - 大白话解释：就像你准备做一道菜前，厨师长会快速翻看你的食材清单——有没有漏买盐？葱姜蒜是不是写成了“大葱”“小蒜”（但实际系统里叫“葱段”“姜末”）？锅具是否备好？然后告诉你：“3样缺货，别开火；5样不标准，小心糊锅；剩下7样OK，可以下锅”。

- **`_normalized_text(value)`**：给任何输入“做清洁”的小帮手。  
  - 输入：任意类型的数据（字符串、数字、None、空对象等）。  
  - 输出：一个干净的字符串（如果是 `None` 或空值，就变成空字符串 `""`；再把前后空格去掉）。  
  - 大白话解释：就像你收到一张手写的便签，字迹潦草还带涂改，它负责帮你擦掉墨点、裁掉毛边、统一用正楷重抄一遍，确保后面所有检查都基于“干净文本”进行，避免 `"  登录  "` 和 `"登录"` 被当成两个不同东西。

- **`_is_non_dom_involved_element(value)`**：判断某个“涉及元素”是不是“不用找HTML”的特殊角色。  
  - 输入：任意值（比如 `"页面"`、`"地址栏"`、`None`）。  
  - 输出：`True` 或 `False`。  
  - 大白话解释：就像检查购物清单里的“商品”，发现写着“运费”“满减券”——这些不是货架上的实物，不用去仓库找，直接打个勾就行。这里也一样：`"页面"`、`"浏览器地址栏"` 这些是抽象概念，不对应网页上某个 `<button>`，所以跳过 DOM 元素校验环节。

- **`resolve_page_object(project, page)`**（来自外部模块）：根据项目名和页面名，“召唤”出该页面的元素地图（即每个按钮/输入框在代码里叫什么名字）。  
  - 输入：`project="mall"`（商城项目）、`page="login"`（登录页）。  
  - 输出：一个字典，例如 `{"username_input": "#user", "login_btn": "button[type=submit]"}`，或抛出异常（如果地图不存在/损坏）。  
  - 大白话解释：就像你去陌生城市旅游，先打开手机里的“高德地图”，输入“北京南站”，它立刻显示出口A/B/C、地铁14号线入口、卫生间位置……这个函数就是调出“网页版高德”，告诉后续检查：“你要找的‘用户名框’，代码里叫 `username_input`，对应 CSS 选择器 `#user`”。

## 🧩 调用关系与数据流转
```
用户提交 payload（JSON 数据） 
        ↓
PrecheckSelectedIntentsService.execute() 接收并启动检查
        ↓
→ 先标准化字段：project/page → 用 _normalized_text 清洗
→ 获取候选意图列表 → 从 payload 提取 raw_candidates + selected_intent_ids
        ↓
→ 调用 preview_store.resolve_selected_candidates()  
   （根据 preview_id 查历史快照，或 fallback 到原始 raw_candidates）
        ↓
→ 调用 self._context.candidate_normalizer.normalize_candidates()  
   （统一格式：补默认值、转小写、去重等）
        ↓
→ 调用 resolve_page_object(project, page)  
   （尝试加载当前页面的“元素地图”，失败则记下错误）
        ↓
→ 对每个 normalized_candidate 循环检查：
     ├─ 提取 intent_id/title/involved_elements/expected_result 等字段 → 全部用 _normalized_text 清洗
     ├─ 过滤掉 _NON_DOM_INVOLVED_ELEMENTS（如"页面"）→ 只留要查 HTML 的元素名
     ├─ 调用 resolve_involved_element_codes(mappable_list, page_object)  
        （拿着“用户名框”“登录按钮”这些名字，去 page_object 地图里查真实选择器，返回 codes + 未知元素列表）
     └─ 综合判断 status（block/warn/ok）并收集 reasons
        ↓
→ 汇总所有 items + 统计 status_counts → 返回最终报告
```

## 💡 值得学习的写法
- **防御式清洗无处不在**：所有可能为 `None` 或带空格的字段（`payload.project`、`candidate.title` 等）都第一时间用 `_normalized_text()` 处理，避免后续 `.lower()` 或 `in` 判断报错，也防止 `"  login  "` 和 `"login"` 被误判为不同项。
- **状态累积式判断**：检查 `intent_id` 缺失 → 设 `status="block"`；再发现 `expected_result` 缺失 → 只在 `status=="ok"` 时才升级为 `"warn"`，不会把 `"block"` 错误覆盖成 `"warn"`，逻辑清晰不打架。
- **fallback 机制优雅**：当 `resolve_page_object()` 失败时，不中断流程，而是记下 `page_object_error`，并在每条意图检查中统一追加一条“页面对象不可用”的原因，既保证容错，又不掩盖问题。
- **语义化常量分组**：把 `"页面"` `"地址栏"` 等非 DOM 元素集中定义为 `_NON_DOM_INVOLVED_ELEMENTS` 集合，比散落各处的 `if value in ["页面", "地址栏"]` 更易维护、更易读懂。

## ⚠️ 需要注意的地方
- **`getattr(payload, "xxx", "")` 的隐式假设**：代码默认 `payload` 是一个支持 `getattr` 的对象（如 Pydantic 模型或魔改字典），但如果传入纯字典 `{}`，`getattr({}, "page", "")` 会返回 `""`（没问题）；但若传入 `None`，`getattr(None, "page", "")` 会直接报 `AttributeError` —— 实际上线前需确认前端传参结构或加一层 `if payload is None` 保护。
- **`involved_elements` 类型校验脆弱**：只检查 `isinstance(candidate.get("involved_elements"), list)`，但如果它是 `tuple`、`set` 或自定义迭代器，就会被跳过，导致 `mappable_involved_elements` 为空 → 触发“缺少 involved_elements”警告。建议改为 `isinstance(..., (list, tuple))` 或用 `list(candidate.get("involved_elements", []))` 更鲁棒。
- **硬编码最大数量 20**：`if len(normalized_candidates) > 20:` 抛出错误，但这个限制值写死在代码里，未来调整需改源码。更佳做法是抽成配置项（如 `settings.MAX_PRECHECK_CANDIDATES = 20`）。
- **`page_object_error` 的 key 不确定性**：取 `page_object_error.get("reason") or page_object_error.get("message")`，依赖外部异常类 `ExecutionCompilerError.to_detail()` 总是返回含 `"reason"` 或 `"message"` 的字典。若未来异常结构变更（比如改成 `"error_msg"`），此处会拿到空字符串，降低报错可读性。建议加兜底：`or "未知错误"`。