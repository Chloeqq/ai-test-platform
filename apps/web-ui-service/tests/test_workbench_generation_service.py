from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services import workbench_generation_service


def test_allocate_case_id_skips_existing_requested_case_id(tmp_path: Path) -> None:
    assets_root = tmp_path / "test-cases"
    ai_cases_root = assets_root / "ai-generated"
    ai_cases_root.mkdir(parents=True, exist_ok=True)
    existing_case_id = "atp-web-ret-query-fn-ai-0001"
    (ai_cases_root / f"{existing_case_id}.yaml").write_text("id: atp-web-ret-query-fn-ai-0001\n", encoding="utf-8")

    allocated = workbench_generation_service._allocate_case_id(
        requested_case_id=existing_case_id,
        project="atp",
        page="ret",
        module="query",
        ai_cases_root=ai_cases_root,
        existing_case_ids=[existing_case_id],
    )

    assert allocated == "atp-web-ret-query-fn-ai-0002"


def test_preview_payload_uses_parser_runtime_source_count_when_source_summary_missing() -> None:
    def _fake_parse(**_: Any) -> dict[str, Any]:
        return {
            "requirement_spec": {
                "page": "returnapply",
                "priority": "P1",
                "parse_confidence": 0.81,
                "test_intents": [{"intent_id": "intent-01", "intent_type": "functional"}],
                "ambiguities": [],
                "business_rules": [],
                "parser_runtime": {"source_count": 2},
                "source_inputs": [
                    {"source_type": "text"},
                    {"source_type": "prd"},
                ],
                "change_impact": {},
            }
        }

    payload = workbench_generation_service.build_preview_test_points_payload(
        effective_requirement="示例需求",
        normalized_page="returnapply",
        source="text",
        input_sources=[],
        openapi_spec={},
        prd_text="",
        prd_url="",
        user_story="",
        git_diff="",
        git_diff_path="",
        openapi_url="",
        defect_ticket="",
        runtime_logs="",
        run_orchestrator_parse=_fake_parse,
        render_requirement_spec_markdown=lambda _: "",
        extract_quality_gate=lambda _: {},
    )

    item = payload["item"]
    assert item["source_count"] == 2
    assert item["source_types"] == ["text", "prd"]
