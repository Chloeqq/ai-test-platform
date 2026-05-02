from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
import re

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
import app.models.page_object  # noqa: F401
from app.models.page_object import PageObjectCandidateElement, PageObjectCandidateGroup, PageObjectRecorderSession, PageObjectRef
from app.models.test_case import TestCase
import app.models.test_case  # noqa: F401
import app.models.test_project as test_project_model
import app.models.test_project  # noqa: F401
import app.models.workbench_state  # noqa: F401
from app.routers.page_objects import router as page_objects_router
from app.routers.page_objects_recorder import router as page_objects_recorder_router
from app.schemas.page_object import PageObjectCreate
from app.services import page_object_recorder_service, page_object_service


@pytest.fixture()
def page_object_recorder_client(tmp_path: Path) -> Iterator[tuple[TestClient, Session]]:
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
    Base.metadata.create_all(bind=engine)
    session = testing_session()
    session.add(
        test_project_model.TestProject(
            project_code="atp",
            project_name="ATP",
            description="integration test project",
            created_by="pytest",
            status="active",
        )
    )
    session.commit()

    app = FastAPI()
    app.include_router(page_objects_router)
    app.include_router(page_objects_recorder_router)

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        yield client, session
    finally:
        client.close()
        session.close()


def test_page_object_recorder_session_lifecycle_with_ingest(
    page_object_recorder_client: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, _db = page_object_recorder_client

    fake_pid = 43210

    def fake_start_codegen_process(url: str, script_path: Path) -> int:
        assert str(url).startswith("http")
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(
            "\n".join(
                [
                    'page.get_by_role("button", name="登录").click()',
                    'page.get_by_test_id("login-submit").click()',
                    'page.locator("#username").fill("admin")',
                ]
            ),
            encoding="utf-8",
        )
        return fake_pid

    def fake_stop_codegen_process(process_pid: int | None) -> None:
        assert int(process_pid or 0) == fake_pid

    monkeypatch.setattr(page_object_recorder_service, "_start_codegen_process", fake_start_codegen_process)
    monkeypatch.setattr(page_object_recorder_service, "_stop_codegen_process", fake_stop_codegen_process)
    monkeypatch.setattr(page_object_recorder_service, "_RECORDER_ROOT", tmp_path)

    create_resp = client.post(
        "/api/page-objects/recorder/sessions",
        json={
            "project_code": "atp",
            "client": "web",
            "page_code": "login-page",
            "page_name": "登录页",
            "url": "http://127.0.0.1:8013/login",
            "started_by": "qa-admin",
        },
    )
    assert create_resp.status_code == 201
    session_item = create_resp.json()["item"]
    assert session_item["status"] == "active"
    assert int(session_item["recorded_step_count"]) >= 3
    session_id = str(session_item["session_id"])

    heartbeat_resp = client.post(
        f"/api/page-objects/recorder/sessions/{session_id}/heartbeat",
        json={"heartbeat_by": "qa-admin"},
    )
    assert heartbeat_resp.status_code == 200
    assert heartbeat_resp.json()["item"]["status"] == "active"

    stop_resp = client.post(
        f"/api/page-objects/recorder/sessions/{session_id}/stop",
        json={"ingest_to_page_object": True, "changed_by": "qa-admin"},
    )
    assert stop_resp.status_code == 200
    assert int(stop_resp.json()["ingested_count"]) == 0
    assert int(stop_resp.json()["page_element_total_count"]) == 0
    assert str(stop_resp.json()["first_element_code"] or "") == ""
    assert stop_resp.json()["session"]["status"] == "stopped"
    assert stop_resp.json()["page_object_action"] == "created"
    assert stop_resp.json()["page_object"]["page_code"] == "login-page"
    steps = stop_resp.json()["steps"]
    assert len(steps) >= 3
    assert [item["action"] for item in steps[:3]] == ["click", "click", "fill"]
    assert not any(item.get("element_code") for item in steps[:3])
    candidates = stop_resp.json()["element_candidates"]
    assert len(candidates) >= 2
    assert all("score" in item for item in candidates)
    assert all(item.get("recommended_action") in {"ingest", "review", "skip"} for item in candidates)
    assert not any(bool(item.get("ingested")) for item in candidates)
    assert stop_resp.json()["verification"]["requested"] is False

    page_resp = client.get(
        "/api/page-objects/login-page",
        params={"project_code": "atp", "client": "web"},
    )
    assert page_resp.status_code == 200
    assert int(page_resp.json()["item"]["element_count"]) == 0
    assert page_resp.json()["item"]["page_url"] == "/login"
    assert page_resp.json()["item"]["precondition_state"] == ""
    elements_resp = client.get(
        "/api/page-objects/login-page/elements",
        params={"project_code": "atp", "client": "web"},
    )
    assert elements_resp.status_code == 200
    assert elements_resp.json()["items"] == []

    recorder_resp = client.get(f"/api/page-objects/recorder/sessions/{session_id}")
    assert recorder_resp.status_code == 200
    assert int(recorder_resp.json()["item"]["recorded_step_count"]) >= 3

    stop_again_resp = client.post(
        f"/api/page-objects/recorder/sessions/{session_id}/stop",
        json={"ingest_to_page_object": True, "changed_by": "qa-admin"},
    )
    assert stop_again_resp.status_code == 200
    assert int(stop_again_resp.json()["ingested_count"]) == 0
    assert int(stop_again_resp.json()["page_element_total_count"]) == 0
    assert str(stop_again_resp.json()["first_element_code"] or "") == ""
    assert len(stop_again_resp.json()["steps"]) >= 3
    assert len(stop_again_resp.json()["element_candidates"]) >= 2
    assert not any(bool(item.get("ingested")) for item in stop_again_resp.json()["element_candidates"])
    assert stop_again_resp.json()["verification"]["requested"] is False
    assert stop_again_resp.json()["page_object_action"] == "already_stopped"


def test_recorder_stop_defaults_to_candidate_governance_without_formal_elements(
    page_object_recorder_client: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, db_session = page_object_recorder_client

    def fake_start_codegen_process(_url: str, script_path: Path) -> int:
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(
            "\n".join(
                [
                    'page.get_by_test_id("login-submit").click()',
                    'page.get_by_placeholder("请输入账号").fill("admin")',
                    'page.get_by_text("100000").click()',
                ]
            ),
            encoding="utf-8",
        )
        return 24680

    monkeypatch.setattr(page_object_recorder_service, "_start_codegen_process", fake_start_codegen_process)
    monkeypatch.setattr(page_object_recorder_service, "_stop_codegen_process", lambda _pid: None)
    monkeypatch.setattr(page_object_recorder_service, "_RECORDER_ROOT", tmp_path)

    create_resp = client.post(
        "/api/page-objects/recorder/sessions",
        json={
            "project_code": "atp",
            "client": "web",
            "page_code": "candidate-login",
            "page_name": "登录页",
            "url": "http://127.0.0.1:8013/login",
            "started_by": "qa-admin",
        },
    )
    assert create_resp.status_code == 201
    session_id = str(create_resp.json()["item"]["session_id"])

    stop_resp = client.post(
        f"/api/page-objects/recorder/sessions/{session_id}/stop",
        json={"changed_by": "qa-admin"},
    )
    assert stop_resp.status_code == 200
    payload = stop_resp.json()
    assert payload["session"]["status"] == "stopped"
    assert payload["page_object_action"] == "created"
    assert payload["page_match_status"] == "matched"
    assert int(payload["ingested_count"]) == 0
    assert int(payload["page_element_total_count"]) == 0
    assert int(payload["candidate_count"]) >= 3
    assert int(payload["candidate_group_count"]) >= 3
    assert int(payload["promotable_count"]) >= 1

    elements_resp = client.get(
        "/api/page-objects/candidate-login/elements",
        params={"project_code": "atp", "client": "web"},
    )
    assert elements_resp.status_code == 200
    assert elements_resp.json()["items"] == []

    candidate_rows = db_session.query(PageObjectCandidateElement).filter_by(session_id=session_id).all()
    assert len(candidate_rows) >= 3
    assert {str(row.candidate_status) for row in candidate_rows} == {"pending"}
    assert any(str(row.raw_locator_type) == "data-testid" for row in candidate_rows)
    placeholder_row = next(row for row in candidate_rows if str(row.raw_locator_type) == "placeholder")
    assert str(placeholder_row.proposed_element_code or "") == "account_input"
    assert not re.search(r"_[0-9a-f]{8}$", str(placeholder_row.proposed_element_code or ""))
    group_rows = db_session.query(PageObjectCandidateGroup).filter_by(page_code="candidate-login").all()
    assert len(group_rows) >= 3
    assert {str(row.promotion_status) for row in group_rows} == {"pending"}

    candidate_rows[0].candidate_status = "rejected"
    candidate_rows[0].review_note = "manual reject marker"
    candidate_rows[1].candidate_status = "reviewed"
    candidate_rows[1].review_note = "manual reviewed marker"
    db_session.add_all([candidate_rows[0], candidate_rows[1]])
    db_session.commit()

    stop_again_resp = client.post(
        f"/api/page-objects/recorder/sessions/{session_id}/stop",
        json={"changed_by": "qa-admin"},
    )
    assert stop_again_resp.status_code == 200
    assert stop_again_resp.json()["page_object_action"] == "already_stopped"
    assert int(stop_again_resp.json()["candidate_count"]) == len(candidate_rows)
    returned_statuses = {str(item.get("candidate_status") or "") for item in stop_again_resp.json()["element_candidates"]}
    assert "rejected" in returned_statuses
    assert "reviewed" in returned_statuses


def test_recorder_stop_ignores_legacy_direct_ingest_flag(
    page_object_recorder_client: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, _db = page_object_recorder_client

    def fake_start_codegen_process(_url: str, script_path: Path) -> int:
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text('page.get_by_test_id("login-submit").click()', encoding="utf-8")
        return 13579

    create_calls = 0

    def fake_create_page_element(*_args: object, **_kwargs: object) -> dict[str, object]:
        nonlocal create_calls
        create_calls += 1
        raise HTTPException(status_code=400, detail={"code": "locator_type_invalid", "message": "bad locator"})

    monkeypatch.setattr(page_object_recorder_service, "_start_codegen_process", fake_start_codegen_process)
    monkeypatch.setattr(page_object_recorder_service, "_stop_codegen_process", lambda _pid: None)
    monkeypatch.setattr(page_object_recorder_service, "_RECORDER_ROOT", tmp_path)
    monkeypatch.setattr(page_object_recorder_service.page_object_service, "create_page_element", fake_create_page_element)

    create_resp = client.post(
        "/api/page-objects/recorder/sessions",
        json={
            "project_code": "atp",
            "client": "web",
            "page_code": "recorder-error",
            "page_name": "录制错误页",
            "url": "http://127.0.0.1:8013/login",
            "started_by": "qa-admin",
        },
    )
    assert create_resp.status_code == 201
    session_id = str(create_resp.json()["item"]["session_id"])

    stop_resp = client.post(
        f"/api/page-objects/recorder/sessions/{session_id}/stop",
        json={"ingest_to_page_object": True, "changed_by": "qa-admin"},
    )
    assert stop_resp.status_code == 200
    assert stop_resp.json()["ingested_count"] == 0
    assert create_calls == 0


def test_recorder_candidates_are_enhanced_by_source_semantics(
    page_object_recorder_client: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, db_session = page_object_recorder_client
    source_root = tmp_path / "mall-admin-web"
    source_root.mkdir()
    (source_root / "order.vue").write_text(
        """
        <template>
          <el-form-item label="订单编号" prop="orderSn">
            <el-input placeholder="请输入编号" />
          </el-form-item>
          <el-table-column label="编号" prop="orderSn" />
        </template>
        """,
        encoding="utf-8",
    )

    def fake_start_codegen_process(_url: str, script_path: Path) -> int:
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(
            "\n".join(
                [
                    'page.get_by_placeholder("请输入编号").fill("20260430001")',
                    'page.get_by_text("编号").click()',
                ]
            ),
            encoding="utf-8",
        )
        return 24681

    monkeypatch.setenv("PAGE_OBJECT_SOURCE_ROOTS_ATP", str(source_root))
    monkeypatch.setattr(page_object_recorder_service, "_start_codegen_process", fake_start_codegen_process)
    monkeypatch.setattr(page_object_recorder_service, "_stop_codegen_process", lambda _pid: None)
    monkeypatch.setattr(page_object_recorder_service, "_RECORDER_ROOT", tmp_path / "recorder")

    create_resp = client.post(
        "/api/page-objects/recorder/sessions",
        json={
            "project_code": "atp",
            "client": "web",
            "page_code": "order",
            "page_name": "订单列表",
            "url": "http://127.0.0.1:8013/#/oms/order",
            "started_by": "qa-admin",
        },
    )
    assert create_resp.status_code == 201
    session_id = str(create_resp.json()["item"]["session_id"])

    stop_resp = client.post(
        f"/api/page-objects/recorder/sessions/{session_id}/stop",
        json={"changed_by": "qa-admin"},
    )
    assert stop_resp.status_code == 200

    rows = db_session.query(PageObjectCandidateElement).filter_by(session_id=session_id).all()
    by_locator = {str(row.raw_locator_value): row for row in rows}
    assert str(by_locator["请输入编号"].proposed_element_code) == "order_sn_input"
    assert str(by_locator["请输入编号"].proposed_element_name) == "订单编号输入框"
    assert str(by_locator["请输入编号"].business_type_guess) == "input"
    assert str(by_locator["编号"].proposed_element_code) == "order_sn_column"
    assert str(by_locator["编号"].proposed_element_name) == "编号列"

    group = db_session.query(PageObjectCandidateGroup).filter_by(group_key=str(by_locator["编号"].group_key)).one()
    assert str(group.business_domain_guess) == "table"


def test_recorder_filters_dynamic_text_locators_and_derives_login_precondition(
    page_object_recorder_client: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, _db = page_object_recorder_client

    def fake_start_codegen_process(_url: str, script_path: Path) -> int:
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(
            "\n".join(
                [
                    'page.get_by_text("本月销售总额").click()',
                    'page.get_by_text("100000").click()',
                    'page.get_by_text("+10%").click()',
                    'page.get_by_text("本月订单总数10000+10%同比上月本周订单总数1000").click()',
                    'page.get_by_role("button", name="刷新").click()',
                ]
            ),
            encoding="utf-8",
        )
        return 67890

    monkeypatch.setattr(page_object_recorder_service, "_start_codegen_process", fake_start_codegen_process)
    monkeypatch.setattr(page_object_recorder_service, "_stop_codegen_process", lambda _pid: None)
    monkeypatch.setattr(page_object_recorder_service, "_RECORDER_ROOT", tmp_path)

    create_resp = client.post(
        "/api/page-objects/recorder/sessions",
        json={
            "project_code": "atp",
            "client": "web",
            "page_code": "home",
            "page_name": "首页",
            "url": "http://127.0.0.1:8013/#/login",
            "started_by": "qa-admin",
        },
    )
    assert create_resp.status_code == 201
    session_id = str(create_resp.json()["item"]["session_id"])

    stop_resp = client.post(
        f"/api/page-objects/recorder/sessions/{session_id}/stop",
        json={"ingest_to_page_object": True, "changed_by": "qa-admin"},
    )
    assert stop_resp.status_code == 200
    candidates = stop_resp.json()["element_candidates"]
    assert len(candidates) >= 4

    page_resp = client.get(
        "/api/page-objects/home",
        params={"project_code": "atp", "client": "web"},
    )
    assert page_resp.status_code == 200
    page_item = page_resp.json()["item"]
    assert page_item["page_url"] == ""
    assert page_item["precondition_state"] == "依赖登录页完成认证后进入"

    elements_resp = client.get(
        "/api/page-objects/home/elements",
        params={"project_code": "atp", "client": "web"},
    )
    assert elements_resp.status_code == 200
    assert elements_resp.json()["items"] == []
    candidate_map = {
        str(item["locator_value"]): item
        for item in candidates
    }
    assert "本月销售总额" in candidate_map
    assert candidate_map["100000"]["recommended_action"] == "skip"
    assert "dynamic_text" in candidate_map["100000"]["risk_tags"]
    assert candidate_map["+10%"]["recommended_action"] == "skip"
    assert "dynamic_text" in candidate_map["+10%"]["risk_tags"]


def test_recorder_normalizes_metric_text_with_trailing_number(
    page_object_recorder_client: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, _db = page_object_recorder_client

    def fake_start_codegen_process(_url: str, script_path: Path) -> int:
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(
            "\n".join(
                [
                    'page.get_by_text("本周销售总额12345").click()',
                    'page.get_by_text("100000").click()',
                ]
            ),
            encoding="utf-8",
        )
        return 13579

    monkeypatch.setattr(page_object_recorder_service, "_start_codegen_process", fake_start_codegen_process)
    monkeypatch.setattr(page_object_recorder_service, "_stop_codegen_process", lambda _pid: None)
    monkeypatch.setattr(page_object_recorder_service, "_RECORDER_ROOT", tmp_path)

    create_resp = client.post(
        "/api/page-objects/recorder/sessions",
        json={
            "project_code": "atp",
            "client": "web",
            "page_code": "home",
            "page_name": "首页",
            "url": "http://127.0.0.1:8013/#/home",
            "started_by": "qa-admin",
        },
    )
    assert create_resp.status_code == 201
    session_id = str(create_resp.json()["item"]["session_id"])

    stop_resp = client.post(
        f"/api/page-objects/recorder/sessions/{session_id}/stop",
        json={"ingest_to_page_object": True, "changed_by": "qa-admin"},
    )
    assert stop_resp.status_code == 200

    locator_values = {str(item.get("locator_value") or "") for item in stop_resp.json()["element_candidates"]}
    assert "本周销售总额" in locator_values
    assert "本周销售总额12345" not in locator_values
    candidate_map = {str(item.get("locator_value") or ""): item for item in stop_resp.json()["element_candidates"]}
    assert candidate_map["100000"]["recommended_action"] == "skip"


def test_recorder_verification_result_is_reflected_in_candidates(
    page_object_recorder_client: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, _db = page_object_recorder_client

    def fake_start_codegen_process(_url: str, script_path: Path) -> int:
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(
            "\n".join(
                [
                    'page.get_by_role("button", name="提交").click()',
                    'page.get_by_text("首页").click()',
                ]
            ),
            encoding="utf-8",
        )
        return 22334

    def fake_probe(_url: str, _locators, *, timeout_ms: int):
        assert int(timeout_ms) == 1200
        return (
            {
                ("role", "提交", "button"): {
                    "status": "ok",
                    "match_count": 1,
                    "visible": True,
                    "interactable": True,
                },
                ("text", "首页", ""): {
                    "status": "ambiguous",
                    "match_count": 3,
                    "visible": None,
                    "interactable": None,
                },
            },
            "ok",
        )

    monkeypatch.setattr(page_object_recorder_service, "_start_codegen_process", fake_start_codegen_process)
    monkeypatch.setattr(page_object_recorder_service, "_stop_codegen_process", lambda _pid: None)
    monkeypatch.setattr(page_object_recorder_service, "_probe_availability", fake_probe)
    monkeypatch.setattr(page_object_recorder_service, "_RECORDER_ROOT", tmp_path)

    create_resp = client.post(
        "/api/page-objects/recorder/sessions",
        json={
            "project_code": "atp",
            "client": "web",
            "page_code": "demo",
            "page_name": "演示页",
            "url": "http://127.0.0.1:8013/demo",
            "started_by": "qa-admin",
        },
    )
    assert create_resp.status_code == 201
    session_id = str(create_resp.json()["item"]["session_id"])

    stop_resp = client.post(
        f"/api/page-objects/recorder/sessions/{session_id}/stop",
        json={"ingest_to_page_object": True, "verify_locators": True, "verify_timeout_ms": 1200, "changed_by": "qa-admin"},
    )
    assert stop_resp.status_code == 200
    assert stop_resp.json()["verification"]["requested"] is True
    assert stop_resp.json()["verification"]["status"] == "ok"
    candidates = stop_resp.json()["element_candidates"]
    by_key = {
        (str(item["locator_type"]), str(item["locator_value"]), str(item.get("role", ""))): item
        for item in candidates
    }
    role_item = by_key[("role", "提交", "button")]
    assert role_item["probe"]["status"] == "ok"
    assert role_item["probe"]["match_count"] == 1
    assert role_item["recommended_action"] in {"ingest", "review"}
    text_item = by_key[("text", "首页", "")]
    assert text_item["probe"]["status"] == "ambiguous"
    assert "probe_ambiguous" in text_item["risk_tags"]
    assert text_item["recommended_action"] == "skip"


def test_recorder_session_stop_marks_existing_page_object_when_identity_exists(
    page_object_recorder_client: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, db_session = page_object_recorder_client
    db_session.add(
        test_project_model.TestProject(
            project_code="mall",
            project_name="Mall",
            description="",
            status="active",
            created_by="qa-admin",
        )
    )
    db_session.commit()
    page_object_service.create_page_object(
        db_session,
        PageObjectCreate(
            project_code="mall",
            client="web",
            page_code="login",
            page_name="登录页",
            created_by="qa-admin",
        ),
    )

    def fake_start_codegen_process(_url: str, script_path: Path) -> int:
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text('page.get_by_role("button", name="登录").click()', encoding="utf-8")
        return 12345

    monkeypatch.setattr(page_object_recorder_service, "_start_codegen_process", fake_start_codegen_process)
    monkeypatch.setattr(page_object_recorder_service, "_stop_codegen_process", lambda _pid: None)
    monkeypatch.setattr(page_object_recorder_service, "_RECORDER_ROOT", tmp_path)

    create_resp = client.post(
        "/api/page-objects/recorder/sessions",
        json={
            "project_code": "mall",
            "client": "web",
            "page_code": "login",
            "page_name": "登录页",
            "url": "http://127.0.0.1:8013/login",
            "started_by": "qa-admin",
        },
    )
    assert create_resp.status_code == 201
    session_id = str(create_resp.json()["item"]["session_id"])

    stop_resp = client.post(
        f"/api/page-objects/recorder/sessions/{session_id}/stop",
        json={"ingest_to_page_object": True, "changed_by": "qa-admin"},
    )
    assert stop_resp.status_code == 200
    assert stop_resp.json()["page_object_action"] == "existing"
    assert stop_resp.json()["page_object"]["page_code"] == "login"


def test_recorder_session_can_generate_test_case_draft_and_link_refs(
    page_object_recorder_client: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, db_session = page_object_recorder_client

    def fake_start_codegen_process(_url: str, script_path: Path) -> int:
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(
            "\n".join(
                [
                    'page.get_by_role("button", name="提交").click()',
                    'page.get_by_test_id("submit-btn").click()',
                    'page.locator("#username").fill("qa-user")',
                ]
            ),
            encoding="utf-8",
        )
        return 55667

    monkeypatch.setattr(page_object_recorder_service, "_start_codegen_process", fake_start_codegen_process)
    monkeypatch.setattr(page_object_recorder_service, "_stop_codegen_process", lambda _pid: None)
    monkeypatch.setattr(page_object_recorder_service, "_RECORDER_ROOT", tmp_path)

    create_resp = client.post(
        "/api/page-objects/recorder/sessions",
        json={
            "project_code": "atp",
            "client": "web",
            "page_code": "home",
            "page_name": "首页",
            "url": "http://127.0.0.1:8013/#/home",
            "started_by": "qa-admin",
        },
    )
    assert create_resp.status_code == 201
    session_id = str(create_resp.json()["item"]["session_id"])

    stop_resp = client.post(
        f"/api/page-objects/recorder/sessions/{session_id}/stop",
        json={"ingest_to_page_object": True, "changed_by": "qa-admin"},
    )
    assert stop_resp.status_code == 200
    assert int(stop_resp.json()["ingested_count"]) == 0

    draft_resp = client.post(
        f"/api/page-objects/recorder/sessions/{session_id}/cases/draft",
        json={"creator": "qa-admin", "link_page_refs": True},
    )
    assert draft_resp.status_code == 201
    item = draft_resp.json()["item"]
    assert str(item["case_id"]).strip()
    assert int(item["case_step_count"]) >= 2
    assert int(item["linked_ref_count"]) == 0

    created_case = db_session.query(TestCase).filter_by(case_id=str(item["case_id"])).one_or_none()
    assert created_case is not None
    assert str(created_case.page_code) == "home"
    assert str(created_case.source_ref).startswith("recorder:")
    assert isinstance(created_case.test_steps, list)
    assert len(created_case.test_steps) >= 2

    refs = db_session.query(PageObjectRef).filter_by(reference_type="test_case", reference_key=str(item["case_id"])).all()
    assert refs == []


def test_list_recorder_sessions_returns_history_summary(
    page_object_recorder_client: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, _db = page_object_recorder_client

    def fake_start_codegen_process(_url: str, script_path: Path) -> int:
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(
            "\n".join(
                [
                    'page.get_by_role("button", name="登录").click()',
                    'page.locator("#username").fill("tester")',
                ]
            ),
            encoding="utf-8",
        )
        return 11223

    monkeypatch.setattr(page_object_recorder_service, "_start_codegen_process", fake_start_codegen_process)
    monkeypatch.setattr(page_object_recorder_service, "_stop_codegen_process", lambda _pid: None)
    monkeypatch.setattr(page_object_recorder_service, "_RECORDER_ROOT", tmp_path)

    create_a_resp = client.post(
        "/api/page-objects/recorder/sessions",
        json={
            "project_code": "atp",
            "client": "web",
            "page_code": "history-page",
            "page_name": "历史页",
            "url": "http://127.0.0.1:8013/history",
            "started_by": "qa-admin",
        },
    )
    assert create_a_resp.status_code == 201
    session_a = str(create_a_resp.json()["item"]["session_id"])

    stop_a_resp = client.post(
        f"/api/page-objects/recorder/sessions/{session_a}/stop",
        json={"ingest_to_page_object": False, "changed_by": "qa-admin"},
    )
    assert stop_a_resp.status_code == 200

    create_b_resp = client.post(
        "/api/page-objects/recorder/sessions",
        json={
            "project_code": "atp",
            "client": "web",
            "page_code": "history-page",
            "page_name": "历史页",
            "url": "http://127.0.0.1:8013/history2",
            "started_by": "qa-admin",
        },
    )
    assert create_b_resp.status_code == 201

    list_resp = client.get(
        "/api/page-objects/recorder/sessions",
        params={"project_code": "atp", "client": "web", "page_code": "history-page"},
    )
    assert list_resp.status_code == 200
    payload = list_resp.json()
    assert int(payload["total"]) >= 2
    items = payload["items"]
    assert len(items) >= 2
    assert all("recorded_steps" not in item for item in items)
    assert all("recorded_step_count" in item for item in items)
    stopped_item = next(item for item in items if str(item.get("session_id") or "") == session_a)
    assert int(stopped_item["candidate_count"]) >= 2
    assert int(stopped_item["candidate_summary"]["candidate_count"]) == int(stopped_item["candidate_count"])
    statuses = {str(item.get("status") or "") for item in items}
    assert "stopped" in statuses
    assert "active" in statuses

    stopped_resp = client.get(
        "/api/page-objects/recorder/sessions",
        params={"project_code": "atp", "client": "web", "page_code": "history-page", "status": "stopped"},
    )
    assert stopped_resp.status_code == 200
    stopped_items = stopped_resp.json()["items"]
    assert len(stopped_items) >= 1
    assert all(str(item["status"]) == "stopped" for item in stopped_items)


def test_get_recorder_session_playback_returns_steps_and_script(
    page_object_recorder_client: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, _db = page_object_recorder_client

    def fake_start_codegen_process(_url: str, script_path: Path) -> int:
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(
            "\n".join(
                [
                    'page.get_by_role("button", name="提交").click()',
                    'page.locator("#username").fill("qa-user")',
                ]
            ),
            encoding="utf-8",
        )
        return 55678

    monkeypatch.setattr(page_object_recorder_service, "_start_codegen_process", fake_start_codegen_process)
    monkeypatch.setattr(page_object_recorder_service, "_stop_codegen_process", lambda _pid: None)
    monkeypatch.setattr(page_object_recorder_service, "_RECORDER_ROOT", tmp_path)

    create_resp = client.post(
        "/api/page-objects/recorder/sessions",
        json={
            "project_code": "atp",
            "client": "web",
            "page_code": "playback-page",
            "page_name": "回放页",
            "url": "http://127.0.0.1:8013/playback",
            "started_by": "qa-admin",
        },
    )
    assert create_resp.status_code == 201
    session_id = str(create_resp.json()["item"]["session_id"])

    stop_resp = client.post(
        f"/api/page-objects/recorder/sessions/{session_id}/stop",
        json={"ingest_to_page_object": False, "changed_by": "qa-admin"},
    )
    assert stop_resp.status_code == 200

    playback_resp = client.get(f"/api/page-objects/recorder/sessions/{session_id}/playback")
    assert playback_resp.status_code == 200
    playback_item = playback_resp.json()["item"]
    session = playback_item["session"]
    assert str(session["session_id"]) == session_id
    assert int(playback_item["recorded_step_count"]) >= 2
    assert len(playback_item["recorded_steps"]) >= 2
    assert bool(playback_item["can_replay"]) is True
    script_code = str(playback_item["script_code"] or "")
    assert "get_by_role" in script_code
    assert "fill" in script_code


def test_replay_recorder_session_executes_persisted_script(
    page_object_recorder_client: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, _db = page_object_recorder_client
    executed: dict[str, object] = {}

    def fake_start_codegen_process(_url: str, script_path: Path) -> int:
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text('page.get_by_role("button", name="提交").click()', encoding="utf-8")
        return 55679

    def fake_run_recorder_script(script_path: Path, *, timeout_seconds: int) -> dict[str, object]:
        executed["script_path"] = str(script_path)
        executed["timeout_seconds"] = timeout_seconds
        return {
            "status": "passed",
            "exit_code": 0,
            "stdout_tail": "ok",
            "stderr_tail": "",
            "started_at": "2026-04-27T00:00:00+00:00",
            "finished_at": "2026-04-27T00:00:01+00:00",
            "duration_seconds": 1,
            "timed_out": False,
        }

    monkeypatch.setattr(page_object_recorder_service, "_start_codegen_process", fake_start_codegen_process)
    monkeypatch.setattr(page_object_recorder_service, "_stop_codegen_process", lambda _pid: None)
    monkeypatch.setattr(page_object_recorder_service, "_run_recorder_script", fake_run_recorder_script)
    monkeypatch.setattr(page_object_recorder_service, "_RECORDER_ROOT", tmp_path)

    create_resp = client.post(
        "/api/page-objects/recorder/sessions",
        json={
            "project_code": "atp",
            "client": "web",
            "page_code": "replay-page",
            "page_name": "真实回放页",
            "url": "http://127.0.0.1:8013/replay",
            "started_by": "qa-admin",
        },
    )
    assert create_resp.status_code == 201
    session_id = str(create_resp.json()["item"]["session_id"])
    stop_resp = client.post(
        f"/api/page-objects/recorder/sessions/{session_id}/stop",
        json={"ingest_to_page_object": False, "changed_by": "qa-admin"},
    )
    assert stop_resp.status_code == 200

    replay_resp = client.post(
        f"/api/page-objects/recorder/sessions/{session_id}/replay",
        json={"timeout_seconds": 30},
    )
    assert replay_resp.status_code == 200
    replay_item = replay_resp.json()["item"]
    assert replay_item["status"] == "passed"
    assert int(replay_item["exit_code"]) == 0
    assert int(replay_item["recorded_step_count"]) >= 1
    assert str(executed["script_path"]).endswith(".codegen.py")
    assert int(executed["timeout_seconds"]) == 30


def test_replay_recorder_session_blocks_active_session(
    page_object_recorder_client: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, _db = page_object_recorder_client

    def fake_start_codegen_process(_url: str, script_path: Path) -> int:
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text('page.get_by_role("button", name="提交").click()', encoding="utf-8")
        return 55680

    monkeypatch.setattr(page_object_recorder_service, "_start_codegen_process", fake_start_codegen_process)
    monkeypatch.setattr(page_object_recorder_service, "_RECORDER_ROOT", tmp_path)

    create_resp = client.post(
        "/api/page-objects/recorder/sessions",
        json={
            "project_code": "atp",
            "client": "web",
            "page_code": "active-replay-page",
            "page_name": "未停止回放页",
            "url": "http://127.0.0.1:8013/replay",
            "started_by": "qa-admin",
        },
    )
    assert create_resp.status_code == 201
    session_id = str(create_resp.json()["item"]["session_id"])

    replay_resp = client.post(f"/api/page-objects/recorder/sessions/{session_id}/replay", json={})
    assert replay_resp.status_code == 409
    assert "先停止" in str(replay_resp.json().get("detail", ""))


def test_recorder_session_create_blocked_when_project_inactive(
    page_object_recorder_client: tuple[TestClient, Session],
) -> None:
    client, db_session = page_object_recorder_client
    db_session.add(
        test_project_model.TestProject(
            project_code="mall",
            project_name="Mall",
            description="",
            status="inactive",
            created_by="qa-admin",
        )
    )
    db_session.commit()

    create_resp = client.post(
        "/api/page-objects/recorder/sessions",
        json={
            "project_code": "mall",
            "client": "web",
            "page_code": "mall-login",
            "page_name": "商城登录页",
            "url": "http://127.0.0.1:8013/login",
            "started_by": "qa-admin",
        },
    )
    assert create_resp.status_code == 409
    assert "project is inactive" in str(create_resp.json().get("detail", "")).lower()


def test_resolve_playwright_command_prefers_current_python(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(page_object_recorder_service.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(page_object_recorder_service.shutil, "which", lambda _name: "/tmp/fake-playwright")
    monkeypatch.setattr(page_object_recorder_service.sys, "executable", "/tmp/venv/bin/python")

    assert page_object_recorder_service._resolve_playwright_command() == [
        "/tmp/venv/bin/python",
        "-m",
        "playwright",
    ]


def test_resolve_playwright_command_raises_clear_error_when_runtime_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(page_object_recorder_service.importlib.util, "find_spec", lambda name: None)
    monkeypatch.setattr(page_object_recorder_service.shutil, "which", lambda _name: None)
    monkeypatch.setattr(page_object_recorder_service.sys, "executable", "/tmp/missing-python")

    with pytest.raises(HTTPException) as exc_info:
        page_object_recorder_service._resolve_playwright_command()

    assert int(exc_info.value.status_code) == 503
    assert "/tmp/missing-python -m pip install -r requirements-dev.txt" in str(exc_info.value.detail)


def test_start_codegen_process_raises_clear_error_when_display_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        page_object_recorder_service,
        "_resolve_playwright_command",
        lambda: [
            str(page_object_recorder_service.sys.executable),
            "-c",
            "import sys;sys.stderr.write('Missing X server or $DISPLAY\\n');sys.exit(1)",
        ],
    )

    script_path = tmp_path / "rec_launch_fail.codegen.py"
    with pytest.raises(HTTPException) as exc_info:
        page_object_recorder_service._start_codegen_process("http://127.0.0.1:8013/login", script_path)

    assert int(exc_info.value.status_code) == 503
    assert "缺少图形桌面" in str(exc_info.value.detail)


def test_cleanup_orphan_recorder_artifacts_endpoint(
    page_object_recorder_client: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, db_session = page_object_recorder_client
    monkeypatch.setattr(page_object_recorder_service, "_RECORDER_ROOT", tmp_path)

    kept_script = tmp_path / "rec_kept0001.codegen.py"
    kept_steps = tmp_path / "rec_kept0001.codegen.steps.json"
    kept_script.write_text("# kept", encoding="utf-8")
    kept_steps.write_text("[]", encoding="utf-8")
    db_session.add(
        PageObjectRecorderSession(
            session_id="rec_kept0001",
            project_code="atp",
            client="web",
            page_code="home",
            page_name="首页",
            url="http://127.0.0.1:8013/#/home",
            status="stopped",
            process_pid=None,
            script_path=str(kept_script.resolve()),
            started_by="qa-admin",
        )
    )
    db_session.commit()

    orphan_script = tmp_path / "rec_orphan0001.codegen.py"
    orphan_steps = tmp_path / "rec_orphan0001.codegen.steps.json"
    orphan_script.write_text("# orphan", encoding="utf-8")
    orphan_steps.write_text("[]", encoding="utf-8")
    steps_only_orphan = tmp_path / "rec_orphan0002.codegen.steps.json"
    steps_only_orphan.write_text("[]", encoding="utf-8")

    cleanup_resp = client.post("/api/page-objects/recorder/artifacts/cleanup", json={})
    assert cleanup_resp.status_code == 200
    item = cleanup_resp.json()["item"]
    assert int(item["orphan_file_count"]) == 2
    assert int(item["cleaned_file_count"]) == 3
    assert not orphan_script.exists()
    assert not orphan_steps.exists()
    assert not steps_only_orphan.exists()
    assert kept_script.exists()
    assert kept_steps.exists()


def test_batch_delete_recorder_sessions_physically_removes_sessions_candidates_and_artifacts(
    page_object_recorder_client: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, db_session = page_object_recorder_client
    monkeypatch.setattr(page_object_recorder_service, "_RECORDER_ROOT", tmp_path)

    page_object_service.create_page_object(
        db_session,
        PageObjectCreate(
            project_code="atp",
            client="web",
            page_code="recorder-delete",
            page_name="录制删除页",
        ),
    )
    script_path = tmp_path / "rec_delete.codegen.py"
    steps_path = script_path.with_suffix(".steps.json")
    stderr_path = script_path.with_name("rec_delete.codegen.stderr.log")
    script_path.write_text('page.get_by_role("button", name="保存").click()', encoding="utf-8")
    steps_path.write_text("[]", encoding="utf-8")
    stderr_path.write_text("stderr", encoding="utf-8")
    db_session.add_all(
        [
            PageObjectRecorderSession(
                session_id="rec-delete-1",
                project_code="atp",
                client="web",
                page_code="recorder-delete",
                page_name="录制删除页",
                url="http://127.0.0.1:8013/demo",
                status="stopped",
                script_path=str(script_path.resolve()),
                started_by="qa-admin",
            ),
            PageObjectCandidateGroup(
                project_code="atp",
                client="web",
                page_code="recorder-delete",
                group_key="role:save",
                candidate_count=1,
                session_count=1,
                promotion_status="pending",
            ),
            PageObjectCandidateElement(
                project_code="atp",
                client="web",
                page_code="recorder-delete",
                session_id="rec-delete-1",
                candidate_key="cand-rec-delete",
                group_key="role:save",
                raw_locator_type="role",
                raw_locator_value="保存",
                quality_score=80,
            ),
        ]
    )
    db_session.commit()

    delete_resp = client.post(
        "/api/page-objects/recorder/sessions/batch/delete",
        params={"project_code": "atp", "client": "web"},
        json={"session_ids": ["rec-delete-1"], "delete_artifacts": True},
    )
    assert delete_resp.status_code == 200
    item = delete_resp.json()["item"]
    assert int(item["deleted_session_count"]) == 1
    assert int(item["deleted_candidate_count"]) == 1
    assert int(item["deleted_artifact_count"]) == 3
    assert db_session.query(PageObjectRecorderSession).filter_by(session_id="rec-delete-1").count() == 0
    assert db_session.query(PageObjectCandidateElement).filter_by(candidate_key="cand-rec-delete").count() == 0
    assert db_session.query(PageObjectCandidateGroup).filter_by(group_key="role:save").count() == 0
    assert not script_path.exists()
    assert not steps_path.exists()
    assert not stderr_path.exists()
