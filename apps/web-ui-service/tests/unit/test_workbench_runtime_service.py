import os
from pathlib import Path

import pytest
import yaml

from app.services import workbench_runtime_service


def _write_minimal_case_yaml(case_dir: Path, *, page_url: str = "http://host.docker.internal:5174/#/login") -> Path:
    """写入包含 page_url 的最小合法用例 YAML，返回文件路径。"""
    case_dir.mkdir(parents=True, exist_ok=True)
    case_path = case_dir / "case.yaml"
    payload = {
        "version": "v1.1",
        "id": "test-case-0001",
        "execution": {
            "page": "login",
            "page_url": page_url,
            "steps": [],
        },
    }
    case_path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    return case_path


def test_replace_allure_results_dir_updates_existing_alluredir() -> None:
    command = ["python", "-m", "pytest", "--alluredir", "/tmp/old-results"]

    updated = workbench_runtime_service.replace_allure_results_dir(command, Path("/tmp/run-results"))

    assert updated == ["python", "-m", "pytest", "--alluredir", "/tmp/run-results"]
    assert command == ["python", "-m", "pytest", "--alluredir", "/tmp/old-results"]


def test_replace_allure_results_dir_appends_when_missing() -> None:
    command = ["python", "-m", "pytest"]

    updated = workbench_runtime_service.replace_allure_results_dir(command, Path("/tmp/run-results"))

    assert updated == ["python", "-m", "pytest", "--alluredir", "/tmp/run-results"]


def test_build_run_command_visible_mode_records_video_and_uses_short_observation_defaults(tmp_path: Path) -> None:
    case_path = _write_minimal_case_yaml(tmp_path)
    command, env = workbench_runtime_service.build_run_command(
        case_path,
        get_python_bin_fn=lambda: "python",
        repo_root=Path("/repo"),
        allure_results_root=Path("/tmp/allure-results"),
        environ={"RECORDER_DESKTOP_ENABLED": "true", "DISPLAY": ":99"},
    )

    assert "--headed" in command
    assert command[command.index("--slowmo") + 1] == "80"
    assert env["WORKBENCH_RECORD_VIDEO"] == "1"
    assert env["WORKBENCH_VISIBLE_STEP_DELAY_MS"] == "100"
    assert env["WORKBENCH_VISIBLE_HOLD_MS"] == "800"
    assert env["WORKBENCH_RUN_TIMEOUT_SECONDS"] == "120"


def test_build_run_command_batch_mode_disables_visible_delay_and_video(tmp_path: Path) -> None:
    case_path = _write_minimal_case_yaml(tmp_path)
    command, env = workbench_runtime_service.build_run_command(
        case_path,
        get_python_bin_fn=lambda: "python",
        repo_root=Path("/repo"),
        allure_results_root=Path("/tmp/allure-results"),
        environ={
            "WORKBENCH_BATCH_RUN": "true",
            "RECORDER_DESKTOP_ENABLED": "true",
            "DISPLAY": ":99",
        },
    )

    assert "--headed" not in command
    assert "--slowmo" not in command
    assert env["WORKBENCH_RECORD_VIDEO"] == "0"
    assert env["WORKBENCH_VISIBLE_STEP_DELAY_MS"] == "0"
    assert env["WORKBENCH_VISIBLE_HOLD_MS"] == "0"


def test_build_run_command_rejects_case_yaml_without_page_url(tmp_path: Path) -> None:
    # 文件存在但 page_url 为空 — 应明确报错
    case_path = tmp_path / "case.yaml"
    case_path.write_text(
        yaml.safe_dump({"version": "v1.1", "execution": {"page": "login", "steps": []}}),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="page_url"):
        workbench_runtime_service.build_run_command(
            case_path,
            get_python_bin_fn=lambda: "python",
            repo_root=Path("/repo"),
            allure_results_root=Path("/tmp/allure-results"),
            environ={},
        )


def test_build_run_command_rejects_missing_case_yaml() -> None:
    # 文件不存在 — 应明确报错
    with pytest.raises(RuntimeError, match="无法读取用例 YAML"):
        workbench_runtime_service.build_run_command(
            Path("/tmp/nonexistent-case.yaml"),
            get_python_bin_fn=lambda: "python",
            repo_root=Path("/repo"),
            allure_results_root=Path("/tmp/allure-results"),
            environ={},
        )


def test_build_run_command_allows_runtime_cases_root(tmp_path: Path) -> None:
    case_path = _write_minimal_case_yaml(tmp_path / "web-ui/runs/runtime-cases/run-001")

    _command, env = workbench_runtime_service.build_run_command(
        case_path,
        get_python_bin_fn=lambda: "python",
        repo_root=Path("/repo"),
        allure_results_root=Path("/tmp/allure-results"),
        environ={},
    )

    allowed_roots = env["TEST_CASE_ALLOWED_ROOTS"].split(os.pathsep)
    assert str(case_path.resolve().parent.parent) in allowed_roots
    assert str(case_path.resolve().parent) not in allowed_roots


def test_build_run_command_does_not_allow_arbitrary_case_parent(tmp_path: Path) -> None:
    case_path = _write_minimal_case_yaml(tmp_path / "outside")

    _command, env = workbench_runtime_service.build_run_command(
        case_path,
        get_python_bin_fn=lambda: "python",
        repo_root=Path("/repo"),
        allure_results_root=Path("/tmp/allure-results"),
        environ={},
    )

    allowed_roots = env["TEST_CASE_ALLOWED_ROOTS"].split(os.pathsep)
    assert str(case_path.resolve().parent) not in allowed_roots
    assert allowed_roots == [str((Path("/repo") / "assets" / "test-cases" / "ai-generated").resolve())]


def test_materialize_runtime_case_yaml_writes_isolated_runtime_file(tmp_path: Path) -> None:
    runtime_case_path = workbench_runtime_service.materialize_runtime_case_yaml(
        run_id="run-001",
        case_id="mall-web-login-auth-fn-ai-0001",
        script_code="version: '1.0'\nname: login",
        runs_dir=tmp_path,
    )

    assert runtime_case_path == tmp_path / "runtime-cases" / "run-001" / "mall-web-login-auth-fn-ai-0001.yaml"
    assert runtime_case_path.read_text(encoding="utf-8") == "version: '1.0'\nname: login\n"


def test_build_runner_termination_failure_marks_timeout_as_runner_failure() -> None:
    failure = workbench_runtime_service.build_runner_termination_failure(
        run_id="run-1",
        case_id="TC-LOGIN-0001",
        project="mall",
        case_path="/tmp/case.yaml",
        return_code=-9,
        timeout_seconds=90,
        timed_out=True,
    )

    assert failure["failure_type"] == "runner_timeout"
    assert failure["analysis"]["failure_source"] == "runner"
    assert "90s" in failure["summary"]


def test_build_fallback_execution_record_preserves_identity_and_timeout_metadata() -> None:
    record = workbench_runtime_service.build_fallback_execution_record(
        {
            "run_id": "run-1",
            "case_id": "TC-LOGIN-0001",
            "project": "mall",
            "source": "manual",
            "mode": "generate_and_run",
            "execution_record": {"step_summary": {"page": "login"}},
        },
        status_value="failed",
        return_code=-9,
        started_at="2026-05-13T06:25:22+00:00",
        finished_at="2026-05-13T06:26:52+00:00",
        artifacts_dir=Path("/tmp/run-artifacts"),
        videos_dir=Path("/tmp/run-videos"),
        timeout_seconds=90,
        timed_out=True,
    )

    assert record["run_id"] == "run-1"
    assert record["case_id"] == "TC-LOGIN-0001"
    assert record["status"] == "failed"
    assert record["evidence_index"]["runner_exit_code"] == -9
    assert record["evidence_index"]["runner_timed_out"] is True
    assert record["metadata"]["failure_type"] == "runner_timeout"


def test_update_runtime_run_with_retry_swallows_final_database_failure() -> None:
    calls = 0

    def failing_update(_run_id: str, _updates: dict) -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("database in recovery")

    workbench_runtime_service.update_runtime_run_with_retry(
        "run-1",
        {"status": "failed"},
        update_runtime_run=failing_update,
        attempts=2,
        retry_delay_seconds=0,
    )

    assert calls == 2
