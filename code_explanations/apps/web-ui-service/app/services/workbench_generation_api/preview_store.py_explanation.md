# 📘 代码说明书
## 一句话概括
这是一个为“测试点预览功能”服务的后台工具文件，负责把用户在网页上临时生成的测试用例草稿（比如点击某个按钮后自动生成的测试点）安全地存起来、读出来，并整理成前端友好的格式展示给用户看。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `workbench_generation_api/preview_store.py` | 管理“测试点预览快照”的整个生命周期：保存、加载、清洗、转换、筛选和组装成不同用途的响应（如列表页、详情页、诊断页） |

## 🔍 核心函数/类说明
- **`save_preview_snapshot()`**：把用户刚生成的一组测试点“拍个快照”，存成一个带唯一编号的 JSON 文件  
  - 输入：项目名、页面名、来源（手动/自动）、需求描述、原始数据（`preview_payload`）、追踪ID  
  - 输出：包含 `preview_id` 等元信息的完整快照字典  
  - 大白话解释：就像你写完一篇草稿后按 Ctrl+S → 它会自动起个名字（比如 `preview-ab3f1e8c2d4b5678.json`），存在固定文件夹里，方便以后随时打开看  

- **`load_preview_snapshot(preview_id)`**：根据 ID 找到并读取那个快照文件  
  - 输入：`preview_id`（例如 `"preview-ab3f1e8c2d4b5678"`）  
  - 输出：解析后的 Python 字典（即快照内容）  
  - 大白话解释：就像你双击一个文档文件 → 它帮你打开并读出里面写了啥；如果文件丢了或打不开，就礼貌地告诉你“找不到”或“文件损坏了”  

- **`build_public_preview_response(snapshot)`**：把原始快照“翻译”成前端能直接渲染的简洁版数据（用于列表页）  
  - 输入：从 `load_preview_snapshot` 拿到的原始快照字典  
  - 输出：一个结构清晰、字段精简、带统计信息（如测试点类型分布）、含跳转链接的字典  
  - 大白话解释：就像把一本厚厚的工程笔记，提炼成一页 PPT：只留标题、优先级、大概步骤、预期结果、点击就能看详情的链接——让产品经理/测试同学一眼看懂  

- **`build_preview_diagnostics(preview_id)`**：生成“技术诊断报告”，给开发/算法同学看内部细节（比如为什么这个需求没被正确解析）  
  - 输入：`preview_id`  
  - 输出：含解析置信度、质量门禁（quality gate）、歧义点、依赖图、运行时日志等深度信息的字典  
  - 大白话解释：就像汽车的“故障码读取器”——不光告诉你“车开不动了”，还告诉你可能是火花塞老化、油路堵塞、还是 ECU 软件 bug  

- **`get_preview_intents(preview_id, selected_intent_ids)`**：从快照里精准捞出指定的测试点（支持全拿 or 只拿某几个）  
  - 输入：快照 ID + 可选的意图 ID 列表（如 `["intent-01", "intent-03"]`）  
  - 输出：匹配的测试点列表（每个是字典）  
  - 大白话解释：就像在微信聊天记录里搜关键词 → 支持“查全部”或“只查我标记为‘重点’的那几条”  

- **`resolve_selected_candidates()`**：智能 fallback 机制——当用户指定的测试点 ID 在快照里找不到时，自动退回到备用方案（比如用默认顺序或 fallback 列表）  
  - 输入：快照 ID、想选的 ID 列表、兜底的测试点列表  
  - 输出：最终确定的测试点列表（优先按用户意愿，不行就用备选）  
  - 大白话解释：就像你点外卖选了“不要香菜”，但商家没货 → 它不会报错，而是默默给你换成“少放葱”，保证你能吃上饭  

- **`build_preview_intent_detail(preview_id, intent_id)`**：返回单个测试点的完整详情（用于点击某个测试点后弹出的详情弹窗）  
  - 输入：快照 ID 和意图 ID  
  - 输出：含该测试点全部原始字段的嵌套字典  
  - 大白话解释：就像点开微信里的某条消息 → 展开看到完整文字、时间、发送人、甚至撤回提示  

## 🧩 调用关系与数据流转
```
save_preview_snapshot() 
  └── 生成 preview_id → 写入文件（路径由 _preview_path() 计算）

load_preview_snapshot(preview_id) 
  └── 调用 _preview_path(preview_id) → 读文件 → 解析 JSON

build_public_preview_response(snapshot)
  └── 调用 _requirement_spec(snapshot) → 提取 requirement_spec
        └── 调用 _quality_gate(...) → 合并 quality_gate
      └── 遍历 test_intents → 对每个调用 _public_intent(...)
            └── 调用 _steps_summary(...) → 按优先级取 steps/steps_hint/summary
      └── 统计 intent_type 分布

build_preview_diagnostics(preview_id)
  └── load_preview_snapshot() → _requirement_spec() → _sanitize_requirement_spec_for_diagnostics()
        └── _sanitize_parser_runtime() → 剔除敏感/冗余字段（llm_trace 等）

get_preview_intents(preview_id, selected_ids)
  └── load_preview_snapshot() → _requirement_spec() → 提取 test_intents 并过滤

resolve_selected_candidates()
  └── 先调用 get_preview_intents() 尝试精准匹配
        └── 匹配失败？→ 回退到 fallback_candidates 列表

build_preview_intent_detail(preview_id, intent_id)
  └── 调用 get_preview_intents(preview_id, [intent_id]) → 找到后包装返回
```

## 💡 值得学习的写法
- **统一的数据清洗函数（`_text`, `_list`, `_dict`）**：所有字段访问前都先过一遍“安全转换”，避免 `None.get("xxx")` 报错，也省去满屏 `or ""` 或 `if x else []`，像给所有输入戴了“防摔保护套”  
- **正则预编译 `_PREVIEW_ID_RE`**：提前编译好 ID 校验正则，每次调用都飞快，而不是每次现场 `re.compile()` 浪费 CPU  
- **`deepcopy` + `pop` 的组合拳（`_sanitize_parser_runtime`）**：既保留原始数据结构，又干净剔除不想暴露的字段（如 LLM 追踪日志），比手动删 key 更安全、更易维护  
- **fallback 逻辑藏在 `resolve_selected_candidates` 里**：不是简单报错，而是有策略地降级（先按 ID 找 → 找不到就用 fallback 列表 → 还不行就按默认顺序），用户体验丝滑  
- **路径计算与文件操作分离（`_preview_path()`）**：把“ID 怎么变路径”抽成独立函数，以后要改存储规则（比如加日期子目录）只需动这一处  

## ⚠️ 需要注意的地方
- **`_preview_path()` 会抛 404 异常，但 `save_preview_snapshot()` 却不校验 preview_id 格式**：虽然保存时 ID 是自己生成的（肯定合法），但如果未来有人手动生成 ID 调用此函数，可能绕过校验 → 建议在 `save_preview_snapshot()` 开头也加一次 `_PREVIEW_ID_RE.match()` 校验  
- **`_steps_summary()` 截断逻辑有隐藏风险**：`[:160]` 是对拼接后的字符串截断，但如果前两个 step 各 100 字，拼起来就超长 → 实际显示可能被粗暴砍断在中间词，建议改成“逐个加，超长就停”  
- **`_public_intent()` 默认 `intent_id` 是 `"intent-01"` 这种硬编码**：如果多个快照都用相同 index，会导致 ID 冲突（虽然后端不校验唯一性，但前端路由可能出问题）→ 更稳妥是用 `uuid.uuid4().hex[:6]` 生成短随机 ID  
- **`build_preview_diagnostics()` 返回的 `parser_runtime` 没做深度清洗**：只清了顶层字段，但若 `parser_runtime` 里还有嵌套的 `llm_trace`，就会漏掉 → 应递归清理或明确文档说明“仅浅层清洗”  
- **文件锁 `workbench_state_store.FILE_LOCK` 是全局单例**：如果未来并发量大，所有 preview 操作都会排队等锁 → 可考虑按 `preview_id` 哈希分桶，实现细粒度锁（如 `lock_map[hash(preview_id) % 16]`）