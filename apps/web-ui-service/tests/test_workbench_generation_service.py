from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import HTTPException
import pytest

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

    payload = workbench_generation_service.build_preview_response(
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


def test_normalize_generated_case_title_strips_heading_and_bullet_text() -> None:
    assert workbench_generation_service._normalize_generated_case_title("登录功能：") == ""
    assert (
        workbench_generation_service._normalize_generated_case_title("- 正确账号密码可登录成功")
        == "正确账号密码可登录成功"
    )


def test_ensure_execution_steps_keeps_ai_steps_raw_when_present() -> None:
    case_yaml = {
        "execution": {
            "page": "login",
            "steps": [
                {"action": "login"},
                {"action": "assert_visible", "target": "home_page"},
            ],
        }
    }

    workbench_generation_service._ensure_execution_steps(
        case_yaml=case_yaml,
        page="login",
        title="输入正确用户名密码，点击登录，成功进入首页",
        infer_targets=lambda _page: ("menu_target", "assert_target"),
    )

    execution = case_yaml.get("execution") if isinstance(case_yaml.get("execution"), dict) else {}
    steps = execution.get("steps") if isinstance(execution.get("steps"), list) else []
    assert len(steps) == 2
    assert steps == [
        {"action": "login"},
        {"action": "assert_visible", "target": "home_page"},
    ]


def test_ensure_execution_steps_falls_back_only_when_ai_steps_missing() -> None:
    case_yaml = {"execution": {"page": "login", "steps": []}}

    try:
        workbench_generation_service._ensure_execution_steps(
            case_yaml=case_yaml,
            page="login",
            title="输入正确用户名密码，点击登录，成功进入首页",
            infer_targets=lambda _page: ("menu_target", "assert_target"),
        )
    except ValueError as exc:
        assert "empty execution.steps" in str(exc)
        return
    raise AssertionError("expected ValueError when AI steps are missing in pure-ai mode")


def test_build_generated_case_payload_passes_through_orchestrator_validation_error() -> None:
    class _Payload:
        project = "atp"
        page = "login"
        requirement = "登录功能"
        title = "登录功能"
        source = "manual"
        case_id = ""
        priority = "P1"
        tags = ["ai-generated"]
        input_sources = []
        openapi_spec = {}
        prd_text = ""
        prd_url = ""
        user_story = ""
        git_diff = ""
        git_diff_path = ""
        openapi_url = ""
        defect_ticket = ""
        runtime_logs = ""

    def _raise_unprocessable(**_: Any):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "validation_error",
                "message": "test-design-agent returned invalid structured output",
                "reason_code": "test_design_invalid_output",
            },
        )

    with pytest.raises(HTTPException) as exc_info:
        workbench_generation_service.build_generated_case_payload(
            payload=_Payload(),
            normalized_page="login",
            effective_requirement="登录功能",
            multisource_enabled=False,
            input_sources=[],
            openapi_spec={},
            run_orchestrator_generate=_raise_unprocessable,
            extract_quality_gate=lambda _payload: None,
            safe_case_id=lambda value: str(value or ""),
            infer_targets=lambda _page: ("", ""),
            write_case_yaml=lambda _path, _case_yaml: "",
            save_case_state=lambda _project, _case_yaml, _case_path: {},
            append_history=lambda _entry: None,
            now_iso=lambda: "",
            is_quality_gate_blocked=lambda _payload: (False, None),
            ai_cases_root=Path("/tmp"),
            utc=None,
            datetime_module=None,
            http_exception_cls=HTTPException,
            bad_gateway_status=502,
            unprocessable_entity_status=422,
            allocate_case_id=workbench_generation_service._allocate_case_id,
            existing_case_ids=[],
            selected_candidate=None,
        )

    assert exc_info.value.status_code == 422
    assert isinstance(exc_info.value.detail, dict)
    assert exc_info.value.detail.get("reason_code") == "test_design_invalid_output"
