"""AI 编排器 HTTP API：Flask 路由、鉴权、可观测性与控制台静态资源。"""

import json
import logging
import os
import time
import uuid
from functools import wraps
from pathlib import Path

from flask import Flask, Response, g, jsonify, request
from werkzeug.serving import make_server

from asset_service import AssetService  # type: ignore[import-not-found]
from shared_backend.observability import configure_logging, set_request_id, summarize_http_context, summarize_log_value
from orchestrator_service import OrchestratorError, OrchestratorService, OrchestratorValidationError  # type: ignore[import-not-found]
from wsgi_asgi import WSGIToASGIAdapter  # type: ignore[import-not-found]

# 可选 API Key；未配置时跳过鉴权（便于本地开发）
_ORCHESTRATOR_API_KEY = os.environ.get("ORCHESTRATOR_API_KEY", "").strip()
_AUTH_EXEMPT_PATHS = frozenset({"/health"})
_AUTH_EXEMPT_PREFIXES = ("/console",)


def _require_api_key(f):
    """装饰器：校验 Bearer 或 X-Api-Key 头（未配置密钥时直通）。"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not _ORCHESTRATOR_API_KEY:
            return f(*args, **kwargs)
        token = (request.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
        if not token:
            token = (request.headers.get("X-Api-Key") or "").strip()
        if token != _ORCHESTRATOR_API_KEY:
            return jsonify({"error": {"code": "unauthorized", "message": "invalid or missing API key"}}), 401
        return f(*args, **kwargs)
    return decorated

_CONSOLE_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>Scaffold Console</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="/console/styles.css">
</head>
<body>
  <main class="console-shell">
    <h1>Scaffold Console</h1>
    <p>Orchestrator console shell.</p>
    <script src="/console/app.js"></script>
  </main>
</body>
</html>
"""

_CONSOLE_JS = """(() => {
  function loadTemplates() {
    return ["catalog"];
  }
  window.loadTemplates = loadTemplates;
})();
"""

_CONSOLE_CSS = """body {
  font-family: sans-serif;
  margin: 0;
  background: #f7f7f7;
  color: #1f2937;
}
.console-shell {
  max-width: 720px;
  margin: 48px auto;
  padding: 24px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
}
"""
configure_logging(service_name="ai-orchestrator")
access_logger = logging.getLogger("orchestrator.access")


def _preview_request_payload() -> str:
    """为访问日志生成 JSON 请求体的脱敏摘要。"""
    if request.method not in {"POST", "PUT", "PATCH"}:
        return ""
    if not request.is_json:
        return ""
    payload = request.get_json(silent=True)
    return summarize_log_value(payload) if payload is not None else ""


def _render_requirement_analysis_markdown(
    service: OrchestratorService,
    requirement_spec: dict[str, object],
) -> str:
    """将需求规格渲染为 Markdown；失败时回退为简易列表。"""
    renderer = getattr(service, "render_requirement_spec_markdown", None)
    if callable(renderer):
        try:
            return str(renderer(requirement_spec))
        except Exception:
            pass
    page = str(requirement_spec.get("page", "")).strip() if isinstance(requirement_spec, dict) else ""
    priority = str(requirement_spec.get("priority", "")).strip() if isinstance(requirement_spec, dict) else ""
    return (
        "# 需求测试点分析\n\n"
        f"- 页面: `{page or '-'}`\n"
        f"- 优先级: `{priority or 'P1'}`\n"
    )


def create_app(
    service: OrchestratorService | None = None,
    asset_service: AssetService | None = None,
) -> Flask:
    """创建并注册编排器 REST 路由、中间件与错误处理器。"""
    app = Flask(__name__, static_folder=None)
    orchestrator_service = service or OrchestratorService()
    asset_tool_service = asset_service or AssetService()

    @app.before_request
    def _attach_request_id():
        """为每个请求注入 trace id 并记录请求开始日志。"""
        request_id = str(request.headers.get("x-request-id", "")).strip() or str(uuid.uuid4())
        g.request_id = request_id
        g.request_started_at = time.perf_counter()
        set_request_id(request_id)
        access_logger.info(
            "http_request_start %s",
            summarize_http_context(
                method=request.method,
                path=request.path,
                query=request.query_string.decode("utf-8", errors="ignore"),
                client=request.remote_addr or "-",
                request_id=request_id,
                payload=_preview_request_payload(),
            ),
        )

    @app.before_request
    def _check_api_key():
        """全局 before_request：对健康检查与控制台路径豁免鉴权。"""
        if not _ORCHESTRATOR_API_KEY:
            return None
        if request.path in _AUTH_EXEMPT_PATHS:
            return None
        if any(request.path.startswith(p) for p in _AUTH_EXEMPT_PREFIXES):
            return None
        token = (request.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
        if not token:
            token = (request.headers.get("X-Api-Key") or "").strip()
        if token != _ORCHESTRATOR_API_KEY:
            return jsonify({"error": {"code": "unauthorized", "message": "invalid or missing API key"}}), 401
        return None

    @app.after_request
    def _write_request_id_header(response: Response):
        """回写 X-Request-Id 并记录请求耗时。"""
        request_id = str(getattr(g, "request_id", "")).strip()
        if request_id:
            response.headers["X-Request-Id"] = request_id
        started_at = float(getattr(g, "request_started_at", 0.0) or 0.0)
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2) if started_at > 0 else -1.0
        access_logger.info(
            "http_request_end %s",
            summarize_http_context(
                method=request.method,
                path=request.path,
                query=request.query_string.decode("utf-8", errors="ignore"),
                client=request.remote_addr or "-",
                request_id=request_id,
                status_code=response.status_code,
                duration_ms=duration_ms,
            ),
        )
        return response

    @app.errorhandler(OrchestratorError)
    def handle_orchestrator_error(exc: OrchestratorError):
        access_logger.warning(
            "http_request_orchestrator_error %s",
            summarize_http_context(
                method=request.method,
                path=request.path,
                query=request.query_string.decode("utf-8", errors="ignore"),
                client=request.remote_addr or "-",
                request_id=str(getattr(g, "request_id", "")).strip() or "-",
                status_code=exc.status_code,
                error=exc.to_response(),
            ),
        )
        return jsonify(exc.to_response()), exc.status_code

    @app.errorhandler(404)
    def handle_not_found(_exc):
        access_logger.warning(
            "http_request_not_found %s",
            summarize_http_context(
                method=request.method,
                path=request.path,
                query=request.query_string.decode("utf-8", errors="ignore"),
                client=request.remote_addr or "-",
                request_id=str(getattr(g, "request_id", "")).strip() or "-",
                status_code=404,
            ),
        )
        return jsonify({"error": {"code": "not_found", "message": "Route not found"}}), 404

    @app.errorhandler(Exception)
    def handle_internal_error(exc):
        if isinstance(exc, OrchestratorError):
            return jsonify(exc.to_response()), exc.status_code
        access_logger.exception(
            "http_request_unhandled_exception %s",
            summarize_http_context(
                method=request.method,
                path=request.path,
                query=request.query_string.decode("utf-8", errors="ignore"),
                client=request.remote_addr or "-",
                request_id=str(getattr(g, "request_id", "")).strip() or "-",
                status_code=500,
                error=exc,
            ),
        )
        return jsonify({"error": {"code": "internal_error", "message": "an unexpected error occurred"}}), 500

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/health/llm")
    def llm_health():
        probe_raw = str(request.args.get("probe", "true")).strip().lower()
        probe = probe_raw not in {"0", "false", "off", "no"}
        return jsonify(orchestrator_service.get_llm_health(probe=probe))

    @app.get("/")
    @app.get("/console")
    def console_index():
        return Response(_CONSOLE_HTML, mimetype="text/html")

    @app.get("/console/app.js")
    def console_app_js():
        return Response(_CONSOLE_JS, mimetype="application/javascript")

    @app.get("/console/styles.css")
    def console_styles():
        return Response(_CONSOLE_CSS, mimetype="text/css")

    @app.get("/assets/scaffold/templates")
    def list_scaffold_templates():
        return jsonify(asset_tool_service.list_scaffold_templates())

    @app.get("/assets/scaffold/templates/<template_name>")
    def get_scaffold_template(template_name: str):
        return jsonify(asset_tool_service.get_scaffold_template(template_name))

    @app.get("/reports/latest")
    def get_latest_report():
        return jsonify(orchestrator_service.get_latest_report())

    @app.get("/reports/<case_id>")
    def get_report(case_id: str):
        return jsonify(orchestrator_service.get_report(case_id))

    @app.get("/runners/catalog")
    def get_runner_catalog():
        return jsonify(orchestrator_service.list_runners())

    @app.get("/failures/clusters")
    def get_failure_clusters():
        limit = _read_int_query_arg("limit", default=200, min_value=1, max_value=2000)
        max_clusters = _read_int_query_arg("max_clusters", default=20, min_value=1, max_value=200)
        queue = request.args.get("queue", "")
        failure_class = request.args.get("failure_class", "")
        severity = request.args.get("severity", "")
        return jsonify(
            orchestrator_service.get_failure_clusters(
                limit=limit,
                max_clusters=max_clusters,
                queue=queue,
                failure_class=failure_class,
                severity=severity,
            )
        )

    @app.get("/failures/clusters/<cluster_id>")
    def get_failure_cluster(cluster_id: str):
        limit = _read_int_query_arg("limit", default=200, min_value=1, max_value=2000)
        return jsonify(orchestrator_service.get_failure_cluster(cluster_id=cluster_id, limit=limit))

    @app.post("/orchestrate")
    def orchestrate():
        payload = _read_json_object()
        mode = _resolve_mode(payload)
        execute = _resolve_execute_flag(payload, mode)
        orchestrate_kwargs = {
            "requirement": payload.get("requirement", ""),
            "page": payload.get("page", ""),
            "execute": execute,
            "source": payload.get("source", "manual"),
            "mode": mode,
            "runner": payload.get("runner", "playwright"),
        }
        optional_fields = [
            "input_sources",
            "openapi_spec",
            "prd_text",
            "prd_url",
            "user_story",
            "git_diff",
            "git_diff_path",
            "openapi_url",
            "defect_ticket",
            "runtime_logs",
        ]
        for field in optional_fields:
            value = payload.get(field)
            if value is None:
                continue
            orchestrate_kwargs[field] = value

        result = orchestrator_service.orchestrate(**orchestrate_kwargs)
        return jsonify(orchestrator_service.serialize_result(result)), 201

    @app.post("/requirements/parse")
    def parse_requirement():
        payload = _read_json_object()
        parse_kwargs = {
            "requirement": payload.get("requirement", ""),
            "page": payload.get("page", ""),
            "source": payload.get("source", "manual"),
        }
        optional_fields = [
            "input_sources",
            "openapi_spec",
            "prd_text",
            "prd_url",
            "user_story",
            "git_diff",
            "git_diff_path",
            "openapi_url",
            "defect_ticket",
            "runtime_logs",
        ]
        for field in optional_fields:
            value = payload.get(field)
            if value is None:
                continue
            parse_kwargs[field] = value
        parsed = orchestrator_service.parse_requirement(**parse_kwargs)
        markdown = _render_requirement_analysis_markdown(orchestrator_service, parsed if isinstance(parsed, dict) else {})
        return (
            jsonify(
                {
                    "requirement_spec": parsed,
                    "requirement_analysis_markdown": markdown,
                    "output_contract": {
                        "machine_schema": "RequirementSpecV1",
                        "human_render": "RequirementAnalysisMarkdownV1",
                        "rendered_by": "orchestrator-api",
                    },
                }
            ),
            201,
        )

    @app.post("/risk/evaluate")
    def evaluate_risk():
        payload = _read_json_object()
        risk_report = orchestrator_service.evaluate_risk(
            requirement_spec=payload.get("requirement_spec", {}),
            execution_plan=payload.get("execution_plan", {}),
            execution_record=payload.get("execution_record", {}),
            failure_analysis=payload.get("failure_analysis", {}),
            failure_triage=payload.get("failure_triage", {}),
        )
        return (
            jsonify(
                {
                    "risk_report": risk_report,
                    "output_contract": {
                        "machine_schema": "RiskReportV1",
                        "human_render": "RiskReportMarkdownV1",
                        "rendered_by": "orchestrator-api",
                    },
                }
            ),
            201,
        )

    @app.post("/failures/triage")
    def triage_failure():
        payload = _read_json_object()
        triage_result = orchestrator_service.triage_failure(
            failure_analysis=payload.get("failure_analysis", {}),
            execution_record=payload.get("execution_record", {}),
            evidence_manifest=payload.get("evidence_manifest", {}),
            report=payload.get("report", {}),
        )
        return (
            jsonify(
                {
                    "failure_triage": triage_result,
                    "output_contract": {
                        "machine_schema": "FailureTriageV1",
                        "human_render": "FailureTriageMarkdownV1",
                        "rendered_by": "orchestrator-api",
                    },
                }
            ),
            201,
        )

    @app.get("/requirements/telemetry/summary")
    def requirement_telemetry_summary():
        limit = _read_int_query_arg("limit", default=500, min_value=1, max_value=5000)
        prompt_version = request.args.get("prompt_version", "")
        model = request.args.get("model", "")
        mode = request.args.get("mode", "")
        stage = request.args.get("stage", "")
        return jsonify(
            orchestrator_service.get_requirement_parse_telemetry_summary(
                limit=limit,
                prompt_version=prompt_version,
                model=model,
                mode=mode,
                stage=stage,
            )
        )

    @app.post("/healing/preview")
    def healing_preview():
        payload = _read_json_object()
        result = orchestrator_service.preview_self_healing_advice(
            page=payload.get("page", ""),
            case=payload.get("case"),
            failure_reason=payload.get("failure_reason", ""),
            failure_analysis=payload.get("failure_analysis"),
        )
        return jsonify({"self_healing_advice": result})

    @app.post("/assets/page-objects")
    def create_page_object():
        payload = _read_json_object()
        result = asset_tool_service.create_page_object(
            page=payload.get("page", ""),
            description=payload.get("description", ""),
        )
        return jsonify(result), 201

    @app.post("/assets/page-objects/<page>/elements")
    def add_page_element(page: str):
        payload = _read_json_object()
        result = asset_tool_service.add_page_element(
            page=page,
            element_name=payload.get("name", ""),
            locator_type=payload.get("locator_type", ""),
            locator_value=payload.get("locator_value", ""),
            role=payload.get("role"),
            description=payload.get("description"),
        )
        return jsonify(result), 201

    @app.post("/assets/test-cases/sync")
    def sync_test_case():
        payload = _read_json_object()
        result = asset_tool_service.sync_test_case(
            file_path=payload.get("file", ""),
            menu_target=payload.get("menu_target"),
            assert_target=payload.get("assert_target"),
        )
        return jsonify(result)

    @app.post("/assets/scaffold")
    def scaffold_assets():
        payload = _read_json_object()
        result = asset_tool_service.scaffold_page_assets(
            page=payload.get("page", ""),
            title=payload.get("title", ""),
            requirement=payload.get("requirement", ""),
            description=payload.get("description", ""),
            priority=payload.get("priority", "P1"),
            menu_label=payload.get("menu_label"),
            assert_label=payload.get("assert_label"),
            template=payload.get("template"),
            elements=payload.get("elements") if payload.get("elements") is not None else None,
        )
        return jsonify(result), 201

    def _read_json_object() -> dict:
        content_type = request.headers.get("Content-Type", "")
        if "application/json" not in content_type.lower():
            raise OrchestratorError(
                code="unsupported_media_type",
                message="Content-Type must be application/json",
                status_code=415,
            )
        raw_body = request.get_data(cache=False, as_text=True)
        try:
            payload = json.loads(raw_body or "{}")
        except json.JSONDecodeError as exc:
            raise OrchestratorError(
                code="invalid_json",
                message="Request body is not valid JSON",
                status_code=400,
            ) from exc
        if not isinstance(payload, dict):
            raise OrchestratorError(
                code="invalid_json",
                message="JSON body must be an object",
                status_code=400,
            )
        return payload

    def _read_int_query_arg(name: str, *, default: int, min_value: int, max_value: int) -> int:
        raw = request.args.get(name, str(default))
        try:
            value = int(str(raw).strip())
        except (TypeError, ValueError) as exc:
            raise OrchestratorValidationError(f"{name} must be an integer") from exc
        return max(min_value, min(value, max_value))

    app.config["ORCHESTRATOR_SERVICE"] = orchestrator_service
    app.config["ASSET_SERVICE"] = asset_tool_service
    return app


def create_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    service: OrchestratorService | None = None,
    asset_service: AssetService | None = None,
):
    """创建 werkzeug 多线程 HTTP 服务器（CLI serve 子命令使用）。"""
    app = create_app(service=service, asset_service=asset_service)
    return make_server(host, port, app, threaded=True)


def _resolve_mode(payload: dict) -> str:
    """从请求体解析编排模式：generate_only 或 generate_and_run。"""
    mode = payload.get("mode")
    if mode is None:
        return "generate_and_run" if bool(payload.get("execute", False)) else "generate_only"

    normalized_mode = str(mode).strip().lower()
    if normalized_mode in {"generate_only", "generate_and_run"}:
        return normalized_mode
    raise OrchestratorValidationError("mode must be one of: generate_only, generate_and_run")


def _resolve_execute_flag(payload: dict, mode: str) -> bool:
    """根据 mode 推断是否执行生成的用例。"""
    if payload.get("mode") is None:
        return bool(payload.get("execute", False))
    return mode == "generate_and_run"


# 模块级应用：WSGI 用 flask_app，ASGI 用 app 适配器
flask_app = create_app()
app = WSGIToASGIAdapter(flask_app)
