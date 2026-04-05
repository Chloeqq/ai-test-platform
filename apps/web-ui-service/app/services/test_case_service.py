from __future__ import annotations

import difflib
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Sequence, TypeAlias

from datetime_compat import UTC
from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.test_case import (
    TestCase,
    TestCaseDefect,
    TestCaseExecution,
    TestCaseVersion,
)
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
    normalize_data_config,
    normalize_markers,
    normalize_report_url as normalize_report_url,
    normalize_status,
    normalize_tags,
    normalize_test_case_type,
    positive_ids,
    refresh_existing_data_driven_script,
)
from app.services.test_case_search_service import (
    build_test_case_search_context,
    parse_test_case_search_query,
)

PaginationPayload: TypeAlias = dict[str, int | bool | None]
FilterOptionsPayload: TypeAlias = dict[str, list[str]]


@dataclass(frozen=True)
class TestCaseListResult:
    cases: list[TestCase]
    pagination: PaginationPayload
    filters: FilterOptionsPayload
    latest_versions: dict[int, int]
    search_context: dict[str, str]


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


def case_or_404(db: Session, case_id: int) -> TestCase:
    case = db.execute(select(TestCase).where(TestCase.id == case_id)).scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="test case not found")
    return case


def list_test_cases(
    db: Session,
    *,
    q: str,
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
    stmt = select(TestCase)
    if keyword:
        raw_term = keyword
        term = f"%{raw_term}%"
        conditions: list[Any] = [
            TestCase.name.like(term),
            TestCase.module.like(term),
            TestCase.product_line.like(term),
            TestCase.creator.like(term),
        ]
        if raw_term.isdigit():
            conditions.append(TestCase.id == int(raw_term))
        stmt = stmt.where(or_(*conditions))
    if priority.strip():
        stmt = stmt.where(TestCase.priority == priority.strip())
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

    cases = db.execute(stmt).scalars().all()
    tag_filter = tag.strip()
    if tag_filter:
        cases = [item for item in cases if tag_filter in (item.tags or [])]

    sort_field_value = str(sort_field or "").strip().lower() or "updated_at"
    sort_order_value = str(sort_order or "").strip().lower() or "desc"
    reverse = sort_order_value != "asc"

    def sort_key(item: TestCase) -> Any:
        if sort_field_value == "created_at":
            return item.created_at or datetime.min.replace(tzinfo=UTC)
        if sort_field_value == "priority":
            mapping = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
            return mapping.get(str(item.priority or "").strip().upper(), 99)
        if sort_field_value == "status":
            mapping = {"active": 0, "inactive": 1, "deprecated": 2}
            return mapping.get(str(item.status or "").strip().lower(), 99)
        return item.updated_at or item.created_at or datetime.min.replace(tzinfo=UTC)

    cases = sorted(cases, key=sort_key, reverse=reverse)

    total_items = len(cases)
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
            "test_types": test_types,
            "tags": tags,
            "priorities": priorities,
            "statuses": sorted({item[0] for item in db.execute(select(TestCase.status)).all() if item[0]}),
            "creators": creators,
            "last_results": last_results,
        },
        latest_versions=latest_versions,
        search_context=build_test_case_search_context(
            keyword=keyword,
            product_line=product_line.strip(),
            module=module.strip(),
            test_type=test_type_filter,
            status=status_filter,
            creator=creator_context,
            last_result=last_result_filter,
        ),
    )


def create_test_case(db: Session, payload: TestCaseCreate) -> TestCase:
    ensure_seed_data(db)
    tags = normalize_tags(payload.tags)
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

    case = TestCase(
        name=name,
        product_line=payload.product_line.strip(),
        module=payload.module.strip(),
        priority=payload.priority.strip() or "P2",
        test_type=normalize_test_case_type(payload.test_type),
        tags=tags,
        markers=normalize_markers(payload.markers),
        creator=payload.creator.strip() or "admin",
        pytest_path=payload.pytest_path.strip(),
        status=normalize_status(payload.status),
        script_code=script_code,
        data_config=data_config,
        last_execution_result="unknown",
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


def get_test_case_detail(db: Session, case_id: int) -> TestCaseDetailResult:
    ensure_seed_data(db)
    case = case_or_404(db, case_id)
    defects = db.execute(
        select(TestCaseDefect)
        .where(TestCaseDefect.case_id == case_id)
        .order_by(TestCaseDefect.created_at.desc())
    ).scalars().all()
    executions = db.execute(
        select(TestCaseExecution)
        .where(TestCaseExecution.case_id == case_id)
        .order_by(TestCaseExecution.executed_at.desc(), TestCaseExecution.id.desc())
        .limit(10)
    ).scalars().all()
    versions = db.execute(
        select(TestCaseVersion)
        .where(TestCaseVersion.case_id == case_id)
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


def update_test_case(db: Session, case_id: int, payload: TestCaseUpdate) -> TestCaseMutationResult:
    case = case_or_404(db, case_id)
    changed = False
    latest_version_no: int | None = None

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
    if payload.priority is not None:
        case.priority = payload.priority.strip() or case.priority
        changed = True
    if payload.test_type is not None:
        case.test_type = normalize_test_case_type(payload.test_type)
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
    if payload.pytest_path is not None:
        case.pytest_path = payload.pytest_path.strip()
        changed = True
    if payload.status is not None:
        case.status = normalize_status(payload.status)
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

    if changed:
        case.updated_at = datetime.now(UTC)
        db.add(case)
        if payload.script_code is not None:
            latest_version_no = _next_version_no(db, case_id)
            db.add(
                TestCaseVersion(
                    case_id=case_id,
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
            latest_version_no = _next_version_no(db, case_id)
            db.add(
                TestCaseVersion(
                    case_id=case_id,
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
    case_id: int,
    from_version: int,
    to_version: int,
) -> TestCaseVersionComparison:
    ensure_seed_data(db)
    case_or_404(db, case_id)
    from_item = db.execute(
        select(TestCaseVersion).where(
            TestCaseVersion.case_id == case_id,
            TestCaseVersion.version_no == from_version,
        )
    ).scalar_one_or_none()
    to_item = db.execute(
        select(TestCaseVersion).where(
            TestCaseVersion.case_id == case_id,
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


def update_script(db: Session, case_id: int, payload: TestCaseScriptUpdate) -> int:
    case = case_or_404(db, case_id)
    old_lines = len((case.script_code or "").splitlines())
    new_lines = len(payload.script_code.splitlines())
    delta = new_lines - old_lines
    case.script_code = payload.script_code
    case.updated_at = datetime.now(UTC)
    db.add(case)
    next_version = _next_version_no(db, case_id)
    db.add(
        TestCaseVersion(
            case_id=case_id,
            version_no=next_version,
            script_code=payload.script_code,
            changed_by=payload.changed_by.strip() or "admin",
            change_summary=f"script updated, line delta {delta:+d}",
        )
    )
    db.commit()
    return next_version


def batch_delete_test_cases(db: Session, ids: Sequence[object]) -> int:
    target_ids = positive_ids(ids)
    if not target_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ids must not be empty")
    deleted_count = db.query(TestCase).filter(TestCase.id.in_(target_ids)).delete(
        synchronize_session=False
    )
    db.query(TestCaseDefect).filter(TestCaseDefect.case_id.in_(target_ids)).delete(
        synchronize_session=False
    )
    db.query(TestCaseExecution).filter(TestCaseExecution.case_id.in_(target_ids)).delete(
        synchronize_session=False
    )
    db.query(TestCaseVersion).filter(TestCaseVersion.case_id.in_(target_ids)).delete(
        synchronize_session=False
    )
    db.commit()
    return int(deleted_count)


def batch_update_test_case_tags(db: Session, payload: BatchTagsUpdatePayload) -> int:
    target_ids = positive_ids(payload.ids)
    if not target_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ids must not be empty")
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
    target_ids = positive_ids(payload.ids)
    if not target_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ids must not be empty")
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


def list_test_cases_for_export(db: Session, ids: Sequence[object]) -> list[TestCase]:
    target_ids = positive_ids(ids)
    if not target_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ids must not be empty")
    return list(
        db.execute(
            select(TestCase).where(TestCase.id.in_(target_ids)).order_by(TestCase.id.asc())
        ).scalars().all()
    )


def add_test_case_defect(
    db: Session,
    case_id: int,
    defect_key: str,
    defect_url: str = "",
) -> TestCaseDefect:
    case_or_404(db, case_id)
    key = defect_key.strip()
    if not key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="defect_key must not be empty")
    defect = TestCaseDefect(case_id=case_id, defect_key=key, defect_url=defect_url.strip())
    db.add(defect)
    db.commit()
    db.refresh(defect)
    return defect
