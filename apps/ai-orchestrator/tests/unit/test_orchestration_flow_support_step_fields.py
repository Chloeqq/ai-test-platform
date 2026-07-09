"""_materialize_compiled_steps 不应静默丢弃 DSL step 字段。

见 shared_backend/step_fields.py 的模块说明——这是项目里第 6 处独立维护
"按固定字段重建 step 字典"的位置，且是唯一一处在 ai-orchestrator 服务里
（其余都在 web-ui-service），容易在排查跨服务问题时被漏掉。
"""
from __future__ import annotations

import sys
from pathlib import Path

src_root = Path(__file__).resolve().parents[2] / "src"
if str(src_root) not in sys.path:
    sys.path.insert(0, str(src_root))
repo_root = Path(__file__).resolve().parents[4]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from services.orchestration_flow_support import OrchestrationFlowSupport
from shared_backend.step_fields import STEP_FIELD_NAMES


def test_materialize_compiled_steps_preserves_attribute_field() -> None:
    step = {
        "action": "assert_attribute",
        "target": "login-password-input",
        "selector": "login-password-input",
        "locator_type": "data-testid",
        "intent_id": "intent-27",
        "traceability": {},
        "value": "password",
        "attribute": "type",
    }
    result = OrchestrationFlowSupport._materialize_compiled_steps(case={"execution": {}}, compiled_steps=[step])
    rendered = result["execution"]["steps"][0]
    for field_name in ("action", "target", "selector", "locator_type", "intent_id", "value", "attribute"):
        assert field_name in rendered, f"_materialize_compiled_steps 丢掉了字段 {field_name!r}"
    assert rendered["attribute"] == "type"


def test_materialize_compiled_steps_preserves_any_step_field_present() -> None:
    """通用兜底：STEP_FIELD_NAMES 里任意非空字段都不应被丢——不只是 attribute。

    count 字段例外：原逻辑只在 action == "assert_count" 时才带 count，
    这是有意的 action 门控（避免给不需要计数的步骤塞一个无意义的字段），
    不是漏改，这里单独验证而不放进通用兜底断言。
    """
    step = {name: f"value-{name}" for name in STEP_FIELD_NAMES}
    step["action"] = "assert_attribute"
    result = OrchestrationFlowSupport._materialize_compiled_steps(case={"execution": {}}, compiled_steps=[step])
    rendered = result["execution"]["steps"][0]
    for field_name in STEP_FIELD_NAMES - {"count"}:
        assert field_name in rendered, f"_materialize_compiled_steps 丢掉了字段 {field_name!r}"

    count_step = dict(step, action="assert_count")
    count_result = OrchestrationFlowSupport._materialize_compiled_steps(case={"execution": {}}, compiled_steps=[count_step])
    assert "count" in count_result["execution"]["steps"][0]
