# 📘 代码说明书
## 一句话概括
这是一个给网页“按钮、输入框、链接”等界面元素起名字的智能检查员——它能判断你起的名字（比如 `user_login_button`）是否符合团队规范，并在不合规时给出清晰错误提示和更合适的建议名。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `page_element_code_policy.py` | 负责校验和生成前端页面元素的编码（element code），确保命名统一、语义清晰、不含技术噪音（如 `xpath`、`div`）、不带冗余前缀（如 `page_home_`），并支持中英文语义映射（如把“重置”自动转成 `reset`）。 |

## 🔍 核心函数/类说明
- **`ElementCodePolicyResult`**：一个装结果的“小信封”，里面固定放四样东西  
  - 输入：无（它是数据容器，不是函数）  
  - 输出：`valid`（是否合格）、`normalized_code`（你原来写的原样）、`suggested_code`（推荐改写的名字）、`errors`（不合格的原因列表）  
  - 大白话解释：就像快递单上的“收件状态”+“原始地址”+“系统建议的新地址”+“为什么原地址不能送”（比如“门牌号含中文”“写了‘第3个div’这种临时描述”）。

- **`suggest_element_code()`**：基础版“起名助手”  
  - 输入：一段原始文本（如 `"用户登录按钮"` 或 `"CSS定位元素: #login-btn"`），可选页面名（`page_code="home"`）和业务类型（`business_type="button"`）  
  - 输出：一个干净、合规的蛇形命名（如 `"user_login_button"`）  
  - 大白话解释：它先把文字转成小写、去标点、用下划线连起来（`"用户登录按钮"` → `"user_login_button"`），再删掉像 `css`、`div`、`temp` 这类“程序员随手写的定位词”，最后根据 `business_type` 自动加后缀（`button` → `_button`），避免你手动拼错。

- **`suggest_business_element_code()`**：升级版“起名助手”，会看懂中文意思  
  - 输入：同上，但更聪明  
  - 输出：优先用语义映射（如 `"重置"` → `"reset"`），再加业务后缀（`"reset_button"`）；如果语义匹配不上，就退回到 `suggest_element_code()` 的规则  
  - 大白话解释：它不只机械转拼音，而是像产品经理一样理解业务——看到“用户名输入框”，直接建议 `username_input`；看到“审核通过”，建议 `review_approved`，而不是 `shen_he_tong_guo`。

- **`validate_element_code_policy()`**：严格的“命名审查官”  
  - 输入：你提交的元素编码（如 `"loginBtn"`）、所属页面（`"user_manage"`）、业务类型（`"button"`）  
  - 输出：一个 `ElementCodePolicyResult` 对象，告诉你“合格吗？哪里错了？建议改成啥？”  
  - 大白话解释：它逐条核对：① 是不是全小写+下划线？② 有没有偷偷塞 `xpath`、`div` 这种“技术废话”？③ 最后是不是数字（比如 `btn1`）？④ 有没有多此一举写 `page_user_manage_login_btn`（前缀应由页面对象管理，不该塞进元素名里）？⑤ 类型是 `password_toggle` 就必须叫 `password_toggle` —— 全部过关才算合格。

- **`require_valid_element_code()`**：审查官的“执法模式”  
  - 输入：同上  
  - 输出：如果合格，就原样返回你的编码；不合格就直接抛出 HTTP 错误（400 Bad Request），附带友好的错误信息和推荐名  
  - 大白话解释：这是 FastAPI 接口里真正用的函数——比如你在 API 请求里传了 `"LoginBtn"`，它立刻拦下说：“不行！得小写+下划线，推荐用 `login_button`”，并让前端立刻看到红字提醒，不用自己写一堆 if 判断。

## 🧩 调用关系与数据流转
```
外部调用（如 FastAPI 接口）
        ↓
require_valid_element_code() 
        ↓（调用验证）
validate_element_code_policy()
        ├─→ suggest_business_element_code() 
        │         ↓（优先走语义解析）
        │    _semantic_code_from_text() → 查表匹配中文词（如“取消”→"cancel"）
        │         ↓（失败则降级）
        │    suggest_element_code() → 纯字符串清洗+过滤噪音词+加后缀
        │
        ├─→ _strip_page_prefix() → 去掉 page_xxx_ 前缀（防重复）
        ├─→ _append_business_suffix() → 根据 business_type 补后缀（button→_button）
        └─→ 各项规则检查（正则、黑名单、后缀校验等）→ 汇总 errors

最终：所有结果打包进 ElementCodePolicyResult 返回
```

## 💡 值得学习的写法
- **语义词典按长度倒序匹配**：`SEMANTIC_PHRASES` 中的中文短语（如“审核通过”“审核”）按长度从长到短排序，先匹配长的，避免“审核通过”被拆成“审核”+“通过”两个词，保证语义完整。
- **噪音词集合分层设计**：`STRICT_LOCATOR_NOISE_TOKENS`（绝对禁止）和 `SUGGESTION_NOISE_TOKENS`（仅建议时过滤）分开，让“检查”和“建议”逻辑解耦，各司其职。
- **`_snake()` 函数的健壮清洗**：用两次正则（非字母数字→下划线，多个下划线→一个），再 `.strip("_")`，完美处理 `"用户名！！！"` → `"username"`、`"  A B C  "` → `"a_b_c"` 等各种脏数据。
- **`dataclass(frozen=True)` 防篡改**：`ElementCodePolicyResult` 设为不可变，确保审查结果一旦生成就不能被意外修改，增强可靠性。

## ⚠️ 需要注意的地方
- **`page_code` 为空时 `_page_token("")` 返回空字符串**：`_strip_page_prefix()` 中若 `page_code=""`，会跳过前缀清理逻辑——这是有意设计（页面无关元素无需去前缀），但新手可能误以为“没生效”，需注意文档说明。
- **`business_type="password_toggle"` 是硬性特例**：它不走任何后缀拼接逻辑，强制要求编码必须等于 `"password_toggle"`，否则报错。容易忽略这个例外，导致调试时卡住。
- **中文语义匹配不支持嵌套或模糊匹配**：比如 `"批量删除按钮"` 只能匹配到 `"删除"` 和 `"按钮"`，但 `"批量"` 不在词典里就会丢失；不会自动合成 `"batch_delete_button"`。需要人工补全 `SEMANTIC_PHRASES`。
- **`FORMAL_ELEMENT_CODE_PATTERN` 长度限制是 3–80 字符**：但 `suggest_*` 函数生成的建议名可能超长（比如超长中文转译），此时返回空字符串而非截断——调用方需自行处理“无建议名”的情况，否则前端可能显示空白推荐。