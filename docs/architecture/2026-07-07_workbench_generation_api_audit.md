# workbench_generation_api 静态审计报告

> **日期：** 2026-07-07
> **审计范围：** `apps/web-ui-service/app/services/workbench_generation_api/`（32个 .py 文件）
> **重构状态：** Phase 1/2/3 已完成，本次审计为后续优化提供基线

---

## 1. 硬编码清单

### 1.1 高风险（应修复）

| # | 文件:行号 | 硬编码值 | 问题 | 建议 |
|---|----------|---------|------|------|
| 1 | `steps/structurer.py:284` | `"assert"` (raw string) | `ACTION_ASSERT_VISIBLE`=`"assert_visible"`，raw `"assert"`写出的 `steps_hint` 与 step action 不匹配 | **常量化：用 `ACTION_ASSERT_VISIBLE`** |
| 2 | `compilation/precondition.py:27` | `"登录" in merged` | magic string 条件判断 | **常量化：用 `LOGGED_IN_TOKENS`** |
| 3 | `generate_case_service.py:174` | `20` (候选限制) | 与 `constants.py:MAX_CANDIDATES=200` 矛盾 | **常量化：引用 `_c.MAX_CANDIDATES`** |
| 4 | `save_test_point_assets_service.py:318` | `page == "login"` | magic string 页面判断 | **常量化：用 `LoginPasswordVisibilityHook().page_code`** |
| 5 | `precheck_selected_intents_service.py:46` | `"mall"` (默认 project) | 硬编码默认项目 | **配置化：环境变量，必填校验** |
| 6 | `preview_store.py:120` | `"mall"` (默认 project) | 重复硬编码 | **同上** |
| 7 | `elements/loader.py:18-39` | `_FALLBACK_LOGIN_PAGE_MAP` (37条映射) | 仅在三层回退最终兜底时使用，生产中不应触发 | **保留（已有 LOGGER.warning）** |
| 8 | `precheck_selected_intents_service.py:14-24` | `_NON_DOM_INVOLVED_ELEMENTS` (13个元素) | 过滤规则硬编码 | **规则引擎化：从页面对象标注获取** |
| 9 | `constants.py:88` | `"macro123"` (DEFAULT_TEST_PASSWORD) | 测试密码硬编码 | **配置化：环境变量/数据池** |
| 10 | `repository.py:144` | `"case_id already exists" not in detail_text` | 文本匹配错误识别 | **常量化：用错误码** |
| 11 | `constants.py:37,55` | `"#/home"`, `"#/login"` | 路由硬编码 | **配置化：从 page_object 读取**（已有 @deprecated 标记） |
| 12 | `constants.py:91-92,95-96,109-110` | login 专属元素 code/name | 单页面专属硬编码 | **页面对象化**（已有 @deprecated 标记） |

### 1.2 中风险（应排期）

| # | 文件 | 问题 | 建议 |
|---|------|------|------|
| 1 | `constants.py:69-74` | `PRECONDITION_APPLICABLE_POINT_TYPES`, `REVIEW_POINT_TYPES` frozenset | 规则引擎化 |
| 2 | `precheck_selected_intents_service.py:106-130` | 多条中文原因字符串 | 常量化 |
| 3 | `precheck_selected_intents_service.py:108-130` | `"block"`, `"warn"`, `"ok"` 状态字符串 | 枚举化 |
| 4 | `preview_store.py:71,180` | API 路由拼接 | 配置化 |
| 5 | `preview_store.py:182-185` | schema 版本标识 | 常量化 |
| 6 | `repository.py:69,76` | `case_type="FN"`, `source="AI"` | 常量化 |
| 7 | `repository.py:214` | `source="ai"` (大小写与 `"AI"` 不一致) | 常量化对齐 |
| 8 | `generate_case_service.py` | 多处硬编码错误消息/限制 | 常量化 |
| 9 | `candidate_normalizer.py:209-241` | 中文文案模板 | 配置外置 |
| 10 | `elements/resolver.py:66-74` | `.removesuffix("_input").removesuffix("-input")` | 委托 element_naming |

### 1.3 低风险（保留）

- 消息/警告文案模板（`MSG_*`）
- raw_text fallback 文案（`ASSERT_*_FALLBACK_TEXT`）
- 正则清洗规则
- dict key
- 数值阈值（`MAX_CANDIDATES`）
- DSL 协议前缀（`"element:"`, `format_steps_hint`）
- HTML 标准属性值（`"type"`, `"text"`, `"password"`）

---

## 2. 架构问题总结

### 2.1 BUG: steps_hint 中 `"assert"` ≠ `ACTION_ASSERT_VISIBLE`

- **`steps/structurer.py:284`**
- 代码：`format_steps_hint("assert", _c.HOME_ELEMENT_NAME)`
- 同一函数中 step 正确使用了 `ACTION_ASSERT_VISIBLE` (= `"assert_visible"`)
- **影响：** steps_hint 写出的值是 `"assert:首页菜单"`，而对应的 DSL step action 是 `"assert_visible"`，编译器解析时 hint 无法匹配到 step

### 2.2 跨模块私有 API 使用

- `_data_ref_for_element` 在 `elements/resolver.py` 中定义为模块级私有函数（`_` 前缀），被 `steps/structurer.py` 跨子包导入使用
- 应改为 `ElementResolver` 的公开方法，或迁入共享工具

### 2.3 无循环依赖

导入图严格无环：`elements → steps → compilation → save_service`，`hooks → compilation`，`assets → compilation`。结构清晰。

### 2.4 无重复函数定义

`_list_text`、`_append_unique` 已统一从 `shared_backend.type_utils` 导入，无本地重复。

### 2.5 generate_case_service.py 与 constants.py 阈值不一致

- `generate_case_service.py:174` 硬编码 `20`
- `constants.py:138` 定义 `MAX_CANDIDATES = 200`
- 两个文件各自定义了自己的限制，应统一

---

## 3. 一致性检查

| 检查项 | 结果 |
|--------|------|
| `format_steps_hint()` 统一使用 | ⚠️ 1处异常（line 284 `"assert"`） |
| `_c.ELEMENT_PREFIX` 统一使用 | ✅ 无 raw `"element:"` |
| `ACTION_*` 常量统一使用 | ⚠️ `line 284` 异常 |
| `SOURCE_TYPE_*` 常量统一使用 | ✅ |
| `__init__.py` 导出对齐 | ✅ 所有子包导出完整 |
| 函数重复定义 | ✅ 无 |

---

## 4. 重构建议（按优先级）

### Phase 4.1（立即修复，~30分钟）

1. **修复 `structurer.py:284`** — `"assert"` → `ACTION_ASSERT_VISIBLE`
2. **修复 `precondition.py:27`** — `"登录" in merged` → `any(t in merged for t in LOGGED_IN_TOKENS)`
3. **修复 `save_service.py:318`** — `page == "login"` → `page == LoginPasswordVisibilityHook().page_code`
4. **删除 `save_service.py:30`** — 移除未使用的 `fallback_precondition` import
5. **修复 `generate_case_service.py:174`** — `20` → `_c.MAX_CANDIDATES`

### Phase 4.2（短期，1天）

6. **移除默认 `"mall"` project** — `precheck_selected_intents_service.py:46`、`preview_store.py:120`
7. **常量化状态/原因字符串** — `precheck_selected_intents_service.py`
8. **常量化 `repository.py`** — `case_type`, `source` 常量 + 错误码匹配
9. **`_data_ref_for_element` 重构** — 移入 `ElementResolver` 公开方法

### Phase 4.3（中期，按需）

10. **`_NON_DOM_INVOLVED_ELEMENTS` 规则引擎化**
11. **`DEFAULT_TEST_PASSWORD` 配置化**
12. **路由 `#/home`, `#/login` 从 page_object 配置读取**

---

## 5. 当前目录结构（Phase 2 完成后）

```
workbench_generation_api/
├── __init__.py
├── constants.py                  # 模块常量
├── context.py                    # WorkbenchContext
├── feature_flags.py              # 特性开关
├── payloads.py                   # 请求 payload 模型
│
├── elements/                     # 元素解析
│   ├── loader.py                 # DB→YAML→默认 加载
│   └── resolver.py               # ElementResolver
│
├── steps/                        # 步骤结构化
│   └── structurer.py             # structured_steps_from_candidate
│
├── hooks/                        # 页面 Hook
│   ├── base.py                   # PageHook ABC
│   └── login_password_visibility.py  # 登录页密码可见性
│
├── compilation/                  # 测试点编译
│   ├── point_builder.py          # build_point
│   └── precondition.py           # fallback_precondition
│
├── assets/                       # 资产查询
│   ├── preview.py                # 预览数据
│   ├── queries.py                # 资产查询
│   ├── coverage.py               # 覆盖率矩阵
│   └── statistics.py             # 统计工具
│
├── save_test_point_assets_service.py  # Service 入口
├── generate_case_service.py      # 用例生成
├── precheck_selected_intents_service.py  # 预校验
├── candidate_normalizer.py       # 候选标准化
├── scenario_engine.py            # 场景引擎
├── preview_store.py              # 预览存储
├── preview_test_points_usecase.py # 预览用例
├── repository.py                 # DB 仓储
├── usecase_factory.py            # 工厂函数
├── orchestrator_client.py        # AI 编排客户端
└── orchestrator_client_factory.py # 客户端工厂
```

**结构评分：** 模块划分清晰，职责分离合理。`save_test_point_assets_service.py` 作为编排入口，子模块各司其职。无循环依赖。文件大小均符合 CI 护栏。
