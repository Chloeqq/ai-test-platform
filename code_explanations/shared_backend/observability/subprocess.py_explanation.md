# 📘 代码说明书
## 一句话概括  
这是一个“带日志监控的子进程执行器”——它像一位细心的项目经理，帮你安全、透明地运行外部命令（比如 `git clone`、`python script.py`），同时全程记录每一步发生了什么，并确保不会卡死或丢失日志。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `observability/subprocess.py` | 提供一个增强版的 `subprocess.run()`：自动打日志（含请求 ID 追踪）、实时捕获 stdout/stderr、超时自动杀进程、线程安全、日志内容智能截断防刷屏 |

## 🔍 核心函数/类说明
- **`_summarize_subprocess_output(text, max_length=1200)`**：作用是对长文本（比如 10MB 的编译日志）做“智能压缩”，只留开头关键部分 + 省略号，避免日志被撑爆。  
  - 输入：一串字符串（如 `stdout` 内容），最大允许长度（默认 1200 字符）  
  - 输出：截断后的字符串（例如 `"Starting build... [500 more chars] ... Done. ✅"`）  
  - 大白话解释：就像微信转发长文章时只显示前几行+“全文请点击查看”，防止日志里全是滚动刷屏的无用信息。

- **`run_logged_subprocess(...)`**：作用是「安全、可追踪、可调试地运行一条命令」，是本文件真正的主角。  
  - 输入：命令参数列表（如 `["ls", "-l", "/tmp"]`）、工作目录、环境变量、超时时间、日志前缀等  
  - 输出：标准的 `subprocess.CompletedProcess` 对象（含 `returncode`、`stdout`、`stderr`）  
  - 大白话解释：它不只是跑命令，而是给你配了「三件套」——① 开跑前大声报备（日志里记下命令和超时）；② 边跑边直播输出（每行 stdout/stderr 都立刻记日志，还带上当前请求 ID）；③ 超时了立刻拔电源（`kill` 进程）+ 善后（等线程收尾），最后还给你一份带摘要的结案报告。特别适合在 Web 后端（比如 FastAPI 接口里）调用外部工具，出了问题一眼就能定位是哪次请求、哪条命令、卡在哪一步。

## 🧩 调用关系与数据流转  
```
用户调用 run_logged_subprocess(["git", "pull"])  
       ↓  
1. 先记一条「开始日志」→ 包含命令、路径、超时、request_id  
       ↓  
2. 用 subprocess.Popen 启动命令，但不直接 wait()，而是把 stdout/stderr 当成「流水线」  
       ↓  
3. 启动两个后台小工人（线程）：  
   ├─ stdout 工人 → 一行行读 stdout → 存进 stdout_chunks 列表 + 每行都记 INFO 日志  
   └─ stderr 工人 → 一行行读 stderr → 存进 stderr_chunks 列表 + 每行都记 WARNING 日志  
       ↓  
4. 主线程等进程结束（或超时）：  
   ├─ ✅ 正常结束 → 收集所有 chunk → 拼成完整 stdout/stderr → 记「结束日志」→ 返回 CompletedProcess  
   └─ ⚠️ 超时了 → 主动 kill 进程 → 等工人线程最多 5 秒收工 → 记「超时警告日志」→ 抛出带完整输出的 TimeoutExpired 异常  
       ↓  
5. 无论成功失败，最后都确保两个工人线程彻底退出（join）
```

## 💡 值得学习的写法
- **用 `daemon=True` 线程 + `thread.join(timeout=5)` 做优雅收尾**：工人线程不阻塞主程序，超时后也不死等，既保证日志尽量不丢，又避免主线程被拖住 —— 像快递员送完最后一单，公司允许他 5 分钟内打卡下班，超时就自动锁门。
- **`set_request_id(captured_request_id)` 在子线程里手动恢复请求 ID**：因为 Python 线程不自动继承父线程的上下文变量（如 `contextvars`），这里显式恢复，确保 `stderr` 日志里也能看到正确的 `request_id` —— 就像每个分店员工上岗前，都要戴上总部发的工牌，不然查不到是谁干的。
- **`iter(stream.readline, "")` 实现非阻塞逐行读取**：不用 `readlines()` 一次性加载全部（怕内存炸），也不用 `read(1)` 太慢，而是“有新行就读一行，没新行就等”，平衡了实时性和内存占用。
- **日志中用 `log_prefix` 统一标记来源**：同一个函数既能当 `git` 工具用，也能当 `docker build` 工具用，只需换前缀，日志一目了然，方便 grep 过滤。

## ⚠️ 需要注意的地方
- **`bufsize=1` + `text=True` 是必须搭配的**：`bufsize=1` 表示行缓冲（遇到 `\n` 就刷出），配合 `text=True` 才能让 `readline()` 正常工作；如果漏掉 `text=True`，`readline()` 会返回 `bytes`，而日志函数期望 `str`，直接报错。
- **`subprocess.Popen` 的 `env` 参数不会自动继承父进程环境**：如果传了 `env={}`，就会清空所有环境变量（连 `PATH` 都没了），导致 `ls`、`python` 找不到。正确做法是 `env = {**os.environ, "MY_VAR": "1"}` 或用 `os.environ.copy()`。
- **`threading.Thread(daemon=True)` 的风险**：主线程退出时，daemon 线程会被强制杀死 —— 如果你在脚本末尾直接 `exit()`，可能来不及打印最后几行日志。生产环境建议用 `atexit` 或显式 `join()` 确保收尾。
- **`summarize_log_value` 截断逻辑对二进制内容不友好**：虽然代码里 `text=True` 保证了输入是字符串，但如果子进程输出了乱码或特殊 Unicode（如 emoji + 中文混排），`len()` 计算字符数可能和终端显示宽度不一致，导致摘要“砍”在中间 —— 不影响功能，但日志可读性略降。