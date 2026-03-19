import json
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

REPO_ROOT = Path(__file__).resolve().parents[4]
ORCHESTRATOR_SRC = REPO_ROOT / "apps" / "ai-orchestrator" / "src"
if str(ORCHESTRATOR_SRC) not in sys.path:
    sys.path.insert(0, str(ORCHESTRATOR_SRC))

from asset_service import AssetService  # noqa: E402
from orchestrator_service import (  # noqa: E402
    OrchestratorError,
    OrchestratorService,
    OrchestratorValidationError,
)

router = APIRouter(tags=["legacy-console"])


def _asset_service() -> AssetService:
    return AssetService(repo_root=REPO_ROOT)


def _orchestrator_service() -> OrchestratorService:
    return OrchestratorService(repo_root=REPO_ROOT)


def _error_response(exc: OrchestratorError) -> JSONResponse:
    return JSONResponse(exc.to_response(), status_code=exc.status_code)


async def _read_json_object(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type.lower():
        raise OrchestratorError(
            code="unsupported_media_type",
            message="Content-Type must be application/json",
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        )
    raw_body = await request.body()
    try:
        payload = json.loads(raw_body or b"{}")
    except json.JSONDecodeError as exc:
        raise OrchestratorError(
            code="invalid_json",
            message="Request body is not valid JSON",
            status_code=status.HTTP_400_BAD_REQUEST,
        ) from exc
    if not isinstance(payload, dict):
        raise OrchestratorError(
            code="invalid_json",
            message="JSON body must be an object",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return payload


def _resolve_mode(payload: dict[str, Any]) -> str:
    mode = payload.get("mode")
    if mode is None:
        return "generate_and_run" if bool(payload.get("execute", False)) else "generate_only"
    normalized_mode = str(mode).strip().lower()
    if normalized_mode in {"generate_only", "generate_and_run"}:
        return normalized_mode
    raise OrchestratorValidationError("mode must be one of: generate_only, generate_and_run")


def _resolve_execute_flag(payload: dict[str, Any], mode: str) -> bool:
    if payload.get("mode") is None:
        return bool(payload.get("execute", False))
    return mode == "generate_and_run"


@router.get("/assets/scaffold/templates")
def list_scaffold_templates() -> dict[str, Any]:
    try:
        return _asset_service().list_scaffold_templates()
    except OrchestratorError as exc:
        return _error_response(exc)


@router.get("/assets/scaffold/templates/{template_name}")
def get_scaffold_template(template_name: str) -> dict[str, Any]:
    try:
        return _asset_service().get_scaffold_template(template_name)
    except OrchestratorError as exc:
        return _error_response(exc)


@router.post("/assets/scaffold", status_code=status.HTTP_201_CREATED)
async def scaffold_assets(request: Request) -> dict[str, Any]:
    try:
        payload = await _read_json_object(request)
        result = _asset_service().scaffold_page_assets(
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
        return result
    except OrchestratorError as exc:
        return _error_response(exc)


@router.post("/assets/page-objects", status_code=status.HTTP_201_CREATED)
async def create_page_object(request: Request) -> dict[str, Any]:
    try:
        payload = await _read_json_object(request)
        result = _asset_service().create_page_object(
            page=payload.get("page", ""),
            description=payload.get("description", ""),
        )
        return result
    except OrchestratorError as exc:
        return _error_response(exc)


@router.post("/assets/page-objects/{page}/elements", status_code=status.HTTP_201_CREATED)
async def add_page_element(page: str, request: Request) -> dict[str, Any]:
    try:
        payload = await _read_json_object(request)
        result = _asset_service().add_page_element(
            page=page,
            element_name=payload.get("name", ""),
            locator_type=payload.get("locator_type", ""),
            locator_value=payload.get("locator_value", ""),
            role=payload.get("role"),
            description=payload.get("description"),
        )
        return result
    except OrchestratorError as exc:
        return _error_response(exc)


@router.post("/assets/test-cases/sync")
async def sync_test_case(request: Request) -> dict[str, Any]:
    try:
        payload = await _read_json_object(request)
        result = _asset_service().sync_test_case(
            file_path=payload.get("file", ""),
            menu_target=payload.get("menu_target"),
            assert_target=payload.get("assert_target"),
        )
        return result
    except OrchestratorError as exc:
        return _error_response(exc)


@router.get("/reports/latest")
def get_latest_report() -> dict[str, Any]:
    try:
        return _orchestrator_service().get_latest_report()
    except OrchestratorError as exc:
        return _error_response(exc)


@router.get("/reports/{case_id}")
def get_report(case_id: str) -> dict[str, Any]:
    try:
        return _orchestrator_service().get_report(case_id)
    except OrchestratorError as exc:
        return _error_response(exc)


@router.get("/failures/clusters")
def get_failure_clusters(request: Request) -> dict[str, Any]:
    try:
        limit = _read_int_query_arg(request, "limit", default=200, min_value=1, max_value=2000)
        max_clusters = _read_int_query_arg(request, "max_clusters", default=20, min_value=1, max_value=200)
        return _orchestrator_service().get_failure_clusters(
            limit=limit,
            max_clusters=max_clusters,
            queue=request.query_params.get("queue", ""),
            failure_class=request.query_params.get("failure_class", ""),
            severity=request.query_params.get("severity", ""),
        )
    except OrchestratorError as exc:
        return _error_response(exc)


@router.get("/failures/clusters/{cluster_id}")
def get_failure_cluster(cluster_id: str, request: Request) -> dict[str, Any]:
    try:
        limit = _read_int_query_arg(request, "limit", default=200, min_value=1, max_value=2000)
        return _orchestrator_service().get_failure_cluster(cluster_id=cluster_id, limit=limit)
    except OrchestratorError as exc:
        return _error_response(exc)


@router.post("/orchestrate", status_code=status.HTTP_201_CREATED)
async def orchestrate(request: Request) -> dict[str, Any]:
    try:
        payload = await _read_json_object(request)
        mode = _resolve_mode(payload)
        execute = _resolve_execute_flag(payload, mode)
        service = _orchestrator_service()
        orchestrate_kwargs: dict[str, Any] = {
            "requirement": payload.get("requirement", ""),
            "page": payload.get("page", ""),
            "execute": execute,
            "source": payload.get("source", "manual"),
            "mode": mode,
        }
        for field in [
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
        ]:
            if field in payload and payload.get(field) is not None:
                orchestrate_kwargs[field] = payload.get(field)
        result = service.orchestrate(**orchestrate_kwargs)
        return service.serialize_result(result)
    except OrchestratorError as exc:
        return _error_response(exc)


def _read_int_query_arg(request: Request, name: str, *, default: int, min_value: int, max_value: int) -> int:
    raw = request.query_params.get(name, str(default))
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError) as exc:
        raise OrchestratorValidationError(f"{name} must be an integer") from exc
    return max(min_value, min(value, max_value))


@router.post("/requirements/parse", status_code=status.HTTP_201_CREATED)
async def parse_requirement(request: Request) -> dict[str, Any]:
    try:
        payload = await _read_json_object(request)
        parse_kwargs: dict[str, Any] = {
            "requirement": payload.get("requirement", ""),
            "page": payload.get("page", ""),
            "source": payload.get("source", "manual"),
        }
        for field in [
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
        ]:
            if field in payload and payload.get(field) is not None:
                parse_kwargs[field] = payload.get(field)
        parsed = _orchestrator_service().parse_requirement(**parse_kwargs)
        return {"requirement_spec": parsed}
    except OrchestratorError as exc:
        return _error_response(exc)


@router.post("/scripts/generate", status_code=status.HTTP_201_CREATED)
async def generate_script(request: Request) -> dict[str, Any]:
    try:
        payload = await _read_json_object(request)
        generated = _orchestrator_service().generate_script(
            case=payload.get("case", {}),
            framework=payload.get("framework", "playwright"),
            language=payload.get("language", "python"),
        )
        return {"generated_script": generated}
    except OrchestratorError as exc:
        return _error_response(exc)


@router.post("/execution/plan", status_code=status.HTTP_201_CREATED)
async def plan_execution(request: Request) -> dict[str, Any]:
    try:
        payload = await _read_json_object(request)
        execution_plan = _orchestrator_service().plan_execution(
            case=payload.get("case", {}),
            execution_requested=bool(payload.get("execution_requested", False)),
            source=payload.get("source", "manual"),
            execution_config=payload.get("execution_config", {}),
        )
        return {"execution_plan": execution_plan}
    except OrchestratorError as exc:
        return _error_response(exc)


@router.post("/risk/evaluate", status_code=status.HTTP_201_CREATED)
async def evaluate_risk(request: Request) -> dict[str, Any]:
    try:
        payload = await _read_json_object(request)
        risk_report = _orchestrator_service().evaluate_risk(
            requirement_spec=payload.get("requirement_spec", {}),
            execution_plan=payload.get("execution_plan", {}),
            execution_record=payload.get("execution_record", {}),
            failure_analysis=payload.get("failure_analysis", {}),
            failure_triage=payload.get("failure_triage", {}),
        )
        return {"risk_report": risk_report}
    except OrchestratorError as exc:
        return _error_response(exc)


@router.post("/failures/triage", status_code=status.HTTP_201_CREATED)
async def triage_failure(request: Request) -> dict[str, Any]:
    try:
        payload = await _read_json_object(request)
        triage = _orchestrator_service().triage_failure(
            failure_analysis=payload.get("failure_analysis", {}),
            execution_record=payload.get("execution_record", {}),
            evidence_manifest=payload.get("evidence_manifest", {}),
            report=payload.get("report", {}),
        )
        return {"failure_triage": triage}
    except OrchestratorError as exc:
        return _error_response(exc)


@router.post("/healing/preview")
async def healing_preview(request: Request) -> dict[str, Any]:
    try:
        payload = await _read_json_object(request)
        result = _orchestrator_service().preview_self_healing_advice(
            page=payload.get("page", ""),
            case=payload.get("case"),
            failure_reason=payload.get("failure_reason", ""),
            failure_analysis=payload.get("failure_analysis"),
        )
        return {"self_healing_advice": result}
    except OrchestratorError as exc:
        return _error_response(exc)
