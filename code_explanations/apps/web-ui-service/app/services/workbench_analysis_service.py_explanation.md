# 📘 代码说明书
## 一句话概括
这是一个「网页自动化测试智能分析服务」的核心逻辑文件，它能自动打开网页、识别页面元素、生成测试步骤、评估测试风险，并给出是否需要人工审核的明确建议——就像一个懂前端、会写测试脚本、还带风险评估能力的“测试工程师助手”。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `workbench_analysis_service.py` | 提供整套网页分析流水线：从 URL 解析 → 页面截图分析 → 元素识别 → 测试步骤生成 → Page Object 补全 → 风险打分 → 审核建议输出，是整个自动化测试“智能大脑”的主干。 |

## 🔍 核心函数/类说明
- **`extract_page_surface()`**：作用——像“网页侦探”一样，用浏览器真实访问目标页面（先登录再跳转），抓取当前页面所有按钮、输入框、标题、表格等结构信息，并判断页面是否加载稳定。  
  - 输入：页面 URL、登录配置、等待策略等  
  - 输出：一个包含页面结构、元素候选、加载状态、iframe 情况等的详细字典  
  - 大白话解释：它不是靠猜，而是真的打开浏览器、填账号密码、点登录、等页面静止，再把页面“长什么样”拍张高清快照（结构化数据版），连弹窗、搜索框、表格都标清楚。

- **`build_requirement_steps()`**：作用——把一句模糊的测试需求（比如“查商品编号为3的商品”）翻译成可执行的测试脚本步骤。  
  - 输入：需求文字、页面名、已分析好的页面结构（`surface`）、解析后的页面 URL  
  - 输出：一个按顺序排列的操作列表，如 `[{"action":"login"}, {"action":"goto","value":"#/product"}, {"action":"fill","target":"search_input","value":"3"}]`  
  - 大白话解释：就像你告诉助理“帮我找编号3的商品”，它立刻想清楚：得先登录 → 再进商品页 → 找到搜索框 → 输入3 → 点查询 → 等表格出现 → 验证表格可见。每一步都写得明明白白，连“等什么元素出现”都指定好了。

- **`enhance_page_object_from_surface()`**：作用——自动更新“页面对象模型”（Page Object），把刚才分析出的新元素（比如新发现的“导出按钮”）补进 YAML 文件，避免手动维护过时。  
  - 输入：页面名、刚分析出的页面结构（`surface`）、保存 Page Object 的路径  
  - 输出：更新后的 `.page-object.yaml` 文件路径  
  - 大白话解释：以前改页面就要人肉打开 YAML 文件加一行；现在它看到页面多了个“导出按钮”，就自动在对应页面的 YAML 里加上这一行定义，相当于给你的测试脚本“自动续费会员”，永远跟得上前端变化。

- **`evaluate_risk_report()`**：作用——综合所有信息（页面是否稳定？元素是否可信？测试步骤是否可靠？有没有报错？），打一个 0–100 的风险分，并决定：直接放行 ✅ / 需要人工看看 ⚠️ / 必须拦住 ❌。  
  - 输入：页面名、需求、各环节分析结果（surface/page object/test points）、最终执行状态（成功/失败/超时）  
  - 输出：一份带风险等级、扣分原因、建议动作、证据清单的完整报告  
  - 大白话解释：它像项目组里的 QA 经理，看完所有测试员交上来的材料（页面截图、脚本、日志），快速判断：“这个版本有点悬，3 个按钮识别不准 + 登录不稳定 + 2 个步骤建议跳过 → 风险分 78 → 必须让老张人工确认一下才能上线”。

- **`build_page_analysis_context()`**：作用——整个分析流程的“中央调度台”，把页面分析、Page Object、测试点计划等模块的结果统一整理、标准化、去重、补默认值，输出一个干净整齐的“分析大礼包”。  
  - 输入：页面名、URL、各模块原始数据（surface/object/test_points）  
  - 输出：一个结构清晰、字段统一、类型安全的字典，所有子模块结果都放在固定 key 下（如 `"page_surface_summary"`、`"test_point_summary"`）  
  - 大白话解释：各部门（前端、测试、运维）交来一堆格式乱七八糟的材料（JSON/YAML/日志片段），它负责统一盖章、编号、装订成册，确保后面所有人看的都是同一份标准版“项目简报”。

## 🧩 调用关系与数据流转
```
用户请求（如：分析商品页） 
    ↓
extract_page_surface() → 【真开浏览器】→ 得到 raw_surface（原始页面结构数据）
    ↓
build_requirement_steps() + surface_inferred_elements() → 基于 raw_surface 生成测试步骤 & 推荐元素
    ↓
enhance_page_object_from_surface() → 把推荐元素写进 page-object.yaml（持久化）
    ↓
build_page_analysis_context() → 整合 surface + page_object + test_points → 得到 analysis_bundle（标准化大礼包）
    ↓
evaluate_risk_report() → 读取 analysis_bundle + 执行状态 → 计算风险分 → 调用 build_risk_report() → 输出最终报告
        ↓
        build_risk_report() → 查看各模块问题（低置信元素数、缺失元素数、待审步骤数）→ 加权扣分 → 定级（high/medium/low）→ 给建议（block/manual_review/allow）
```

## 💡 值得学习的写法
- **“函数即插件”设计**：几乎所有核心函数（如 `validate_page_surface_url_fn`, `wait_for_surface_stable_fn`）都通过参数传入，而非硬编码调用。这意味着你可以轻松替换登录方式（换 SSO）、换等待策略（换 Playwright/Cypress）、换风险规则（换扣分逻辑），像搭乐高一样组合能力。
- **防御式数据清洗无处不在**：每个函数开头几乎都有 `_dict_value()` / `_list_value()` / `_clamp_confidence()` 这类小工具，把 `None`/`str`/`int` 等混乱输入，统一转成安全的 `dict`/`list`/`float`。就像给所有入口装了“安检门”，不怕上游传垃圾数据。
- **“语义化扣分”代替魔法数字**：`build_risk_report()` 里不是写 `score += 15`，而是 `append_factor(factor="missing_page_object_elements", factor_score=po_penalty, reason="缺3个元素")` —— 扣分理由自动生成，报告里直接显示“因缺3个元素扣18分”，可读性拉满。
- **“双保险”异常兜底**：`evaluate_risk_report()` 在调用外部风险评估服务失败时，会自动降级使用本地规则生成报告，并记录警告（`"risk-evaluation-agent unavailable: ..."`）。系统不会崩，只是“降级智能”，体验不中断。

## ⚠️ 需要注意的地方
- **Playwright 是硬依赖但未显式声明**：`extract_page_surface()` 里 `from playwright.sync_api import ...` 是运行时才导入，如果没装 `playwright` 包，函数会静默返回空字典 `{}`，而不是报错！新手可能以为“分析成功了”，实际什么都没做。✅ 建议：在文件顶部加 `try/except` 提前检查或文档注明。
- **环境变量敏感，容易漏配**：`TEST_USERNAME`/`TEST_PASSWORD`/`BASE_URL` 等全靠 `os.getenv()`，一旦忘记设置，登录流程直接跳过，后续所有分析基于“未登录态”页面（比如一直卡在登录页），但代码只打 warning 不报错。✅ 建议：对关键 env 做 `if not xxx: raise ValueError("请设置 TEST_USERNAME")`。
- **YAML 写入不加锁，多进程可能冲突**：`ensure_page_object()` 和 `enhance_page_object_from_surface()` 都会直接 `write_text()` 到同一个 `.page-object.yaml` 文件。如果多个测试同时分析同一页面，可能互相覆盖。✅ 建议：加文件锁（`threading.Lock` 或临时文件原子写入）。
- **正则提取搜索值太简单，易误判**：`extract_requirement_search_value()` 只找第一个数字或引号内内容，遇到“查订单号为 ABC-2024-001 的订单”会提取出 `2024` 而非 `ABC-2024-001`。✅ 建议：增加业务关键词上下文匹配（如“订单号为”后的内容）或允许配置提取规则。