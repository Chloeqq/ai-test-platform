# 📘 代码说明书
## 一句话概括
这个文件是“工作台生成 API”的**指挥官工厂**——它负责根据当前系统配置（比如 orchestrator 的地址、超时时间），现场组装出一个功能齐全的“指挥官”（`OrchestratorClient`），专门用来和后端的“工作流协调服务”（orchestrator）打交道，比如解析需求、生成方案等。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `workbench_generation_api/orchestrator_client_factory.py` | 创建并配置一个可直接调用的 `OrchestratorClient` 实例，把环境配置、网络请求逻辑、辅助工具都打包好，让其他模块“开箱即用”，不用重复写 URL 拼接、超时设置、参数整理这些琐事。 |

## 🔍 核心函数/类说明
- **`_post_json(url, payload, *, timeout_seconds)`**：一个“快递员封装函数”，专门负责把数据（`payload`）打包成 JSON，发给指定网址（`url`），并设定送货时限（`timeout_seconds`）；如果送货失败（比如对方服务器没响应或挂了），就自动换成用户友好的错误提示（502 或 504 错误）。
  - 输入：目标网址 `url`、要发送的数据字典 `payload`、超时秒数 `timeout_seconds`
  - 输出：服务器返回的 JSON 字典（成功时），或抛出 `HTTPException` 异常（失败时）
  - 大白话解释：就像你叫外卖前，APP 帮你自动填好餐厅地址、菜品清单、还设好“10 分钟没接单就提醒你”，而不是每次都要手动输一遍——这里就是把重复的“发请求+管超时+报错美化”这件事自动化了。

- **`build_orchestrator_client()`**：真正的“指挥官组装流水线”，它读取项目配置（比如 orchestrator 地址在哪、最多等几秒），然后现场造出两个核心动作函数（`_run_parse` 和 `_run_generate`），再把它们和几个现成的工具函数一起塞进 `OrchestratorClient` 这个“万能遥控器”里，最后把遥控器交给你。
  - 输入：无显式参数（但内部会读取全局配置 `get_settings()`）
  - 输出：一个配置好的 `OrchestratorClient` 实例
  - 大白话解释：就像你买扫地机器人，盒子里面不只有一台机器，还有已配好的 APP（`_run_parse` / `_run_generate`）、已绑定的 Wi-Fi（`settings.orchestrator_url`）、已设好的清洁时长（`timeout_seconds`），以及附赠的“脏污检测卡”（`_extract_quality_gate`）和“禁区识别贴纸”（`_is_quality_gate_blocked`）——全是一体化交付，拆开就能用。

## 🧩 调用关系与数据流转
```
build_orchestrator_client() 
│
├─→ 读取配置 get_settings() → 得到 orchestrator_url、timeout_seconds 等
│
├─→ 定义 _run_parse(**kwargs)：
│     │
│     ├─→ 拼接 URL：orchestrator_url + "/requirements/parse"
│     ├─→ 从 kwargs 中智能提取参数（如 requirement、prd_text、git_diff…），过滤空值，转成字符串再去除首尾空格
│     └─→ 调用 _post_json(拼接后的URL, 整理好的payload, timeout_seconds) → 返回解析结果
│
├─→ 定义 _run_generate(**kwargs)：
│     │
│     ├─→ 拼接 URL：orchestrator_url + "/orchestrate"
│     ├─→ 同样智能整理参数，并固定加入 "mode": "generate_only", "execute": False
│     └─→ 调用 _post_json(...) → 返回生成结果
│
└─→ 将 _run_parse、_run_generate、以及三个共享工具函数（_extract_quality_gate 等）一起传入 OrchestratorClient 构造函数
     ↓
     返回一个 ready-to-use 的 OrchestratorClient 实例
```

## 💡 值得学习的写法
- ✅ **参数“懒收集”设计**：`_run_parse` 和 `_run_generate` 都用 `**kwargs` 接收任意参数，再按需从中取值（如 `kwargs.get("prd_text", "")`），既灵活又健壮——新增一种输入源（比如加个 `"error_screenshot"`）只需在调用方传进去，这里完全不用改代码。
- ✅ **URL 拼接防双斜杠**：`settings.orchestrator_url.rstrip('/')` 主动去掉末尾 `/`，再手动加 `/requirements/parse`，彻底避免 `https://api.com//requirements/parse` 这种无效地址，小细节很稳。
- ✅ **空值统一清洗**：对所有文本类字段（如 `prd_text`, `git_diff`）都做 `str(... or "").strip()`，确保传给后端的永远是干净字符串，不会因 `None` 或纯空格导致解析失败。
- ✅ **职责清晰分层**：网络请求（`_post_json`）、业务逻辑（`_run_parse`/`_run_generate`）、配置管理（`get_settings`）、工具能力（`_extract_quality_gate`）完全解耦，每个函数只干一件事，改起来不牵一发而动全身。

## ⚠️ 需要注意的地方
- ⚠️ **`openapi_spec` 类型检查太窄**：代码中判断 `isinstance(kwargs.get("openapi_spec"), dict) and kwargs.get("openapi_spec")` 才传它，但如果 `openapi_spec` 是 `str`（比如 YAML 字符串）或 `bytes`，就会被悄悄忽略——实际使用中可能需要支持更多格式，否则前端传了 OpenAPI 文本却没生效，排查会很懵。
- ⚠️ **`timeout_seconds` 全局复用风险**：目前 parse 和 generate 都用同一个 `settings.orchestrator_timeout_seconds`，但解析需求通常很快（毫秒级），生成方案可能很慢（几十秒）。若超时设得太短，生成容易失败；设得太长，解析又显得卡顿。理想情况应允许为不同操作单独配置超时。
- ⚠️ **`_run_generate` 固定 mode 和 execute 可能僵化**：现在硬编码了 `"mode": "generate_only"` 和 `"execute": False`，未来如果想支持“生成+立即执行”，就得改这里——建议考虑把这类策略参数也从 `**kwargs` 中动态读取（比如 `kwargs.get("mode", "generate_only")`），提升扩展性。
- ⚠️ **缺少输入校验日志**：当某个字段（如 `requirement`）为空时，函数照常发请求，但后端可能直接报错。建议在发请求前加简单日志（如 `logger.debug("Calling parse with requirement=%r", requirement)`），方便快速定位“谁传了个空需求”。