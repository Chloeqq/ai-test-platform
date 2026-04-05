from __future__ import annotations

import re
from typing import Any


PAGE_KEYWORD_MAPPING: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("returnapply", ("returnapply", "return-apply", "refund", "return")),
    ("order", ("order",)),
    ("product", ("product", "catalog", "goods")),
    ("billing", ("billing", "invoice")),
    ("payment", ("payment",)),
    ("permission", ("permission", "auth", "role")),
)


def _page_candidates(text: str) -> list[str]:
    lowered = str(text or "").strip().lower()
    matches: list[str] = []
    for page, keywords in PAGE_KEYWORD_MAPPING:
        if any(keyword in lowered for keyword in keywords):
            matches.append(page)
    return list(dict.fromkeys(matches))


def parse_defect_ticket(defect_ticket: str = "") -> dict[str, Any]:
    raw_text = str(defect_ticket or "").strip()
    ticket_match = re.search(r"\b([A-Z][A-Z0-9]+-\d+)\b", raw_text)
    severity_match = re.search(r"\b(severity|priority)\s*[:=]\s*([a-zA-Z0-9_-]+)", raw_text, flags=re.IGNORECASE)
    component_match = re.search(r"\b(component|module)\s*[:=]\s*([a-zA-Z0-9_./-]+)", raw_text, flags=re.IGNORECASE)
    labels_match = re.search(r"\b(labels?)\s*[:=]\s*([a-zA-Z0-9_., -]+)", raw_text, flags=re.IGNORECASE)
    severity = severity_match.group(2).strip().lower() if severity_match else ""
    if not severity:
        lowered = raw_text.lower()
        if "critical" in lowered or "p0" in lowered:
            severity = "critical"
        elif "high" in lowered or "p1" in lowered:
            severity = "high"
        elif "medium" in lowered or "p2" in lowered:
            severity = "medium"
        elif "low" in lowered or "p3" in lowered:
            severity = "low"
    labels: list[str] = []
    if labels_match:
        labels = [
            item.strip().lower()
            for item in re.split(r"[,\s]+", labels_match.group(2).strip())
            if item.strip()
        ]
    reproduction_steps = [
        line.strip("- ").strip()
        for line in raw_text.splitlines()
        if line.strip().startswith(("-", "*", "1.", "2.", "3."))
    ]
    regression_priority_boost = 0
    if severity in {"critical", "high"}:
        regression_priority_boost += 2
    if any(label in {"regression", "prod", "security"} for label in labels):
        regression_priority_boost += 1
    business_rule_hints = []
    if raw_text:
        business_rule_hints.append(
            {
                "rule_id": f"defect.{ticket_match.group(1).lower()}" if ticket_match else "defect.unknown",
                "rule_type": "defect_ticket",
                "rule_text": raw_text[:200],
                "severity": severity or "medium",
                "source_ids": [ticket_match.group(1)] if ticket_match else [],
                "description": raw_text[:200],
            }
        )
    if any(token in raw_text.lower() for token in ("permission", "unauthorized", "forbidden", "只能查看自己的", "越权")):
        business_rule_hints.append(
            {
                "rule_id": "defect.permission_scope",
                "rule_type": "permission",
                "rule_text": "访问范围需要受权限限制。",
                "severity": severity or "high",
                "source_ids": [ticket_match.group(1)] if ticket_match else [],
                "description": "缺陷文本中包含权限或越权线索。",
            }
        )
    return {
        "source": "jira",
        "ticket_key": ticket_match.group(1) if ticket_match else "",
        "severity": severity,
        "component": component_match.group(2).strip() if component_match else "",
        "labels": labels[:10],
        "reproduction_steps": reproduction_steps[:10],
        "regression_priority_boost": regression_priority_boost,
        "page_candidates": _page_candidates(raw_text),
        "design_input_fragments": [raw_text[:240]] if raw_text else [],
        "business_rule_hints": business_rule_hints,
    }
