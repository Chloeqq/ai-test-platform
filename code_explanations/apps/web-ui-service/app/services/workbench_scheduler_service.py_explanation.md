# 📘 代码说明书
## 一句话概括
这是一个“调度指挥室”的小助手，专门帮自动化测试系统（比如跑网页或手机App测试）看清当前任务排队情况、分析资源压力，并生成下一步该往哪派活的执行计划。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `workbench_scheduler_service.py` | 提供两个核心能力：① **看全局**（统计所有待调度/运行中/已完成的任务分布和压力）；② **做派单**（把排队中的任务按环境、工具、资源类型分组，告诉系统“这批活该一起发给哪个设备池”） |

## 🔍 核心函数/类说明
- **`_int_value(value: Any) -> int`**：作用——安全地把任何乱七八糟的东西（空值、字符串、None、错误类型）都变成一个整数，出错就默认返回 0。  
  - 输入：任意类型的数据（比如 `"123"`、`None`、`"abc"`、`[]`）  
  - 输出：一个整数（如 `123`、`0`、`0`、`0`）  
  - 大白话解释：就像收银台的“万能扫码器”——扫得上就报数字，扫不上就当没东西，绝不卡机、不报错，保证后面算数不崩。

- **`_environment_pool_for_task(item: dict) -> str`**：作用——根据任务描述（比如它说要跑在手机上？还是跑API？还是吃内存的浏览器？），决定该把它塞进哪个“干活专用车间”。  
  - 输入：一个任务字典（含 `runner` 和 `resource_profile` 字段）  
  - 输出：一个车间名字（字符串），比如 `"mobile-device-farm"`（手机农场）、`"web-browser-heavy"`（重负载浏览器车间）  
  - 大白话解释：就像快递分拣员看包裹上的标签——写“生鲜”，送冷链车；写“易碎”，贴泡沫；这里写 `"runner": "mobile"`，就直接塞进“手机测试专用流水线”。

- **`build_scheduler_summary(...)`**：作用——生成一份《今日调度健康报告》，告诉你：总共多少活？哪些队列快挤爆了？哪些资源（手机/浏览器/重型机器）最忙？还顺手给出两条人话建议。  
  - 输入：`items`（所有任务列表，每项是字典）、`task_summary`（额外汇总信息，比如被拦下的任务数）  
  - 输出：一个大字典，含总数、各队列详情（带“压力等级”low/medium/high）、各类资源使用分布、以及可读性建议  
  - 大白话解释：就像餐厅店长下班前看的“今日运营日报”：总接单127份，A号窗口排了8人（⚠️高压！），B号窗口3人（✅正常），厨房里烤箱用了70%，搅拌机只用了20%……最后加一句：“明天早班多配个烤箱师傅”。

- **`build_scheduler_dispatch_plan(...)`**：作用——生成一份《马上要发的派单清单》，把所有“正在排队等开工”的任务，按“去哪个队列 + 用什么工具 + 要啥资源 + 进哪个车间”四要素打包成一个个“任务包”（叫 lane），并告诉每个包该并发跑几个。  
  - 输入：`items`（所有任务列表）  
  - 输出：一个字典，含总共打了几个包（`lane_count`），以及每个包的详情（含任务ID列表、预估耗时、推荐并发数）  
  - 大白话解释：就像外卖站调度员把一堆待送订单，按“区域+骑手车型+餐盒类型”分组——西区+电瓶车+保温袋 → 一组；东区+自行车+普通袋 → 一组；再给每组标上：“这组5单，建议2人同时送，别堆一起”。

## 🧩 调用关系与数据流转
```
外部调用者（比如 FastAPI 接口）
        ↓
build_scheduler_summary(items=..., task_summary=...)  
   ├─→ _int_value() × 多次（处理各种数字字段）  
   ├─→ _environment_pool_for_task() × 每个 item（决定车间）  
   └─→ 统计结果 → 整理成 queue_rows → 排序 → 加 pressure 判断 → 合成 recommendations  
        ↓  
build_scheduler_dispatch_plan(items=...)  
   ├─→ _int_value()（算预估时间）  
   ├─→ _environment_pool_for_task()（再次决定车间）  
   └─→ 按 (queue, runner, resource_profile, environment_pool) 打包 → 算推荐并发数 → 排序输出
```
💡 数据流转关键点：  
- 两个主函数都依赖 `_environment_pool_for_task()` 做“车间匹配”，但各自独立调用，不互相传参；  
- 所有原始 `items` 列表被遍历两次（一次看全局，一次做派单），但彼此隔离，互不影响；  
- 中间所有统计（如 `defaultdict(int)`）都是函数内局部变量，不污染外部。

## 💡 值得学习的写法
- ✅ **防御式取值 + 安全转整型**：`str(item.get("xxx", "default")).strip() or "default"` 和 `_int_value()` 组合，彻底避开 `KeyError` / `TypeError` / `NoneType` 错误，新手抄作业也不怕崩。  
- ✅ **用 tuple 当字典 key 实现多维分组**：`(queue, runner, resource_profile, environment_pool)` 直接当 `lanes` 的 key，比拼接字符串或嵌套字典更清晰、更高效、不易出错。  
- ✅ **压力分级逻辑直白好维护**：`if queued >= 5: "high"` 这种规则写死在代码里，虽然简单，但产品说“改规则”时，开发一眼就能找到、改得准、测得快。  
- ✅ **排序 key 用负号实现“降序优先”**：`key=lambda row: (-queued, -running, queue)` 让“排队多的排前面”，比写复杂 comparator 更 Pythonic。

## ⚠️ 需要注意的地方
- ⚠️ **`items` 里混入非字典类型会静默跳过**：`if not isinstance(item, dict): continue` 是友好，但万一上游传了个 `[1,2,3]` 或 `None` 进来，函数不会报错也不会提醒——日志里可能就少了这几条，排查时容易懵。建议加 warn 日志（尤其开发环境）。  
- ⚠️ **`_environment_pool_for_task()` 的判断顺序有隐含优先级**：`runner == "mobile"` 在前，`resource_profile in {...}` 在后。如果某任务同时有 `"runner": "mobile"` 和 `"resource_profile": "heavy"`，它一定进 `"mobile-device-farm"`，不会考虑 heavy —— 这是设计意图还是疏漏？需确认文档或注释。  
- ⚠️ **`recommended_concurrency` 规则太简单**：目前只看 `resource_profile`，但实际并发数可能还受 CPU/内存/设备数限制。硬编码 `1 if heavy else 2` 在真实生产环境可能不准，后续应支持配置化或动态探测。  
- ⚠️ **`task_id` 转字符串未防空**：`str(item.get("task_id", "")).strip()` 如果 `task_id` 是 `None`，会变成 `"None"` 字符串——可能造成后续 ID 匹配失败。应统一用 `_int_value()` 或显式判空。