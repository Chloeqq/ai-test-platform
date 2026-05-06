# 📘 代码说明书
## 一句话概括  
这是一个“全自动测试用例生成流水线”的核心引擎——它像一位经验丰富的测试工程师，接收一个模糊的需求（比如“用户登录要支持手机号和邮箱两种方式”），自动梳理出所有可能的测试场景（正常/异常/边界）、生成可执行的测试用例、绑定页面元素、甚至直接跑一遍测试并汇总结果。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `full_chain_service.py` | 实现“全链路测试生成”主流程：从解析需求 → 预览测试点 → 构建测试矩阵 → 卡点检查覆盖率 → 生成用例 → 执行测试 → 返回结构化报告 |

## 🔍 核心函数/类说明
- **`FullChainPipeline` 类**：整条流水线的“总装车间”，把各个步骤（准备、预览、建模、卡点、生成、执行）串起来，每个步骤只干一件事，像工厂里的不同工位。  
  - 输入：一个原始请求（比如前端传来的 JSON 表单）  
  - 输出：一份带 summary（摘要）、stages（各阶段明细）、generated（生成结果）的完整报告字典  
  - 大白话解释：你告诉它“我要测登录功能”，它就帮你：① 看懂你说啥（清理文字、判断是哪种输入）；② 先给你列个“可能要测的点清单”（比如“手机号空、邮箱格式错、密码太短…”）；③ 按你选的“测试强度”（普通/全面/边界）挑出重点场景；④ 检查“是不是漏了关键场景？”（比如你要求覆盖全部边界但只生成了2个，就拦住不往下走）；⑤ 真正生成可运行的测试脚本；⑥ 自动把脚本跑一遍，告诉你哪些通过、哪些失败、哪几个没绑上页面按钮；⑦ 最后交给你一份清晰的“体检报告”。

- **`FullChainService` 类**：流水线的“前台接待员”，只负责接单（`execute`）并把活儿转给 `FullChainPipeline` 去干，自己不碰具体逻辑。  
  - 输入：同上，原始请求数据  
  - 输出：同上，最终报告  
  - 大白话解释：就像餐厅的点餐员——你递菜单（payload），她不炒菜也不洗碗，只是把菜单交给后厨（pipeline），等菜（报告）好了再端给你。

- **`_normalize_chain_text()` 函数**：所有文字输入的“清洁工”，专门处理可能为空、为 None、带空格的字符串。  
  - 输入：任意类型值（比如 `None`、`"  登录  "`、`123`）  
  - 输出：干净的字符串（`""`、`"登录"`、`"123"`）  
  - 大白话解释：防止程序被“空格”“空值”绊倒，统一先擦干净再干活。

- **`FullChainPipelineState` 数据类**：整条流水线的“随身记事本”，记录每一步干了什么、产出啥、中间状态是啥。  
  - 输入：无（初始化时填入 payload）  
  - 输出：无（纯容器，供各 stage 读写）  
  - 大白话解释：就像快递员送件时背的电子记事本——第1站收件（`payload`），第2站贴单（`preview_payload`），第3站分拣（`candidates`），第4站查缺（`coverage_matrix`）……所有中间结果都记在这里，后面步骤随时翻看。

## 🧩 调用关系与数据流转  
```
用户请求（payload）  
    ↓  
FullChainService.execute()  
    ↓  
FullChainPipeline.run() → 创建 FullChainPipelineState（记事本）  
    ↓  
stage_prepare_request() → 清理文字、判断输入类型、算出“真正要测的需求”（effective_requirement）  
    ↓  
stage_preview_test_points() → 调用 generation_service.build_preview_response() → 得到“测试点清单”（preview_payload）  
    ↓  
stage_build_candidate_matrix() → 用 preview_payload + 用户选的“测试强度” → 调用 scenario_engine.build_candidate_matrix() → 得到候选场景列表（candidates）和覆盖率分析（coverage_matrix）  
    ↓  
stage_coverage_gate() → 检查 coverage_matrix → 若不达标（如漏场景/覆盖率低）→ 直接报错中断  
    ↓  
stage_generate_cases() → 把 candidates + 原始 payload 整合成新请求 → 调用 GenerateCaseService.execute() → 得到可执行用例（generated_items）  
    ↓  
stage_execute_cases() → 对每个 generated_item：  
　　　├─ 查数据库找用例（repository.find_test_case_by_case_id）  
　　　├─ 自动绑定页面元素（repository.bind_case_page_object_refs）  
　　　├─ 统计步骤行数（repository.count_case_step_rows）  
　　　└─ 若用户勾选“生成后立即运行”，则调用 runtime.start_run() + wait_run_terminal() → 得到执行结果（execution_items）  
    ↓  
stage_build_response() → 把记事本（state）里所有字段整理成最终 JSON 报告  
    ↓  
返回给用户
```

## 💡 值得学习的写法
- **“阶段式流水线”设计（Stage Pattern）**：把复杂流程拆成 `stage_xxx()` 独立方法，每个只做一件事、只读写 `state`，逻辑清晰、易测试、易增删步骤（比如未来加“发送邮件通知”只需新增 `stage_notify()`）。
- **防御性数据清洗无处不在**：所有字符串都过 `_normalize_chain_text()`，所有列表都用 `[x for x in ... if isinstance(x, dict)]` 过滤，避免 `None` 或类型错误导致崩溃。
- **“兜底默认值”思维**：当用户没填项目（如 `payload.title` 为空），自动补 `"全链路自动生成用例"`；当没生成候选场景，就用最基础的单条用例兜底，不让流程卡死。
- **覆盖率门禁（Coverage Gate）**：不是生成完就结束，而是主动检查“是否覆盖了所有要求场景”，像质检员在出厂前拦下不合格品，保证质量底线。
- **状态集中管理**：用 `dataclass` 定义 `FullChainPipelineState`，所有中间数据一目了然，避免散落全局变量或层层传参。

## ⚠️ 需要注意的地方
- **`payload` 类型模糊风险**：代码里大量使用 `Any` 和 `isinstance(..., dict)` 判断，但没强制校验 payload 结构。如果前端传错字段名（如把 `requirement` 写成 `req`），可能静默变成空字符串，导致后续步骤失效。✅ 建议：加 Pydantic 模型校验入口。
- **硬编码默认值过多**：`project="mall"`、`source="manual"`、`priority="P1"` 等频繁出现，若业务扩展需支持多项目，默认值可能误用。✅ 建议：提取为配置常量或上下文参数。
- **异常处理不够精细**：`stage_execute_cases()` 中 `except Exception as exc` 捕获所有异常，掩盖了具体错误类型（如文件权限、网络超时、JSON 解析失败），不利于排查。✅ 建议：按具体异常类型分层捕获（如 `FileNotFoundError`、`TimeoutError`）。
- **`run_status_counts` 统计逻辑有隐患**：遍历 `execution_items` 时用 `item.get("status")`，但如果某个 `item` 是 `None` 或非字典，`get` 返回 `None` → `_normalize_chain_text(None)` 变成 `""` → key 变成 `"unknown"`，可能掩盖真实失败原因。✅ 建议：加 `if isinstance(item, dict)` 保护。
- **`stage_build_candidate_matrix` 的兜底逻辑易误解**：当 `candidates` 为空时，会强行生成一条默认用例，但此时 `coverage_matrix` 的 `status` 和 `coverage_ratio` 是基于这条默认用例计算的，可能给出“100%覆盖”的假象。✅ 建议：兜底时明确标记 `status: "fallback"` 并降低 `coverage_ratio`。