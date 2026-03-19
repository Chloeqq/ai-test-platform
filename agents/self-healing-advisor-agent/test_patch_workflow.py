import json
from pathlib import Path
import sys

import pytest
import yaml


AGENT_ROOT = Path(__file__).resolve().parent
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from apply_patch import apply_patch_plan
from patch_generator import generate_patch_plan
from rollback import rollback_patch
from self_healing_executor import SelfHealingExecutor
from self_healing_orchestrator import SelfHealingOrchestrator


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def test_patch_preview_rejects_stable_smoke_case(tmp_path: Path):
    smoke_root = tmp_path / "assets" / "test-cases" / "smoke"
    ai_root = tmp_path / "assets" / "test-cases" / "ai-generated"
    page_objects_root = tmp_path / "assets" / "page-objects" / "web"

    _write_yaml(
        smoke_root / "product-smoke.yaml",
        {
            "id": "TC-PRODUCT-SMOKE-001",
            "execution": {
                "page": "product",
                "steps": [
                    {"action": "login"},
                    {"action": "click", "target": "product_menu"},
                    {"action": "wait_for", "target": "product_list_title"},
                    {"action": "assert_visible", "target": "product_list_title"},
                ],
            },
        },
    )
    _write_yaml(
        page_objects_root / "product.page-object.yaml",
        {
            "page": "product",
            "elements": {
                "product_menu": {"locator_type": "css", "locator_value": ".menu"},
                "product_list_title": {"locator_type": "css", "locator_value": ".title"},
                "product_table": {"locator_type": "css", "locator_value": ".table"},
            },
        },
    )
    suggestion_path = tmp_path / "suggestion.json"
    suggestion_path.write_text(
        json.dumps(
            {
                "advice_type": "assertion_update",
                "target": "product_table",
                "confidence": 0.91,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    plan = generate_patch_plan(
        smoke_root / "product-smoke.yaml",
        suggestion_path,
        ai_generated_root=ai_root,
        page_objects_root=page_objects_root,
    )

    assert plan["allowed_to_apply"] is False
    assert "Only ai-generated YAML cases can be auto-healed." in plan["reason"]


def test_apply_and_rollback_patch_workflow(tmp_path: Path):
    ai_root = tmp_path / "assets" / "test-cases" / "ai-generated"
    page_objects_root = tmp_path / "assets" / "page-objects" / "web"
    rollback_root = tmp_path / "artifacts" / "yaml-rollbacks"

    case_path = ai_root / "TC-PRODUCT-SEARCH-001.yaml"
    original_case = {
        "version": "v4",
        "id": "TC-PRODUCT-SEARCH-001",
        "execution": {
            "runner": "playwright",
            "page": "product",
            "variables": {},
            "steps": [
                {"action": "login"},
                {"action": "click", "target": "product_menu"},
                {"action": "wait_for", "target": "product_list_title"},
                {"action": "assert_visible", "target": "product_list_title"},
            ],
        },
    }
    _write_yaml(case_path, original_case)
    _write_yaml(
        page_objects_root / "product.page-object.yaml",
        {
            "page": "product",
            "elements": {
                "product_menu": {"locator_type": "css", "locator_value": ".menu"},
                "product_list_title": {"locator_type": "css", "locator_value": ".title"},
                "product_table": {"locator_type": "css", "locator_value": ".table"},
            },
        },
    )

    suggestion_path = tmp_path / "suggestion.json"
    suggestion_path.write_text(
        json.dumps(
            {
                "summary": "replace assertion target",
                "advice_type": "assertion_update",
                "target": "product_table",
                "suggestion": "人工修改断言目标到已有 target。",
                "confidence": 0.88,
                "fix_candidates": ["product_table"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    plan = generate_patch_plan(
        case_path,
        suggestion_path,
        ai_generated_root=ai_root,
        page_objects_root=page_objects_root,
    )
    assert plan["allowed_to_apply"] is True
    assert "product_list_title" in plan["diff"]
    assert "product_table" in plan["diff"]

    plan_path = tmp_path / "patch-plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    receipt = apply_patch_plan(plan_path, rollback_root=rollback_root, ai_generated_root=ai_root)
    updated_data = yaml.safe_load(case_path.read_text(encoding="utf-8"))
    updated_steps = updated_data["execution"]["steps"]

    assert updated_steps[2]["target"] == "product_table"
    assert updated_steps[3]["target"] == "product_table"

    rollback_result = rollback_patch(Path(receipt["receipt_path"]), ai_generated_root=ai_root)
    restored_data = yaml.safe_load(case_path.read_text(encoding="utf-8"))
    restored_steps = restored_data["execution"]["steps"]

    assert restored_steps[2]["target"] == "product_list_title"
    assert restored_steps[3]["target"] == "product_list_title"
    assert Path(rollback_result["result_path"]).exists()


def test_apply_refuses_when_case_changed_after_preview(tmp_path: Path):
    ai_root = tmp_path / "assets" / "test-cases" / "ai-generated"
    page_objects_root = tmp_path / "assets" / "page-objects" / "web"

    case_path = ai_root / "TC-PRODUCT-SEARCH-001.yaml"
    _write_yaml(
        case_path,
        {
            "id": "TC-PRODUCT-SEARCH-001",
            "execution": {
                "page": "product",
                "steps": [
                    {"action": "login"},
                    {"action": "click", "target": "product_menu"},
                    {"action": "wait_for", "target": "product_list_title"},
                    {"action": "assert_visible", "target": "product_list_title"},
                ],
            },
        },
    )
    _write_yaml(
        page_objects_root / "product.page-object.yaml",
        {
            "page": "product",
            "elements": {
                "product_menu": {"locator_type": "css", "locator_value": ".menu"},
                "product_list_title": {"locator_type": "css", "locator_value": ".title"},
                "product_table": {"locator_type": "css", "locator_value": ".table"},
            },
        },
    )
    suggestion_path = tmp_path / "suggestion.json"
    suggestion_path.write_text(
        json.dumps(
            {
                "advice_type": "assertion_update",
                "target": "product_table",
                "confidence": 0.9,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    plan = generate_patch_plan(
        case_path,
        suggestion_path,
        ai_generated_root=ai_root,
        page_objects_root=page_objects_root,
    )
    plan_path = tmp_path / "patch-plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    case_path.write_text(case_path.read_text(encoding="utf-8") + "\n# changed after preview\n", encoding="utf-8")

    with pytest.raises(ValueError, match="does not match the previewed version"):
        apply_patch_plan(plan_path, rollback_root=tmp_path / "rollbacks", ai_generated_root=ai_root)


def test_executor_runs_preview_apply_and_rollback(tmp_path: Path):
    ai_root = tmp_path / "assets" / "test-cases" / "ai-generated"
    page_objects_root = tmp_path / "assets" / "page-objects" / "web"
    rollback_root = tmp_path / "artifacts" / "yaml-rollbacks"

    case_path = ai_root / "TC-PRODUCT-SEARCH-001.yaml"
    _write_yaml(
        case_path,
        {
            "id": "TC-PRODUCT-SEARCH-001",
            "execution": {
                "page": "product",
                "steps": [
                    {"action": "login"},
                    {"action": "click", "target": "product_menu"},
                    {"action": "wait_for", "target": "product_list_title"},
                    {"action": "assert_visible", "target": "product_list_title"},
                ],
            },
        },
    )
    _write_yaml(
        page_objects_root / "product.page-object.yaml",
        {
            "page": "product",
            "elements": {
                "product_menu": {"locator_type": "css", "locator_value": ".menu"},
                "product_list_title": {"locator_type": "css", "locator_value": ".title"},
                "product_table": {"locator_type": "css", "locator_value": ".table"},
            },
        },
    )
    suggestion_path = tmp_path / "suggestion.json"
    suggestion_path.write_text(
        json.dumps(
            {
                "advice_type": "assertion_update",
                "target": "product_table",
                "confidence": 0.92,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    executor = SelfHealingExecutor(
        ai_generated_root=ai_root,
        page_objects_root=page_objects_root,
        rollback_root=rollback_root,
    )

    plan = executor.preview(case_path, suggestion_path)
    assert plan["allowed_to_apply"] is True

    plan_path = executor.save_preview(plan, tmp_path / "executor-plan.json")
    receipt = executor.apply(plan_path)
    updated_data = yaml.safe_load(case_path.read_text(encoding="utf-8"))
    assert updated_data["execution"]["steps"][2]["target"] == "product_table"

    rollback_result = executor.rollback(Path(receipt["receipt_path"]))
    restored_data = yaml.safe_load(case_path.read_text(encoding="utf-8"))
    assert restored_data["execution"]["steps"][2]["target"] == "product_list_title"
    assert Path(rollback_result["result_path"]).exists()


def test_self_healing_orchestrator_keeps_patch_when_rerun_succeeds(tmp_path: Path):
    ai_root = tmp_path / "assets" / "test-cases" / "ai-generated"
    page_objects_root = tmp_path / "assets" / "page-objects" / "web"
    rollback_root = tmp_path / "artifacts" / "yaml-rollbacks"
    artifact_dir = tmp_path / "artifacts" / "case-1"
    case_path = ai_root / "TC-PRODUCT-SEARCH-001.yaml"

    _write_yaml(
        case_path,
        {
            "id": "TC-PRODUCT-SEARCH-001",
            "execution": {
                "page": "product",
                "steps": [
                    {"action": "login"},
                    {"action": "click", "target": "product_menu"},
                    {"action": "wait_for", "target": "product_list_title"},
                    {"action": "assert_visible", "target": "product_list_title"},
                ],
            },
        },
    )
    _write_yaml(
        page_objects_root / "product.page-object.yaml",
        {
            "page": "product",
            "elements": {
                "product_menu": {"locator_type": "css", "locator_value": ".menu"},
                "product_list_title": {"locator_type": "css", "locator_value": ".title"},
                "product_table": {"locator_type": "css", "locator_value": ".table"},
            },
        },
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "suggestion.json").write_text(
        json.dumps(
            {
                "advice_type": "assertion_update",
                "target": "product_table",
                "confidence": 0.91,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    executor = SelfHealingExecutor(
        ai_generated_root=ai_root,
        page_objects_root=page_objects_root,
        rollback_root=rollback_root,
    )
    orchestrator = SelfHealingOrchestrator(executor=executor, ai_generated_root=ai_root)

    result = orchestrator.run_from_artifacts(
        artifact_dir,
        case_path,
        rerun_case=lambda _case_path: {"success": True, "returncode": 0},
    )

    updated_data = yaml.safe_load(case_path.read_text(encoding="utf-8"))
    assert result["status"] == "success"
    assert result["attempts_used"] == 1
    assert result["healed"] is True
    assert result["rolled_back"] is False
    assert Path(result["result_path"]).exists()
    assert Path(result["plan_path"]).exists()
    assert updated_data["execution"]["steps"][2]["target"] == "product_table"
    assert updated_data["execution"]["steps"][3]["target"] == "product_table"


def test_self_healing_orchestrator_rolls_back_when_rerun_fails(tmp_path: Path):
    ai_root = tmp_path / "assets" / "test-cases" / "ai-generated"
    page_objects_root = tmp_path / "assets" / "page-objects" / "web"
    rollback_root = tmp_path / "artifacts" / "yaml-rollbacks"
    artifact_dir = tmp_path / "artifacts" / "case-2"
    case_path = ai_root / "TC-PRODUCT-SEARCH-001.yaml"

    _write_yaml(
        case_path,
        {
            "id": "TC-PRODUCT-SEARCH-001",
            "execution": {
                "page": "product",
                "steps": [
                    {"action": "login"},
                    {"action": "click", "target": "product_menu"},
                    {"action": "wait_for", "target": "product_list_title"},
                    {"action": "assert_visible", "target": "product_list_title"},
                ],
            },
        },
    )
    _write_yaml(
        page_objects_root / "product.page-object.yaml",
        {
            "page": "product",
            "elements": {
                "product_menu": {"locator_type": "css", "locator_value": ".menu"},
                "product_list_title": {"locator_type": "css", "locator_value": ".title"},
                "product_table": {"locator_type": "css", "locator_value": ".table"},
            },
        },
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "suggestion.json").write_text(
        json.dumps(
            {
                "advice_type": "assertion_update",
                "target": "product_table",
                "confidence": 0.91,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    executor = SelfHealingExecutor(
        ai_generated_root=ai_root,
        page_objects_root=page_objects_root,
        rollback_root=rollback_root,
    )
    orchestrator = SelfHealingOrchestrator(executor=executor, ai_generated_root=ai_root)

    result = orchestrator.run_from_artifacts(
        artifact_dir,
        case_path,
        rerun_case=lambda _case_path: {"success": False, "returncode": 1},
    )

    restored_data = yaml.safe_load(case_path.read_text(encoding="utf-8"))
    assert result["status"] == "rollback"
    assert result["attempts_used"] == 1
    assert result["healed"] is False
    assert result["rolled_back"] is True
    assert Path(result["rollback_result"]["result_path"]).exists()
    assert restored_data["execution"]["steps"][2]["target"] == "product_list_title"
    assert restored_data["execution"]["steps"][3]["target"] == "product_list_title"


def test_self_healing_orchestrator_rejects_low_confidence_and_repeat_attempts(tmp_path: Path):
    ai_root = tmp_path / "assets" / "test-cases" / "ai-generated"
    page_objects_root = tmp_path / "assets" / "page-objects" / "web"
    artifact_dir = tmp_path / "artifacts" / "case-3"
    case_path = ai_root / "TC-PRODUCT-SEARCH-001.yaml"

    _write_yaml(
        case_path,
        {
            "id": "TC-PRODUCT-SEARCH-001",
            "execution": {
                "page": "product",
                "steps": [
                    {"action": "login"},
                    {"action": "click", "target": "product_menu"},
                    {"action": "wait_for", "target": "product_list_title"},
                    {"action": "assert_visible", "target": "product_list_title"},
                ],
            },
        },
    )
    _write_yaml(
        page_objects_root / "product.page-object.yaml",
        {
            "page": "product",
            "elements": {
                "product_menu": {"locator_type": "css", "locator_value": ".menu"},
                "product_list_title": {"locator_type": "css", "locator_value": ".title"},
                "product_table": {"locator_type": "css", "locator_value": ".table"},
            },
        },
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "suggestion.json").write_text(
        json.dumps(
            {
                "advice_type": "assertion_update",
                "target": "product_table",
                "confidence": 0.7,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    executor = SelfHealingExecutor(
        ai_generated_root=ai_root,
        page_objects_root=page_objects_root,
        rollback_root=tmp_path / "rollbacks",
    )
    orchestrator = SelfHealingOrchestrator(executor=executor, ai_generated_root=ai_root)

    low_confidence = orchestrator.run_from_artifacts(
        artifact_dir,
        case_path,
        rerun_case=lambda _case_path: {"success": True},
    )
    repeated_attempt = orchestrator.run_from_artifacts(
        artifact_dir,
        case_path,
        previous_attempts=1,
        rerun_case=lambda _case_path: {"success": True},
    )

    assert low_confidence["status"] == "rejected"
    assert "greater than 0.7" in low_confidence["reason"]
    assert low_confidence["attempts_used"] == 0
    assert repeated_attempt["status"] == "rejected"
    assert "Maximum self-healing attempts reached" in repeated_attempt["reason"]
