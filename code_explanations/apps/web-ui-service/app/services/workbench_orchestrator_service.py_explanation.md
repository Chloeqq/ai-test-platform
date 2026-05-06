# 📘 代码说明书
## 一句话概括
这是一个专门负责「安全、可靠地给后台工作台编排服务（orchestrator）发 JSON 请求」的工具函数，就像一个细心又靠谱的快递员：它打包好货（JSON 数据）、填好单子（带请求 ID 和密钥）、准时出发（带超时控制），全程录像（详细日志），遇到丢件、拒收、地址错误等任何问题都会立刻打电话反馈（抛出带状态码的异常），而不是默默吞掉错误。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `workbench_orchestrator_service.py` | 提供统一的 HTTP POST 请求封装，专用于与「工作台任务编排服务」通信，兼顾日志追踪、错误分类、超时防护和 API 密钥自动注入。 |

## 🔍 核心函数/类说明
- **`def post_json()`**：作用是向指定 URL 发送一个 JSON 格式的 POST 请求，并确保整个过程可监控、可诊断、可恢复。
  - 输入：
    - `url`: 要发给谁？（比如 `https://orchestrator.internal/run-task`）
    - `payload`: 要送什么货？（一个 Python 字典，比如 `{"task": "export", "user_id": 123}`）
    - `timeout_seconds`: 最多等多久？（默认 5 分钟，避免卡死）
    - `http_exception_cls`: 如果出错了，想抛出什么类型的错误？（比如 FastAPI 的 `HTTPException`，方便前端直接显示）
  - 输出：从对方服务器返回的 JSON 解析后的 Python 字典（比如 `{"status": "queued", "job_id": "abc123"}`）
  - 大白话解释：它不是简单调用 `requests.post()`，而是像一位经验丰富的“接口管家”——  
    ✅ 自动加上请求 ID（方便查哪次请求出了问题）  
    ✅ 自动带上 API 密钥（不用每个地方都手动写）  
    ✅ 记录完整请求/响应日志（开始时间、耗时、状态码、错误原因）  
    ✅ 把不同网络错误“翻译”成清晰的 HTTP 错误（502 表示对方挂了，504 表示等太久了）  
    ✅ 还会检查对方回的到底是不是合法 JSON，是不是字典格式，防止解析崩溃或逻辑错乱  

## 🧩 调用关系与数据流转
```
外部业务代码（比如某个 FastAPI 接口）  
     ↓ 调用 post_json(url="...", payload={...})  
     → 自动读取配置（API 密钥、超时设置） + 生成请求 ID  
     → 打包 JSON → 构造带 header 的 urllib.Request  
     ↓ 发送请求（urlopen）  
         ├─ ✅ 成功 → 读响应 → 解析 JSON → 检查是否为 dict → 返回 data  
         ├─ ❌ HTTP 错误（4xx/5xx）→ 读错误体 → 尝试提取 error 字段 → 抛出定制 HTTPException  
         ├─ ❌ 网络不可达（URLError）→ 抛出 502（Bad Gateway）  
         ├─ ❌ 超时（TimeoutError / socket.timeout）→ 抛出 504（Gateway Timeout）  
         └─ ❌ 返回内容不是 JSON 或不是字典 → 抛出 502（Bad Gateway）  
     ↓ 所有异常都会被记录日志，并带上 request_id 和耗时，方便运维定位  
```

## 💡 值得学习的写法
- **日志上下文统一化**：用 `summarize_http_context()` 一次性生成结构化日志片段，所有日志行（成功/失败/超时）都保持相同字段（method/path/request_id/status_code/duration_ms/error），极大提升日志检索和监控告警效率。
- **错误体智能解析**：收到 HTTP 错误时，不直接把原始 HTML 或乱码当错误信息，而是先尝试 `json.loads()` 提取 `"error"` 字段，失败了才退回到字符串描述——让报错对开发者更友好。
- **密钥注入零侵入**：通过 `**({"X-Api-Key": ...} if ... else {})` 动态拼接 headers，既支持密钥存在时自动添加，也完全兼容密钥为空的测试/本地环境，无需 if-else 分支。
- **超时双保险**：同时捕获 `TimeoutError`（高层超时）和 `socket.timeout`（底层套接字超时），覆盖 urllib 不同层级的超时异常，避免漏处理。

## ⚠️ 需要注意的地方
- **别直接传敏感数据进 payload**：这个函数会把整个 `payload` 打印到 INFO 日志里（`summarize_http_context(..., payload=payload)`），如果 payload 含密码、token、用户隐私字段，会直接泄露！必须在调用前脱敏（比如删掉 `"password"` 字段）或改用更安全的日志策略。
- **`http_exception_cls` 必须接受 `status_code` 和 `detail` 参数**：如果你传入自定义异常类（比如 `MyCustomError`），它必须能用 `MyCustomError(status_code=504, detail="...")` 初始化，否则会报错。FastAPI 的 `HTTPException` 是符合的，但普通 `Exception` 不行（所以默认值其实是“危险”的，生产建议显式传 `HTTPException`）。
- **`urllib` 不自动重试**：它只发一次，失败就报错。如果业务需要“对方临时抖动，重试 2 次就好”，这个函数不提供，需在外层包装重试逻辑。
- **JSON 编码用 `ensure_ascii=False`**：支持中文等 Unicode 字符，但要注意接收方是否能正确解码 UTF-8；若对接老系统可能需确认兼容性。