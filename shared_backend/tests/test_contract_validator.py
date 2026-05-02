"""Tests for ContractValidator inter-layer validation logic."""
from __future__ import annotations

import pytest
from shared_backend.schemas.validator import ContractValidator


_PAGE_OBJECT = {
    "elements": {
        "username_input": {"selector": "#user", "type": "css"},
        "login_button": {"selector": "button.login", "type": "css"},
    }
}


@pytest.fixture
def validator() -> ContractValidator:
    return ContractValidator()


class TestFieldCompleteness:
    def test_valid_points_pass(self, validator: ContractValidator) -> None:
        points = [
            {
                "intent_id": "intent-01",
                "key": "intent-01",
                "action": "fill",
                "target": "username_input",
                "expected_result": "用户名输入成功并可见。",
                "involved_elements": ["username_input"],
                "steps": [{"action": "fill", "target": "username_input"}],
            }
        ]
        result = validator.validate_normalized_test_points(points, strict=True)
        assert result.valid
        assert not result.errors

    def test_missing_intent_id_strict_error(self, validator: ContractValidator) -> None:
        points = [{"action": "click", "target": "login_button"}]
        result = validator.validate_normalized_test_points(points, strict=True)
        assert not result.valid
        assert any("intent_id" in e for e in result.errors)

    def test_missing_intent_id_non_strict_warning(self, validator: ContractValidator) -> None:
        points = [{"action": "click", "target": "login_button"}]
        result = validator.validate_normalized_test_points(points, strict=False)
        assert result.valid
        assert any("intent_id" in w for w in result.warnings)

    def test_no_action_no_steps_strict_error(self, validator: ContractValidator) -> None:
        points = [{"intent_id": "intent-01"}]
        result = validator.validate_normalized_test_points(points, strict=True)
        assert not result.valid

    def test_missing_involved_elements_strict_error(self, validator: ContractValidator) -> None:
        points = [{
            "intent_id": "intent-01",
            "action": "click",
            "expected_result": "点击后页面有反馈。",
            "steps": [{"action": "click", "target": "login_button"}],
        }]
        result = validator.validate_normalized_test_points(points, strict=True)
        assert not result.valid
        assert any("involved_elements" in e for e in result.errors)

    def test_noop_action_warns(self, validator: ContractValidator) -> None:
        points = [{"intent_id": "intent-01", "action": "noop"}]
        result = validator.validate_normalized_test_points(points, strict=False)
        assert any("noop" in w for w in result.warnings)

    def test_duplicate_intent_step_pair_error(self, validator: ContractValidator) -> None:
        points = [
            {"intent_id": "intent-01", "action": "click", "expected_result": "按钮可点击。", "step_index": 1},
            {"intent_id": "intent-01", "action": "fill", "expected_result": "输入可成功。", "step_index": 1},
        ]
        result = validator.validate_normalized_test_points(points, strict=True)
        assert not result.valid
        assert any("duplicate" in e for e in result.errors)

    def test_missing_expected_result_strict_error(self, validator: ContractValidator) -> None:
        points = [
            {
                "intent_id": "intent-01",
                "key": "intent-01",
                "action": "click",
                "target": "login_button",
                "involved_elements": ["login_button"],
                "steps": [{"action": "click", "target": "login_button"}],
            }
        ]
        result = validator.validate_normalized_test_points(points, strict=True)
        assert not result.valid
        assert any("missing expected_result" in e for e in result.errors)

    def test_precondition_login_allows_empty_expected_result(self, validator: ContractValidator) -> None:
        points = [
            {
                "intent_id": "login-00",
                "key": "login-00",
                "point_type": "precondition",
                "action": "login",
                "steps": [{"action": "login", "raw_text": "Use shared login precondition."}],
                "involved_elements": [],
            }
        ]
        result = validator.validate_normalized_test_points(points, strict=True)
        assert result.valid
        assert not result.errors


class TestIntentCoverage:
    def test_full_coverage_no_warnings(self, validator: ContractValidator) -> None:
        spec = {"test_intents": [{"intent_id": "intent-01"}, {"intent_id": "intent-02"}]}
        points = [
            {"intent_id": "intent-01", "action": "click"},
            {"intent_id": "intent-02", "action": "fill"},
        ]
        result = validator.validate_intent_coverage(spec, points)
        assert result.valid
        assert not result.warnings

    def test_orphan_point_warns(self, validator: ContractValidator) -> None:
        spec = {"test_intents": [{"intent_id": "intent-01"}]}
        points = [
            {"intent_id": "intent-01", "action": "click"},
            {"intent_id": "intent-99", "action": "fill"},
        ]
        result = validator.validate_intent_coverage(spec, points)
        assert any("intent-99" in w and "not found" in w for w in result.warnings)

    def test_uncovered_intent_warns(self, validator: ContractValidator) -> None:
        spec = {"test_intents": [{"intent_id": "intent-01"}, {"intent_id": "intent-02"}]}
        points = [{"intent_id": "intent-01", "action": "click"}]
        result = validator.validate_intent_coverage(spec, points)
        assert any("intent-02" in w and "no corresponding" in w for w in result.warnings)


class TestElementResolution:
    def test_known_target_passes(self, validator: ContractValidator) -> None:
        points = [{"target": "username_input", "action": "fill"}]
        result = validator.validate_element_resolution(points, _PAGE_OBJECT)
        assert result.valid
        assert not [w for w in result.warnings if "not in page" in w]

    def test_unknown_target_warns(self, validator: ContractValidator) -> None:
        points = [{"target": "nonexistent", "action": "click"}]
        result = validator.validate_element_resolution(points, _PAGE_OBJECT)
        assert any("nonexistent" in w for w in result.warnings)

    def test_unknown_target_strict_errors(self, validator: ContractValidator) -> None:
        points = [{"target": "nonexistent", "action": "click"}]
        result = validator.validate_element_resolution(points, _PAGE_OBJECT, strict=True)
        assert not result.valid
        assert any("nonexistent" in e for e in result.errors)


class TestFullValidation:
    def test_full_validation_aggregates_results(self, validator: ContractValidator) -> None:
        spec = {"test_intents": [{"intent_id": "intent-01"}]}
        points = [
            {
                "intent_id": "intent-01",
                "action": "fill",
                "target": "username_input",
                "expected_result": "输入后值正确。",
                "involved_elements": ["username_input"],
            }
        ]
        result = validator.validate_full(spec, points, _PAGE_OBJECT)
        assert result.valid

    def test_full_validation_catches_multiple_issues(self, validator: ContractValidator) -> None:
        spec = {"test_intents": [{"intent_id": "intent-01"}, {"intent_id": "intent-02"}]}
        points = [
            {"action": "click", "target": "nonexistent"},
        ]
        result = validator.validate_full(spec, points, _PAGE_OBJECT, strict=True)
        assert not result.valid
        assert len(result.errors) >= 1
        assert len(result.warnings) == 0
