from pathlib import Path
import sys


SRC_ROOT = Path(__file__).resolve().parent / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from agent import SelfHealingAdvisorAgent


def test_self_healing_advisor_outputs_manual_suggestions_only():
    agent = SelfHealingAdvisorAgent()
    agent.client = None

    result = agent.advise(
        {
            "page": "product",
            "failure_reason": "expected product list title to be visible",
            "available_targets": ["product_menu", "product_list_title", "search_input", "search_button"],
            "failure_analysis": {
                "failure_category": "assertion",
            },
        }
    )

    assert result["suggestion_type"] == "assertion_update"
    assert result["safe_to_apply_manually"] is True
    assert result["suggested_changes"]
    assert "manually" in result["summary"].lower() or "manual" in result["summary"].lower()
