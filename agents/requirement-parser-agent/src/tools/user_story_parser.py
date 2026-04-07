from __future__ import annotations

import re
from typing import Any


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def parse_user_story(raw_text: str) -> dict[str, Any]:
    text = str(raw_text or "").strip()
    if not text:
        return {}

    normalized = _normalize(text)
    result: dict[str, Any] = {"raw": normalized}

    # English style: As a <role>, I want <goal>, so that <benefit>.
    match_en = re.search(
        r"as\s+(?:an?\s+)?(?P<role>.+?),\s*i\s+want\s+(?P<goal>.+?)(?:,\s*so\s+that\s+(?P<benefit>.+?))?(?:\.|$)",
        normalized,
        re.IGNORECASE,
    )
    if match_en:
        result["role"] = _normalize(match_en.group("role") or "")
        result["goal"] = _normalize(match_en.group("goal") or "")
        result["benefit"] = _normalize(match_en.group("benefit") or "")

    # Chinese style: 作为...，我希望...，以便...
    match_zh = re.search(r"作为(?P<role>.+?)[，,]\s*我(?:希望|想要|需要)(?P<goal>.+?)(?:[，,]\s*(?:以便|从而)(?P<benefit>.+?))?(?:。|$)", normalized)
    if match_zh:
        result["role"] = _normalize(match_zh.group("role") or "")
        result["goal"] = _normalize(match_zh.group("goal") or "")
        result["benefit"] = _normalize(match_zh.group("benefit") or "")

    acceptance = re.findall(r"(?:验收标准|AC|Acceptance Criteria)\s*[:：-]\s*([^。\n]+)", text, re.IGNORECASE)
    if acceptance:
        result["acceptance_criteria"] = [_normalize(item) for item in acceptance if _normalize(item)]

    role = _normalize(str(result.get("role", "")))
    goal = _normalize(str(result.get("goal", "")))
    benefit = _normalize(str(result.get("benefit", "")))
    if not role and not goal and not benefit:
        return {}
    return result

