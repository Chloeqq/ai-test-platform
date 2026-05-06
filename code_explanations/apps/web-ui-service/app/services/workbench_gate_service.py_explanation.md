# 📘 代码说明书
## 一句话概括
这是一个「自动化测试门禁系统」的核心服务模块，负责根据页面分析、测试结果、风险评估等数据，**自动判断某次测试是否能放行（allow）、必须拦截（block）还是需要人工复核（manual_review）**，并支持权限控制、二次审批、撤销等完整决策生命周期管理。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `workbench_gate_service.py` | 提供测试执行前的“智能门禁”判断逻辑与决策管理能力，像一个严谨又灵活的「测试安检站」：自动扫描风险、按规则打标、支持人工盖章放行/拦停，并记录谁在什么时候做了什么决定。 |

## 🔍 核心函数/类说明
- **`build_execution_gate()`**：作用——根据一整套页面和测试分析数据（比如缺失元素、低置信度、风险报告等），**自动生成本次测试的门禁决策（allow/block/manual_review）及详细依据**。  
  - 输入：页面名、最终执行状态、覆盖率、页面结构/语义/对象分析、测试点汇总、人工复核状态、风险报告等十多项结构化数据。  
  - 输出：一个包含 `decision`（最终决策）、`blockers`（阻断原因）、`warnings`（待审提示）、`evidence`（证据链）、`metrics`（指标快照）等字段的字典。  
  - 大白话解释：就像一位经验丰富的测试组长，快速翻看「页面截图+元素报告+测试日志+风险预警」后，在纸上写下：“❌ 拦停！因为缺3个关键按钮；⚠️ 建议复核：有2个低置信元素；✅ 证据见第5、7、12行日志”。这个函数就是那位组长的大脑。

- **`upsert_execution_gate_decision()`**：作用——**保存或更新一条门禁决策记录（比如某人点了‘放行’或‘拦截’）**，是门禁操作的“落库入口”。  
  - 输入：决策载荷（payload，含 project/run_id/page/decision 等）、操作人信息（actor）。  
  - 输出：写入后的完整决策记录（字典）。  
  - 大白话解释：就像在安检站的登记本上写一笔：“2024-05-20 14:30，mall 项目，run_id=abc123，页面=addproduct，李四（角色：QA）决定：ALLOW”。它还会自动处理“二次审批”逻辑（比如 block 需要两个领导签字）。

- **`execution_gate_decision_for_run()`**：作用——**根据 run_id（测试流水号）查出最新一条匹配的门禁决策**，是前端或下游服务“查结果”的主要接口。  
  - 输入：run_id（必填），可选 project 和 page 进行精确过滤。  
  - 输出：找到的决策字典，没找到则返回空字典 `{}`。  
  - 大白话解释：相当于在登记本里翻找：“请找出 run_id=abc123 的最新一条安检结论”，只看最新那条，旧的覆盖掉。

- **`approve_execution_gate_decision()`**：作用——**执行“二次审批”动作**（比如第一个审批人点了 block，第二个领导来确认是否真拦）。  
  - 输入：project/run_id/page/审批人信息/备注。  
  - 输出：审批完成后的更新后记录。  
  - 大白话解释：就像第二位领导在登记本同一行末尾签上名字和时间：“已复核，同意拦截 —— 王五（总监），2024-05-20 15:02”。

- **`revoke_execution_gate_decision()`**：作用——**撤销一条已做的门禁决策**（比如发现点错了，或流程变更）。  
  - 输入：project/run_id/page/撤销人信息/备注。  
  - 输出：撤销后的记录（status 变为 revoked）。  
  - 大白话解释：在登记本那行字上画个大叉，并写：“已撤销 —— 张三（原决策人），2024-05-20 16:10”，或者由管理员代为划叉。

- **`require_execution_gate_decision_permission()`**：作用——**校验当前操作人是否有权执行某项决策（如 block/allow）**，是权限守门员。  
  - 输入：操作人信息（actor）、想做的决策（decision）。  
  - 输出：无（校验通过就安静放行；不通过直接抛 HTTP 403 错误）。  
  - 大白话解释：就像安检站门口的保安，看到有人想按“红色紧急拦截按钮”，先扫一眼工牌：“您是 QA？抱歉，只有 Admin 或 Security 角色才能按这个按钮”。

- **`execution_gate_policy_baseline()`**：作用——**生成一份可读的门禁策略说明书（JSON 格式）**，告诉所有人：“我们怎么自动判断？哪些情况拦？哪些要人看？谁有权限？”  
  - 输入：无。  
  - 输出：包含 `system_decision_rules`（自动规则）、`manual_override_boundary`（人工权限边界）、`non_goals`（明确不做的事）的策略字典。  
  - 大白话解释：相当于把公司《测试门禁SOP手册》自动生成成网页版，让每个新来的测试工程师、产品经理都能立刻看懂：“哦，原来缺2个按钮就拦，有1个待确认分组就要人工看”。

## 🧩 调用关系与数据流转
```
用户发起请求（如：点击“放行”按钮）
        ↓
FastAPI 路由 → 调用 upsert_execution_gate_decision(payload, actor=xxx)
        ↓
upsert_execution_gate_decision() 内部：
   ├─→ _normalize_page_slug() 标准化页面名（addprouct → addproduct）
   ├─→ _safe_case_id() 生成或清洗 case_id（空时自动造一个带时间戳的）
   ├─→ normalize_execution_gate_decision() 校验 decision 是否合法（allow/block/manual_review）
   ├─→ is_execution_gate_privileged_role() + can_bypass_dual_approval() 查权限（决定要不要走二次审批）
   └─→ state_store.write_json_list() 将决策写入本地 JSON 文件（带文件锁防并发）

另一条线：查询决策
用户请求“查 run_id=abc123 的门禁结果”
        ↓
FastAPI 路由 → 调用 execution_gate_decision_for_run(run_id="abc123")
        ↓
execution_gate_decision_for_run() 内部：
   ├─→ state_store.read_json_list() 读取所有历史决策
   ├─→ _normalize_page_slug() 标准化页面名做比对
   └─→ 遍历找到匹配 run_id 的最新一条，返回结构化结果

再一条线：生成策略文档
前端请求 /api/gate/policy
        ↓
FastAPI 路由 → 调用 execution_gate_policy_baseline()
        ↓
内部读取 get_settings() 获取配置（如阈值、角色列表），组装成易读的策略 JSON

最后：构建原始门禁报告（非决策，是分析）
AI 分析引擎 → 调用 build_execution_gate(...) 传入所有分析数据
        ↓
build_execution_gate() 内部：
   ├─→ 逐条比对配置阈值（如 missing_required_count ≥ 2? → 加入 blockers）
   ├─→ _dedup_keep_order() 去重并保序（避免重复提醒“缺按钮”两次）
   └─→ 返回带 evidence/metrics 的完整分析报告（供人工决策参考）
```

## 💡 值得学习的写法
- **`_dedup_keep_order()`**：用 `set` 记录已见项 + `list` 保序，一行代码解决“去重且不打乱顺序”问题，比 `list(set(...))` 更可靠（后者无序），比 `dict.fromkeys(...)` 更直白，是 Python 中处理“有序去重”的优雅范本。
- **`execution_gate_decision_identity()` + `PAGE_ALIAS_MAP`**：用元组 `(project, run_id, page)` 作为决策唯一标识，且 `page` 先标准化（`addprouct`→`addproduct`），让不同拼写/格式的页面名指向同一决策，避免“同页不同策”的混乱，体现了“逻辑 ID ≠ 原始输入”的设计智慧。
- **`_payload_value()`**：统一处理 `dict` 和 `object` 两种 payload 类型（`.get()` vs `.getattr()`），让函数既能接 FastAPI 的 Pydantic 模型，也能接普通字典，极大提升兼容性，是“防御性编程”的好例子。
- **`build_execution_gate_audit_snapshot()`**：把原始 `execution_gate` 报告“翻译”成审计友好的精简版（只留关键字段、限制列表长度、拼接摘要），避免前端直接暴露冗余细节，兼顾性能与可读性。
- **策略配置兜底逻辑**：所有 `getattr(settings, "xxx", default)` 后都跟 `or ["admin"]` 或 `or False`，确保即使配置为空也不崩，系统总有安全默认行为（如没配特权角色，默认只有 admin 能操作），是生产级代码的稳健体现。

## ⚠️ 需要注意的地方
- **`state_store` 是纯文件读写（JSON List）**：⚠️ 这不是数据库！高并发时靠 `FILE_LOCK` 硬扛，但若部署多实例（多个 FastAPI 进程），**锁失效，会出现数据覆盖**。上线前必须改用 Redis 或数据库，否则“两人同时审批”会丢数据。
- **`upsert_execution_gate_decision()` 的“更新”逻辑有陷阱**：它只按 `(project, run_id, page)` 匹配，但 `case_id` 是动态生成的（`_safe_case_id()`），如果用户传了空 `case_id`，每次都会生成新 ID，导致“同一 run_id 的多次决策无法合并”，变成多条记录。应强制 `case_id` 由上游保证一致，或在 identity 中去掉 `case_id`。
- **`normalize_page_slug()` 的字符过滤太激进**：只留字母数字和 `-/_`，会把中文页面名（如 `"商品详情页"`）全干掉变成空字符串，最终 fallback 到 `"product"`，造成严重误匹配。需补充对 Unicode 字母的支持（如 `ch.isalnum() or ch in {"-", "_"} or (ord(ch) >= 0x4E00 and ord(ch) <= 0x9FFF)`）。
- **`require_execution_gate_decision_permission()` 的错误提示不够友好**：当权限不足时，返回的是 `HTTPException(detail={...})`，但前端可能只取 `detail.message`，而 `allowed_roles` 在嵌套对象里，容易被忽略。建议把 `allowed_roles` 直接塞进 `message` 字符串里，或统一用 `detail: str` 格式。
- **`build_execution_gate()` 中的 `asset_context` 处理嵌套过深**：连续 `asset_context.get("review_summary", {}).get("pending_review_count", 0)` 这种写法，一旦中间某个 key 是 `None` 或非 dict，就会 `AttributeError`。应全部用 `if isinstance(..., dict)` 保护，或引入 `dict.get(key, default)` 的递归版本（如 `deep_get(asset_context, "review_summary.pending_review_count", 0)`）。