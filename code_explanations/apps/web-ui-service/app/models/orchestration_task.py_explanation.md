# 📘 代码说明书
## 一句话概括
这是一个用来在数据库里“记账”自动化任务的模板——就像给每个待执行的AI工作流（比如“从Excel读数据→让AI总结→存到数据库”）发一张带编号、状态和详细说明书的工单。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `orchestration_task.py` | 定义了“自动化任务”在数据库里长什么样，即告诉程序：每次要记录一个任务时，必须包含哪些字段（比如名字、状态、输入数据、配置等），相当于设计了一张标准工单表格。 |

## 🔍 核心函数/类说明
- **`class OrchestrationTask(Base)`**：这是一个数据库“表模板”，不是函数，但它决定了未来所有自动化任务信息如何被存进电脑的“电子台账”里。
  - 输入：无（它不接收参数，而是被其他代码用来创建真实的数据行）  
  - 输出：无（它本身不运行，只提供结构；真正存数据的是用它创建的对象，比如 `task = OrchestrationTask(task_name="日报生成")`）  
  - 大白话解释：想象你开了一家“智能代办事务所”，每个客户下单（比如“每周一自动整理销售数据”），你就得填一张标准登记表——这张表的表头（姓名、电话、事项、紧急程度、备注…）就是这个类定义的。它不干活，但保证所有人填的表格式统一，后续查、筛、改都方便。

## 🧩 调用关系与数据流转
（本文件是纯“结构定义”，不包含业务逻辑，因此没有函数调用链）  
→ 其他文件（比如API接口或任务调度器）会「引用」它：  
  `from app.models.orchestration_task import OrchestrationTask`  
→ 然后创建真实任务对象：  
  `new_task = OrchestrationTask(task_name="用户画像生成", status="queued", input_source_payload={"file_id": "abc123"})`  
→ 再交给数据库操作模块（如 `session.add(new_task); session.commit()`）→ 数据真正写入 `orchestration_tasks` 表中  
→ 后续查询、更新状态（如把 `"queued"` 改成 `"running"`）也都基于这个类来操作同一张表  

简图：  
```
API接口 / 调度器 → 创建 OrchestrationTask 实例 → 数据库会话（session）→ 写入/读取 orchestration_tasks 表
```

## 💡 值得学习的写法
- ✅ `mapped_column(JSON, default=dict)`：用 `dict` 作为默认值（而不是 `None` 或 `{}` 字面量），避免多个实例意外共享同一个空字典（Python 中可变默认参数的经典坑已规避）。  
- ✅ 所有 JSON 字段都设 `default=dict`：确保即使没传数据，字段也不会是 `NULL`，后续代码直接 `.get("key")` 更安全，不用总判空。  
- ✅ `index=True` 合理加在常用于查询的字段上（如 `task_name`, `status`, `created_at`）：就像给通讯录按“姓氏”“城市”贴标签，查起来飞快——比如“查所有 status='failed' 的任务”就不用翻全表。  
- ✅ `server_default=func.now()`：让数据库自己填创建时间，不怕程序时钟不准或网络延迟导致时间错乱，也省得每次手动写 `datetime.now()`。

## ⚠️ 需要注意的地方
- ⚠️ `input_source_payload`, `agent_config`, `asset_binding`, `execution_config`, `preview_snapshot` 全是 `JSON` 类型：它们看起来像 Python 字典，但**存进数据库前会被自动转成 JSON 字符串，读出来时再转回字典**——所以不能存函数、类实例、日期对象等非JSON原生类型，否则会报错。  
- ⚠️ `String(255)` 和 `String(80)` 是长度限制：如果 `task_name` 超过255个字符（比如一段超长描述），数据库会直接拒绝保存（报错），不是自动截断！前端或调用方需提前校验。  
- ⚠️ `created_by` 默认是 `"admin"`：如果系统支持多用户，这里**不能依赖默认值**，必须由登录用户信息显式传入，否则所有任务都显示是 admin 下的单，失去审计意义。  
- ⚠️ 没有定义外键或约束（比如 `status` 只能是 `"queued"/"running"/"done"/"failed"`）：靠代码约定而非数据库强制，容易因拼写错误（如 `"faild"`）导致状态混乱，建议后期加 `CheckConstraint` 或枚举类型增强健壮性。