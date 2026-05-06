# 📘 代码说明书
## 一句话概括
这是一个用来“查字典”的工具文件——它把存放在 JSON 文件里的各种案件分类（比如“诈骗”“盗窃”）的编码、名称、别名等信息，整理成方便程序快速查找和转换的结构。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `case_dictionary.py` | 管理案件类型字典：从 JSON 文件加载数据，提供按“种类”（如 `crime_type`）查编码、查名称、查别名、反向解析（输入别名 → 得到标准编码）等功能 |

## 🔍 核心函数/类说明
- **`_normalize_items(items)`**：作用——把原始杂乱的数据（可能有空值、大小写不一、非字典项）变成统一格式的干净列表  
  - 输入：任意类型的数据（通常是 JSON 解析后的 list 或其他乱七八糟的东西）  
  - 输出：一个规范的字典列表，每个字典含 `code`（小写去空格）、`name`（默认用 code 补充）、`enabled`（是否启用）、`aliases`（全转小写去空格的别名列表）  
  - 大白话解释：就像收快递时，快递员把一堆没贴标签、歪斜、带胶带的包裹，统一贴上“编号+名字+是否可用+别名贴纸”，方便你以后一眼认出哪个是哪个。

- **`load_case_dictionaries()`**：作用——一次性读取并缓存整个字典文件（只加载一次，后面都用缓存）  
  - 输入：无（自动读取固定路径的 `case_dictionaries.json`）  
  - 输出：一个大字典，键是种类名（如 `"crime_type"`），值是该种类下所有标准化后的条目列表  
  - 大白话解释：像图书馆管理员每天早上只开一次总书库大门，把所有分类字典（刑法类、民法类…）搬进办公室抽屉里锁好；之后谁来查，都不用再跑书库，直接拉开抽屉翻。

- **`get_dictionary_items(kind)`**：作用——拿到某一种类（如 `"crime_type"`）下所有可用+禁用的条目  
  - 输入：种类名（字符串，大小写不敏感）  
  - 输出：该种类对应的标准化条目列表（每个条目是 `{"code": "...", "name": "...", ...}`）  
  - 大白话解释：你跟管理员说“我要看‘犯罪类型’这一栏的所有卡片”，他立刻从抽屉里拿出一叠，不管上面标着“启用”还是“停用”。

- **`get_code_name_map(kind)`**：作用——生成“编码 → 名称”的快捷查询表（只包含启用的条目）  
  - 输入：种类名  
  - 输出：形如 `{"zhapian": "诈骗", "qieze": "盗窃"}` 的字典  
  - 大白话解释：相当于给每张启用的卡片背面印上“标准名”，你只要报编码（比如 `"zhapian"`），马上知道它叫“诈骗”。

- **`get_alias_code_map(kind)`**：作用——生成“别名或编码 → 标准编码”的映射表（比如输入 `"骗钱"` 或 `"zhapian"`，都返回 `"zhapian"`）  
  - 输入：种类名  
  - 输出：形如 `{"zhapian": "zhapian", "骗钱": "zhapian", "诈骗": "zhapian", "qieze": "qieze", "偷东西": "qieze"}` 的字典  
  - 大白话解释：这是最聪明的“翻译官”——不管你用方言、口语、错别字、缩写还是标准编码来问，它都能把你拉回唯一正确的答案（标准编码）。

- **`resolve_dictionary_code(kind, value)`**：作用——把任意用户输入（如 `"骗钱"`、`" ZHAPIAN "`、`None`）安全地转成标准编码  
  - 输入：种类名 + 待解析的值（字符串/空值等）+ 可选兜底值（fallback）  
  - 输出：匹配到的标准编码，或 fallback（如果没匹配上）  
  - 大白话解释：你随手打了个“我被坑了”，系统默默查表发现 `"坑了"` 在 `"骗钱"` 别名里 → 返回 `"zhapian"`；打错成 `"zhpian"`？查不到 → 返回你设定的默认值（比如 `"unknown"`）。

- **`resolve_dictionary_name(kind, code)`**：作用——把编码（或别名）转成中文名称（带兜底保护）  
  - 输入：种类名 + 编码/别名字符串  
  - 输出：对应中文名，或 fallback（没找到时返回 fallback，找不到还为空就返回原编码）  
  - 大白话解释：你输入 `"zhapian"`，它告诉你叫“诈骗”；你输 `"骗钱"`，它也告诉你叫“诈骗”；你输 `"abc123"`，它老实说“我不知道”，返回你给的 `"暂未定义"`。

## 🧩 调用关系与数据流转
```
[用户调用]  
   ↓  
resolve_dictionary_code("crime_type", "骗钱")  
   ↓ → 先调用 get_alias_code_map("crime_type")  
         ↓ → 内部调用 get_dictionary_items("crime_type")  
               ↓ → 内部调用 load_case_dictionaries()（首次触发加载+缓存）  
                     ↓ → 读取 JSON 文件 → _normalize_items() 清洗数据  
         ← 返回 { "骗钱":"zhapian", "zhapian":"zhapian", ... }  
   ← 查表得 "zhapian"  

同理，resolve_dictionary_name("crime_type", "骗钱")  
   ↓ → 调用 get_code_name_map("crime_type")  
         ↓ → 调用 get_dictionary_items("crime_type")（复用已加载数据）  
               ↓ → 过滤 enabled=True 的条目 → 构建 {"zhapian":"诈骗"}  
         ← 返回映射字典  
   ← 查表得 "诈骗"
```

> ✅ 所有函数都依赖 `get_dictionary_items()`，而它又依赖 `load_case_dictionaries()` 的缓存结果；  
> ✅ `get_alias_code_map()` 和 `get_code_name_map()` 都是“加工缓存数据”，不重复读文件；  
> ✅ `resolve_*` 函数是面向用户的“友好入口”，自带容错（空值/大小写/空白符处理）和 fallback 机制。

## 💡 值得学习的写法
- `@lru_cache(maxsize=1)` 用得恰到好处：整个字典文件只加载一次，后续所有查询都飞快，且线程安全（FastAPI 多请求也不怕重复读文件）。
- `_normalize_items()` 对数据“宽容又坚定”：跳过非列表、非字典项，但对每个合法项强制清洗（`.strip().lower()`），避免前端传参不规范导致崩溃。
- `resolve_*` 函数统一处理 `None`/空字符串/空白符，并做 `.strip().lower()` 标准化，让接口像“傻瓜相机”——怎么拍都出片。
- `get_alias_code_map()` 把 `code` 自己也加进映射（`alias_map[code] = code`），这样无论输编码还是别名，逻辑完全一致，不用分支判断。

## ⚠️ 需要注意的地方
- `_DATA_PATH` 是硬编码路径，如果项目结构变动（比如 `data/` 不在同级目录），会直接报错 `FileNotFoundError`，建议加一层存在性检查或日志提示。
- `json.loads(...)` 没包 `try/except`：若 `case_dictionaries.json` 文件损坏（如多逗号、乱码），程序启动或首次调用时会崩溃，建议在 `load_case_dictionaries()` 中捕获 `json.JSONDecodeError` 并友好报错。
- `get_enabled_codes(kind)` 返回 `set[str]`，但没做 `enabled` 字段存在性兜底（靠 `item.get("enabled", True)` 已处理），不过如果 JSON 里写了 `"enabled": null`，`bool(None)` 是 `False`，可能误判——建议明确注释“`enabled` 应为布尔值，null 视为 False”。
- 所有 `str(...).strip().lower()` 对 `None` 安全（因 `str(None) == "None"`），但业务上可能更希望 `None` 直接跳过，当前逻辑虽能运行，但语义稍隐晦，可考虑加注释说明设计意图。