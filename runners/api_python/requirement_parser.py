"""Requirement Parser — Sprint 2 Day 6.

Converts natural language requirements into structured TestIntent objects
via LLM. AI only understands intent — it NEVER guesses API paths, status
codes, DB fields, or business rules.

Supports two modes:
  - LLM mode: uses OpenAI-compatible API (OPENAI_API_KEY + OPENAI_BASE_URL)
  - Mock mode: deterministic classification for testing
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from app.models.api_test_models import TestIntent


# ---------------------------------------------------------------------------
# LLM Prompt
# ---------------------------------------------------------------------------

_REQUIREMENT_PARSER_PROMPT = """You are a test intent analyzer. Your job is to read a requirement
and output structured test intents. You are NOT a test case generator.

RULES:
1. Extract test intents from the requirement. Each intent = one test scenario.
2. For each intent, output:
   - name: short kebab-case name (e.g. "login_success")
   - scenario: "positive" | "negative" | "boundary"
   - description: one sentence describing what to verify
3. NEVER output: api paths, HTTP status codes, SQL queries, element locators,
   error messages, test data values.
4. If the requirement is ambiguous, mark it as scenario="boundary" and add a
   note in description.

Output ONLY valid JSON, no markdown, no explanation:

{
  "intents": [
    {
      "name": "login_success",
      "scenario": "positive",
      "description": "Correct credentials should authenticate and return a token"
    }
  ]
}

Requirement:
{requirement}

Output:"""


# ---------------------------------------------------------------------------
# Mock mode — deterministic keyword-based classification (no LLM needed)
# ---------------------------------------------------------------------------

_NEGATIVE_KEYWORDS = [
    "错误", "失败", "拒绝", "不能", "无法", "无效", "非法",
    "不存在", "为空", "空", "错误密码", "wrong", "invalid",
    "锁定", "禁用", "过期",
]
_POSITIVE_KEYWORDS = [
    "成功", "正确", "通过", "可以", "正常", "success",
]
_BOUNDARY_KEYWORDS = [
    "边界", "最大", "最小", "超过", "小于", "大于",
    "空格", "特殊字符", "超长",
]


def _classify_scenario(text: str) -> str:
    """Simple keyword-based scenario classification for mock mode."""
    text_lower = text.lower()
    boundary_hits = sum(1 for kw in _BOUNDARY_KEYWORDS if kw in text_lower)
    negative_hits = sum(1 for kw in _NEGATIVE_KEYWORDS if kw in text_lower)
    positive_hits = sum(1 for kw in _POSITIVE_KEYWORDS if kw in text_lower)

    if boundary_hits >= 1 and boundary_hits >= negative_hits:
        return "boundary"
    if negative_hits > positive_hits:
        return "negative"
    return "positive"


def _extract_intents_mock(requirement: str) -> list[dict[str, Any]]:
    """Deterministic intent extraction without LLM.

    Splits requirement into sentences, classifies each as a test intent.
    Used for testing and as fallback when LLM is unavailable.
    """
    if not requirement or not requirement.strip():
        return []
    sentences = re.split(r"[；;。\n，,、]+", requirement)
    sentences = [s.strip() for s in sentences if len(s.strip()) >= 4]

    intents: list[dict[str, Any]] = []
    for i, sent in enumerate(sentences):
        scenario = _classify_scenario(sent)
        name = re.sub(r"[^\w]+", "_", sent[:30]).strip("_").lower()
        if not name:
            name = f"intent_{i + 1}"
        intents.append({
            "name": name,
            "scenario": scenario,
            "description": sent,
        })

    # Deduplicate by name
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for intent in intents:
        if intent["name"] not in seen:
            seen.add(intent["name"])
            unique.append(intent)
    return unique


# ---------------------------------------------------------------------------
# LLM mode
# ---------------------------------------------------------------------------

def _call_llm(prompt: str) -> str:
    """Call OpenAI-compatible API and return the response text."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    try:
        import openai
        client = openai.OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1000,
        )
        return response.choices[0].message.content or ""
    except ImportError:
        # Fallback: direct HTTP call
        import requests
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 1000,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


def _parse_llm_response(text: str) -> list[dict[str, Any]]:
    """Extract JSON from LLM response, handling markdown fences."""
    text = text.strip() if text else ""

    # Try to extract from markdown json fence
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence_match:
        text = fence_match.group(1).strip()

    # Try direct JSON parse
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        # Try to find JSON object boundaries
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start >= 0 and brace_end > brace_start:
            try:
                data = json.loads(text[brace_start:brace_end + 1])
            except (json.JSONDecodeError, ValueError):
                return []
        else:
            return []

    if isinstance(data, dict):
        return data.get("intents", [])
    if isinstance(data, list):
        return data
    return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_requirement(
    requirement: str,
    *,
    use_llm: bool = False,
) -> list[dict[str, Any]]:
    """Parse a natural language requirement into a list of TestIntent dicts.

    Args:
        requirement: Natural language requirement text.
        use_llm: If True, use LLM for parsing. If False, use mock classifier.

    Returns:
        List of intent dicts with keys: name, scenario, description.
    """
    if not requirement or not requirement.strip():
        return []

    if use_llm:
        try:
            prompt = _REQUIREMENT_PARSER_PROMPT.format(requirement=requirement.strip())
            response_text = _call_llm(prompt)
            intents = _parse_llm_response(response_text)
            if intents:
                return intents
            # LLM returned empty/invalid → fall back to mock
        except Exception:
            pass  # Fall back to mock on any LLM error

    return _extract_intents_mock(requirement)


def parse_to_test_intents(
    requirement: str,
    *,
    use_llm: bool = False,
) -> list[TestIntent]:
    """Parse requirement and return TestIntent objects.

    Convenience wrapper that returns Pydantic models suitable for
    passing to execute_api_test().
    """
    raw = parse_requirement(requirement, use_llm=use_llm)
    return [
        TestIntent(
            name=item.get("name", f"intent_{i}"),
            scenario=item.get("scenario", "positive"),
        )
        for i, item in enumerate(raw)
    ]
