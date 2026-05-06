# 📘 代码说明书
## 一句话概括
这个文件是项目工作台的“项目管家”，负责统一整理、校验和确保可用的所有项目（比如“mall”“shop”等），它从数据库、本地文件夹等多个地方收集项目信息，并保证你要操作的项目一定存在且能写入。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `workbench_project_service.py` | 管理所有项目的基本信息（编码、名称、状态、来源），提供「列出项目」「获取项目编码列表」「确保项目可写」三大功能，是前端或工作台逻辑调用项目数据的统一入口 |

## 🔍 核心函数/类说明
- **`_normalize_project_code(value: str) -> str`**：作用是把用户随便输的项目名（比如 `"mall-2024!"` 或 `"  SHOP_1 "`）变成干净、安全、统一的小写编码（如 `"mall2024"` 或 `"shop1"`）  
  - 输入：任意字符串（甚至空、None、带符号、大小混杂）  
  - 输出：2–10位纯字母数字的小写字符串（如 `"mall"`）  
  - 大白话解释：就像你给快递填收货地址时，系统自动帮你把“上海市·浦东新区——张江路123号（A栋）”简化成“上海浦东张江路123号”，去掉标点、空格、大小写干扰，只留核心标识；如果简化后太短（<2字）或太长（>10字），就直接报错，防止乱码项目名污染系统。

- **`list_project_items(db: Session, *, state_root: Path | None = None) -> list[dict]`**：作用是“拉出一张当前所有项目的完整花名册”，包含项目编码、名字、状态、来源四要素  
  - 输入：数据库连接 `db`（查数据库里的项目）、可选的 `state_root`（一个本地文件夹路径，比如存着老项目配置的目录）  
  - 输出：一个列表，每个元素是类似 `{"project_code": "mall", "project_name": "MALL", "status": "active", "source": "default"}` 的字典  
  - 大白话解释：它像一位细心的档案管理员，按顺序翻三本册子：① 先记下默认项目“mall”；② 再去数据库里抄一份正式项目名单；③ 如果你还指定了一个“老文件夹”，它还会进去看看里面每个子文件夹名（比如 `order/` `user/`）是不是也能当项目用。全程自动去重、自动标准化、自动补默认值，最后交给你一份整齐的总表。

- **`list_project_codes(db: Session, *, state_root: Path | None = None) -> list[str]`**：作用是从花名册里只抽出“项目编码”这一列，变成简单字符串列表  
  - 输入：同上（`db` 和可选的 `state_root`）  
  - 输出：如 `["mall", "order", "user"]`  
  - 大白话解释：就像你只需要员工工号列表发给HR做权限配置，不关心姓名和部门——它只是对 `list_project_items` 的结果做了个“一键提取工号”操作，非常轻量。

- **`ensure_project_writable(db: Session, project_code: str) -> str`**：作用是“保底创建+激活项目”，确保你要写的那个项目不仅存在，而且处于可编辑状态  
  - 输入：数据库连接 `db` + 用户想操作的原始项目编码（比如 `"SHOP-2024"`）  
  - 输出：标准化后的项目编码（如 `"shop2024"`）  
  - 大白话解释：就像你去租办公室，前台先查系统有没有“302室”——没有？立刻帮你登记一间；有？再确认这间现在没被锁住（即状态是 active）。整个过程全自动，你只要说“我要用 shop-2024”，它就确保你能往里存文件、改配置，绝不卡壳。

## 🧩 调用关系与数据流转
```
外部调用（如 FastAPI 接口 / 前端按钮）
        ↓
ensure_project_writable() 
   → 先调用 _normalize_project_code() 标准化输入
   → 再调用 list_project_items() 获取当前所有项目编码集合
   → 若不在集合中 → 调用 test_project_service.create_project() 创建新项目
   → 最后调用 test_project_service.ensure_project_active_for_write() 激活项目

list_project_codes() 
   → 直接调用 list_project_items() 得到完整列表，再用列表推导式抽字段

list_project_items()
   → 反复调用 _normalize_project_code() 标准化每个项目编码
   → 调用 test_project_service.list_projects(db) 查数据库项目
   → （可选）遍历 state_root 文件夹读取本地目录名作为项目
   → 所有项目统一 add() 到 items 列表（内部闭包函数）
```

## 💡 值得学习的写法
- **闭包函数 `add()` 封装重复逻辑**：在 `list_project_items` 里定义了一个内部 `add()` 函数，统一处理“标准化→去重→组装字典→追加”，避免三处遍历逻辑重复写校验和拼接代码，干净又不易出错。
- **防御式默认值链式处理**：如 `str(project_name or normalized.upper()).strip() or normalized.upper()` —— 先尝试用传入的名字，为空就用编码大写，再防一手空格，最后兜底还是大写，层层保险，不怕上游传 `None` 或空字符串。
- **`seen: set[str]` 实现高效去重**：用集合记录已添加的编码，O(1) 判断是否重复，比每次遍历列表快得多，尤其项目多时优势明显。
- **`state_root` 可选但健壮处理**：用 `if state_root and state_root.exists():` 双重检查，既支持不传（`None`），也防传了错误路径，体现对调用方的宽容。

## ⚠️ 需要注意的地方
- **`_normalize_project_code` 抛异常但上层静默吞掉**：在 `list_project_items` 的 `add()` 里，如果标准化失败（如空字符串、超长），会 `raise ValueError`，但被 `except ValueError: return` 吞掉——这意味着坏项目名不会报错，而是悄悄消失。如果后期需要审计“哪些项目被过滤了”，这里会丢失线索。
- **`list_project_items` 可能重复添加 DEFAULT_PROJECT_CODE**：开头加了一次默认项目，结尾又有个 `if not items:` 再加一次——虽然概率极低（除非数据库和文件夹全空且 `state_root` 无效），但逻辑稍显冗余，容易让人困惑“到底谁才是最终兜底”。
- **`ensure_project_writable` 中两次调用 `list_project_items()`**：一次在 `existing_codes = {...}` 构建集合，另一次在 `test_project_service.ensure_project_active_for_write()` 内部可能再次调用（取决于该函数实现）——若未缓存，会造成重复查询数据库，影响性能，建议考虑加缓存或重构为单次获取。
- **硬编码 `DEFAULT_PROJECT_CODE = "mall"`**：虽是常量，但若未来要支持多环境（开发/测试/生产默认不同），这种写法会让切换困难，建议抽到配置文件或环境变量中。