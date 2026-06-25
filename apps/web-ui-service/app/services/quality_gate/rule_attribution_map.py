"""规则→归因映射表 — 将质量门规则映射到 failure analysis 的分类体系。

复用 failure-analysis-agent 的 8 类 failure_category 和 6 类 failure_source。
多项目可扩展：新项目追加条目即可，无需改代码逻辑。
"""

from __future__ import annotations

from typing import Any

# 映射条目: {rule_id: {failure_category, failure_source, confidence}}
# failure_category: locator|assertion|timeout|environment|authentication|network|data|unknown
# failure_source: page_object|page_analysis|case_design|app_bug|environment|unknown
_RULE_ATTRIBUTION: dict[str, dict[str, Any]] = {
    "RULE_001": {"failure_category": "data", "failure_source": "case_design",
                 "confidence": 0.85},
    "RULE_002": {"failure_category": "data", "failure_source": "case_design",
                 "confidence": 0.90},
    "RULE_003": {"failure_category": "assertion", "failure_source": "case_design",
                 "confidence": 0.88},
    "RULE_004": {"failure_category": "data", "failure_source": "environment",
                 "confidence": 0.70},
    "RULE_005": {"failure_category": "data", "failure_source": "case_design",
                 "confidence": 0.75},
    "RULE_006": {"failure_category": "locator", "failure_source": "page_object",
                 "confidence": 0.92},
    "RULE_007": {"failure_category": "data", "failure_source": "case_design",
                 "confidence": 0.65},
    "RULE_008": {"failure_category": "assertion", "failure_source": "case_design",
                 "confidence": 0.90},
    "RULE_009": {"failure_category": "assertion", "failure_source": "page_object",
                 "confidence": 0.80},
    "RULE_010": {"failure_category": "data", "failure_source": "case_design",
                 "confidence": 0.85},
    "RULE_011": {"failure_category": "data", "failure_source": "case_design",
                 "confidence": 0.70},
    "RULE_012": {"failure_category": "assertion", "failure_source": "case_design",
                 "confidence": 0.75},
    "RULE_013": {"failure_category": "environment", "failure_source": "environment",
                 "confidence": 0.72},
    "RULE_014": {"failure_category": "locator", "failure_source": "page_object",
                 "confidence": 0.85},
    "RULE_015": {"failure_category": "assertion", "failure_source": "case_design",
                 "confidence": 0.75},
    "RULE_016": {"failure_category": "unknown", "failure_source": "unknown",
                 "confidence": 0.60},
    "RULE_017": {"failure_category": "unknown", "failure_source": "case_design",
                 "confidence": 0.55},
}


def resolve_attribution(rule_results: list[dict[str, Any]]) -> dict[str, Any]:
    """从规则结果列表计算聚合归因。

    返回 {failure_category, failure_source, confidence, triggered_rules}。
    多个规则触发时取最高置信度的归因。
    """
    triggered = [r for r in rule_results if isinstance(r, dict) and not r.get("passed", True)]
    if not triggered:
        return {
            "failure_category": "unknown",
            "failure_source": "unknown",
            "confidence": 0.0,
            "triggered_rules": [],
        }

    best = None
    best_conf = -1.0
    for r in triggered:
        rid = r.get("rule_id", "")
        attr = _RULE_ATTRIBUTION.get(rid)
        if attr and attr.get("confidence", 0) > best_conf:
            best = attr
            best_conf = attr["confidence"]

    if best is None:
        return {
            "failure_category": "unknown",
            "failure_source": "unknown",
            "confidence": 0.0,
            "triggered_rules": [r.get("rule_id", "") for r in triggered],
        }

    return {
        "failure_category": best["failure_category"],
        "failure_source": best["failure_source"],
        "confidence": best["confidence"],
        "triggered_rules": [r.get("rule_id", "") for r in triggered],
    }
