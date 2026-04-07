from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
import app.models.test_case as test_case_model
import app.models.test_project  # noqa: F401
import app.models.workbench_state  # noqa: F401
from app.routers import legacy_workbench
from app.routers.workbench_generation import router as workbench_generation_router
from app.services import test_case_service, workbench_generation_service


@pytest.fixture()
def workbench_generation_client() -> tuple[TestClient, Session]:
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
    app.include_router(workbench_generation_router)

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

    monkeypatch.setattr(legacy_workbench, "ASSETS_CASES_ROOT", assets_root)
    monkeypatch.setattr(legacy_workbench, "AI_CASES_ROOT", ai_cases_root)
    monkeypatch.setattr(legacy_workbench, "_sync_stage_a_workbench_state", lambda: None)
    monkeypatch.setattr(legacy_workbench, "_ensure_dirs", lambda: None)
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

    monkeypatch.setattr(legacy_workbench, "ASSETS_CASES_ROOT", assets_root)
    monkeypatch.setattr(legacy_workbench, "AI_CASES_ROOT", ai_cases_root)
    monkeypatch.setattr(legacy_workbench, "_sync_stage_a_workbench_state", lambda: None)
    monkeypatch.setattr(legacy_workbench, "_ensure_dirs", lambda: None)
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
    assert int(saved_count or 0) == 2
