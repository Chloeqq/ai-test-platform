import json
import logging
import time
import uuid
from pathlib import Path

from flask import Flask, Response, g, jsonify, request, send_from_directory
from starlette.middleware.wsgi import WSGIMiddleware
from werkzeug.serving import make_server

from asset_service import AssetService
from apps.shared_backend.observability import configure_logging, set_request_id
from orchestrator_service import OrchestratorError, OrchestratorService, OrchestratorValidationError

WEB_CONSOLE_ROOT = Path(__file__).resolve().parents[2] / "web-console" / "static"
configure_logging(service_name="ai-orchestrator")
access_logger = logging.getLogger("orchestrator.access")


def _render_requirement_analysis_markdown(
    service: OrchestratorService,
    requirement_spec: dict[str, object],
) -> str:
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
    app = Flask(__name__, static_folder=None)
    orchestrator_service = service or OrchestratorService()
    asset_tool_service = asset_service or AssetService()

    @app.before_request
    def _attach_request_id():
        request_id = str(request.headers.get("x-request-id", "")).strip() or str(uuid.uuid4())
        g.request_id = request_id
        g.request_started_at = time.perf_counter()
        set_request_id(request_id)

    @app.after_request
    def _write_request_id_header(response: Response):
        request_id = str(getattr(g, "request_id", "")).strip()
        if request_id:
            response.headers["X-Request-Id"] = request_id
        started_at = float(getattr(g, "request_started_at", 0.0) or 0.0)
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2) if started_at > 0 else -1.0
        access_logger.info(
            "http_request method=%s path=%s status=%s duration_ms=%.2f client=%s",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
            request.remote_addr or "-",
        )
        return response

    @app.errorhandler(OrchestratorError)
    def handle_orchestrator_error(exc: OrchestratorError):
        return jsonify(exc.to_response()), exc.status_code

    @app.errorhandler(404)
    def handle_not_found(_exc):
        return jsonify({"error": {"code": "not_found", "message": "Route not found"}}), 404

    @app.errorhandler(500)
    def handle_internal_error(exc):
        if isinstance(exc, OrchestratorError):
            return jsonify(exc.to_response()), exc.status_code
        return jsonify({"error": {"code": "internal_error", "message": str(exc)}}), 500

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/")
    @app.get("/console")
    def console_index():
        return send_from_directory(WEB_CONSOLE_ROOT, "index.html", mimetype="text/html")

    @app.get("/console/app.js")
    def console_app_js():
        return send_from_directory(
            WEB_CONSOLE_ROOT,
            "app.js",
            mimetype="application/javascript",
        )

    @app.get("/console/styles.css")
    def console_styles():
        return send_from_directory(WEB_CONSOLE_ROOT, "styles.css", mimetype="text/css")

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

    @app.post("/scripts/generate")
    def generate_script():
        payload = _read_json_object()
        script_bundle = orchestrator_service.generate_script(
            case=payload.get("case", {}),
            framework=payload.get("framework", "playwright"),
            language=payload.get("language", "python"),
        )
        return (
            jsonify(
                {
                    "generated_script": script_bundle,
                    "output_contract": {
                        "machine_schema": "GeneratedScriptV1",
                        "human_render": "GeneratedScriptPreviewMarkdownV1",
                        "rendered_by": "orchestrator-api",
                    },
                }
            ),
            201,
        )

    @app.post("/execution/plan")
    def plan_execution():
        payload = _read_json_object()
        execution_plan = orchestrator_service.plan_execution(
            case=payload.get("case", {}),
            execution_requested=bool(payload.get("execution_requested", False)),
            source=payload.get("source", "manual"),
            execution_config=payload.get("execution_config", {}),
        )
        return (
            jsonify(
                {
                    "execution_plan": execution_plan,
                    "output_contract": {
                        "machine_schema": "ExecutionPlanV1",
                        "human_render": "ExecutionPlanMarkdownV1",
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
    app = create_app(service=service, asset_service=asset_service)
    return make_server(host, port, app, threaded=True)


def _resolve_mode(payload: dict) -> str:
    mode = payload.get("mode")
    if mode is None:
        return "generate_and_run" if bool(payload.get("execute", False)) else "generate_only"

    normalized_mode = str(mode).strip().lower()
    if normalized_mode in {"generate_only", "generate_and_run"}:
        return normalized_mode
    raise OrchestratorValidationError("mode must be one of: generate_only, generate_and_run")


def _resolve_execute_flag(payload: dict, mode: str) -> bool:
    if payload.get("mode") is None:
        return bool(payload.get("execute", False))
    return mode == "generate_and_run"


flask_app = create_app()
app = WSGIMiddleware(flask_app)
