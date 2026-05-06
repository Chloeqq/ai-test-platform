# 📘 代码说明书
## 一句话概括
这个文件是整个项目的“数据库管家”，负责连接数据库、创建会话（就像打开一个和数据库聊天的窗口），并安全地把聊天窗口交给其他代码用完后自动关掉。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `database.py` | 统一管理数据库连接和会话，让其他模块不用操心怎么连数据库、怎么关连接，只管安心“说话”（读写数据） |

## 🔍 核心函数/类说明
- **`get_db()`**：作用是提供一个“可重复使用的数据库对话窗口”，专为 FastAPI 的依赖注入设计。
  - 输入：无（不需要你传任何东西）
  - 输出：一个 `Session` 对象（你可以把它想象成一张“数据库通话卡”，拿着它就能查/改数据）
  - 大白话解释：就像餐厅的传菜员——你（比如某个 API 接口）说“我要查用户”，传菜员（`get_db`）就立刻去后厨（数据库）领一张干净的通话卡（`db = SessionLocal()`），交给你用；等你用完了（不管成功还是出错），传菜员一定帮你把这张卡还回去并擦干净（`db.close()`），避免卡片堆满厨房（连接泄漏）。

- **`class Base(DeclarativeBase)`**：作用是所有数据库模型的“共同祖先”。
  - 输入：无
  - 输出：无（它本身不干活，但所有要存进数据库的“数据模板”（比如 User、Post 类）都得声明“我是 Base 的孩子”）
  - 大白话解释：就像学校给每个班级发的统一练习册封面——`Base` 就是那个印着校徽和“XX学校练习册”的空白封面。后面老师写的 `class User(Base)` 就相当于在这本封面上贴了张标签：“这是用户班的练习册”。这样学校（SQLAlchemy）一看封面就知道：“哦，这本是正规册子，可以收进档案室（数据库）”。

- **`engine` 和 `SessionLocal`**：不是函数也不是类，而是两个关键“工具”。
  - `engine`：数据库的“总开关+翻译官”——它知道怎么连上 MySQL/PostgreSQL/SQLite，还能把 Python 话（比如 `user.name = "张三"`）翻译成数据库能听懂的 SQL 语句（比如 `UPDATE users SET name='张三'...`）。
  - `SessionLocal`：一个“造对话卡的机器”——每次调用它，就造出一张新的、干净的通话卡（数据库会话），保证每个人用的都是独立、不串线的通道。

## 🧩 调用关系与数据流转
```
FastAPI 启动 → 加载 database.py → 创建 engine（连库）和 SessionLocal（造卡机）
       ↓
某个 API 路由（如 /users/）→ 声明依赖 get_db() 
       ↓
get_db() 被调用 → SessionLocal() 造一张新通话卡（db）→ yield db 给路由函数用
       ↓
路由函数用 db.query(User).filter(...).all() 查数据 → 数据从数据库流进 Python 变量
       ↓
路由函数执行结束（或中途报错）→ 自动触发 finally: db.close() → 归还并清理通话卡
```

## 💡 值得学习的写法
- 使用 `Generator[Session, None, None]` 类型提示 + `yield` + `finally`：实现了“自动关卡”机制，既保证了资源一定释放（比手动 try/finally 更可靠），又让 FastAPI 能自然地把 `db` 当作依赖注入进去，是 Python 中“上下文管理”思想的优雅落地。
- 动态配置 `engine_kwargs`：根据数据库类型（SQLite vs 其他）自动开关不同参数（比如 SQLite 不需要连接池，所以跳过 pool_size 等设置），避免“给自行车装飞机引擎”式的错误配置。
- `pool_pre_ping=True`：像定期敲门检查——每次从连接池取连接前，先问一句“你还活着吗？”，避免拿到一个已断开的“僵尸连接”导致报错，极大提升线上稳定性。

## ⚠️ 需要注意的地方
- `settings.database_url.startswith("sqlite")` 这个判断很脆弱：如果 URL 是 `sqlite:///./app.db?check_same_thread=False`（带查询参数），`.startswith("sqlite")` 仍成立，但后面 `connect_args` 会被重复设置（虽然 SQLAlchemy 通常能合并，但属于隐式行为，建议用 `settings.database_url.lower().startswith(("sqlite:///", "sqlite+pysqlite:///"))` 更严谨）。
- `max_overflow` 设为 `max(0, int(...))` 是对的，但若配置文件里填了负数或非数字（如 `"abc"`），`int("abc")` 会直接崩溃——这里缺少配置校验，应在 `get_settings()` 或加载时做容错。
- `get_db()` 是生成器函数，**绝不能直接调用 `get_db()` 拿 session**（比如 `db = get_db()`），那样只会得到一个 generator 对象，而不是真正的数据库会话！必须通过 FastAPI 依赖注入（`def api_route(db: Session = Depends(get_db)):`）或 `with next(get_db()) as db:` 才能正确使用。