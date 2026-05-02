from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import app.models.page_object as page_object_model
import app.models.test_case as test_case_model
import app.models.test_point as test_point_model
from app.services import test_case_service, workbench_generation_service, workbench_runtime_service, workbench_state_store
from app.services.workbench_generation_api import context as generation_context
from app.services.workbench_generation_api import preview_test_points_usecase


class _StubOrchestratorClient:
    def __init__(self, *, parse_result: dict[str, object] | None = None) -> None:
        self._parse_result = parse_result or {}

    def parse(self, **_kwargs: object) -> dict[str, object]:
        return dict(self._parse_result)

    def generate(self, **_kwargs: object) -> dict[str, object]:
        return {}

    def extract_quality_gate(self, payload: object) -> dict[str, object] | None:
        return workbench_generation_service.extract_quality_gate(payload)

    def is_quality_gate_blocked(self, payload: object) -> tuple[bool, dict[str, object] | None]:
        return workbench_generation_service.is_quality_gate_blocked(payload)

    def render_requirement_spec_markdown(self, requirement_spec: dict[str, object]) -> str:
        return workbench_generation_service.render_requirement_spec_markdown(requirement_spec)


def test_generate_case_sync_does_not_fail_for_same_asset_case_id(
    workbench_generation_client: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, db_session = workbench_generation_client
    assets_root = tmp_path / "test-cases"
    ai_cases_root = assets_root / "ai-generated"
    ai_cases_root.mkdir(parents=True, exist_ok=True)
    case_id = "atp-web-ret-query-fn-ai-0002"
    case_file = ai_cases_root / f"{case_id}.yaml"
    case_file.write_text(
        "id: atp-web-ret-query-fn-ai-0002\n"
        "title: workbench generated case\n"
        "module: query\n"
        "priority: P1\n"
        "tags:\n"
        "  - ai-generated\n"
        "execution:\n"
        "  page: ret\n"
        "  steps:\n"
        "    - action: click\n"
        "      target: query_button\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(workbench_state_store, "ASSETS_CASES_ROOT", assets_root)
    monkeypatch.setattr(workbench_state_store, "AI_CASES_ROOT", ai_cases_root)
    monkeypatch.setattr(test_case_service, "ASSETS_CASES_ROOT", assets_root)

    def _stub_build_generated_case_payload(**_kwargs: object) -> dict[str, object]:
        return {
            "message": "case generated",
            "item": {
                "case_id": case_id,
                "project": "atp",
                "path": str(case_file.resolve()),
                "yaml_content": case_file.read_text(encoding="utf-8"),
                "state": {},
            },
        }

    monkeypatch.setattr(
        workbench_generation_service,
        "build_generated_case_payload",
        _stub_build_generated_case_payload,
    )

    response = client.post(
        "/api/workbench/generate",
        json={
            "project": "atp",
            "page": "ret",
            "requirement": "验证退货查询可用",
            "source": "manual",
            "case_id": case_id,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    item = payload["item"]
    assert item["case_id"] == case_id
    assert item["synced_case"]["case_id"] == case_id

    saved = db_session.execute(select(test_case_model.TestCase).where(test_case_model.TestCase.case_id == case_id)).scalar_one_or_none()
    assert saved is not None


def test_generate_case_supports_batch_candidates(
    workbench_generation_client: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, db_session = workbench_generation_client
    assets_root = tmp_path / "test-cases"
    ai_cases_root = assets_root / "ai-generated"
    ai_cases_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(workbench_state_store, "ASSETS_CASES_ROOT", assets_root)
    monkeypatch.setattr(workbench_state_store, "AI_CASES_ROOT", ai_cases_root)
    monkeypatch.setattr(test_case_service, "ASSETS_CASES_ROOT", assets_root)

    counter = {"value": 0}

    def _stub_build_generated_case_payload(**kwargs: object) -> dict[str, object]:
        counter["value"] += 1
        index = counter["value"]
        current_payload = kwargs.get("payload")
        title = str(getattr(current_payload, "title", "") or f"batch-{index}").strip() or f"batch-{index}"
        case_id = f"atp-web-ret-query-fn-ai-{index:04d}"
        case_file = ai_cases_root / f"{case_id}.yaml"
        case_file.write_text(
            "\n".join(
                [
                    f"id: {case_id}",
                    f"title: {title}",
                    "module: query",
                    "priority: P1",
                    "tags:",
                    "  - ai-generated",
                    "execution:",
                    "  page: ret",
                    "  steps:",
                    "    - action: click",
                    "      target: query_button",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return {
            "message": "case generated",
            "item": {
                "case_id": case_id,
                "project": "atp",
                "path": str(case_file.resolve()),
                "yaml_content": case_file.read_text(encoding="utf-8"),
                "state": {},
            },
        }

    monkeypatch.setattr(
        workbench_generation_service,
        "build_generated_case_payload",
        _stub_build_generated_case_payload,
    )

    response = client.post(
        "/api/workbench/generate",
        json={
            "project": "atp",
            "page": "ret",
            "requirement": "验证退货查询可用",
            "source": "manual",
            "selected_candidates": [
                {"title": "候选一", "intent_type": "functional", "priority": "P1"},
                {"title": "候选二", "intent_type": "negative", "priority": "P1"},
            ],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["count"] == 2
    assert isinstance(payload["items"], list)
    assert len(payload["items"]) == 2
    assert payload["item"]["case_id"] == "atp-web-ret-query-fn-ai-0001"
    assert payload["items"][1]["case_id"] == "atp-web-ret-query-fn-ai-0002"

    saved_count = db_session.execute(select(func.count(test_case_model.TestCase.id))).scalar_one()
    assert int(saved_count or 0) >= 2


def test_generate_case_batch_filters_metadata_noise_candidates(
    workbench_generation_client: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, db_session = workbench_generation_client
    assets_root = tmp_path / "test-cases"
    ai_cases_root = assets_root / "ai-generated"
    ai_cases_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(workbench_state_store, "ASSETS_CASES_ROOT", assets_root)
    monkeypatch.setattr(workbench_state_store, "AI_CASES_ROOT", ai_cases_root)
    monkeypatch.setattr(test_case_service, "ASSETS_CASES_ROOT", assets_root)

    counter = {"value": 0}

    def _stub_build_generated_case_payload(**kwargs: object) -> dict[str, object]:
        counter["value"] += 1
        index = counter["value"]
        current_payload = kwargs.get("payload")
        title = str(getattr(current_payload, "title", "") or f"batch-{index}").strip() or f"batch-{index}"
        case_id = f"atp-web-ret-query-fn-ai-{index:04d}"
        case_file = ai_cases_root / f"{case_id}.yaml"
        case_file.write_text(
            "\n".join(
                [
                    f"id: {case_id}",
                    f"title: {title}",
                    "module: query",
                    "priority: P1",
                    "tags:",
                    "  - ai-generated",
                    "execution:",
                    "  page: ret",
                    "  steps:",
                    "    - action: click",
                    "      target: query_button",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return {
            "message": "case generated",
            "item": {
                "case_id": case_id,
                "project": "atp",
                "path": str(case_file.resolve()),
                "yaml_content": case_file.read_text(encoding="utf-8"),
                "state": {},
            },
        }

    monkeypatch.setattr(
        workbench_generation_service,
        "build_generated_case_payload",
        _stub_build_generated_case_payload,
    )

    response = client.post(
        "/api/workbench/generate",
        json={
            "project": "atp",
            "page": "login",
            "requirement": "登录测试",
            "source": "manual",
            "selected_candidates": [
                {"title": "[page_url] http://localhost:5173/#/login", "intent_type": "api", "priority": "P0"},
                {"title": 'source": "manual",', "intent_type": "functional", "priority": "P1"},
                {"title": "[user_story] 需求: 一次生成可追溯测试点", "intent_type": "functional", "priority": "P1"},
                {"title": "【模块】认证中心-登录", "intent_type": "functional", "priority": "P1"},
                {
                    "title": "用户名为空，点击登录，提示不能为空",
                    "summary": "用户名为空时给出必填提示",
                    "intent_type": "negative",
                    "priority": "P1",
                    "precondition": "登录页可访问",
                    "steps": ["1. 留空用户名并输入正确密码", "2. 点击登录按钮"],
                    "expected": "提示用户名不能为空",
                },
            ],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["count"] == 1
    assert len(payload["items"]) == 1
    assert counter["value"] == 1

    names = db_session.execute(select(test_case_model.TestCase.name)).scalars().all()
    assert "用户名为空，点击登录，提示不能为空" in names


def test_preview_test_points_keeps_llm_intents_without_rule_filtering(
    workbench_generation_client: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _db_session = workbench_generation_client
    monkeypatch.setattr(
        preview_test_points_usecase,
        "build_orchestrator_client",
        lambda: _StubOrchestratorClient(
            parse_result={
                "requirement_spec": {
                    "page": "login",
                    "priority": "P1",
                    "test_intents": [
                        {"title": "验证用户登录模块功能是否正常", "summary": "正确用户名与密码可登录", "intent_type": "functional"},
                        {"title": "用户名为空点击登录提示必填", "summary": "用户名为空时应提示", "intent_type": "negative"},
                        {"title": 'type":"new_requirement",', "summary": "metadata noise", "intent_type": "functional"},
                        {"title": 'requirement_overview": {', "summary": "metadata noise", "intent_type": "functional"},
                        {"title": "[priority_policy] P1=业务规则异常", "summary": "policy noise", "intent_type": "negative"},
                        {"title": "[domain_rule] 首页依赖登录页，未登录禁止进入首页核心区", "summary": "rule noise", "intent_type": "functional"},
                        {"title": "[user_story]角色: 测试人员", "summary": "story role noise", "intent_type": "functional"},
                        {"title": "【模块】认证中心-登录", "summary": "section heading noise", "intent_type": "functional"},
                        {"title": "【页面】login（登录页）", "summary": "section heading noise", "intent_type": "functional"},
                        {"title": 'source": "manual",', "summary": "json kv noise", "intent_type": "functional"},
                        {"title": 'page_elements": [', "summary": "json kv noise", "intent_type": "functional"},
                    ],
                }
            }
        ),
    )

    response = client.post(
        "/api/workbench/preview-test-points",
        json={
            "project": "atp",
            "page": "login",
            "requirement": "登录页测试点",
            "source": "manual",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    item = payload.get("item") if isinstance(payload, dict) else {}
    item = item if isinstance(item, dict) else {}
    assert int(item.get("intent_count", 0)) == 11
    requirement_spec = item.get("requirement_spec") if isinstance(item.get("requirement_spec"), dict) else {}
    intents = requirement_spec.get("test_intents") if isinstance(requirement_spec.get("test_intents"), list) else []
    assert len(intents) == 11
    titles = [str(intent.get("title", "")).strip() for intent in intents if isinstance(intent, dict)]
    assert 'type":"new_requirement",' in titles
    assert "[priority_policy] P1=业务规则异常" in titles


def test_preview_test_points_does_not_expand_login_compound_intents(
    workbench_generation_client: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _db_session = workbench_generation_client
    monkeypatch.setattr(
        preview_test_points_usecase,
        "build_orchestrator_client",
        lambda: _StubOrchestratorClient(
            parse_result={
                "requirement_spec": {
                    "page": "login",
                    "priority": "P0",
                    "test_intents": [
                        {"title": "1. 正常流程：用户输入正确的用户名密码，点击登录，成功进入首页", "intent_type": "functional"},
                        {"title": "2. 权限控制：未登录状态下，禁止访问首页核心区域", "intent_type": "security"},
                        {"title": "3. 异常处理：用户名/密码错误、为空、格式非法，给出对应提示", "intent_type": "negative"},
                        {"title": "4. 边界校验：用户名/密码长度超限，提示格式错误", "intent_type": "negative"},
                        {"title": '{"name": "首页", "key_attribute": "核心区域"}', "intent_type": "functional"},
                        {"title": 'priority": "P', "intent_type": "functional"},
                    ],
                }
            }
        ),
    )

    response = client.post(
        "/api/workbench/preview-test-points",
        json={
            "project": "atp",
            "page": "login",
            "requirement": "登录页测试点",
            "source": "manual",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    item = payload.get("item") if isinstance(payload, dict) else {}
    item = item if isinstance(item, dict) else {}
    requirement_spec = item.get("requirement_spec") if isinstance(item.get("requirement_spec"), dict) else {}
    intents = requirement_spec.get("test_intents") if isinstance(requirement_spec.get("test_intents"), list) else []
    titles = [str(intent.get("title", "")).strip() for intent in intents if isinstance(intent, dict)]

    assert "1. 正常流程：用户输入正确的用户名密码，点击登录，成功进入首页" in titles
    assert "2. 权限控制：未登录状态下，禁止访问首页核心区域" in titles
    assert "3. 异常处理：用户名/密码错误、为空、格式非法，给出对应提示" in titles
    assert "4. 边界校验：用户名/密码长度超限，提示格式错误" in titles
    assert '{"name": "首页", "key_attribute": "核心区域"}' in titles
    assert 'priority": "P' in titles


def test_full_chain_run_generates_case_steps_binds_page_objects_and_executes(
    workbench_generation_client: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, db_session = workbench_generation_client
    assets_root = tmp_path / "test-cases"
    ai_cases_root = assets_root / "ai-generated"
    ai_cases_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(workbench_state_store, "ASSETS_CASES_ROOT", assets_root)
    monkeypatch.setattr(workbench_state_store, "AI_CASES_ROOT", ai_cases_root)
    monkeypatch.setattr(test_case_service, "ASSETS_CASES_ROOT", assets_root)

    page_obj = page_object_model.PageObject(
        project_code="atp",
        client="web",
        page_code="login",
        page_name="登录页",
        page_url="/login",
        status="draft",
        created_by="tester",
    )
    db_session.add(page_obj)
    db_session.commit()
    db_session.refresh(page_obj)
    db_session.add(
        page_object_model.PageElement(
            page_object_id=int(page_obj.id),
            element_code="login_button",
            element_name="登录按钮",
            locator_type="css",
            locator_value="#login-btn",
            role="button",
            status="active",
            is_primary=True,
        )
    )
    db_session.commit()

    monkeypatch.setattr(
        generation_context,
        "build_orchestrator_client",
        lambda: _StubOrchestratorClient(
            parse_result={
                "requirement_spec": {
                    "page": "login",
                    "priority": "P1",
                    "test_intents": [
                        {"title": "正常登录", "summary": "输入正确账号密码后登录成功", "intent_type": "functional", "priority": "P1"},
                        {"title": "异常登录", "summary": "密码错误提示", "intent_type": "negative", "priority": "P1"},
                    ],
                }
            }
        ),
    )

    counter = {"value": 0}

    def _stub_build_generated_case_payload(**kwargs: object) -> dict[str, object]:
        counter["value"] += 1
        index = counter["value"]
        current_payload = kwargs.get("payload")
        title = str(getattr(current_payload, "title", "") or f"chain-{index}").strip() or f"chain-{index}"
        case_id = f"atp-web-login-core-fn-ai-{index:04d}"
        case_file = ai_cases_root / f"{case_id}.yaml"
        case_file.write_text(
            "\n".join(
                [
                    f"id: {case_id}",
                    f"title: {title}",
                    "module: login",
                    "priority: P1",
                    "tags:",
                    "  - ai-generated",
                    "execution:",
                    "  page: login",
                    "  steps:",
                    "    - action: fill",
                    "      target: username_input",
                    "      value: qa-user",
                    "    - action: click",
                    "      target: login_button",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return {
            "message": "case generated",
            "item": {
                "case_id": case_id,
                "project": "atp",
                "path": str(case_file.resolve()),
                "yaml_content": case_file.read_text(encoding="utf-8"),
                "state": {},
            },
        }

    monkeypatch.setattr(
        workbench_generation_service,
        "build_generated_case_payload",
        _stub_build_generated_case_payload,
    )
    monkeypatch.setattr(
        workbench_runtime_service,
        "start_run",
        lambda **kwargs: {"run_id": f"run-{kwargs.get('case_id', 'unknown')}", "status": "queued"},
    )
    monkeypatch.setattr(
        workbench_runtime_service,
        "wait_run_terminal",
        lambda run_id, timeout_seconds=240: ({"run_id": run_id, "status": "passed"}, False),
    )

    response = client.post(
        "/api/workbench/full-chain/run",
        json={
            "project": "atp",
            "page": "login",
            "requirement": "用户登录能力全覆盖",
            "source": "manual",
            "max_cases": 2,
            "run_after_generate": True,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    summary = payload["summary"]
    assert int(summary["generated_case_count"]) == 2
    assert int(summary["test_step_row_count"]) >= 4
    assert int(summary["linked_ref_count"]) >= 2
    assert int(summary["executed_count"]) == 2
    assert int(summary["run_status_counts"].get("passed", 0)) == 2
    assert "test_point_store" not in payload["stages"]
    assert "persisted_test_point_count" not in summary

    step_rows = db_session.execute(select(func.count(test_case_model.TestCaseStep.id))).scalar_one()
    assert int(step_rows or 0) >= 4
    point_rows = db_session.execute(select(func.count(test_point_model.TestPoint.id))).scalar_one()
    assert int(point_rows or 0) == 0
    bound_refs = db_session.execute(
        select(func.count(page_object_model.PageObjectRef.id)).where(page_object_model.PageObjectRef.reference_type == "test_case")
    ).scalar_one()
    assert int(bound_refs or 0) >= 2


def test_full_chain_run_blocks_on_coverage_gap_when_gate_enabled(
    workbench_generation_client: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, _db_session = workbench_generation_client
    assets_root = tmp_path / "test-cases"
    ai_cases_root = assets_root / "ai-generated"
    ai_cases_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(workbench_state_store, "ASSETS_CASES_ROOT", assets_root)
    monkeypatch.setattr(workbench_state_store, "AI_CASES_ROOT", ai_cases_root)
    monkeypatch.setattr(test_case_service, "ASSETS_CASES_ROOT", assets_root)

    monkeypatch.setattr(
        generation_context,
        "build_orchestrator_client",
        lambda: _StubOrchestratorClient(
            parse_result={
                "requirement_spec": {
                    "page": "login",
                    "priority": "P1",
                    "test_intents": [
                        {"title": "正常登录", "summary": "输入正确账号密码后登录成功", "intent_type": "functional", "priority": "P1"},
                        {"title": "异常登录", "summary": "密码错误提示", "intent_type": "negative", "priority": "P1"},
                    ],
                }
            }
        ),
    )

    def _unexpected_build_generated_case_payload(**_kwargs: object) -> dict[str, object]:
        raise AssertionError("coverage gate blocked path should not generate cases")

    monkeypatch.setattr(
        workbench_generation_service,
        "build_generated_case_payload",
        _unexpected_build_generated_case_payload,
    )

    response = client.post(
        "/api/workbench/full-chain/run",
        json={
            "project": "atp",
            "page": "login",
            "requirement": "用户登录能力全覆盖",
            "source": "manual",
            "max_cases": 2,
            "combination_mode": "full",
            "coverage_profile": "normal+abnormal+boundary",
            "coverage_threshold": 1.0,
            "coverage_gate_block_on_gap": True,
            "run_after_generate": True,
        },
    )

    assert response.status_code == 422
    payload = response.json()
    detail = payload.get("detail") if isinstance(payload, dict) else {}
    detail = detail if isinstance(detail, dict) else {}
    assert detail.get("code") == "coverage_gate_blocked"
    coverage_matrix = detail.get("coverage_matrix") if isinstance(detail.get("coverage_matrix"), dict) else {}
    assert str(coverage_matrix.get("status", "")).lower() == "gap"
