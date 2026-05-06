# 📘 代码说明书
## 一句话概括
这是一个“需求预览生成器”，它把各种零散的需求输入（比如用户故事、PRD文档、API接口定义、代码变更等）统一喂给一个智能解析器，再从中提取关键信息（如测试意图、业务规则、模糊点、影响范围等），最后整理成前端页面能直接展示的结构化数据和 Markdown 文档。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `preview_pipeline.py` | 整个“需求预览”功能的流水线中枢：不自己解析需求，而是协调多个小工具（函数）各干各的活，把原始杂乱输入变成干净、可读、可展示的预览结果 |

## 🔍 核心函数/类说明
- **`def run_preview_pipeline()`**：整个预览功能的“总指挥”，负责串起所有步骤  
  - 输入：一大串需求相关材料（如 `effective_requirement` 是核心需求描述，`openapi_spec` 是接口定义，`git_diff` 是代码改动，还有 PRD、用户故事、缺陷单等等），以及 5 个“小帮手函数”（比如 `run_orchestrator_parse` 是主解析器，`render_requirement_spec_markdown` 是生成文档的，`extract_quality_gate` 是检查质量门槛的……）  
  - 输出：一个结构清晰的字典 `result`，里面包含页面要显示的所有内容——比如“这个需求有 3 类测试意图”“涉及 2 种数据源”“影响支付和订单模块”“质量检查通过/不通过”等  
  - 大白话解释：就像一家餐厅的“前台调度员”——客人（前端）递来一叠材料（需求文档、接口说明、代码改动…），调度员不亲自炒菜，而是把材料分发给后厨（解析器）、文案组（Markdown 生成器）、质检员（质量门禁）、统计员（计数汇总），最后把每道菜的名字、辣度、份数、备注都填进一张标准菜单（`result`），交给客人看。

## 🧩 调用关系与数据流转
```
外部调用者（如 FastAPI 接口） 
    ↓ 传入所有原始数据 + 5 个“工具函数”
run_preview_pipeline() 
    ↓ 记录输入日志（log_debug_event）
    ↓ 调用 run_orchestrator_parse(...) → 得到原始解析结果 parse_result
        ↓ 从 parse_result 中取出 requirement_spec（核心需求结构体）
        ↓ 用 render_requirement_spec_markdown(...) 把它转成易读的 Markdown（如果还没生成过）
        ↓ 用 extract_quality_gate(...) 检查是否满足上线基本要求（比如“必须有测试意图”）
        ↓ 用 list_value(...) 安全地提取列表字段（如 test_intents、ambiguities），不怕 None 或格式错
        ↓ 用 dict_value(...) 安全地提取字典字段（如 parser_runtime、change_impact）
        ↓ 手动计算各种统计值（intent_type_distribution、source_count、source_types 去重等）
    ↓ 把所有加工好的数据组装进 result 字典
    ↓ 记录输出日志（log_debug_event）
    ↓ 返回 result 给前端
```

## 💡 值得学习的写法
- ✅ **“函数即配置”设计**：把 `run_orchestrator_parse`、`render_requirement_spec_markdown` 等作为参数传入，而不是硬编码调用。就像餐厅不固定用哪位厨师，而是“谁来了就用谁”，方便未来换模型、换渲染器、换质检规则，完全不用改流水线代码。  
- ✅ **防御式取值封装**：`list_value` 和 `dict_value` 这两个函数专门处理“可能为 None / 不是列表 / 不是字典”的脏数据，避免 `.get("xxx", []).append(...)` 这种写法报错，让主逻辑干净又健壮。  
- ✅ **自动兜底与默认值**：比如 `page` 取不到就用空字符串，`priority` 没有就默认 `"P1"`，`source_count` 算不出来就退化为 `len(source_inputs)`，极大提升容错性。  
- ✅ **去重逻辑简洁清晰**：`deduped_source_types` 用普通 for 循环+手动查重，比用 `set()` 更可控（保留首次出现顺序），且对空值、非字符串做了 `str().strip()` 处理，很接地气。

## ⚠️ 需要注意的地方
- ⚠️ **`requirement_spec` 的来源太“黑盒”**：它完全依赖 `run_orchestrator_parse` 的输出，但这个函数没在本文件里定义。如果它返回的结构不一致（比如把 `test_intents` 放在 `requirement_spec["details"]["intents"]` 里），后面所有 `list_value(requirement_spec.get("test_intents"))` 都会拿空，而代码不会报错，只会默默返回空列表——这种“静默失败”最难调试。  
- ⚠️ **`source_count` 计算有两层 fallback，但逻辑略绕**：先从 `source_summary["source_count"]` 取，没有就从 `parser_runtime["source_count"]` 取，再没有才用 `len(source_inputs)`。但如果 `source_inputs` 本身是 `None` 或不是列表，`len()` 会直接报错——而 `list_value()` 并没用在这里，属于遗漏防护。  
- ⚠️ **`intent_type_distribution` 统计时忽略非字典项**：`for item in test_intents:` 里只处理 `isinstance(item, dict)`，但如果 `test_intents` 里混了字符串或数字（比如 `"login_flow"`），它们会被跳过且不报警，可能导致统计总数不准，却难以发现。  
- ⚠️ **日志事件名硬编码**：`"runtime.preview.input"` 和 `"runtime.preview.output"` 是固定字符串，如果后续想统一改成 `"preview.pipeline.input"`，得全局搜索替换，建议抽成常量。