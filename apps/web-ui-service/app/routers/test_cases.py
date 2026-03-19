import csv
import difflib
import io
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.test_case import TestCase, TestCaseDefect, TestCaseExecution, TestCaseVersion
from app.schemas.test_case import (
    BatchExportPayload,
    BatchIdsPayload,
    BatchTagsUpdatePayload,
    TestCaseCreate,
    TestCaseScriptUpdate,
)

router = APIRouter(prefix="/api/test-cases", tags=["test-cases"])


def _normalize_tags(tags: list[str]) -> list[str]:
    normalized: list[str] = []
    for item in tags:
        value = str(item).strip()
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def _normalize_report_url(report_url: str, execution_id: int) -> str:
    value = str(report_url or "").strip()
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return f"/reports/{execution_id}"


def _positive_ids(values: list[Any]) -> list[int]:
    ids: list[int] = []
    for raw in values:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value > 0 and value not in ids:
            ids.append(value)
    return ids


def _ensure_seed_data(db: Session) -> None:
    existing_count = db.execute(select(func.count(TestCase.id))).scalar_one()
    if existing_count and existing_count > 0:
        return

    now = datetime.now(UTC)
    seed_cases = [
        TestCase(
            name="商品搜索结果展示",
            product_line="电商平台",
            module="商品中心",
            priority="P1",
            tags=["smoke", "search", "web"],
            creator="alice",
            script_code=(
                "def test_product_search(page):\n"
                "    page.goto('/products')\n"
                "    page.fill('#search', '耳机')\n"
                "    page.click('#search-btn')\n"
                "    assert page.locator('.result-item').count() > 0\n"
            ),
            last_execution_result="passed",
            created_at=now,
            updated_at=now,
        ),
        TestCase(
            name="订单创建基础流程",
            product_line="电商平台",
            module="订单中心",
            priority="P1",
            tags=["regression", "order"],
            creator="bob",
            script_code=(
                "def test_create_order(page):\n"
                "    page.goto('/cart')\n"
                "    page.click('#checkout')\n"
                "    page.fill('#address', '上海市浦东新区')\n"
                "    page.click('#submit-order')\n"
                "    assert page.locator('.order-success').is_visible()\n"
            ),
            last_execution_result="failed",
            created_at=now,
            updated_at=now,
        ),
        TestCase(
            name="登录态过期重定向",
            product_line="会员体系",
            module="认证服务",
            priority="P2",
            tags=["auth", "api", "security"],
            creator="carol",
            script_code=(
                "def test_auth_expired_redirect(page):\n"
                "    page.goto('/profile')\n"
                "    page.context.clear_cookies()\n"
                "    page.reload()\n"
                "    assert '/login' in page.url\n"
            ),
            last_execution_result="skipped",
            created_at=now,
            updated_at=now,
        ),
    ]
    db.add_all(seed_cases)
    db.commit()

    cases = db.execute(select(TestCase)).scalars().all()
    for case in cases:
        db.add(
            TestCaseVersion(
                case_id=case.id,
                version_no=1,
                script_code=case.script_code,
                changed_by=case.creator,
                change_summary="initial version",
                created_at=now,
            )
        )

    db.add_all(
        [
            TestCaseDefect(case_id=cases[1].id, defect_key="BUG-3421", defect_url="https://jira.local/BUG-3421"),
            TestCaseDefect(case_id=cases[1].id, defect_key="BUG-3510", defect_url="https://jira.local/BUG-3510"),
        ]
    )

    db.add_all(
        [
            TestCaseExecution(case_id=cases[0].id, status="passed", duration_ms=18240, report_url="/reports/101"),
            TestCaseExecution(case_id=cases[0].id, status="passed", duration_ms=16900, report_url="/reports/102"),
            TestCaseExecution(case_id=cases[1].id, status="failed", duration_ms=23100, report_url="/reports/201"),
            TestCaseExecution(case_id=cases[1].id, status="passed", duration_ms=21090, report_url="/reports/202"),
            TestCaseExecution(case_id=cases[2].id, status="skipped", duration_ms=0, report_url="/reports/301"),
        ]
    )
    db.commit()


def _case_or_404(db: Session, case_id: int) -> TestCase:
    case = db.execute(select(TestCase).where(TestCase.id == case_id)).scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="test case not found")
    return case


def _ai_generate_script(requirement: str, module: str) -> str:
    normalized_requirement = requirement.strip() or "请补充需求"
    return (
        f"def test_ai_generated_{module.lower().replace(' ', '_')}(page):\n"
        f"    # AI根据需求生成：{normalized_requirement}\n"
        "    page.goto('/')\n"
        "    # TODO: 补充关键操作步骤\n"
        "    assert page.title() is not None\n"
    )


def _to_list_item(case: TestCase) -> dict[str, Any]:
    return {
        "id": case.id,
        "name": case.name,
        "product_line": case.product_line,
        "module": case.module,
        "priority": case.priority,
        "tags": list(case.tags or []),
        "creator": case.creator,
        "last_execution_result": case.last_execution_result,
        "updated_at": case.updated_at,
    }


@router.get("/tree")
def get_module_tree(db: Session = Depends(get_db)) -> dict[str, Any]:
    _ensure_seed_data(db)
    cases = db.execute(select(TestCase.product_line, TestCase.module).order_by(TestCase.product_line, TestCase.module)).all()
    grouped: dict[str, set[str]] = {}
    for product_line, module in cases:
        grouped.setdefault(product_line, set()).add(module)
    return {
        "items": [
            {"product_line": product_line, "modules": sorted(list(modules))}
            for product_line, modules in sorted(grouped.items(), key=lambda item: item[0])
        ]
    }


@router.get("")
def list_test_cases(
    q: str = Query(default=""),
    tag: str = Query(default=""),
    priority: str = Query(default=""),
    creator: str = Query(default=""),
    last_result: str = Query(default=""),
    product_line: str = Query(default=""),
    module: str = Query(default=""),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ensure_seed_data(db)
    stmt = select(TestCase).order_by(TestCase.updated_at.desc(), TestCase.id.desc())
    if q.strip():
        term = f"%{q.strip()}%"
        stmt = stmt.where((TestCase.name.like(term)) | (TestCase.module.like(term)))
    if priority.strip():
        stmt = stmt.where(TestCase.priority == priority.strip())
    if creator.strip():
        stmt = stmt.where(TestCase.creator == creator.strip())
    if last_result.strip():
        stmt = stmt.where(TestCase.last_execution_result == last_result.strip())
    if product_line.strip():
        stmt = stmt.where(TestCase.product_line == product_line.strip())
    if module.strip():
        stmt = stmt.where(TestCase.module == module.strip())

    cases = db.execute(stmt).scalars().all()
    tag_filter = tag.strip()
    if tag_filter:
        cases = [item for item in cases if tag_filter in (item.tags or [])]

    tags = sorted(
        {
            tag_item
            for case in db.execute(select(TestCase.tags)).all()
            for tag_item in (case[0] or [])
            if str(tag_item).strip()
        }
    )
    creators = sorted({item[0] for item in db.execute(select(TestCase.creator)).all() if item[0]})
    priorities = sorted({item[0] for item in db.execute(select(TestCase.priority)).all() if item[0]})
    last_results = sorted({item[0] for item in db.execute(select(TestCase.last_execution_result)).all() if item[0]})

    return {
        "items": [_to_list_item(case) for case in cases],
        "filters": {
            "tags": tags,
            "priorities": priorities,
            "creators": creators,
            "last_results": last_results,
        },
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_test_case(payload: TestCaseCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    _ensure_seed_data(db)
    tags = _normalize_tags(payload.tags)
    script_code = payload.script_code.strip()
    name = payload.name.strip()
    if payload.mode == "ai":
        script_code = _ai_generate_script(payload.requirement, payload.module)
        if not name:
            short_req = payload.requirement.strip()[:14] if payload.requirement.strip() else "AI生成用例"
            name = f"{payload.module}-{short_req}"

    if not script_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="script_code must not be empty")
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name must not be empty")

    case = TestCase(
        name=name,
        product_line=payload.product_line.strip(),
        module=payload.module.strip(),
        priority=payload.priority.strip() or "P2",
        tags=tags,
        creator=payload.creator.strip() or "admin",
        script_code=script_code,
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
    return {"item": _to_list_item(case)}


@router.get("/{case_id}")
def get_test_case(case_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    _ensure_seed_data(db)
    case = _case_or_404(db, case_id)
    defects = db.execute(
        select(TestCaseDefect).where(TestCaseDefect.case_id == case_id).order_by(TestCaseDefect.created_at.desc())
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
    return {
        "basic": {
            **_to_list_item(case),
            "created_at": case.created_at,
        },
        "script_code": case.script_code,
        "defects": [
            {
                "id": item.id,
                "defect_key": item.defect_key,
                "defect_url": item.defect_url,
                "created_at": item.created_at,
            }
            for item in defects
        ],
        "executions": [
            {
                "id": item.id,
                "status": item.status,
                "duration_ms": item.duration_ms,
                "report_url": _normalize_report_url(item.report_url, item.id),
                "executed_at": item.executed_at,
            }
            for item in executions
        ],
        "versions": [
            {
                "id": item.id,
                "version_no": item.version_no,
                "changed_by": item.changed_by,
                "change_summary": item.change_summary,
                "created_at": item.created_at,
            }
            for item in versions
        ],
    }


@router.get("/{case_id}/versions/compare")
def compare_case_versions(
    case_id: int,
    from_version: int = Query(..., gt=0),
    to_version: int = Query(..., gt=0),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ensure_seed_data(db)
    _case_or_404(db, case_id)
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
    return {
        "from_version": from_version,
        "to_version": to_version,
        "added_lines": added_lines,
        "removed_lines": removed_lines,
        "diff_lines": diff_lines,
    }


@router.put("/{case_id}/script")
def update_script(case_id: int, payload: TestCaseScriptUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    case = _case_or_404(db, case_id)
    old_lines = len((case.script_code or "").splitlines())
    new_lines = len(payload.script_code.splitlines())
    delta = new_lines - old_lines
    case.script_code = payload.script_code
    case.updated_at = datetime.now(UTC)
    db.add(case)
    latest_version = db.execute(
        select(TestCaseVersion.version_no)
        .where(TestCaseVersion.case_id == case_id)
        .order_by(TestCaseVersion.version_no.desc())
        .limit(1)
    ).scalar_one_or_none()
    next_version = int(latest_version or 0) + 1
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
    return {"message": "script updated", "version_no": next_version}


@router.post("/batch/delete")
def batch_delete(payload: BatchIdsPayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    ids = _positive_ids(payload.ids)
    if not ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ids must not be empty")
    deleted_count = db.query(TestCase).filter(TestCase.id.in_(ids)).delete(synchronize_session=False)
    db.query(TestCaseDefect).filter(TestCaseDefect.case_id.in_(ids)).delete(synchronize_session=False)
    db.query(TestCaseExecution).filter(TestCaseExecution.case_id.in_(ids)).delete(synchronize_session=False)
    db.query(TestCaseVersion).filter(TestCaseVersion.case_id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    return {"deleted_count": deleted_count}


@router.post("/batch/tags")
def batch_update_tags(payload: BatchTagsUpdatePayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    ids = _positive_ids(payload.ids)
    if not ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ids must not be empty")
    target_tags = _normalize_tags(payload.tags)
    if not target_tags:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="tags must not be empty")

    updated = 0
    cases = db.execute(select(TestCase).where(TestCase.id.in_(ids))).scalars().all()
    for case in cases:
        if payload.mode == "append":
            case.tags = _normalize_tags(list(case.tags or []) + target_tags)
        else:
            case.tags = target_tags
        case.updated_at = datetime.now(UTC)
        db.add(case)
        updated += 1
    db.commit()
    return {"updated_count": updated}


@router.post("/batch/export")
def batch_export(payload: BatchExportPayload, db: Session = Depends(get_db)) -> Response:
    ids = _positive_ids(payload.ids)
    if not ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ids must not be empty")
    cases = db.execute(select(TestCase).where(TestCase.id.in_(ids)).order_by(TestCase.id.asc())).scalars().all()
    if payload.format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "name", "product_line", "module", "priority", "tags", "creator", "last_execution_result"])
        for case in cases:
            writer.writerow(
                [
                    case.id,
                    case.name,
                    case.product_line,
                    case.module,
                    case.priority,
                    ",".join(case.tags or []),
                    case.creator,
                    case.last_execution_result,
                ]
            )
        body = output.getvalue()
        return Response(
            content=body,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=test-cases.csv"},
        )

    body_items = [_to_list_item(case) for case in cases]
    import json

    return Response(
        content=json.dumps(body_items, ensure_ascii=False, default=str, indent=2),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=test-cases.json"},
    )


@router.post("/{case_id}/defects", status_code=status.HTTP_201_CREATED)
def add_defect(case_id: int, defect_key: str, defect_url: str = "", db: Session = Depends(get_db)) -> dict[str, Any]:
    _case_or_404(db, case_id)
    key = defect_key.strip()
    if not key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="defect_key must not be empty")
    defect = TestCaseDefect(case_id=case_id, defect_key=key, defect_url=defect_url.strip())
    db.add(defect)
    db.commit()
    db.refresh(defect)
    return {
        "item": {
            "id": defect.id,
            "defect_key": defect.defect_key,
            "defect_url": defect.defect_url,
            "created_at": defect.created_at,
        }
    }
