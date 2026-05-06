# 📘 代码说明书
## 一句话概括
这是一个为 Python 后端服务（比如 FastAPI）量身定制的「智能日志管家」——它能自动给每条日志打上请求 ID、隐藏密码/密钥等敏感信息、把超长内容自动截断、按需输出结构化 JSON 或易读文本，并支持同时写入控制台和滚动日志文件。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `observability/logging.py` | 提供一套开箱即用、安全又清晰的日志配置与工具函数，让开发者不用重复造轮子，就能拥有生产级日志能力（带上下文、脱敏、格式统一、多目标输出）。 |

## 🔍 核心函数/类说明
- **`set_request_id()` / `get_request_id()`**：作用是给当前「线程+协程」绑定一个唯一的请求 ID（比如 `"req_abc123"`），后续所有日志都能带上它。  
  - 输入：一个字符串 ID（如来自 HTTP 请求头）  
  - 输出：无（`set`）或当前 ID 字符串（`get`）  
  - 大白话解释：就像快递员送包裹时贴一张“订单号标签”，这个标签会自动粘在本次请求里产生的所有日志上，方便你从成千上万条日志中快速揪出“这单到底发生了啥”。

- **`redact_sensitive_payload()`**：作用是扫描任意数据（比如用户提交的 JSON 表单、数据库查询参数），把含密码、token、密钥等关键词的字段值替换成 `***`。  
  - 输入：任意 Python 数据（字典/列表/字符串等）+ 最大递归深度（防卡死）  
  - 输出：脱敏后的新数据（原数据不被修改）  
  - 大白话解释：就像给日志里的“身份证复印件”打码——看到 `{"password": "123456"}` 就变成 `{"password": "***"}`，既保留结构方便排查，又绝不泄露真实密码。

- **`summarize_log_value()`**：作用是把任意值（尤其是可能超长的请求体、错误堆栈）安全地转成一段「适合打印的日志字符串」，自动处理编码、JSON 序列化、脱敏、截断。  
  - 输入：任意值 + 最大长度（默认 4000 字符）  
  - 输出：一行简洁、安全、可读的字符串（如 `"payload={\"user\": \"alice\", \"token\": \"***\"}"`）  
  - 大白话解释：相当于日志界的“文字压缩器+马赛克笔”——不管丢进来的是 10MB 的图片二进制、还是嵌套 10 层的报错对象，它都能稳稳吐出一句干净利落的描述，不会崩、不漏密、不刷屏。

- **`summarize_http_context()`**：作用是把一次 HTTP 请求的关键信息（方法、路径、参数、耗时、状态码、错误等）组装成一条人眼友好、机器也易解析的“摘要日志”。  
  - 输入：一堆 HTTP 相关参数（大部分可选）  
  - 输出：一个空格分隔的字符串，如 `"method=POST path=/login query=?ref=home status=200 duration_ms=12.34 payload={\"user\":\"alice\"}"`
  - 大白话解释：就像交警写的“事故简报”——不写废话，只列关键要素，一眼看清谁（client）、干了啥（method/path）、结果如何（status/duration）、带了啥（payload）、出啥事了（error），排查问题快如闪电。

- **`_RequestContextFilter` 类**：作用是在每条日志生成前，自动塞进 `request_id`、`service`（服务名）、`app_env`（环境名）这三个“身份标签”。  
  - 大白话解释：相当于日志打印机的“自动盖章机”——每次打印前，默默在右下角盖上「工号：req_xxx」「部门：auth-service」「楼层：prod」，无需程序员手动写。

- **`_JsonFormatter` 类**：作用是把日志转成标准 JSON 字符串（带时间戳、级别、模块名、行号、异常堆栈等），方便 ELK、Datadog 等工具采集分析。  
  - 大白话解释：就像把日记本内容一键转成 Excel 表格——每行一个 JSON 对象，字段整齐，机器一扫就懂，再也不用手动 grep 拼凑信息。

- **`configure_logging()`**：作用是“一键启动日志系统”——设置日志级别、选择 JSON 或文本格式、决定是否写文件、配置文件滚动策略、给 Uvicorn 等第三方日志也统一管理。  
  - 输入：服务名称（如 `"user-service"`）  
  - 输出：无（但会让整个程序的日志行为立刻生效）  
  - 大白话解释：就像给房子装好水电总闸+智能面板——按一下，所有灯（日志源）、空调（Uvicorn）、冰箱（SQLAlchemy）都按你的规则运行，再也不用到处 `logging.basicConfig(...)`。

## 🧩 调用关系与数据流转
```
configure_logging("auth-service")  
    ↓ （初始化）  
创建 _RequestContextFilter → 绑定到所有 Handler  
创建 _JsonFormatter 或普通 Formatter → 绑定到所有 Handler  
添加 StreamHandler（控制台）和可选 RotatingFileHandler（日志文件）  
→ root logger 和 uvicorn/sqlalchemy 等 logger 全部接管  

当某处调用 logging.info("登录成功")：  
    ↓  
_RequestContextFilter.filter() 被触发 → 自动注入 record.request_id / record.service  
    ↓  
_Formatter.format() 被触发 → 构建 payload 字典 →  
    ↓  
summarize_http_context(...)（若用于 HTTP 日志） →  
    ↓  
summarize_log_value(payload) →  
    ↓  
redact_sensitive_payload(payload) → 扫描并替换敏感字段  
    ↓  
json.dumps(payload) → 输出最终日志行
```

## 💡 值得学习的写法
- **用 `contextvars.ContextVar` 实现请求级变量**：比老式 `threading.local()` 更靠谱，完美兼容 FastAPI 的异步协程（async/await），确保每个请求的 `request_id` 不会串门。
- **敏感词匹配用 `any(marker in lowered)` 而非正则**：简单、高效、不易误杀（比如 `"my_password_reset_token"` 会被完整识别，而正则容易写错边界）。
- **`summarize_log_value` 的兜底策略极周全**：先试 UTF-8 解码 bytes，失败用 `repr`；再试 JSON 序列化，失败直接 `str()`；最后强制截断——像一个经验丰富的急救员，总有一招能救活。
- **`configure_logging` 的幂等设计**：用 `_CONFIGURED_SERVICES` 集合记录已配置的服务名，防止重复调用导致 handler 叠加（否则日志会重复打印 N 遍！）。
- **环境变量解析封装成 `_env_bool()`**：把 `"1"/"true"/"yes"` 等常见真值字符串统一识别，避免每个地方都写 `os.getenv("X").lower() in ["true","1"]`。

## ⚠️ 需要注意的地方
- **`redact_sensitive_payload` 对 `set` 类型排序后转 list**：如果原始数据是 `set`，输出会变成有序列表（丢失 set 无序性），且 `sorted(..., key=str)` 可能引发 `TypeError`（如含不可比对象）。实际业务中 `set` 很少出现在 HTTP payload，但若用于内部日志，需留意。
- **`summarize_http_context` 中 `payload` 和 `error` 默认不参与日志（除非显式传入）**：新手常以为“只要调用这个函数就会自动抓请求体”，其实必须手动传 `payload=request_body`，否则日志里看不到 `payload=` 这一项。
- **`RotatingFileHandler` 的 `maxBytes` 默认 10MB，但未做磁盘空间预警**：如果日志狂打且磁盘小，可能撑爆磁盘。生产环境建议配合监控（如 Prometheus）或外部日志轮转工具（logrotate）。
- **`_JsonFormatter.formatException` 未做脱敏处理**：如果异常信息里明文包含密码（如 `ValueError: Invalid token 'abc123'`），会原样写入 JSON 的 `"exception"` 字段——需额外在捕获异常时手动清洗。
- **`configure_logging` 修改了 `root_logger` 和多个第三方 logger（如 `"uvicorn.access"`）**：如果项目其他地方也调用了 `logging.basicConfig()` 或手动 `addHandler()`，可能导致冲突或日志重复，务必确保这是全项目唯一日志入口。