# 📘 代码说明书
## 一句话概括  
这是一个定义「工作台（Workbench）各类运行状态和人工干预记录」的数据库模型文件，相当于给系统建了一套“电子档案柜”，专门存各种自动化任务执行过程中的快照、审核决定、拦截判断、操作日志、缺陷关联和故障归因校准等信息。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `workbench_state.py` | 定义了 6 个数据库表模型（类），分别对应工作台中不同类型的运行状态与人工决策数据，是整个系统“记住发生了什么”的底层基础。 |

## 🔍 核心函数/类说明  
- **`class WorkbenchRuntimeRun`**：记录一次自动化运行的“快照”  
  - 输入：无（这是数据库模型，不直接接收输入）  
  - 输出：无（这是定义结构，不是执行逻辑）  
  - 大白话解释：就像你点外卖后，平台会记下“订单号（run_id）、来自哪个门店（project）、在哪个页面发起（page）、当前状态（status，比如‘运行中’‘失败’）、附带的参数（payload，比如用户选的口味、地址）”，这个类就是设计这张“订单快照表”的模板。  

- **`class WorkbenchReviewDecision`**：记录人工审核的“拍板结果”  
  - 大白话解释：当系统跑完一个任务，不确定要不要放行时，会推给人工看——比如“这段自动生成的文案是否合规？”。这个类就存下“谁审的（没显式字段但可扩展）、审的是哪个项目+哪次运行+哪页（project/run_id/page）、审核类型（review_type，如‘文案审核’‘截图审核’）、最终结论（status，如‘通过’‘驳回’）以及补充说明（payload）”。  

- **`class WorkbenchExecutionGateDecision`**：记录自动闸门的“开关决定”  
  - 大白话解释：像地铁进站前的闸机——系统会在关键节点自动判断“这次运行能不能继续往下走？”。这个类就存下“对哪个项目+哪次运行+哪页做的拦截/放行决定（decision 字段，值可能是 'allow' 或 'block'）”，相当于给自动化流程装了个智能红绿灯。  

- **`class WorkbenchHistoryEvent`**：记录所有“谁在什么时候干了啥”的操作日志  
  - 大白话解释：就像微信的“最近访问”或淘宝的“操作记录”，它不存决策结果，只忠实记下“谁（actor_display）、什么时候（created_at）、对哪次运行（run_id）、在哪页（page）、做了什么动作（action，如‘点击重试’‘提交审核’）、结果如何（status）、还附带简要总结（detail_summary）”。方便事后查问题、做复盘。  

- **`class WorkbenchDefectLink`**：记录“测试用例”和“缺陷报告”的绑定关系  
  - 大白话解释：开发写了一个功能（case_id），测试发现有问题（defect_id），这个类就是把它们俩“用胶水粘起来”的登记表——比如“登录按钮失效”这个缺陷（defect_id），是由“登录流程第3步”这个测试用例（case_id）暴露出来的。避免问题找不到根、修复没闭环。  

- **`class WorkbenchFailureSourceCalibration`**：记录“故障原因到底是谁的锅？”的人工校准  
  - 大白话解释：系统有时会自动猜故障原因（比如“页面加载慢，可能是网络问题”），但人看了真实情况可能说：“不对，其实是后端接口超时！”。这个类就专门存下“样本ID（sample_id）、对应哪次运行（run_id）、哪个用例（case_id）、哪页（page）、人认为的真实原因（confirmed_failure_source）、系统原来猜的（predicted_failure_source）、人最后怎么判的（human_decision，如‘确认’‘修正’）”，用来训练和优化系统的“猜因能力”。  

## 🧩 调用关系与数据流转  
这些类**本身不互相调用**（它们只是“表格设计图”，不是“操作员”），但实际使用时，其他代码会按需调用它们来存/查数据，典型流转如下：  

```
用户触发一次运行 → 
  [WorkbenchRuntimeRun] 记录初始状态（run_id, project, status="pending"）→ 
  系统执行中 → 
    [WorkbenchHistoryEvent] 记一条“开始执行”日志 → 
    遇到需要审核的环节 → 
      [WorkbenchReviewDecision] 存下待审状态 → 
      人工审核后 → 
        [WorkbenchReviewDecision] 更新 status → 
        [WorkbenchHistoryEvent] 记一条“人工审核完成”日志 → 
    遇到执行闸门 → 
      [WorkbenchExecutionGateDecision] 存下拦截/放行决定 → 
    运行失败 → 
      [WorkbenchFailureSourceCalibration] 等待人工标注真实原因 → 
      同时 [WorkbenchDefectLink] 可能关联新缺陷 → 
      所有变更都自动更新 created_at/updated_at 时间戳
```  
✅ 关键点：所有类都共享 `created_at`（创建时间）和 `updated_at`（最后修改时间），由数据库自动维护，开发者不用手动写时间。

## 💡 值得学习的写法  
- ✅ **统一的时间处理**：所有模型都用 `DateTime(timezone=True)` + `server_default=func.now()` + `onupdate=func.now()`，确保时间精准且全自动，避免手动填时间导致的混乱。  
- ✅ **防重复设计**：每个表都加了 `UniqueConstraint`（唯一约束），比如 `WorkbenchRuntimeRun` 用 `run_id` 唯一，`WorkbenchReviewDecision` 用 `(project, run_id, page, review_type)` 四元组唯一——就像“同一份报告不能被同一个人审两次”，从数据库层面杜绝脏数据。  
- ✅ **灵活又安全的 JSON 字段**：`payload: Mapped[dict]` 用 `JSON` 类型存储任意结构化数据（比如复杂参数、嵌套结果），既保留扩展性，又比 `Text` 更易查询和校验。  
- ✅ **默认值全覆盖**：每个字段都有 `default=`（字符串空值、空字典、"default"等），避免插入时漏填字段报错，新手友好。

## ⚠️ 需要注意的地方  
- ⚠️ **`String(120)` 不是万能的**：`run_id`、`project` 等字段限制 120 字符，如果未来 ID 变长（比如用了 UUIDv7 或带路径的长哈希），会截断报错。建议注释里说明预期长度，或改用 `Text`（但会损失索引效率）。  
- ⚠️ **`WorkbenchHistoryEvent` 没有 `updated_at`**：它只有 `created_at`，意味着这条日志一旦写入就不能被修改（符合日志不可篡改原则 ✅），但如果业务需要标记“日志已确认/已归档”，就得额外加字段，不能依赖 `updated_at`。  
- ⚠️ **`linked_at` 在 `WorkbenchDefectLink` 中是 String 而非 DateTime**：它本意可能是“关联时间”，但存成字符串（如 `"2024-05-20T14:30"`）无法直接排序或范围查询。应改为 `DateTime(timezone=True)` 并设 `server_default=func.now()` 更合理。  
- ⚠️ **`payload` 默认是 `dict`，但没做非空校验**：如果传 `None` 进去，SQLAlchemy 可能报错或存成 `null`，而前端读取时容易崩。建议加 `nullable=False` 和 `default=dict` 双保险（当前已有 default，但没禁 null，稳妥起见可补 `nullable=False`）。