from __future__ import annotations

import difflib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence, TypeAlias

from datetime_compat import UTC
from fastapi import HTTPException, status
from shared_backend.case_ids import (
    build_case_id,
    build_case_metadata,
    infer_client_code,
    match_case_id,
    next_case_sequence,
    normalize_case_id,
    normalize_case_type as normalize_business_case_type,
    normalize_client_code,
    normalize_source_code,
)
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
import yaml

from app.models.test_case import (
    TestCase,
    TestCaseDefect,
    TestCaseExecution,
    TestCaseTreeNode,
    TestCaseVersion,
)
from app.models.test_project import TestProject
from app.schemas.test_case import (
    BatchStatusUpdatePayload,
    BatchTagsUpdatePayload,
    TestCaseCreate,
    TestCaseDataConfig,
    TestCaseScriptUpdate,
    TestCaseUpdate,
)
from app.services.test_case_bootstrap_service import (
    ensure_seed_data,
    get_module_tree_items as get_module_tree_items,
)
from app.services.test_case_data_service import (
    DataConfigPayload,
    compose_data_driven_script,
    generate_ai_script,
    normalize_case_ids,
    normalize_data_config,
    normalize_markers,
    normalize_optional_text,
    normalize_report_url as normalize_report_url,
    normalize_status,
    normalize_tags,
    normalize_test_case_type,
    normalize_test_steps,
    normalize_text_list,
    positive_ids,
    render_test_steps_text,
    refresh_existing_data_driven_script,
)
from app.services.test_case_search_service import (
    build_test_case_search_context,
    parse_test_case_search_query,
)

PaginationPayload: TypeAlias = dict[str, int | bool | None]
FilterOptionsPayload: TypeAlias = dict[str, list[str]]
StatsPayload: TypeAlias = dict[str, int | float]

REPO_ROOT = Path(__file__).resolve().parents[4]
ASSETS_CASES_ROOT = REPO_ROOT / "assets" / "test-cases"
EXECUTION_REPORTS_ROOT = REPO_ROOT / "reports" / "executions"
DEFAULT_PROJECT_CODE = "atp"


@dataclass(frozen=True)
class TestCaseListResult:
    cases: list[TestCase]
    pagination: PaginationPayload
    filters: FilterOptionsPayload
    latest_versions: dict[int, int]
    search_context: dict[str, str]
    stats: StatsPayload


@dataclass(frozen=True)
class TestCaseDetailResult:
    case: TestCase
    defects: list[TestCaseDefect]
    executions: list[TestCaseExecution]
    versions: list[TestCaseVersion]
    data_config: DataConfigPayload


@dataclass(frozen=True)
class TestCaseMutationResult:
    case: TestCase
    data_config: DataConfigPayload
    script_code: str
    latest_version_no: int | None


@dataclass(frozen=True)
class TestCaseVersionComparison:
    from_version: int
    to_version: int
    added_lines: int
    removed_lines: int
    diff_lines: list[str]


def _normalize_project_code(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    return normalized or DEFAULT_PROJECT_CODE


def _normalize_business_case_id(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    normalized = normalize_case_id(raw, fallback="").strip().lower()
    if not normalized or not match_case_id(normalized):
        return ""
    return normalized


def _ensure_project_exists(db: Session, project_code: str) -> None:
    normalized_project_code = _normalize_project_code(project_code)
    existing = db.execute(
        select(TestProject).where(TestProject.project_code == normalized_project_code)
    ).scalar_one_or_none()
    if existing:
        return
    db.add(
        TestProject(
            project_code=normalized_project_code,
            project_name=normalized_project_code.upper(),
            description="Auto-created from synchronized workbench generation",
            status="active",
            created_by="system",
        )
    )
    db.commit()


def _workbench_steps(case_yaml: dict[str, Any]) -> list[dict[str, Any]]:
    execution = case_yaml.get("execution") if isinstance(case_yaml, dict) else {}
    if not isinstance(execution, dict):
        return []
    return normalize_test_steps(execution.get("steps") if isinstance(execution.get("steps"), list) else [])


def _workbench_requirement(case_yaml: dict[str, Any]) -> list[str]:
    if not isinstance(case_yaml, dict):
        return []
    return normalize_text_list(case_yaml.get("requirement") if isinstance(case_yaml.get("requirement"), list) else [])


def _workbench_yaml_script(case_yaml: dict[str, Any]) -> str:
    if not isinstance(case_yaml, dict):
        return ""
    return yaml.safe_dump(case_yaml, allow_unicode=True, sort_keys=False).strip() + "\n"


def _existing_asset_case_ids() -> list[str]:
    if not ASSETS_CASES_ROOT.exists():
        return []
    return [path.stem for path in ASSETS_CASES_ROOT.rglob("*.yaml")]


def _delete_case_asset_files(case_ids: Sequence[str]) -> list[str]:
    if not ASSETS_CASES_ROOT.exists():
        return []
    target_case_ids = {
        _normalize_business_case_id(item)
        for item in case_ids
        if _normalize_business_case_id(item)
    }
    if not target_case_ids:
        return []
    removed_paths: list[str] = []
    for yaml_path in ASSETS_CASES_ROOT.rglob("*.yaml"):
        normalized_stem = _normalize_business_case_id(yaml_path.stem)
        if normalized_stem not in target_case_ids:
            continue
        yaml_path.unlink(missing_ok=True)
        removed_paths.append(str(yaml_path))
    return removed_paths


def _delete_execution_report_files(case_ids: Sequence[str]) -> list[str]:
    if not EXECUTION_REPORTS_ROOT.exists():
        return []
    target_case_ids = {
        _normalize_business_case_id(item)
        for item in case_ids
        if _normalize_business_case_id(item)
    }
    if not target_case_ids:
        return []
    removed_paths: list[str] = []
    for case_id in sorted(target_case_ids):
        report_json = EXECUTION_REPORTS_ROOT / f"{case_id}.report.json"
        report_md = EXECUTION_REPORTS_ROOT / f"{case_id}.report.md"
        for report_path in (report_json, report_md):
            if not report_path.exists():
                continue
            report_path.unlink(missing_ok=True)
            removed_paths.append(str(report_path))
    return removed_paths


def _is_ddt_case(case: TestCase) -> bool:
    case_id_value = str(case.case_id or "").strip().lower()
    name_value = str(case.name or "").strip().lower()
    if "ddt" in case_id_value or "ddt" in name_value:
        return True
    tags = [str(item or "").strip().lower() for item in (case.tags or [])]
    if any("ddt" in item for item in tags):
        return True
    markers = [str(item or "").strip().lower() for item in (case.markers or [])]
    if any("ddt" in item for item in markers):
        return True
    data_config = case.data_config if isinstance(case.data_config, dict) else {}
    if bool(data_config.get("ddt_enabled")):
        return True
    parameter_line = str(data_config.get("parameter_line", "")).strip().lower()
    if "ddt" in parameter_line:
        return True
    return False


def _dedupe_text_items(values: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    for raw in values:
        value = str(raw or "").strip()
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def _existing_case_ids(db: Session, *, exclude_case_id: int | None = None) -> list[str]:
    stmt = select(TestCase.case_id)
    if exclude_case_id:
        stmt = stmt.where(TestCase.id != exclude_case_id)
    database_case_ids = [
        _normalize_business_case_id(item)
        for item in db.execute(stmt).scalars().all()
    ]
    asset_case_ids = [_normalize_business_case_id(item) for item in _existing_asset_case_ids()]
    return _dedupe_text_items([*asset_case_ids, *database_case_ids])


def _source_code_for_mode(mode: str, source: str) -> str:
    requested = str(source or "").strip()
    if requested:
        return normalize_source_code(requested)
    if str(mode or "").strip().lower() == "ai":
        return "ai"
    return "mn"


def _created_source_from_code(source_code: str) -> str:
    normalized = str(source_code or "").strip().lower()
    if normalized == "ai":
        return "ai"
    if normalized == "fb":
        return "workbench"
    if normalized == "imp":
        return "import"
    return "manual"


def _resolve_case_identity(
    db: Session,
    *,
    requested_case_id: str,
    project_code: str,
    client: str,
    product_line: str,
    module: str,
    page_code: str,
    module_code: str,
    title: str,
    description: str,
    tags: list[str],
    case_type: str,
    source: str,
    test_type: str,
    pytest_path: str,
    exclude_case_id: int | None = None,
    allow_existing_requested_case_id: bool = False,
) -> dict[str, str]:
    normalized_project_code = _normalize_project_code(project_code)
    resolved_client = normalize_client_code(
        client or infer_client_code(test_type, runner=pytest_path)
    )
    metadata = build_case_metadata(
        page=page_code or module or product_line or "common",
        module=module_code or module or product_line or "core",
        title=title,
        description=description,
        tags=tags,
        project=normalized_project_code,
        client=resolved_client,
        source_hint=source,
        legacy=normalize_source_code(source or "mn") == "imp",
    )
    resolved_case_type = normalize_business_case_type(case_type or metadata["case_type"])
    resolved_source = normalize_source_code(source or metadata["source"])
    resolved_page_code = metadata["page_code"]
    resolved_module_code = metadata["module_code"]
    existing_case_ids = _existing_case_ids(db, exclude_case_id=exclude_case_id)

    requested = str(requested_case_id or "").strip()
    normalized_requested = _normalize_business_case_id(requested)
    if requested:
        if not normalized_requested:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="case_id must follow shared_backend naming rules",
            )
        if normalized_requested in existing_case_ids and not allow_existing_requested_case_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"case_id already exists: {normalized_requested}",
            )
        resolved_case_id = normalized_requested
    else:
        sequence = next_case_sequence(
            existing_case_ids=existing_case_ids,
            page=module or product_line or resolved_page_code,
            module=module or product_line or resolved_module_code,
            project=normalized_project_code,
            client=resolved_client,
            page_code=resolved_page_code,
            module_code=resolved_module_code,
            case_type=resolved_case_type,
            source=resolved_source,
        )
        resolved_case_id = build_case_id(
            page=module or product_line or resolved_page_code,
            module=module or product_line or resolved_module_code,
            sequence=sequence,
            project=normalized_project_code,
            client=resolved_client,
            page_code=resolved_page_code,
            module_code=resolved_module_code,
            case_type=resolved_case_type,
            source=resolved_source,
        )

    return {
        "case_id": resolved_case_id,
        "project_code": normalized_project_code,
        "client": resolved_client,
        "page_code": resolved_page_code,
        "page_name": metadata["page_name"],
        "module_code": resolved_module_code,
        "module_name": metadata["module_name"],
        "case_type": resolved_case_type,
        "source": resolved_source,
    }


def case_or_404(db: Session, case_id: int | str) -> TestCase:
    ensure_seed_data(db)
    raw_case_id = str(case_id or "").strip()
    case: TestCase | None
    if raw_case_id.isdigit():
        case = db.execute(select(TestCase).where(TestCase.id == int(raw_case_id))).scalar_one_or_none()
    else:
        normalized_case_id = _normalize_business_case_id(raw_case_id)
        if not normalized_case_id:
            case = None
        else:
            case = db.execute(
                select(TestCase).where(TestCase.case_id == normalized_case_id)
            ).scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="test case not found")
    return case


def resolve_target_case_ids(
    db: Session,
    *,
    ids: Sequence[object] | None = None,
    case_ids: Sequence[object] | None = None,
) -> list[int]:
    ensure_seed_data(db)
    target_ids = positive_ids(ids or [])
    normalized_case_ids: list[str] = []
    for raw in normalize_case_ids(case_ids or []):
        normalized = _normalize_business_case_id(raw)
        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"invalid case_id: {raw}",
            )
        if normalized not in normalized_case_ids:
            normalized_case_ids.append(normalized)

    if normalized_case_ids:
        rows = db.execute(
            select(TestCase.case_id, TestCase.id).where(TestCase.case_id.in_(normalized_case_ids))
        ).all()
        matched_map = {str(case_id): int(item_id) for case_id, item_id in rows}
        missing_case_ids = [item for item in normalized_case_ids if item not in matched_map]
        if missing_case_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"test case not found: {missing_case_ids[0]}",
            )
        for case_id_value in normalized_case_ids:
            item_id = matched_map[case_id_value]
            if item_id not in target_ids:
                target_ids.append(item_id)
    return target_ids


def list_test_cases(
    db: Session,
    *,
    q: str,
    project_code: str,
    source: str,
    tag: str,
    priority: str,
    status: str,
    creator: str,
    last_result: str,
    product_line: str,
    module: str,
    test_type: str,
    sort_field: str,
    sort_order: str,
    page: int,
    page_size: int,
) -> TestCaseListResult:
    ensure_seed_data(db)
    parsed_search = parse_test_case_search_query(q)
    keyword = parsed_search.keyword
    creator_filter = creator.strip()
    parsed_creator_filter = parsed_search.creator.strip()
    creator_context = creator_filter or parsed_creator_filter
    last_result_filter = last_result.strip() or parsed_search.last_result
    status_filter = status.strip() or parsed_search.status
    test_type_filter = test_type.strip() or parsed_search.test_type
    source_filter = source.strip().lower() or parsed_search.source
    stmt = select(TestCase)
    if project_code.strip():
        stmt = stmt.where(TestCase.project_code == _normalize_project_code(project_code))
    if keyword:
        raw_term = keyword
        term = f"%{raw_term}%"
        normalized_case_id = _normalize_business_case_id(raw_term)
        conditions: list[Any] = [
            TestCase.case_id.like(term),
            TestCase.name.like(term),
            TestCase.module.like(term),
            TestCase.product_line.like(term),
            TestCase.creator.like(term),
        ]
        if normalized_case_id:
            conditions.append(TestCase.case_id == normalized_case_id)
        if raw_term.isdigit():
            conditions.append(TestCase.id == int(raw_term))
        stmt = stmt.where(or_(*conditions))
    if priority.strip():
        priority_values = [item.strip().upper() for item in str(priority or "").split(",") if item.strip()]
        if priority_values:
            if len(priority_values) == 1:
                stmt = stmt.where(TestCase.priority == priority_values[0])
            else:
                stmt = stmt.where(TestCase.priority.in_(priority_values))
    if status_filter:
        stmt = stmt.where(TestCase.status == normalize_status(status_filter))
    if creator_filter:
        stmt = stmt.where(TestCase.creator == creator_filter)
    elif parsed_creator_filter:
        stmt = stmt.where(TestCase.creator.like(f"%{parsed_creator_filter}%"))
    if last_result_filter:
        stmt = stmt.where(TestCase.last_execution_result == last_result_filter)
    if product_line.strip():
        stmt = stmt.where(TestCase.product_line == product_line.strip())
    if module.strip():
        stmt = stmt.where(TestCase.module == module.strip())
    if test_type_filter:
        stmt = stmt.where(TestCase.test_type == normalize_test_case_type(test_type_filter))
    if source_filter in {"ai", "mn", "cv", "imp", "fb"}:
        stmt = stmt.where(TestCase.source == source_filter)

    cases = db.execute(stmt).scalars().all()
    tag_filter = tag.strip()
    if tag_filter:
        cases = [item for item in cases if tag_filter in (item.tags or [])]

    sort_field_value = str(sort_field or "").strip().lower() or "updated_at"
    sort_order_value = str(sort_order or "").strip().lower() or "desc"
    reverse = sort_order_value != "asc"

    def sort_key(item: TestCase) -> Any:
        if sort_field_value in {"id", "case_id"}:
            return str(item.case_id or "").strip() or f"{item.id:08d}"
        if sort_field_value == "name":
            return str(item.name or "").strip().lower()
        if sort_field_value == "module":
            return (
                str(item.product_line or "").strip().lower(),
                str(item.module or "").strip().lower(),
                str(item.case_id or "").strip().lower(),
            )
        if sort_field_value == "created_at":
            return item.created_at or datetime.min.replace(tzinfo=UTC)
        if sort_field_value == "priority":
            mapping = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
            return mapping.get(str(item.priority or "").strip().upper(), 99)
        if sort_field_value == "status":
            mapping = {"active": 0, "inactive": 1, "deprecated": 2}
            return mapping.get(str(item.status or "").strip().lower(), 99)
        if sort_field_value in {"last_result", "last_execution_result"}:
            mapping = {"failed": 0, "unknown": 1, "skipped": 2, "passed": 3}
            return mapping.get(str(item.last_execution_result or "").strip().lower(), 99)
        return item.updated_at or item.created_at or datetime.min.replace(tzinfo=UTC)

    cases = sorted(cases, key=sort_key, reverse=reverse)

    total_items = len(cases)
    passed_count = sum(1 for item in cases if str(item.last_execution_result or "").strip().lower() == "passed")
    failed_count = sum(1 for item in cases if str(item.last_execution_result or "").strip().lower() == "failed")
    skipped_count = sum(1 for item in cases if str(item.last_execution_result or "").strip().lower() == "skipped")
    automated_count = sum(1 for item in cases if str(item.automation_status or "").strip().lower() == "automated")
    pass_rate = round((passed_count / total_items) * 100, 1) if total_items else 0.0
    automation_rate = round((automated_count / total_items) * 100, 1) if total_items else 0.0
    total_pages = max(1, (total_items + page_size - 1) // page_size) if total_items else 1
    selected_page = max(1, min(page, total_pages))
    start = (selected_page - 1) * page_size
    page_cases = cases[start:start + page_size]
    latest_versions: dict[int, int] = {}
    if page_cases:
        version_rows = db.execute(
            select(TestCaseVersion.case_id, func.max(TestCaseVersion.version_no))
            .where(TestCaseVersion.case_id.in_([case.id for case in page_cases]))
            .group_by(TestCaseVersion.case_id)
        ).all()
        latest_versions = {int(case_id): int(version_no or 0) for case_id, version_no in version_rows}

    tags = sorted(
        {
            tag_item
            for case in db.execute(select(TestCase.tags)).all()
            for tag_item in (case[0] or [])
            if str(tag_item).strip()
        }
    )
    creators = sorted({item[0] for item in db.execute(select(TestCase.creator)).all() if item[0]})
    product_lines = sorted({item[0] for item in db.execute(select(TestCase.product_line)).all() if item[0]})
    modules = sorted({item[0] for item in db.execute(select(TestCase.module)).all() if item[0]})
    project_codes = sorted({item[0] for item in db.execute(select(TestCase.project_code)).all() if item[0]})
    priorities = sorted(
        {item[0] for item in db.execute(select(TestCase.priority)).all() if item[0]}
    )
    last_results = sorted(
        {
            item[0]
            for item in db.execute(select(TestCase.last_execution_result)).all()
            if item[0]
        }
    )
    sources = sorted({item[0] for item in db.execute(select(TestCase.source)).all() if item[0]})
    test_types = sorted({item[0] for item in db.execute(select(TestCase.test_type)).all() if item[0]})

    return TestCaseListResult(
        cases=page_cases,
        pagination={
            "page": selected_page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
            "has_prev": selected_page > 1,
            "has_next": selected_page < total_pages,
            "prev_page": selected_page - 1 if selected_page > 1 else None,
            "next_page": selected_page + 1 if selected_page < total_pages else None,
        },
        filters={
            "product_lines": product_lines,
            "modules": modules,
            "project_codes": project_codes,
            "test_types": test_types,
            "tags": tags,
            "priorities": priorities,
            "statuses": sorted({item[0] for item in db.execute(select(TestCase.status)).all() if item[0]}),
            "sources": sources,
            "creators": creators,
            "last_results": last_results,
        },
        latest_versions=latest_versions,
        search_context=build_test_case_search_context(
            keyword=keyword,
            project_code=project_code.strip(),
            product_line=product_line.strip(),
            module=module.strip(),
            priority=priority.strip(),
            test_type=test_type_filter,
            status=status_filter,
            creator=creator_context,
            last_result=last_result_filter,
            source=source_filter,
        ),
        stats={
            "total": total_items,
            "passed": passed_count,
            "failed": failed_count,
            "skipped": skipped_count,
            "automated": automated_count,
            "automation_rate": automation_rate,
            "pass_rate": pass_rate,
        },
    )


def create_test_case(db: Session, payload: TestCaseCreate) -> TestCase:
    ensure_seed_data(db)
    tags = normalize_tags(payload.tags)
    related_services = normalize_text_list(payload.related_services)
    scenario_types = normalize_text_list(payload.scenario_types)
    artifact_links = normalize_text_list(payload.artifact_links)
    test_steps = normalize_test_steps(payload.test_steps)
    data_config = normalize_data_config(payload.data_config)
    script_code = payload.script_code.strip()
    name = payload.name.strip()
    if payload.mode == "ai":
        script_code = generate_ai_script(payload.requirement, payload.module)
        if not name:
            short_req = (
                payload.requirement.strip()[:14]
                if payload.requirement.strip()
                else "AI生成用例"
            )
            name = f"{payload.module}-{short_req}"

    script_code = compose_data_driven_script(script_code, data_config)

    if not script_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="script_code must not be empty")
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name must not be empty")

    normalized_test_type = normalize_test_case_type(payload.test_type)
    resolved_identity = _resolve_case_identity(
        db,
        requested_case_id=payload.case_id,
        project_code=payload.project_code,
        client=payload.client,
        product_line=payload.product_line.strip(),
        module=payload.module.strip(),
        page_code=payload.page_code.strip(),
        module_code=payload.module_code.strip(),
        title=name,
        description=payload.expected_result or payload.notes or payload.requirement,
        tags=tags,
        case_type=payload.case_type,
        source=_source_code_for_mode(payload.mode, payload.source),
        test_type=normalized_test_type,
        pytest_path=payload.pytest_path,
    )
    created_source = _created_source_from_code(resolved_identity["source"])
    normalized_test_steps_text = payload.test_steps_text.strip() or render_test_steps_text(test_steps)
    normalized_trigger_entry = normalize_optional_text(payload.trigger_entry) or (
        "API" if normalized_test_type == "api" else "UI"
    )
    normalized_automation_status = normalize_optional_text(payload.automation_status) or (
        "automated" if (payload.pytest_path.strip() or script_code.strip()) else "manual"
    )

    case = TestCase(
        case_id=resolved_identity["case_id"],
        project_code=resolved_identity["project_code"],
        client=resolved_identity["client"],
        page_code=resolved_identity["page_code"],
        page_name=resolved_identity["page_name"],
        module_code=resolved_identity["module_code"],
        module_name=resolved_identity["module_name"],
        case_type=resolved_identity["case_type"],
        source=resolved_identity["source"],
        name=name,
        product_line=payload.product_line.strip(),
        module=payload.module.strip(),
        chain_stage=normalize_optional_text(payload.chain_stage),
        sut_service=normalize_optional_text(payload.sut_service),
        related_services=related_services,
        priority=payload.priority.strip() or "P2",
        test_type=normalized_test_type,
        scenario_types=scenario_types,
        trigger_entry=normalized_trigger_entry,
        fault_injection_type=normalize_optional_text(payload.fault_injection_type),
        fault_injection_target=normalize_optional_text(payload.fault_injection_target),
        fault_injection_params=normalize_optional_text(payload.fault_injection_params),
        setup_sql=normalize_optional_text(payload.setup_sql),
        precondition_state=normalize_optional_text(payload.precondition_state),
        test_steps=test_steps,
        test_steps_text=normalized_test_steps_text,
        concurrency_model=normalize_optional_text(payload.concurrency_model),
        retry_policy=normalize_optional_text(payload.retry_policy),
        expected_result=normalize_optional_text(payload.expected_result),
        assert_sql=normalize_optional_text(payload.assert_sql),
        event_assertion=normalize_optional_text(payload.event_assertion),
        metric_assertion=normalize_optional_text(payload.metric_assertion),
        cleanup_script=normalize_optional_text(payload.cleanup_script),
        artifact_links=artifact_links,
        notes=normalize_optional_text(payload.notes),
        tags=tags,
        markers=normalize_markers(payload.markers),
        creator=payload.creator.strip() or "admin",
        assignee=payload.assignee.strip(),
        pytest_path=payload.pytest_path.strip(),
        status=normalize_status(payload.status),
        automation_status=normalized_automation_status,
        created_source=created_source,
        source_ref=payload.source_ref.strip(),
        script_code=script_code,
        data_config=data_config,
        last_execution_result="unknown",
        last_report_url="",
        last_synced_at=datetime.now(UTC) if created_source in {"ai", "workbench"} else None,
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    db.add(
        TestCaseVersion(
            case_id=case.id,
            version_no=1,
            script_code=case.script_code,
            changed_by=case.creator,
            change_summary=f"case created by {payload.mode}",
        )
    )
    db.commit()
    return case


def upsert_test_case_from_workbench(
    db: Session,
    *,
    project_code: str,
    case_yaml: dict[str, Any],
    source_path: str,
    source_name: str = "ai-workbench",
) -> TestCase:
    ensure_seed_data(db)
    normalized_case_id = _normalize_business_case_id((case_yaml or {}).get("id"))
    if not normalized_case_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="generated case is missing a valid case_id",
        )

    normalized_project_code = _normalize_project_code(project_code)
    _ensure_project_exists(db, normalized_project_code)

    title = normalize_optional_text(case_yaml.get("title")) or normalized_case_id
    tags = normalize_tags(normalize_text_list(case_yaml.get("tags")))
    requirement_lines = _workbench_requirement(case_yaml)
    description = normalize_optional_text(case_yaml.get("description")) or "\n".join(requirement_lines)
    steps = _workbench_steps(case_yaml)
    execution = case_yaml.get("execution") if isinstance(case_yaml, dict) else {}
    execution = execution if isinstance(execution, dict) else {}
    page_slug = normalize_optional_text(execution.get("page") or case_yaml.get("module") or "common") or "common"
    module_slug = normalize_optional_text(case_yaml.get("module") or page_slug) or page_slug
    metadata = build_case_metadata(
        page=page_slug,
        module=module_slug,
        title=title,
        description=description,
        tags=tags,
        project=normalized_project_code,
        client="web",
        source_hint="ai",
    )
    existing = db.execute(
        select(TestCase).where(TestCase.case_id == normalized_case_id)
    ).scalar_one_or_none()
    resolved_identity = _resolve_case_identity(
        db,
        requested_case_id=normalized_case_id,
        project_code=normalized_project_code,
        client="web",
        product_line=page_slug,
        module=module_slug,
        page_code=metadata["page_code"],
        module_code=metadata["module_code"],
        title=title,
        description=description,
        tags=tags,
        case_type=metadata["case_type"],
        source="ai",
        test_type="ui",
        pytest_path="",
        exclude_case_id=existing.id if existing else None,
        allow_existing_requested_case_id=True,
    )
    script_code = _workbench_yaml_script(case_yaml)
    expected_result = (
        normalize_optional_text(case_yaml.get("expected_result"))
        or "\n".join(requirement_lines)
        or description
    )
    owner = normalize_optional_text(case_yaml.get("owner")) or source_name
    source_ref = normalize_optional_text(source_path)
    chain_stage = normalize_optional_text(case_yaml.get("chain_stage")) or metadata["page_name"]
    notes = normalize_optional_text(case_yaml.get("notes")) or "Synchronized from AI workbench generated asset."
    test_steps_text = render_test_steps_text(steps)

    if existing is None:
        case = TestCase(
            case_id=resolved_identity["case_id"],
            project_code=resolved_identity["project_code"],
            client=resolved_identity["client"],
            page_code=resolved_identity["page_code"],
            page_name=resolved_identity["page_name"],
            module_code=resolved_identity["module_code"],
            module_name=resolved_identity["module_name"],
            case_type=resolved_identity["case_type"],
            source=resolved_identity["source"],
            name=title,
            product_line=resolved_identity["page_name"],
            module=resolved_identity["module_name"],
            chain_stage=chain_stage,
            sut_service=normalize_optional_text(case_yaml.get("sut_service")),
            related_services=normalize_text_list(case_yaml.get("related_services")),
            priority=normalize_optional_text(case_yaml.get("priority")) or "P1",
            test_type="ui",
            scenario_types=normalize_text_list(case_yaml.get("scenario_types")),
            trigger_entry=normalize_optional_text(case_yaml.get("trigger_entry")) or "UI",
            fault_injection_type=normalize_optional_text(case_yaml.get("fault_injection_type")),
            fault_injection_target=normalize_optional_text(case_yaml.get("fault_injection_target")),
            fault_injection_params=normalize_optional_text(case_yaml.get("fault_injection_params")),
            setup_sql=normalize_optional_text(case_yaml.get("setup_sql")),
            precondition_state=normalize_optional_text(case_yaml.get("precondition_state")),
            test_steps=steps,
            test_steps_text=test_steps_text,
            concurrency_model=normalize_optional_text(case_yaml.get("concurrency_model")),
            retry_policy=normalize_optional_text(case_yaml.get("retry_policy")),
            expected_result=expected_result,
            assert_sql=normalize_optional_text(case_yaml.get("assert_sql")),
            event_assertion=normalize_optional_text(case_yaml.get("event_assertion")),
            metric_assertion=normalize_optional_text(case_yaml.get("metric_assertion")),
            cleanup_script=normalize_optional_text(case_yaml.get("cleanup_script")),
            artifact_links=normalize_text_list(case_yaml.get("artifact_links")),
            notes=notes,
            tags=tags,
            markers=normalize_markers([]),
            creator=owner,
            assignee=owner,
            pytest_path="",
            status="inactive",
            automation_status="automated" if steps else "manual",
            created_source="ai",
            source_ref=source_ref,
            script_code=script_code,
            data_config=normalize_data_config(TestCaseDataConfig()),
            last_execution_result="unknown",
            last_report_url="",
            last_synced_at=datetime.now(UTC),
        )
        db.add(case)
        db.commit()
        db.refresh(case)
        db.add(
            TestCaseVersion(
                case_id=case.id,
                version_no=1,
                script_code=case.script_code,
                changed_by=owner,
                change_summary="case synchronized from ai workbench",
            )
        )
        db.commit()
        db.refresh(case)
        return case

    existing.project_code = resolved_identity["project_code"]
    existing.client = resolved_identity["client"]
    existing.page_code = resolved_identity["page_code"]
    existing.page_name = resolved_identity["page_name"]
    existing.module_code = resolved_identity["module_code"]
    existing.module_name = resolved_identity["module_name"]
    existing.case_type = resolved_identity["case_type"]
    existing.source = resolved_identity["source"]
    existing.name = title
    existing.product_line = resolved_identity["page_name"]
    existing.module = resolved_identity["module_name"]
    existing.chain_stage = chain_stage
    existing.sut_service = normalize_optional_text(case_yaml.get("sut_service"))
    existing.related_services = normalize_text_list(case_yaml.get("related_services"))
    existing.priority = normalize_optional_text(case_yaml.get("priority")) or existing.priority or "P1"
    existing.test_type = "ui"
    existing.scenario_types = normalize_text_list(case_yaml.get("scenario_types"))
    existing.trigger_entry = normalize_optional_text(case_yaml.get("trigger_entry")) or "UI"
    existing.fault_injection_type = normalize_optional_text(case_yaml.get("fault_injection_type"))
    existing.fault_injection_target = normalize_optional_text(case_yaml.get("fault_injection_target"))
    existing.fault_injection_params = normalize_optional_text(case_yaml.get("fault_injection_params"))
    existing.setup_sql = normalize_optional_text(case_yaml.get("setup_sql"))
    existing.precondition_state = normalize_optional_text(case_yaml.get("precondition_state"))
    existing.test_steps = steps
    existing.test_steps_text = test_steps_text
    existing.concurrency_model = normalize_optional_text(case_yaml.get("concurrency_model"))
    existing.retry_policy = normalize_optional_text(case_yaml.get("retry_policy"))
    existing.expected_result = expected_result
    existing.assert_sql = normalize_optional_text(case_yaml.get("assert_sql"))
    existing.event_assertion = normalize_optional_text(case_yaml.get("event_assertion"))
    existing.metric_assertion = normalize_optional_text(case_yaml.get("metric_assertion"))
    existing.cleanup_script = normalize_optional_text(case_yaml.get("cleanup_script"))
    existing.artifact_links = normalize_text_list(case_yaml.get("artifact_links"))
    existing.notes = notes
    existing.tags = tags
    existing.creator = existing.creator or owner
    existing.assignee = owner
    existing.status = "inactive"
    existing.automation_status = "automated" if steps else "manual"
    existing.created_source = "ai"
    existing.source_ref = source_ref
    existing.script_code = script_code
    existing.last_synced_at = datetime.now(UTC)
    existing.updated_at = datetime.now(UTC)
    db.add(existing)
    db.commit()

    db.add(
        TestCaseVersion(
            case_id=existing.id,
            version_no=_next_version_no(db, existing.id),
            script_code=existing.script_code,
            changed_by=owner,
            change_summary="case re-synchronized from ai workbench",
        )
    )
    db.commit()
    db.refresh(existing)
    return existing


def get_test_case_detail(db: Session, case_id: int | str) -> TestCaseDetailResult:
    ensure_seed_data(db)
    case = case_or_404(db, case_id)
    defects = db.execute(
        select(TestCaseDefect)
        .where(TestCaseDefect.case_id == case.id)
        .order_by(TestCaseDefect.created_at.desc())
    ).scalars().all()
    executions = db.execute(
        select(TestCaseExecution)
        .where(TestCaseExecution.case_id == case.id)
        .order_by(TestCaseExecution.executed_at.desc(), TestCaseExecution.id.desc())
        .limit(10)
    ).scalars().all()
    versions = db.execute(
        select(TestCaseVersion)
        .where(TestCaseVersion.case_id == case.id)
        .order_by(TestCaseVersion.version_no.desc(), TestCaseVersion.id.desc())
    ).scalars().all()
    normalized_data_config = normalize_data_config(
        TestCaseDataConfig.model_validate(case.data_config or {})
    )
    return TestCaseDetailResult(
        case=case,
        defects=list(defects),
        executions=list(executions),
        versions=list(versions),
        data_config=normalized_data_config,
    )


def _next_version_no(db: Session, case_id: int) -> int:
    latest_version = db.execute(
        select(TestCaseVersion.version_no)
        .where(TestCaseVersion.case_id == case_id)
        .order_by(TestCaseVersion.version_no.desc())
        .limit(1)
    ).scalar_one_or_none()
    return int(latest_version or 0) + 1


def update_test_case(db: Session, case_id: int | str, payload: TestCaseUpdate) -> TestCaseMutationResult:
    case = case_or_404(db, case_id)
    changed = False
    latest_version_no: int | None = None

    if payload.project_code is not None:
        next_value = _normalize_project_code(payload.project_code)
        if case.project_code != next_value:
            case.project_code = next_value
            changed = True
    if payload.client is not None:
        next_value = normalize_client_code(
            payload.client or infer_client_code(case.test_type, runner=case.pytest_path)
        )
        if case.client != next_value:
            case.client = next_value
            changed = True
    if payload.page_code is not None:
        next_value = normalize_optional_text(payload.page_code)
        if next_value and case.page_code != next_value:
            case.page_code = next_value
            changed = True
    if payload.module_code is not None:
        next_value = normalize_optional_text(payload.module_code)
        if next_value and case.module_code != next_value:
            case.module_code = next_value
            changed = True
    if payload.case_type is not None:
        next_value = normalize_business_case_type(payload.case_type or case.case_type)
        if case.case_type != next_value:
            case.case_type = next_value
            changed = True
    if payload.source is not None:
        next_value = normalize_source_code(payload.source or case.source)
        if case.source != next_value:
            case.source = next_value
            changed = True
    if payload.name is not None:
        name = payload.name.strip()
        if name:
            case.name = name
            changed = True
    if payload.product_line is not None:
        case.product_line = payload.product_line.strip() or case.product_line
        changed = True
    if payload.module is not None:
        case.module = payload.module.strip() or case.module
        changed = True
    if payload.chain_stage is not None:
        case.chain_stage = normalize_optional_text(payload.chain_stage)
        changed = True
    if payload.sut_service is not None:
        case.sut_service = normalize_optional_text(payload.sut_service)
        changed = True
    if payload.related_services is not None:
        case.related_services = normalize_text_list(payload.related_services)
        changed = True
    if payload.priority is not None:
        case.priority = payload.priority.strip() or case.priority
        changed = True
    if payload.test_type is not None:
        case.test_type = normalize_test_case_type(payload.test_type)
        changed = True
    if payload.scenario_types is not None:
        case.scenario_types = normalize_text_list(payload.scenario_types)
        changed = True
    if payload.trigger_entry is not None:
        case.trigger_entry = normalize_optional_text(payload.trigger_entry)
        changed = True
    if payload.fault_injection_type is not None:
        case.fault_injection_type = normalize_optional_text(payload.fault_injection_type)
        changed = True
    if payload.fault_injection_target is not None:
        case.fault_injection_target = normalize_optional_text(payload.fault_injection_target)
        changed = True
    if payload.fault_injection_params is not None:
        case.fault_injection_params = normalize_optional_text(payload.fault_injection_params)
        changed = True
    if payload.setup_sql is not None:
        case.setup_sql = normalize_optional_text(payload.setup_sql)
        changed = True
    if payload.precondition_state is not None:
        case.precondition_state = normalize_optional_text(payload.precondition_state)
        changed = True
    if payload.test_steps is not None:
        case.test_steps = normalize_test_steps(payload.test_steps)
        changed = True
    if payload.test_steps_text is not None:
        case.test_steps_text = normalize_optional_text(payload.test_steps_text)
        changed = True
    if payload.concurrency_model is not None:
        case.concurrency_model = normalize_optional_text(payload.concurrency_model)
        changed = True
    if payload.retry_policy is not None:
        case.retry_policy = normalize_optional_text(payload.retry_policy)
        changed = True
    if payload.expected_result is not None:
        case.expected_result = normalize_optional_text(payload.expected_result)
        changed = True
    if payload.assert_sql is not None:
        case.assert_sql = normalize_optional_text(payload.assert_sql)
        changed = True
    if payload.event_assertion is not None:
        case.event_assertion = normalize_optional_text(payload.event_assertion)
        changed = True
    if payload.metric_assertion is not None:
        case.metric_assertion = normalize_optional_text(payload.metric_assertion)
        changed = True
    if payload.cleanup_script is not None:
        case.cleanup_script = normalize_optional_text(payload.cleanup_script)
        changed = True
    if payload.artifact_links is not None:
        case.artifact_links = normalize_text_list(payload.artifact_links)
        changed = True
    if payload.notes is not None:
        case.notes = normalize_optional_text(payload.notes)
        changed = True
    if payload.tags is not None:
        case.tags = normalize_tags(payload.tags)
        changed = True
    if payload.markers is not None:
        case.markers = normalize_markers(payload.markers)
        changed = True
    if payload.creator is not None:
        case.creator = payload.creator.strip() or case.creator
        changed = True
    if payload.assignee is not None:
        case.assignee = payload.assignee.strip()
        changed = True
    if payload.pytest_path is not None:
        case.pytest_path = payload.pytest_path.strip()
        changed = True
    if payload.status is not None:
        case.status = normalize_status(payload.status)
        changed = True
    if payload.automation_status is not None:
        case.automation_status = normalize_optional_text(payload.automation_status) or case.automation_status
        changed = True
    if payload.source_ref is not None:
        case.source_ref = normalize_optional_text(payload.source_ref)
        changed = True

    data_config_updated = False
    normalized_data_config = normalize_data_config(
        TestCaseDataConfig.model_validate(case.data_config or {})
    )
    if payload.data_config is not None:
        normalized_data_config = normalize_data_config(payload.data_config)
        case.data_config = normalized_data_config
        case.script_code = refresh_existing_data_driven_script(
            case.script_code or "",
            normalized_data_config,
        )
        data_config_updated = True
        changed = True

    if payload.script_code is not None:
        case.script_code = payload.script_code
        changed = True

    if payload.automation_status is None and (
        payload.pytest_path is not None or payload.script_code is not None
    ):
        case.automation_status = "automated" if (case.pytest_path or case.script_code) else "manual"

    if payload.test_steps_text is None and payload.test_steps is not None:
        case.test_steps_text = render_test_steps_text(case.test_steps if isinstance(case.test_steps, list) else [])

    if (payload.case_id is not None and str(payload.case_id).strip()) or not _normalize_business_case_id(case.case_id):
        resolved_identity = _resolve_case_identity(
            db,
            requested_case_id=payload.case_id or "",
            project_code=case.project_code,
            client=case.client,
            product_line=case.product_line,
            module=case.module,
            page_code=case.page_code,
            module_code=case.module_code,
            title=case.name,
            description=case.expected_result or case.notes,
            tags=normalize_tags(list(case.tags or [])),
            case_type=case.case_type,
            source=case.source,
            test_type=case.test_type,
            pytest_path=case.pytest_path,
            exclude_case_id=case.id,
        )
        if case.case_id != resolved_identity["case_id"]:
            case.case_id = resolved_identity["case_id"]
            changed = True
        case.project_code = resolved_identity["project_code"]
        case.client = resolved_identity["client"]
        case.page_code = resolved_identity["page_code"]
        case.page_name = resolved_identity["page_name"]
        case.module_code = resolved_identity["module_code"]
        case.module_name = resolved_identity["module_name"]
        case.case_type = resolved_identity["case_type"]
        case.source = resolved_identity["source"]
    else:
        refreshed_metadata = build_case_metadata(
            page=case.page_code or case.module or case.product_line or "common",
            module=case.module_code or case.module or case.product_line or "core",
            title=case.name,
            description=case.expected_result or case.notes,
            tags=list(case.tags or []),
            project=case.project_code,
            client=case.client,
            source_hint=case.source,
            legacy=case.source == "imp",
        )
        case.page_name = refreshed_metadata["page_name"]
        case.module_name = refreshed_metadata["module_name"]

    if changed:
        case.updated_at = datetime.now(UTC)
        db.add(case)
        if payload.script_code is not None:
            latest_version_no = _next_version_no(db, case.id)
            db.add(
                TestCaseVersion(
                    case_id=case.id,
                    version_no=latest_version_no,
                    script_code=case.script_code,
                    changed_by=(
                        payload.creator.strip()
                        if payload.creator and payload.creator.strip()
                        else case.creator
                    ),
                    change_summary="case updated",
                )
            )
        elif data_config_updated:
            latest_version_no = _next_version_no(db, case.id)
            db.add(
                TestCaseVersion(
                    case_id=case.id,
                    version_no=latest_version_no,
                    script_code=case.script_code,
                    changed_by=case.creator,
                    change_summary="data config updated",
                )
            )
        db.commit()

    return TestCaseMutationResult(
        case=case,
        data_config=normalized_data_config,
        script_code=case.script_code,
        latest_version_no=latest_version_no,
    )


def compare_case_versions(
    db: Session,
    case_id: int | str,
    from_version: int,
    to_version: int,
) -> TestCaseVersionComparison:
    ensure_seed_data(db)
    case = case_or_404(db, case_id)
    from_item = db.execute(
        select(TestCaseVersion).where(
            TestCaseVersion.case_id == case.id,
            TestCaseVersion.version_no == from_version,
        )
    ).scalar_one_or_none()
    to_item = db.execute(
        select(TestCaseVersion).where(
            TestCaseVersion.case_id == case.id,
            TestCaseVersion.version_no == to_version,
        )
    ).scalar_one_or_none()
    if not from_item or not to_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="version not found")

    diff_lines = list(
        difflib.unified_diff(
            (from_item.script_code or "").splitlines(),
            (to_item.script_code or "").splitlines(),
            fromfile=f"v{from_version}",
            tofile=f"v{to_version}",
            lineterm="",
        )
    )
    added_lines = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
    removed_lines = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))
    return TestCaseVersionComparison(
        from_version=from_version,
        to_version=to_version,
        added_lines=added_lines,
        removed_lines=removed_lines,
        diff_lines=diff_lines,
    )


def update_script(db: Session, case_id: int | str, payload: TestCaseScriptUpdate) -> int:
    case = case_or_404(db, case_id)
    old_lines = len((case.script_code or "").splitlines())
    new_lines = len(payload.script_code.splitlines())
    delta = new_lines - old_lines
    case.script_code = payload.script_code
    case.updated_at = datetime.now(UTC)
    db.add(case)
    next_version = _next_version_no(db, case.id)
    db.add(
        TestCaseVersion(
            case_id=case.id,
            version_no=next_version,
            script_code=payload.script_code,
            changed_by=payload.changed_by.strip() or "admin",
            change_summary=f"script updated, line delta {delta:+d}",
        )
    )
    db.commit()
    return next_version


def batch_delete_test_cases(
    db: Session,
    ids: Sequence[object] | None = None,
    case_ids: Sequence[object] | None = None,
) -> int:
    target_ids = resolve_target_case_ids(db, ids=ids, case_ids=case_ids)
    if not target_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ids or case_ids must not be empty")
    deleting_rows = db.execute(
        select(TestCase.id, TestCase.case_id).where(TestCase.id.in_(target_ids))
    ).all()
    deleting_case_ids = [
        _normalize_business_case_id(item_case_id)
        for _item_id, item_case_id in deleting_rows
        if _normalize_business_case_id(item_case_id)
    ]
    db.query(TestCaseDefect).filter(TestCaseDefect.case_id.in_(target_ids)).delete(
        synchronize_session=False
    )
    db.query(TestCaseExecution).filter(TestCaseExecution.case_id.in_(target_ids)).delete(
        synchronize_session=False
    )
    db.query(TestCaseVersion).filter(TestCaseVersion.case_id.in_(target_ids)).delete(
        synchronize_session=False
    )
    deleted_count = db.query(TestCase).filter(TestCase.id.in_(target_ids)).delete(
        synchronize_session=False
    )
    db.commit()
    _delete_case_asset_files(deleting_case_ids)
    _delete_execution_report_files(deleting_case_ids)
    return int(deleted_count)


def purge_ddt_test_cases(db: Session) -> dict[str, Any]:
    ensure_seed_data(db)
    cases = list(db.execute(select(TestCase).order_by(TestCase.id.asc())).scalars().all())
    target_cases = [item for item in cases if _is_ddt_case(item)]
    if not target_cases:
        return {
            "deleted_count": 0,
            "deleted_case_ids": [],
        }
    target_ids = [int(item.id) for item in target_cases]
    target_case_ids = [
        _normalize_business_case_id(item.case_id)
        for item in target_cases
        if _normalize_business_case_id(item.case_id)
    ]
    deleted_count = batch_delete_test_cases(db, ids=target_ids)
    return {
        "deleted_count": deleted_count,
        "deleted_case_ids": target_case_ids,
    }


def batch_update_test_case_tags(db: Session, payload: BatchTagsUpdatePayload) -> int:
    target_ids = resolve_target_case_ids(db, ids=payload.ids, case_ids=payload.case_ids)
    if not target_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ids or case_ids must not be empty")
    target_tags = normalize_tags(payload.tags)
    if not target_tags:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="tags must not be empty")

    updated = 0
    cases = db.execute(select(TestCase).where(TestCase.id.in_(target_ids))).scalars().all()
    for case in cases:
        if payload.mode == "append":
            case.tags = normalize_tags(list(case.tags or []) + target_tags)
        else:
            case.tags = target_tags
        case.updated_at = datetime.now(UTC)
        db.add(case)
        updated += 1
    db.commit()
    return updated


def batch_update_test_case_status(db: Session, payload: BatchStatusUpdatePayload) -> int:
    target_ids = resolve_target_case_ids(db, ids=payload.ids, case_ids=payload.case_ids)
    if not target_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ids or case_ids must not be empty")
    target_status = normalize_status(payload.status)

    updated = 0
    cases = db.execute(select(TestCase).where(TestCase.id.in_(target_ids))).scalars().all()
    for case in cases:
        if case.status == target_status:
            continue
        case.status = target_status
        case.updated_at = datetime.now(UTC)
        db.add(case)
        db.add(
            TestCaseVersion(
                case_id=case.id,
                version_no=_next_version_no(db, case.id),
                script_code=case.script_code,
                changed_by=case.creator,
                change_summary=f"status updated to {target_status}",
            )
        )
        updated += 1
    db.commit()
    return updated


def list_test_cases_for_export(
    db: Session,
    ids: Sequence[object] | None = None,
    case_ids: Sequence[object] | None = None,
) -> list[TestCase]:
    ensure_seed_data(db)
    target_ids = resolve_target_case_ids(db, ids=ids, case_ids=case_ids)
    if not target_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ids or case_ids must not be empty")
    return list(
        db.execute(
            select(TestCase).where(TestCase.id.in_(target_ids)).order_by(TestCase.id.asc())
        ).scalars().all()
    )


def add_test_case_defect(
    db: Session,
    case_id: int | str,
    defect_key: str,
    defect_url: str = "",
) -> TestCaseDefect:
    case = case_or_404(db, case_id)
    key = defect_key.strip()
    if not key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="defect_key must not be empty")
    defect = TestCaseDefect(case_id=case.id, defect_key=key, defect_url=defect_url.strip())
    db.add(defect)
    db.commit()
    db.refresh(defect)
    return defect


def create_module_tree_node(
    db: Session,
    *,
    project_code: str,
    product_line: str,
    module: str = "",
) -> dict[str, Any]:
    ensure_seed_data(db)
    normalized_project_code = _normalize_project_code(project_code)
    normalized_product_line = str(product_line or "").strip()
    normalized_module = str(module or "").strip()
    if not normalized_product_line:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="product_line must not be empty")
    exists = db.execute(
        select(TestCaseTreeNode).where(
            TestCaseTreeNode.project_code == normalized_project_code,
            TestCaseTreeNode.product_line == normalized_product_line,
            TestCaseTreeNode.module == normalized_module,
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="tree node already exists")
    node = TestCaseTreeNode(
        project_code=normalized_project_code,
        product_line=normalized_product_line,
        module=normalized_module,
    )
    db.add(node)
    db.commit()
    return {
        "project_code": normalized_project_code,
        "product_line": normalized_product_line,
        "module": normalized_module,
    }


def update_module_tree_node(
    db: Session,
    *,
    project_code: str,
    product_line: str,
    module: str,
    new_product_line: str,
    new_module: str = "",
) -> dict[str, Any]:
    ensure_seed_data(db)
    normalized_project_code = _normalize_project_code(project_code)
    old_product_line = str(product_line or "").strip()
    old_module = str(module or "").strip()
    target_product_line = str(new_product_line or "").strip()
    target_module = str(new_module or "").strip()
    if not old_product_line or not target_product_line:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="product_line must not be empty")

    case_stmt = select(TestCase).where(
        TestCase.project_code == normalized_project_code,
        TestCase.product_line == old_product_line,
    )
    if old_module:
        case_stmt = case_stmt.where(TestCase.module == old_module)
    matching_cases = list(db.execute(case_stmt).scalars().all())

    existing_node = db.execute(
        select(TestCaseTreeNode).where(
            TestCaseTreeNode.project_code == normalized_project_code,
            TestCaseTreeNode.product_line == old_product_line,
            TestCaseTreeNode.module == old_module,
        )
    ).scalar_one_or_none()
    if not matching_cases and existing_node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tree node not found")

    for case in matching_cases:
        case.product_line = target_product_line
        if old_module:
            case.module = target_module
        case.updated_at = datetime.now(UTC)
        db.add(case)

    duplicate = db.execute(
        select(TestCaseTreeNode).where(
            TestCaseTreeNode.project_code == normalized_project_code,
            TestCaseTreeNode.product_line == target_product_line,
            TestCaseTreeNode.module == target_module,
        )
    ).scalar_one_or_none()
    if duplicate is None:
        db.add(
            TestCaseTreeNode(
                project_code=normalized_project_code,
                product_line=target_product_line,
                module=target_module,
            )
        )
    if existing_node is not None:
        db.delete(existing_node)
    db.commit()
    return {
        "project_code": normalized_project_code,
        "product_line": target_product_line,
        "module": target_module,
        "updated_cases": len(matching_cases),
    }


def delete_module_tree_node(
    db: Session,
    *,
    project_code: str,
    product_line: str,
    module: str = "",
    cascade_cases: bool = False,
) -> dict[str, Any]:
    ensure_seed_data(db)
    normalized_project_code = _normalize_project_code(project_code)
    normalized_product_line = str(product_line or "").strip()
    normalized_module = str(module or "").strip()
    if not normalized_product_line:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="product_line must not be empty")

    case_stmt = select(TestCase.id, TestCase.case_id).where(
        TestCase.project_code == normalized_project_code,
        TestCase.product_line == normalized_product_line,
    )
    if normalized_module:
        case_stmt = case_stmt.where(TestCase.module == normalized_module)
    case_rows = list(db.execute(case_stmt).all())
    target_case_ids = [str(item_case_id or "").strip() for _item_id, item_case_id in case_rows if str(item_case_id or "").strip()]

    if case_rows and not cascade_cases:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"tree node still has {len(case_rows)} cases; set cascade_cases=true to delete them together",
        )

    deleted_cases = 0
    if case_rows and cascade_cases:
        deleted_cases = batch_delete_test_cases(db, case_ids=target_case_ids)

    node_stmt = select(TestCaseTreeNode).where(
        TestCaseTreeNode.project_code == normalized_project_code,
        TestCaseTreeNode.product_line == normalized_product_line,
    )
    if normalized_module:
        node_stmt = node_stmt.where(TestCaseTreeNode.module == normalized_module)
    else:
        node_stmt = node_stmt.where(TestCaseTreeNode.module == "")
    node = db.execute(node_stmt).scalar_one_or_none()
    if node is not None:
        db.delete(node)
        db.commit()
    return {
        "project_code": normalized_project_code,
        "product_line": normalized_product_line,
        "module": normalized_module,
        "deleted_cases": int(deleted_cases),
    }
