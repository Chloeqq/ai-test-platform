# 错误返回规范

这份文档定义平台错误在 API 层和前端侧的稳定返回方式。

## 1. 当前返回形态

### FastAPI 层

- 常规 `HTTPException` 返回 `{"detail": ...}`
- 校验失败返回 `{"detail": [...]}` 或结构化 detail
- 未处理异常返回 `{"detail": "Internal Server Error", "request_id": "..."}`

### Orchestrator 层

- 返回 `{"error": {"code": "...", "message": "...", "details": ...}}`
- 404、401、500 都使用统一 error 包装

## 2. 常见状态码

- `400`：请求参数不合法
- `401`：未授权或 token 无效
- `404`：资源不存在
- `422`：结构化校验失败或映射失败
- `500`：未处理错误
- `502`：下游服务失败或响应不合法
- `504`：下游超时

## 3. 推荐前端展示

- `detail` 是面向用户的核心提示
- `code` 用于分流和诊断
- `request_id` 用于日志追踪
- 不要把 502 当成业务校验失败

## 4. 生成链路常见错误

- `page must not be empty`
- `missing explicit steps_hint`
- `input step requires explicit target`
- `orchestrator request timed out`
- `requirement parser failed`

## 5. 与 Dify 的关系

- Dify 工作流失败也要返回可诊断的错误结构
- LLM 节点输出不合法应直接失败，不要包装成成功结果
- 检索失败、映射失败、结构校验失败要分开报错

