from __future__ import annotations

import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
import importlib.util
from pathlib import Path
import shutil
from time import time

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy", reason="sqlalchemy is required for e2e smoke DB seeding")
select = sqlalchemy.select


def _start_login_demo_server(repo_root: Path) -> tuple[HTTPServer, threading.Thread, str]:
    fixture_dir = repo_root / "runners" / "web-playwright-python" / "fixtures" / "login-demo"
    if not fixture_dir.is_dir():
        raise RuntimeError(f"missing fixture dir: {fixture_dir}")

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(fixture_dir), **kwargs)

        def log_message(self, _format, *_args):
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}/#/login"
    return server, thread, base_url


def _seed_login_contract_elements() -> None:
    from app.core.database import SessionLocal
    from app.models.page_object import PageElement, PageObject

    with SessionLocal() as db:
        page_object = db.execute(
            select(PageObject).where(
                PageObject.project_code == "atp",
                PageObject.client == "web",
                PageObject.page_code == "login",
            )
        ).scalar_one_or_none()
        if page_object is None:
            raise RuntimeError("atp/web/login page object not found in DB")
        existing_codes = {
            str(code).strip()
            for code in db.execute(
                select(PageElement.element_code).where(PageElement.page_object_id == int(page_object.id))
            ).scalars().all()
            if str(code).strip()
        }
        additions = [
            ("login_menu", "css", "#btnLogin", ""),
            ("login_list_title", "css", "#navHome", ""),
        ]
        for element_code, locator_type, locator_value, role in additions:
            if element_code in existing_codes:
                continue
            db.add(
                PageElement(
                    page_object_id=int(page_object.id),
                    element_code=element_code,
                    element_name=element_code,
                    locator_type=locator_type,
                    locator_value=locator_value,
                    backup_locator="",
                    health_status=1,
                    version=1,
                    role=role,
                    status="active",
                    is_primary=True,
                    owner="pytest",
                )
            )
        db.commit()


def _clean_runner_artifacts(repo_root: Path) -> None:
    runner_root = repo_root / "runners" / "web-playwright-python"
    for path in (runner_root / "artifacts", runner_root / "test-results" / "videos"):
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)


@pytest.mark.integration
@pytest.mark.e2e
def test_orchestrate_execute_true_runs_real_runner_and_emits_full_artifacts(monkeypatch: pytest.MonkeyPatch):
    repo_root = Path(__file__).resolve().parents[4]
    src_root = Path(__file__).resolve().parents[2] / "src"
    db_path = repo_root / "apps" / "web-ui-service" / "dev.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    app_spec = importlib.util.spec_from_file_location("orchestrator_app_module", src_root / "app.py")
    if app_spec is None or app_spec.loader is None:
        raise RuntimeError("failed to load orchestrator app module spec")
    app_module = importlib.util.module_from_spec(app_spec)
    app_spec.loader.exec_module(app_module)
    create_app = app_module.create_app
    OrchestratorService = app_module.OrchestratorService

    server, thread, base_url = _start_login_demo_server(repo_root)
    try:
        monkeypatch.setenv("BASE_URL", base_url)
        monkeypatch.setenv("TEST_USERNAME", "demo")
        monkeypatch.setenv("TEST_PASSWORD", "demo123")
        monkeypatch.setenv("TEST_DESIGN_MODE", "deterministic")
        deterministic_sequence = int(time()) % 9000 + 1000
        deterministic_case_id = f"ATP-WEB-LOGIN-CORE-FN-AI-{deterministic_sequence:04d}"
        monkeypatch.setenv("TEST_DESIGN_DETERMINISTIC_CASE_ID", deterministic_case_id)
        _clean_runner_artifacts(repo_root)
        _seed_login_contract_elements()

        service = OrchestratorService(repo_root=repo_root)
        app = create_app(service=service)
        client = app.test_client()

        response = client.post(
            "/orchestrate",
            json={
                "requirement": "验证页面入口元素可操作并可见",
                "page": "login",
                "execute": True,
                "source": "manual",
                "runner": "playwright",
            },
        )

        payload = response.get_json() or {}
        if response.status_code != 201:
            details = ((payload.get("error") or {}).get("details") or {})
            runner_stderr = str(details.get("runner_stderr") or "")
            runner_stdout = str(details.get("runner_stdout") or "")
            sandbox_launch_denied = (
                "MachPortRendezvousServer" in runner_stdout
                and "Permission denied (1100)" in runner_stdout
            )
            if sandbox_launch_denied:
                pytest.skip("Playwright Chromium launch is blocked by host sandbox permissions")
        assert response.status_code == 201, payload
        assert payload.get("execution_requested") is True
        assert payload.get("runner_exit_code") == 0, payload

        execution_record = payload.get("execution_record") or {}
        assert execution_record.get("status") == "passed"
        assert execution_record.get("version") == "ExecutionRecordV1"
        evidence_index = execution_record.get("evidence_index") or {}
        artifact_categories = evidence_index.get("artifact_categories") or {}
        assert artifact_categories.get("execution_record_files", 0) >= 1
        assert evidence_index.get("execution_requested") is True

        report = payload.get("report") or {}
        assert report.get("status") == "passed"
        assert report.get("execution_record", {}).get("status") == "passed"
        assert report.get("execution_record", {}).get("version") == "ExecutionRecordV1"

        report_json_path = Path(str(payload.get("report_json_path", "")).strip())
        report_markdown_path = Path(str(payload.get("report_markdown_path", "")).strip())
        report_summary_path = Path(str(payload.get("report_summary_path", "")).strip())
        case_path = Path(str(payload.get("case_path", "")).strip())

        assert report_json_path.exists()
        assert report_markdown_path.exists()
        assert report_summary_path.exists()
        assert case_path.exists()

    finally:
        server.shutdown()
        thread.join(timeout=5)
