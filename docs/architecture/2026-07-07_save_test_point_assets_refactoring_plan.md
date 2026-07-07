# save_test_point_assets_service.py 静态审计与重构方案

> **日期：** 2026-07-07
> **审计范围：** `apps/web-ui-service/app/services/workbench_generation_api/save_test_point_assets_service.py`（841行）
> **关联模块：** `constants.py`, `context.py`, `repository.py`, `usecase_factory.py`, `shared_backend/*`
> **最后更新：** 2026-07-07（Phase 1 + Phase 2 完成）

---

## 进度总览

| 阶段 | 状态 | 完成日期 | 测试结果 |
|------|------|---------|---------|
| Phase 1：常量化 + 消除硬编码 | ✅ 完成 | 2026-07-07 | 267 passed |
| Phase 2：模块拆分 + DB 读路径 | ✅ 完成 | 2026-07-07 | 267 passed |
| Phase 3：规则引擎化 + 公共库统一 | ⬜ 待开始 | - | - |

### Phase 1 完成详情

**变更文件：**
- `constants.py`：+4 常量（`ASSERT_VISIBLE_FALLBACK_TEXT`, `ASSERT_URL_FALLBACK_TEXT`, `ASSERT_TEXT_FALLBACK_TEXT`, `SAVED_BY`）
- `save_test_point_assets_service.py`：~40 处硬编码已替换为常量

**替换明细：**

| 类别 | 数量 | 示例 |
|------|------|------|
| `"element:"` → `_c.ELEMENT_PREFIX` | 7 | `"element:home_menu"` → `f"{ELEMENT_PREFIX}{HOME_ELEMENT_CODE}"` |
| action 字符串 → `ACTION_*` | 10 | `"input"` → `ACTION_INPUT` |
| source_type → `_c.SOURCE_TYPE_*` | 6 | `"inline"` → `_c.SOURCE_TYPE_INLINE` |
| 密码可见性 → `_c.PASSWORD_*` | 6 | `"text"` → `_c.PASSWORD_VISIBILITY_TEXT` |
| 展示名/raw_text → `_c.*` | 8 | `"首页菜单"` → `_c.HOME_ELEMENT_NAME` |
| 消息模板 → `_c.MSG_*` | 6 | f-string → `_c.MSG_*.format()` |
| steps_hint → `format_steps_hint()` | 5 | `f"click:{name}"` → `format_steps_hint(ACTION_CLICK, name)` |
| 默认值/其他 | 5 | `"P1"` → `_c.DEFAULT_PRIORITY`, `"mall"` 默认值移除 |

**保留未改（Phase 2 处理）：**
- `_LOGIN_ELEMENT_RULES`：整个元组留到 Phase 2 改为 DB 驱动

**新增导入：** `ACTION_ASSERT_ATTRIBUTE`, `ACTION_CANDIDATE`（来自 `shared_backend.step_fields`）

---

### Phase 2 完成详情（2026-07-07）

**目标：按职责拆分文件，元素从 DB 读取（三层回退）**

**新建模块（8 个新文件）：**

| 文件 | 行数 | 职责 |
|------|------|------|
| `save_service.py` | 331 | SaveTestPointAssetsService 精简入口 |
| `elements/loader.py` | 124 | DB→YAML→默认 三层回退加载 alias_map |
| `elements/resolver.py` | 74 | ElementResolver 替换硬编码 _LOGIN_ELEMENT_RULES |
| `steps/structurer.py` | 327 | structured_steps_from_candidate 核心函数 |
| `hooks/base.py` | 30 | PageHook ABC 基类 |
| `hooks/login_password_visibility.py` | 115 | 登录页密码可见性 Hook |
| `compilation/point_builder.py` | 135 | build_point + _resolve_involved_element_codes |
| `compilation/precondition.py` | 25 | fallback_precondition |
| `assets/preview.py` | 65 | 预览数据加载 |
| `assets/queries.py` | 50 | 存量资产查询 |
| `assets/coverage.py` | 85 | 覆盖率矩阵 |
| `assets/statistics.py` | 27 | 统计工具 |

**改造文件：**

| 文件 | 变更 |
|------|------|
| `save_test_point_assets_service.py` | 841行 → 70行（纯 re-export 后向兼容层） |
| `usecase_factory.py` | import 路径改为 `save_service` |
| `constants.py` | Phase 1 新增常量 |

**关键变化：**

| 变化 | 旧 | 新 |
|------|----|----|
| 元素来源 | `_LOGIN_ELEMENT_RULES` 硬编码 | `loader.load_alias_map(db, project, page)` 从 DB 加载 |
| 元素解析 | `_login_element_from_text()` | `ElementResolver(alias_map).resolve(text)` |
| 密码可见性 | 内联 `if element_code == "login-password-toggle-btn"` | `PageHook.post_click_assertions()` |
| DB 读路径 | 无 | `execute()` 入口加载 alias_map，注入调用链 |
| 回退策略 | 无 | DB → YAML资产 → 默认login页映射 |

**测试结果：** 267 passed, 0 failed（Docker 环境验证通过）

---

## 1. 硬编码清单

### 1.1 元素规则（_LOGIN_ELEMENT_RULES）— 风险：高

| 行号 | 硬编码值 | 类别 | 处理建议 |
|------|---------|------|---------|
| 109-115 | 整个 `_LOGIN_ELEMENT_RULES` 元组（5条规则 × 4字段 = 20个字符串） | 元素码/别名/展示名 | **DB化**：从 `page_elements` 表 + `element_naming` 推导 |

当前问题：元素别名、展示名、data_key 全部硬编码。`element_naming.py` 已有 `element_display_name()` 和 `element_data_key()` 能从 element_code 自动推导。别名应来自 DB 的 `page_elements.aliases_json` 字段。

### 1.2 Action 字符串 — 风险：中

| 行号 | 硬编码值 | shared_backend 已有常量 | 处理建议 |
|------|---------|----------------------|---------|
| 166 | `"assert_attribute"` | `ACTION_ASSERT_ATTRIBUTE` | **常量化** |
| 193, 300 | `"input"` | `ACTION_INPUT` | **常量化** |
| 205, 338 | `"click"` | `ACTION_CLICK` | **常量化** |
| 360 | `"goto"` | `ACTION_GOTO` | **常量化** |
| 370, 424 | `"candidate_step"` | `ACTION_CANDIDATE` | **常量化** |
| 381 | `"assert_visible"` | `ACTION_ASSERT_VISIBLE` | **常量化** |
| 414 | `"assert_url"` | `ACTION_ASSERT_URL` | **常量化** |

> 注：`step_fields.py` 已导入但未使用这些常量。

### 1.3 `"element:"` 前缀 — 风险：中

| 行号 | 出现形式 | 处理建议 |
|------|---------|---------|
| 167, 194, 207 | `"element:login-password-input"` | `f"{_c.ELEMENT_PREFIX}{_c.LOGIN_PASSWORD_INPUT_CODE}"` |
| 301 | `f"element:{element_code}"` | `f"{_c.ELEMENT_PREFIX}{element_code}"` |
| 339 | `f"element:{element_code}"` | `f"{_c.ELEMENT_PREFIX}{element_code}"` |
| 383 | `"element:home_menu"` | `f"{_c.ELEMENT_PREFIX}{_c.HOME_ELEMENT_CODE}"` |
| 400 | `f"element:{target_code}"` | `f"{_c.ELEMENT_PREFIX}{target_code}"` |
| 288 | `.removeprefix("element:")` | `.removeprefix(_c.ELEMENT_PREFIX)` |

`constants.py:145` 已定义 `ELEMENT_PREFIX = "element:"`，但未被使用。

### 1.4 展示名/raw_text — 风险：中

| 行号 | 值 | constants.py 已有常量 | 处理建议 |
|------|---|-------------------|---------|
| 168 | `"密码输入框"` | `LOGIN_PASSWORD_INPUT_NAME` | **常量化** |
| 195 | `"密码输入框"` | 同上 | **常量化** |
| 208 | `"显示/隐藏眼睛图标"` | `LOGIN_PASSWORD_TOGGLE_NAME` | **常量化** |
| 384 | `"首页菜单"` | `HOME_ELEMENT_NAME` | **常量化** |
| 385 | `"校验首页菜单可见"` | 缺失 | 常量化为 `ASSERT_VISIBLE_FALLBACK_TEXT` |
| 416 | `"校验仍停留在登录页"` | 缺失 | 常量化为 `ASSERT_URL_FALLBACK_TEXT` |
| 198 | `"建立前置条件：先输入密码"` | `RAW_TEXT_PRERCOND_INPUT` | **常量化** |
| 209 | `"建立前置条件：点击眼睛图标切换为明文"` | `RAW_TEXT_PRERCOND_TOGGLE` | **常量化** |

### 1.5 data_ref / source_type — 风险：中

| 行号 | 值 | constants.py 已有常量 | 处理建议 |
|------|---|-------------------|---------|
| 196 | `"data_ref": "password"` | `PASSWORD_DATA_REF` | **常量化** |
| 284 | `data["password"]` | 同上 | **常量化** |
| 284, 308, 324 | `"source_type": "inline"` | `SOURCE_TYPE_INLINE` | **常量化** |
| 739 | `"source_type": "selection_save"` | `SOURCE_TYPE_SELECTION_SAVE` | **常量化** |

### 1.6 路由/URL — 风险：高

| 行号 | 值 | 处理建议 |
|------|---|---------|
| 361 | `_c.GOTO_DEFAULT_ROUTE` → `"#/home"` | 应从页面对象 `route_pattern` 字段读取 |
| 413 | `_c.ASSERT_URL_FALLBACK` → `"#/login"` | 应从页面对象配置读取 |

### 1.7 密码可见性方向判断 — 风险：中

| 行号 | 值 | 处理建议 |
|------|---|---------|
| 156, 162 | `"text"` | `_c.PASSWORD_VISIBILITY_TEXT` |
| 158, 164 | `"password"` | `_c.PASSWORD_VISIBILITY_PASSWORD` |
| 169 | `"attribute": "type"` | `_c.ASSERT_ATTR_TYPE` |

### 1.8 警告/错误消息 — 风险：低

| 行号 | 硬编码消息 | constants.py 已有 | 处理建议 |
|------|----------|----------------|---------|
| 311 | `f"{element_name} 的空格输入..."` | `MSG_SPACE_INPUT_STEPS_HINT_LIMITATION` | 使用 `_c.MSG_*.format()` |
| 329 | `f"{element_name} 输入步骤缺少..."` | `MSG_INPUT_STEP_MISSING_DATA` | 同上 |
| 376 | `f"步骤仍需人工结构化：{step_text}"` | `MSG_NEEDS_MANUAL_STRUCTURING` | 同上 |
| 425 | `"缺少可结构化步骤。"` | `MSG_NO_STRUCTURABLE_STEPS` | **常量化** |
| 494 | `"缺少结构化步骤。"` | `MSG_STEPS_MISSING` | **常量化** |
| 496 | `"缺少涉及元素。"` | `MSG_ELEMENTS_MISSING` | **常量化** |

### 1.9 其他 — 风险：低

| 行号 | 值 | 处理建议 |
|------|---|---------|
| 635 | 默认项目 `"mall"` | 删除默认值，project 必填校验已在后续代码中 |
| 686 | `"selected_candidates exceeds max size 200"` | 使用 `f"...{_c.MAX_CANDIDATES}"` |
| 726 | `f"{page} 页面测试点资产集"` | 使用 `_c.asset_title_for_page(page)` |
| 758 | `"saved_by": "web_ui_service"` | 常量化 |

---

## 2. 架构问题总结

### 2.1 职责耦合严重（风险：高）

当前 `save_test_point_assets_service.py`（841行）承担了至少 5 个职责：

| 职责 | 行数 | 说明 |
|------|------|------|
| 元素识别与匹配 | ~120行 | `_LOGIN_ELEMENT_RULES` + `_login_element_from_text` |
| 步骤分类与结构化 | ~180行 | `_structured_steps_from_candidate`：input/click/goto/assert分支 |
| 密码可见性逻辑 | ~80行 | `_password_visibility_*`：登录页专属逻辑硬编码在通用服务中 |
| 测试点编译 | ~80行 | `_build_point`：字段提取+组装 |
| 资产编排与持久化 | ~200行 | `SaveTestPointAssetsService.execute`：校验→编译→文件写→DB写 |

### 2.2 页面逻辑硬编码（风险：高）

`_LOGIN_ELEMENT_RULES` 将 login 页面的元素规则硬编码在服务代码中。每新增一个页面都需要改代码。正确的做法是从 DB 的 `page_elements` 表加载。

### 2.3 重复规则体系（风险：中）

存在两套平行的"值来源"体系：

1. **`_input_value_from_text`**：从自然语言步骤文本中提取输入值（正则匹配）
2. **`hint_value_map`**：从 AI 生成的 `steps_hint` 协议解析值（`input:target=value`）

这两套体系都在 `_structured_steps_from_candidate` 中被调用，hint_value_map 仅作为 fallback_value_map 的兜底。但二者的解析逻辑各自独立，缺乏统一的数据源抽象。

### 2.4 数据库读路径缺失（风险：高）

当前 `SaveTestPointAssetsService.execute()` 的数据流：

```
前端 payload → 编译 point → 写文件 → 写DB ✓
```

但元素解析时：

```
步骤文本 → _login_element_from_text → 硬编码 _LOGIN_ELEMENT_RULES ✗
```

元素信息完全来自硬编码，**不从 DB 读取**。`shared_backend/page_object_queries.py` 的 `fetch_page_object_id` / `fetch_page_elements` 以及 `PageObjectRepository` 都已就绪，但未被调用。

### 2.5 steps_hint 隐式协议依赖（风险：中）

`steps_hint` 格式 `action:target=value` 在多处手工拼接（f-string），而非统一通过 `format_steps_hint()`。一处格式变更需要改多处。

### 2.6 不可扩展的 if-else 规则链（风险：中）

`_structured_steps_from_candidate` 和 `_build_expected_assertions` 中的 action 分类逻辑是线性 if-elif 链。新增 action 类型需要修改核心函数。

---

## 3. 可复用公共函数（已有但未使用/未统一）

### 3.1 本文件内可提取到 shared_backend 的函数

| 函数 | 重复次数（跨代码库） | 建议归宿 |
|------|-------------------|---------|
| `_list_text` | 4处 | `type_utils.py` → `as_text_list(value) -> list[str]` |
| `_append_unique` | 3处 | `type_utils.py` → `append_unique(items, value)` |
| `_input_value_from_text` | 1处（但通用性强） | `text_utils.py` → `extract_input_value(text) -> tuple[bool, Any]` |
| `_data_ref_for_element` | 1处 | 委托给 `element_naming.element_data_key()`，自身逻辑可废弃 |

### 3.2 已导入但未使用的 shared_backend 常量

`step_fields.py` 导入了 `ACTION_INPUT`, `ACTION_CLICK`, `ACTION_GOTO`, `ACTION_ASSERT_VISIBLE`, `ACTION_ASSERT_TEXT`, `ACTION_ASSERT_URL`, `format_steps_hint` — **全部未使用**，仍用原始字符串。

### 3.3 已有但未被本文件调用的 DB 读路径

| 模块 | 函数 | 用途 |
|------|------|------|
| `shared_backend/page_object_queries` | `fetch_page_object_id()`, `fetch_page_elements()` | 从DB查页面对象和元素 |
| `app/repositories/page_object_repository` | `get_by_identity()`, `list_elements_by_page_object_id()` | ORM方式查页面对象和元素 |
| `shared_backend/element_binding` | `build_element_alias_map()`, `resolve_element_code()` | 构建别名映射并解析元素 |

---

## 4. DB 数据流分析

### 4.1 当前状态

```
┌──────────┐    ┌──────────────────────┐    ┌───────────┐
│ 前端payload │ → │ save_test_point_assets │ → │ 文件系统    │
│ (candidates)│    │ _service.py            │    │ (state/*.json)│
└──────────┘    └──────────────────────┘    └───────────┘
                         │
                         ▼
                ┌──────────────────┐
                │ test_points 表    │ ← repository.sync_test_points()
                │ test_point_assets表│ ← test_point_asset_store.save_asset()
                └──────────────────┘
                         ↑
                写入路径正常 ✓
                         
                         ✗ 读取路径缺失：
                ┌──────────────────┐
                │ page_elements 表  │ ← 从未被本服务查询！
                │ page_objects 表   │ ← 从未被本服务查询！
                └──────────────────┘
```

### 4.2 目标状态

```
┌──────────┐    ┌──────────────────────┐    ┌───────────┐
│ 前端payload │ → │ save_test_point_assets │ → │ 文件系统    │
└──────────┘    │ _service.py            │    └───────────┘
                └──────────────────────┘
                         │
                ┌────────┼────────┐
                ▼        ▼        ▼
          test_points  test_point  page_elements
             表        _assets表     表
                         │
                    读取元素别名/名称 ↑
```

---

## 5. 重构方案

### Phase 1（短期，1-2天）：常量化 + 消除硬编码

**目标：零硬编码，不改架构**

| 任务 | 文件 | 说明 |
|------|------|------|
| 1.1 使用 `_c.ELEMENT_PREFIX` | save_service | 替换所有 `"element:"` 字符串 |
| 1.2 使用 `ACTION_*` 常量 | save_service | 替换所有 action 字符串 |
| 1.3 使用 `_c.SOURCE_TYPE_*` | save_service | 替换 `"inline"`, `"selection_save"` |
| 1.4 使用 `_c.PASSWORD_*` | save_service | 替换密码可见性硬编码 |
| 1.5 使用 `_c.HOME_ELEMENT_*` | save_service | 替换首页元素硬编码 |
| 1.6 使用 `_c.MSG_*` | save_service | 替换警告消息模板 |
| 1.7 使用 `_c.asset_title_for_page()` | save_service | 替换标题模板 |
| 1.8 使用 `format_steps_hint()` | save_service | 替换所有 f-string 拼接的 steps_hint |
| 1.9 补充 constants.py 缺失常量 | constants.py | `ASSERT_VISIBLE_FALLBACK_TEXT`, `ASSERT_URL_FALLBACK_TEXT` |

### Phase 2（中期，3-5天）：模块拆分 + DB 读路径

**目标：按职责拆分文件，元素从 DB 读取**

#### 2.1 目录结构

```
workbench_generation_api/
├── __init__.py
├── context.py                    # WorkbenchContext（不变）
├── repository.py                 # WorkbenchGenerationRepository（不变）
├── usecase_factory.py            # 工厂函数（不变）
│
├── constants.py                  # 本模块常量（Phase 1 补充完整）
├── feature_flags.py              # 特性开关（不变）
│
├── elements/                     # 【新】元素解析子模块
│   ├── __init__.py
│   ├── resolver.py               # _login_element_from_text → ElementResolver 类
│   ├── loader.py                 # _load_page_object_from_db + _build_element_mapping
│   └── naming.py                  # _data_ref_for_element（委托 element_naming）
│
├── steps/                        # 【新】步骤结构化子模块
│   ├── __init__.py
│   ├── classifier.py             # _classify_step_action
│   ├── structurer.py             # _structured_steps_from_candidate
│   ├── assertions.py             # _build_expected_assertions
│   └── input_value.py            # _input_value_from_text（或迁入 shared_backend/text_utils.py）
│
├── hooks/                        # 【新】页面级 Hook（可插拔特殊逻辑）
│   ├── __init__.py
│   ├── base.py                   # PageHook 基类
│   └── login_password_visibility.py  # _password_visibility_* 迁移到此
│
├── compilation/                  # 【新】测试点编译
│   ├── __init__.py
│   ├── point_builder.py          # _build_point
│   ├── plan_builder.py           # _build_test_point_plan
│   └── precondition.py           # _fallback_precondition
│
├── assets/                       # 【新】资产查询与统计
│   ├── __init__.py
│   ├── queries.py                # _existing_test_point_asset_ids, _find_existing_page_asset_for_upsert
│   ├── coverage.py               # _coverage_matrix_from_requirement_spec
│   ├── statistics.py             # _intent_type_distribution, _first_candidate_title
│   └── preview.py                # _preview_requirement, _candidate_snapshot
│
├── save_service.py               # SaveTestPointAssetsService（精简，~200行）
│
├── candidate_normalizer.py       # CandidateNormalizer（不变）
├── generate_case_service.py      # GenerateCaseService（不变）
├── precheck_selected_intents_service.py  # （不变）
├── preview_store.py              # （不变）
├── preview_test_points_usecase.py # （不变）
├── scenario_engine.py            # （不变）
├── orchestrator_client.py        # （不变）
├── orchestrator_client_factory.py # （不变）
└── payloads.py                   # （不变）
```

#### 2.2 DB 元素加载（关键改动）

```python
# elements/loader.py

def load_page_object_for_page(
    db: Session,
    *,
    project: str,
    client: str = "web",
    page: str,
) -> dict[str, Any]:
    """从 DB 加载页面对象及其元素，构建别名映射。
    
    优先级：DB(page_objects + page_elements) → YAML资产 → 空字典
    """
    # 1. 从 DB 查询
    from app.repositories.page_object_repository import PageObjectRepository
    repo = PageObjectRepository(db)
    po = repo.get_by_identity(project_code=project, client=client, page_code=page)
    if po:
        elements = repo.list_elements_by_page_object_id(po.id)
        return {
            "page": page,
            "elements": {
                elem.element_code: {
                    "name": elem.element_name,
                    "type": elem.locator_type,
                    "selector": elem.locator_value,
                    "role": elem.role,
                    "aliases": elem.aliases_json or [],
                }
                for elem in elements
            }
        }
    # 2. 回退到 YAML 资产
    from shared_backend.page_object_assets import load_page_object_yaml
    yaml_po = load_page_object_yaml(page)
    if yaml_po:
        return yaml_po
    return {}
```

#### 2.3 PageHook 基类（密码可见性逻辑解耦）

```python
# hooks/base.py
from abc import ABC, abstractmethod

class PageHook(ABC):
    """页面级钩子：处理特定页面的特殊逻辑。"""
    
    @abstractmethod
    def page_code(self) -> str: ...
    
    def setup_precondition_steps(self, precondition: str) -> list[dict[str, Any]]:
        return []
    
    def post_click_assertions(self, element_code: str, expected: str) -> list[dict[str, Any]]:
        return []
```

### Phase 3（长期，1-2周）：规则引擎化 + 共享库统一

**3.1 提取通用函数到 shared_backend**
- `as_text_list()` → `type_utils.py`
- `append_unique()` → `type_utils.py`
- `extract_input_value()` → `text_utils.py`

**3.2 Action 处理器注册表**
- 将 `_structured_steps_from_candidate` 中的 if-elif 链改为注册表模式
- 每个 action 类型有独立的 handler 函数

**3.3 页面对象预加载缓存**
- 在请求上下文中缓存已加载的 page_object，避免同一页面重复查询 DB

---

## 6. 建议目录结构（完整）

```
workbench_generation_api/
├── __init__.py
├── constants.py
├── context.py
├── feature_flags.py
├── repository.py
├── usecase_factory.py
│
├── elements/
│   ├── __init__.py           # 导出 ElementResolver
│   ├── resolver.py           # 元素识别（从 alias_map 解析）
│   └── loader.py             # 从 DB/YAML 加载页面对象
│
├── steps/
│   ├── __init__.py
│   ├── classifier.py         # _classify_step_action
│   ├── structurer.py         # _structured_steps_from_candidate
│   ├── assertions.py         # _build_expected_assertions
│   └── input_value.py        # _input_value_from_text
│
├── hooks/
│   ├── __init__.py
│   ├── base.py               # PageHook ABC
│   └── login_password_visibility.py
│
├── compilation/
│   ├── __init__.py
│   ├── point_builder.py      # _build_point
│   ├── plan_builder.py       # _build_test_point_plan
│   └── precondition.py       # _fallback_precondition
│
├── assets/
│   ├── __init__.py
│   ├── queries.py            # 存量资产查询
│   ├── coverage.py           # 覆盖率矩阵
│   ├── statistics.py         # 统计工具
│   └── preview.py            # 预览数据加载
│
├── save_service.py           # SaveTestPointAssetsService（精简入口）
│
├── candidate_normalizer.py
├── generate_case_service.py
├── precheck_selected_intents_service.py
├── preview_store.py
├── preview_test_points_usecase.py
├── scenario_engine.py
├── orchestrator_client.py
├── orchestrator_client_factory.py
└── payloads.py
```

### 文件大小预期

| 文件 | 预期行数 | 说明 |
|------|---------|------|
| `save_service.py` | ~250 | 仅编排逻辑 |
| `steps/structurer.py` | ~250 | 步骤结构化核心 |
| `elements/resolver.py` | ~80 | 元素识别 |
| `elements/loader.py` | ~60 | DB加载 |
| `steps/assertions.py` | ~60 | 断言生成 |
| `hooks/login_password_visibility.py` | ~100 | 密码可见性逻辑 |
| `compilation/point_builder.py` | ~120 | 测试点编译 |
| `compilation/plan_builder.py` | ~80 | Plan构造 |
| `assets/` 各文件 | 各 ~50 | 查询/统计工具 |

所有文件均 < 300 行，符合 CI 护栏。

---

## 7. 数据一致性保障

### 7.1 写入保证（已有，不变）

- `repository.sync_test_points()` → `test_points` 表（逐条 upsert + commit）
- `test_point_asset_store.save_asset()` → `test_point_assets` 表（upsert + commit）

### 7.2 读取新增（Phase 2）

- 元素别名/名称 → 从 `page_elements` 表读取（aliases_json, element_name）
- 页面路由 → 从 `page_objects` 表读取（route_pattern）
- 降级：DB 无数据 → `page_object_assets.py` YAML 文件 → `constants.py` 默认值

### 7.3 不变式

1. `script_code`（DB `test_cases` 表）是唯一可执行格式
2. `assets/test-cases/*.yaml` 从 `script_code` 派生
3. `web-ui/state/` 是可重建缓存
4. 本服务编译的 `TestPointPlanV1` → `test_points` + `test_point_assets` 是权威事实源
