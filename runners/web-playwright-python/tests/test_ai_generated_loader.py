from pathlib import Path

import pytest
import yaml

from runner.test_case_loader import load_ai_generated_test_cases


pytestmark = [pytest.mark.contract]


@pytest.fixture(autouse=True)
def clear_auth_state():
    yield


@pytest.fixture(autouse=True)
def capture_failure_artifacts():
    yield


def test_ai_generated_loader_only_reads_ai_generated_directory():
    test_cases = load_ai_generated_test_cases()

    assert test_cases, "No ai-generated test cases found"
    assert all(case["id"].startswith("TC-") for case in test_cases)
    assert all(case["execution"]["page"] for case in test_cases)
    assert all("smoke" not in case.get("tags", []) for case in test_cases)


def test_ai_generated_loader_rejects_smoke_case_path():
    smoke_case_path = Path(__file__).resolve().parents[3] / "assets" / "test-cases" / "smoke" / "product-smoke.yaml"

    with pytest.raises(ValueError, match="TEST_CASE_PATH must stay under"):
        load_ai_generated_test_cases(case_path=str(smoke_case_path))


def test_ai_generated_loader_accepts_case_path_inside_ai_generated(tmp_path: Path):
    ai_case_path = tmp_path / "TC-AI-001.yaml"
    ai_case_path.write_text(
        yaml.safe_dump(
            {
                "version": "v4",
                "id": "TC-AI-001",
                "title": "AI only case",
                "module": "product",
                "priority": "P1",
                "tags": ["product"],
                "owner": "qa-team",
                "status": "automated",
                "description": "AI generated case",
                "requirement": ["AI case"],
                "data": {},
                "execution": {
                    "runner": "playwright",
                    "page": "product",
                    "variables": {},
                    "steps": [
                        {"action": "login"},
                        {"action": "click", "target": "product_menu"},
                    ],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    from runner import test_case_loader

    original_root = test_case_loader.AI_GENERATED_CASES_ROOT
    test_case_loader.AI_GENERATED_CASES_ROOT = tmp_path
    try:
        test_cases = load_ai_generated_test_cases(case_path=str(ai_case_path))
    finally:
        test_case_loader.AI_GENERATED_CASES_ROOT = original_root

    assert len(test_cases) == 1
    assert test_cases[0]["id"] == "TC-AI-001"
