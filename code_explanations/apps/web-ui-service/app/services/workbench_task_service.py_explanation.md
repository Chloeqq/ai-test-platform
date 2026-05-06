# 📘 代码说明书
## 一句话概括
这是一个「自动化测试任务仪表盘后台服务」，专门负责从磁盘（文件）和内存（运行时）中**收集、清洗、统一建模、评估风险与新鲜度**所有测试执行记录（比如 UI 自动化用例跑完后生成的报告），最终输出一个结构清晰、带治理建议的“任务健康总览”——就像给测试流水线装了一个智能体检中心。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `workbench_task_service.py` | 测试任务的“中央调度+健康诊断”核心服务：它不执行测试，但把所有散落的测试结果（文件/内存）捡起来、擦干净、打标签、量血压、写诊断书，并告诉工程师：“这个任务该人工看看了”“那个任务可以放心上线了”。 |

## 🔍 核心函数/类说明
- **`collect_execution_records_with_meta()`**：作用——**“全城扫楼式收件员”**，主动去磁盘上找所有测试记录（`execution_record.json`）和配套清单（`evidence_manifest.json`），还顺手拉取内存里还没写到磁盘的“活任务”。  
  - 输入：一堆路径（存测试文件的文件夹）、开关（是否启用兼容模式）、各种“翻译器函数”（把脏数据变干净）、日志对象。  
  - 输出：一个按时间倒序排好的任务列表 `trimmed` + 一份“体检报告摘要” `meta`（比如多少条来自清单、多少条靠兼容扫描、整体健康分是“healthy”还是“degraded”）。  
  - 大白话解释：就像物业管家，挨家挨户收快递（测试记录）：优先收贴了“已签收单”（manifest）的快件；没单子的，看业主（系统）是否还开着“老式代收服务”（compat_scan）才收；同时还会问楼上住户（runtime 内存）有没有刚打包好、还没下楼的快件。最后把所有快件按送达时间排序，剔除重复件，再统计：共收了127件，其中105件有签收单，12件靠代收，10件是楼上刚递下来的——这就是它的产出。

- **`build_execution_task_view()`**：作用——**“任务身份证制作员”**，把每一条原始记录（不管来自文件还是内存）变成一张标准、丰富、带判断的“任务档案卡”。  
  - 输入：一条原始任务数据（字典）+ 一堆“加工工具”（如时间解析、case_id 标准化、freshness 计算函数等）。  
  - 输出：一个结构统一、字段齐全、自带结论的字典，包含：任务ID、状态、来源（清单/兼容扫描/实时内存）、证据是否新鲜、是否健康、是否需要人工复核、变更影响有多大、该回归哪些模块……  
  - 大白话解释：就像医院给每个病人做标准化体检：抽血（读取 execution_record）、拍片（读取 manifest）、问诊（分析 metadata）、查既往史（traceability_summary），最后生成一张“体检报告单”，上面写着：血压正常、血糖偏高、建议复查肝功能、近期别喝酒——这里就是“证据陈旧（stale）、traceability 有缺口、top_factor 是 api_contract，建议人工复核”。

- **`build_task_evidence_freshness()`**：作用——**“证据保质期计算器”**，判断一个测试任务的证据（截图、日志、视频等）是不是“过期”了。  
  - 输入：任务来源（清单？内存？）、当前队列状态（排队中？运行中？）、几个时间戳（开始/结束/创建）、是否有清单、当前时间函数、ISO 时间解析函数。  
  - 输出：一个字典，明确告诉你证据是“fresh（新鲜）”“aging（快过期）”“stale（已过期）”，以及过期了多少秒、依据哪个时间点算的、为什么这么判。  
  - 大白话解释：就像超市理货员看牛奶保质期——如果这盒奶是“当天生产+贴了正规标签”（has_manifest），就按24小时算保质期；如果是“散装桶装奶，没贴标”（compat_scan），只给12小时；如果是“现挤现卖的鲜奶，还在牛身上”（runtime_realtime），那就不算保质期，直接标“live（热乎着呢）”。它算的就是这个“还能不能信”的时间窗口。

- **`build_task_governance_risk()`**：作用——**“治理风险打分员”**，综合证据健康度、新鲜度、清单动作三方面，给任务打一个0~9的“治理风险分”，并划分等级（critical/high/medium/low）。  
  - 输入：一条已构建好的任务视图（含 `evidence_health`、`evidence_freshness`、`manifest_action` 等字段）。  
  - 输出：一个字典，含 `level`（等级）、`score`（总分）、`reason`（扣分原因，如“证据陈旧+清单缺失+需回填”）。  
  - 大白话解释：就像银行风控系统——你信用分=还款记录（health）+ 近期消费活跃度（freshness）+ 是否绑定工资卡（manifest_action）。全A得0分（低风险）；有一项D就加3分；三项都D就9分（critical），立刻冻结额度。这里就是用类似逻辑给测试任务“授信”。

- **`build_execution_task_summary()`**：作用——**“团队健康年报撰写人”**，对一批任务（比如最近100条）做群体画像和关键问题聚类。  
  - 输入：一批已构建好的任务视图列表 + 当前筛选条件快照 + 风险评估函数。  
  - 输出：一个超大字典，含总数、各状态分布、各来源占比、风险等级分布、推荐回归包类型、最紧急的5个高风险任务详情、是否可关闭兼容扫描等决策建议。  
  - 大白话解释：就像公司HR出季度人力报告——“本季度共入职127人，其中83%来自校招（manifest），12%社招（compat_scan），5%内推（runtime）；高风险员工（governance_risk=critical）共3人，集中在API合同变更岗（api_contract），建议立即安排导师带教（manual_review）；全员平均试用期通过率92%，已达关闭‘实习转正缓冲期’（compat_scan）条件”。它输出的就是这份“测试任务健康年报”。

- **`_gate_recommendation_for_item()`**：作用——**“门禁策略执行官”**，根据风险等级、traceability 缺口、变更因子等，决定这个任务在上线前该走哪条通道：直接放行（allow）、人工复核（manual_review）、还是拦截（block）。  
  - 输入：治理等级、是否有 traceability 缺口、数据源数量、最严重变更因子。  
  - 输出：一个元组 `(action, reason)`，如 `("manual_review", "api_contract 变更影响较大，建议提升到人工复核")`。  
  - 大白话解释：就像机场安检闸机——VIP（critical）直通禁区（block）；普通旅客（high）走人工通道（manual_review）；行李有可疑物（traceability gap）也强制人工开箱；而“api_contract”“business_rule”这类高危物品标签，哪怕只是普通旅客也得额外检查。它就是这个智能闸机的决策大脑。

- **`_strict_mode_status_for_item()`**：作用——**“严格模式资格审查员”**，判断一个任务是否已准备好告别“兼容模式”（compat_scan），完全依赖清单（manifest-first）工作。  
  - 输入：任务来源、清单动作、是否有清单、是否实时补充、证据健康状态。  
  - 输出：`(status, reason)`，如 `("ready", "任务已稳定走 manifest-first 路径，可作为 strict-mode 候选")`。  
  - 大白话解释：就像驾校考科目二——必须全程用“标准路线”（has_manifest）、不依赖教练喊话（not runtime_realtime）、不临时改道（manifest_action=="ok"）、车辆自检全绿（evidence_health=="healthy"），才能拿到“独立驾驶资格证（ready）”。它就是那个考官。

## 🧩 调用关系与数据流转
```
[入口] FastAPI 接口（如 /tasks） 
       ↓ 调用
collect_execution_records_with_meta() 
       ├─→ 扫描 artifact_roots 目录 → 找 evidence_manifest.json → 解析 → 关联 execution_record.json → 加入 items
       ├─→ 扫描 artifact_roots 目录 → 找 execution_record.json（无 manifest）→ 若 compat_scan_enabled 则加入 items
       └─→ 合并 runtime_jobs（内存） + runtime_runs_file（临时文件）→ 构建 runtime_realtime 任务 → 加入 items
             ↓ （items 经过去重、截断、排序）
返回 trimmed（任务列表） + meta（统计摘要）

trimmed 中每个 item 
       ↓ 逐个传入
build_execution_task_view() 
       ├─→ 调用 build_task_evidence_freshness_fn(...) → 得 freshness 字段
       ├─→ 调用 _strict_mode_status_for_item(...) → 得 strict_mode 字段
       ├─→ 调用 _gate_recommendation_for_item(...) → 为后续 summary 准备 gate_recommendation
       └─→ 整合所有字段 → 返回标准化 task view

所有 task view 组成列表 items 
       ↓ 传入
build_execution_task_summary() 
       ├─→ 对每个 item 调用 build_task_governance_risk_fn(...) → 得 governance_risk
       ├─→ 对每个 item 调用 _gate_recommendation_for_item(...) → 得 gate_recommendation
       ├─→ 统计各类分布（status、source、risk level…）
       └─→ 计算全局指标（manifest_first_ratio、strict_mode_can_disable_compat_scan…）
             ↓ 返回最终聚合报告
```

## 💡 值得学习的写法
- **“函数即配置”思想贯穿始终**：所有 `Callable[[...], ...]` 参数（如 `normalize_execution_record_payload`, `parse_iso_datetime`）都不是硬编码逻辑，而是让调用方自由注入——就像给汽车预留了油箱盖、充电口、氢气口三种接口，换能源不用改车身。这让服务极度灵活，测试环境可注入 mock 时间函数，生产环境用真实 UTC。
- **防御性数据提取三件套 `_int_value` / `_dict_value` / `_list_value`**：面对可能为 `None`、字符串、数字、甚至乱码的输入，不抛异常，而是安全兜底返回 `0` / `{}` / `[]`。就像快递员收件，发现面单模糊，就默认写“未知地址”，而不是拒收。
- **多源时间兜底策略**：`execution_record_time_value()` 会依次尝试 `finished_at` → `started_at` → `created_at`，全空则用文件修改时间。像医生看病，问不出症状就查体温、听心跳、看面色，总有办法抓到一个时间锚点。
- **“Manifest First” 渐进式演进设计**：通过 `compat_scan_enabled` 开关 + `strict_mode_status` 三级状态（ready/caution/blocked）+ `strict_mode_can_disable_compat_scan` 全局判断，把“废弃旧路径”这件事做成可灰度、可监控、可回滚的工程实践，而非一刀切。
- **语义化枚举映射 `_scope_from_factor()`**：把开发写的 `"api_contract"` 字符串，自动映射成 `"api_contract_regression"` 这种带业务含义的 scope，避免前端或下游硬编码魔法字符串，是典型的“一次定义，处处受益”。

## ⚠️ 需要注意的地方
- **⚠️ `collect_execution_records_with_meta()` 的路径去重逻辑有陷阱**：它用 `consumed_record_paths: set[Path]` 去重，但 `Path.resolve()` 在符号链接场景下可能导致同一文件被多次收录（如 `/a/b.json` 和 `/c/d.json` 指向同一物理文件）。若项目大量用软链，需确认 `resolve()` 是否符合预期，否则会漏统计。
- **⚠️ `build_execution_task_view()` 中 `case_id` 标准化位置易错**：它在最后一步才调用 `normalize_case_id()`，但前面 `step_summary.get("page")` 等字段并未标准化。如果不同来源的 case_id 格式不一（如 `CASE-123` vs `case_123`），可能导致相同页面被统计为多个不同 page。建议关键标识字段尽早标准化。
- **⚠️ `build_task_governance_risk()` 的分数体系是“经验公式”**：`health_score` / `freshness_score` / `action_score` 的权重（0~4）是人为设定的，未见训练或AB测试验证。当业务重点变化（如更看重时效而非健康），需同步调整分数映射表，否则风险评级会失真。
- **⚠️ `build_execution_task_summary()` 的 top5 排序不稳定**：`governance_risk_top_items.sort(...)` 仅用 `governance_risk_score` 和 `task_id` 排序，若多个任务分数相同且 `task_id` 为空，排序结果可能因 Python 版本或运行环境不同而波动，影响前端展示一致性。建议增加唯一稳定字段（如 `finished_at`）作为第三排序键。
- **⚠️ `parse_optional_bool_query()` 对空字符串返回 `None`，但很多地方假设它返回 `bool`**：例如 `if not compat_scan_enabled:` 可能因传入空字符串而误判为 `False`。虽然代码里多数用 `if compat_scan_enabled is True:` 避开了，但新人容易踩坑，建议在函数文档或类型注解中强提醒“此函数返回 `bool | None`，请务必显式比较”。