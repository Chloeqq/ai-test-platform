# 📘 代码说明书
## 一句话概括
这个文件是项目的“状态管家”，专门负责管理各种业务对象（比如测试用例、执行记录、AI生成结果等）的**合法状态值**和**状态名称翻译**，确保系统里不会出现乱七八糟的状态名，也不会把“Draft”写成“draft ”或“DRAFT ”导致出错。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `state_machines.py` | 定义所有业务状态的合法取值、状态间允许的切换规则，并提供状态标准化（大小写/空格容错）和状态名翻译（如把 `"ready"` 变成中文“就绪”）的功能 |

## 🔍 核心函数/类说明
- **`normalize_case_status(value, fallback="ready")`**：把用户或数据库传来的任意“用例状态”值（比如 `" DRAFT "`、`None`、`123`、`"Ready"`）统一转成小写、去空格后的标准字符串，并检查它是否在预设的合法状态列表里；如果不是，就返回默认值 `"ready"`。
  - 输入：任意类型的数据（字符串、数字、None、对象等），以及一个备用状态名（fallback）
  - 输出：一个合法的小写状态字符串（如 `"draft"`、`"ready"`），绝不会是错别字或空值
  - 大白话解释：就像快递柜的“扫码开门”——不管你是扫模糊了、扫反了、还是手抖多按了个空格，它都能自动帮你“对齐”到正确的柜子编号；扫不上？那就默认打开最常用的1号柜（fallback）。
- **`normalize_run_status(value, fallback="generated")`**：同上，但专用于“执行记录”（run）的状态标准化，fallback 默认是 `"generated"`。
  - 输入/输出/大白话逻辑同上，只是管的是另一类东西（比如一条自动化测试的执行过程）。
- **`get_case_status_name(code)`**：把一个状态编码（如 `"draft"`）翻译成人类看得懂的名字（比如中文“草稿”），背后调用了字典服务；如果找不到，就原样返回清理后的 code。
  - 输入：一个状态码字符串（如 `"draft"`）
  - 输出：对应的人类友好名称（如 `"草稿"`），或安全兜底的原始字符串
  - 大白话解释：就像手机通讯录——你输入联系人缩写 `"zsw"`，它自动显示全名“张三旺”；输错了？那就老老实实显示你打的 `"zsw"`，不瞎猜。
- **`get_run_status_name(code)`** 和 **`get_ai_status_name(code)`**：同上，分别是给“执行状态”和“AI状态”做翻译的“姓名翻译官”，各司其职，互不干扰。

## 🧩 调用关系与数据流转
```
外部数据（如API请求体、数据库字段）  
        ↓  
normalize_case_status() / normalize_run_status() / normalize_ai_status()  
        ↓（返回标准化后的合法状态码，如 "draft"）  
get_case_status_name() / get_run_status_name() / get_ai_status_name()  
        ↓（返回可读名称，如 "草稿"）  
→ 前端展示 / 日志记录 / 审计报告
```
补充说明：  
- 所有 `normalize_*` 函数都先调用 `str(value or "").strip().lower()` 做基础清洗（把 `None` → `""`，`" Draft "` → `"draft"`）；  
- 然后查预加载的 `CASE_STATUS_CODES`（来自字典服务）判断是否合法；  
- `get_*_status_name()` 则进一步调用 `resolve_dictionary_name(...)`，从统一词典服务中查翻译（类似查字典）；  
- 所有状态转换规则（如 `CASE_STATE_TRANSITIONS`）目前**只定义、未使用**（属于“预留接口”，为后续状态机校验打基础）。

## 💡 值得学习的写法
- ✅ **状态码集中管理 + 预加载**：`CASE_STATUS_CODES = get_enabled_codes("case_status")` 在模块加载时就一次性拉取并缓存所有合法状态，避免每次调用都查数据库或远程服务，又快又稳。  
- ✅ **fallback 设计防崩**：每个 normalize 函数都有 `fallback` 参数，确保哪怕字典缺失、配置错误、输入完全离谱，系统也不会报错崩溃，而是优雅降级——这是生产级代码的“安全气囊”。  
- ✅ **类型提示 + 显式关键字参数**：`def normalize_case_status(value: Any, *, fallback: str = "ready")` 中的 `*` 强制 `fallback` 必须用关键字传（如 `fallback="draft"`），防止调用时顺序写错，大幅提升可读性和健壮性。

## ⚠️ 需要注意的地方
- ⚠️ **状态转换规则尚未启用**：`CASE_STATE_TRANSITIONS` 等字典目前只是“静静躺着”，代码里没有任何地方检查“当前是 draft，能不能直接切到 passed？”——如果业务需要状态流转控制（比如审批流），必须额外写校验逻辑，否则这些规则就是“装饰画”。  
- ⚠️ **`resolve_dictionary_name` 是黑盒依赖**：它的实现不在本文件中（在 `case_dictionary.py`），如果那个模块返回 `None` 或抛异常，这里的 `get_*_status_name()` 就可能出问题；建议未来加一层 try/except + 更友好的 fallback。  
- ⚠️ **`Any` 类型太宽泛，易埋隐患**：`value: Any` 虽然灵活，但可能让调用方传入不可 `str()` 的对象（比如自定义类没写 `__str__`），导致 `str(value)` 报 `TypeError`；更稳妥的做法是加简单类型判断或文档注明“建议传字符串/数字”。