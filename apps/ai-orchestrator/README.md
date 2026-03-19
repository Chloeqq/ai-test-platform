# AI Orchestrator

最小可运行骨架，负责把 `test-design-agent` 和 `web-playwright-python` 串起来。
当前 HTTP 服务层基于 Flask 实现，并通过 `create_server()` 保持现有 CLI 与集成测试兼容。

## CLI

```bash
python src/main.py orchestrate \
  --page product \
  --requirement "验证商品搜索功能" \
  --execute
```

功能：

- 调用 `agents/test-design-agent` 生成 YAML 用例
- 保存到 `assets/test-cases/ai-generated/`
- 可选地触发 `runners/web-playwright-python/tests/test_yaml_ai_generated.py`
- 在 `reports/executions/` 下生成 JSON 和 Markdown 执行报告

## HTTP

```bash
python src/main.py serve --host 127.0.0.1 --port 8000
```

如果只想安装 orchestrator 自己的运行依赖：

```bash
pip install -r requirements.txt
```

如果你在代码里嵌入 orchestrator，也可以直接创建 Flask app：

```python
from app import create_app

app = create_app()
```

也可以用 Flask 标准方式启动：

```bash
cd /Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator
PYTHONPATH=src flask --app src/wsgi:app run --host 127.0.0.1 --port 8000
```

如果要用 Docker 启动：

```bash
cd /Users/bettyhuang/PycharmProjects/ai-test-platform
docker build -f apps/ai-orchestrator/Dockerfile -t ai-orchestrator:local .
docker run --rm -p 8000:8000 ai-orchestrator:local
```

接口：

- `GET /`
- `GET /console`
- `GET /health`
- `GET /reports/latest`
- `GET /reports/{case_id}`
- `GET /assets/scaffold/templates`
- `GET /assets/scaffold/templates/{template}`
- `POST /orchestrate`
- `POST /healing/preview`
- `POST /assets/page-objects`
- `POST /assets/page-objects/{page}/elements`
- `POST /assets/test-cases/sync`
- `POST /assets/scaffold`
- OpenAPI 说明见 [openapi/orchestrator-openapi.yaml](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/openapi/orchestrator-openapi.yaml)

内置控制台：

- 打开 [http://127.0.0.1:8000/console](http://127.0.0.1:8000/console)
- 页面会直接调用 scaffold 模板接口和 `POST /assets/scaffold`
- 控制台实现说明见 [apps/web-console/README.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-console/README.md)

请求体示例：

```json
{
  "page": "product",
  "requirement": "验证商品搜索功能",
  "execute": false,
  "mode": "generate_only",
  "source": "manual"
}
```

说明：

- `mode` 可选，支持：
  - `generate_only`
  - `generate_and_run`
- 如果同时传 `mode` 和 `execute`，以 `mode` 为准
- `source` 可选，支持：
  - `manual`
  - `ai`
  - `regression`
- `source` 只进入报告与记录，不改变执行逻辑

## POST /orchestrate 响应规范

成功：

- `201 Created`

```json
{
  "case": {},
  "case_path": "/abs/path/to/assets/test-cases/ai-generated/TC-XXX.yaml",
  "execution_requested": false,
  "runner_exit_code": null,
  "runner_stdout": "",
  "runner_stderr": "",
  "report": {
    "status": "generated",
    "summary": "Generated test case TC-XXX for page product. Execution was not requested.",
    "case_id": "TC-XXX",
    "case_title": "示例用例",
    "page": "product",
    "case_path": "/abs/path/to/assets/test-cases/ai-generated/TC-XXX.yaml",
    "execution_requested": false,
    "source": "manual",
    "request_context": {
      "page": "product",
      "mode": "generate_only",
      "source": "manual",
      "execution_requested": false
    },
    "started_at": "2026-03-17T12:00:00+00:00",
    "finished_at": "2026-03-17T12:00:01+00:00",
    "runner_exit_code": null,
    "metrics": {
      "passed": 0,
      "failed": 0,
      "skipped": 0,
      "errors": 0
    },
    "pytest_results": {
      "collected": null,
      "passed": 0,
      "failed": 0,
      "skipped": 0,
      "errors": 0,
      "runner_exit_code": null,
      "duration_seconds": null,
      "has_stderr": false
    },
    "failure_reason": "",
    "failure_analysis": {
      "summary": "No failure analysis needed because the run did not fail.",
      "failure_category": "unknown",
      "likely_cause": "",
      "risk_level": "low",
      "recommended_action": "No immediate failure action is required.",
      "confidence": 1.0,
      "evidence_used": []
    },
    "self_healing_advice": {
      "summary": "No self-healing action is required because the run did not fail.",
      "suggestion_type": "no_change",
      "suggested_changes": [
        "Keep the current YAML and page-object unchanged."
      ],
      "rationale": "The run passed, so only a no-op advisory is returned.",
      "confidence": 1.0,
      "safe_to_apply_manually": true
    },
    "evidence": {
      "screenshots": [],
      "html_pages": [],
      "meta_files": [],
      "analysis_files": [],
      "videos": [],
      "other_files": [],
      "total_files": 0
    },
    "runner_stdout_excerpt": "",
    "runner_stderr_excerpt": ""
  },
  "report_json_path": "/abs/path/to/reports/executions/TC-XXX.report.json",
  "report_markdown_path": "/abs/path/to/reports/executions/TC-XXX.report.md",
  "report_summary_path": "/abs/path/to/runners/web-playwright-python/artifacts/report_summary.txt"
}
```

报告说明：

- `report.status`
  - `generated`：只生成用例，未执行
  - `passed`：执行成功
  - `failed`：执行失败
- `report.metrics`
  - 从 pytest 输出中提取的通过/失败/跳过/错误数量
- `report.source`
  - 标识本次请求来源，如 `manual / ai / regression`
  - 只用于报告和记录，不影响执行逻辑
- `report.request_context`
  - 记录本次请求的输入上下文
  - 当前包含 `page / mode / source / execution_requested`
  - 只用于回显和追踪，不改变执行逻辑
- `report.pytest_results`
  - 更完整的 pytest 运行结果，包括 collected、duration_seconds、has_stderr
- `report.failure_reason`
  - 从 pytest 输出中提取的直接失败原因
- `report.failure_analysis`
  - 基于失败信息和证据做出的结构化失败原因分析
- `report.self_healing_advice`
  - 基于失败原因和当前 page-object target 给出的修复建议
  - 当前只输出建议，不会自动修改 YAML 或 page-object
- `report.self_healing_suggestion_preview`
  - 从 runner 侧落盘的 `suggestion.json` 读取并解析出的建议预览
  - 用于展示真实失败产物中的修复建议内容
- `report.evidence`
  - 本次执行新增的证据文件索引，包括截图、HTML、meta、analysis、视频
- `report_json_path`
  - 机器可读报告
- `report_markdown_path`
  - 人可读报告
- `report_summary_path`
  - 执行后生成的聚合失败分析汇总文件路径
  - 只在执行链路中有意义；未执行时为空字符串

### 查询最新执行报告

```http
GET /reports/latest
```

### 按 case id 查询执行报告

```http
GET /reports/TC-PRODUCT-GEN-002
```

这两个接口都会返回：

- `report`
- `report_json_path`
- `report_markdown_path`
- `report_summary_path`

### 预览自动修复建议

```json
POST /healing/preview
{
  "page": "product",
  "failure_reason": "expected product list title to be visible",
  "failure_analysis": {
    "summary": "UI assertion failed on product page.",
    "failure_category": "assertion",
    "likely_cause": "The expected product list title was not rendered.",
    "risk_level": "high",
    "recommended_action": "Review the stable assertion target manually.",
    "confidence": 0.84,
    "evidence_used": ["stdout"]
  }
}
```

返回：

- `self_healing_advice`

说明：

- 这个接口只做建议预览
- 不会自动修改 YAML
- 不会自动修改 page-object

阶段8专项清单见：

- [stage8-self-healing-advisor-checklist.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/conventions/stage8-self-healing-advisor-checklist.md)

错误：

- `400 Bad Request`
  - `invalid_json`
- `404 Not Found`
  - `not_found`
- `415 Unsupported Media Type`
  - `unsupported_media_type`
- `422 Unprocessable Entity`
  - `validation_error`
- `502 Bad Gateway`
  - `runner_failed`
- `500 Internal Server Error`
  - `internal_error`

错误体格式：

```json
{
  "error": {
    "code": "validation_error",
    "message": "requirement must not be empty"
  }
}
```

## 资产管理 API

### 创建 page object

```json
POST /assets/page-objects
{
  "page": "catalog",
  "description": "商品目录页"
}
```

### 增加 page element

```json
POST /assets/page-objects/catalog/elements
{
  "name": "catalog_menu",
  "locator_type": "role",
  "role": "menuitem",
  "locator_value": "商品目录"
}
```

### 同步已有 test case 步骤

```json
POST /assets/test-cases/sync
{
  "file": "assets/test-cases/smoke/product-smoke.yaml"
}
```

### 一次性创建 page object + smoke case 骨架

```json
POST /assets/scaffold
{
  "page": "catalog",
  "title": "商品目录",
  "requirement": "商品目录页面展示",
  "template": "catalog",
  "description": "创建目录页骨架",
  "elements": [
    {
      "name": "catalog_search_input",
      "locator_type": "css",
      "locator_value": "input[name='keyword']",
      "description": "搜索输入框"
    },
    {
      "name": "catalog_search_button",
      "locator_type": "role",
      "role": "button",
      "locator_value": "搜索"
    },
    {
      "name": "catalog_search_entry",
      "locator_type": "role",
      "role": "menuitem",
      "locator_value": "商品目录查询",
      "smoke_role": "menu"
    },
    {
      "name": "catalog_results_panel",
      "locator_type": "css",
      "locator_value": ".catalog-results",
      "smoke_role": "assert"
    }
  ]
}
```

`elements[].smoke_role` 可选值：

- `menu`：指定 smoke 用例里的点击目标
- `assert`：指定 smoke 用例里的等待/断言目标

`template` 当前支持的内置模板：

- `catalog`
- `list`
- `detail`

### 查看可用 scaffold 模板

```http
GET /assets/scaffold/templates
```

### 查看单个 scaffold 模板详情

```http
GET /assets/scaffold/templates/catalog
```

## 测试

建议从仓库根目录执行：

```bash
make install-dev
make test-orchestrator
```
