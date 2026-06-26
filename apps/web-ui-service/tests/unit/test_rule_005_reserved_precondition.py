"""RULE_005 结构化 preconditions 校验 — 预留未实现类型应给 WARNING。

补齐跨层一致性：编译器对 api_call 等预留类型硬失败，质量门也必须提前
标记（passed=False/WARNING），而非把它当作合法类型静默放行。
"""
from __future__ import annotations

from shared_backend.quality_gate import GateContext
from app.services.quality_gate.rules.rule_005_missing_precondition import (
    MissingPreconditionRule,
)


def _validate(case_yaml: dict):
    return MissingPreconditionRule().validate(GateContext(case_yaml=case_yaml))


def test_reserved_type_api_call_flagged_not_passed() -> None:
    result = _validate({
        "preconditions": [{"type": "api_call"}],
        "requirement": {},
        "execution": {"steps": []},
    })
    assert result.passed is False
    assert "预留" in result.message


def test_implemented_type_account_state_passes() -> None:
    result = _validate({
        "preconditions": [{"type": "account_state", "state": "locked"}],
        "requirement": {},
        "execution": {"steps": []},
    })
    assert result.passed is True
