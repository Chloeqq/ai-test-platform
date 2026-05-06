# 📘 代码说明书
## 一句话概括
这是一个用户认证模块，负责处理注册、登录、获取令牌和查看当前登录用户信息这四件事，就像一个「数字门卫」：检查你是谁、给你一把临时钥匙（token）、确认你有权限进门，并告诉你“你现在是谁”。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `auth.py` | 实现用户注册、登录、令牌发放和身份验证的 API 接口，是整个系统登录功能的“总开关”。 |

## 🔍 核心函数/类说明
- **`_build_token_response(user: User) -> Token`**：作用是把刚登录成功的用户信息打包成一个“带钥匙的用户名片”。
  - 输入：一个数据库里的 `User` 对象（含 ID、用户名、角色等）。
  - 输出：一个 `Token` 对象，里面包含一串加密生成的访问令牌（access_token）和用户基本信息（`UserRead`）。
  - 大白话解释：就像酒店前台给你房卡（token）的同时，顺手递上一张印着你名字和房间号的卡片（用户信息）——既让你能开门，又让你知道自己是谁、有什么权限。

- **`register(payload: UserCreate, db: Session)`**：作用是允许新用户自己注册账号（但不能注册管理员）。
  - 输入：用户填的注册表单（用户名、密码、想选的角色）。
  - 输出：成功后返回这个新用户的精简信息（不含密码！）。
  - 大白话解释：就像自助奶茶店的会员注册机——你输入名字、密码、勾选“只想看菜单（viewer）”或“想试新品（tester）”，它检查名字没被占，就给你开个账户；但“店长权限（admin）”得老板手动开，不对外开放。

- **`login(payload: LoginRequest, db: Session)`**：作用是用手机号+密码方式登录，返回令牌。
  - 输入：用户名和明文密码（比如 `{"username": "alice", "password": "123"}`）。
  - 输出：一个 `Token`（含 access_token 和用户信息）。
  - 大白话解释：就像你用 App 登录——输对账号密码，系统就给你发一个“限时入场券”，凭它接下来 30 分钟能进后台看数据。

- **`issue_token(form_data: OAuth2PasswordRequestForm, db: Session)`**：作用是支持标准 OAuth2 表单提交方式的登录（常被 Postman 或前端框架自动调用）。
  - 输入：不是 JSON，而是 `x-www-form-urlencoded` 格式（像网页表单那样，字段叫 `username` 和 `password`）。
  - 输出：同 `login()`，也是 `Token`。
  - 大白话解释：相当于同一扇门装了两种门禁读卡器——一种是 App 扫码登录（`/login`），一种是浏览器传统表单提交（`/token`），都通向同一个后台验证逻辑，只是“刷卡姿势”不同。

- **`me(current_user: User)`**：作用是“我是谁？”——让已登录用户查自己的完整身份信息。
  - 输入：靠 `Depends(get_current_user)` 自动从请求头里取出解码后的用户（就像门卫看了你的入场券，就知道你是谁）。
  - 输出：当前用户的 `UserRead` 信息。
  - 大白话解释：就像你走进公司大楼刷了卡，前台系统自动弹出你的工牌照片和部门信息：“您好，张三，前端组，工号 10086”。

## 🧩 调用关系与数据流转
```
用户发起请求
     ↓
[register] 或 [login] 或 [issue_token] 或 [me]
     ↓（都需连接数据库）
db = Depends(get_db) → 查询 User 表（查重 / 查用户 / 验证密码）
     ↓
验证失败？→ 抛出 HTTPException（401/403/409）→ 返回错误提示
     ↓
验证成功？
     ├─ register → 创建 User 对象 → 写入 DB → 返回 UserRead
     ├─ login / issue_token → 调用 _build_token_response() → 生成 token + 用户信息 → 返回 Token
     └─ me → 直接返回 current_user 的 UserRead（无需查库，已由 get_current_user 提前解码好）
```

> 💡 小提示：`get_current_user` 是另一个文件里的函数（不在本段代码中），它会自动从请求头 `Authorization: Bearer xxx` 中取出 token，解密并确认是否过期、是否有效——就像门禁系统自动扫描你的入场券真伪。

## 💡 值得学习的写法
- **复用 `_build_token_response`**：把“生成 token + 包装用户信息”的逻辑抽成私有函数，`login` 和 `issue_token` 都调它，避免重复写两遍，改一处全生效。
- **角色默认降级为 `"viewer"`**：`role=payload.role.strip().lower() or "viewer"` 这句很聪明——如果用户没填角色、或只填了空格，就自动变成最安全的“围观群众”，防呆又安全。
- **两个登录入口（`/login` 和 `/token`）并存**：兼顾开发者调试（JSON 方便 Postman）和标准 OAuth2 客户端（表单兼容性好），用户体验和规范性都照顾到了。
- **`UserRead.model_validate(user)`**：不用手动一个个字段赋值，直接用 Pydantic 模型“一键转成干净响应体”，自动过滤掉敏感字段（如 `hashed_password`），省心又安全。

## ⚠️ 需要注意的地方
- **注册时没校验密码强度**：代码只做了基础哈希，但没检查“密码是否太短”或“是否全是数字”，上线前建议加 Pydantic 的 `@field_validator` 或在 `UserCreate` 模型里约束。
- **`issue_token` 和 `login` 功能高度重复**：虽然目前靠不同输入格式区分，但未来维护容易漏改一个——理想做法是让其中一个内部调用另一个（比如 `issue_token` → `login`），避免逻辑双写。
- **`_build_token_response` 里传了 `user.role`，但 `create_access_token` 是否真的用了它？**：如果 `create_access_token` 函数没在 token payload 里存 `role`，那这里传进去就白费了；需要确认 `security.py` 里 token 生成逻辑是否真正携带了角色信息，否则权限控制会失效。
- **`select(User).where(...).scalar_one_or_none()` 可能慢**：没给 `username` 字段建数据库索引的话，用户一多就会变卡——就像图书馆没按书名排序，找书得翻遍所有架子。上线前务必确保 `username` 是数据库唯一索引。