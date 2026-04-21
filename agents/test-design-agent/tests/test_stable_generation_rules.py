from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from src.agent import TestDesignAgent, TestDesignAgentError  # noqa: E402
from src.prompt import SYSTEM_PROMPT, build_generate_prompt  # noqa: E402


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content


class _FakeChoice:
    def __init__(self, content: str):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, responses: list[str]):
        self._responses = responses
        self.calls: list[dict[str, object]] = []
        self._cursor = 0

    def create(self, **kwargs):
        self.calls.append(kwargs)
        index = min(self._cursor, len(self._responses) - 1)
        self._cursor += 1
        return _FakeResponse(self._responses[index])


class _FakeChat:
    def __init__(self, responses: list[str]):
        self.completions = _FakeCompletions(responses)


class _FakeClient:
    def __init__(self, responses: list[str]):
        self.chat = _FakeChat(responses)


def _build_agent(responses: list[str], *, retries: int = 3) -> TestDesignAgent:
    agent = object.__new__(TestDesignAgent)
    agent.client = _FakeClient(responses)
    agent.model = "unit-test-model"
    agent.max_retries = retries
    agent.timeout_seconds = 30
    return agent


def _valid_case_payload() -> dict[str, object]:
    return {
        "version": "v4",
        "id": "atp-web-login-auth-fn-ai-9999",
        "title": "登录页-认证模块-负面场景-执行验证-账号锁定提示正确",
        "module": "auth",
        "priority": "P1",
        "tags": ["ai-generated", "login"],
        "owner": "qa-team",
        "status": "automated",
        "description": "账号锁定时登录提示",
        "requirement": ["账号锁定登录提示"],
        "data": {"username": ["test001"], "password": ["123456"]},
        "execution": {
            "runner": "playwright",
            "page": "login",
            "variables": {},
            "steps": [
                {"action": "fill", "target": "locked_username_input", "value": "test001"},
                {"action": "fill", "target": "password_input", "value": "123456"},
                {"action": "click", "target": "login_button"},
            ],
        },
    }


def test_generate_keeps_llm_steps_without_local_rule_rewrite(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _build_agent([json.dumps(_valid_case_payload(), ensure_ascii=False)])
    monkeypatch.setattr("src.agent.list_page_elements", lambda _page: ["username_input", "password_input", "login_button"])

    generated = agent.generate(requirement="账号锁定登录提示", page="login")

    assert generated["execution"]["steps"][0]["target"] == "locked_username_input"
    calls = agent.client.chat.completions.calls
    assert len(calls) == 1
    assert calls[0]["model"] == "unit-test-model"


def test_generate_retries_until_structured_output_is_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    valid_payload = json.dumps(_valid_case_payload(), ensure_ascii=False)
    agent = _build_agent(
        [
            "not-json",
            json.dumps({"version": "v4"}, ensure_ascii=False),
            valid_payload,
        ],
        retries=3,
    )
    monkeypatch.setattr("src.agent.list_page_elements", lambda _page: [])

    generated = agent.generate(requirement="登录功能", page="login")

    assert generated["id"] == "atp-web-login-auth-fn-ai-9999"
    assert len(agent.client.chat.completions.calls) == 3


def test_generate_fails_with_explicit_code_after_retry_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _build_agent(["{}", "{}", "{}"], retries=3)
    monkeypatch.setattr("src.agent.list_page_elements", lambda _page: [])

    with pytest.raises(TestDesignAgentError) as exc_info:
        agent.generate(requirement="登录功能", page="login")

    err = exc_info.value
    assert err.code == "test_design_invalid_output"
    assert int(err.details.get("attempts", 0)) == 3


def test_design_bundle_is_generated_by_llm_and_schema_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "version": "TestDesignBundleV1",
        "page": "login",
        "requirement": ["登录功能覆盖"],
        "requirement_spec": {"page": "login"},
        "case": _valid_case_payload(),
        "test_points": {"points": [{"key": "tp-01", "action": "click"}]},
        "traceability": {"coverage": "partial"},
        "review_summary": {"pending_review_count": 1},
        "confidence": 0.82,
        "warnings": [],
        "requires_review": True,
        "metadata": {"generator": "test-design-agent"},
    }
    agent = _build_agent([json.dumps(payload, ensure_ascii=False)], retries=3)
    monkeypatch.setattr("src.agent.list_page_elements", lambda _page: [])

    bundle = agent.design_bundle(requirement="登录功能覆盖", page="login", requirement_spec={"page": "login"})

    assert bundle["case"]["execution"]["page"] == "login"
    assert "test_points" in bundle
    assert "traceability" in bundle
    assert "review_summary" in bundle


def test_generate_retries_when_data_value_is_not_array(monkeypatch: pytest.MonkeyPatch) -> None:
    invalid_payload = _valid_case_payload()
    invalid_payload["data"] = {"username": "test001"}
    valid_payload = _valid_case_payload()

    agent = _build_agent(
        [
            json.dumps(invalid_payload, ensure_ascii=False),
            json.dumps(valid_payload, ensure_ascii=False),
        ],
        retries=3,
    )
    monkeypatch.setattr("src.agent.list_page_elements", lambda _page: [])

    generated = agent.generate(requirement="登录功能", page="login")
    assert generated["data"]["username"] == ["test001"]
    assert len(agent.client.chat.completions.calls) == 2


def test_system_prompt_contains_single_intent_and_real_step_constraints() -> None:
    assert "一个用例只对应一个测试意图" in SYSTEM_PROMPT
    assert "禁止出现连续重复 login" in SYSTEM_PROMPT
    assert "intent-01～intent-99" in SYSTEM_PROMPT


def test_generate_prompt_contains_action_whitelist_and_timeout_example() -> None:
    prompt = build_generate_prompt(
        requirement="验证登录超时提示",
        page="login",
        page_elements=["username_input", "password_input", "login_button", "timeout_toast"],
    )
    assert "fill / click / wait_for / assert_visible / assert_text" in prompt
    assert '"version": "v4"' in prompt
    assert '"action": "assert_text"' in prompt
