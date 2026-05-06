# 📘 代码说明书
## 一句话概括  
这是一个“项目配置管家”，负责从环境变量、默认值和业务规则中，智能组装出整个应用运行所需的所有配置（比如数据库地址、登录网址、权限规则等），确保不同环境（开发/测试/生产）能自动用上合适的设置。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `config.py` | 应用的“中央配置中心”：统一读取环境变量、做逻辑判断、提供安全合理的默认值，并封装成结构化对象供其他模块使用 |

## 🔍 核心函数/类说明
- **`_env_bool(name: str, default: bool) -> bool`**：把环境变量字符串（如 `"1"`、`"true"`、`"YES"`）**智能转成 `True`/`False`**  
  - 输入：环境变量名（如 `"REDIS_ENABLED"`）和默认布尔值  
  - 输出：解析后的 `True` 或 `False`  
  - 大白话解释：就像一个“翻译官”，把人写的各种写法（`"on"`、`"1"`、`"yes"`）都统一翻译成程序能懂的开关状态，避免因大小写或拼写差异导致配置失效。

- **`_resolve_evidence_manifest_policy() -> str`**：决定“证据清单策略”该用哪种模式（严格/兼容/自动）  
  - 输入：无（只读取环境变量 `"EVIDENCE_MANIFEST_POLICY"`）  
  - 输出：`"strict"` / `"compat"` / `"auto"` 中的一个字符串  
  - 大白话解释：就像给安检定规则——是“必须查身份证+护照”（strict）、还是“身份证或护照任一即可”（compat）、还是“先看当前环境再决定”（auto）。

- **`_default_evidence_manifest_compat_scan_enabled() -> bool`**：决定“是否开启兼容模式扫描”  
  - 输入：无（内部调用 `_resolve_evidence_manifest_policy()` 和 `_current_app_env()`）  
  - 输出：`True` 或 `False`  
  - 大白话解释：它不是直接读环境变量，而是“动脑筋”做决策——比如在生产环境（`prod`）自动关掉兼容扫描（更安全），在本地开发环境（`dev`）则默认打开（更方便调试）。

- **`_parse_csv(raw: str) -> list[str]`**：把逗号分隔的字符串（如 `"admin,qa-lead,release-manager"`）**拆成干净的角色列表**  
  - 输入：原始字符串（可能带空格、空项）  
  - 输出：去空格、去空项、小写的字符串列表，如 `["admin", "qa-lead", "release-manager"]`  
  - 大白话解释：像用厨房滤网过滤豆子——把乱七八糟的输入（多余空格、空行、大小写混杂）全筛掉，只留下干净可用的角色名。

- **`_default_page_surface_allowed_hosts() -> list[str]`**：生成“允许访问登录页的网站名单”  
  - 输入：无（读取 `PAGE_SURFACE_ALLOWED_HOSTS` 环境变量 + `BASE_URL` + 当前环境）  
  - 输出：去重、小写、包含 `localhost`/`127.0.0.1`（开发时）或线上域名（生产时）的主机名列表  
  - 大白话解释：就像小区门禁系统——自动把你的开发电脑（`localhost`）加进白名单；如果填了 `BASE_URL=https://myapp.com`，就顺手把 `myapp.com` 加进去；你还能手动追加其他域名（比如测试用的 `staging.myapp.com`）。

- **`Settings(BaseModel)`**：所有配置的“结构化存钱罐”  
  - 输入：无（但每个字段背后都连着一个 `default_factory` 函数）  
  - 输出：一个带类型提示、可校验、可序列化的配置对象（比如 `settings.database_url` 就是字符串，`settings.jwt_expire_minutes` 就是整数）  
  - 大白话解释：不是一堆零散变量，而是一个“带标签的收纳盒”——每样东西（数据库地址、JWT过期时间…）都有固定位置、固定类型、固定默认值，拿起来就能用，还不怕填错（Pydantic 会自动检查）。

- **`get_settings() -> Settings`**：获取配置的“唯一入口”  
  - 输入：无  
  - 输出：一个 `Settings` 实例  
  - 大白话解释：就像酒店前台——你只管说“我要房间信息”，它永远只给你同一份最新、最准、已缓存好的配置（`@lru_cache` 保证只算一次，又快又省）。

## 🧩 调用关系与数据流转  
```
get_settings() 
    ↓（调用 Settings 构造函数）
Settings.__init__()
    ↓（每个字段按需调用 default_factory）
    ├─ _default_orchestrator_api_key() → orchestrator_api_key 字段  
    ├─ _resolve_evidence_manifest_policy() → evidence_manifest_policy 字段  
    ├─ _default_evidence_manifest_compat_scan_enabled() → evidence_manifest_compat_scan_enabled 字段  
    ├─ _default_base_url() → page_surface_login_url 字段  
    ├─ _default_page_surface_allowed_hosts() → page_surface_allowed_hosts 字段  
    │      ↓（内部调用）
    │      ├─ _parse_csv() → 解析环境变量  
    │      └─ _default_base_url() → 提取 BASE_URL 的域名  
    ├─ _default_execution_gate_decision_roles() → execution_gate_decision_privileged_roles 字段  
    │      ↓（内部调用）
    │      └─ _parse_csv() → 解析角色列表  
    └─ ...（其他字段同理）
```
✅ 数据流向本质是：**环境变量 → 辅助函数（清洗/判断）→ Settings 字段 → get_settings() 统一出口**

## 💡 值得学习的写法  
- **环境变量 + 智能默认值双保险**：不盲目信任环境变量（比如 `APP_ENV` 缺失时默认 `dev`），也不硬编码死值，而是结合业务规则（如 `STRICT_EVIDENCE_POLICY_ENVS` 集合）动态推导，既灵活又安全。  
- **`@lru_cache(maxsize=1)` 用得恰到好处**：配置一旦加载就永不变化，缓存一次永久复用，避免重复解析、重复计算，性能零损耗。  
- **字段级 `default_factory` 而非全局默认值**：每个配置项独立决策（比如 `page_surface_allowed_hosts` 会根据 `BASE_URL` 和 `APP_ENV` 自动加域名+本地地址），而不是所有环境共用一个静态列表，真正实现“一环境一策”。  
- **`_parse_csv` 统一处理 CSV 字符串**：所有需要逗号分隔列表的地方（角色、主机名等）都复用这个函数，避免到处写 `split(",")` + `strip()` + `filter(None)`，代码整洁且不易出错。

## ⚠️ 需要注意的地方  
- **`DEFAULT_DB_PATH` 是相对路径，依赖项目结构**：它向上找两级（`parents[2]`）才到 `dev.db`，如果项目目录结构变了（比如把 `config.py` 移到更深的子包），数据库路径就会错——建议在部署文档里明确要求项目根目录结构。  
- **`_default_base_url()` 的 fallback 逻辑有隐藏依赖**：当 `BASE_URL` 为空且 `APP_ENV` 是 `dev` 时，它返回 `"http://localhost:5173/login#/login"` —— 这个地址明显是为前端 Vite 开发服务器（端口 5173）定制的，如果前端换框架或改端口，这里会静默失效，需同步更新。  
- **`_current_app_env()` 被多个函数反复调用，但没缓存**：虽然 `get_settings()` 整体被缓存，但 `_current_app_env()` 在 `_default_evidence_manifest_compat_scan_enabled()`、`_default_page_surface_allowed_hosts()` 等函数里各自调用了一次 `os.getenv()`，虽影响极小，但统一用 `@lru_cache` 包一层更严谨。  
- **`_default_page_surface_allowed_hosts()` 的 dedup 逻辑有陷阱**：它先加域名、再加 `localhost`、最后加用户配置，但 dedup 是按字符串全匹配（`"localhost"` 和 `"LOCALHOST"` 视为不同）。虽然代码里强制 `.lower()`，但如果用户配置里写了 `"LOCALHOST"`，dedup 仍会保留两个——建议在 `deduped` 前统一转小写再去重（当前代码已做，但容易忽略这个细节）。