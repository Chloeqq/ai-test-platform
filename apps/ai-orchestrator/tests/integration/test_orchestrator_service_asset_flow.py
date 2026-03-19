from pathlib import Path

import pytest
import yaml


pytestmark = [pytest.mark.integration]


def test_orchestrator_service_persists_generated_case_via_asset_toolkit(tmp_path: Path):
    import sys

    src_root = Path(__file__).resolve().parents[2] / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))

    from orchestrator_service import OrchestratorService

    service = OrchestratorService(repo_root=Path(__file__).resolve().parents[4])
    service.generated_cases_root = tmp_path / "assets" / "test-cases" / "ai-generated"
    service.generated_cases_root.mkdir(parents=True)

    def fake_generate_case(requirement: str, page: str):
        return {
            "version": "v4",
            "id": "TC-PRODUCT-GEN-001",
            "title": "生成商品用例",
            "module": "product",
            "priority": "P1",
            "tags": ["product"],
            "owner": "qa-team",
            "status": "automated",
            "description": "生成的商品用例",
            "requirement": [requirement],
            "data": {},
            "execution": {
                "runner": "playwright",
                "page": page,
                "variables": {},
                "steps": [
                    {"action": "login"},
                    {"action": "assert_visible", "target": "product_list_title"},
                ],
            },
        }

    service._generate_case = fake_generate_case  # type: ignore[method-assign]

    result = service.orchestrate(
        requirement="验证商品列表展示",
        page="product",
        execute=False,
    )

    saved_path = Path(result.case_path)
    assert saved_path.exists()
    assert saved_path.parent == tmp_path / "assets" / "test-cases" / "ai-generated"

    with open(saved_path, "r", encoding="utf-8") as f:
        saved_case = yaml.safe_load(f)

    assert "ai-generated" in saved_case["tags"]
    assert "product" in saved_case["tags"]
    assert result.case["id"] == "TC-PRODUCT-GEN-001"
    assert result.test_points["page"] == "product"
    assert result.test_points["points"][0]["action"] == "login"
    assert result.execution_record["status"] == "generated"
    assert result.execution_record["step_summary"]["total_steps"] == 2
    assert result.report is not None
    assert result.report["status"] == "generated"
    assert result.report["execution_record"]["status"] == "generated"
    assert result.report["request_context"]["mode"] == "generate_only"
    assert result.report["request_context"]["source"] == "manual"
    assert Path(result.report_json_path).exists()
    assert Path(result.report_markdown_path).exists()
    assert result.report_summary_path == ""


def test_orchestrator_service_builds_execution_report_after_runner_success(tmp_path: Path):
    import sys
    import subprocess

    src_root = Path(__file__).resolve().parents[2] / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))

    from orchestrator_service import OrchestratorService

    service = OrchestratorService(repo_root=Path(__file__).resolve().parents[4])
    service.generated_cases_root = tmp_path / "assets" / "test-cases" / "ai-generated"
    service.report_root = tmp_path / "reports" / "executions"
    service.runner_root = tmp_path / "runner"
    service.generated_cases_root.mkdir(parents=True)

    def fake_generate_case(requirement: str, page: str):
        return {
            "version": "v4",
            "id": "TC-PRODUCT-GEN-002",
            "title": "执行商品用例",
            "module": "product",
            "priority": "P1",
            "tags": ["product"],
            "owner": "qa-team",
            "status": "automated",
            "description": "执行用例",
            "requirement": [requirement],
            "data": {},
            "execution": {
                "runner": "playwright",
                "page": page,
                "variables": {},
                "steps": [
                    {"action": "login"},
                    {"action": "assert_visible", "target": "product_list_title"},
                ],
            },
        }

    service._generate_case = fake_generate_case  # type: ignore[method-assign]

    artifact_dir = service.runner_root / "artifacts" / "test-report-success"
    video_dir = service.runner_root / "test-results" / "videos"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    video_dir.mkdir(parents=True, exist_ok=True)

    def fake_run_case(case_id: str, case_path: Path):
        (artifact_dir / "failed.png").write_bytes(b"png")
        (artifact_dir / "page.html").write_text("<html></html>", encoding="utf-8")
        (artifact_dir / "meta.txt").write_text("URL: http://example.test", encoding="utf-8")
        (artifact_dir / "analysis.txt").write_text("Summary: none", encoding="utf-8")
        (artifact_dir / "suggestion.json").write_text('{"advice_type":"no_change"}', encoding="utf-8")
        (artifact_dir / "execution_record.json").write_text(
            '{"run_id":"TC-PRODUCT-GEN-002:2026-03-18T00:00:00+00:00","case_id":"TC-PRODUCT-GEN-002","project":"default","source":"manual","mode":"generate_and_run","status":"passed","started_at":"2026-03-18T00:00:00+00:00","finished_at":"2026-03-18T00:00:01+00:00","step_summary":{"page":"product","requirement_count":1,"total_steps":2,"action_types":["assert_visible","login"]},"evidence_index":{"total_files":6,"artifact_categories":{"screenshots":1,"html_pages":1,"meta_files":1,"analysis_files":1,"suggestion_files":1,"execution_record_files":1,"self_healing_result_files":0,"videos":0,"other_files":0},"runner_exit_code":0,"execution_requested":true}}',
            encoding="utf-8",
        )
        (artifact_dir / "self_healing_result.json").write_text(
            '{"status":"success","reason":"Patch applied and rerun succeeded.","attempts_used":1,"healed":true,"rolled_back":false,"confidence":0.81,"plan_path":"/tmp/plan.json","result_path":"/tmp/result.json"}',
            encoding="utf-8",
        )
        (video_dir / f"{case_id}.webm").write_bytes(b"webm")
        return subprocess.CompletedProcess(
            args=["pytest"],
            returncode=0,
            stdout="============================== 1 passed in 0.12s ==============================\n",
            stderr="",
        )

    service._run_case = fake_run_case  # type: ignore[method-assign]

    result = service.orchestrate(
        requirement="验证商品列表展示",
        page="product",
        execute=True,
    )

    assert result.report is not None
    assert result.report["status"] == "passed"
    assert result.execution_record["status"] == "passed"
    assert result.execution_record["evidence_index"]["total_files"] >= 1
    assert result.report["metrics"]["passed"] == 1
    assert result.report["pytest_results"]["passed"] == 1
    assert result.report["failure_reason"] == ""
    assert result.report["self_healing_enabled"] is False
    assert result.report["self_healing_attempted"] is True
    assert result.report["failure_analysis"]["risk_level"] == "low"
    assert result.report["self_healing_advice"]["suggestion_type"] == "no_change"
    assert result.report["self_healing_advice"]["safe_to_apply_manually"] is True
    assert result.report["self_healing_suggestion_preview"]["advice_type"] == "no_change"
    assert result.report["self_healing_execution_preview"]["status"] == "success"
    assert result.report["execution_record"]["status"] == "passed"
    assert result.report["execution_record"]["case_id"] == "TC-PRODUCT-GEN-002"
    assert result.report["evidence"]["execution_record_files"]
    assert result.report["request_context"]["mode"] == "generate_and_run"
    assert result.report["request_context"]["execution_requested"] is True
    assert result.report["evidence"]["screenshots"]
    assert result.report["evidence"]["analysis_files"]
    assert result.report["evidence"]["suggestion_files"]
    assert result.report["evidence"]["self_healing_result_files"]
    assert result.report["evidence"]["videos"]
    assert Path(result.report_json_path).exists()
    assert Path(result.report_markdown_path).exists()
    assert Path(result.report_summary_path).exists()


def test_orchestrator_service_builds_failure_reason_and_analysis_for_failed_run(tmp_path: Path):
    import sys
    import subprocess

    src_root = Path(__file__).resolve().parents[2] / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))

    from orchestrator_service import OrchestratorService, RunnerExecutionError

    service = OrchestratorService(repo_root=Path(__file__).resolve().parents[4])
    service.generated_cases_root = tmp_path / "assets" / "test-cases" / "ai-generated"
    service.report_root = tmp_path / "reports" / "executions"
    service.runner_root = tmp_path / "runner"
    service.generated_cases_root.mkdir(parents=True)

    def fake_generate_case(requirement: str, page: str):
        return {
            "version": "v4",
            "id": "TC-PRODUCT-GEN-003",
            "title": "失败商品用例",
            "module": "product",
            "priority": "P1",
            "tags": ["product"],
            "owner": "qa-team",
            "status": "automated",
            "description": "失败用例",
            "requirement": [requirement],
            "data": {},
            "execution": {
                "runner": "playwright",
                "page": page,
                "variables": {},
                "steps": [
                    {"action": "login"},
                    {"action": "assert_visible", "target": "product_list_title"},
                ],
            },
        }

    service._generate_case = fake_generate_case  # type: ignore[method-assign]

    artifact_dir = service.runner_root / "artifacts" / "test-report-failure"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    def fake_run_case(case_id: str, case_path: Path):
        (artifact_dir / "failed.png").write_bytes(b"png")
        (artifact_dir / "analysis.txt").write_text("Summary: assertion", encoding="utf-8")
        (artifact_dir / "suggestion.json").write_text('{"advice_type":"assertion_update"}', encoding="utf-8")
        (artifact_dir / "execution_record.json").write_text(
            '{"run_id":"TC-PRODUCT-GEN-003:2026-03-18T00:00:00+00:00","case_id":"TC-PRODUCT-GEN-003","project":"default","source":"manual","mode":"generate_and_run","status":"failed","started_at":"2026-03-18T00:00:00+00:00","finished_at":"2026-03-18T00:00:01+00:00","step_summary":{"page":"product","requirement_count":1,"total_steps":2,"action_types":["assert_visible","login"]},"evidence_index":{"total_files":3,"artifact_categories":{"screenshots":1,"html_pages":0,"meta_files":0,"analysis_files":1,"suggestion_files":1,"execution_record_files":1,"self_healing_result_files":0,"videos":0,"other_files":0},"runner_exit_code":1,"execution_requested":true}}',
            encoding="utf-8",
        )
        (artifact_dir / "self_healing_result.json").write_text(
            '{"status":"rollback","reason":"Patch applied but rerun failed; rollback completed.","attempts_used":1,"healed":false,"rolled_back":true,"confidence":0.84,"plan_path":"/tmp/plan.json","result_path":"/tmp/result.json"}',
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            args=["pytest"],
            returncode=1,
            stdout=(
                "collected 1 item\n"
                "tests/test_yaml_ai_generated.py F\n"
                "=================================== FAILURES ===================================\n"
                "E AssertionError: expected product list title to be visible\n"
                "============================== 1 failed in 0.34s ==============================\n"
            ),
            stderr="",
        )

    service._run_case = fake_run_case  # type: ignore[method-assign]
    service._run_failure_analysis_agent = lambda payload: {  # type: ignore[method-assign]
        "summary": "UI assertion failed on product page.",
        "failure_category": "assertion",
        "likely_cause": "The expected product list title was not rendered.",
        "risk_level": "high",
        "recommended_action": "Check whether the product list page loaded correctly and whether the assertion target changed.",
        "confidence": 0.84,
        "evidence_used": ["stdout", "screenshots"],
    }
    service._run_self_healing_advisor_agent = lambda payload: {  # type: ignore[method-assign]
        "summary": "Recommend manually checking the assertion target.",
        "suggestion_type": "assertion_update",
        "suggested_changes": [
            "Check whether product_list_title is still the correct stable assertion target.",
            "If the page changed intentionally, update the assertion target manually.",
        ],
        "rationale": "The failure is assertion-related and should be reviewed manually before changing YAML.",
        "confidence": 0.79,
        "safe_to_apply_manually": True,
    }

    with pytest.raises(RunnerExecutionError) as exc_info:
        service.orchestrate(
            requirement="验证商品列表展示",
            page="product",
            execute=True,
        )

    details = exc_info.value.details
    assert details["report"]["status"] == "failed"
    assert details["report"]["pytest_results"]["failed"] == 1
    assert details["report"]["failure_reason"] == "expected product list title to be visible"
    assert details["report"]["failure_analysis"]["failure_category"] == "assertion"
    assert details["report"]["self_healing_advice"]["suggestion_type"] == "assertion_update"
    assert details["report"]["self_healing_advice"]["safe_to_apply_manually"] is True
    assert details["report"]["self_healing_suggestion_preview"]["advice_type"] == "assertion_update"
    assert details["report"]["self_healing_suggestion_preview"]["summary"]
    assert details["report"]["self_healing_execution_preview"]["status"] == "rollback"
    assert details["report"]["self_healing_enabled"] is False
    assert details["report"]["self_healing_attempted"] is True
    assert details["report"]["request_context"]["mode"] == "generate_and_run"
    assert details["report"]["evidence"]["analysis_files"]
    assert details["report"]["evidence"]["suggestion_files"]
    assert details["report"]["evidence"]["self_healing_result_files"]
    assert Path(details["report_json_path"]).exists()
    assert Path(details["report_markdown_path"]).exists()
    assert Path(details["report_summary_path"]).exists()


def test_orchestrator_service_reads_latest_and_named_reports(tmp_path: Path):
    import sys

    src_root = Path(__file__).resolve().parents[2] / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))

    from orchestrator_service import OrchestratorService

    service = OrchestratorService(repo_root=Path(__file__).resolve().parents[4])
    service.report_root = tmp_path / "reports" / "executions"
    service.runner_root = tmp_path / "runner"
    service.report_root.mkdir(parents=True)
    (service.runner_root / "artifacts").mkdir(parents=True)
    (service.runner_root / "artifacts" / "report_summary.txt").write_text(
        "\n".join(
            [
                "Management Summary:",
                "- Total Failed Cases: 3",
                "- Environment Failures: 1",
                "- Business Failures: 2",
                "- High Risk Failures: 1",
                "- Cases With Actionable Self-Healing Advice: 2",
                "",
                "Per-Case Details:",
                "1. Case: TC-LOGIN-001",
                "   Failure Category: authentication",
                "   Actionable Suggestion: no",
                "   Suggestion Advice Type: no_change",
                "   Suggestion Target: -",
                "",
                "2. Case: TC-PRODUCT-001",
                "   Failure Category: assertion",
                "   Actionable Suggestion: yes",
                "   Suggestion Advice Type: assertion_update",
                "   Suggestion Target: product_list_title",
                "",
                "3. Case: TC-PRODUCT-002",
                "   Failure Category: locator",
                "   Actionable Suggestion: yes",
                "   Suggestion Advice Type: locator_update",
                "   Suggestion Target: product_table",
                "",
            ]
        ),
        encoding="utf-8",
    )

    older = service.report_root / "TC-OLDER.report.json"
    older.write_text('{"case_id":"TC-OLDER","status":"passed","summary":"older"}', encoding="utf-8")
    (service.report_root / "TC-OLDER.report.md").write_text("# older\n", encoding="utf-8")

    latest = service.report_root / "TC-LATEST.report.json"
    latest.write_text('{"case_id":"TC-LATEST","status":"failed","summary":"latest"}', encoding="utf-8")
    (service.report_root / "TC-LATEST.report.md").write_text("# latest\n", encoding="utf-8")

    named_report = service.get_report("TC-LATEST")
    latest_report = service.get_latest_report()

    assert named_report["report"]["case_id"] == "TC-LATEST"
    assert named_report["report"]["self_healing_suggestion_preview"] == {}
    assert named_report["report_summary_preview"]["total_failed_cases"] == 3
    assert named_report["report_summary_preview"]["actionable_self_healing_cases"] == 2
    assert named_report["report_summary_preview"]["environment_failure_cases"] == ["TC-LOGIN-001"]
    assert named_report["report_summary_preview"]["actionable_self_healing_case_details"][0]["case_id"] == "TC-PRODUCT-001"
    assert latest_report["report"]["case_id"] == "TC-LATEST"
    assert latest_report["report_markdown_path"].endswith("TC-LATEST.report.md")
    assert latest_report["report_summary_preview"]["environment_failures"] == 1
    assert latest_report["report_summary_preview"]["actionable_self_healing_case_details"][1]["target"] == "product_table"


def test_orchestrator_service_previews_self_healing_advice_without_mutating_assets(tmp_path: Path):
    import sys

    src_root = Path(__file__).resolve().parents[2] / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))

    from orchestrator_service import OrchestratorService

    service = OrchestratorService(repo_root=Path(__file__).resolve().parents[4])
    service._run_self_healing_advisor_agent = lambda payload: {  # type: ignore[method-assign]
        "summary": f"Preview for {payload['page']}",
        "suggestion_type": "wait_strategy",
        "suggested_changes": [
            f"Prefer a stable wait target from: {', '.join(payload['available_targets'])}"
        ],
        "rationale": "This is a read-only preview.",
        "confidence": 0.71,
        "safe_to_apply_manually": True,
    }

    advice = service.preview_self_healing_advice(
        page="product",
        case={
            "id": "TC-PRODUCT-GEN-900",
            "execution": {
                "page": "product",
                "steps": [{"action": "login"}],
            },
        },
        failure_reason="Timeout waiting for product_list_title",
        failure_analysis={
            "summary": "The product page did not become ready in time.",
            "failure_category": "timeout",
            "likely_cause": "The target was not ready.",
            "risk_level": "medium",
            "recommended_action": "Review wait strategy manually.",
            "confidence": 0.7,
            "evidence_used": ["stdout"],
        },
    )

    assert advice["suggestion_type"] == "wait_strategy"
    assert advice["safe_to_apply_manually"] is True
    assert "product_list_title" in advice["suggested_changes"][0]
