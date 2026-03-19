from pathlib import Path

import pytest

from runner.action_registry import ACTION_DEFINITIONS
from runner.page_object_validator import validate_page_object_schema
from runner.paths import PAGE_OBJECTS_ROOT, TEST_CASES_ROOT
from runner.schema_validator import validate_testcase_schema
from runner.yaml_loader import load_yaml_file


pytestmark = [pytest.mark.contract]


STABLE_SMOKE_BASELINE = {
    "login-smoke.yaml": {
        "id": "TC-LOGIN-001",
        "page": "login",
        "steps": [
            {"action": "login"},
            {"action": "assert_visible", "target": "home_menu"},
        ],
    },
    "order-smoke.yaml": {
        "id": "TC-ORDER-001",
        "page": "order",
        "steps": [
            {"action": "login"},
            {"action": "click", "target": "order_menu"},
            {"action": "wait_for", "target": "order_list_title"},
            {"action": "assert_visible", "target": "order_list_title"},
        ],
    },
    "permission-smoke.yaml": {
        "id": "TC-PERMISSION-001",
        "page": "permission",
        "steps": [
            {"action": "login"},
            {"action": "click", "target": "permission_menu"},
            {"action": "wait_for", "target": "permission_table"},
            {"action": "assert_visible", "target": "permission_table"},
        ],
    },
    "product-smoke.yaml": {
        "id": "TC-PRODUCT-001",
        "page": "product",
        "steps": [
            {"action": "login"},
            {"action": "click", "target": "product_menu"},
            {"action": "wait_for", "target": "product_list_title"},
            {"action": "assert_visible", "target": "product_list_title"},
        ],
    },
}


STABLE_SMOKE_PAGE_OBJECT_TARGETS = {
    "login": {"username_input", "password_input", "login_button", "home_menu"},
    "order": {"order_menu", "order_list_title"},
    "permission": {"permission_menu", "permission_table"},
    "product": {"product_menu", "product_list_title", "search_input", "search_button", "product_table"},
}


def test_all_web_page_objects_are_non_empty_and_schema_valid():
    page_object_paths = sorted(PAGE_OBJECTS_ROOT.glob("*.page-object.yaml"))
    assert page_object_paths, "No web page objects found"

    for path in page_object_paths:
        page_object = load_yaml_file(path)
        assert page_object is not None, f"Page object file is empty: {path}"
        validate_page_object_schema(
            page_object,
            expected_page=path.name.replace(".page-object.yaml", ""),
        )


def test_all_test_cases_are_non_empty_schema_valid_and_reference_known_targets():
    test_case_paths = sorted(TEST_CASES_ROOT.rglob("*.yaml"))
    assert test_case_paths, "No YAML test cases found"

    seen_ids = set()

    for path in test_case_paths:
        test_case = load_yaml_file(path)
        assert test_case is not None, f"Test case file is empty: {path}"
        validate_testcase_schema(test_case)

        case_id = test_case["id"]
        assert case_id not in seen_ids, f"Duplicate test case id found: {case_id}"
        seen_ids.add(case_id)

        page_name = test_case["execution"]["page"]
        page_object_path = PAGE_OBJECTS_ROOT / f"{page_name}.page-object.yaml"
        assert page_object_path.exists(), f"Missing page object for test case {case_id}: {page_object_path}"

        page_object = load_yaml_file(page_object_path)
        assert page_object is not None, f"Page object file is empty: {page_object_path}"
        validate_page_object_schema(page_object, expected_page=page_name)

        elements = page_object["elements"]
        for index, step in enumerate(test_case["execution"]["steps"], start=1):
            action = step["action"]
            assert action in ACTION_DEFINITIONS, f"Unsupported action in {path}: {action}"

            requires_target = ACTION_DEFINITIONS[action]["requires_target"]
            target = step.get("target")

            if requires_target:
                assert target, f"Step {index} in {path} requires target for action '{action}'"

            if target:
                assert target in elements, (
                    f"Step {index} in {path} references missing target '{target}' for page '{page_name}'"
                )


def test_stable_smoke_yaml_baseline_is_frozen():
    smoke_paths = sorted(path.name for path in TEST_CASES_ROOT.joinpath("smoke").glob("*.yaml"))
    assert smoke_paths == sorted(STABLE_SMOKE_BASELINE), "Stable smoke YAML set changed unexpectedly"

    for file_name, baseline in STABLE_SMOKE_BASELINE.items():
        path = TEST_CASES_ROOT / "smoke" / file_name
        test_case = load_yaml_file(path)
        assert test_case is not None, f"Stable smoke file is empty: {path}"

        assert test_case["id"] == baseline["id"]
        assert test_case["execution"]["page"] == baseline["page"]
        assert test_case["execution"]["runner"] == "playwright"
        assert test_case["execution"]["variables"] == {}
        assert test_case["data"] == {}
        assert test_case["execution"]["steps"] == baseline["steps"]

        first_step = test_case["execution"]["steps"][0]
        assert first_step == {"action": "login"}, f"First step in {file_name} must be bare login"
        assert "target" not in first_step, f"login step in {file_name} must not contain target"
        assert "value" not in first_step, f"login step in {file_name} must not contain value"


def test_stable_smoke_page_object_targets_are_frozen():
    for page_name, expected_targets in STABLE_SMOKE_PAGE_OBJECT_TARGETS.items():
        path = PAGE_OBJECTS_ROOT / f"{page_name}.page-object.yaml"
        page_object = load_yaml_file(path)
        assert page_object is not None, f"Stable page object is empty: {path}"
        actual_targets = set(page_object["elements"])
        assert expected_targets.issubset(actual_targets), (
            f"Stable page object targets changed for {page_name}: missing {sorted(expected_targets - actual_targets)}"
        )
