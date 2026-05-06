# 📘 代码说明书
## 一句话概括
这是一个「工作台历史记录加工器」——它把原始的、零散的操作日志（比如谁在什么时候点了什么、跑了个什么任务）变成用户能在网页上清晰浏览、筛选、排序、分页查看的「智能历史列表」，还顺手统计出关键指标（比如多少次被门禁拦下、多少次需要人工复核）。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `workbench_history_service.py` | 负责对「工作台操作历史数据」进行清洗、补全、过滤、排序、分页和统计汇总，最终生成前端可直接渲染的结构化响应 |

## 🔍 核心函数/类说明
- **`_enrich_history_row()`**：给一条原始日志“贴标签、加备注”，让它变得更丰富、更有信息量  
  - 输入：一条原始日志字典（如 `{"run_id": "abc123", "action": "run_test"}`），外加两个“查详情”的小工具（`resolve_governance_snapshot` 和 `resolve_failure_snapshot`）  
  - 输出：加工后的日志字典（可能新增了 `risk_summary`、`failure_analysis`、`detail_summary` 等字段）  
  - 大白话解释：就像你收到一条快递通知“包裹已发出”，它会自动去查物流系统（治理快照）和客服工单系统（失败快照），然后给你补上：“⚠️ 风险等级高｜门禁未通过｜失败原因是网络超时｜需人工复核”，最后还自动生成一句人话摘要：“失败来源=网络超时；人工复核=是”——所有这些都塞进同一条记录里，不用前端再反复请求。

- **`_matches_history_filters()`**：判断某条加工后的日志是否符合用户当前设置的筛选条件（比如只看“失败”状态、或包含“登录页”的记录）  
  - 输入：一条加工好的日志 + 所有筛选条件（动作、状态、关键词等）+ 一个“页面名标准化”小工具（比如把 `LoginPage` 和 `login-page` 都转成 `loginpage` 方便搜索）  
  - 输出：`True`（留下）或 `False`（过滤掉）  
  - 大白话解释：像超市自助结账机的扫码枪——扫到商品就比对“是不是我想要的”：是不是指定动作？是不是指定状态？名字里有没有关键词？连“页面名”都会先统一格式再搜，避免 `Login` 和 `login` 被当成两个东西。

- **`_sort_history_rows()`**：按用户选择的方式（时间新→旧、动作字母序、门禁结果等）给日志排好队  
  - 输入：一堆加工并筛选后的日志列表 + 排序指令（如 `"gate_asc"`）  
  - 输出：重新排列后的日志列表  
  - 大白话解释：就像整理一叠乱放的明信片——你可以选择按“寄出时间”排（最新在最前）、按“城市名”排（北京、成都、广州…）、甚至按“盖的邮戳类型”排，而且每种排序都默认“时间”作为第二排序依据（同城市的按时间排），避免顺序随机。

- **`_paginate_rows()`**：把排好队的日志切成一页一页（比如每页50条），并告诉前端“总共多少页、当前第几页、一共多少条”  
  - 输入：完整日志列表 + 当前页码 + 每页条数  
  - 输出：含 `items`（本页数据）、`page`、`total_pages` 等字段的分页对象  
  - 大白话解释：就像看书——整本书太厚，我们只翻“第3页”，它就精准切出第101~150条，并告诉你：“这本书共20页，你正在看第3页”。

- **`_build_history_summary()`**：快速扫一遍所有日志，统计出老板最爱看的几个数字（比如“门禁拒绝了多少次？”“自愈失败多少次？”“哪个操作最常发生？”）  
  - 输入：加工+筛选+排序后的日志列表  
  - 输出：一个含各类计数和“TOP1”信息的统计字典  
  - 大白话解释：就像班级老师点完名后立刻报数：“全班45人，迟到3人，举手回答问题最多的是小明（12次），穿红衣服的有8人，戴眼镜的有15人…”——全是高频问题的一键答案。

- **`list_history()`**：整个流程的“总指挥”，串联所有步骤，输出最终结果  
  - 输入：原始日志列表 + 各种参数（筛选词、排序方式、分页设置等）+ 两个“查详情”的工具函数  
  - 输出：一个结构清晰的字典，含 `items`（本页数据）、`summary`（统计摘要）、`pagination`（分页信息）、`meta`（本次查询参数）  
  - 大白话解释：就像餐厅后厨的主厨——客人点单（传入参数），他指挥洗菜（`_enrich`）、切配（`_matches`）、摆盘（`_sort`）、装盒（`_paginate`）、写小票（`_build_summary`），最后端出一盘色香味俱全的菜（标准响应），连打包盒（`meta`）都印着订单号。

- **`build_workbench_history_payload()`**：`list_history()` 的“马甲”，功能完全一样，只是名字更直白，方便其他模块调用  
  - 输入/输出：和 `list_history` 完全一致  
  - 大白话解释：就像一个人有两个微信名——“张三”是正式名（`list_history`），“工作台历史组装工”是花名（`build_workbench_history_payload`），同事喊哪个都行，干的活儿没区别。

- **`summarize_quality_gate_events()`**：不自己干活，而是把活儿“转包”给另一个文件（`workbench_quality_gate_summary_service.py`）  
  - 输入：原始日志 + 参数  
  - 输出：对方返回的统计结果  
  - 大白话解释：就像你让助理帮你订会议室，助理其实只是打了个电话给行政部——它自己不查空闲时间，只负责把你的需求（“今天下午3点，要能投屏的”）原样转达，并把行政部的回复（“301会议室已订好”）交给你。

## 🧩 调用关系与数据流转
```
用户请求 → build_workbench_history_payload() 
        ↓ （本质是调 list_history）
list_history()
├─ 循环处理每条原始日志 → _enrich_history_row() 
│                         ↓ 返回加工后的单条日志
│                         ↓ 传给过滤器
├─ 对每条加工日志 → _matches_history_filters() 
│                  ↓ 返回 True/False 决定是否保留
├─ 收集所有通过的行 → rows 列表
├─ rows → _sort_history_rows() → sorted_rows
├─ sorted_rows → _build_history_summary() → summary
├─ sorted_rows → _paginate_rows() → pagination（含 items）
↓
最终返回：{
  "items": pagination["items"],     // 本页数据
  "summary": summary,               // 统计结果
  "pagination": { ... },            // 分页元信息
  "meta": { ... }                   // 查询参数快照
}
```

## 💡 值得学习的写法
- **空值防御全自动**：所有 `.get("xxx", {})` 后紧跟 `if isinstance(..., dict)` 判断，再 `.get("yyy", "")` ——像给每一扇门都配了两把锁，确保不会因某个字段突然变 `None` 或字符串而崩掉，健壮性拉满。  
- **默认函数兜底**：`resolve_governance_snapshot or (lambda _run_id: {})` 这种写法，让参数可选且安全——没传“查详情”函数？那就默认返回空字典，后续逻辑照常运行，绝不报错。  
- **`_pick_top_bucket()` 抽离通用逻辑**：统计 TOP1 的代码（按数量降序、数量相同时按字母升序）只写一次，被三个地方复用（动作、门禁、自愈），避免重复劳动和不一致。  
- **`detail_summary` 的三级 fallback 机制**：当失败分析没内容 → 自动 fallback 到风险摘要；没风险 → fallback 到语义摘要；还没？fallback 到自愈摘要。像汽车的三级安全气囊，层层兜底保证总有摘要可展示。  
- **关键词搜索的“全字段拼接”策略**：把时间、动作、页面、备注等十几处文本全揉成一个大字符串再搜，用户输“login error”就能命中 `page="LoginPage"` + `note="登录报错"`，体验丝滑。

## ⚠️ 需要注意的地方
- **`limit` 是“加工前截断”，不是“分页后限制”**：`for item in history_items:` 循环里 `if len(rows) >= normalized_limit: break` ——这意味着如果原始数据有1万条，但你设 `limit=100`，它只加工前100条匹配的（可能漏掉后面更符合条件的）。想严格取“全局前100”，得先不限制加工，再对 `sorted_rows` 取 `[:100]`。  
- **`normalize_page_slug` 默认行为有隐含转换**：`lambda value: str(value).strip().lower()` 会把所有页面名转小写，但若业务中 `AdminPage` 和 `adminpage` 是不同概念，这里就悄悄合并了，需确认是否符合预期。  
- **`_matches_history_filters()` 中 `actor_filter` 是“包含”而非“等于”**：`actor_filter not in actor_value` 表示只要显示名里有关键词就留下（如搜“张”能匹配“张三”“李小张”），但若想精确匹配“张三”，这里逻辑就不够用了。  
- **`_build_history_summary()` 中 `boundary_rejected_count` 的判定有歧义**：既判 `self_healing_status == "rejected"`，又判 `boundary.get("allowed") is False`，但这两个条件可能同时成立，导致同一条日志被重复计数（目前代码是 `+=1`，所以没问题），不过逻辑上建议明确是“或”关系还是“且”关系，加注释说明。  
- **`sort` 参数容错强但易误导**：`str(sort or "timestamp_desc").strip().lower() or "timestamp_desc"` 会让 `sort=None`、`sort=""`、`sort="   "` 全变成 `"timestamp_desc"`，很友好；但若用户误传 `sort="TIMESTAMP_DESC"`（大写），也会被转成小写，而函数内部只认 `"timestamp_desc"`，没问题——但若未来新增 `sort="RunId_ASC"`，大小写敏感就可能出 bug，建议统一用枚举或校验。