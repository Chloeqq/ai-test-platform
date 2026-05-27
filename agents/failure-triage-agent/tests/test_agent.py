from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PACKAGE_ROOT / "src"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

SCHEMA_SPEC = importlib.util.spec_from_file_location("src.schema", SRC_ROOT / "schema.py")
assert SCHEMA_SPEC and SCHEMA_SPEC.loader
SCHEMA_MODULE = importlib.util.module_from_spec(SCHEMA_SPEC)
sys.modules["src.schema"] = SCHEMA_MODULE
SCHEMA_SPEC.loader.exec_module(SCHEMA_MODULE)

AGENT_SPEC = importlib.util.spec_from_file_location("src.agent", SRC_ROOT / "agent.py")
assert AGENT_SPEC and AGENT_SPEC.loader
AGENT_MODULE = importlib.util.module_from_spec(AGENT_SPEC)
sys.modules["src.agent"] = AGENT_MODULE
AGENT_SPEC.loader.exec_module(AGENT_MODULE)

FailureTriageAgent = AGENT_MODULE.FailureTriageAgent


def test_triage_routes_page_object_failures_to_qa_automation() -> None:
    payload = FailureTriageAgent().triage(
        failure_analysis={
            "failure_category": "locator",
            "failure_source": "page_object",
            "risk_level": "medium",
            "confidence": 0.91,
        },
        execution_record={"status": "failed", "step_summary": {"page": "product", "action_types": ["click"]}},
        evidence_manifest={"total_files": 2, "analysis_files": ["/tmp/a.txt"]},
        report={"page": "product"},
    )

    assert payload["owner_team"] == "qa-automation"
    assert payload["queue"] == "ui-regression"
    assert payload["signals"]["failure_source"] == "page_object"


def test_triage_routes_app_bug_failures_to_product_engineering() -> None:
    payload = FailureTriageAgent().triage(
        failure_analysis={
            "failure_category": "assertion",
            "failure_source": "app_bug",
            "risk_level": "medium",
            "confidence": 0.84,
        },
        execution_record={"status": "failed", "step_summary": {"page": "order", "action_types": ["submit"]}},
        evidence_manifest={"total_files": 1},
        report={"page": "order"},
    )

    assert payload["owner_team"] == "product-engineering"
    assert payload["queue"] == "product-regression"
    assert payload["triage_label"].startswith("app_bug:assertion:")
    assert any(action["action"] == "collect_backend_logs" for action in payload["actions"])


def test_triage_routes_case_design_failures_to_review_queue() -> None:
    payload = FailureTriageAgent().triage(
        failure_analysis={
            "failure_category": "assertion",
            "failure_source": "case_design",
            "risk_level": "low",
            "confidence": 0.72,
        },
        execution_record={"status": "failed", "step_summary": {"page": "product", "action_types": ["assert_text"]}},
        evidence_manifest={"total_files": 1},
        report={"page": "product"},
    )

    assert payload["owner_team"] == "qa-design"
    assert payload["queue"] == "case-design-review"
    assert any(action["action"] == "review_assertions_and_test_points" for action in payload["actions"])


def test_triage_forces_manual_review_on_low_source_confidence() -> None:
    payload = FailureTriageAgent().triage(
        failure_analysis={
            "failure_category": "assertion",
            "failure_source": "case_design",
            "failure_source_confidence": 0.55,
            "risk_level": "low",
            "confidence": 0.8,
        },
        execution_record={"status": "failed", "step_summary": {"page": "product", "action_types": ["assert_text"]}},
        evidence_manifest={"total_files": 1},
        report={"page": "product"},
    )

    assert payload["requires_manual_review"] is True
    assert payload["signals"]["failure_source_confidence"] == 0.55
