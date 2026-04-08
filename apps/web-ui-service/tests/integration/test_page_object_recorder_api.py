from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
import app.models.page_object  # noqa: F401
from app.models.page_object import PageObjectRecorderSession, PageObjectRef
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
    assert int(stop_resp.json()["ingested_count"]) >= 2
    assert int(stop_resp.json()["page_element_total_count"]) >= int(stop_resp.json()["ingested_count"])
    assert str(stop_resp.json()["first_element_code"] or "").strip()
    assert stop_resp.json()["session"]["status"] == "stopped"
    assert stop_resp.json()["page_object_action"] == "created"
    assert stop_resp.json()["page_object"]["page_code"] == "login-page"
    steps = stop_resp.json()["steps"]
    assert len(steps) >= 3
    assert [item["action"] for item in steps[:3]] == ["click", "click", "fill"]
    assert all(item.get("element_code") for item in steps[:3])
    candidates = stop_resp.json()["element_candidates"]
    assert len(candidates) >= 2
    assert all("score" in item for item in candidates)
    assert all(item.get("recommended_action") in {"ingest", "review", "skip"} for item in candidates)
    assert any(bool(item.get("ingested")) for item in candidates)
    assert stop_resp.json()["verification"]["requested"] is False

    page_resp = client.get(
        "/api/page-objects/login-page",
        params={"project_code": "atp", "client": "web"},
    )
    assert page_resp.status_code == 200
    assert int(page_resp.json()["item"]["element_count"]) >= 2
    assert page_resp.json()["item"]["page_url"] == "/login"
    assert page_resp.json()["item"]["precondition_state"] == ""

    recorder_resp = client.get(f"/api/page-objects/recorder/sessions/{session_id}")
    assert recorder_resp.status_code == 200
    assert int(recorder_resp.json()["item"]["recorded_step_count"]) >= 3

    stop_again_resp = client.post(
        f"/api/page-objects/recorder/sessions/{session_id}/stop",
        json={"ingest_to_page_object": True, "changed_by": "qa-admin"},
    )
    assert stop_again_resp.status_code == 200
    assert int(stop_again_resp.json()["ingested_count"]) == 0
    assert int(stop_again_resp.json()["page_element_total_count"]) >= 2
    assert str(stop_again_resp.json()["first_element_code"] or "").strip()
    assert len(stop_again_resp.json()["steps"]) >= 3
    assert len(stop_again_resp.json()["element_candidates"]) >= 2
    assert stop_again_resp.json()["verification"]["requested"] is False
    assert stop_again_resp.json()["page_object_action"] == "already_stopped"


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
    locator_values = {item["locator_value"] for item in elements_resp.json()["items"]}
    assert "本月销售总额" in locator_values
    assert "100000" not in locator_values
    assert "+10%" not in locator_values
    assert "本月订单总数10000+10%同比上月本周订单总数1000" not in locator_values
    candidate_map = {
        str(item["locator_value"]): item
        for item in candidates
    }
    assert candidate_map["100000"]["recommended_action"] == "skip"
    assert "dynamic_text" in candidate_map["100000"]["risk_tags"]
    assert candidate_map["+10%"]["recommended_action"] == "skip"
    assert "dynamic_text" in candidate_map["+10%"]["risk_tags"]


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
    assert int(stop_resp.json()["ingested_count"]) >= 2

    draft_resp = client.post(
        f"/api/page-objects/recorder/sessions/{session_id}/cases/draft",
        json={"creator": "qa-admin", "link_page_refs": True},
    )
    assert draft_resp.status_code == 201
    item = draft_resp.json()["item"]
    assert str(item["case_id"]).strip()
    assert int(item["case_step_count"]) >= 2
    assert int(item["linked_ref_count"]) >= 1

    created_case = db_session.query(TestCase).filter_by(case_id=str(item["case_id"])).one_or_none()
    assert created_case is not None
    assert str(created_case.page_code) == "home"
    assert str(created_case.source_ref).startswith("recorder:")
    assert isinstance(created_case.test_steps, list)
    assert len(created_case.test_steps) >= 2

    refs = db_session.query(PageObjectRef).filter_by(reference_type="test_case", reference_key=str(item["case_id"])).all()
    assert len(refs) >= 1


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
