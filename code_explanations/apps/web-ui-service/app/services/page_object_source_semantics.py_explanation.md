# 📘 代码说明书
## 一句话概括
这是一个为前端页面元素（如按钮、输入框、表格列等）自动“起有意义名字”的智能助手——它扫描项目源码文件（Vue/React/HTML等），从代码文本中提取语义线索（比如`label="用户名"`、`placeholder="请输入邮箱"`），结合业务场景（登录页？表格页？导航栏？）和命名规范，生成标准化、可读性强的业务语义代码标识（如`username_input`、`user_list_column`），用于后续自动化测试或低代码平台的元素识别。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `page_object_source_semantics.py` | 从真实前端源码中“读懂”页面元素的业务含义，并为它们生成统一、可复用的语义化代码名称（如`login_button`、`search_input`），充当“页面语义词典”的构建器 |

## 🔍 核心函数/类说明
- **`build_source_semantic_catalog()`**：整个文件的“总开关”，负责一键生成一份完整的页面语义词典。
  - 输入：当前页面代号（如`"user-management"`）、路由路径（如`"/users"`）、项目名（用于查配置）、可选的源码路径列表、可选的业务术语映射表（如`{"搜索": "search"}`）
  - 输出：一个 `SourceSemanticCatalog` 实例（就像一本查字典用的“语义词典”）
  - 大白话解释：你告诉它“我现在在用户管理页，路径是 `/users`，属于 `admin-proj` 项目”，它就去项目里翻 Vue/TSX 文件，找到所有带 `label="新增"`、`placeholder="邮箱"`、`<el-table-column label="姓名">` 这类文字的地方，再结合上下文（比如这个页面是不是登录页？有没有 router 配置？），给每个元素起一个既准确又统一的名字（比如 `"add_button"`、`"email_input"`、`"name_column"`），最后把所有名字打包成一本可随时查询的“词典”。

- **`_extract_hints_from_content()`**：文件里的“阅读理解专家”，专门负责从一段前端源码字符串中“抠出”所有能起名的线索。
  - 输入：源码文本（如一个 `.vue` 文件的内容）、当前页面代号、文件路径名、业务术语映射表
  - 输出：一个字典，key 是归一化后的文本（如 `"用户名"` → `"yonghuzhanghao"`），value 是一组可能的语义提示（`SourceSemanticHint`），每个提示包含：建议的名字（`code_seed`）、中文描述（`name`）、业务类型（`input`/`button`/`column`）、业务领域（`auth`/`table`/`navigation`）、来源文件、优先级
  - 大白话解释：它像一个细心的编辑，逐行扫描代码，看到 `<el-form-item label="用户名">` 就记下“这是个输入框，叫`username_input`，属于登录/用户模块，优先级高”；看到 `placeholder="搜索关键词"` 就记下“这是个搜索输入框，叫`search_keyword_input`”；看到 `path: "/users", meta: {title: "用户列表"}` 就记下“这个路由对应菜单项`user_list_menu`”。它不只看表面文字，还会结合标签属性（`prop`）、上下文（是否含 `show-password`）、甚至文件路径来判断更准的名字。

- **`SourceSemanticCatalog` 类**：生成的“语义词典”本身，提供两种查词方式。
  - 输入（`match` 方法）：定位方式（如 `"text"` 文本匹配、`"placeholder"` 占位符匹配）+ 具体值（如 `"提交"`）+ 可选角色（如 `"button"`）
  - 输出：最匹配的一个 `SourceSemanticHint`（即最合适的语义化名字和描述）
  - 大白话解释：这本词典不是简单地“找相同文字”，而是智能匹配。比如你问：“在页面上找文字是‘提交’的按钮”，它会翻词典，发现有 `{"tijiao": [SourceSemanticHint(code_seed="submit_button", ...), ...]}`，再根据规则（按钮匹配按钮得分高、优先级高）挑出最优解——相当于词典自带“模糊搜索+权重排序”功能。

- **`_business_domain()`**：给元素打上“业务标签”的小判官。
  - 输入：页面代号 + 元素文本（如 `"login"` + `"密码"`）
  - 输出：一个业务领域字符串（如 `"auth"`）
  - 大白话解释：它像给商品贴分类标签。看到“登录”、“密码”、“账号”就贴“认证（auth）”标签；看到“菜单”、“导航”就贴“导航（navigation）”；看到“表格”、“列”就贴“表格（table）”。这样同一个名字 `save_button` 在登录页叫 `login_save_button`，在用户页叫 `user_save_button`，避免混淆。

- **`_button_code_seed()` / `_snake()` 等工具函数**：一群“文字美容师”，负责把原始文本变成规范的代码名。
  - 输入：原始文本（如 `"重置密码"`）
  - 输出：蛇形命名（snake_case）的代码种子（如 `"reset_password_button"`）
  - 大白话解释：它们把中文、驼峰名、带空格的句子，统统变成程序员最爱的 `lowercase_with_underscores` 格式，并自动补上业务后缀（`_button`, `_input`），确保生成的名字既可读又合法（比如不会出现 `my-button` 这种非法变量名）。

## 🧩 调用关系与数据流转
```
build_source_semantic_catalog()  ←（用户调用入口）
    ↓ 读取环境变量/项目配置 → _source_roots() + _normalize_semantic_terms()
    ↓ 扫描文件 → _iter_source_files()
    ↓ 计算文件相关性得分 → _file_score() （结合 page_code、route、路径名）
    ↓ 按得分排序，只处理前30个最相关的文件
        ↓ 对每个高分文件：
            path.read_text() → 得到 content 字符串
            ↓ 传给 → _extract_hints_from_content()
                ↓ 内部调用一堆“提取器”：
                    re.finditer(...) for <el-form-item> → _add_hint() → 生成 input 提示
                    re.finditer(...) for <el-button> → _button_code_seed() → _add_hint() → 生成 button 提示
                    re.finditer(...) for <el-table-column> → _add_hint() → 生成 column 提示
                    _extract_router_title_blocks() → _add_hint() → 生成 menu 提示
                    ...（其他提取器）
                ↓ 所有提示汇总到 hints 字典
    ↓ 将所有 hints 交给 → SourceSemanticCatalog.__init__()
    ↓ 用 cache_key 查缓存 → 若命中直接返回；否则存入 _SOURCE_CATALOG_CACHE
    ↓ 返回最终的 SourceSemanticCatalog 实例

→ 后续使用时，调用 catalog.match(locator_type="text", locator_value="保存") 
    ↓ 触发 _contextual_hint_score() 计算每个候选提示的综合得分（优先级 + 类型匹配奖励）
    ↓ 返回最高分的 SourceSemanticHint
```

## 💡 值得学习的写法
- **缓存设计精巧**：用 `SourceCatalogCacheKey` 元组（含项目、页面、路径、术语、文件数、最新修改时间戳）作为缓存键，确保只要源码没变、配置没变，就绝对复用结果，避免重复扫描千个文件——就像“菜谱缓存”，改了食材才重做，否则直接端上热菜。
- **正则提取+语义增强双保险**：不只靠硬编码的标签名（如 `<el-button>`），还用 `_source_business_code_from_text()` 从自定义术语表（`PAGE_OBJECT_SOURCE_TERMS_JSON`）中查映射（如 `"搜索"` → `"search"`），让团队能用自己习惯的中文词驱动标准命名，兼顾灵活性与规范性。
- **分数制动态排序**：`_file_score()` 和 `_contextual_hint_score()` 用加权打分替代硬逻辑，让“哪个文件更相关”“哪个提示更靠谱”变成可量化、可调试的数学问题，而不是一堆 if-else 堆砌。
- **防御式编程无处不在**：所有文件读取、JSON 解析、正则匹配、路径解析都包裹 `try/except` 或空值检查（`str(value or "")`），确保哪怕某一行代码写错了、某个文件打不开、某个 JSON 格式乱了，整个系统依然健壮运行，只是跳过那个“坏零件”。

## ⚠️ 需要注意的地方
- **环境变量敏感，本地调试易失败**：`SOURCE_ROOTS_ENV`、`PAGE_OBJECT_SOURCE_TERMS_JSON` 等全靠环境变量注入，如果本地 `.env` 文件漏配或格式错误（比如 JSON 少了个逗号），`_source_roots()` 会返回空列表，`build_source_semantic_catalog()` 直接返回空词典——调试时第一反应应是 `print(os.getenv("PAGE_OBJECT_SOURCE_TERMS_JSON"))` 看是否读到了。
- **正则表达式脆弱，前端框架升级可能失效**：所有 `re.finditer(...)` 都强依赖 Element Plus 的标签写法（如 `<el-form-item label="...">`）。如果团队升级到 Ant Design Vue 或改用纯 HTML，这些正则会全部失灵，需同步更新提取逻辑——就像“按书名找章节”，换了一套教材，目录规则就得重写。
- **缓存键未包含 Python 版本或依赖版本**：`cache_key` 里没放 `suggest_business_element_code` 函数的版本信息。如果该函数内部逻辑升级（比如新支持了 AI 生成），但缓存键不变，旧缓存仍会被复用，导致语义名“过期”——建议未来在 key 中加入 `hashlib.md5(inspect.getsource(suggest_business_element_code).encode()).hexdigest()`。
- **大文件/深目录易触发性能瓶颈**：`_iter_source_files()` 用 `rglob("*")` 遍历所有子目录，若 `node_modules` 未被正确过滤（比如路径名含 `node_modules` 但大小写不符），或 `MAX_FILE_BYTES=512KB` 设得过大，可能卡死或 OOM——上线前务必用真实项目跑一遍 `time python -c "from page_object_source_semantics import _iter_source_files; print(len(_iter_source_files([Path('.')])))"` 测量。