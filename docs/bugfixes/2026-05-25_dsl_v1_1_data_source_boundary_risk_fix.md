# 2026-05-25 DSL V1.1 `data` 唯一来源边界风险修复留档

## 1. 文档日期与范围
- 日期：2026-05-25
- 范围：DSL V1.1 `data` 来源边界（`inline/pool/env`）相关新增链路
- 目标：按“问题 -> 修复 -> 风险 -> 验证”沉淀本轮修复
- 铁律确认：被测地址仍保持 `http://localhost:5174/#/login`，本轮未改写

## 2. 问题清单（本轮处理）
1. 运行链路依赖数据池快照，若数据库未迁移新表会导致执行直接失败。
2. 数据池接口只有登录态保护，缺少管理员权限门禁；且列表存在明文暴露风险。
3. 生成器 `data key` 复用逻辑残留旧格式比较，可能误生成 `*_2` 重复键。
4. `POST_PROCESSING_ENABLED=false` 时，`data` 结构校验可被绕过。
5. 数据池 `status` 非法值被静默回退为 `active`，存在误激活风险。
6. Runner 批量加载时，单条坏 AI YAML 会导致整批运行失败（一票否决）。
7. 数据池审计日志 `before/after` 使用 `str(...)`，不利于结构化检索与审计分析。

## 3. 修复动作（代码落地）

### 3.1 运行链路迁移容错（问题 1）
- 文件：`apps/web-ui-service/app/services/test_data_pool_service.py`
- 变更：
  - `serialize_runner_data_pool_snapshot()` 增加表存在检查（`inspect(...).has_table(...)`）。
  - 新增 SQLAlchemy 异常兜底，异常时返回空快照 `{}` 并记录 warning。
- 结果：
  - 未迁移或短时 DB 异常不再阻断 `run_case` 主流程。

### 3.2 数据池权限与明文控制（问题 2）
- 文件：`apps/web-ui-service/app/routers/test_data_pools.py`
- 变更：
  - 所有 `/api/test-data-pools` 接口新增 admin 角色门禁（非 admin 返回 403）。
  - `list items` 增加 `reveal_secret` 参数，默认 `false`。
- 文件：`apps/web-ui-service/app/services/test_data_pool_service.py`
- 变更：
  - `list_data_pool_items()` 默认返回脱敏结构：`item_value=""` + `item_value_preview` + `has_value`。
  - 仅在 `reveal_secret=true` 时返回明文。
- 结果：
  - 默认场景不再回传明文凭据；非 admin 无权读写数据池。

### 3.3 生成器 data key 复用修正（问题 3）
- 文件：`apps/web-ui-service/app/services/workbench_generation_compiler/runtime/generate_pipeline.py`
- 变更：
  - `_reserve_data_key()` 改为兼容 `inline` 新结构、legacy list/scalar 的等值比较。
- 结果：
  - 相同语义输入不再因格式差异被误判为冲突键。

### 3.4 关闭后处理开关时仍强制 data 契约（问题 4）
- 文件：`apps/web-ui-service/app/services/test_case_service.py`
- 变更：
  - `_sanitize_workbench_case_yaml_for_storage()` 在开关判断前先执行 `_normalize_workbench_data_sources_for_storage()`。
  - `_workbench_yaml_script()` 在 `POST_PROCESSING_ENABLED=false` 分支也执行 data 规范化。
- 结果：
  - `data` 结构校验不再被环境开关绕过。

### 3.5 数据池状态非法值 fail-fast（问题 5）
- 文件：`apps/web-ui-service/app/services/test_data_pool_service.py`
- 变更：
  - `_normalized_pool_status()` 从“非法值回退 active”改为直接 422，错误码 `data_pool_invalid_status`。
- 结果：
  - 拼写错误或脏数据不会被静默激活。

### 3.6 Runner 批量加载降级策略（问题 6）
- 文件：`runners/web-playwright-python/runner/test_case_loader.py`
- 变更：
  - `_ensure_formal_ai_cases_have_source_identity()` 改为 `_filter_formal_ai_cases_by_source_identity()`。
  - 显式单用例执行（`case_id/case_path`）继续严格失败。
  - 批量目录模式跳过坏 AI 用例并记录 warning，不阻断其它用例。
- 结果：
  - 保留严格门禁同时降低批量任务被单条历史脏数据拖垮的风险。

### 3.7 审计日志结构化（问题 7）
- 文件：`apps/web-ui-service/app/services/test_data_pool_service.py`
- 变更：
  - 新增 `_json_text()`，`before_value/after_value` 改为 JSON 文本序列化。
- 结果：
  - 审计信息可机器解析，便于后续查询与比对。

## 4. 本轮变更后的剩余风险
1. 数据池值目前按文本存储（`item_value: Text`），复杂对象/类型语义仍依赖上层约定。
2. `reveal_secret=true` 仍会返回明文，需由前端与操作规范约束最小化使用。
3. 部分测试日志仍有 `HTTP_422_UNPROCESSABLE_ENTITY` deprecation warning，后续可统一升级到新常量。
4. Runner 测试存在 `pytest.mark.contract` 未注册警告，不影响功能但建议统一 pytest 标记配置。

## 5. 验证结果

### 5.1 静态检查
- `python3 -m py_compile`（相关修改文件）通过。

### 5.2 后端测试
- 命令：`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/python -m pytest -q apps/web-ui-service/tests/test_workbench_generation_service.py apps/web-ui-service/tests/test_case_id_flow.py apps/web-ui-service/tests/test_data_pool_service.py`
- 结果：`40 passed`。

### 5.3 Runner 测试
- 命令：`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=.:tools ../../.venv/bin/python -m pytest -q -c /dev/null tests/test_data_expander.py tests/test_ai_generated_loader.py tests/test_assert_text_action.py`
- 结果：`15 passed`。

### 5.4 新增测试覆盖点
- `apps/web-ui-service/tests/test_data_pool_service.py`
  - 非法状态值 fail-fast
  - 默认脱敏返回
  - 引用阻断删除
  - 快照仅导出 active 池/键
- `runners/web-playwright-python/tests/test_ai_generated_loader.py`
  - `RUN_MODE=all` 下跳过坏 AI 用例并保留 smoke 用例

## 6. 结论
本轮 7 个风险点已完成修复并通过定向回归，`data` 唯一来源边界在“生成器 -> 用例中心 -> Runner -> 数据池治理”链路上已形成可追溯、可审计、失败即中断的收敛行为，并保持对被测地址铁律不改写。
