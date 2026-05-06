# 📘 代码说明书
## 一句话概括
这是一个为工作台生成系统（Workbench Generation）量身定制的「调试日志工具包」，它像一个安静的幕后观察员，在开发时自动记录关键步骤的数据快照、对比变化、生成唯一追踪ID，并把所有调试信息整齐存进文件或打印到日志里，帮程序员快速定位“数据哪一步悄悄变了”。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `workbench_generation_compiler/debug.py` | 提供一整套轻量、线程安全、可开关的调试能力：判断是否开启调试、生成稳定ID、深拷贝/摘要数据、比对字典/列表差异、自动写入调试日志行。 |

## 🔍 核心函数/类说明
- **`debug_enabled()`**：作用——检查环境变量 `WORKBENCH_GENERATION_DEBUG` 是否被设为真值（如 `"1"`、`"true"`、`"yes"`），决定是否启用整套调试功能。  
  - 输入：无  
  - 输出：`True` 或 `False`（布尔值）  
  - 大白话解释：就像电灯的总开关——你没在电脑里设置 `WORKBENCH_GENERATION_DEBUG=1`，这整套调试功能就完全不运行，不占资源、不写日志、不锁线程，彻底静音。

- **`build_trace_id(*, stage: str, payload: Any)`**：作用——为每一次调试事件生成一个「指纹级唯一ID」，确保同一逻辑流程（比如“解析模板”→“生成代码”→“校验输出”）中的每一步都能被准确串起来追踪。  
  - 输入：`stage`（当前阶段名，如 `"parse"`）、`payload`（当前传入的数据，比如一个配置字典）  
  - 输出：形如 `wbgen-a1b2c3d4e5f67890` 的16位短哈希ID  
  - 大白话解释：就像快递单号——不同包裹（不同 stage+数据）一定有不同单号；相同包裹哪怕重发一次，单号也一样（因为用了稳定 JSON 序列化），方便你查“这个输入对应的全过程日志在哪”。

- **`digest_payload(payload: Any)`**：作用——给任意数据算出一个简短、稳定的「内容指纹」（前16位 SHA256），用来快速判断两个数据是否“长得一样”。  
  - 输入：任意 Python 数据（字典、列表、字符串、数字等）  
  - 输出：16位小写十六进制字符串（如 `"a1b2c3d4e5f67890"`）  
  - 大白话解释：就像给一本书生成“文字指纹”——不管书是横排还是竖排、加了空格还是没加，只要内容一字不差，指纹就完全一样；内容差一个标点，指纹就天差地别。避免用 `str(dict)` 这种靠不住的方式比对。

- **`_json_clone(value: Any)`**：作用——尝试用 JSON 方式做一次“干净深拷贝”（先转成 JSON 字符串再解析回来），失败则退化为 `copy.deepcopy`。  
  - 输入：任意数据  
  - 输出：一份内存独立、结构相同的新副本  
  - 大白话解释：就像给一张照片做高清复印——复印后原图被涂改，复印件还保持原样；特别适合保存调试快照，防止后续代码意外修改了原始数据导致日志记录失真。

- **`_diff_summary(left: Any, right: Any)`**：作用——智能对比两份数据（支持 dict/list/普通值），只告诉你“哪里不一样”，且严格限制输出长度（最多20个键），避免日志爆炸。  
  - 输入：两个待比较的数据  
  - 输出：一个精简的差异报告字典（含新增/删除/变更的 key 列表，或长度变化、是否相等）  
  - 大白话解释：就像 Word 的“比较文档”功能——不显示全文，只高亮告诉你：“第3行少了 `timeout` 字段，`headers` 字典里 `Content-Type` 值从 `text/plain` 变成了 `application/json`”，一眼抓住重点。

- **`log_debug_event(...)`**：作用——整个模块的「门面函数」，负责收集成熟的调试事件（事件名、trace_id、数据、对比目标等），生成结构化日志行，同时写入 Python 日志和本地 `.jsonl` 文件。  
  - 输入：`logger`（日志器）、`event`（事件名如 `"template.resolved"`）、`trace_id`（追踪ID）、`payload`（当前数据）、`extra`（可选：含 `compare_with_event` 等辅助信息）  
  - 输出：无（副作用：打日志 + 写文件）  
  - 大白话解释：就像调试日记本的“记事按钮”——你按一下（调一次这个函数），它就自动：① 把当前数据拍个快照存好；② 如果你想跟上一步比，它就翻出上一步的快照；③ 算出两者的差异；④ 把所有信息打包成一行标准 JSON；⑤ 同时写进控制台日志和硬盘文件，随时可查。

## 🧩 调用关系与数据流转
```
用户代码调用 log_debug_event(...)  
        ↓  
→ 检查 debug_enabled() → 若为 False，直接返回（不执行任何操作）  
→ 若为 True：  
　　├─ 用 _layer_from_event() 提取 event 名的首段（如 "template.resolved" → "template"）作为分层标签  
　　├─ 用 _json_clone() 对 payload 做安全快照 → payload_snapshot  
　　├─ 用 _SNAPSHOT_LOCK 加锁 → 安全地把 (trace_id, event) → payload_snapshot 存入全局字典 _SNAPSHOTS  
　　├─ 若 extra 中指定 compare_with_event：  
　　│　　　└─ 从 _SNAPSHOTS 中尝试取出 (trace_id, compare_with_event) 对应的旧快照 → compare_snapshot  
　　├─ 用 summarize_payload() 分别生成 payload 和 compare_snapshot 的摘要（含类型、指纹、key 列表等）  
　　├─ 用 _diff_summary() 计算两者差异  
　　├─ 组装 event_payload 字典（含 event、layer、trace_id、summary、diff_summary 等）  
　　├─ 用 _to_stable_json() 序列化成标准 JSON 字符串  
　　├─ logger.info() 打印到日志（带固定前缀 "workbench_generation_debug"）  
　　└─ _append_debug_file_line() 写入 /tmp/workbench_generation_debug.jsonl（或自定义路径）
```

## 💡 值得学习的写法
- ✅ **环境变量开关 + 集中式判断**：`debug_enabled()` 作为统一入口，所有调试逻辑都先过它，确保关闭时零开销（连字符串拼接、锁、IO 都跳过），比每个函数里写 `if os.getenv(...)` 更干净、更可靠。  
- ✅ **JSON 优先深拷贝 `_json_clone`**：用 `json.dumps` + `json.loads` 实现“语义深拷贝”，天然过滤掉不可 JSON 序列化的对象（如函数、socket），且结果更规范（key 排序、无多余空格）；失败时优雅降级到 `deepcopy`，兼顾鲁棒性。  
- ✅ **线程安全快照池 `_SNAPSHOT_LOCK` + `_SNAPSHOTS`**：用极简的全局字典 + 细粒度锁，实现跨函数、跨线程的数据快照共享，让 `A` 函数存、`B` 函数取成为可能，是实现“前后步对比”的基石。  
- ✅ **`.jsonl` 文件格式设计**：每次调用 `_append_debug_file_line()` 写一行 JSON，不换行、不逗号、不括号——这种格式可逐行读取、易用 `grep` 查找、兼容大数据工具（如 jq、pandas.read_json(lines=True)），比单个大 JSON 更实用。  
- ✅ **差异报告智能截断**：`_diff_summary` 对 dict 的 `added_keys`/`removed_keys`/`changed_keys` 明确限制 `[:20]`，防止单次日志撑爆屏幕或文件，体现对生产环境友好性。

## ⚠️ 需要注意的地方
- ⚠️ **`_SNAPSHOTS` 是全局可变状态**：虽然加了锁，但如果多个 trace_id 混用同一个 `event` 名（比如都叫 `"step1"`），会导致快照被覆盖。务必确保 `event` 在同一 `trace_id` 下是唯一的（推荐用 `"module.step_name"` 格式）。  
- ⚠️ **`_to_stable_json` 的 `default=str` 有信息损失**：当遇到无法 JSON 序列化的对象（如自定义类实例、datetime），会调用 `repr()` 或 `str()`，可能导致摘要指纹失效（两个不同对象 `str()` 结果相同）。若需精准对比，应在 `payload` 传入前做标准化（如转成 dict）。  
- ⚠️ **`_debug_output_file()` 默认写入 `/tmp/`**：Linux/macOS 临时目录可能被系统清理，且 Windows 上 `/tmp` 路径无效；若需长期保留，必须通过 `WORKBENCH_GENERATION_DEBUG_FILE` 环境变量显式指定绝对路径（如 `~/debug.jsonl`）。  
- ⚠️ **`log_debug_event` 不捕获异常**：内部 `_append_debug_file_line()` 发生 IO 错误（如磁盘满、权限不足）会被静默吞掉（`except Exception: return`），可能让你误以为日志写入成功。建议在关键场景额外检查文件是否真实增长。  
- ⚠️ **`_layer_from_event("a.b.c")` 只取第一段**：`split(".", 1)[0]` 逻辑简单，但若 `event="api.v1.users.create"`，`layer` 就是 `"api"`，而非 `"api.v1"`；如果需要多级分层，需调整此逻辑。