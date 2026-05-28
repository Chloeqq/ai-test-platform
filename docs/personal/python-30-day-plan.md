# Python 独立写作能力 — 30 天每日练习清单

## 铁律

1. **全程关闭 AI 工具**（Cursor/Copilot/Claude/GPT）。只允许查 Python 官方文档。
2. **每天 3-4 小时**，分两段：上午 1.5-2h 写新代码，下午 1.5-2h 逆向练习。
3. **每道题都手写**，不复制粘贴。哪怕写错，也要自己 debug。
4. **每日做完打 ✓**。连续 3 天没打 ✓，回到第 1 天重来。

---

## 第 1 周：基础语法 + 数据结构（建立手感）

### Day 1 — 字符串与列表操作

**上午（写新函数）**：
```python
# 1. 反转字符串 "hello" → "olleh"
# 2. 统计字符串中每个字符出现次数 "hello" → {"h":1, "e":1, "l":2, "o":1}
# 3. 列表去重并保持顺序 [1,2,2,3,1,4] → [1,2,3,4]
# 4. 找出列表中出现次数最多的元素 [1,2,2,3,2,4] → 2
# 5. 将列表按每 N 个元素分组 [1,2,3,4,5,6], n=2 → [[1,2],[3,4],[5,6]]
```

**下午（逆向项目代码）**：
- 关掉项目文件，自己重写 `dedup_keep_order`（type_utils.py:38）
- 自己重写 `str_value`（type_utils.py:33）
- 写完对照原代码，找出自己缺了什么

**检验**：能不用搜索就写出列表推导式 `[x for x in items if condition]`

---

### Day 2 — 字典操作

**上午（写新函数）**：
```python
# 1. 合并两个字典，有重复 key 时值相加
# 2. 翻转字典的 key 和 value {a:1, b:2} → {1:a, 2:b}，处理重复 value
# 3. 提取嵌套字典中的指定路径 get_nested({"a":{"b":{"c":1}}}, ["a","b","c"]) → 1
# 4. 按 value 降序排列字典
# 5. 统计一个句子中每个单词的出现次数
```

**下午（逆向项目代码）**：
- 自己重写 `dict_value`、`list_value`、`json_dict`（type_utils.py）
- 自己重写 `_dedup_keep_order`（execution_compiler.py:860）
- 对照原代码，特别注意 `isinstance` 检查的习惯

**检验**：能写出 `.get(key, default)` 和 `for k, v in d.items()`

---

### Day 3 — set 集合与条件判断

**上午（写新函数）**：
```python
# 1. 找出两个列表的交集、并集、差集
# 2. 判断一个列表是否有重复元素
# 3. 删除字符串中的所有元音字母 (a e i o u)
# 4. 判断一个字符串是否只包含字母和数字
# 5. 给定年份列表，找出所有闰年
```

**下午（逆向项目代码）**：
- 自己重写 `_env_bool`（orchestrator_service.py:309）
- 自己重写 `_env_int`、`_env_float`（orchestrator_service.py:365, 317）
- 关注异常处理：为什么 catch `(TypeError, ValueError)` 而不是 `Exception`

**检验**：能解释 `x = a or b or "default"` 的执行逻辑

---

### Day 4 — 循环与控制流

**上午（写新函数）**：
```python
# 1. 实现 FizzBuzz：1-100，3的倍数输出Fizz，5的倍数Buzz，都满足FizzBuzz
# 2. 打印九九乘法表
# 3. 找出 1-1000 中的所有质数
# 4. 实现二分查找（排序列表中查找元素的索引）
# 5. 判断一个字符串是否是回文 "racecar" → True
```

**下午（逆向项目代码）**：
- 自己重写 `_normalized_text`（execution_compiler.py:45）
- 自己重写 `_compact`（execution_compiler.py:51）
- 理解 `re.sub` 的用法，特别是不熟悉的替换模式

**检验**：能用 `break`、`continue`、`for-else` 结构

---

### Day 5 — 函数与参数

**上午（写新函数）**：
```python
# 1. 写一个接受任意数量参数的函数，返回它们的和
# 2. 写一个接受任意数量关键字参数的函数，返回一个排序后的字典
# 3. 写一个带默认参数的函数，计算列表中位数
# 4. 写一个装饰器，打印函数执行耗时
# 5. 写一个装饰器，让函数失败时重试最多 3 次
```

**下午（逆向项目代码）**：
- 自己重写 `_clamp_confidence`（execution_compiler.py:96）
- 自己重写 `bounded_score`（type_utils.py:49）
- 理解 `*` 参数分隔符（keyword-only 参数）的作用

**检验**：能写出一个带 `*args, **kwargs` 的函数，并解释它们分别接收什么

---

### Day 6 — 异常处理

**上午（写新函数）**：
```python
# 1. 写一个函数读取文件，文件不存在时返回默认值
# 2. 写一个函数解析 JSON 字符串，格式错误时返回空字典
# 3. 写一个函数，用 try-except-else-finally 完整结构处理数据库连接
# 4. 自定义一个异常类，包含错误码和消息
# 5. 写一个函数调用链，最底层抛异常，最顶层捕获，中间层不做处理
```

**下午（逆向项目代码）**：
- 自己重写 `OrchestratorError` 类（orchestrator_service.py:33-58）
- 自己重写 `ExecutionCompilerError` 类（execution_compiler.py:27-42）
- 注意：为什么 `from exc` 而不是只 `raise`，理解 exception chaining

**检验**：能解释 `raise ... from exc` vs `raise ... from None` 的区别

---

### Day 7 — 文件读写与 JSON/YAML

**上午（写新函数）**：
```python
# 1. 读一个文本文件，统计行数、单词数、字符数（类似 wc 命令）
# 2. 读一个 JSON 文件，找到所有 key 为 "id" 的值
# 3. 写一个 JSON 文件（含嵌套结构），用 indent=2 格式化
# 4. 读一个 CSV 文件，按某列值过滤行
# 5. 把一个嵌套字典写入 YAML 文件
```

**下午（逆向项目代码）**：
- 自己重写 `_iter_recent_reports`（orchestrator_service.py:781-796）
- 注意 `path.glob()` 和 `path.stat().st_mtime` 的用法
- 自己重写 `_save_case` 的逻辑（不依赖 AI 看你的代码）

**检验**：能独立写出 `with open(file) as f: data = json.load(f)` 的正确模式

---

## 第 2 周：函数式思维 + 项目代码深入

### Day 8 — 列表推导与生成器

**上午（写新函数）**：
```python
# 1. 用列表推导生成 1-100 的平方数
# 2. 用列表推导过滤出列表中所有偶数
# 3. 写一个生成器函数，逐行读取大文件，yield 每一行
# 4. 写一个生成器，产生斐波那契数列的前 N 项
# 5. 用列表推导 + 条件过滤，从字典列表中提取符合条件的记录
```

**下午（逆向项目代码）**：
- 自己重写 `list_filtered`（test_case_repository.py:99-149）
- 注意 `.scalars().all()` 和 `list()` 的区别
- 思考：这个函数有哪些地方可以简化

**检验**：能写生成器函数 `yield`，并能解释生成器和列表的区别（内存）

---

### Day 9 — map/filter/sorted + lambda

**上午（写新函数）**：
```python
# 1. 用 map 将字符串列表全部转为大写
# 2. 用 filter 过滤出列表中大于 10 的数
# 3. 用一个 lambda + sorted 对字典列表按某个字段排序
# 4. 用 sorted + key=lambda 实现多条件排序
# 5. 用 zip 将两个列表合并成字典
```

**下午（逆向项目代码）**：
- 自己重写 `_build_evidence_manifest`（orchestrator_service.py:1497-1537）
- 注意 `sorted()`、`set` 差集运算、`sum(len(...))` 的用法
- 思考：哪些地方可以用字典映射简化 if-elif 链

**检验**：能写 `sorted(items, key=lambda x: x["name"])` 且不查文档

---

### Day 10 — 字典映射表代替 if-elif

**今天的目标只有一个**：把你编译器里那个 40 行的 if-elif 链改成字典映射。

**上午**：学习字典映射模式
```python
# 1. 用字典实现简单的计算器：{"add": lambda a,b: a+b, ...}
# 2. 用字典 + 函数引用替换 if-elif 分支
# 3. 处理 "找不到 key" 的情况：.get(key, default_handler)
```

**下午**：改 execution_compiler.py:346-381
```
关掉 AI，把 normalize_test_points_to_actions 中的 action 映射部分
从 if-elif 链改成字典映射表。
```

**检验**：改完后的代码少于 15 行（原来 35 行），且功能一样

---

### Day 11 — enumerate 与索引

**上午（写新函数）**：
```python
# 1. 遍历列表时同时输出索引和元素
# 2. 找出列表中重复元素的所有索引位置
# 3. 将两个列表按索引对应合并 [(1,'a'),(2,'b')] → [{index:0, num:1, char:'a'}, ...]
# 4. 实现一个简单的分页器：给定列表和页码，返回对应页的数据
# 5. 用 enumerate 重写 FizzBuzz（用索引而不是单独维护计数器）
```

**下午（逆向项目代码）**：
- 自己重写 `_extract_steps`（execution_compiler.py:120-138）
- 自己重写 `normalize_test_points`（execution_compiler.py:141-191）
- 注意 `for point_index, raw_point in enumerate(points)` 的模式

**检验**：能不用 range(len(...)) 来遍历列表，用 enumerate 代替

---

### Day 12 — re 正则表达式

**上午（写新函数）**：
```python
# 1. 从字符串中提取所有数字
# 2. 判断一个字符串是否是合法的邮箱地址
# 3. 判断一个字符串是否是合法的手机号
# 4. 从 URL 中提取域名
# 5. 替换字符串中所有的中文标点为英文标点
```

**下午（逆向项目代码）**：
- 自己重写 `_slug_token`（orchestrator_service.py:375）
- 自己重写 `_parse_input_value`（execution_compiler.py:203-214）
- 理解 `re.search`、`re.match`、`re.sub`、`re.findall` 的区别

**检验**：能不用查文档写出 `re.search(r"正则", text)` 和 `re.sub(r"正则", "替换", text)`

---

### Day 13 — dataclass 与类型系统

**上午（写新函数）**：
```python
# 1. 定义一个 dataclass 表示"用户"（姓名、年龄、邮箱）
# 2. 给 dataclass 添加一个方法，返回用户的显示名称
# 3. 用 dataclass 定义一个"API 响应"结构（状态码、数据、错误信息）
# 4. 用 dataclass 定义一个"LLM 请求"（model, messages, temperature, max_tokens）
# 5. 用 asdict 将 dataclass 转换为字典
```

**下午（逆向项目代码）**：
- 自己重写 `OrchestrationResult` dataclass（orchestrator_service.py:85-107）
- 理解 `dataclass` 和 `@dataclass` 装饰器
- 思考：为什么用 dataclass 而不是普通 dict

**检验**：能从头定义一个带类型注解和默认值的 dataclass

---

### Day 14 — pytest 测试

**上午（学测试框架）**：
```python
# 1. 写一个简单的 pytest 测试函数，测试 Day1 写的反转字符串函数
# 2. 用 parametrize 写参数化测试（多组输入输出）
# 3. 用 pytest.raises 测试函数是否正确抛出异常
# 4. 用 conftest.py 定义一个 fixture，在多个测试中共享
# 5. 用 monkeypatch 模拟一个函数的行为
```

**下午**：
- 读你项目中 `tests/conftest.py`，理解 fixture 的作用
- 选一个你 Day1-Day13 写的函数，给它写 3 个测试用例

**检验**：能用 `pytest` 跑自己的测试，理解 pass/fail/error 的区别

---

## 第 3 周：async/await + 网络编程

### Day 15 — 理解同步 vs 异步

**上午（概念 + 简单练习）**：
```python
# 1. 写一个同步函数，time.sleep(1) 三次，记录总耗时（应该 ~3s）
# 2. 写一个异步函数，asyncio.sleep(1) 三次，用 asyncio.gather 并发，记录总耗时（应该 ~1s）
# 3. 理解这 3 个的区别：
#    - 同步串行（一个等完再下一个）
#    - 多线程（多个线程同时跑）
#    - 异步协程（一个线程内切换）
```

**下午**：
- 用 `asyncio.run()` 运行第一个 async 程序
- 理解 `await` 的语义："等待，但不阻塞当前线程"
- 对比 `time.sleep` vs `asyncio.sleep`

**检验**：能口头解释为什么会 async 版本只需要 1 秒

---

### Day 16 — async def + await 基础

**上午（写新函数）**：
```python
# 1. 写一个 async 函数，模拟从 API 获取数据（asyncio.sleep 模拟延迟）
# 2. 写 3 个 async 函数，用 asyncio.gather 并发执行
# 3. 写一个 async 函数，用 gather 并发调用 5 个不同的"API"
# 4. 处理 gather 中的异常：return_exceptions=True
# 5. 用 asyncio.wait_for 给异步任务加超时限制
```

**下午（逆向 + 改造）**：
- 把你项目中 `_parse_requirement_spec` 改造成 async 版本（先做一个模拟版本，不真的调 LLM）
- 把 `_generate_case` 也改成 async
- 用 `asyncio.gather` 同时调用这两个

**检验**：能独立写一个 async 函数，并在另一个 async 函数中 await 它

---

### Day 17 — aiohttp 并发 HTTP 请求

**上午（写新函数）**：
```python
# 1. 用 aiohttp 并发请求 3 个 URL，获取响应状态码
# 2. 写一个 async 函数，用 aiohttp 请求一个 JSON API，解析返回
# 3. 用 asyncio.gather + aiohttp 并发请求 10 个 URL
# 4. 用 asyncio.Semaphore 限制并发数为 3
# 5. 处理网络异常：超时、连接失败、非 200 响应
```

**下午**：
- 用 aiohttp 写一个简单的 async HTTP 客户端
- 对比 `requests`（同步）和 `aiohttp`（异步）的写法差异

**检验**：能独立写出 `async with session.get(url) as resp: data = await resp.json()`

---

### Day 18 — FastAPI async 端点

**上午（写新函数）**：
```python
# 1. 创建一个 FastAPI 应用，写一个 async GET 端点
# 2. 写一个 async POST 端点，接收 JSON body，返回处理结果
# 3. 在端点中调用一个 async 函数（如 Day16 的 API 调用）
# 4. 写一个 async 端点，调用 3 个外部 API 并聚合结果
# 5. 用 HTTPException 返回错误响应
```

**下午**：
- 把你项目的 websocket 或路由文件打开，理解 `async def endpoint()` 的模式
- 写一个 FastAPI 端点，接收一个字符串 → 调用 OpenAI API → 返回结果

**检验**：能独立写出一个 async FastAPI 端点，包含请求体解析和错误处理

---

### Day 19 — Pydantic BaseModel 入门

**上午（写新函数）**：
```python
# 1. 定义一个 Pydantic BaseModel：User（name: str, age: int, email: str）
# 2. 给 User 添加 field_validator：age 必须在 0-150 之间
# 3. 定义一个嵌套模型：Order（id: str, user: User, items: list[str], total: float）
# 4. 用 model_validate() 把 dict 转为 Pydantic 模型
# 5. 用 model_dump() 把 Pydantic 模型转回 dict
```

**下午（逆向你的项目）**：
- 把你项目中一个典型的 dict 结构（比如 `case: dict[str, Any]`）改成 Pydantic model
- 思考：用 Pydantic model 代替 dict 的好处是什么

**检验**：能定义一个 Pydantic BaseModel，用 model_validate 校验输入，catch ValidationError

---

### Day 20 — Pydantic + FastAPI 整合

**上午（写新函数）**：
```python
# 1. 用 Pydantic model 作为 FastAPI POST 端点的 request body
# 2. FastAPI 自动校验：故意发错误的数据给端点，看自动返回的 422 错误
# 3. 定义 response_model，让 FastAPI 自动过滤返回字段
# 4. 处理可选字段：Optional[str]、有默认值的字段
# 5. 用 Pydantic model 定义 LLM 输出格式，用 model_validate 校验 LLM 返回
```

**下午**：
- 写一个完整的端点：接收用户查询 → 调 OpenAI → Pydantic 校验返回 → 返回结构化 JSON
- 这就是 AI 应用工程师最基础的面试题

**检验**：能独立写出 FastAPI endpoint + Pydantic request/response model 的完整链路

---

### Day 21 — 休息日 + 复习

今天不写新代码。回顾 Day 1-20 的代码练习，特别是：
1. 哪些还写不出来的，今天补上
2. 整理一份你自己的"代码片段笔记"（手写，不要复制粘贴）

---

## 第 4 周：综合能力 + 面试题实战

### Day 22 — OpenAI API 独立调用

**上午**：关掉 AI，对着 OpenAI API 文档，独立写：
```python
# 1. 用 openai 库调用 chat.completions.create()
# 2. 解析返回的 message.content
# 3. 处理 API 错误：network error / rate limit / invalid API key
# 4. 加重试逻辑：失败后等待再重试，最多 3 次
# 5. 用 Pydantic 定义期望的 JSON 输出格式
```

**检验**：能独立写一个函数 `async def call_llm(prompt: str) -> LLMResponse`，完整包含调用、解析、校验、重试

---

### Day 23 — Embedding + 向量检索

**上午**：
```python
# 1. 用 openai 库调 embeddings.create() 生成文本向量
# 2. 理解 embedding 是什么：一段文本 → 一个 1536 维的 float 列表
# 3. 用 numpy 计算两个 embedding 的余弦相似度
# 4. 在内存中实现一个简单的向量检索：存 N 个向量，给定查询返回 top-3
# 5. 用 ChromaDB 做同样的检索（对比自己写和用库的区别）
```

**检验**：能从一堆文档中找到与查询最相似的 3 篇

---

### Day 24 — 完整 RAG 链路

**上午**：独立写一个完整的 RAG 脚本（约 100-150 行）：
```python
# 1. 准备 5 篇"文档"（每篇 200 字的中文段落）
# 2. 分块 → embedding → 存储到 ChromaDB
# 3. 用户输入查询 → embedding → 检索 top-3 → 拼成 prompt
# 4. 调 LLM 生成答案
# 5. 返回答案 + 引用来源
```

**检验**：脚本能跑通，面对一个简单查询能返回有来源引用的答案

---

### Day 25 — Streaming 响应

**上午**：
```python
# 1. 用 OpenAI streaming API（stream=True），逐块打印 LLM 输出
# 2. 在 FastAPI 中用 StreamingResponse 返回 streaming 内容
# 3. 用 SSE（Server-Sent Events）格式流式返回
# 4. 在前端用 EventSource 接收 streaming 数据
```

**检验**：能写出一个 FastAPI 端点，用户请求后能看到逐字输出的效果

---

### Day 26 — 面试题模拟：AI 应用

**全天**：计时完成以下题目（每道 25 分钟，关闭 AI）：

1. "写一个函数，接收用户查询和文档列表，用 embedding 找到最相关的文档，调用 LLM 生成答案。包含错误处理。"

2. "把上面的函数改成 async 版本，支持并发处理多个查询。"

3. "用 Pydantic 定义一个 ChatMessage 模型，写一个函数把消息列表转为 OpenAI API 的 messages 格式。"

---

### Day 27 — 面试题模拟：Python 基础

**全天**：计时完成（每道 15 分钟）：

1. "实现一个 LRU Cache，支持 get 和 put 操作。"
2. "合并 K 个有序列表。"
3. "写一个装饰器，让函数在 N 秒内最多执行一次（debounce）。"
4. "写一个函数，扁平化嵌套列表 [1,[2,[3,4]],5] → [1,2,3,4,5]。"

---

### Day 28 — 读懂你项目的代码

**全天**：逐文件读你项目的核心代码，能口述每个函数做什么：

- `execution_compiler.py` 的前 200 行（DSL 编译核心）
- `orchestrator_service.py` 的 `__init__` 方法（依赖注入结构）
- `test_case_repository.py` 全部（Repository 模式）

要求：每一行都要能解释为什么这样写，而不是 "AI 帮我写的"。

---

### Day 29 — 项目代码重构

把你编译器中的 if-elif 链改成字典映射表（Day 10 可能已经做了）。
再选一个函数，用 Pydantic model 替换它的 `dict[str, Any]` 返回类型。

---

### Day 30 — 综合测验

**全天**：关闭所有 AI 工具，独立完成以下任务：

> 写一个 FastAPI 应用，包含一个 POST /chat 端点：
> - 接收用户消息、对话历史
> - 用 embedding 从 ChromaDB 检索相关上下文
> - 拼成 prompt 调用 OpenAI streaming API
> - 流式返回结果
> - 所有输入输出用 Pydantic 模型校验
> - 包含完整的错误处理和重试

如果第 30 天能独立完成这个，你具备了 AI 应用工程师的**基本编码能力**。

---

## 每日执行清单

| 日 | 主题 | ✓ |
|----|------|---|
| 1 | 字符串与列表操作 | |
| 2 | 字典操作 | |
| 3 | set 与条件判断 | |
| 4 | 循环与控制流 | |
| 5 | 函数与参数（装饰器） | |
| 6 | 异常处理 | |
| 7 | 文件读写与 JSON/YAML | |
| 8 | 列表推导与生成器 | |
| 9 | map/filter/sorted + lambda | |
| 10 | 字典映射表代替 if-elif | |
| 11 | enumerate 与索引 | |
| 12 | re 正则表达式 | |
| 13 | dataclass 与类型系统 | |
| 14 | pytest 测试 | |
| 15 | 理解同步 vs 异步 | |
| 16 | async def + await 基础 | |
| 17 | aiohttp 并发 HTTP | |
| 18 | FastAPI async 端点 | |
| 19 | Pydantic BaseModel | |
| 20 | Pydantic + FastAPI 整合 | |
| 21 | 复习日 | |
| 22 | OpenAI API 独立调用 | |
| 23 | Embedding + 向量检索 | |
| 24 | 完整 RAG 链路 | |
| 25 | Streaming 响应 | |
| 26 | 面试题：AI 应用 | |
| 27 | 面试题：Python 基础 | |
| 28 | 读懂项目代码 | |
| 29 | 项目代码重构 | |
| 30 | 综合测验 | |

---

## 重要的提醒

1. **前 7 天最难**。你会反复想 "我用 AI 一分钟就写完了"。忍住。这个痛苦过程就是学习。
2. **第 10 天是关键节点**。如果你能把 35 行的 if-elif 改成 5 行的字典映射表，你的思维模式已经变了。
3. **第 22 天之后是分水岭**。这之前你在补基础，之后你在建 AI 应用。第 30 天的综合测验就是你的简历项目。
4. **进度可以慢，不能假**。一天没完成没关系，但不要用 AI 假装完成了。假的进度是浪费你自己的时间。
