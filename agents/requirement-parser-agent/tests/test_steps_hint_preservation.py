from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
import sys


AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

src_pkg = ModuleType("src")
src_pkg.__path__ = [str(AGENT_ROOT / "src")]
sys.modules["src"] = src_pkg

spec = importlib.util.spec_from_file_location("src.agent", AGENT_ROOT / "src" / "agent.py")
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
RequirementParserAgent = module.RequirementParserAgent


def test_coerce_llm_overlay_preserves_steps_hint() -> None:
    agent = RequirementParserAgent()
    overlay = agent._coerce_llm_overlay(
        overlay={
            "page": "login",
            "priority": "P1",
            "parse_confidence": 0.9,
            "test_intents": [
                {
                    "title": "首次登录成功",
                    "intent_type": "functional",
                    "priority": "P0",
                    "precondition": "用户已登录",
                    "steps": ["输入账号", "点击登录"],
                    "steps_hint": ["input:username_input", "click:login_button"],
                    "target": "username_input",
                    "value": "test001",
                    "expected_result": "进入首页",
                    "involved_elements": ["username_input", "login_button"],
                }
            ],
        },
        page="login",
    )

    intents = overlay.get("test_intents") if isinstance(overlay.get("test_intents"), list) else []
    assert len(intents) == 1
    assert intents[0]["steps_hint"] == ["input:username_input", "click:login_button"]
    assert intents[0]["target"] == "username_input"
    assert intents[0]["value"] == "test001"


def test_overlay_to_test_intents_preserves_steps_hint() -> None:
    intents = RequirementParserAgent._overlay_to_test_intents(
        llm_overlay={
            "test_intents": [
                {
                    "intent_id": "intent-01",
                    "title": "首次登录成功",
                    "intent_type": "functional",
                    "priority": "P1",
                    "precondition": "用户未登录",
                    "steps": ["输入账号", "点击登录"],
                    "steps_hint": ["input:username_input", "click:login_button"],
                    "target": "username_input",
                    "value": "test001",
                    "expected_result": "进入首页",
                    "involved_elements": ["username_input", "login_button"],
                }
            ]
        },
        page="login",
    )

    assert len(intents) == 1
    assert intents[0].steps_hint == ["input:username_input", "click:login_button"]
    assert intents[0].target == "username_input"
    assert intents[0].value == "test001"
