"""AI 测试质量评估中心 — API 路由。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.id_gen import generate_dataset_id, generate_item_id, generate_run_id
from app.models.quality_eval import QualityEvalDataset, QualityEvalItem, QualityEvalRun
from app.repositories.quality_eval_repository import QualityEvalRepository
from app.schemas.quality_eval import (
    CreateDatasetRequest,
    CreateRunRequest,
    DatasetDetailResponse,
    DatasetResponse,
    EvalResultResponse,
    RunReportResponse,
    RunResponse,
)
from app.services.quality_eval_service import (
    EvaluationExecutionError,
    build_run_report,
    execute_evaluation_run,
)

router = APIRouter(tags=["quality-eval"], prefix="")


def _repo(db: Session) -> QualityEvalRepository:
    return QualityEvalRepository(db)


def _to_run_response(r: QualityEvalRun) -> RunResponse:
    """Run ORM → RunResponse 转换，单点维护。"""
    return RunResponse(
        run_id=r.run_id,
        dataset_id=r.dataset_id,
        project_code=r.project_code,
        agent_version=r.agent_version,
        llm_model=r.llm_model,
        prompt_version=r.prompt_version,
        gate_rule_version=r.gate_rule_version,
        task_type=r.task_type,
        eval_dimensions=r.eval_dimensions or [],
        status=r.status,
        total_items=r.total_items,
        completed_items=r.completed_items,
        overall_score=r.overall_score,
        coverage_score=r.coverage_score,
        assertion_score=r.assertion_score,
        executability_score=r.executability_score,
        consistency_score=r.consistency_score,
        robustness_score=r.robustness_score,
        hallucination_risk=r.hallucination_risk,
        created_at=r.created_at,
        finished_at=r.finished_at,
    )


# ── Dataset ──────────────────────────────────────────────────

@router.get("/api/quality-eval/datasets")
def list_datasets(
    project: str = Query(default="atp"),
    task_type: str = Query(default=""),
    db: Session = Depends(get_db),
) -> list[DatasetResponse]:
    items = _repo(db).list_datasets(project_code=project, task_type=task_type)
    return [
        DatasetResponse(
            dataset_id=d.dataset_id,
            project_code=d.project_code,
            name=d.name,
            description=d.description or "",
            task_type=d.task_type,
            eval_dimensions=d.eval_dimensions or [],
            item_count=d.item_count,
            version=d.version,
            created_at=d.created_at,
            updated_at=d.updated_at,
        )
        for d in items
    ]


@router.post("/api/quality-eval/datasets")
def create_dataset(
    body: CreateDatasetRequest,
    db: Session = Depends(get_db),
) -> DatasetResponse:
    repo = _repo(db)
    dataset_id = generate_dataset_id(body.task_type)

    ds = QualityEvalDataset(
        dataset_id=dataset_id,
        project_code=body.project_code,
        name=body.name,
        description=body.description,
        task_type=body.task_type,
        eval_dimensions=body.eval_dimensions,
    )
    repo.save_dataset(ds)

    for idx, item_input in enumerate(body.items):
        item = QualityEvalItem(
            item_id=generate_item_id(idx + 1),
            dataset_id=dataset_id,
            requirement_text=item_input.requirement_text,
            expected_coverage=item_input.expected_coverage,
            expected_assertions=item_input.expected_assertions,
            expected_page_codes=item_input.expected_page_codes,
            perturbed_requirement=item_input.perturbed_requirement,
            known_issues=item_input.known_issues,
            category=item_input.category,
            context_json=item_input.context_json,
        )
        repo.save_items([item])

    repo.increment_dataset_item_count(dataset_id, len(body.items))

    return DatasetResponse(
        dataset_id=ds.dataset_id,
        project_code=ds.project_code,
        name=ds.name,
        description=ds.description or "",
        task_type=ds.task_type,
        eval_dimensions=ds.eval_dimensions or [],
        item_count=len(body.items),
        version=ds.version,
        created_at=ds.created_at,
        updated_at=ds.updated_at,
    )


@router.get("/api/quality-eval/datasets/{dataset_id}")
def get_dataset(
    dataset_id: str,
    db: Session = Depends(get_db),
) -> DatasetDetailResponse:
    repo = _repo(db)
    ds = repo.get_dataset(dataset_id)
    if ds is None:
        raise HTTPException(status_code=404, detail="数据集不存在")

    items = repo.list_items(dataset_id)
    return DatasetDetailResponse(
        dataset_id=ds.dataset_id,
        project_code=ds.project_code,
        name=ds.name,
        description=ds.description or "",
        task_type=ds.task_type,
        eval_dimensions=ds.eval_dimensions or [],
        item_count=ds.item_count,
        version=ds.version,
        created_at=ds.created_at,
        updated_at=ds.updated_at,
        items=[
            {
                "item_id": it.item_id,
                "requirement_text": it.requirement_text,
                "expected_coverage": it.expected_coverage,
                "expected_assertions": it.expected_assertions,
                "expected_page_codes": it.expected_page_codes,
                "known_issues": it.known_issues,
            }
            for it in items
        ],
    )


@router.delete("/api/quality-eval/datasets/{dataset_id}")
def delete_dataset(
    dataset_id: str,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    repo = _repo(db)
    ok = repo.delete_dataset(dataset_id)
    if not ok:
        raise HTTPException(status_code=404, detail="数据集不存在")
    return {"status": "deleted"}


# ── Run ──────────────────────────────────────────────────────

@router.get("/api/quality-eval/runs")
def list_runs(
    project: str = Query(default="atp"),
    dataset_id: str = Query(default=""),
    db: Session = Depends(get_db),
) -> list[RunResponse]:
    items = _repo(db).list_runs(project_code=project, dataset_id=dataset_id)
    return [_to_run_response(r) for r in items]


@router.post("/api/quality-eval/runs")
def create_run(
    body: CreateRunRequest,
    db: Session = Depends(get_db),
) -> RunResponse:
    repo = _repo(db)
    ds = repo.get_dataset(body.dataset_id)
    if ds is None:
        raise HTTPException(status_code=404, detail="数据集不存在")

    run_id = generate_run_id()
    run = QualityEvalRun(
        run_id=run_id,
        dataset_id=body.dataset_id,
        project_code=body.project_code,
        agent_version=body.agent_version,
        llm_model=body.llm_model,
        prompt_version=body.prompt_version,
        gate_rule_version=body.gate_rule_version,
        task_type=body.task_type,
        eval_dimensions=body.eval_dimensions,
    )
    repo.save_run(run)
    return _to_run_response(run)


@router.post("/api/quality-eval/runs/{run_id}/execute")
def execute_run(
    run_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        result = execute_evaluation_run(db, run_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except EvaluationExecutionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api/quality-eval/runs/{run_id}")
def get_run(
    run_id: str,
    db: Session = Depends(get_db),
) -> RunResponse:
    repo = _repo(db)
    r = repo.get_run(run_id)
    if r is None:
        raise HTTPException(status_code=404, detail="评测运行不存在")
    return _to_run_response(r)


@router.get("/api/quality-eval/runs/{run_id}/results")
def list_run_results(
    run_id: str,
    db: Session = Depends(get_db),
) -> list[EvalResultResponse]:
    repo = _repo(db)
    run = repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="评测运行不存在")

    items = repo.list_items(run.dataset_id)
    item_map = {it.item_id: it for it in items}
    results = repo.list_results(run_id)

    return [
        EvalResultResponse(
            result_id=r.result_id,
            run_id=r.run_id,
            item_id=r.item_id,
            requirement_text=(
                matched.requirement_text if (matched := item_map.get(r.item_id)) else ""
            ),
            coverage_score=r.coverage_score,
            coverage_detail=r.coverage_detail or {},
            assertion_score=r.assertion_score,
            assertion_detail=r.assertion_detail or {},
            executability_score=r.executability_score,
            executability_detail=r.executability_detail or {},
            consistency_score=r.consistency_score,
            robustness_score=r.robustness_score,
            hallucination_flags=r.hallucination_flags or [],
            hallucination_score=r.hallucination_score,
            weighted_score=r.weighted_score,
            latency_ms=r.latency_ms,
            error_message=r.error_message or "",
        )
        for r in results
    ]


@router.get("/api/quality-eval/runs/{run_id}/report")
def get_run_report(
    run_id: str,
    db: Session = Depends(get_db),
) -> RunReportResponse:
    try:
        report = build_run_report(db, run_id)
        return RunReportResponse(**report)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/api/quality-eval/runs/{run_id}")
def delete_run(
    run_id: str,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    repo = _repo(db)
    ok = repo.delete_run(run_id)
    if not ok:
        raise HTTPException(status_code=404, detail="评测运行不存在")
    return {"status": "deleted"}
