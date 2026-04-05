from pathlib import Path
import sys


AGENT_ROOT = Path(__file__).resolve().parent
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from suggest import SelfHealingAdvisor  # noqa: E402


def test_suggest_never_emits_new_target():
    advisor = SelfHealingAdvisor()
    advisor.client = None

    result = advisor.suggest(
        {
            "page": "product",
            "failure_reason": "locator not found for product list title",
            "failure_analysis": {
                "failure_category": "locator",
                "likely_cause": "The selector or target may be outdated.",
            },
            "available_targets": [
                "product_menu",
                "product_list_title",
                "search_input",
                "search_button",
                "product_table",
            ],
        }
    )

    available_targets = {
        "product_menu",
        "product_list_title",
        "search_input",
        "search_button",
        "product_table",
    }

    assert result["advice_type"] == "locator_update"
    assert result["target"] in available_targets or result["target"] == ""
    assert set(result["fix_candidates"]).issubset(available_targets)


def test_normalize_output_filters_unknown_target_and_blocks_auto_modify_wording():
    result = SelfHealingAdvisor._normalize_output(
        {
            "summary": "尝试自动修复建议",
            "advice_type": "locator_update",
            "target": "brand_new_target",
            "suggestion": "建议自动修改 YAML 并切换 target。",
            "confidence": 0.9,
            "fix_candidates": ["product_table", "brand_new_target"],
        },
        ["product_table", "product_list_title"],
    )

    assert result["target"] == ""
    assert result["fix_candidates"] == ["product_table"]
    assert "自动修改" not in result["suggestion"]
    assert "人工修改" in result["suggestion"]


def test_low_confidence_suppresses_suggestion_output():
    result = SelfHealingAdvisor._normalize_output(
        {
            "summary": "建议替换为 product_table",
            "advice_type": "locator_update",
            "target": "product_table",
            "suggestion": "人工修改为 product_table。",
            "confidence": 0.49,
            "fix_candidates": ["product_table"],
        },
        ["product_table", "product_list_title"],
    )

    assert result["advice_type"] == "no_change"
    assert result["target"] == ""
    assert result["suggestion"] == ""
    assert result["fix_candidates"] == []
    assert result["confidence"] == 0.49
