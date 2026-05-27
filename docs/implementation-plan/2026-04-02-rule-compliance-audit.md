# docs/rule 当前对齐盘点（2026-04-03）

## 范围
- [/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/rule/ai_code_development_spec_v1.0.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/rule/ai_code_development_spec_v1.0.md)
- [/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/rule/ai_test_platform_architecture_blueprint_v1.0.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/rule/ai_test_platform_architecture_blueprint_v1.0.md)
- [/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/rule/ai_test_platform_governance_v1.0.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/rule/ai_test_platform_governance_v1.0.md)
- [/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/rule/codex_system_super_prompt_anti_chaos_v1.0.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/rule/codex_system_super_prompt_anti_chaos_v1.0.md)
- [/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/rule/test_case_naming_spec_v1.0.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/rule/test_case_naming_spec_v1.0.md)

## 结论
当前项目已经完成了大部分“结构化、分层、规范化”的主线目标，并且这轮已经把字典独立数据源、状态机显式模块、AI 观测字段统一入口和规则强校验第一版真正落到代码里。

最准确的判断是：
- 已完成：主链拆分、Case ID 平台生成与规范化、治理与审计第一版、多源结构化第一版、前端治理页面第一版、字典独立数据源第一版、Case/AI/Run 状态机显式模块第一版、平台级 AI 观测字段第一版
- 部分完成：字典中心产品化、版本治理统一化、Prompt/Model/Fallback 统一治理、平台级强校验全覆盖
- 未完成：权限模型全量落地、状态机统一落库、独立 Prompt Manager / Model Router / Fallback Engine 中心

## 已做到

### 1. 代码分层与单体拆分
- `orchestrator_service.py` 已从超大单体拆成 facade + support
- `legacy_workbench.py` 已收敛为 compat facade + infra bridge
- router / service / state 边界已基本成型

### 2. Case ID 平台规范化
- `case_id` 已统一为平台生成与归一
- 当前规范已稳定为：
  - `project-client-page-module-type-source-seq`
  - 示例：`atp-web-ret-query-sm-ai-0001`
- 共享入口：
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/case_ids.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/case_ids.py)

### 3. 测试资产标准化第一版
- 历史资产已做 `case_id` 标准化迁移
- 标题、描述、首条需求摘要已做中文优先清洗
- 标题已收紧为 4~5 段业务语义
- Allure、报告、任务、门禁等页面已统一消费标准化 `case_id`

### 4. 治理主线第一版
- review / gate / audit / dashboard / trend / flaky / failure cluster 已进入可消费状态
- scheduler / defects / assets / gate / trends / flaky 已有首版独立页面

### 5. AI 输出结构化第一版
- orchestrator 已稳定输出 requirement spec / test points / execution record / report payload
- 多源输入已完成第一版闭环
- fallback / explainability / traceability 已进入主链

### 6. 字典独立数据源第一版
- 页面、模块、类型、来源、状态等规则字典已从散落代码映射升级为共享数据源：
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/data/case_dictionaries.json](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/data/case_dictionaries.json)
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/case_dictionary.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/case_dictionary.py)
- `case_id` 归一、规则校验、创建链路和前端字典接口现在都开始复用同一份字典源

### 7. 状态机显式模块第一版
- Case / Run / AI 三类状态已经收敛到共享模块：
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/state_machines.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/state_machines.py)
- 当前已具备：
  - 状态码枚举
  - 状态中文名
  - 基础状态归一
  - 基础状态迁移校验

### 8. 平台级 AI 观测字段第一版
- orchestrator / parser fallback / execution record 已开始统一写入：
  - `trace_id`
  - `prompt_version`
  - `model`
  - `fallback_used`
  - `fallback_reason`
- 共享入口：
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/observability/ai_trace.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/observability/ai_trace.py)

## 部分做到

### 1. 字典与规则中心
- 当前已有独立共享字典数据源：
  - `page_code`
  - `module_code`
  - `case_type`
  - `source`
  - `case_status / run_status / ai_status / migration_status`
- 但还没有独立的“字典中心”产品能力：
  - 无完整后台维护入口
  - 无完整数据库字典表统一托管
  - 仍有少量历史映射残留在旧兼容逻辑中

### 2. 平台强校验
- 当前已补：
  - `case_id` 结构校验
  - `case_title` 至少 4 段语义校验
  - 枚举字段校验
  - 页面/模块字典命中校验
  - AI 状态基础校验
- 但还没有做到全链路强校验：
  - 所有创建入口统一强制
  - 所有历史资产全量清洗后再收紧
  - 所有 AI 输出统一由 validator 拦截后才能入库

### 3. 状态机治理
- 已有显式共享状态机模块承接 Case / Run / AI 状态
- 但还没有完全做到：
  - review / gate / run / ai 全部统一落库
  - 所有 service 层全部只依赖状态机模块而非局部规则

### 4. 版本治理
- 页面和用例已有版本相关能力
- 但还没有做到统一版本中心和完整 Ready 版本不可覆盖约束

### 5. Prompt / Model / Fallback 治理
- 已有 `prompt_version`、parser runtime、fallback explainability、`trace_id`
- execution record 已开始统一写入 AI 观测字段
- 但还没有独立 Prompt Manager / Model Router / Fallback Engine 中心

## 还没做到

### 1. 权限模型全量落地
- 文档中的 Admin / QA Lead / QA Engineer / Developer / AI Agent 角色体系未全量实现

### 2. 字典中心产品化
- 页面、模块、类型、来源、状态虽然已有共享数据源，但还没有真正的独立治理中心 UI/后台

### 3. 全量状态机入领域层
- 当前虽然已有共享 state machine 模块，但仍以 service 侧治理为主，未做到全量落库与统一消费

### 4. 平台级观测统一化
- `trace_id / fallback / model / prompt_version` 已部分记录
- 但还没有所有链路统一、稳定、可检索地对齐

## 本轮已执行

### A1. 新增共享规则校验模块
- 新增：
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/case_rules.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/case_rules.py)
- 当前能力：
  - `case_id` 结构校验
  - `case_title` 语义质量校验
  - `description` 中文基本校验
  - `case_type / source / status / migration_status / ai_status` 枚举校验
  - 结构化元数据补齐

### A2. 将规则接入保存链路
- 接入：
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python/runner/asset_toolkit.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python/runner/asset_toolkit.py)
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_asset_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_asset_service.py)

### A3. 补共享规则测试
- 新增：
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/tests/test_case_rules.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/tests/test_case_rules.py)

### A4. 将资产合同测试纳入规则校验
- 更新：
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python/tests/test_asset_contracts.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python/tests/test_asset_contracts.py)

### A5. 将规则字典升级为独立共享数据源
- 新增：
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/data/case_dictionaries.json](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/data/case_dictionaries.json)
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/case_dictionary.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/case_dictionary.py)
- 新增接口：
  - `GET /api/workbench/case-dictionaries`

### A6. 将状态机显式收敛成共享模块
- 新增：
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/state_machines.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/state_machines.py)
- 当前覆盖：
  - `case_status`
  - `run_status`
  - `ai_status`
  - `migration_status`

### A7. 将 AI 观测字段统一收敛到共享入口
- 新增：
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/observability/ai_trace.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/observability/ai_trace.py)
- 已接入：
  - requirement parser fallback
  - orchestrator requirement spec
  - execution record metadata
  - telemetry event

### A8. 收紧标题规则并切换 AI 资产保存为平台生成 ID
- 更新：
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python/runner/asset_toolkit.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python/runner/asset_toolkit.py)
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/scripts/normalize_case_texts.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/scripts/normalize_case_texts.py)
- 当前效果：
  - `ai-generated` 资产保存时优先使用平台规范 ID
  - 标题默认收紧为 4~5 段业务语义
  - 历史 YAML 文案已再次清洗

## 执行清单

### P0 已执行
- [x] 扫描 `docs/rule` 与当前实现差距
- [x] 新增共享 `case` 规则校验模块
- [x] 接入 YAML 资产保存链路
- [x] 接入 workbench 手工保存链路
- [x] 增加共享规则测试
- [x] 增加资产合同规则测试
- [x] 将页面/模块/类型/来源/状态升级成独立共享字典源
- [x] 将 `case_title` 标题格式收紧成完整 4~5 段业务语义
- [x] 将 Case / AI / Run 状态机显式收敛成统一模块
- [x] 将 `prompt_version / model / fallback / trace_id` 统一收敛到平台观测字段

### P1 下一步继续做
- [ ] 将 AI 生成链路改成“只产结构化字段，由平台统一拼 ID”
- [ ] 将规则 validator 扩展到所有创建入口与导入入口
- [ ] 将 review / gate 状态也继续并入统一状态机消费
- [ ] 将字典源落到后台维护能力与数据库托管
- [ ] 将标题与描述质量校验纳入 CI 质量巡检

### P2 暂不强推
- [ ] 权限中心按规则文档角色全量落地
- [ ] Prompt Manager / Model Router / Fallback Engine 独立产品化
- [ ] 独立字典中心 UI 与后台维护台

## 当前建议
当前最值得继续推进的不是继续写更多规则文档，而是把这些规则进一步落实到“创建入口、AI 生成入口、资产迁移入口”的统一 validator 链路中，并让字典源、状态机、观测字段真正成为平台级基础设施。
