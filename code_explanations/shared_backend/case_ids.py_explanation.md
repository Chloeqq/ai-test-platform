# 📘 代码说明书
## 一句话概括  
这个文件是「测试用例ID的智能生成器和解析器」——它能根据页面名、模块名、功能描述等自然语言信息，自动编出像 `mall-web-ret-auth-fn-ai-0042` 这样规范、可读、可追溯的测试用例编号，并能反向从编号里拆出含义，还能帮你在已有编号基础上自动生成下一个序号（比如 `0042` → `0043`）。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `case_ids.py` | 统一管理测试用例 ID 的「命名规则」「智能推断」「标准化生成」「安全解析」和「元数据补全」，让测试人员不用死记硬背编码规则，输入“退货页的登录模块”就能得到标准 ID，输入 `TC-return-login-123` 也能自动转成 `mall-web-ret-auth-fn-ai-0123`。 |

## 🔍 核心函数/类说明
- **`build_case_id()`**：作用——根据你提供的页面、模块、序号等信息，生成一个完整、合规、带前缀的测试用例 ID（如 `mall-web-ret-auth-fn-ai-0001`）。  
  - 输入：`page="退货页"`、`module="登录"`、`sequence=1`（还可选填项目/客户端/类型/来源等，默认值已预设好）  
  - 输出：字符串格式的标准用例 ID（全部小写、连字符分隔、序号自动补零为4位）  
  - 大白话解释：就像「快递单号生成机」——你告诉它“发往退货页、走登录模块、这是第1个”，它就吐出一个全球唯一、符合公司规范、带校验位（长度/字符）的“快递单号”，别人一看就知道是哪块业务、谁生成的、第几个。
  
- **`infer_page_code()` / `infer_module_code()` / `infer_case_type()` / `infer_source_code()`**：作用——当没给明确编码（如 `"ret"` 或 `"auth"`）时，自动从中文名、标题、标签甚至操作步骤里“猜”出最可能的编码。  
  - 输入：`page="订单退款页"`、`title="用户点击‘申请退款’按钮"`、`tags=["regression", "payment"]`  
  - 输出：`"ref"`（退款页）、`"subm"`（提交模块）、`"rg"`（回归测试）、`"mn"`（人工编写）  
  - 大白话解释：像「AI小秘书」——你随手写“我要测退款流程”，它立刻读懂关键词，把模糊描述翻译成系统能识别的“密码”（`ref`+`subm`+`rg`），省得你翻文档查编码表。

- **`normalize_case_id()`**：作用——把五花八门的用户输入（如 `"TC_订单退款-123"`、`"test-case-return-42"`、甚至 `"mall-web-ret-auth-fn-ai-0042:20240501"`）统统“捋直”，转成标准格式。  
  - 输入：任意乱写的 ID 字符串（支持带时间戳 `:` 分隔）  
  - 输出：标准小写 ID（如 `"mall-web-ref-subm-rg-mn-0123"`），或带时间戳的 `"mall-web-ref-subm-rg-mn-0123:20240501"`  
  - 大白话解释：像「ID 洗衣机」——不管丢进去的是油渍T恤（`TC_return_123`）、泥巴裤（`test case refund #42`）还是带水印的衬衫（`xxx:20240501`），出来都是干净平整、统一挂牌（标准格式）的工装服。

- **`next_case_sequence()`**：作用——在一堆已有用例 ID 中，找出同属一个业务前缀（比如都是 `mall-web-ret-auth-*`）的最大序号，自动+1，避免手动数错。  
  - 输入：`existing_case_ids=["mall-web-ret-auth-fn-ai-0001", "mall-web-ret-auth-fn-ai-0003"]`, `page="退货页"`, `module="认证"`  
  - 输出：`4`（因为已有 0001 和 0003，下一个是 0004）  
  - 大白话解释：像「自动点钞机+1」——你把一叠编号纸币（用例ID）塞进去，它快速扫一遍，发现最大是 0003，马上告诉你：“下一张该印 0004 了”，再也不怕漏号、重号、手抖输错。

- **`build_case_metadata()`**：作用——不只生成 ID，还顺手把 ID 背后的“人话含义”打包成字典，比如 `"page_name": "退货页"`、`"module_name": "身份认证"`、`"case_type_name": "回归测试"`。  
  - 输入：`page="退货页"`、`module="登录"`、`title="验证退款密码"`、`tags=["security"]`  
  - 输出：一个含 10 个字段的字典，包含所有标准化编码 + 对应中文名 + 项目信息  
  - 大白话解释：像「快递单的详情页」——不只给你单号 `mall-web-ref-auth-rg-mn-0001`，还附赠：收件地址（退货页）、包裹内容（身份认证模块）、服务类型（回归测试）、寄件人（AI生成）、甚至备注（含 security 标签）——方便报表、搜索、审计，一眼看懂。

## 🧩 调用关系与数据流转  
```
用户输入（自然语言 or 粗糙ID）  
    ↓  
infer_*() 函数群（猜编码） → normalize_*() 函数群（校验+规整）  
    ↓                              ↓  
build_case_prefix() ←───────┐      │  
    ↓                       │      │  
build_case_id() ←───────────┼──────┘  
    ↓  
normalize_case_id() ←───────（支持反向解析 & 容错转换）  
    ↓  
match_case_id() ←───────────（正则精准匹配，用于校验和拆解）  
    ↓  
next_case_sequence() ←──────（用 match 提取 prefix + sequence，找最大值+1）  
    ↓  
build_case_metadata() ←─────（调用 infer/normalize 获取所有编码，再查 name 映射表补中文名）
```

> 💡 关键流转逻辑：所有“智能推断”（infer）都优先查字典映射表（如 `get_alias_code_map("page")`），查不到才用关键词规则兜底；所有“标准化”（normalize）都先过 `_to_code()` 做 ASCII 清洗 + 长度控制，再查白名单校验（如 `CLIENT_CODES`），不合法就 fallback；所有 ID 构建都依赖 `build_case_prefix()` 这个“前缀组装中心”。

## 💡 值得学习的写法
- **字典映射 + 规则兜底双保险**：`normalize_page_code()` 先查 `resolve_dictionary_code()`（精确匹配业务词典），失败再走 `_to_code()`（模糊清洗），既保准确又保容错，像“先查身份证号，查不到再按姓名+生日猜”。
- **正则命名组 + 动态拼接**：`_CASE_ID_PATTERN` 用 `(?P<project>...)` 给每段命名，后续 `match.group("project")` 直接取值，比用索引 `match.group(1)` 更清晰、不易错。
- **`split_run_id()` 巧妙处理时间戳**：用一次 `split(":", 1)` 就分离 ID 和时间（即使时间里有多个 `:`），避免正则复杂化，简单高效。
- **`_as_text_list()` 统一输入归一化**：把 `str`/`list`/`tuple`/`set` 全部转成干净字符串列表，消除类型判断分支，后续代码直接遍历，清爽利落。
- **`next_case_sequence()` 的 prefix 匹配逻辑**：不是简单比对原始字符串，而是用 `match_case_id()` 解析后，用相同规则重新拼 `candidate_prefix`，确保“苹果比苹果”，避免因大小写、多余空格导致误判。

## ⚠️ 需要注意的地方
- **`_to_code()` 的“缩写生成”有陷阱**：当清洗后字符串太长（如 `"userAuthenticationService"`），它会先取每段前3字母（`"USR"`），再取首字母（`"UAS"`），最后才用 fallback。但若原词是 `"core"` → `"CORE"`（6字）→ 符合长度直接返回，而 `"core-module"` → `"CORE-MODULE"` → `"COREMODULE"`（10字）→ 被截断 → `"COR"`（3字）→ 可能和 `"cart"` 冲突。建议关键编码尽量走字典映射，少依赖自动缩写。
- **`infer_module_code()` 的步骤解析有隐式依赖**：它会扫描 `steps` 列表里的 `action` 和 `target` 字段，但如果传入的 `steps` 是非标准结构（如字段名是 `operation` 而非 `action`），就会漏判。调用方必须保证数据格式一致。
- **`normalize_case_id()` 的 fallback 风险**：当输入完全无法解析（如纯数字 `"12345"`），它会无条件返回 `DEFAULT_CASE_ID`（`"mall-web-common-core-fn-ai-0001"`），可能掩盖真实错误。建议在关键路径加日志告警。
- **大小写敏感易踩坑**：`PAGE_CODE_MAP` 和 `PAGE_NAME_MAP` 的 key 是大写（`"RET"`），但 `normalize_page_code()` 返回的是小写（`"ret"`），所以查 `PAGE_NAME_MAP.get(page_code.upper(), ...)` 这步必不可少——漏掉 `.upper()` 就查不到中文名，新手容易忘。
- **`match_case_id()` 不校验业务有效性**：它只检查格式是否匹配正则，但不验证 `client="web"` 是否在 `CLIENT_CODES` 里。也就是说，`"mall-weeb-common-core-fn-ai-0001"`（weeb 拼错）也能过 `match_case_id()`，但会在 `normalize_client_code()` 里 fallback 成 `"web"`。需注意：正则匹配 ≠ 业务合法。