# 📘 代码说明书
## 一句话概括
这是一个为前端 React 应用提供「壳页面」（Shell Page）的 FastAPI 后端服务，负责在用户访问任意页面时，自动注入登录用户信息、动态导航菜单、平台名称等通用上下文，并返回一个带 React 应用入口的 HTML 页面（类似“装修好的毛坯房”——结构固定，内容可换）。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `ui_shell_service.py` | 提供统一的 HTML 页面渲染服务：识别当前登录用户、生成带高亮/展开状态的左侧导航栏、注入 React 静态资源版本号防缓存，并把一切组装成最终返回给浏览器的 HTML 页面 |

## 🔍 核心函数/类说明
- **`_resolve_request_user(request: Request) -> dict`**：作用——从请求里“找人”，判断当前是谁在访问网站。  
  - 输入：FastAPI 的 `Request` 对象（就像快递员送来的包裹，里面装着请求头、IP、认证信息等）  
  - 输出：一个含 `"user_name"` 和 `"user_initial"` 的字典（比如 `{"user_name": "张三", "user_initial": "张"}`）  
  - 大白话解释：它像一个“门卫”，先看有没有带 JWT 令牌（Bearer Token），有就解码查用户名；没令牌就翻翻其他“暗号”（比如 `x-user-name` 或 `x-forwarded-user` 请求头）；全都没有，就默认叫“访客”，首字母是“访”。整个过程不报错、不中断，兜底很稳。

- **`_navigation(current_key: str) -> list`**：作用——生成左侧导航菜单，并智能标记“哪个菜单正在被使用”和“哪些菜单要默认展开”。  
  - 输入：当前页面的唯一标识（如 `"cases"` 表示用户正打开“用例列表”页）  
  - 输出：一个嵌套的菜单列表，每个菜单项都带 `"active"`（是否高亮）、`"open"`（是否展开）、`"children"`（子菜单）等字段  
  - 大白话解释：它不是简单列菜单，而是会“看路标”——比如你进了 `/cases/review`，它不仅把“待审核用例”标为高亮，还会让整个“用例中心”大菜单自动展开，就像你走进商场某家店，整条“美食街”的灯都为你亮起来。

- **`build_base_context(request, current_key) -> dict`**：作用——把所有页面都需要的“基础配件”打包好，作为模板渲染的原材料。  
  - 输入：请求对象 + 当前页面 key  
  - 输出：一个大字典，包含 `request`、平台名、用户姓名、首字母、导航菜单、React 资源版本号等  
  - 大白话解释：就像装修师傅准备的“标准工具箱”——无论你要装厨房还是卧室，里面永远有锤子（用户信息）、卷尺（导航结构）、油漆编号（资源版本），只等你往模板里一倒，HTML 就自动长出来。

- **`_react_asset_version() -> str`**：作用——给 React 打包后的 JS 文件加个“时间戳版号”，强制浏览器更新静态资源。  
  - 输入：无  
  - 输出：一个纯数字字符串（如 `"1715234890"`，其实是 `main.js` 文件最后修改时间的秒数）  
  - 大白话解释：浏览器爱“记性好”（缓存 JS），改了代码用户却看不到效果？这函数偷偷看一眼 `main.js` 文件是“几点写的”，把这个时间当版本号塞进 HTML 里（比如 `<script src="/static/react/assets/main.js?v=1715234890">`），浏览器一看“哇，新版！”，立刻重新下载，再也不用让用户手动 Ctrl+F5。

- **`render_template(...)`**：作用——真正把 HTML 页面“烘培”出来的终极函数。  
  - 输入：请求对象、模板文件名（如 `"base.html"`）、当前菜单 key、额外补充的数据（可选）  
  - 输出：一个 `HTMLResponse`（即浏览器能直接显示的网页）  
  - 大白话解释：它是“面包师”——先把基础配料（用户、导航、平台名等）混进面团（`build_base_context`），再按你指定的模具（`template_name`）压型，最后送进烤箱（Jinja2 模板引擎）出炉，端出一份热腾腾的 HTML 页面。

## 🧩 调用关系与数据流转
```
用户访问 /cases → FastAPI 路由调用 render_template()
                      ↓
              render_template() 
                  ├─→ build_base_context(request, "cases") 
                  │       ├─→ _resolve_request_user(request) → 返回用户信息
                  │       └─→ _navigation("cases") 
                  │               └─→ 遍历所有菜单，标记 "case_center" 为 open，"cases" 为 active
                  │       └─→ _react_asset_version() → 读取 main.js 修改时间
                  │
                  └─→ 合并额外 context（如有）
                          ↓
            Jinja2 模板引擎用这些数据渲染 base.html → 返回 HTMLResponse 给浏览器
```

## 💡 值得学习的写法
- ✅ **多层兜底的用户识别逻辑**：先试 JWT Token，失败再试常见代理头（`x-forwarded-user`），最后才用默认值——适配了开发、测试、K8s Ingress、Nginx 多种部署场景，鲁棒性极强。  
- ✅ **导航菜单的“智能激活”设计**：不用每个路由单独配置“该开哪个菜单”，而是靠 `current_key` 自动推导父子激活状态，新增页面只需加一条菜单配置，完全零耦合。  
- ✅ **用文件修改时间做前端资源版本号**：比硬编码版本号或 Git commit ID 更轻量、更自动化，且无需构建脚本参与，`main.js` 一变，版本号自动更新。  
- ✅ **`safe_next_path()` 的防御式路径校验**：防止恶意跳转（如 `//evil.com` 或 `javascript:`），默认跳转到 `/ai-generation`，安全又友好。

## ⚠️ 需要注意的地方
- ⚠️ `_resolve_request_user()` 中对 `decode_access_token()` 的异常捕获仅用了 `except HTTPException`，但 JWT 解析可能抛出其他异常（如 `JWTError`, `ValueError`），若未被捕获会导致 500 错误——建议改为 `except Exception` 或明确补全常见异常类型。  
- ⚠️ `_navigation()` 中 `always_open_keys` 是硬编码集合，如果未来新增顶级菜单（如 `"monitoring"`），但忘了加进这个集合，它的子菜单点击后不会保持展开——建议从 `nav_items` 中自动提取所有含 `children` 的 `key`，避免遗漏。  
- ⚠️ `STATIC_REACT_DIR / "assets" / "main.js"` 路径假设 React 打包后一定生成 `main.js` 且放在 `assets/` 下，若项目配置了 Webpack/Vite 的 `output.filename` 或 `assetsDir` 改变，这里会静默失败（返回 `"dev"`），导致缓存失效——建议增加日志或 fallback 提示。  
- ⚠️ `render_template()` 的 `context` 参数是 `dict | None`，但若传入非字典类型（如 `None` 以外的 `str` 或 `list`），`.update()` 会直接报错——建议加类型检查或 `context = context or {}` 安全初始化。