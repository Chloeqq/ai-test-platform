# 📘 代码说明书
## 一句话概括
这是一个「工作台状态管家」，负责把前端（Web UI）产生的各种操作记录、运行数据、评审决定等，**自动选择存到文件里还是数据库里**，就像一个智能快递员：根据天气（配置）决定用自行车（文件）还是货车（数据库）送货，确保数据不丢、不乱、随时可查。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `workbench_state_store.py` | 统一管理 Web 工作台（如测试运行、人工评审、缺陷关联等）的状态数据存储逻辑，支持「文件存储」和「数据库存储」双模式，并自动切换 |

## 🔍 核心函数/类说明
- **`_resolve_state_backend()`**：作用——读取环境变量 `WORKBENCH_STATE_BACKEND`，决定数据存哪儿（文件 or 数据库）。  
  - 输入：无（只读环境变量）  
  - 输出：字符串 `"file"` 或 `"database"`（若设为 `"auto"`，还会检查数据库连接地址是否是 PostgreSQL）  
  - 大白话解释：就像你家装修时，工长问“水电走明线还是暗线？”，这个函数就是那个工长——它看配置（比如你贴的便签条 `"WORKBENCH_STATE_BACKEND=auto"`），再偷偷瞄一眼“水电总闸”（`DATABASE_URL`），最后拍板：“用暗线（数据库）更稳！”或“明线（文件）够用了”。

- **`_is_db_enabled_for_path(path)`**：作用——判断某个具体数据文件（比如 `history.json`）当前是否该走数据库存储。  
  - 输入：一个 `Path` 对象（如 `HISTORY_FILE`）  
  - 输出：`True`（走数据库）或 `False`（走文件）  
  - 大白话解释：它是个“门禁保安”，手里拿着一张表（6个预设的 JSON 文件路径），还知道当前是“文件模式”还是“数据库模式”。你递上一个文件路径（比如 `defect-links.json`），它立刻查表+查模式，告诉你：“这个归数据库管 ✅” 或 “这个还是放文件夹里 ❌”。

- **`_upsert_db_item(path, item)`**：作用——把一条数据「插入或更新」到数据库对应表中（upsert = insert + update）。  
  - 输入：文件路径（用来找对应数据库表）、一个字典数据（如 `{ "run_id": "r123", "status": "success" }`）  
  - 输出：无（默默写进数据库）  
  - 大白话解释：就像你去奶茶店点单，店员（函数）一看你给的是“订单号 r123”，先翻小本本（查数据库）有没有这单；没有就新建一单；有就改状态、加备注。每种单子（`runtime-runs`、`review-decisions`…）都有专属模板（对应不同数据库模型），它能精准匹配、不填错格子。

- **`read_json_list(path)` / `write_json_list(path, items)`**：作用——统一读/写 JSON 数组文件（如 `history.json` 里存着 `[{}, {}, ...]`），但会自动委托给文件或数据库。  
  - 输入：文件路径 + （写入时）数据列表  
  - 输出：读取时返回 `list[dict]`，写入时无返回  
  - 大白话解释：这是两个“万能插座”。你插上 `HISTORY_FILE`，它自动识别：如果后台设了数据库，就从库里捞最新500条历史；如果设了文件，就打开 `history.json` 读内容。你不用记“今天该调哪个函数”，只管说“我要读历史”——它自己选最合适的路。

- **`append_history(entry)` / `append_runtime_run(entry)` / `update_runtime_run(run_id, updates)`**：作用——对外提供的「傻瓜式」数据操作接口，分别用于：添加一条历史记录、新增/追加一次运行记录、更新某次运行的状态。  
  - 输入：要存的数据（字典）或运行ID+更新字段  
  - 输出：无  
  - 大白话解释：这是给其他程序员用的「快捷按钮」。比如点击“开始测试”，前端调 `append_runtime_run({"run_id":"r456","status":"running"})`，它就自动：① 加时间戳；② 锁住文件防多人同时写乱套；③ 看配置决定存文件还是库；④ 存完最多留1000条（自动截断老数据）。你按一下，它全搞定。

## 🧩 调用关系与数据流转
```
外部调用（如 FastAPI 接口或前端 JS）  
    ↓  
append_history() / append_runtime_run() / update_runtime_run()  
    ↓（都带 FILE_LOCK 防并发）  
→ 先调 _is_db_enabled_for_path() 判断存储方式  
    ├─ 若为 True → 走数据库分支：  
    │     ↓  
    │   _upsert_db_item() 或 _replace_db_items() 或 _read_db_items()  
    │     ↓（通过 SessionLocal 连接数据库）  
    │   SQLAlchemy 操作 WorkbenchXXX 模型表  
    │  
    └─ 若为 False → 走文件分支：  
          ↓  
        _read_file_json_list() 或 直接 json.dumps/json.loads 操作磁盘文件  
          ↓  
        文件内容存于 web-ui/state/... 目录下（如 history.json）
```

## 💡 值得学习的写法
- **双模无缝切换设计**：所有业务函数（`append_*`, `update_*`）完全不关心底层是文件还是数据库，只通过 `_is_db_enabled_for_path()` 和统一的 `_upsert_db_item()` / `_read_db_items()` 封装隔离差异，未来加 Redis 或云存储只需改这几个底层函数。
- **“锁+截断”保稳定**：`append_*` 函数用 `threading.Lock` 防止多线程写同一文件冲突；同时 `items[:500]` / `items[:1000]` 自动限制历史长度，避免 JSON 文件无限膨胀卡死。
- **智能默认值填充**：`append_history()` 自动补 `timestamp`，`append_runtime_run()` 补 `updated_at`，调用方传 `{ "action": "start" }` 就行，不用操心时间字段——减少出错，也更符合直觉。
- **路径即配置**：用常量 `HISTORY_FILE`、`RUNTIME_RUNS_FILE` 等直接关联数据库模型（`_db_model_for_path()`），让“哪个文件对应哪张表”一目了然，增删表只需加一行路径映射，不用改逻辑。

## ⚠️ 需要注意的地方
- **数据库模式下 `update_runtime_run()` 效率隐患**：它先 `_read_db_items()` 把全表数据拉到内存，再遍历找 `run_id` 更新——如果表里有上万条运行记录，会很慢且吃内存！正确做法应直接发 SQL `UPDATE ... WHERE run_id=...`，而不是“全查再遍历”。
- **文件模式无事务保护**：`write_json_list()` 是“先读全文件 → 内存改 → 全写回”，若写入中途崩溃（断电/kill），整个 JSON 文件可能损坏变空或乱码。而数据库有事务保证，文件模式需额外加临时文件 + 原子重命名（如 `history.json.tmp` → `history.json`）。
- **环境变量解析脆弱**：`_resolve_state_backend()` 对 `WORKBENCH_STATE_BACKEND` 值只做简单 `strip().lower()`，若填了 `"FILE "`（末尾空格）或 `"Database"`（大小写混），会直接报 `RuntimeError` 中断服务——建议加 `str(raw).strip().lower()` 并容错提示。
- **`_normalize_payload()` 的隐藏风险**：它把非字典类型（如 `None`、`list`、`str`）转成空字典 `{}`，但 `payload` 字段在数据库里是 JSON 类型，若业务真需要存 `["a","b"]` 或 `null`，这里会静默变成 `{}`，导致数据丢失且难以排查。