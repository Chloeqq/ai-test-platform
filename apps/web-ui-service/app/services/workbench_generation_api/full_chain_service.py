from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .context import WorkbenchContext
from .payloads import GenerateCasePayload
from .candidate_normalizer import CandidateNormalizer
from .generate_case_service import GenerateCaseService
from .orchestrator_client import OrchestratorClient
from .repository import WorkbenchGenerationRepository
from .scenario_engine import ScenarioEngine


def _normalize_chain_text(value: Any) -> str:
    return str(value or "").strip()


@dataclass
class FullChainPipelineState:
    payload: Any
    normalized_page: str = ""
    requirement_text: str = ""
    input_sources: list[dict[str, Any]] = field(default_factory=list)
    openapi_spec: dict[str, Any] = field(default_factory=dict)
    has_multisource_inputs: bool = False
    effective_requirement: str = ""
    preview_payload: dict[str, Any] = field(default_factory=dict)
    normalized_mode: str = "intent_based"
    normalized_profile: list[str] = field(default_factory=lambda: ["normal", "abnormal", "boundary"])
    candidates: list[dict[str, Any]] = field(default_factory=list)
    coverage_matrix: dict[str, Any] = field(default_factory=dict)
    generated_payload: dict[str, Any] = field(default_factory=dict)
    generated_items: list[dict[str, Any]] = field(default_factory=list)
    case_matrix: list[dict[str, Any]] = field(default_factory=list)
    execution_items: list[dict[str, Any]] = field(default_factory=list)
    linked_ref_total: int = 0
    step_row_total: int = 0
    run_status_counts: dict[str, int] = field(default_factory=dict)


class FullChainPipeline:
    def __init__(
        self,
        *,
        context: WorkbenchContext,
    ) -> None:
        self._context = context
        self._orchestrator_client = context.orchestrator_client
        self._candidate_normalizer = context.candidate_normalizer
        self._scenario_engine = context.scenario_engine
        self._repository = context.repository
        self._generate_case_service = GenerateCaseService(context=context)
        self._generation_service = context.generation
        self._flags = context.flags
        self._runtime = context.runtime

    def stage_prepare_request(self, state: FullChainPipelineState) -> None:
        self._runtime.ensure_dirs()
        state.normalized_page = self._runtime.normalize_page_slug(state.payload.page) if _normalize_chain_text(state.payload.page) else ""
        state.requirement_text = _normalize_chain_text(state.payload.requirement)
        state.input_sources = [item for item in state.payload.input_sources if isinstance(item, dict)]
        state.openapi_spec = state.payload.openapi_spec if isinstance(state.payload.openapi_spec, dict) else {}
        state.has_multisource_inputs = self._generation_service.has_multisource_inputs(
            input_sources=state.input_sources,
            openapi_spec=state.openapi_spec,
            prd_text=state.payload.prd_text,
            prd_url=state.payload.prd_url,
            user_story=state.payload.user_story,
            git_diff=state.payload.git_diff,
            git_diff_path=state.payload.git_diff_path,
            openapi_url=state.payload.openapi_url,
            defect_ticket=state.payload.defect_ticket,
            runtime_logs=state.payload.runtime_logs,
        )
        state.effective_requirement = self._generation_service.resolve_effective_requirement(
            requirement_text=state.requirement_text,
            normalized_page=state.normalized_page,
            multisource_enabled=state.has_multisource_inputs,
            build_system_requirement=self._runtime.build_system_requirement,
        )
        if not state.effective_requirement and not state.has_multisource_inputs and not state.normalized_page:
            raise self._runtime.HTTPException(
                status_code=self._runtime.status.HTTP_400_BAD_REQUEST,
                detail="requirement must not be empty when no page or additional input sources are provided",
            )

    def stage_preview_test_points(self, state: FullChainPipelineState) -> None:
        state.preview_payload = self._generation_service.build_preview_response(
            effective_requirement=state.effective_requirement,
            normalized_page=state.normalized_page,
            source=_normalize_chain_text(state.payload.source) or "manual",
            input_sources=state.input_sources,
            openapi_spec=state.openapi_spec,
            prd_text=state.payload.prd_text,
            prd_url=state.payload.prd_url,
            user_story=state.payload.user_story,
            git_diff=state.payload.git_diff,
            git_diff_path=state.payload.git_diff_path,
            openapi_url=state.payload.openapi_url,
            defect_ticket=state.payload.defect_ticket,
            runtime_logs=state.payload.runtime_logs,
            run_orchestrator_parse=self._orchestrator_client.parse,
            render_requirement_spec_markdown=self._orchestrator_client.render_requirement_spec_markdown,
            extract_quality_gate=self._orchestrator_client.extract_quality_gate,
            project=_normalize_chain_text(state.payload.project) or "mall",
        )

    def stage_build_candidate_matrix(self, state: FullChainPipelineState) -> None:
        state.normalized_mode = self._scenario_engine.normalize_combination_mode(state.payload.combination_mode)
        state.normalized_profile = self._scenario_engine.normalize_coverage_profile(state.payload.coverage_profile)
        state.candidates, state.coverage_matrix = self._scenario_engine.build_candidate_matrix(
            preview_payload=state.preview_payload,
            max_cases=int(state.payload.max_cases),
            combination_mode=state.normalized_mode,
            coverage_profile=state.normalized_profile,
            candidate_normalizer=self._candidate_normalizer,
        )
        if not state.candidates:
            state.candidates = self._candidate_normalizer.normalize_candidates(
                [
                    {
                        "title": _normalize_chain_text(state.payload.title) or "全链路自动生成用例",
                        "summary": state.effective_requirement,
                        "intent_type": "functional",
                        "priority": _normalize_chain_text(state.payload.priority) or "P1",
                        "tags": list(state.payload.tags or []),
                    }
                ]
            )
            default_scenario = self._scenario_engine.scenario_from_intent(state.candidates[0]) if state.candidates else "normal"
            state.coverage_matrix = {
                "combination_mode": state.normalized_mode,
                "coverage_profile": state.normalized_profile,
                "required_scenarios": state.normalized_profile,
                "detected_input_scenarios": [default_scenario],
                "covered_scenarios": [default_scenario],
                "missing_scenarios": [item for item in state.normalized_profile if item != default_scenario],
                "status": "full" if default_scenario in state.normalized_profile else "gap",
                "coverage_ratio": 1.0 if default_scenario in state.normalized_profile else 0.0,
                "expected_case_count": len(state.candidates),
                "generated_case_count": len(state.candidates),
                "truncated_by_max_cases": False,
                "expected_full_combinations": len(state.candidates),
            }

    def stage_coverage_gate(self, state: FullChainPipelineState) -> None:
        coverage_ratio = float(state.coverage_matrix.get("coverage_ratio", 0.0) or 0.0)
        coverage_status = _normalize_chain_text(state.coverage_matrix.get("status")).lower() or "unknown"
        if state.payload.coverage_gate_block_on_gap:
            threshold = float(state.payload.coverage_threshold)
            has_gap = bool(state.coverage_matrix.get("missing_scenarios")) or coverage_status != "full" or coverage_ratio < threshold
            if has_gap:
                raise self._runtime.HTTPException(
                    status_code=self._runtime.status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "coverage_gate_blocked",
                        "message": "coverage gate blocked full-chain run",
                        "coverage_matrix": state.coverage_matrix,
                        "threshold": threshold,
                    },
                )

    def stage_generate_cases(self, state: FullChainPipelineState) -> None:
        explicit_raw = list(state.payload.selected_candidates or [])
        explicit_list = [item for item in explicit_raw if isinstance(item, dict)]
        candidates_for_generate = state.candidates
        if explicit_list:
            normalized_explicit = self._candidate_normalizer.normalize_candidates(explicit_list)
            if normalized_explicit:
                candidates_for_generate = normalized_explicit
        generate_payload = GenerateCasePayload(
            project=_normalize_chain_text(state.payload.project) or "mall",
            page=state.normalized_page,
            requirement=state.effective_requirement,
            title=_normalize_chain_text(state.payload.title) or "全链路自动生成",
            case_id=_normalize_chain_text(state.payload.case_id),
            priority=_normalize_chain_text(state.payload.priority) or "P1",
            tags=list(state.payload.tags or []),
            source=_normalize_chain_text(state.payload.source) or "manual",
            input_sources=state.input_sources,
            openapi_spec=state.openapi_spec,
            prd_text=state.payload.prd_text,
            prd_url=state.payload.prd_url,
            user_story=state.payload.user_story,
            git_diff=state.payload.git_diff,
            git_diff_path=state.payload.git_diff_path,
            openapi_url=state.payload.openapi_url,
            defect_ticket=state.payload.defect_ticket,
            runtime_logs=state.payload.runtime_logs,
            preview_id=_normalize_chain_text(
                (state.preview_payload.get("item", {}) if isinstance(state.preview_payload, dict) else {}).get("preview_id")
            ),
            selected_candidates=candidates_for_generate,
        )
        state.generated_payload = self._generate_case_service.execute(generate_payload, mode="full_chain")
        state.generated_items = state.generated_payload.get("items") if isinstance(state.generated_payload.get("items"), list) else []

    def stage_execute_cases(self, state: FullChainPipelineState) -> None:
        state.case_matrix = []
        state.execution_items = []
        state.linked_ref_total = 0
        state.step_row_total = 0
        for raw_item in state.generated_items:
            item = raw_item if isinstance(raw_item, dict) else {}
            case_business_id = _normalize_chain_text(item.get("case_id"))
            case_obj = self._repository.find_test_case_by_case_id(case_business_id)
            linked_ref_count = 0
            skipped_ref_count = 0
            step_row_count = 0
            if case_obj is not None:
                if self._flags.page_object_auto_bind_enabled():
                    bind_result = self._repository.bind_case_page_object_refs(case_obj)
                    linked_ref_count = int(bind_result.get("linked_ref_count", 0))
                    skipped_ref_count = int(bind_result.get("skipped_ref_count", 0))
                step_row_count = self._repository.count_case_step_rows(case_db_id=int(case_obj.id))
            state.linked_ref_total += linked_ref_count
            state.step_row_total += step_row_count
            state.case_matrix.append(
                {
                    "case_id": case_business_id,
                    "name": _normalize_chain_text(item.get("title") or item.get("name")),
                    "path": _normalize_chain_text(item.get("path")),
                    "step_row_count": step_row_count,
                    "linked_ref_count": linked_ref_count,
                    "skipped_ref_count": skipped_ref_count,
                }
            )
            if not state.payload.run_after_generate:
                continue
            run_result = {
                "case_id": case_business_id,
                "run_id": "",
                "status": "skipped",
                "timed_out": False,
                "error": "",
            }
            raw_path = _normalize_chain_text(item.get("path"))
            if not raw_path:
                run_result["error"] = "missing case asset path"
                state.execution_items.append(run_result)
                continue
            case_path = Path(raw_path)
            if not case_path.exists():
                run_result["error"] = f"case file not found: {case_path}"
                state.execution_items.append(run_result)
                continue
            try:
                job = self._runtime.start_run(
                    project=_normalize_chain_text(state.payload.project) or "mall",
                    case_id=case_business_id,
                    case_path=case_path,
                    source="full-chain",
                )
                run_id = _normalize_chain_text(job.get("run_id"))
                final_item, timed_out = self._runtime.wait_run_terminal(run_id, timeout_seconds=int(state.payload.wait_seconds))
                final_payload = final_item if isinstance(final_item, dict) else job
                final_status = _normalize_chain_text(final_payload.get("status")) or "running"
                run_result.update(
                    {
                        "run_id": run_id,
                        "status": final_status,
                        "timed_out": bool(timed_out),
                    }
                )
            except Exception as exc:  # pragma: no cover
                run_result["status"] = "error"
                run_result["error"] = str(exc)
            state.execution_items.append(run_result)
        state.run_status_counts = {}
        for item in state.execution_items:
            key = _normalize_chain_text(item.get("status")) or "unknown"
            state.run_status_counts[key] = int(state.run_status_counts.get(key, 0)) + 1

    def stage_build_response(self, state: FullChainPipelineState) -> dict[str, Any]:
        return {
            "summary": {
                "project": _normalize_chain_text(state.payload.project) or "mall",
                "effective_requirement": state.effective_requirement,
                "combination_mode": state.normalized_mode,
                "coverage_profile": state.normalized_profile,
                "test_point_candidate_count": len(state.candidates),
                "generated_case_count": len(state.case_matrix),
                "test_step_row_count": state.step_row_total,
                "linked_ref_count": state.linked_ref_total,
                "executed_count": len(state.execution_items),
                "run_status_counts": state.run_status_counts,
                "coverage_status": _normalize_chain_text(state.coverage_matrix.get("status")) or "unknown",
                "coverage_ratio": float(state.coverage_matrix.get("coverage_ratio", 0.0) or 0.0),
                "coverage_missing_count": len(state.coverage_matrix.get("missing_scenarios") or []),
            },
            "stages": {
                "test_point_matrix": state.preview_payload.get("item", {}) if isinstance(state.preview_payload, dict) else {},
                "coverage_matrix": state.coverage_matrix,
                "test_case_matrix": state.case_matrix,
                "execution_results": state.execution_items,
            },
            "generated": {
                "count": int(state.generated_payload.get("count", 0) or 0),
                "items": state.generated_items,
            },
        }

    def run(self, payload: Any) -> dict[str, Any]:
        state = FullChainPipelineState(payload=payload)
        self.stage_prepare_request(state)
        self.stage_preview_test_points(state)
        self.stage_build_candidate_matrix(state)
        self.stage_coverage_gate(state)
        self.stage_generate_cases(state)
        self.stage_execute_cases(state)
        return self.stage_build_response(state)


class FullChainService:
    def __init__(self, *, pipeline: FullChainPipeline) -> None:
        self._pipeline = pipeline

    def execute(self, payload: Any) -> dict[str, Any]:
        return self._pipeline.run(payload)
