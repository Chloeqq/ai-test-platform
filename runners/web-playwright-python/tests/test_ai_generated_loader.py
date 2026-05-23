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
    assert all(case["id"] == case["id"].lower() for case in test_cases)
    assert all(len(case["id"].split("-")) >= 3 for case in test_cases)
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


def test_ai_generated_loader_accepts_runtime_case_path_from_extra_root(monkeypatch, tmp_path: Path):
    runtime_root = tmp_path / "runtime-cases" / "run-001"
    runtime_root.mkdir(parents=True)
    runtime_case_path = runtime_root / "TC-AI-RUNTIME.yaml"
    runtime_case_path.write_text(
        yaml.safe_dump(
            {
                "version": "v4",
                "id": "TC-AI-RUNTIME",
                "title": "Runtime case",
                "module": "login",
                "priority": "P1",
                "tags": ["login"],
                "owner": "qa-team",
                "status": "automated",
                "description": "Runtime case",
                "requirement": ["Runtime case"],
                "data": {},
                "execution": {
                    "runner": "playwright",
                    "page": "login",
                    "variables": {},
                    "steps": [
                        {"action": "goto", "value": "http://localhost:5174/#/login"},
                    ],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TEST_CASE_ALLOWED_ROOTS", str(runtime_root))

    test_cases = load_ai_generated_test_cases(case_path=str(runtime_case_path))

    assert len(test_cases) == 1
    assert test_cases[0]["id"] == "TC-AI-RUNTIME"


def test_ai_generated_loader_validates_explicit_case_path_schema(monkeypatch, tmp_path: Path):
    runtime_root = tmp_path / "runtime-cases" / "run-invalid"
    runtime_root.mkdir(parents=True)
    runtime_case_path = runtime_root / "TC-AI-INVALID.yaml"
    runtime_case_path.write_text(
        yaml.safe_dump(
            {
                "version": "v4",
                "id": "TC-AI-INVALID",
                "title": "Invalid runtime case",
                "module": "login",
                "priority": "P1",
                "tags": ["login"],
                "owner": "qa-team",
                "status": "automated",
                "description": "Missing execution steps",
                "requirement": ["Invalid runtime case"],
                "data": {},
                "execution": {
                    "runner": "playwright",
                    "page": "login",
                    "variables": {},
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TEST_CASE_ALLOWED_ROOTS", str(runtime_root))

    with pytest.raises(Exception, match="'steps' is a required property"):
        load_ai_generated_test_cases(case_path=str(runtime_case_path))


def test_ai_generated_loader_accepts_top_level_assertions(monkeypatch, tmp_path: Path):
    runtime_root = tmp_path / "runtime-cases" / "run-assertions"
    runtime_root.mkdir(parents=True)
    runtime_case_path = runtime_root / "TC-AI-ASSERTIONS.yaml"
    runtime_case_path.write_text(
        yaml.safe_dump(
            {
                "version": "v1",
                "id": "TC-AI-ASSERTIONS",
                "title": "Runtime case with executable assertions",
                "module": "login",
                "priority": "P1",
                "tags": ["ai-generated"],
                "owner": "qa-team",
                "status": "automated",
                "description": "Runtime case with assertions",
                "requirement": {
                    "intent_id": "intent-01",
                    "title": "首次登录成功",
                    "type": "functional",
                },
                "data": {},
                "execution": {
                    "runner": "playwright",
                    "page": "login",
                    "variables": {},
                    "steps": [
                        {"action": "goto", "value": "http://localhost:5174/#/login"},
                    ],
                },
                "assertions": [
                    {
                        "action": "assert_url",
                        "value": "/#/home",
                        "expected_result": "登录后进入首页",
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TEST_CASE_ALLOWED_ROOTS", str(runtime_root))

    test_cases = load_ai_generated_test_cases(case_path=str(runtime_case_path))

    assert test_cases[0]["assertions"][0]["action"] == "assert_url"


def test_ai_generated_loader_rejects_assert_url_without_value(monkeypatch, tmp_path: Path):
    runtime_root = tmp_path / "runtime-cases" / "run-invalid-assertions"
    runtime_root.mkdir(parents=True)
    runtime_case_path = runtime_root / "TC-AI-ASSERTIONS-INVALID.yaml"
    runtime_case_path.write_text(
        yaml.safe_dump(
            {
                "version": "v1",
                "id": "TC-AI-ASSERTIONS-INVALID",
                "title": "Runtime case with invalid assertions",
                "module": "login",
                "priority": "P1",
                "tags": ["ai-generated"],
                "owner": "qa-team",
                "status": "automated",
                "description": "Runtime case with invalid assertions",
                "requirement": ["Invalid assertion case"],
                "data": {},
                "execution": {
                    "runner": "playwright",
                    "page": "login",
                    "variables": {},
                    "steps": [
                        {"action": "goto", "value": "http://localhost:5174/#/login"},
                    ],
                },
                "assertions": [
                    {
                        "action": "assert_url",
                        "expected_result": "登录后进入首页",
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TEST_CASE_ALLOWED_ROOTS", str(runtime_root))

    with pytest.raises(Exception, match="'value' is a required property"):
        load_ai_generated_test_cases(case_path=str(runtime_case_path))
