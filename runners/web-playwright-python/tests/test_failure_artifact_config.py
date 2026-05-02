import importlib.util
import os
from pathlib import Path

import pytest


pytestmark = [pytest.mark.contract]


CONFTST_PATH = Path(__file__).resolve().parents[1] / "conftest.py"
SPEC = importlib.util.spec_from_file_location("web_playwright_python_conftest", CONFTST_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.fixture(autouse=True)
def clear_auth_state():
    yield


@pytest.fixture(autouse=True)
def capture_failure_artifacts():
    yield


def test_resolve_artifacts_dir_defaults_under_runner(monkeypatch):
    monkeypatch.delenv("PLAYWRIGHT_ARTIFACTS_DIR", raising=False)

    artifacts_dir = MODULE.resolve_artifacts_dir()

    assert artifacts_dir.name == "artifacts"
    assert artifacts_dir.exists()


def test_resolve_video_dir_supports_relative_override(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PLAYWRIGHT_VIDEO_DIR", "custom-videos")

    video_dir = MODULE.resolve_video_dir()

    assert video_dir.name == "custom-videos"
    assert video_dir.exists()


def test_sanitize_artifact_name_preserves_unique_node_shape():
    sanitized = MODULE.sanitize_artifact_name(
        "tests/test_yaml_ai_generated.py::test_yaml_ai_generated[Verify Product Search Function]"
    )

    assert "tests_test_yaml_ai_generated_py" in sanitized
    assert "__test_yaml_ai_generated" in sanitized
    assert "[Verify_Product_Search_Function]" in sanitized


def test_extract_failure_message_prefers_longreprtext():
    class FakeReport:
        longreprtext = "AssertionError: product title not visible"

    message = MODULE.extract_failure_message(FakeReport())

    assert message == "AssertionError: product title not visible"


def test_build_failure_analysis_payload_includes_error_html_and_url(tmp_path: Path):
    screenshot_path = tmp_path / "failed.png"
    html_path = tmp_path / "page.html"
    meta_path = tmp_path / "meta.txt"

    payload = MODULE.build_failure_analysis_payload(
        error_message="AssertionError: product title not visible",
        page_html="<html><body>商品列表</body></html>",
        current_url="http://example.test/product",
        page_title="商品列表",
        screenshot_path=screenshot_path,
        html_path=html_path,
        meta_path=meta_path,
    )

    assert payload["error"] == "AssertionError: product title not visible"
    assert payload["current_url"] == "http://example.test/product"
    assert "商品列表" in payload["page_html"]
    assert payload["report"]["evidence"]["screenshots"] == [str(screenshot_path)]


def test_build_failure_analysis_payload_includes_failed_element_context(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TEST_PROJECT", "mall")
    payload = MODULE.build_failure_analysis_payload(
        error_message="Timeout waiting for locator",
        page_html="<html></html>",
        current_url="http://example.test/product",
        page_title="商品列表",
        screenshot_path=tmp_path / "failed.png",
        html_path=tmp_path / "page.html",
        meta_path=tmp_path / "meta.txt",
        failure_context={
            "failed_step": {
                "step_index": 2,
                "page_code": "product",
                "action": "click",
                "target": "product_name_input",
                "selector": "[data-testid='product-name']",
                "locator_type": "testid",
                "intent_id": "intent-01",
            }
        },
    )

    assert payload["failed_step"]["element_code"] == "product_name_input"
    assert payload["element_impact"]["project_code"] == "mall"
    assert payload["element_impact"]["page_code"] == "product"
    assert payload["element_impact"]["governance_href"] == (
        "/assets/page-objects/product/elements/product_name_input?project=mall"
    )


def test_normalize_failure_context_prefers_case_project_over_env(monkeypatch):
    monkeypatch.setenv("TEST_PROJECT", "mall")

    context = MODULE.normalize_failure_context(
        {
            "project_code": "atp",
            "failed_step": {
                "step_index": 1,
                "page_code": "profile",
                "target": "profile_title",
                "locator_type": "testid",
            },
        }
    )

    assert context["element_impact"]["project_code"] == "atp"
    assert context["element_impact"]["governance_href"].endswith("profile_title?project=atp")


def test_resolve_project_code_from_request_prefers_test_case_project(monkeypatch):
    monkeypatch.setenv("TEST_PROJECT", "mall")

    class FakeCallSpec:
        params = {"test_case": {"id": "case-01", "project_code": "atp"}}

    class FakeNode:
        callspec = FakeCallSpec()

    assert MODULE.resolve_project_code_from_request(FakeNode()) == "atp"


def test_build_execution_record_uses_test_case_project(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TEST_PROJECT", "mall")

    class FakeCallSpec:
        params = {"test_case": {"id": "case-01", "project_code": "atp", "execution": {"steps": []}}}

    class FakeNode:
        nodeid = "tests/test_demo.py::test_demo[case-01]"
        callspec = FakeCallSpec()

    record = MODULE.build_execution_record(
        request=FakeNode(),
        case_dir=tmp_path,
        status="passed",
        started_at="2026-05-01T00:00:00+00:00",
        finished_at="2026-05-01T00:00:01+00:00",
        duration_seconds=1.0,
        runner_exit_code=0,
    )

    assert record["project"] == "atp"


def test_render_meta_text_includes_core_fields(tmp_path: Path):
    text = MODULE.render_meta_text(
        nodeid="tests/test_yaml_ai_generated.py::test_yaml_ai_generated[case]",
        captured_at="2026-03-17T12:00:00+00:00",
        current_url="http://example.test/product",
        page_title="商品列表",
        screenshot_path=tmp_path / "failed.png",
        html_path=tmp_path / "page.html",
        video_path=tmp_path / "video.webm",
        suggestion_path=tmp_path / "suggestion.json",
    )

    assert "NodeID: tests/test_yaml_ai_generated.py::test_yaml_ai_generated[case]" in text
    assert "URL: http://example.test/product" in text
    assert "Title: 商品列表" in text
    assert "Video: " in text
    assert "Suggestion: " in text


def test_render_analysis_text_outputs_human_readable_summary():
    text = MODULE.render_analysis_text(
        {
            "summary": "UI assertion failed on product page.",
            "failure_category": "assertion",
            "likely_cause": "The expected product title was not visible.",
            "risk_level": "high",
            "recommended_action": "Check the product page locator.",
            "confidence": 0.82,
            "failed_step": {"page_code": "product", "element_code": "product_name_input"},
            "element_impact": {"governance_href": "/assets/page-objects/product/elements/product_name_input?project=mall"},
            "evidence_used": ["error", "page_html", "current_url"],
        }
    )

    assert "Summary: UI assertion failed on product page." in text
    assert "Failure Category: assertion" in text
    assert "Element Impact: " in text
    assert "Evidence Used: error, page_html, current_url" in text


def test_render_suggestion_text_outputs_human_readable_summary():
    text = MODULE.render_suggestion_text(
        {
            "summary": "仅建议人工检查现有 target。",
            "advice_type": "locator_update",
            "target": "product_table",
            "suggestion": "人工检查并优先复用 product_table。",
            "confidence": 0.81,
            "fix_candidates": ["product_table", "product_list_title"],
        }
    )

    assert "Advice Type: locator_update" in text
    assert "Target: product_table" in text
    assert "Fix Candidates: product_table, product_list_title" in text


def test_render_failure_overview_outputs_readable_summary(tmp_path: Path):
    text = MODULE.render_failure_overview(
        failure_message="AssertionError: product title not visible",
        analysis_result={
            "summary": "UI assertion failed on product page.",
            "failure_category": "assertion",
            "risk_level": "high",
            "likely_cause": "The expected product title was not visible.",
        },
        suggestion_result={
            "summary": "仅建议人工检查现有 target。",
            "advice_type": "locator_update",
            "target": "product_table",
            "confidence": 0.81,
        },
        current_url="http://example.test/product",
        page_title="商品列表",
        screenshot_path=tmp_path / "failed.png",
        html_path=tmp_path / "page.html",
        analysis_path=tmp_path / "analysis.txt",
        suggestion_path=tmp_path / "suggestion.json",
        video_path=tmp_path / "video.webm",
    )

    assert "Failure Overview" in text
    assert "Error: AssertionError: product title not visible" in text
    assert "- Category: assertion" in text
    assert "- Advice Type: locator_update" in text
    assert "- Target: product_table" in text
    assert "- Video: " in text


def test_load_available_targets_reads_existing_page_object_targets():
    targets = MODULE.load_available_targets("product")

    assert "product_menu" in targets
    assert "product_table" in targets


def test_find_recent_video_file_returns_latest_match(tmp_path: Path):
    video_dir = tmp_path / "videos"
    video_dir.mkdir()
    older = video_dir / "older.webm"
    newer = video_dir / "newer.webm"
    older.write_bytes(b"older")
    newer.write_bytes(b"newer")
    os.utime(older, (1, 1))
    os.utime(newer, (2, 2))

    found = MODULE.find_recent_video_file(video_dir, since_timestamp=0.0)

    assert found == newer


def test_extract_allure_test_metadata_from_parametrized_case():
    os.environ["BASE_URL"] = "http://localhost:5173/login#/login"
    os.environ["RUN_MODE"] = "ai"
    os.environ["RUN_SOURCE"] = "regression"

    class FakeCallSpec:
        params = {
            "test_case": {
                "id": "tc-product-GEN-001",
                "title": "验证商品搜索功能",
                "tags": ["product", "ai-generated"],
                "execution": {"page": "product"},
            }
        }

    class FakeNode:
        callspec = FakeCallSpec()
        name = "test_yaml_ai_generated"

    class FakeRequest:
        node = FakeNode()

    metadata = MODULE.extract_allure_test_metadata(FakeRequest())

    assert metadata == {
        "title": "验证商品搜索功能",
        "case_id": "tc-product-GEN-001",
        "page": "product",
        "tags": ["product", "ai-generated"],
        "base_url": "http://localhost:5173/login#/login",
        "run_mode": "ai",
        "run_source": "regression",
    }


def test_apply_allure_test_metadata_calls_dynamic_api(monkeypatch):
    calls = []

    class FakeDynamic:
        @staticmethod
        def title(value):
            calls.append(("title", value))

        @staticmethod
        def feature(value):
            calls.append(("feature", value))

        @staticmethod
        def story(value):
            calls.append(("story", value))

        @staticmethod
        def label(name, value):
            calls.append(("label", name, value))

        @staticmethod
        def tag(value):
            calls.append(("tag", value))

    class FakeAllure:
        dynamic = FakeDynamic()

    monkeypatch.setattr(MODULE, "allure", FakeAllure())

    result = MODULE.apply_allure_test_metadata(
        {
            "title": "验证商品搜索功能",
            "case_id": "tc-product-GEN-001",
            "page": "product",
            "tags": ["product", "ai-generated"],
            "base_url": "http://localhost:5173/login#/login",
            "run_mode": "ai",
            "run_source": "manual",
        }
    )

    assert result is True
    assert ("title", "验证商品搜索功能") in calls
    assert ("feature", "product") in calls
    assert ("story", "tc-product-GEN-001") in calls
    assert ("label", "case_id", "tc-product-GEN-001") in calls
    assert ("label", "base_url", "http://localhost:5173/login#/login") in calls
    assert ("label", "run_mode", "ai") in calls
    assert ("label", "run_source", "manual") in calls
    assert ("tag", "product") in calls
    assert ("tag", "ai-generated") in calls


def test_build_execution_record_contains_core_fields(tmp_path: Path):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    (case_dir / "meta.txt").write_text("URL: http://example.test\n", encoding="utf-8")
    (case_dir / "analysis.txt").write_text("Summary: failed\n", encoding="utf-8")

    class FakeCallSpec:
        params = {
            "test_case": {
                "id": "tc-product-GEN-001",
                "requirement": ["验证商品页面展示"],
                "execution": {
                    "page": "product",
                    "steps": [{"action": "login"}, {"action": "click", "target": "product_menu"}],
                },
            }
        }

    class FakeNode:
        callspec = FakeCallSpec()
        nodeid = "tests/test_yaml_ai_generated.py::test_yaml_ai_generated[case]"

    record = MODULE.build_execution_record(
        request=FakeNode(),
        case_dir=case_dir,
        status="failed",
        started_at="2026-03-18T00:00:00+00:00",
        finished_at="2026-03-18T00:00:01+00:00",
        duration_seconds=1.0,
        runner_exit_code=1,
    )

    assert record["case_id"] == "tc-product-GEN-001"
    assert record["version"] == "ExecutionRecordV1"
    assert record["status"] == "failed"
    assert record["step_summary"]["page"] == "product"
    assert record["step_summary"]["total_steps"] == 2
    assert record["evidence_index"]["artifact_categories"]["meta_files"] == 1
    assert record["evidence_index"]["artifact_categories"]["execution_record_files"] == 1
    assert record["metadata"]["pytest_phase"] == "call"


def test_build_execution_record_includes_failure_element_impact(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TEST_PROJECT", "mall")
    case_dir = tmp_path / "case"
    case_dir.mkdir()

    class FakeCallSpec:
        params = {
            "test_case": {
                "id": "tc-product-GEN-001",
                "execution": {
                    "page": "product",
                    "steps": [{"action": "click", "target": "product_name_input"}],
                },
            }
        }

    class FakeNode:
        callspec = FakeCallSpec()
        nodeid = "tests/test_yaml_ai_generated.py::test_yaml_ai_generated[case]"
        _failure_context = {
            "failed_step": {
                "step_index": 1,
                "page_code": "product",
                "action": "click",
                "target": "product_name_input",
                "selector": "[data-testid='product-name']",
                "locator_type": "testid",
            }
        }

    record = MODULE.build_execution_record(
        request=FakeNode(),
        case_dir=case_dir,
        status="failed",
        started_at="2026-03-18T00:00:00+00:00",
        finished_at="2026-03-18T00:00:01+00:00",
        duration_seconds=1.0,
        runner_exit_code=1,
    )

    assert record["metadata"]["failed_step"]["element_code"] == "product_name_input"
    assert record["metadata"]["element_impact"]["governance_href"].endswith(
        "/product/elements/product_name_input?project=mall"
    )


def test_report_status_and_exit_code_handles_failed():
    class FakeReport:
        failed = True
        skipped = False
        passed = False

    status, exit_code = MODULE._report_status_and_exit_code(FakeReport())
    assert status == "failed"
    assert exit_code == 1


def test_report_status_and_exit_code_handles_skipped():
    class FakeReport:
        failed = False
        skipped = True
        passed = False

    status, exit_code = MODULE._report_status_and_exit_code(FakeReport())
    assert status == "skipped"
    assert exit_code == 0


def test_select_execution_report_prefers_call_then_setup():
    class FakeItem:
        rep_call = None
        rep_setup = object()
        rep_teardown = object()

    selected = MODULE._select_execution_report(FakeItem())
    assert selected is FakeItem.rep_setup

    class FakeItemCall:
        rep_call = object()
        rep_setup = object()
        rep_teardown = object()

    selected_call = MODULE._select_execution_report(FakeItemCall())
    assert selected_call is FakeItemCall.rep_call


def test_build_evidence_manifest_collects_standard_categories(tmp_path: Path):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    (case_dir / "failed.png").write_bytes(b"png")
    (case_dir / "page.html").write_text("<html></html>", encoding="utf-8")
    (case_dir / "meta.txt").write_text("URL: http://example.test", encoding="utf-8")
    (case_dir / "analysis.txt").write_text("Summary: failed", encoding="utf-8")
    (case_dir / "suggestion.json").write_text('{"advice_type":"locator_update"}', encoding="utf-8")
    (case_dir / "self_healing_result.json").write_text('{"status":"success"}', encoding="utf-8")
    (case_dir / "execution_record.json").write_text('{"run_id":"run-1"}', encoding="utf-8")
    (case_dir / "trace.log").write_text("debug", encoding="utf-8")
    external_video = tmp_path / "videos" / "failure.webm"
    external_video.parent.mkdir(parents=True)
    external_video.write_bytes(b"webm")

    manifest = MODULE.build_evidence_manifest(
        case_dir=case_dir,
        execution_record_path=case_dir / "execution_record.json",
        video_path=external_video,
    )

    assert manifest["schema_version"] == "evidence-manifest.v1"
    assert manifest["version"] == "EvidenceManifestV1"
    assert manifest["screenshots"] == ["failed.png"]
    assert manifest["html_pages"] == ["page.html"]
    assert manifest["meta_files"] == ["meta.txt"]
    assert manifest["analysis_files"] == ["analysis.txt"]
    assert manifest["suggestion_files"] == ["suggestion.json"]
    assert manifest["execution_record_files"] == ["execution_record.json"]
    assert manifest["self_healing_result_files"] == ["self_healing_result.json"]
    assert len(manifest["videos"]) == 1
    assert manifest["videos"][0].endswith("failure.webm")
    assert manifest["other_files"] == ["trace.log"]
    assert manifest["total_files"] == 9


def test_write_evidence_manifest_persists_json_file(tmp_path: Path):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    payload = {
        "schema_version": "evidence-manifest.v1",
        "generated_at": "2026-03-18T00:00:00+00:00",
        "artifact_root": str(case_dir),
        "screenshots": [],
        "html_pages": [],
        "meta_files": [],
        "analysis_files": [],
        "suggestion_files": [],
        "execution_record_files": [],
        "self_healing_result_files": [],
        "videos": [],
        "other_files": [],
        "total_files": 0,
    }

    path = MODULE.write_evidence_manifest(case_dir, payload)

    assert path == case_dir / "evidence_manifest.json"
    assert path.exists()
    assert '"schema_version": "evidence-manifest.v1"' in path.read_text(encoding="utf-8")


def test_attach_allure_failure_artifacts_returns_false_without_allure(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(MODULE, "allure", None)
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    (case_dir / "failed.png").write_bytes(b"png")
    (case_dir / "page.html").write_text("<html></html>", encoding="utf-8")
    (case_dir / "meta.txt").write_text("URL: http://example.test", encoding="utf-8")
    (case_dir / "analysis.txt").write_text("Summary: none", encoding="utf-8")
    (case_dir / "suggestion.json").write_text('{"advice_type":"no_change"}', encoding="utf-8")
    (case_dir / "self_healing_result.json").write_text('{"status":"rejected"}', encoding="utf-8")

    result = MODULE.attach_allure_failure_artifacts(case_dir)

    assert result == {
        "screenshot": False,
        "page_html": False,
        "meta": False,
        "meta_text": False,
        "analysis": False,
        "analysis_text": False,
        "suggestion": False,
        "suggestion_text": False,
        "healing_result": False,
        "healing_result_text": False,
    }


def test_attach_allure_failure_artifacts_attaches_existing_files(tmp_path: Path, monkeypatch):
    calls = []
    content_calls = []

    class FakeAttachmentType:
        PNG = "png"
        HTML = "html"
        TEXT = "text"
        JSON = "json"

    class FakeAttach:
        def __call__(self, content, *, name, attachment_type):
            content_calls.append((content, name, attachment_type))

        @staticmethod
        def file(path, *, name, attachment_type):
            calls.append((Path(path).name, name, attachment_type))

    class FakeAllure:
        attachment_type = FakeAttachmentType()
        attach = FakeAttach()

    monkeypatch.setattr(MODULE, "allure", FakeAllure())
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    (case_dir / "failed.png").write_bytes(b"png")
    (case_dir / "page.html").write_text("<html></html>", encoding="utf-8")
    (case_dir / "meta.txt").write_text("URL: http://example.test", encoding="utf-8")
    (case_dir / "analysis.txt").write_text("Summary: none", encoding="utf-8")
    (case_dir / "suggestion.json").write_text('{"advice_type":"locator_update"}', encoding="utf-8")
    (case_dir / "self_healing_result.json").write_text('{"status":"success"}', encoding="utf-8")

    result = MODULE.attach_allure_failure_artifacts(case_dir)

    assert result == {
        "screenshot": True,
        "page_html": True,
        "meta": True,
        "meta_text": True,
        "analysis": True,
        "analysis_text": True,
        "suggestion": True,
        "suggestion_text": True,
        "healing_result": True,
        "healing_result_text": True,
    }
    assert ("failed.png", "failure-screenshot", "png") in calls
    assert ("page.html", "page-html", "html") in calls
    assert ("suggestion.json", "self-healing-suggestion", "json") in calls
    assert ("self_healing_result.json", "self-healing-result", "json") in calls
    assert any(name == "failure-context" and attachment_type == "text" for _, name, attachment_type in content_calls)
    assert any(name == "ai-failure-analysis" and attachment_type == "text" for _, name, attachment_type in content_calls)
    assert any(name == "self-healing-advice" and attachment_type == "text" for _, name, attachment_type in content_calls)
    assert any(name == "self-healing-result-summary" and attachment_type == "text" for _, name, attachment_type in content_calls)


def test_attach_allure_video_artifact_attaches_webm(tmp_path: Path, monkeypatch):
    calls = []

    class FakeAttachmentType:
        WEBM = "webm"

    class FakeAttach:
        @staticmethod
        def file(path, *, name, attachment_type):
            calls.append((Path(path).name, name, attachment_type))

    class FakeAllure:
        attachment_type = FakeAttachmentType()
        attach = FakeAttach()

    monkeypatch.setattr(MODULE, "allure", FakeAllure())
    video_path = tmp_path / "failure.webm"
    video_path.write_bytes(b"webm")

    result = MODULE.attach_allure_video_artifact(video_path)

    assert result is True
    assert ("failure.webm", "failure-video", "webm") in calls


def test_is_self_healing_enabled_defaults_to_false(monkeypatch):
    monkeypatch.delenv("SELF_HEALING_ENABLED", raising=False)

    assert MODULE.is_self_healing_enabled() is False


def test_is_self_healing_enabled_accepts_true_like_values(monkeypatch):
    monkeypatch.setenv("SELF_HEALING_ENABLED", "true")

    assert MODULE.is_self_healing_enabled() is True


def test_get_self_healing_attempts_parses_non_negative_integer(monkeypatch):
    monkeypatch.setenv("SELF_HEALING_ATTEMPTS", "2")
    assert MODULE.get_self_healing_attempts() == 2

    monkeypatch.setenv("SELF_HEALING_ATTEMPTS", "-3")
    assert MODULE.get_self_healing_attempts() == 0

    monkeypatch.setenv("SELF_HEALING_ATTEMPTS", "abc")
    assert MODULE.get_self_healing_attempts() == 0


def test_resolve_case_yaml_path_prefers_test_case_path_env(monkeypatch, tmp_path: Path):
    case_path = tmp_path / "TC-AI-001.yaml"
    case_path.write_text("id: TC-AI-001\n", encoding="utf-8")
    monkeypatch.setenv("TEST_CASE_PATH", str(case_path))

    resolved = MODULE.resolve_case_yaml_path(object())

    assert resolved == case_path.resolve()


def test_resolve_case_yaml_path_falls_back_to_ai_generated_case_id(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("TEST_CASE_PATH", raising=False)
    fake_repo_root = tmp_path
    ai_generated_root = fake_repo_root / "assets" / "test-cases" / "ai-generated"
    ai_generated_root.mkdir(parents=True)
    case_path = ai_generated_root / "TC-AI-002.yaml"
    case_path.write_text("id: TC-AI-002\n", encoding="utf-8")

    class FakeCallSpec:
        params = {"test_case": {"id": "TC-AI-002"}}

    class FakeNode:
        callspec = FakeCallSpec()

    class FakeRequest:
        node = FakeNode()

    monkeypatch.setattr(MODULE, "__file__", str(fake_repo_root / "runners" / "web-playwright-python" / "conftest.py"))

    resolved = MODULE.resolve_case_yaml_path(FakeRequest())

    assert resolved == case_path.resolve()
