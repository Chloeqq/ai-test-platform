# 📘 代码说明书
## 一句话概括
这个文件是用来给 AI 相关的操作（比如调用大模型、生成文案）自动打上“身份证标签”的小工具——它生成一个唯一、简洁的追踪编号（trace_id），并把操作背景信息（如页面、模型名、提示词版本等）打包塞进请求数据里，方便后续查问题、看效果。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `observability/ai_trace.py` | 提供两个函数：一个「造标签」（生成带 trace_id 的上下文字典），一个「贴标签」（把标签安全地加到任意请求数据里） |

## 🔍 核心函数/类说明
- **`build_ai_trace_context()`**：作用是根据几个业务参数（比如当前在哪个页面、用了哪个模型、提示词是第几版），生成一个标准化的、带唯一编号的“AI操作档案”。
  - 输入：全是可选字符串参数（`page`, `prompt_version`, `model`, `source`, `instructions_version`），不传或传空/None 也没关系。
  - 输出：一个字典，包含 `trace_id`（如 `"ai-trace-a1b2c3d4e5f67890"`）和所有归一化后的字段（比如空字符串变 `"common"`，`None` 变 `"unknown"`）。
  - 大白话解释：就像快递员发包裹前要填一张面单——地址（page）、货物型号（model）、包装说明书版本（instructions_version）……哪怕你没写全，它也会帮你补默认值（比如地址空着就写“通用仓”），最后还用这些信息算出一个独一无二的 16 位订单号（trace_id），保证每个 AI 操作都能被精准认出来。
  
- **`attach_ai_trace_context()`**：作用是把上面生成的“AI档案”（context）安全地塞进一个请求数据（payload）里，不破坏原有结构。
  - 输入：一个原始数据 `payload`（通常是字典，比如发给后端的 JSON 请求体），和一个 `context` 字典（来自 `build_ai_trace_context`）。
  - 输出：一个新的字典，其中 `payload["ai_trace"]` 是合并后的结果（优先保留 payload 原有的 `ai_trace` 内容，再用 context 覆盖/补充字段）。
  - 大白话解释：就像往一个已封好的快递箱里加一张新便签——如果箱子上本来就有张“AI备注条”，就把它和新便签合并（新内容优先）；如果没有，就直接贴上新便签。整个过程不会弄丢箱子原来的东西，也不会搞乱格式。

## 🧩 调用关系与数据流转
```
用户代码（比如某个 API 接口）  
    ↓  
调用 build_ai_trace_context(  
    page="dashboard", model="gpt-4o", prompt_version="v2.1"  
)  
    → 返回 { "trace_id": "ai-trace-1a2b3c4d...", "model": "gpt-4o", ... }  
    ↓  
把这个返回值作为 context，传给 attach_ai_trace_context(  
    payload={"user_id": 123, "query": "帮我总结"},  
    context=上面的字典  
)  
    → 返回新 payload：{  
         "user_id": 123,  
         "query": "帮我总结",  
         "ai_trace": { "trace_id": "...", "model": "gpt-4o", ... }  
       }  
    ↓  
这个最终 payload 被发给后端或记录到日志中，供运维/算法同学追踪分析
```

## 💡 值得学习的写法
- 使用 `*` 强制关键字参数（`def build_ai_trace_context(*, page="", ...)`）：防止调用时误写成位置参数（比如 `build_ai_trace_context("home", "v1")`），让代码更健壮、可读性更强——就像订外卖必须明确说“我要的是 *地址* 和 *备注*”，不能靠顺序猜。
- `_text(value)` 工具函数统一处理空值：把 `None`、空字符串、空白字符都转成 `""` 再 `.strip()`，避免后续拼接时报错或生成奇怪的 trace_id（比如 `" | |gpt-4|..."`）。
- `trace_id` 用 `sha1(...).hexdigest()[:16]` 截取前 16 位：既保证唯一性（SHA1 长度足够防碰撞），又控制长度友好（比完整 40 位短一半，日志里看着清爽）。
- `attach_ai_trace_context` 中用 `**(context or {})` 和 `**trace_payload` 合并字典：天然支持“已有字段不被覆盖，新字段自动补充”，类似微信聊天里“合并联系人资料”——你有电话我有邮箱，咱俩合起来就是完整名片。

## ⚠️ 需要注意的地方
- `build_ai_trace_context` 里所有参数都是字符串类型，但函数内部只做 `str(value or "")` ——如果传入的是复杂对象（比如一个 `User` 类实例），会变成类似 `"<User object at 0x...>"`，可能污染 trace_id。建议调用前确保传的是纯字符串或简单标量。
- `attach_ai_trace_context` 对 `payload` 做了 `dict(payload if isinstance(...) else {})` 安全兜底，但如果 `payload` 是不可迭代对象（比如数字、布尔值），会静默变成空字典 `{}`，可能掩盖数据错误。实际使用时最好提前校验 payload 类型。
- `sha1` 虽然在这里只是做哈希标识（非密码学场景），但 SHA1 已被学术界认为不够安全；如果未来该 trace_id 用于权限或签名场景，需升级为 `sha256` 或 `blake2b`。
- `normalized_source = _text(source) or "manual"` 这行中，如果 `source` 是字符串 `"0"` 或 `"false"`，`_text("0")` 返回 `"0"`（非空），所以 `or "manual"` 不生效——这是合理行为（`"0"` 确实是有效 source），但容易让人误以为“0 就是空”，需注意语义。