# 📘 代码说明书
## 一句话概括
这是一个用来检查“自动化操作指令”（比如点击按钮、等待页面加载）是否写得规范、完整、安全的“质检员”程序——它不执行操作，只负责把用户写的指令清单逐条审核，发现错误就清晰地告诉你哪里错了、为什么错。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `ir_schema_validator.py` | 提供一套规则和工具，专门检查“中间表示（IR）”格式的操作指令是否符合预期结构（比如每步必须有 action 和 target，action 只能是允许的几种），并把错误信息组织成统一、易读的格式。 |

## 🔍 核心函数/类说明
- **`class IRSchemaValidationError`**：一个“带身份证的错误”——不是普通报错，而是自带编号（`code`）、人话提示（`message`）和补充信息（`detail`）的定制化错误。
  - 输入：错误码（如 `"unsupported_action"`）、提示语（如 `"action 'hover' is not allowed"`）、可选的细节字典（如 `{"index": 2, "action": "hover"}`）
  - 输出：无返回值；但调用 `.to_dict()` 可生成标准字典，方便前端或日志直接展示（例如 `{"code": "unsupported_action", "message": "...", "detail": {...}}`）
  - 大白话解释：就像快递拒收单——不光写“拒收”，还写明“拒收原因：地址不全（code: address_missing）”，还附上具体哪一单、哪个地址字段空了（detail）。这样开发人员一眼就知道怎么改，而不是对着 `ValueError` 发呆。

- **`class IRSchemaValidator`**：一个“指令质检员”，初始化时设定允许哪些操作（如默认允许 `"click"`、`"fill"` 等6种），然后可以反复对不同指令清单进行审查。
  - 输入：初始化时可传入自定义允许的操作集合（如 `{"click", "type"}`）；主方法 `validate_ir()` 接收一个类似 `{ "steps": [ {...}, {...} ] }` 的指令字典。
  - 输出：如果全部合格，返回一个“整理干净”的指令字典（所有 `action`/`target` 被标准化为字符串，空格被去掉）；如果不合格，抛出上面那种带身份证的错误。
  - 大白话解释：就像餐厅后厨的“备菜质检员”——你递来一叠做菜步骤卡（`ir`），他先看整体是不是一张完整的卡片（不是乱纸团），再拆开每张小卡（`step`），检查有没有写“做什么”（action）和“对谁做”（target），动作是不是菜单里批准过的（比如不能写“油炸浏览器”这种非法操作），最后把每张卡擦干净、排整齐再还给你；只要有一张卡不合格，他就立刻停下，拿出一张印好编号的拒收单（`IRSchemaValidationError`）交给你。

- **`def validate_ir()`**：质检员的“总入口”，负责检查整份指令清单的骨架是否合规。
  - 输入：整个指令对象（如 `{"steps": [{"action": "click", "target": "#submit"}]}`）
  - 输出：校验通过后的标准化指令字典（同输入结构，但 `steps` 里的每个 step 都被 `validate_step` 处理过）
  - 大白话解释：相当于质检员接到一摞文件，先翻封面确认是“操作指令集”，再数清楚里面有多少张步骤卡（`steps` 必须是数组），然后把每张卡交给手下员工（`validate_step`）挨个检查。

- **`def validate_step()`**：质检员的“步骤检查员”，专管单张操作卡。
  - 输入：单个步骤字典（如 `{"action": "  click  ", "target": "\n #login \n"}`）和当前序号（方便定位第几步出错）
  - 输出：清洗后的步骤字典（如 `{"action": "click", "target": "#login", ...}`，其他原有字段保留）
  - 大白话解释：这张卡送到他手上，他先看有没有写“动作”和“目标”，没写就开拒收单（注明是第几步）；再看动作是不是厨房白名单里的（比如“微波炉加热”不在名单里就不行）；最后把动作和目标两边的空格擦掉，大小写统一（都转成小写），再把这张卡工整地交回给总质检员。

## 🧩 调用关系与数据流转
```
用户调用 validate_ir(ir)  
       ↓  
validate_ir 检查 ir 是否为字典 → 否？→ 抛 IRSchemaValidationError("invalid_ir")  
       ↓ 是  
检查 ir["steps"] 是否为列表 → 否？→ 抛 IRSchemaValidationError("steps_missing")  
       ↓ 是  
对 steps 中每个 step 执行：validate_step(step, index=0), validate_step(step, index=1), ...  
       ↓（逐个调用）  
validate_step 检查 step 是否为字典 → 否？→ 抛错（带 detail={"index": 当前序号}）  
       ↓ 是  
提取 action & target → 去空格 → 检查是否为空 → 是？→ 抛错（列明缺哪个字段 + index）  
       ↓ 否  
检查 action 是否在 allowed_actions 中 → 否？→ 抛错（带 index + 允许的动作列表）  
       ↓ 是  
返回清洗后的 step 字典（action/target 已标准化，其他字段原样保留）  
       ↓  
validate_ir 收集所有清洗后的 step，组装成新字典并返回
```

## 💡 值得学习的写法
- **错误自带“身份证”（code + detail）**：不是简单 `raise ValueError("bad action")`，而是封装成可序列化的对象，`.to_dict()` 直接生成 API 友好的错误响应，前后端联调时省去大量错误码映射工作。
- **默认值与防御性初始化**：`allowed_actions` 参数允许传 `None` 或空集合，自动 fallback 到安全默认集（6个常用动作），避免用户漏配导致“所有操作都被拦住”的意外。
- **字符串标准化一步到位**：`str(... or "").strip()` 同时处理 `None`、空字符串、带空格字符串三种常见脏数据，健壮性强。
- **错误详情（detail）始终是 dict**：用 `dict(detail or {})` 确保 `detail` 永远是可修改的普通字典，避免传入 `frozenset` 或不可变对象导致后续 `.update()` 失败。

## ⚠️ 需要注意的地方
- **`validate_ir` 不校验 `steps` 以外的字段**：比如用户误加了 `{"steps": [...], "timeout": 5000, "env": "staging"}`，这些字段会被原样保留——本模块只管“步骤结构”，不管“额外配置”。如果业务需要限制字段，得在别处加校验。
- **`action` 和 `target` 强制转为字符串并去空格**：如果用户本意是传数字 ID（如 `{"action": "click", "target": 123}`），这里会变成 `"123"` —— 表面没问题，但下游执行时可能因类型不符失败。建议文档注明“target 应为字符串”。
- **`allowed_actions` 传入非 set 类型会静默失效**：比如传 `allowed_actions=["click"]`（列表），因 `isinstance(allowed_actions, set)` 为 `False`，会直接走默认集。应加类型提示或运行时检查（如 `if not isinstance(..., (set, type(None)))`）。
- **没有递归校验嵌套结构**：当前只校验 `steps` 是数组、每个 `step` 是对象，但不对 `step` 内部更深层字段（如 `{"action": "fill", "value": {"name": "Alice"}}` 中的 `value`）做类型检查——这是有意为之（保持轻量），但需确保上游已保证结构扁平。