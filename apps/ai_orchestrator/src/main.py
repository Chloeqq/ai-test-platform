"""AI 编排器 HTTP API：FastAPI 路由、鉴权、可观测性与控制台静态资源。"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from asset_service import AssetService
from shared_backend.observability import (
    configure_logging,
    set_request_id,
    summarize_http_context,
    summarize_log_value,
)
from orchestrator_service import (
    OrchestratorError,
    OrchestratorService,
    OrchestratorValidationError,
)

_ORCHESTRATOR_API_KEY = os.environ.get("ORCHESTRATOR_API_KEY", "").strip()
_AUTH_EXEMPT_PATHS = frozenset({"/health", "/health/llm"})
_AUTH_EXEMPT_PREFIXES = ("/console",)

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


# ---------------------------------------------------------------------------
# 鉴权
# ---------------------------------------------------------------------------

async def _require_api_key(request: Request) -> None:
    if not _ORCHESTRATOR_API_KEY:
        return
    if request.url.path in _AUTH_EXEMPT_PATHS:
        return
    if any(request.url.path.startswith(p) for p in _AUTH_EXEMPT_PREFIXES):
        return
    token = (request.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
    if not token:
        token = (request.headers.get("X-Api-Key") or "").strip()
    if token != _ORCHESTRATOR_API_KEY:
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized", "message": "invalid or missing API key"}})


# ---------------------------------------------------------------------------
# 请求 ID + 访问日志中间件
# ---------------------------------------------------------------------------

class _RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = (request.headers.get("x-request-id") or "").strip() or str(uuid.uuid4())
        started_at = time.perf_counter()
        set_request_id(request_id)

        access_logger.info(
            "http_request_start %s",
            summarize_http_context(
                method=request.method, path=request.url.path,
                query=request.url.query or "",
                client=request.client.host if request.client else "-",
                request_id=request_id,
                payload=_summarize_body(request),
            ),
        )

        response = await call_next(request)
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)

        response.headers["X-Request-Id"] = request_id
        access_logger.info(
            "http_request_end %s",
            summarize_http_context(
                method=request.method, path=request.url.path,
                query=request.url.query or "",
                client=request.client.host if request.client else "-",
                request_id=request_id, status_code=response.status_code,
                duration_ms=duration_ms,
            ),
        )
        return response


def _summarize_body(request: Request) -> str:
    if request.method not in {"POST", "PUT", "PATCH"}:
        return ""
    content_type = request.headers.get("Content-Type", "")
    if "application/json" not in content_type.lower():
        return ""
    return "(body available via FastAPI)"


# ---------------------------------------------------------------------------
# 工厂函数 + 依赖
# ---------------------------------------------------------------------------

_orchestrator_svc: OrchestratorService | None = None
_asset_svc: AssetService | None = None


def _get_orchestrator_service() -> OrchestratorService:
    global _orchestrator_svc
    if _orchestrator_svc is None:
        _orchestrator_svc = OrchestratorService()
    return _orchestrator_svc


def _get_asset_service() -> AssetService:
    global _asset_svc
    if _asset_svc is None:
        _asset_svc = AssetService()
    return _asset_svc


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------

_OPTIONAL_FIELDS = [
    "input_sources", "openapi_spec", "prd_text", "prd_url",
    "user_story", "git_diff", "git_diff_path", "openapi_url",
    "defect_ticket", "runtime_logs",
]


def _pick_optional(payload: dict) -> dict:
    result: dict[str, Any] = {}
    for field in _OPTIONAL_FIELDS:
        value = payload.get(field)
        if value is not None:
            result[field] = value
    return result


def _read_int_query(value: str, *, default: int, min_value: int, max_value: int) -> int:
    try:
        v = int(str(value).strip())
    except (TypeError, ValueError):
        raise OrchestratorValidationError("must be an integer")
    return max(min_value, min(v, max_value))


# ---------------------------------------------------------------------------
# 应用创建
# ---------------------------------------------------------------------------

def _register_core_routes(app: FastAPI) -> None:
    """注册异常处理器、健康检查、控制台路由。"""

    @app.exception_handler(OrchestratorError)
    async def _handle_orchestrator_error(request: Request, exc: OrchestratorError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_response())

    @app.exception_handler(OrchestratorValidationError)
    async def _handle_validation_error(request: Request, exc: OrchestratorValidationError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_response())

    @app.get("/health", dependencies=[])
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/health/llm", dependencies=[])
    async def llm_health(probe: str = Query("true")) -> dict:
        probe_bool = probe.lower() not in {"0", "false", "off", "no"}
        return _get_orchestrator_service().get_llm_health(probe=probe_bool)

    @app.get("/", include_in_schema=False)
    @app.get("/console", include_in_schema=False)
    async def console_index() -> HTMLResponse:
        return HTMLResponse(_CONSOLE_HTML)

    @app.get("/console/app.js", include_in_schema=False)
    async def console_js() -> PlainTextResponse:
        return PlainTextResponse(_CONSOLE_JS, media_type="application/javascript")

    @app.get("/console/styles.css", include_in_schema=False)
    async def console_css() -> PlainTextResponse:
        return PlainTextResponse(_CONSOLE_CSS, media_type="text/css")


def _register_api_routes(app: FastAPI) -> None:
    """注册编排、解析、风险、分诊、遥测、自愈、报表、运行器、聚类路由。"""

    @app.post("/orchestrate", status_code=201)
    async def orchestrate(
        payload: dict[str, Any],
        svc: OrchestratorService = Depends(_get_orchestrator_service),
    ) -> dict:
        mode = payload.get("mode")
        if mode is not None:
            normalized_mode = str(mode).strip().lower()
            if normalized_mode not in {"generate_only", "generate_and_run"}:
                raise OrchestratorValidationError("mode must be one of: generate_only, generate_and_run")
            execute = normalized_mode == "generate_and_run"
        else:
            execute = bool(payload.get("execute", False))
            normalized_mode = "generate_and_run" if execute else "generate_only"

        kwargs: dict[str, Any] = {
            "requirement": payload.get("requirement", ""),
            "page": payload.get("page", ""),
            "execute": execute,
            "source": payload.get("source", "manual"),
            "mode": normalized_mode,
            "runner": payload.get("runner", "playwright"),
            **_pick_optional(payload),
        }
        result = svc.orchestrate(**kwargs)
        return svc.serialize_result(result)

    # ---- Requirement Parse ----

    @app.post("/requirements/parse", status_code=201)
    async def parse_requirement(
        payload: dict[str, Any],
        svc: OrchestratorService = Depends(_get_orchestrator_service),
    ) -> dict:
        kwargs = {
            "requirement": payload.get("requirement", ""),
            "page": payload.get("page", ""),
            "source": payload.get("source", "manual"),
            **_pick_optional(payload),
        }
        parsed = svc.parse_requirement(**kwargs)
        return {
            "requirement_spec": parsed,
            "requirement_analysis_markdown": _render_markdown(svc, parsed if isinstance(parsed, dict) else {}),
            "output_contract": {
                "machine_schema": "RequirementSpecV1",
                "human_render": "RequirementAnalysisMarkdownV1",
                "rendered_by": "orchestrator-api",
            },
        }

    # ---- Risk ----

    @app.post("/risk/evaluate", status_code=201)
    async def evaluate_risk(
        payload: dict[str, Any],
        svc: OrchestratorService = Depends(_get_orchestrator_service),
    ) -> dict:
        risk_report = svc.evaluate_risk(
            requirement_spec=payload.get("requirement_spec", {}),
            execution_plan=payload.get("execution_plan", {}),
            execution_record=payload.get("execution_record", {}),
            failure_analysis=payload.get("failure_analysis", {}),
            failure_triage=payload.get("failure_triage", {}),
        )
        return {
            "risk_report": risk_report,
            "output_contract": {"machine_schema": "RiskReportV1", "human_render": "RiskReportMarkdownV1", "rendered_by": "orchestrator-api"},
        }

    # ---- Failure Triage ----

    @app.post("/failures/triage", status_code=201)
    async def triage_failure(
        payload: dict[str, Any],
        svc: OrchestratorService = Depends(_get_orchestrator_service),
    ) -> dict:
        triage_result = svc.triage_failure(
            failure_analysis=payload.get("failure_analysis", {}),
            execution_record=payload.get("execution_record", {}),
            evidence_manifest=payload.get("evidence_manifest", {}),
            report=payload.get("report", {}),
        )
        return {
            "failure_triage": triage_result,
            "output_contract": {"machine_schema": "FailureTriageV1", "human_render": "FailureTriageMarkdownV1", "rendered_by": "orchestrator-api"},
        }

    # ---- Telemetry ----

    @app.get("/requirements/telemetry/summary")
    async def requirement_telemetry_summary(
        limit: int = Query(500, ge=1, le=5000),
        prompt_version: str = Query(""),
        model: str = Query(""),
        mode: str = Query(""),
        stage: str = Query(""),
        svc: OrchestratorService = Depends(_get_orchestrator_service),
    ) -> dict:
        return svc.get_requirement_parse_telemetry_summary(
            limit=limit, prompt_version=prompt_version,
            model=model, mode=mode, stage=stage,
        )

    # ---- Self-Healing ----

    @app.post("/healing/preview")
    async def healing_preview(
        payload: dict[str, Any],
        svc: OrchestratorService = Depends(_get_orchestrator_service),
    ) -> dict:
        result = svc.preview_self_healing_advice(
            page=payload.get("page", ""),
            case=payload.get("case"),
            failure_reason=payload.get("failure_reason", ""),
            failure_analysis=payload.get("failure_analysis"),
        )
        return {"self_healing_advice": result}

    # ---- Reports ----

    @app.get("/reports/latest")
    async def get_latest_report(svc: OrchestratorService = Depends(_get_orchestrator_service)) -> dict:
        return svc.get_latest_report()

    @app.get("/reports/{case_id}")
    async def get_report(case_id: str, svc: OrchestratorService = Depends(_get_orchestrator_service)) -> dict:
        return svc.get_report(case_id)

    # ---- Runners ----

    @app.get("/runners/catalog")
    async def runners_catalog(svc: OrchestratorService = Depends(_get_orchestrator_service)) -> dict:
        return svc.list_runners()

    # ---- Failure Clusters ----

    @app.get("/failures/clusters")
    async def failure_clusters(
        limit: int = Query(200, ge=1, le=2000),
        max_clusters: int = Query(20, ge=1, le=200),
        queue: str = Query(""),
        failure_class: str = Query(""),
        severity: str = Query(""),
        svc: OrchestratorService = Depends(_get_orchestrator_service),
    ) -> dict:
        return svc.get_failure_clusters(
            limit=limit, max_clusters=max_clusters,
            queue=queue, failure_class=failure_class, severity=severity,
        )

    @app.get("/failures/clusters/{cluster_id}")
    async def failure_cluster(
        cluster_id: str,
        limit: int = Query(200, ge=1, le=2000),
        svc: OrchestratorService = Depends(_get_orchestrator_service),
    ) -> dict:
        return svc.get_failure_cluster(cluster_id=cluster_id, limit=limit)

def _register_asset_routes(app: FastAPI) -> None:
    """注册资产工具路由与鉴权中间件。"""

    @app.get("/assets/scaffold/templates")
    async def list_scaffold_templates(asset: AssetService = Depends(_get_asset_service)) -> dict:
        return asset.list_scaffold_templates()

    @app.get("/assets/scaffold/templates/{template_name}")
    async def get_scaffold_template(template_name: str, asset: AssetService = Depends(_get_asset_service)) -> dict:
        return asset.get_scaffold_template(template_name)

    @app.post("/assets/page-objects", status_code=201)
    async def create_page_object(payload: dict[str, Any], asset: AssetService = Depends(_get_asset_service)) -> dict:
        return asset.create_page_object(
            page=payload.get("page", ""), description=payload.get("description", ""))

    @app.post("/assets/page-objects/{page}/elements", status_code=201)
    async def add_page_element(page: str, payload: dict[str, Any], asset: AssetService = Depends(_get_asset_service)) -> dict:
        return asset.add_page_element(
            page=page, element_name=payload.get("name", ""),
            locator_type=payload.get("locator_type", ""), locator_value=payload.get("locator_value", ""),
            role=payload.get("role"), description=payload.get("description"))

    @app.post("/assets/test-cases/sync")
    async def sync_test_case(payload: dict[str, Any], asset: AssetService = Depends(_get_asset_service)) -> dict:
        return asset.sync_test_case(
            file_path=payload.get("file", ""), menu_target=payload.get("menu_target"),
            assert_target=payload.get("assert_target"))

    @app.post("/assets/scaffold", status_code=201)
    async def scaffold_assets(payload: dict[str, Any], asset: AssetService = Depends(_get_asset_service)) -> dict:
        return asset.scaffold_page_assets(
            page=payload.get("page", ""), title=payload.get("title", ""),
            requirement=payload.get("requirement", ""), description=payload.get("description", ""),
            priority=payload.get("priority", "P1"), menu_label=payload.get("menu_label"),
            assert_label=payload.get("assert_label"), template=payload.get("template"),
            elements=payload.get("elements") if payload.get("elements") is not None else None)

    @app.middleware("http")
    async def _auth_middleware(request: Request, call_next):
        await _require_api_key(request)
        return await call_next(request)


def create_app(
    service: OrchestratorService | None = None,
    asset_service: AssetService | None = None,
) -> FastAPI:
    """创建 FastAPI 应用，注册所有路由。"""
    global _orchestrator_svc, _asset_svc
    if service is not None:
        _orchestrator_svc = service
    if asset_service is not None:
        _asset_svc = asset_service

    app = FastAPI(title="AI Orchestrator", version="1.0")
    app.add_middleware(_RequestLoggingMiddleware)
    _register_core_routes(app)
    _register_api_routes(app)
    _register_asset_routes(app)
    return app


# ---------------------------------------------------------------------------
# Markdown 渲染
# ---------------------------------------------------------------------------

def _render_markdown(svc: OrchestratorService, requirement_spec: dict[str, object]) -> str:
    renderer = getattr(svc, "render_requirement_spec_markdown", None)
    if callable(renderer):
        try:
            return str(renderer(requirement_spec))
        except Exception:
            pass
    page = str(requirement_spec.get("page", "")).strip() if isinstance(requirement_spec, dict) else ""
    priority = str(requirement_spec.get("priority", "")).strip() if isinstance(requirement_spec, dict) else ""
    return f"# 需求测试点分析\n\n- 页面: `{page or '-'}`\n- 优先级: `{priority or 'P1'}`\n"


# ---------------------------------------------------------------------------
# 模块级应用
# ---------------------------------------------------------------------------

def create_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    service: Any = None,
    asset_service: Any = None,
):
    """创建 uvicorn 多线程 HTTP 服务器（集成测试使用）。"""
    import uvicorn

    _app = create_app(service=service, asset_service=asset_service)
    config = uvicorn.Config(_app, host=host, port=port, log_level="error")
    return uvicorn.Server(config)


app = create_app()
