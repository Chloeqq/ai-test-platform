# 📘 代码说明书
## 一句话概括
这是一个「测试用例质检员」：专门检查和补全测试用例（case）的标题、描述、ID、状态等字段是否规范、完整、符合中文习惯和平台字典要求。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `case_rules.py` | 提供测试用例的校验规则（如标题不能全是英文短横线）、自动补全逻辑（如从 case_id 解析出页面/模块信息并填入对应名称），是整个测试用例数据质量的“守门人”。 |

## 🔍 核心函数/类说明
- **`validate_case_title(title: str) -> list[str]`**：检查测试用例标题是否合格  
  - 输入：一个字符串（比如 `"login-page-user-login-success"` 或 `"用户登录成功"`）  
  - 输出：错误提示列表（空列表表示通过）  
  - 大白话解释：就像老师批改作文标题——它会揪出：① 空标题 ❌；② 超过100字太啰嗦 ❌；③ 全是英文短横线拼接（像 `login-user-success`）❌，因为这不是人话；④ 没有中文（纯英文或数字）❌；⑤ 混进了明显英文单词（如 `user`, `login`）❌；⑥ 分段太少（要求至少4段语义，比如“登录页-用户模块-输入正确账号-点击登录-显示欢迎页”才算合格）❌。  

- **`validate_case_description(description: str) -> list[str]`**：检查测试用例描述是否合格  
  - 输入：一个字符串（比如 `"验证用户能正常登录"`）  
  - 输出：错误提示列表（空列表表示通过）  
  - 大白话解释：只做一件事——确保描述里有中文（哪怕一个字），不接受纯英文或空内容。简单粗暴，但很实用。  

- **`validate_case_payload(payload: dict) -> list[str]`**：对整条测试用例数据做“全身体检”  
  - 输入：一个字典（比如 `{ "id": "P1-M2-T3-S4-IMP", "title": "用户登录", ... }`）  
  - 输出：所有发现的错误提示列表（一条或多条）  
  - 大白话解释：它先揪出最致命的 `case_id` 是否合法（用正则匹配 + 规范化），再检查每个字段（page_code、module_code…）是否在平台“词典”里存在（比如 `P1` 必须对应“登录页”，否则报错），最后顺手调用上面两个函数检查标题和描述。相当于一个严谨的质检流水线。  

- **`enrich_case_metadata(payload: dict) -> dict`**：给测试用例“自动贴标签、补名字”  
  - 输入：原始用例数据（可能缺很多字段）  
  - 输出：补全后的字典（新增了 `page_name`, `module_name`, `status_name`, `created_by` 等易读字段）  
  - 大白话解释：就像快递单上只有单号 `P1-M2-T3-S4-IMP`，它能自动查出这是“登录页-用户模块-功能测试-IMP来源”，再把“登录页”“用户模块”这些中文名填进去；还能根据来源（`ai`/`cv`/`fb`）自动标记创建者是“AI”，其他情况默认“HUMAN”。让机器生成的数据也有人味儿。  

- **`CaseRuleViolation(ValueError)`**：自定义错误类型  
  - 输入：无（它是异常类，用来抛错）  
  - 输出：无（抛出时中断流程）  
  - 大白话解释：不是普通报错，而是“规则被违反了”的专用警报，方便上层（比如 FastAPI 接口）统一捕获并返回友好的错误提示，而不是一堆看不懂的 Python traceback。

## 🧩 调用关系与数据流转
```
FastAPI 接口（或其他入口） 
    ↓ 接收用户提交的用例数据（payload）
    → validate_case_payload() 开始质检：
        ├─ 先调用 normalize_case_id() 和 match_case_id() 解析 ID 结构
        ├─ 再逐个检查 page_code / module_code / status 等字段是否在字典中
        └─ 最后调用 validate_case_title() 和 validate_case_description()
    
    ↓ 如果质检通过（errors 为空），可进入下一步：
    → enrich_case_metadata() 补全数据：
        ├─ 再次解析 case_id 得到 project/client/page/module 等信息
        ├─ 调用 build_case_metadata() 生成基础元数据（含中文名）
        ├─ 合并用户输入 + 字典映射 + 默认值 → 填满所有 name 字段（page_name, module_name...）
        └─ 自动推断 created_by / change_source / ai_status 等智能字段
    ↓ 返回补全后的 payload，供后续保存或展示
```

## 💡 值得学习的写法
- **字典预加载 + 静态缓存**：`PAGE_CODE_DICT`、`CASE_STATUS_DICT` 等在文件顶部就一次性生成好，避免每次调用都重复查字典，既快又省资源（类似“提前把菜谱打印出来，不用每次做饭都上网搜”）。  
- **正则分层防御**：用 `_TITLE_CODELIKE_RE` 专抓“假标题”（如 `p1-m2-t3`），用 `_CJK_RE` 和 `_ASCII_WORD_RE` 分别检测中文/英文单词，分工明确，不易漏判。  
- **fallback 机制无处不在**：比如 `get_case_status_name(code, fallback="未知状态")`、`resolve_dictionary_name(..., fallback=code)`、甚至 `normalize_case_status(..., fallback="ready")` —— 所有关键字段都有“保底方案”，系统不会因一个字段异常就崩溃。  
- **“智能默认”逻辑自然嵌入**：`created_by` 不是硬编码，而是根据 `source` 字段动态判断（`ai`/`cv`/`fb` → `"AI"`，其余 → `"HUMAN"`），让规则既有约束力又有灵活性。  
- **函数职责极度单一**：`validate_case_title` 只管标题，`validate_case_description` 只管描述，`enrich_*` 只管补全——改一个功能，几乎不影响其他，维护成本低。

## ⚠️ 需要注意的地方
- **`_text()` 函数的“静默容错”可能掩盖问题**：它把 `None`/`0`/`False` 都转成空字符串 `""`，比如 `raw.get("id")` 是 `0`，会被当成空 ID 报错。如果业务中 ID 允许为数字 0，这里就会误判。  
- **`match.group("xxx")` 依赖正则命名分组，但 `match_case_id()` 没贴出来**：如果那个函数没正确返回带 `page`/`module` 等命名分组的 Match 对象，`enrich_case_metadata()` 会直接抛 `AttributeError`，且错误堆栈不友好（看不出是哪行 regex 没配对）。  
- **中文检测仅靠 Unicode 范围 `[\u4e00-\u9fff]`**：不覆盖繁体字（如「繁」）、日韩文、中文标点（如「，」），严格场景下可能漏判；若未来支持港澳台用语，需扩展范围。  
- **`segments = value.split("-")` 拆分标题时未考虑中文顿号、逗号、空格等分隔符**：当前强制要求用英文短横线 `-` 分段，但真实业务中用户可能写 `"登录页｜用户模块｜输入账号"`，这种会被当“1段”直接报错，体验不友好。  
- **`enrich_case_metadata()` 中多次 `.lower()` + 字典 `.get(key.lower(), ...)`，但字典本身是小写构建的**：看似冗余，实则安全；但如果某处漏了 `.lower()`（比如 `raw.get("page_code")` 直接用了大写），就可能查不到字典项，导致回退到 `metadata["page_name"]` —— 这个 fallback 虽然可用，但会让“用户显式填写的 page_code”失效，属于隐性逻辑陷阱。