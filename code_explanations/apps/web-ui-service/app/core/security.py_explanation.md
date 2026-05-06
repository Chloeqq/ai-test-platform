# 📘 代码说明书
## 一句话概括
这个文件是整个系统的“保安队长”，负责用户登录时的密码加密、验证，以及发放和检查 JWT 登录小票（token），确保只有合法用户才能进入后台。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `security.py` | 实现用户身份认证的核心逻辑：密码加盐加密、旧密码兼容校验、生成/解析登录令牌（JWT）、从令牌中查出当前登录用户 |

## 🔍 核心函数/类说明
- **`hash_password(password: str) -> str`**：把明文密码“锁进保险箱”，变成一串谁都看不懂的乱码（bcrypt 加密哈希）  
  - 输入：用户的原始密码，比如 `"123456"`  
  - 输出：一串长得像 `$2b$12$...` 的加密字符串（每次调用结果都不同，因为加了随机“盐”）  
  - 大白话解释：就像把钥匙扔进碎纸机+混入一把沙子再压成砖——别人拿不到原钥匙，也很难反推出来；而且同一把钥匙碎两次，出来的砖还不一样，防被“字典攻击”。

- **`verify_password(plain_password: str, hashed_password: str) -> bool`**：检查用户输入的密码是否和数据库里存的“保险箱密码”匹配  
  - 输入：用户刚输的密码（明文） + 数据库里存的加密后密码（可能是 bcrypt 或老式 SHA-256）  
  - 输出：`True`（对得上，放行）或 `False`（不对，拦下）  
  - 大白话解释：先试试用标准“开锁工具”（bcrypt）能不能打开；打不开？别急——系统还记得老版本的“简易锁”（SHA-256），就再用那个试试。这是为了不让老用户升级时被迫重设密码，平滑过渡。

- **`create_access_token(...)`**：给成功登录的用户发一张带有效期的电子门禁卡（JWT）  
  - 输入：用户 ID（`subject`）、用户名、角色、过期时间（可选）  
  - 输出：一长串形如 `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` 的 JWT 字符串  
  - 大白话解释：就像酒店前台给你一张房卡——卡上写着“张三，VIP，2小时后失效”，还盖了酒店钢印（签名）。这张卡不用联网查，门禁机自己就能验真伪和时效。

- **`decode_access_token(token: str) -> dict`**：检查用户递来的“门禁卡”是不是真货、有没有过期  
  - 输入：前端传来的 JWT 字符串  
  - 输出：解码后的字典，比如 `{"sub": "123", "username": "zhangsan", "exp": 171xxxxxx}`  
  - 大白话解释：门禁机扫一下卡，核对钢印（签名）是不是酒店盖的，再看卡上写的截止时间是不是还没到。假卡、过期卡、被涂改的卡，一律报警（抛出 401 错误）。

- **`get_current_user(...)`**：拿着用户给的“门禁卡”，查出他到底是谁（从数据库捞出完整用户信息）  
  - 输入：JWT token（自动从请求头 `Authorization: Bearer xxx` 提取） + 数据库连接（自动注入）  
  - 输出：一个 `User` 对象（含 id、姓名、邮箱、是否启用等）  
  - 大白话解释：保安不仅验卡，还要查登记簿——确认卡主“张三”确实住在这栋楼（数据库有记录），而且没被拉黑（`is_active=True`）。查不到或被禁用？对不起，不许进。

## 🧩 调用关系与数据流转
```
用户登录 → [FastAPI路由] → hash_password()     # 注册/改密时加密密码，存进数据库
                            ↓
用户提交账号密码 → [登录接口] → verify_password() → ✅ 放行 → create_access_token() → 返回token给前端
                                                              ↓
前端后续请求带 token → [受保护接口] → get_current_user() 
                                          ↓
                                  decode_access_token() → 解出 {sub: "123", ...}
                                          ↓
                                  用 sub（用户ID）查数据库 → 找到 User 对象 → 注入到接口函数参数中供业务使用
```

## 💡 值得学习的写法
- **双密码兼容设计**：`verify_password()` 同时支持新 bcrypt 和旧 SHA-256，用 `try/except` 自动降级，上线零打扰，老数据无缝迁移。
- **安全比对防时序攻击**：`secrets.compare_digest()` 替代 `==` 比较哈希值，避免黑客通过响应时间差猜出密码哈希（就像关门声长短暴露锁芯结构）。
- **JWT payload 设计清晰**：固定用 `"sub"` 存用户 ID（符合 JWT 标准），额外加 `"username"` 和 `"role"` 方便接口直接用，不用再查库。
- **依赖注入链路干净**：`get_current_user` 直接声明 `Depends(oauth2_scheme)` 和 `Depends(get_db)`，FastAPI 自动完成 token 解析 + DB 连接，业务接口只需写 `current_user: User = Depends(get_current_user)` 就拿到活生生的用户对象。

## ⚠️ 需要注意的地方
- **`subject` 必须是用户 ID 字符串**：`get_current_user()` 里硬编码 `int(subject)`，如果未来想用邮箱或 UUID 当 subject，这里会崩——需同步改 `create_access_token()` 的 `subject` 类型和此处解析逻辑。
- **JWT 密钥必须保密且一致**：`settings.jwt_secret_key` 若在开发/生产环境不一致，会导致 token 在本地能签发却无法解码（报“invalid or expired token”错，实际是签名错）。
- **`datetime.now(UTC)` 依赖 `datetime_compat`**：项目用了自定义 UTC 模块，若未来升级 Python 或删掉该模块，`datetime.now(UTC)` 会报错（应改用 `datetime.now(timezone.utc)`）。
- **未处理 token 黑名单/主动退出**：当前设计 token 过期前永远有效，用户“退出登录”只是前端删 token，后端无感知——如需强制踢人，需额外加 Redis 黑名单逻辑。