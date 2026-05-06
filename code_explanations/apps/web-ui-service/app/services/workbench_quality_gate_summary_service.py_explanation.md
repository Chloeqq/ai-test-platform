# 📘 代码说明书
## 一句话概括
这是一个「质量门禁（Quality Gate）数据统计小管家」，它把一堆杂乱的质量检查记录（比如“这个需求描述太模糊，不给过！”）整理成清晰的报表：告诉你最近堵了多少次、为啥堵、哪类问题最多、哪个页面最常出问题、趋势如何变化，还附带修复建议。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `workbench_quality_gate_summary_service.py` | 负责分析和汇总「质量门禁历史事件」，生成面向测试/产品同学的可读性报表（如阻塞率、TOP问题、24小时趋势、修复指南等） |

## 🔍 核心函数/类说明
- **`summarize_quality_gate_events()`**：整个文件的“大脑”，主入口函数，负责把原始日志变成一张完整的质量健康报告。
  - 输入：`history_items`（一串质量检查记录，每条像“某人在某时间、某页面、因‘高歧义’被拦下”）；可选参数如按页面筛选、按告警码过滤、限制条数、自定义页面标准化规则等。
  - 输出：一个结构化字典，包含总次数、通过/拦截数、拦截率、近14天趋势图数据、近24小时每小时分布、TOP拦截原因、每个问题的修复建议、最近20条拦截详情等。
  - 大白话解释：就像医院的体检报告系统——你丢给它一堆化验单（原始日志），它自动算出血压异常几次、血糖偏高占比多少、最近一周指标怎么变、最可能是什么病（比如“低解析置信度”）、该怎么调理（比如“补全业务目标和PRD”），最后打包成一页能看懂的报告。

- **`_quality_gate_event_from_history()`**：质量日志的“翻译官”，把原始杂乱字段统一格式化成标准事件。
  - 输入：一条原始日志字典（可能字段名不统一、缺字段、类型错乱）。
  - 输出：一个干净、字段齐全的标准事件字典（含时间、动作、用例ID、页面、放行/拦截决定、阶段、拦截原因列表等）。
  - 大白话解释：就像快递员收包裹时，不管寄件人写的是“收货地址”“送货地”还是“目的地”，他都统一记成“收件地址”；这里也一样，不管原始日志里叫 `alert_code` 还是 `code`，都归到标准字段里，确保后续统计不翻车。

- **`_quality_gate_remediation_for_code()`**：问题修复的“小锦囊”，根据错误编码返回人话版整改指南。
  - 输入：一个错误码字符串（如 `"high_ambiguity_present"`）。
  - 输出：一个含标题、具体建议、负责人、优先级的字典（如“先消歧再生成｜逐条澄清判定标准｜产品/测试设计｜P0”）。
  - 大白话解释：就像汽车仪表盘亮了“发动机故障灯”，它不只报错，还弹出提示：“请检查机油液位，建议30分钟内添加，车主自己可操作”。这里就是给每个质量拦截原因配好“说明书”。

- **`_extract_history_quality_gate()`**：质量门禁数据的“找钥匙人”，专门从原始日志里挖出嵌套的 `quality_gate` 字段。
  - 输入：一条原始日志字典。
  - 输出：`quality_gate` 子字典（如果存在且是字典类型），否则 `None`。
  - 大白话解释：原始日志像一个没整理过的抽屉，`quality_gate` 数据可能藏在不同夹层里。这个函数就是专门拉开抽屉、扒开杂物、只拿那个叫“质量门禁”的小盒子出来。

## 🧩 调用关系与数据流转
```
summarize_quality_gate_events()  
    ↓ 接收 history_items 列表  
    → 对每条 item 调用 _quality_gate_event_from_history()  
        → 内部先调用 _extract_history_quality_gate() 拿出 quality_gate 部分  
        → 再清洗 blockers、decision 等字段，组装成标准事件  
    ↓ 得到 events 列表（全是标准事件）  
    → 用 _row_matches() 过滤（按 page / alert_code 筛选）→ 得 rows  
    → 分出 blocked_events / allow_events  
    → 遍历 blocked_events：  
        ↓ 统计 blocker 各 code 出现次数 → blocker_counter  
        ↓ 同时查 _quality_gate_remediation_for_code() 获取修复建议 → alert_details_map  
        ↓ 收集最近样本（最多20条）→ samples  
    → 解析所有事件时间戳 → parsed_rows + latest_seen  
    → 基于 latest_seen 推算最近24小时每小时桶 → hourly_buckets  
    → 汇总 trend（14天）、decision_trend_24h（24小时）、summary_24h（24小时摘要）等  
    ↓ 最终拼成大字典返回
```

## 💡 值得学习的写法
- **防御式清洗无处不在**：所有 `str(...).strip().lower()`、`isinstance(x, dict)`、`if isinstance(y, list) else []` 等写法，像给代码穿了防弹衣——原始日志字段缺失、类型错乱、空值、大小写混用？统统兜住，不崩、不报错、有默认值。
- **“锚点时间”动态计算 24 小时窗口**：不用硬写 `datetime.now() - 24h`，而是先找所有事件里**最新的一条时间**作为锚点（`latest_seen`），再倒推23小时做24个整点桶。这样即使日志延迟到达，趋势图依然准确对齐“最近24小时”，不是“固定昨天此刻到现在”。
- **双字典复用避免重复计算**：`blocker_counter`（只统计次数）和 `alert_details_map`（带修复建议+样本）共用同一套 `code` 键，但各自独立构建，逻辑清晰不耦合；且 `remediation` 只查一次，避免循环里反复调用。
- **`PageNormalizer` 类型提示 + 默认 lambda**：用类型别名 `PageNormalizer = Callable[[str], str]` 提前说清“页面标准化是个函数”，再给默认实现 `lambda value: str(value).strip().lower()`，既灵活（外部可传自定义清洗函数），又零门槛（不传也不报错）。

## ⚠️ 需要注意的地方
- **`_row_matches()` 中的 `normalized_alert` 匹配逻辑是“包含关系”而非“精确匹配”**：代码里是 `if normalized_alert in {alert, code}`，意味着如果你传 `alert_code="low"`，它会误匹配 `"low_parse_confidence"`。实际应为 `==` 才合理，当前写法容易导致筛选结果比预期多。
- **时间解析容错强但可能静默失败**：`try/except` 忽略所有时间解析异常，坏格式时间（如 `"2024-04-01 abc"`）会被直接跳过。虽保证不崩溃，但若大量日志时间格式异常，`trend` 和 `decision_trend_24h` 可能严重缩水，建议加日志告警或统计丢弃数。
- **`limit` 参数未校验上限，可能 OOM**：`history_items[:normalized_limit]` 若原始列表极大（如百万条），而 `limit=500` 是用户可控参数，但若有人恶意传 `limit=1000000`，仍会切片加载全部原始数据到内存。建议加硬上限（如 `min(normalized_limit, 5000)`）。
- **`samples` 最多存 20 条，但没做去重或时效排序**：同个 `code` 的样本可能集中来自同一小时，无法代表时间分布；且新样本永远追加末尾，旧样本不会滚动淘汰（虽然限制了数量，但没保证“最新”）。如需代表性样本，建议按时间倒序取前20。