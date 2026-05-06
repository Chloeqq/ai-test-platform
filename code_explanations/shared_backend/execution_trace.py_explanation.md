# 📘 代码说明书
## 一句话概括
这个文件是用来「给自动化操作过程拍录像+写日记」的——它不执行任何实际操作，而是悄悄记录每一步做了什么、什么时候做的、成功还是失败了，最后整理成清晰的报告。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `execution_trace.py` | 提供两个“记事本”类（`StepTrace` 和 `ExecutionTrace`），专门用来结构化地记录一次自动化任务（比如网页点击、表单填写）中每个步骤和整体的执行情况。 |

## 🔍 核心函数/类说明
- **`_utc_now_iso()`**：作用是生成一个标准格式的当前时间字符串（如 `"2024-05-20T14:23:45.123456+00:00"`）。  
  - 输入：无  
  - 输出：一个符合国际标准（ISO 8601）的 UTC 时间字符串  
  - 大白话解释：就像手机自动设置的“世界标准时间”，避免因电脑时区不同导致记录的时间乱套；每次调用都拍一张“此刻的快照”，确保所有时间戳可比较、不打架。

- **`class StepTrace`**：代表「一个具体操作步骤」的记事本，比如“点击登录按钮”或“输入用户名”。  
  - 输入：创建时需提供 `index`（第几步）、`action`（做什么，如 `"click"`）、`target`（对谁做，如 `"login button"`）、`selector`（怎么找到它，如 `"#login-btn"`）、`status`（结果，如 `"PASS"` 或 `"FAIL"`）  
  - 输出：本身是一个对象，但可通过 `.to_dict()` 转成字典，方便存数据库或发给前端显示  
  - 大白话解释：就像快递包裹上的“操作日志贴纸”——第3步、扫描包裹、扫码枪、`#package-barcode`、成功✅，还自带两个时间戳（开始干和干完的时间），出错了还能写一句“扫不到码”。

- **`class ExecutionTrace`**：代表「一整次任务运行」的记事本，比如“跑一遍用户注册流程”。  
  - 输入：创建时至少要给个唯一编号 `run_id`（像快递单号），其他字段（状态、时间等）会自动填好  
  - 输出：通过 `.to_dict()` 可导出完整报告（含所有步骤）  
  - 大白话解释：就像快递公司的“整单汇总单”——单号 `RUN-789`、状态“已完成”、开始时间、结束时间，下面还附着全部12张“操作贴纸”（即 `steps` 列表）。调用 `.finalize()` 就相当于收件员最后盖章：“这单齐活了！”——它会自动填上结束时间，并根据所有步骤是否都成功，把整单状态标为“passed”或“failed”。

## 🧩 调用关系与数据流转
```
创建 ExecutionTrace（带 run_id）  
     ↓  
调用 .add_step(StepTrace(...)) 多次 → 把每个步骤“塞进”它的 steps 列表里  
     ↓  
所有步骤记录完后，调用 .finalize()  
     ↓  
.finalize() 内部：① 调用 _utc_now_iso() 填写 finished_at；② 检查 steps 中每个 StepTrace.status 是否全为 "PASS" → 决定整单 status  
     ↓  
最后调用 .to_dict() → 遍历 steps，对每个 StepTrace 调用 .to_dict() → 拼出嵌套字典（含所有时间、状态、细节）
```

## 💡 值得学习的写法
- ✅ **`field(default_factory=_utc_now_iso)` 的妙用**：不是直接写 `default=datetime.now(...)`（那会在类定义时就执行一次！），而是用 `default_factory` —— 每次新建对象时才调用 `_utc_now_iso()`，保证每个 `StepTrace` 和 `ExecutionTrace` 的时间戳都是“当场拍的”，精准又安全。  
- ✅ **`.finalize()` 自动判断整体状态**：不用手动写“如果12个步骤都OK才标success”，一行 `all(step.status == "PASS" for step in self.steps)` 就搞定，逻辑干净，不易漏判。  
- ✅ **`.to_dict()` 分层设计**：`ExecutionTrace.to_dict()` 会主动调用每个 `StepTrace.to_dict()`，像“班长收作业再统一交老师”，天然支持嵌套结构导出，后续转 JSON、存数据库、传给前端都毫无压力。

## ⚠️ 需要注意的地方
- ⚠️ **`steps: list[StepTrace] = field(default_factory=list)` 是必须的！** 如果写成 `steps: list[StepTrace] = []`（可变默认参数），所有 `ExecutionTrace` 实例会共享同一个空列表——A任务加的步骤，B任务也能看到！这是 Python 新手经典大坑。  
- ⚠️ **`status` 字段是纯字符串，没有限制枚举值**：目前允许任意字符串（如 `"PASS"`/`"FAIL"`/`"pending"`/甚至 `"apple"`），但后续如果逻辑依赖 `status` 做判断（比如只认 `"PASS"`），拼错大小写（`"pass"`）或打错字就会静默失败。建议未来可加简单校验或改用 `Enum`。  
- ⚠️ **`error` 字段只存在 `StepTrace` 里，`ExecutionTrace` 没有汇总错误信息**：如果想快速知道“这次运行到底哪错了”，目前得遍历所有 `steps` 找 `error != ""` ——可以考虑在 `.finalize()` 里顺便收集首个/所有错误，提升排查效率。