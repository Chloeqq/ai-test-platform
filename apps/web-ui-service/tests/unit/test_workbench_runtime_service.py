from pathlib import Path

from app.services import workbench_runtime_service


def test_replace_allure_results_dir_updates_existing_alluredir() -> None:
    command = ["python", "-m", "pytest", "--alluredir", "/tmp/old-results"]

    updated = workbench_runtime_service.replace_allure_results_dir(command, Path("/tmp/run-results"))

    assert updated == ["python", "-m", "pytest", "--alluredir", "/tmp/run-results"]
    assert command == ["python", "-m", "pytest", "--alluredir", "/tmp/old-results"]


def test_replace_allure_results_dir_appends_when_missing() -> None:
    command = ["python", "-m", "pytest"]

    updated = workbench_runtime_service.replace_allure_results_dir(command, Path("/tmp/run-results"))

    assert updated == ["python", "-m", "pytest", "--alluredir", "/tmp/run-results"]


def test_build_run_command_visible_mode_records_video_and_uses_short_observation_defaults() -> None:
    command, env = workbench_runtime_service.build_run_command(
        Path("/tmp/case.yaml"),
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


def test_build_run_command_batch_mode_disables_visible_delay_and_video() -> None:
    command, env = workbench_runtime_service.build_run_command(
        Path("/tmp/case.yaml"),
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


def test_build_run_command_uses_mall_admin_login_default_base_url() -> None:
    _command, env = workbench_runtime_service.build_run_command(
        Path("/tmp/case.yaml"),
        get_python_bin_fn=lambda: "python",
        repo_root=Path("/repo"),
        allure_results_root=Path("/tmp/allure-results"),
        environ={},
    )

    assert env["BASE_URL"] == "http://localhost:5174/#/login"


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
