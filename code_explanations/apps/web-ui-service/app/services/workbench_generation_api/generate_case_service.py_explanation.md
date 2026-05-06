# 📘 代码说明书
## 一句话概括  
这是一个“智能测试用例生成服务”，它接收用户填写的需求（比如页面名、功能描述、API文档等），结合已有测试用例和页面结构信息，自动生成结构清晰、可直接使用的测试用例，并返回给前端展示。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `workbench_generation_api/generate_case_service.py` | 主力生成引擎：把用户输入的零散信息（页面、需求、API、历史用例等）整合、清洗、补全，调用底层能力生成标准化测试用例，并统一格式返回给前端 |

## 🔍 核心函数/类说明
- **`class GenerateCaseService`**：整个生成流程的“指挥中心”  
  - 输入：一个 `WorkbenchContext`（相当于项目的百宝箱，装着所有工具：存文件的仓库、运行时环境、生成逻辑、候选用例处理器等）  
  - 输出：一个带 `message`/`items`/`count` 的标准响应字典（比如 `{"message": "generated 3 cases", "items": [...], "count": 3}`）  
  - 大白话解释：就像一家「智能测试用例打印店」的店长——顾客（前端）递来一张写着“我要测登录页+用户没填邮箱时的提示”之类的手写单子，店长会：① 检查单子有没有缺关键信息（比如没写页面名就拒收）；② 查查店里已有的类似用例（避免重复造轮子）；③ 翻翻登录页的“结构说明书”（page object），给新用例自动标上按钮/输入框的代码位置；④ 把杂乱信息（PRD、Git改动、OpenAPI）理出真正要测的核心需求；⑤ 一条条生成干净、带标题/优先级/标签的用例，并存进系统；⑥ 最后打包成前端能直接显示的漂亮卡片列表交还给顾客。

- **`_compact_state()`**：把“状态信息”压成最简小包裹  
  - 输入：任意值（通常是字典，比如 `{"asset_id": "A123", "version": 2, "updated_at": "2024-05..."}`）  
  - 输出：只保留非空且类型正确的字段（如 `{"asset_id": "A123", "version": 2}`）  
  - 大白话解释：像快递打包员——不管客户寄来一整箱杂物还是只有一张纸条，都只挑出“货单号（asset_id）”、“版本号（version）”、“最后更新时间（updated_at）”这三样有用的东西，塞进一个小信封，其他乱七八糟的全扔掉。

- **`_compact_quality_gate()`**：把“质量关卡”信息精简成关键指标  
  - 输入：任意值（通常是质量门禁配置，如 `{"decision": "pass", "stage": "uat", "blockers": ["网络超时"]}`）  
  - 输出：提取决策（pass/fail）、阶段（uat/staging）、阻塞项数量（如 `{"decision": "pass", "stage": "uat", "blocker_count": 1}`）  
  - 大白话解释：像安检口的电子屏——不显示全部报警细节，只亮出最关键的三个灯：“是否放行？”（decision）、“在哪个闸机？”（stage）、“有几个违禁品？”（blocker_count）。

- **`_to_public_item()`**：把内部生成的“原始用例数据”变成前端友好的“明信片”  
  - 输入：一个原始用例字典（可能嵌套很深、字段杂乱、含空值）  
  - 输出：扁平、干净、必填字段不为空的字典（如 `{"case_id": "TC-001", "title": "邮箱为空时显示错误提示", "priority": "P1", "state": {"asset_id": "A123"}}`）  
  - 大白话解释：像设计师把工程师画的草图（满是备注、坐标、临时变量）重绘成给产品经理看的高清效果图——只留标题、ID、优先级、关联资产等一眼能懂的信息，多余技术细节全隐藏。

- **`_build_generated_case_payload()`**：把当前任务“翻译”成底层生成器能听懂的指令  
  - 输入：大量参数（用户原始输入 + 清洗后的页面名 + 理清的需求 + 是否多源输入等）  
  - 输出：一个结构严谨的字典，直接喂给 `context.generation.build_generated_case_payload(...)` 这个底层生成函数  
  - 大白话解释：像翻译官——顾客用方言说“帮我弄个能测登录失败的用例”，翻译官把它转成标准普通话+专业术语：“请基于 page=‘login’、requirement=‘当邮箱为空时，弹出红色错误提示’、mode=‘generate’ 生成用例”。

- **`execute()`**：整个服务的“启动按钮”，所有逻辑从这里开始跑  
  - 输入：用户提交的完整请求体（`payload`，含页面、需求、API、候选用例等）和模式（`mode="generate"` 或 `"preview"`）  
  - 输出：最终的 JSON 响应（含 message、items 列表、总数）  
  - 大白话解释：像全自动咖啡机的“开始键”——你按下它（传入 payload），机器内部就自动：① 检查豆子够不够（校验 page）；② 看看水箱有没有水（检查 requirement）；③ 挑选最佳咖啡豆组合（选 candidate）；④ 根据杯子大小调整萃取（normalize_candidates）；⑤ 一杯杯做出来（循环生成）；⑥ 装进托盘（`_to_public_item`）；⑦ 显示“已出3杯”（返回 count 和 items）。

## 🧩 调用关系与数据流转  
```
execute() →（主流程入口）
├─ runtime.ensure_dirs()                    # 确保存放用例的文件夹存在（如创建 ./ai_cases/）
├─ runtime.normalize_page_slug()           # 把 "Login Page" → "login-page"
├─ generation.has_multisource_inputs()     # 判断是否用了多个输入源（PRD+API+Git Diff等）
├─ generation.resolve_effective_requirement() # 综合所有输入，提炼出最该测的一句话（核心需求）
├─ repository.collect_existing_case_ids()  # 扫描已有用例ID，避免重复生成
├─ preview_store.resolve_selected_candidates() # 根据 preview_id 或 fallback 候选列表，拿到待生成的用例草稿
├─ resolve_page_object()                   # 加载页面结构（按钮在哪、输入框ID是什么），用于后续标注元素
├─ enrich_candidate_with_element_codes()   # 给每个候选用例打上“页面元素标签”（如 title→#login-title）
├─ context.candidate_normalizer.normalize_candidates() # 把候选列表标准化（去重、截断、校验）
│
├─ 若无候选用例（batch_candidates为空）→ 直接调用 _build_generated_case_payload() 生成1个 → sync_generated_case_item() 存储 → _to_public_item() 包装 → 返回
│
└─ 若有候选用例（如3个）→ 循环处理每个 candidate：
     ├─ 构造 candidate_payload（合并用户全局设置 + 当前候选特有字段）
     ├─ _context.candidate_normalizer.build_candidate_requirement() # 为当前候选定制需求（如加“邮箱为空”限定）
     ├─ _build_generated_case_payload()      # 生成该候选对应的完整用例数据
     ├─ repository.sync_generated_case_item() # 写入磁盘（YAML文件）+ 更新状态 + 记录历史
     ├─ normalize_case_id()                  # 规范化用例ID（TC-001 → tc-001）
     ├─ 将新ID加入 existing_case_ids（防后续重复）
     └─ _to_public_item()                    # 转成前端可用格式，加入 items 列表
→ 最终汇总 items，返回 {message, item（第一个）, items（全部）, count}
```

## 💡 值得学习的写法
- **防御性数据清洗贯穿始终**：所有 `get(key, default)` 后都跟 `.strip()` 或 `str(...)`, `isinstance(..., dict)` 检查，像给每扇门都加了指纹锁——不怕前端传 `null`、`""`、`123` 或 `{}`，永远有安全兜底。
- **“候选用例”分层处理设计**：`resolve_selected_candidates()`（从预览/回退中取）→ `enrich_candidate_with_element_codes()`（贴页面元素码）→ `normalize_candidates()`（统一封装+限流），像流水线：进货→质检→贴标→装箱，职责清晰不耦合。
- **动态 payload 构造技巧**：用 `payload.model_copy(update=...)`（Pydantic v2）或 `payload.copy(update=...)`（v1）实现“以原始请求为模板，仅覆盖当前候选特有字段”，避免手动拼接字典，既安全又简洁。
- **状态/门禁的“压缩函数”抽象**：`_compact_state()` 和 `_compact_quality_gate()` 把重复的“取值→判空→赋值”逻辑封装成独立小函数，一处修改，全局生效，像给常用操作配了快捷键。

## ⚠️ 需要注意的地方
- **`payload` 属性访问风险**：代码中多次用 `payload.page`、`payload.requirement` 等，但未检查 `payload` 是否为 Pydantic 模型实例。如果传入的是普通字典，`payload.page` 会报 `AttributeError`。✅ 正确做法：统一用 `getattr(payload, "page", "")` 或先 `isinstance(payload, BaseModel)` 判定。
- **`selected_intent_ids` 解析易漏空字符串**：`str(item or "").strip()` 对 `None`/`""` 安全，但若 `item` 是数字 `0`，`str(0 or "")` → `"0"` → `strip()` 后还是 `"0"`，而 `0` 可能是无效 intent_id。⚠️ 建议增加 `if item not in (None, "", 0, "0")` 排除常见假值。
- **`batch_candidates` 截断逻辑藏坑**：`if len(batch_candidates) > 20: raise ...` 在循环生成前检查，但 `normalize_candidates()` 可能返回空列表或少于20个，而用户以为“最多20个”是硬上限。⚠️ 需确认 `normalize_candidates()` 是否会过滤掉无效项，否则实际生成数可能远少于预期。
- **`existing_case_ids` 动态追加的线程安全问题**：在 for 循环中 `existing_case_ids.append(case_id)`，若此服务被并发调用（如用户快速点两次生成），不同请求共享同一 `existing_case_ids` 列表会导致 ID 混淆。✅ 应在循环外深拷贝：`case_ids_snapshot = existing_case_ids.copy()`，循环内只读不写原列表。