"""Unit tests for Requirement Parser — Sprint 2 Day 6."""
from __future__ import annotations

import pytest

from runners.api_python.requirement_parser import (
    _classify_scenario,
    _extract_intents_mock,
    _parse_llm_response,
    parse_requirement,
    parse_to_test_intents,
)


# ---------------------------------------------------------------------------
# _classify_scenario
# ---------------------------------------------------------------------------

def test_classify_positive():
    assert _classify_scenario("正确密码登录成功") == "positive"
    assert _classify_scenario("用户可以正常登录") == "positive"


def test_classify_negative():
    assert _classify_scenario("错误密码无法登录") == "negative"
    assert _classify_scenario("空用户名被拒绝") == "negative"
    assert _classify_scenario("账号被锁定不能登录") == "negative"


def test_classify_boundary():
    assert _classify_scenario("用户名超过最大长度被拒绝") == "boundary"
    assert _classify_scenario("密码包含特殊字符") == "boundary"


def test_classify_neutral():
    """Sentences that don't match any strong keyword → default positive."""
    assert _classify_scenario("用户浏览商品列表") == "positive"


# ---------------------------------------------------------------------------
# _extract_intents_mock
# ---------------------------------------------------------------------------

def test_extract_intents_single():
    intents = _extract_intents_mock("正确密码登录成功")
    assert len(intents) == 1
    assert intents[0]["scenario"] == "positive"


def test_extract_intents_multi():
    requirement = "正确密码登录成功。错误密码被拒绝。空用户名不能登录。"
    intents = _extract_intents_mock(requirement)
    assert len(intents) == 3
    scenarios = [i["scenario"] for i in intents]
    assert scenarios == ["positive", "negative", "negative"]


def test_extract_intents_empty():
    intents = _extract_intents_mock("")
    assert len(intents) == 0


def test_extract_intents_deduplicate():
    """Duplicate sentences should be deduplicated."""
    requirement = "正确密码登录成功。正确密码登录成功。"
    intents = _extract_intents_mock(requirement)
    assert len(intents) == 1


def test_extract_intents_short_filtered():
    """Very short sentences (< 4 chars) are filtered out."""
    requirement = "登录。正确密码登录成功。"
    intents = _extract_intents_mock(requirement)
    assert len(intents) == 1


# ---------------------------------------------------------------------------
# _parse_llm_response
# ---------------------------------------------------------------------------

def test_parse_valid_json():
    text = '{"intents": [{"name": "test", "scenario": "positive", "description": "desc"}]}'
    intents = _parse_llm_response(text)
    assert len(intents) == 1
    assert intents[0]["name"] == "test"


def test_parse_markdown_fenced():
    text = '```json\n{"intents": [{"name": "test", "scenario": "negative"}]}\n```'
    intents = _parse_llm_response(text)
    assert len(intents) == 1
    assert intents[0]["scenario"] == "negative"


def test_parse_invalid_json():
    intents = _parse_llm_response("not json at all")
    assert len(intents) == 0


def test_parse_nested_json():
    text = 'Some text before {"intents": [{"name": "a"}]} and after'
    intents = _parse_llm_response(text)
    assert len(intents) == 1


def test_parse_empty():
    assert len(_parse_llm_response("")) == 0
    assert len(_parse_llm_response(None)) == 0


# ---------------------------------------------------------------------------
# parse_requirement (mock mode)
# ---------------------------------------------------------------------------

def test_parse_requirement_login_scenarios():
    requirement = (
        "验证登录功能：正确密码登录成功，"
        "错误密码提示错误，空用户名拒绝登录"
    )
    intents = parse_requirement(requirement, use_llm=False)
    assert len(intents) == 3
    assert intents[0]["scenario"] == "positive"
    assert intents[1]["scenario"] == "negative"
    assert intents[2]["scenario"] == "negative"


def test_parse_requirement_empty():
    assert len(parse_requirement("")) == 0
    assert len(parse_requirement("   ")) == 0


# ---------------------------------------------------------------------------
# parse_to_test_intents
# ---------------------------------------------------------------------------

def test_parse_to_test_intents_returns_pydantic():
    intents = parse_to_test_intents("正确密码登录成功", use_llm=False)
    assert len(intents) == 1
    assert intents[0].scenario == "positive"
    assert intents[0].name != ""
