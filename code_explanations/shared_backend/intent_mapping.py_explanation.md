# 📘 代码说明书
## 一句话概括
这个文件是自动化测试脚本里的“翻译官”——它把人类写得五花八门的操作指令（比如 `"click: 登录按钮"` 或 `"goto = /dashboard"`），统一翻译成标准、干净、程序能听懂的三要素：**动作类型**（如 `"click"`）、**目标元素**（如 `"btn-login"`）、**附加值**（如 `"admin123"`）。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `intent_mapping.py` | 把用户写的模糊/口语化/格式不一的测试步骤提示（steps_hint），标准化为结构化指令，供后续执行器调用 |

## 🔍 核心函数/类说明
- **`resolve_explicit_step()`**：整个文件的“主厨”，负责端出一道标准化的三明治（动作、目标、值）
  - 输入：`steps_hint`（人写的指令，可能是字符串或字典）、`page`（当前页面名，本函数暂未使用但预留扩展）、`target`/`value`（可选的显式覆盖项）、`page_element_alias_map`（元素别名映射表，比如 `"登录按钮" → "btn-login"`）
  - 输出：一个三元组 `(action: str, target_code: str or None, value: Any)`，例如 `("click", "btn-login", None)` 或 `("goto", None, "/home")`
  - 大白话解释：就像你对智能音箱说“打开灯”“点一下首页的红色按钮”“输入密码123”，它不直接去干活，而是先听懂你说的是哪件事（动作）、对谁干（目标）、要填什么/跳到哪（值），再把这三样打包交给真正的“工人”（比如浏览器操作模块）去执行。

- **`_normalize_action()`**：动作“同义词词典”
  - 输入：任意类型的动作描述（如 `"Tap"`, `"CLICK"`, `"fill in"`）
  - 输出：标准化的小写动作名（如 `"click"`, `"input"`）
  - 大白话解释：不管你说“点”“戳”“按”“tap”，它都统一记作 `"click"`；说“填”“输”“type”，就变成 `"input"`——避免因为措辞不同导致程序不认识。

- **`_split_payload()`**：指令“分词器”
  - 输入：一段带冒号或等号的字符串（如 `"用户名::admin"` 或 `"价格=>>100"`）
  - 输出：`(左侧关键词, 右侧内容)` 元组，比如 `("用户名", "admin")`
  - 大白话解释：看到 `"click:搜索框"` 就拆成动作 `"click"` + 目标 `"搜索框"`；看到 `"assert_text:标题=欢迎回来"` 就拆成目标 `"标题"` + 值 `"欢迎回来"`。

- **`_resolve_target_code()`**：别名“查字典”函数
  - 输入：原始目标名（如 `"登录按钮"`）和别名映射表（如 `{"登录按钮": "btn-login"}`）
  - 输出：查到的真实代码标识符（如 `"btn-login"`），查不到就返回空字符串
  - 大白话解释：测试人员用中文/英文起“昵称”写脚本（更易读），它负责把昵称翻译成程序里真正认得的“身份证号”（如 CSS 选择器或 ID）。

## 🧩 调用关系与数据流转
```
用户输入 steps_hint（如 ["click: 登录按钮", "input: 密码=123"]）
        ↓
resolve_explicit_step() 接收并判断格式：
├─ 若是字典 → 直接取 action/target/value → 进入标准化流程
└─ 若是字符串 → 用 ":" 拆分 → 得到 action_raw + payload → 
        ↓
        _normalize_action(action_raw) → 得到标准动作（如 "click"）
        ↓
        根据动作类型决定怎么处理 payload：
        ├─ goto/login：payload 当作 route 或忽略
        ├─ click/wait_for/assert_visible/assert_text：用 _split_payload(payload) 拆出 target（可能为空）→ 再用 _resolve_target_code() 查真实代码
        ├─ input/assert_metric/assert_url：同样拆 payload → target+value 分离 → target 查别名 → value 保持原样
        ↓
最终返回 (标准化动作, 解析后的目标代码, 值)
```

## 💡 值得学习的写法
- ✅ **多层容错设计**：所有 `_normalized_*` 函数都用 `str(value or "").strip()` 处理 `None`/空值/数字/布尔值，不怕传进来乱七八糟的类型，健壮性拉满。
- ✅ **灵活分隔符支持**：`_split_payload()` 同时支持 `"="`, `"::"`, `"=>"` 等多种分隔符，让写测试的人自由发挥，不用死记硬背一种语法。
- ✅ **动作归一化策略清晰**：用多个 `if in {...}` 分组处理同义词（如 `"click"/"tap"/"press"`），逻辑直白、易维护、好扩展。
- ✅ **提前校验 + 清晰报错**：每一步关键分支都检查必要字段（如 `goto` 必须有 route，`input` 必须有 value），报错信息直接引用原始输入（`f"unsupported explicit step hint: {hint!r}"`），调试时一眼定位问题。

## ⚠️ 需要注意的地方
- ⚠️ `page` 参数在当前函数中完全没被使用！虽然签名里写着，但代码里一句都没用到——可能是为未来扩展预留，也可能是遗漏。调用方如果依赖它传页面上下文，会发现无效。
- ⚠️ `_resolve_target_code()` 返回空字符串 `""` 表示失败，但很多地方只检查 `if not resolved_target:`，容易和合法的空字符串目标混淆（虽然实际中目标一般不会是空字符串，但逻辑上不够严谨）。
- ⚠️ `assert_metric` 的解析逻辑较复杂：先尝试按比较符（`>=`, `==` 等）分割，失败再 fallback 到 `_split_payload`。但如果用户写 `"assert_metric:销售额>100"`，会被正确识别；而写 `"assert_metric:销售额 => 100"`（带空格）就会失败——因为空格破坏了 `">="` 的连续匹配，此时会走 `_split_payload("销售额 => 100")`，结果变成 `("销售额 ", "100")`，左侧多了空格，可能导致查别名失败。
- ⚠️ `resolve_explicit_step()` 强制要求 `steps_hint` 至少有一个有效项（`hints[0]`），但没对 `hints` 是非空列表做深层校验——如果传入 `[None, "click:xx"]`，取 `hints[0]` 仍是 `None`，后续 `_normalized_text(None)` 虽然安全，但语义上可能不是预期行为。