from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.test_case import (
    BatchExportPayload,
    BatchIdsPayload,
    BatchStatusUpdatePayload,
    BatchTagsUpdatePayload,
    TestCaseCreate,
    TestCaseScriptUpdate,
    TestCaseUpdate,
    TreeNodeCreatePayload,
    TreeNodeDeletePayload,
    TreeNodeUpdatePayload,
)
from app.services import test_case_export_service, test_case_mapper, test_case_service

router = APIRouter(prefix="/api/test-cases", tags=["test-cases"])


@router.get("/tree")
def get_module_tree(
    q: str = Query(default=""),
    project_code: str = Query(default=""),
    source: str = Query(default=""),
    tag: str = Query(default=""),
    priority: str = Query(default=""),
    status: str = Query(default=""),
    creator: str = Query(default=""),
    last_result: str = Query(default=""),
    product_line: str = Query(default=""),
    module: str = Query(default=""),
    test_type: str = Query(default=""),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return {
        "items": test_case_service.get_module_tree_items(
            db,
            q=q,
            project_code=project_code,
            source=source,
            tag=tag,
            priority=priority,
            status=status,
            creator=creator,
            last_result=last_result,
            product_line=product_line,
            module=module,
            test_type=test_type,
        )
    }


@router.post("/tree/nodes", status_code=status.HTTP_201_CREATED)
def create_tree_node(payload: TreeNodeCreatePayload, db: Session = Depends(get_db)) -> dict[str, object]:
    node = test_case_service.create_module_tree_node(
        db,
        project_code=payload.project_code,
        product_line=payload.product_line,
        module=payload.module,
    )
    return {"item": node}


@router.put("/tree/nodes")
def update_tree_node(payload: TreeNodeUpdatePayload, db: Session = Depends(get_db)) -> dict[str, object]:
    node = test_case_service.update_module_tree_node(
        db,
        project_code=payload.project_code,
        product_line=payload.product_line,
        module=payload.module,
        new_product_line=payload.new_product_line,
        new_module=payload.new_module,
    )
    return {"item": node}


@router.delete("/tree/nodes")
def delete_tree_node(payload: TreeNodeDeletePayload, db: Session = Depends(get_db)) -> dict[str, object]:
    result = test_case_service.delete_module_tree_node(
        db,
        project_code=payload.project_code,
        product_line=payload.product_line,
        module=payload.module,
        cascade_cases=payload.cascade_cases,
    )
    return {"item": result}


@router.get("")
def list_test_cases(
    q: str = Query(default=""),
    project_code: str = Query(default=""),
    source: str = Query(default=""),
    tag: str = Query(default=""),
    priority: str = Query(default=""),
    status: str = Query(default=""),
    creator: str = Query(default=""),
    last_result: str = Query(default=""),
    product_line: str = Query(default=""),
    module: str = Query(default=""),
    test_type: str = Query(default=""),
    sort_field: str = Query(default="updated_at"),
    sort_order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    result = test_case_service.list_test_cases(
        db,
        q=q,
        project_code=project_code,
        source=source,
        tag=tag,
        priority=priority,
        status=status,
        creator=creator,
        last_result=last_result,
        product_line=product_line,
        module=module,
        test_type=test_type,
        sort_field=sort_field,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    return test_case_mapper.build_list_payload(
        result.cases,
        result.pagination,
        result.filters,
        result.stats,
        result.latest_versions,
        result.search_context,
        result.project_statuses,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_test_case(payload: TestCaseCreate, db: Session = Depends(get_db)) -> dict[str, object]:
    case = test_case_service.create_test_case(db, payload)
    return {"item": test_case_mapper.to_list_item(case, latest_version_no=1)}


@router.get("/{case_id}")
def get_test_case(case_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    detail = test_case_service.get_test_case_detail(db, case_id)
    return test_case_mapper.build_case_detail_payload(
        detail.case,
        detail.defects,
        detail.executions,
        detail.versions,
        detail.data_config,
        project_status=detail.project_status,
        normalize_report_url=test_case_service.normalize_report_url,
    )


@router.put("/{case_id}")
def update_test_case(case_id: str, payload: TestCaseUpdate, db: Session = Depends(get_db)) -> dict[str, object]:
    result = test_case_service.update_test_case(db, case_id, payload)
    return {
        "item": test_case_mapper.to_list_item(result.case, latest_version_no=result.latest_version_no),
        "data_config": result.data_config,
        "script_code": result.script_code,
    }


@router.get("/{case_id}/versions/compare")
def compare_case_versions(
    case_id: str,
    from_version: int = Query(..., gt=0),
    to_version: int = Query(..., gt=0),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    result = test_case_service.compare_case_versions(db, case_id, from_version, to_version)
    return test_case_mapper.build_version_compare_payload(
        from_version=result.from_version,
        to_version=result.to_version,
        added_lines=result.added_lines,
        removed_lines=result.removed_lines,
        diff_lines=result.diff_lines,
    )


@router.put("/{case_id}/script")
def update_script(case_id: str, payload: TestCaseScriptUpdate, db: Session = Depends(get_db)) -> dict[str, object]:
    version_no = test_case_service.update_script(db, case_id, payload)
    return {"message": "script updated", "version_no": version_no}


@router.post("/batch/delete")
def batch_delete(payload: BatchIdsPayload, db: Session = Depends(get_db)) -> dict[str, int]:
    deleted_count = test_case_service.batch_delete_test_cases(
        db,
        ids=payload.ids,
        case_ids=payload.case_ids,
    )
    return {"deleted_count": deleted_count}


@router.post("/batch/purge-ddt")
def batch_purge_ddt_cases(db: Session = Depends(get_db)) -> dict[str, object]:
    purge_result = test_case_service.purge_ddt_test_cases(db)
    from app.routers.workbench_reporting import cleanup_case_consistency

    cleanup_result = cleanup_case_consistency(purge_all=False, db=db)
    return {
        "deleted_count": int(purge_result.get("deleted_count", 0)),
        "deleted_case_ids": list(purge_result.get("deleted_case_ids", [])),
        "consistency_cleanup": cleanup_result,
    }


@router.post("/batch/tags")
def batch_update_tags(payload: BatchTagsUpdatePayload, db: Session = Depends(get_db)) -> dict[str, int]:
    updated_count = test_case_service.batch_update_test_case_tags(db, payload)
    return {"updated_count": updated_count}


@router.post("/batch/status")
def batch_update_status(payload: BatchStatusUpdatePayload, db: Session = Depends(get_db)) -> dict[str, object]:
    updated_count = test_case_service.batch_update_test_case_status(db, payload)
    return {"updated_count": updated_count, "status": payload.status}


@router.post("/batch/export")
def batch_export(payload: BatchExportPayload, db: Session = Depends(get_db)) -> Response:
    cases = test_case_service.list_test_cases_for_export(
        db,
        ids=payload.ids,
        case_ids=payload.case_ids,
    )
    if payload.format == "xlsx":
        return Response(
            content=test_case_export_service.build_export_xlsx(cases),
            media_type=test_case_export_service.EXPORT_MEDIA_TYPE,
            headers={
                "Content-Disposition": f"attachment; filename={test_case_export_service.EXPORT_FILENAME}",
            },
        )
    if payload.format == "csv":
        return Response(
            content=test_case_mapper.build_export_csv(cases),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=test-cases.csv"},
        )

    return Response(
        content=test_case_mapper.build_export_json(
            cases,
            normalize_data_config=test_case_service.normalize_data_config,
        ),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=test-cases.json"},
    )


@router.post("/{case_id}/defects", status_code=status.HTTP_201_CREATED)
def add_defect(case_id: str, defect_key: str, defect_url: str = "", db: Session = Depends(get_db)) -> dict[str, object]:
    defect = test_case_service.add_test_case_defect(db, case_id, defect_key, defect_url)
    return {"item": test_case_mapper.build_defect_item(defect)}
