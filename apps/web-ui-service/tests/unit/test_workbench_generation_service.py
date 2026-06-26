from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi import HTTPException
import pytest

from app.services import workbench_generation_service
from app.services.workbench_generation_api import preview_store
from app.services.workbench_generation_api import save_test_point_assets_service
from app.services.workbench_generation_api.candidate_normalizer import CandidateNormalizer
from app.services.workbench_generation_compiler.runtime import generate_pipeline as generate_pipeline_module
from shared_backend.element_binding import resolve_involved_element_codes
from shared_backend.execution_compiler import ExecutionCompilerError
from shared_backend.schemas.contracts import normalize_test_point_plan_v1


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


def test_saved_test_point_structures_login_candidate_for_dsl_v1_1() -> None:
    point = save_test_point_assets_service._build_point(
        {
            "intent_id": "intent-01",
            "title": "首次登录成功",
            "summary": "首次登录成功",
            "intent_type": "functional",
            "priority": "P0",
            "steps": [
                "在用户名输入框输入正确账号 admin",
                "在密码输入框输入正确密码 macro",
                "点击登录按钮",
            ],
            "expected": "成功登录，页面跳转到首页",
            "involved_elements": ["用户名输入框", "密码输入框", "登录按钮"],
        },
        index=1,
    )

    assert point["precondition"] == "用户未登录，处于登录页面。"
    assert point["data"] == {
        "username": {"source_type": "inline", "value": "admin"},
        "password": {"source_type": "inline", "value": "macro"},
    }
    assert point["steps_hint"] == [
        "input:用户名输入框=admin",
        "input:密码输入框=macro",
        "click:登录按钮",
        "assert:首页菜单",
    ]
    assert [step["action"] for step in point["steps"]] == ["input", "input", "click", "assert_visible"]


def test_saved_test_point_adds_assertion_for_unauthorized_home_redirect() -> None:
    point = save_test_point_assets_service._build_point(
        {
            "intent_id": "intent-24",
            "title": "未登录访问首页被拦截",
            "summary": "未登录访问首页被拦截",
            "intent_type": "security",
            "priority": "P0",
            "precondition": "用户未登录",
            "steps": ["尝试直接访问首页"],
            "expected": "页面跳转回登录页面",
            "involved_elements": ["首页"],
        },
        index=24,
    )

    assert point["steps_hint"] == ["goto:#/home", "assert_url:#/login"]
    assert [step["action"] for step in point["steps"]] == ["goto", "assert_url"]


def test_test_point_plan_normalizer_preserves_dsl_v1_1_fields() -> None:
    normalized, warnings = normalize_test_point_plan_v1(
        {
            "version": "TestPointPlanV1",
            "case_id": "mall-web-login-auth-fn-ai-0001",
            "points": [
                {
                    "key": "intent-01",
                    "intent_id": "intent-01",
                    "point_type": "functional",
                    "precondition": "用户未登录，处于登录页面。",
                    "steps_hint": ["input:用户名输入框=admin", "assert:首页菜单"],
                    "data": {"username": {"source_type": "inline", "value": "admin"}},
                    "steps": [
                        {
                            "action": "input",
                            "target": "element:username_input",
                            "target_name": "用户名输入框",
                            "data_ref": "username",
                            "value": "admin",
                            "raw_text": "在用户名输入框输入正确账号 admin",
                        }
                    ],
                }
            ],
        }
    )

    assert warnings == []
    point = normalized["points"][0]
    assert point["precondition"] == "用户未登录，处于登录页面。"
    assert point["steps_hint"] == ["input:用户名输入框=admin", "assert:首页菜单"]
    assert point["data"] == {"username": {"source_type": "inline", "value": "admin"}}
    assert point["steps"][0]["target_name"] == "用户名输入框"
    assert point["steps"][0]["data_ref"] == "username"


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
    assert "source_count" not in item
    diagnostics = preview_store.build_preview_diagnostics(str(item["preview_id"]))
    diagnostic_item = diagnostics["item"]
    parser_runtime = diagnostic_item["parser_runtime"]
    assert parser_runtime["source_count"] == 2


def test_normalize_generated_case_title_strips_heading_and_bullet_text() -> None:
    assert workbench_generation_service._normalize_generated_case_title("登录功能：") == ""
    assert (
        workbench_generation_service._normalize_generated_case_title("- 正确账号密码可登录成功")
        == "正确账号密码可登录成功"
    )


def test_build_candidate_requirement_focuses_on_single_candidate() -> None:
    normalizer = CandidateNormalizer(SimpleNamespace(testpoint_filter_enabled=lambda: False))
    text = normalizer.build_candidate_requirement(
        "完整登录需求",
        {
            "intent_id": "intent-01",
            "title": "首次登录成功",
            "summary": "首次登录成功",
            "intent_type": "functional",
            "precondition": "用户未登录",
            "steps": ["输入账号", "输入密码", "点击登录"],
            "steps_hint": ["input:username_input", "input:password_input", "click:login_button"],
            "expected": "进入首页",
            "involved_elements": ["username_input", "password_input", "login_button"],
            "involved_element_codes": ["login-role---1", "login-role---2", "login-role---4"],
        },
    )

    assert text.startswith("测试点ID：intent-01")
    assert "steps_hint:" in text
    assert "1. input:username_input" in text
    assert "涉及元素Code：login-role---1、login-role---2、login-role---4" in text
    assert "完整登录需求" not in text
    assert "仅围绕上述单个测试意图生成" in text


def test_normalize_candidates_preserves_steps_hint() -> None:
    normalizer = CandidateNormalizer(SimpleNamespace(testpoint_filter_enabled=lambda: False))
    candidates = normalizer.normalize_candidates(
        [
            {
                "intent_id": "intent-01",
                "title": "首次登录成功",
                "summary": "首次登录成功",
                "intent_type": "functional",
                "priority": "P1",
                "precondition": "用户未登录",
                "steps": ["输入账号", "输入密码", "点击登录"],
                "steps_hint": ["input:username_input", "input:password_input", "click:login_button"],
                "expected": "进入首页",
                "involved_elements": ["username_input", "password_input", "login_button"],
            }
        ]
    )

    assert len(candidates) == 1
    assert candidates[0]["steps_hint"] == ["input:username_input", "input:password_input", "click:login_button"]


def test_resolve_page_object_blocks_yaml_fallback_in_strict_governance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(generate_pipeline_module, "_resolve_page_object_from_db", lambda _project, _page: None)

    with pytest.raises(generate_pipeline_module.ExecutionCompilerError) as exc:
        generate_pipeline_module.resolve_page_object("atp", "login")

    assert exc.value.code == "page_object_not_governed"
    assert "YAML fallback is disabled" in exc.value.reason


def test_resolve_page_object_db_error_does_not_fallback_to_yaml(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(_project: str, _page: str) -> dict[str, Any] | None:
        raise generate_pipeline_module.ExecutionCompilerError(
            code="page_object_db_lookup_failed",
            message="page object DB lookup failed",
            reason="db unavailable",
            stage="resolve_page_object",
        )

    monkeypatch.setattr(generate_pipeline_module, "_resolve_page_object_from_db", _boom)

    with pytest.raises(generate_pipeline_module.ExecutionCompilerError) as exc:
        generate_pipeline_module.resolve_page_object("atp", "login", strict_governance=False)

    assert exc.value.code == "page_object_db_lookup_failed"


def test_resolve_page_object_from_db_only_exposes_qualified_formal_elements(monkeypatch: pytest.MonkeyPatch) -> None:
    page_object = SimpleNamespace(id=1)
    elements = [
        SimpleNamespace(
            id=1,
            element_code="username_input",
            element_name="用户名输入框",
            locator_type="role",
            locator_value="用户名",
            role="textbox",
            status="active",
            review_status="approved",
            stability_level="high",
            business_type="input",
            business_domain="auth",
            aliases_json=["账号输入框"],
            semantic_tags_json=[],
        ),
        SimpleNamespace(
            id=2,
            element_code="dirty_button",
            element_name="脏按钮",
            locator_type="css",
            locator_value=".dirty",
            role="",
            status="active",
            review_status="pending",
            stability_level="low",
            business_type="button",
            business_domain="auth",
            aliases_json=["脏按钮"],
            semantic_tags_json=[],
        ),
    ]

    class _ScalarResult:
        def __init__(self, rows: list[object]) -> None:
            self._rows = rows

        def all(self) -> list[object]:
            return self._rows

    class _ExecuteResult:
        def __init__(self, value: object) -> None:
            self._value = value

        def scalar_one_or_none(self) -> object:
            return self._value

        def scalars(self) -> _ScalarResult:
            return _ScalarResult(self._value)  # type: ignore[arg-type]

    class _Session:
        def __init__(self) -> None:
            self.calls = 0

        def __enter__(self) -> "_Session":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def execute(self, _statement: object) -> _ExecuteResult:
            self.calls += 1
            return _ExecuteResult(page_object if self.calls == 1 else elements)

    monkeypatch.setattr(generate_pipeline_module, "SessionLocal", _Session)

    resolved = generate_pipeline_module._resolve_page_object_from_db("mall", "login")

    assert resolved is not None
    assert set(resolved["elements"]) == {"username_input"}
    assert resolved["elements"]["username_input"]["business_type"] == "input"
    assert "dirty_button" not in resolved["elements"]


def test_resolve_page_object_from_db_infers_login_business_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    page_object = SimpleNamespace(id=1)
    elements = [
        SimpleNamespace(
            id=1,
            element_code="username_input",
            element_name="",
            locator_type="css",
            locator_value="#username",
            role="",
            status="active",
            review_status="approved",
            stability_level="high",
            business_type="input",
            business_domain="auth",
            aliases_json=[],
            semantic_tags_json=[],
        ),
        SimpleNamespace(
            id=2,
            element_code="password_input",
            element_name="",
            locator_type="css",
            locator_value="#password",
            role="",
            status="active",
            review_status="approved",
            stability_level="high",
            business_type="input",
            business_domain="auth",
            aliases_json=[],
            semantic_tags_json=[],
        ),
        SimpleNamespace(
            id=3,
            element_code="login_button",
            element_name="",
            locator_type="css",
            locator_value="#login",
            role="",
            status="active",
            review_status="approved",
            stability_level="high",
            business_type="button",
            business_domain="auth",
            aliases_json=[],
            semantic_tags_json=[],
        ),
    ]

    class _ScalarResult:
        def __init__(self, rows: list[object]) -> None:
            self._rows = rows

        def all(self) -> list[object]:
            return self._rows

    class _ExecuteResult:
        def __init__(self, value: object) -> None:
            self._value = value

        def scalar_one_or_none(self) -> object:
            return self._value

        def scalars(self) -> _ScalarResult:
            return _ScalarResult(self._value)  # type: ignore[arg-type]

    class _Session:
        def __init__(self) -> None:
            self.calls = 0

        def __enter__(self) -> "_Session":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def execute(self, _statement: object) -> _ExecuteResult:
            self.calls += 1
            return _ExecuteResult(page_object if self.calls == 1 else elements)

    monkeypatch.setattr(generate_pipeline_module, "SessionLocal", _Session)

    resolved = generate_pipeline_module._resolve_page_object_from_db("mall", "login")
    codes, unknown = resolve_involved_element_codes(["账号输入框", "密码输入框", "登录按钮"], resolved or {})

    assert unknown == []
    assert codes == ["username_input", "password_input", "login_button"]


def test_enrich_test_points_prefers_candidate_element_codes_for_contract_validation() -> None:
    points = [
        {
            "intent_id": "intent-01",
            "point_type": "functional",
            "action": "candidate",
            "description": "首次登录成功",
            "expected_result": "登录成功",
            "involved_elements": ["账号输入框", "密码输入框", "登录按钮"],
            "steps": [{"action": "candidate_step", "value": "点击登录按钮"}],
        }
    ]
    candidates = [
        {
            "intent_id": "intent-01",
            "title": "首次登录成功",
            "intent_type": "functional",
            "priority": "P0",
            "expected": "登录成功",
            "involved_elements": ["账号输入框", "密码输入框", "登录按钮"],
            "involved_element_codes": ["username_input", "password_input", "login_button"],
        }
    ]

    enriched = generate_pipeline_module._enrich_test_points_with_candidate_snapshots(
        points=points,
        candidate_snapshots=candidates,
    )

    assert enriched[0]["involved_elements"] == ["username_input", "password_input", "login_button"]
    assert enriched[0]["involved_element_aliases"] == ["账号输入框", "密码输入框", "登录按钮"]
    assert enriched[0]["metadata"]["candidate_snapshot"]["involved_elements"] == ["账号输入框", "密码输入框", "登录按钮"]


def test_resolve_page_object_from_db_blocks_existing_page_without_qualified_elements(monkeypatch: pytest.MonkeyPatch) -> None:
    page_object = SimpleNamespace(id=1)
    elements = [
        SimpleNamespace(
            id=1,
            element_code="dirty_button",
            locator_value=".dirty",
            status="active",
            review_status="pending",
            stability_level="low",
        )
    ]

    class _ScalarResult:
        def all(self) -> list[object]:
            return elements

    class _ExecuteResult:
        def __init__(self, value: object = None) -> None:
            self._value = value

        def scalar_one_or_none(self) -> object:
            return page_object

        def scalars(self) -> _ScalarResult:
            return _ScalarResult()

    class _Session:
        def __enter__(self) -> "_Session":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def execute(self, _statement: object) -> _ExecuteResult:
            return _ExecuteResult()

    monkeypatch.setattr(generate_pipeline_module, "SessionLocal", _Session)

    with pytest.raises(generate_pipeline_module.ExecutionCompilerError) as exc:
        generate_pipeline_module._resolve_page_object_from_db("mall", "login")

    assert exc.value.code == "page_object_empty_elements"
    assert "active + review_status=approved" in exc.value.reason


def test_infer_password_toggle_alias_for_login_icon_element() -> None:
    aliases = generate_pipeline_module._infer_element_aliases(
        page="login",
        element_code="login-css-i-path-3",
        element_name="录制元素3",
        locator_value="i path:nth-child(3)",
        role="",
        aliases=[],
    )
    display_name = generate_pipeline_module._element_display_name(
        page="login",
        element_code="login-css-i-path-3",
        element_name="录制元素3",
        locator_value="i path:nth-child(3)",
        role="",
    )

    assert "password_visibility_toggle" in aliases
    assert display_name == "密码显隐开关"


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
            write_case_yaml=lambda _path, _case_yaml: "",
            save_case_state=lambda _project, _case_yaml, _case_path: {},
            append_history=lambda _entry: None,
            now_iso=lambda: "",
            is_quality_gate_blocked=lambda _payload: (False, None),
            ai_cases_root=Path("/tmp"),
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


def test_build_generated_case_payload_saves_test_point_plan_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = SimpleNamespace(
        project="atp",
        page="login",
        requirement="登录功能",
        title="登录功能",
        source="manual",
        case_id="",
        priority="P1",
        tags=["ai-generated"],
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
        selected_candidates=[{"intent_id": "intent-01", "source_asset_id": "atp-web-login-fn-ai-0001"}],
        selected_intent_ids=["intent-01"],
        page_url="",
    )
    ai_cases_root = tmp_path / "ai-generated"
    ai_cases_root.mkdir(parents=True, exist_ok=True)
    written_paths: list[Path] = []
    saved_plan_calls: list[dict[str, Any]] = []

    def _run_orchestrator_generate(**_kwargs: Any) -> dict[str, Any]:
        return {
            "requirement_spec": {
                "page": "login",
                "priority": "P1",
                "test_intents": [
                    {
                        "intent_id": "intent-01",
                        "title": "登录成功",
                        "intent_type": "functional",
                        "priority": "P1",
                        "expected_result": "登录成功",
                        "involved_elements": ["login_button"],
                        "steps": [
                            {"action": "click", "target": "login_button", "raw_text": "点击登录按钮"},
                            {"action": "assert_visible", "target": "login_button", "raw_text": "校验登录按钮可见"},
                        ],
                        "quality_gate": {"decision": "allow", "blockers": []},
                    }
                ],
                "quality_gate": {"decision": "allow", "blockers": []},
            },
            "case": {
                "id": "",
                "project": "atp",
                "module": "login",
                "execution": {"page": "login"},
                "title": "登录功能",
                "priority": "P1",
                "tags": ["ai-generated"],
            },
            "test_points": {
                "version": "TestPointPlanV1",
                "project": "atp",
                "case_id": "",
                "page": "login",
                "points": [
                    {
                        "intent_id": "intent-01",
                        "point_type": "action",
                        "action": "click",
                        "target": "login_button",
                        "expected_result": "登录成功",
                        "involved_elements": ["login_button"],
                        "steps": [
                            {"action": "click", "target": "login_button", "raw_text": "点击登录按钮"},
                            {"action": "assert_visible", "target": "login_button", "raw_text": "校验登录按钮可见"},
                        ],
                    }
                ],
            },
        }

    def _write_case_yaml(path: Path, data: dict[str, Any], **_kwargs: Any) -> str:
        written_paths.append(path)
        path.write_text("id: atp-web-login-fn-ai-0001\n", encoding="utf-8")
        return path.read_text(encoding="utf-8")

    def _save_case_state(_project: str, _case_yaml: dict[str, Any], _case_path: Any) -> dict[str, Any]:
        return {"version": 1}

    def _save_test_point_plan(**kwargs: Any) -> Path:
        saved_plan_calls.append(kwargs)
        plan_path = tmp_path / "test-points" / "atp" / "plans" / "atp-web-login-fn-ai-0001.json"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text("{}", encoding="utf-8")
        return plan_path

    monkeypatch.setattr(
        generate_pipeline_module,
        "resolve_page_object",
        lambda _project, _page: {"elements": {"login_button": {"selector": "#login", "type": "css"}}},
    )

    result = workbench_generation_service.build_generated_case_payload(
        payload=payload,
        normalized_page="login",
        effective_requirement="登录功能",
        multisource_enabled=False,
        input_sources=[],
        openapi_spec={},
        run_orchestrator_generate=_run_orchestrator_generate,
        extract_quality_gate=lambda _payload: {"decision": "allow", "blockers": []},
        write_case_yaml=_write_case_yaml,
        save_case_state=_save_case_state,
        save_test_point_plan=_save_test_point_plan,
        append_history=lambda _entry: None,
        now_iso=lambda: "2026-04-23T00:00:00+00:00",
        is_quality_gate_blocked=lambda _payload: (False, None),
        ai_cases_root=ai_cases_root,
        http_exception_cls=HTTPException,
        bad_gateway_status=502,
        unprocessable_entity_status=422,
        allocate_case_id=lambda **_kwargs: "atp-web-login-fn-ai-0001",
        existing_case_ids=[],
        selected_candidate={"intent_id": "intent-01", "source_asset_id": "atp-web-login-fn-ai-0001"},
    )

    assert written_paths
    assert saved_plan_calls
    assert saved_plan_calls[0]["project"] == "atp"
    assert saved_plan_calls[0]["case_id"] == "atp-web-login-fn-ai-0001"
    assert saved_plan_calls[0]["plan"]["points"][0]["intent_id"] == "intent-01"
    assert result["item"]["test_points_path"]


def test_build_generated_case_payload_directly_compiles_selected_candidate_steps_hint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = {
        "intent_id": "intent-05",
        "title": "账号和密码都为空点击登录",
        "summary": "账号和密码都为空点击登录",
        "intent_type": "negative",
        "priority": "P1",
        "steps": ["清空账号输入框", "清空密码输入框", "点击登录按钮"],
        "steps_hint": ["input:账号输入框=", "input:密码输入框=", "click:登录按钮", "assert:错误提示"],
        "expected": "提示请输入账号和密码",
        "involved_elements": ["账号输入框", "密码输入框", "登录按钮"],
        "involved_element_codes": ["username_input", "password_input", "login_button", "error_message"],
        "source_asset_id": "mall-web-login-auth-fn-ai-0021",
    }
    payload = SimpleNamespace(
        project="mall",
        page="login",
        requirement="登录页身份验证测试点集",
        title="账号和密码都为空点击登录",
        source="ai",
        case_id="",
        priority="P1",
        tags=["ai-generated"],
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
        selected_candidates=[candidate],
        selected_intent_ids=["intent-05"],
        page_url="http://localhost:5174/#/login",
    )
    ai_cases_root = tmp_path / "ai-generated"
    ai_cases_root.mkdir(parents=True, exist_ok=True)
    written_payloads: list[dict[str, Any]] = []

    def _unexpected_orchestrator_call(**_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("selected candidate with steps_hint should not call orchestrator")

    def _write_case_yaml(path: Path, data: dict[str, Any], **_kwargs: Any) -> str:
        written_payloads.append(data)
        import yaml

        text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
        path.write_text(text, encoding="utf-8")
        return text

    monkeypatch.setattr(
        generate_pipeline_module,
        "resolve_page_object",
        lambda _project, _page: {
            "page": "login",
            "page_url": "http://localhost:5174/#/login",
            "elements": {
                "remember_password_checkbox": {
                    "selector": "记住密码",
                    "type": "role",
                    "role": "checkbox",
                    "name": "记住密码复选框",
                    "aliases": ["记住密码"],
                    "business_type": "checkbox",
                },
                "username_input": {
                    "selector": "请输入用户名",
                    "type": "placeholder",
                    "name": "用户名输入框",
                    "aliases": ["账号输入框"],
                    "business_type": "input",
                },
                "password_input": {
                    "selector": "请输入密码",
                    "type": "placeholder",
                    "name": "密码输入框",
                    "aliases": ["密码输入框"],
                    "business_type": "input",
                },
                "login_button": {
                    "selector": "登录",
                    "type": "role",
                    "role": "button",
                    "name": "登录按钮",
                    "aliases": ["登录按钮"],
                    "business_type": "button",
                },
                "error_message": {
                    "selector": ".el-message--error",
                    "type": "css",
                    "name": "错误提示",
                    "aliases": ["错误提示"],
                    "business_type": "message",
                },
                "home_menu": {
                    "selector": "首页",
                    "type": "role",
                    "role": "menuitem",
                    "name": "首页菜单",
                    "aliases": ["首页", "工作台首页"],
                    "business_type": "menu",
                },
                "home-page": {
                    "selector": "home-page",
                    "type": "data-testid",
                    "name": "首页页面容器",
                    "aliases": ["首页", "工作台首页"],
                    "business_type": "container",
                },
            },
        },
    )

    result = workbench_generation_service.build_generated_case_payload(
        payload=payload,
        normalized_page="login",
        effective_requirement="登录页身份验证测试点集",
        multisource_enabled=False,
        input_sources=[],
        openapi_spec={},
        run_orchestrator_generate=_unexpected_orchestrator_call,
        extract_quality_gate=lambda payload: (payload or {}).get("quality_gate") if isinstance(payload, dict) else None,
        write_case_yaml=_write_case_yaml,
        save_case_state=lambda _project, _case_yaml, _case_path: {"version": 1},
        save_test_point_plan=lambda **_kwargs: tmp_path / "test-point-plan.json",
        append_history=lambda _entry: None,
        now_iso=lambda: "2026-05-08T00:00:00+00:00",
        is_quality_gate_blocked=lambda _payload: (False, None),
        ai_cases_root=ai_cases_root,
        http_exception_cls=HTTPException,
        bad_gateway_status=502,
        unprocessable_entity_status=422,
        allocate_case_id=lambda **_kwargs: "mall-web-login-fn-ai-0001",
        existing_case_ids=[],
        selected_candidate=candidate,
    )

    written_case = written_payloads[0]
    steps = written_case["execution"]["steps"]
    non_entry_steps = [step for step in steps if step.get("action") != "goto"]
    assert result["item"]["case_id"] == "mall-web-login-fn-ai-0001"
    assert written_case["version"] == "v1.1"
    assert written_case["requirement"] == {
        "intent_id": "intent-05",
        "title": "账号和密码都为空点击登录",
        "type": "negative",
        "source_asset_id": "mall-web-login-auth-fn-ai-0021",
    }
    assert written_case["execution"]["page_url"] == "http://localhost:5174/#/login"
    assert [step["action"] for step in non_entry_steps] == ["input", "input", "click", "assert_visible"]
    assert [step["target"] for step in non_entry_steps] == [
        "element:username_input",
        "element:password_input",
        "element:login_button",
        "element:error_message",
    ]
    assert written_case["data"] == {
        "username": {"source_type": "inline", "value": ""},
        "password": {"source_type": "inline", "value": ""},
    }
    assert written_case["execution"]["variables"] == {
        "login_username": "{{username}}",
        "login_password": "{{password}}",
    }
    assert non_entry_steps[0]["value"] == "{{login_username}}"
    assert non_entry_steps[1]["value"] == "{{login_password}}"
    assert non_entry_steps[0]["locator_type"] == "placeholder"
    assert non_entry_steps[0]["locator_value"] == "请输入用户名"
    assert non_entry_steps[1]["locator_type"] == "placeholder"
    assert non_entry_steps[1]["locator_value"] == "请输入密码"
    assert non_entry_steps[2]["expected_result"] == "已点击登录按钮"
    assert non_entry_steps[3] == {
        "action": "assert_visible",
        "target": "element:error_message",
        "locator_type": "css",
        "locator_value": ".el-message--error",
        "target_name": "错误提示",
        "expected_result": "提示请输入账号和密码",
    }
    assert written_case["assertions"] == []
    assert "input:密码输入框" not in str(written_case["requirement"])


def test_build_generated_case_payload_writes_product_yaml_for_login_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = "页面跳转至平台工作台首页，顶部展示当前登录用户名 admin，左侧加载对应权限导航菜单"
    candidate = {
        "intent_id": "intent-01",
        "title": "首次登录成功",
        "summary": "首次登录成功",
        "intent_type": "functional",
        "priority": "P0",
        "precondition": "用户未登录，处于登录页面",
        "steps": [
            "在账号输入框输入 test001",
            "在密码输入框输入 123456",
            "点击登录按钮",
        ],
        "steps_hint": ["input:账号输入框=test001", "input:密码输入框=123456", "click:登录按钮"],
        "expected": expected,
        "involved_elements": ["账号输入框", "密码输入框", "登录按钮"],
        "involved_element_codes": ["username_input", "password_input", "login_button"],
        "source_asset_id": "mall-web-login-auth-fn-ai-0021",
        "source_asset_title": "登录页身份验证测试点集",
    }
    payload = SimpleNamespace(
        project="mall",
        page="login",
        requirement="登录页身份验证测试点集",
        title="首次登录成功",
        source="ai",
        case_id="",
        priority="P0",
        tags=["ai-generated"],
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
        selected_candidates=[candidate],
        selected_intent_ids=["intent-01"],
        page_url="http://localhost:5174/#/login",
    )
    ai_cases_root = tmp_path / "ai-generated"
    ai_cases_root.mkdir(parents=True, exist_ok=True)
    written_payloads: list[dict[str, Any]] = []

    def _write_case_yaml(path: Path, data: dict[str, Any], **_kwargs: Any) -> str:
        written_payloads.append(data)
        import yaml

        text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
        path.write_text(text, encoding="utf-8")
        return text

    monkeypatch.setattr(
        generate_pipeline_module,
        "resolve_page_object",
        lambda _project, _page: {
            "page": "login",
            "page_url": "http://localhost:5174/#/login",
            "elements": {
                "username_input": {
                    "selector": "请输入用户名",
                    "type": "placeholder",
                    "name": "用户名输入框",
                    "aliases": ["账号输入框"],
                    "business_type": "input",
                },
                "password_input": {
                    "selector": "请输入密码",
                    "type": "placeholder",
                    "name": "密码输入框",
                    "aliases": ["密码输入框"],
                    "business_type": "input",
                },
                "remember_password_checkbox": {
                    "selector": "记住密码",
                    "type": "role",
                    "role": "checkbox",
                    "name": "记住密码复选框",
                    "aliases": ["记住密码"],
                    "business_type": "checkbox",
                },
                "login_button": {
                    "selector": "登录",
                    "type": "role",
                    "role": "button",
                    "name": "登录按钮",
                    "aliases": ["登录按钮"],
                    "business_type": "button",
                },
                "home_menu": {
                    "selector": "首页",
                    "type": "role",
                    "role": "menuitem",
                    "name": "首页菜单",
                    "aliases": ["首页", "工作台首页"],
                    "business_type": "menu",
                },
                "home-page": {
                    "selector": "home-page",
                    "type": "data-testid",
                    "name": "首页页面容器",
                    "aliases": ["首页", "工作台首页"],
                    "business_type": "container",
                },
            },
        },
    )

    workbench_generation_service.build_generated_case_payload(
        payload=payload,
        normalized_page="login",
        effective_requirement="登录页身份验证测试点集",
        multisource_enabled=False,
        input_sources=[],
        openapi_spec={},
        run_orchestrator_generate=lambda **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected orchestrator call")),
        extract_quality_gate=lambda payload: (payload or {}).get("quality_gate") if isinstance(payload, dict) else None,
        write_case_yaml=_write_case_yaml,
        save_case_state=lambda _project, _case_yaml, _case_path: {"version": 1},
        save_test_point_plan=lambda **_kwargs: tmp_path / "test-point-plan.json",
        append_history=lambda _entry: None,
        now_iso=lambda: "2026-05-08T00:00:00+00:00",
        is_quality_gate_blocked=lambda _payload: (False, None),
        ai_cases_root=ai_cases_root,
        http_exception_cls=HTTPException,
        bad_gateway_status=502,
        unprocessable_entity_status=422,
        allocate_case_id=lambda **_kwargs: "mall-web-login-auth-fn-ai-0007",
        existing_case_ids=[],
        selected_candidate=candidate,
    )

    written_case = written_payloads[0]
    steps = written_case["execution"]["steps"]
    assert written_case["version"] == "v1.1"
    assert written_case["requirement"] == {
        "intent_id": "intent-01",
        "title": "首次登录成功",
        "type": "functional",
        "precondition": "用户未登录，处于登录页面",
        "source_asset_id": "mall-web-login-auth-fn-ai-0021",
    }
    assert written_case["execution"]["page_url"] == "http://localhost:5174/#/login"
    assert written_case["data"] == {
        "username": {"source_type": "inline", "value": "test001"},
        "password": {"source_type": "inline", "value": "123456"},
    }
    assert written_case["execution"]["variables"] == {
        "login_username": "{{username}}",
        "login_password": "{{password}}",
    }
    assert steps[0]["action"] == "goto"
    assert steps[1]["target"] == "element:username_input"
    assert steps[1]["locator_type"] == "placeholder"
    assert steps[1]["locator_value"] == "请输入用户名"
    assert steps[1]["value"] == "{{login_username}}"
    assert steps[2]["target"] == "element:password_input"
    assert steps[2]["locator_type"] == "placeholder"
    assert steps[2]["locator_value"] == "请输入密码"
    assert steps[2]["value"] == "{{login_password}}"
    assert steps[3]["target"] == "element:login_button"
    assert steps[3]["expected_result"] == expected
    assert steps[4] == {
        "action": "assert_visible",
        "target": "element:home_menu",
        "locator_type": "role",
        "locator_value": "首页",
        "role": "menuitem",
        "target_name": "首页菜单",
        "expected_result": "登录后首页菜单可见，确认已离开登录页并进入工作台",
    }
    assert written_case["assertions"] == []
    assert "登录失败" not in str(written_case)
    assert "remember_password_checkbox" not in str(written_case)


def test_dsl_v1_1_enrichment_rejects_input_without_value() -> None:
    product_yaml = {
        "version": "v1",
        "id": "mall-web-login-auth-fn-ai-0001",
        "tags": ["ai-generated"],
        "status": "automated",
        "requirement": {
            "intent_id": "intent-01",
            "source_asset_id": "mall-web-login-auth-fn-ai-0021",
        },
        "execution": {
            "selected_intent_ids": ["intent-01"],
            "steps": [{"action": "input", "target": "element:username_input"}],
        },
        "assertions": [{"action": "assert_visible", "target": "element:home_menu"}],
    }

    with pytest.raises(ExecutionCompilerError) as exc_info:
        generate_pipeline_module._enrich_product_case_yaml_v1_1(product_yaml, page="login")

    assert exc_info.value.code == "dsl_v1_1_missing_input_data_source"


def test_dsl_v1_1_enrichment_rejects_ai_case_without_executable_assertion() -> None:
    product_yaml = {
        "version": "v1",
        "id": "mall-web-login-auth-fn-ai-0001",
        "tags": ["ai-generated"],
        "status": "automated",
        "requirement": {
            "intent_id": "intent-01",
            "source_asset_id": "mall-web-login-auth-fn-ai-0021",
        },
        "execution": {
            "selected_intent_ids": ["intent-01"],
            "steps": [
                {
                    "action": "input",
                    "target": "element:username_input",
                    "value": "asset-maintained-user",
                }
            ],
        },
    }

    with pytest.raises(ExecutionCompilerError) as exc_info:
        generate_pipeline_module._enrich_product_case_yaml_v1_1(product_yaml, page="login")

    assert exc_info.value.code == "dsl_v1_1_missing_executable_assertion"


def test_dsl_v1_1_enrichment_keeps_step_assertions_and_dedupes_top_level() -> None:
    product_yaml = {
        "version": "v1",
        "id": "mall-web-login-auth-fn-ai-0001",
        "tags": ["ai-generated"],
        "status": "automated",
        "requirement": {
            "intent_id": "intent-01",
            "source_asset_id": "mall-web-login-auth-fn-ai-0021",
        },
        "execution": {
            "selected_intent_ids": ["intent-01"],
            "steps": [
                {"action": "input", "target": "element:username_input", "value": "admin"},
                {
                    "action": "assert_visible",
                    "target": "element:home_menu",
                    "locator_type": "role",
                    "locator_value": "首页",
                    "role": "menuitem",
                },
            ],
        },
        "assertions": [
            {
                "action": "assert_visible",
                "target": "element:home_menu",
                "locator_type": "role",
                "locator_value": "首页",
                "role": "menuitem",
            }
        ],
    }

    enriched = generate_pipeline_module._enrich_product_case_yaml_v1_1(product_yaml, page="login")

    steps = enriched["execution"]["steps"]
    assert [step["action"] for step in steps] == ["input", "assert_visible"]
    assert enriched["assertions"] == []


def test_dsl_v1_1_assertion_dedupe_keeps_same_target_different_values() -> None:
    product_yaml = {
        "version": "v1",
        "id": "mall-web-login-auth-fn-ai-0001",
        "tags": ["ai-generated"],
        "status": "automated",
        "requirement": {
            "intent_id": "intent-01",
            "source_asset_id": "mall-web-login-auth-fn-ai-0021",
        },
        "execution": {
            "selected_intent_ids": ["intent-01"],
            "steps": [
                {
                    "action": "assert_text",
                    "target": "element:error_message",
                    "locator_type": "css",
                    "locator_value": ".el-message--error",
                    "value": "请输入用户名",
                }
            ],
        },
        "assertions": [
            {
                "action": "assert_text",
                "target": "element:error_message",
                "locator_type": "css",
                "locator_value": ".el-message--error",
                "value": "请输入用户名",
            },
            {
                "action": "assert_text",
                "target": "element:error_message",
                "locator_type": "css",
                "locator_value": ".el-message--error",
                "value": "请输入密码",
            },
        ],
    }

    enriched = generate_pipeline_module._enrich_product_case_yaml_v1_1(product_yaml, page="login")

    assert enriched["execution"]["steps"][0]["value"] == "请输入用户名"
    assert enriched["assertions"] == [
        {
            "action": "assert_text",
            "target": "element:error_message",
            "locator_type": "css",
            "locator_value": ".el-message--error",
            "value": "请输入密码",
        }
    ]


def test_product_execution_steps_preserve_governed_data_testid_locator() -> None:
    steps = generate_pipeline_module._format_product_execution_steps(
        compiled_steps=[
            {
                "action": "input",
                "target": "username_input",
                "locator_type": "css",
                "locator_value": "input[name='username']",
                "value": "admin",
                "intent_id": "intent-01",
            }
        ],
        page="login",
        page_url="http://localhost:5174/#/login",
        page_object={
            "elements": {
                "username_input": {
                    "selector": "login-username-input",
                    "type": "data-testid",
                    "name": "用户名输入框",
                }
            }
        },
        expected_by_intent={},
    )

    assert steps[0]["locator_type"] == "data-testid"
    assert steps[0]["locator_value"] == "login-username-input"


def test_product_execution_steps_prefer_login_data_testid_counterpart_over_legacy_semantic_element() -> None:
    steps = generate_pipeline_module._format_product_execution_steps(
        compiled_steps=[
            {
                "action": "input",
                "target": "username_input",
                "locator_type": "css",
                "locator_value": "input[name='username']",
                "value": "admin",
                "intent_id": "intent-01",
            },
            {
                "action": "click",
                "target": "login_button",
                "locator_type": "role",
                "locator_value": "登录",
                "intent_id": "intent-01",
            },
        ],
        page="login",
        page_url="http://localhost:5174/#/login",
        page_object={
            "elements": {
                "username_input": {
                    "selector": "请输入用户名",
                    "type": "placeholder",
                    "name": "用户名输入框",
                },
                "login-username-input": {
                    "selector": "login-username-input",
                    "type": "data-testid",
                    "name": "用户名输入框",
                },
                "login_button": {
                    "selector": "登录",
                    "type": "role",
                    "role": "button",
                    "name": "登录按钮",
                },
                "login-submit-btn": {
                    "selector": "login-submit-btn",
                    "type": "data-testid",
                    "name": "登录按钮",
                },
            }
        },
        expected_by_intent={},
    )

    assert steps[0]["target"] == "element:username_input"
    assert steps[0]["locator_type"] == "data-testid"
    assert steps[0]["locator_value"] == "login-username-input"
    assert steps[1]["target"] == "element:login_button"
    assert steps[1]["locator_type"] == "data-testid"
    assert steps[1]["locator_value"] == "login-submit-btn"


def test_trusted_page_url_rejects_payload_override() -> None:
    with pytest.raises(ExecutionCompilerError) as exc_info:
        generate_pipeline_module._trusted_page_url(
            payload_page_url="http://127.0.0.1:8013/react/login",
            page_object={"page_url": "http://localhost:5174/#/login"},
        )

    assert exc_info.value.code == "dsl_v1_1_page_url_mismatch"


def test_attach_point_expected_results_does_not_override_step_expected_result() -> None:
    steps = [
        {
            "action": "click",
            "target": "login_button",
            "intent_id": "intent-01",
            "expected_result": "已点击登录按钮",
        }
    ]
    points = [{"intent_id": "intent-01", "expected_result": "页面跳转至工作台首页"}]

    result = generate_pipeline_module._attach_point_expected_results(steps, points)

    assert result[0]["expected_result"] == "已点击登录按钮"


def test_build_generated_case_payload_rejects_multiple_selected_intents(tmp_path: Path) -> None:
    payload = SimpleNamespace(
        project="mall",
        page="login",
        requirement="登录页身份验证测试点集",
        title="批量意图",
        source="ai",
        case_id="",
        priority="P1",
        tags=["ai-generated"],
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
        selected_candidates=[
            {"intent_id": "intent-01", "source_asset_id": "mall-web-login-auth-fn-ai-0021"},
            {"intent_id": "intent-02", "source_asset_id": "mall-web-login-auth-fn-ai-0021"},
        ],
        selected_intent_ids=["intent-01", "intent-02"],
        page_url="http://localhost:5174/#/login",
    )

    with pytest.raises(HTTPException) as exc_info:
        workbench_generation_service.build_generated_case_payload(
            payload=payload,
            normalized_page="login",
            effective_requirement="登录页身份验证测试点集",
            multisource_enabled=False,
            input_sources=[],
            openapi_spec={},
            run_orchestrator_generate=lambda **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected orchestrator call")),
            extract_quality_gate=lambda _payload: None,
            write_case_yaml=lambda _path, _case_yaml: "",
            save_case_state=lambda _project, _case_yaml, _case_path: {},
            append_history=lambda _entry: None,
            now_iso=lambda: "2026-05-25T00:00:00+00:00",
            is_quality_gate_blocked=lambda _payload: (False, None),
            ai_cases_root=tmp_path,
            http_exception_cls=HTTPException,
            bad_gateway_status=502,
            unprocessable_entity_status=422,
            allocate_case_id=lambda **_kwargs: "mall-web-login-auth-fn-ai-0001",
            existing_case_ids=[],
            selected_candidate=None,
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["code"] == "dsl_v1_1_selected_intent_count_invalid"


def test_generation_payload_redaction_hides_sensitive_values() -> None:
    payload = {
        "selected_candidate": {
            "intent_id": "intent-01",
            "steps_hint": ["input:密码输入框=macro"],
            "password": "macro",
        },
        "input_sources": [{"source_type": "text", "content": "password=123456"}],
        "data": {"password": {"source_type": "inline", "value": "macro"}},
    }

    redacted = generate_pipeline_module._redact_generation_payload(payload)

    assert "macro" not in str(redacted)
    assert "123456" not in str(redacted)
    assert redacted["selected_candidate"]["password"] == "***"
