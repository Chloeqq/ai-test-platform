from __future__ import annotations

import re
from collections import Counter
from typing import Any


PAGE_KEYWORD_MAPPING: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("returnapply", ("returnapply", "return-apply", "refund")),
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


def _detect_changed_areas(text: str, file_path: str) -> list[str]:
    lowered = f"{file_path}\n{text}".lower()
    changed_areas: list[str] = []
    if any(token in lowered for token in ("/api/", "openapi", "swagger", "contract")):
        changed_areas.append("api_contract")
    if any(token in lowered for token in ("permission", "auth", "role", "token", "unauthorized", "forbidden")):
        changed_areas.append("permission")
    if any(token in lowered for token in ("selector", "locator", "button", "placeholder", "文本", "title")):
        changed_areas.append("ui_selector")
    if any(token in lowered for token in ("assert", "expect", "should", "校验", "断言")):
        changed_areas.append("assertion")
    if any(token in lowered for token in ("rule", "status", "state", "审批", "审核", "refund", "return")):
        changed_areas.append("business_rule")
    return list(dict.fromkeys(changed_areas))


def analyze_git_diff(git_diff: str = "", *, git_diff_path: str = "") -> dict[str, Any]:
    diff_text = str(git_diff or "").strip()
    path_hint = str(git_diff_path or "").strip()
    changed_files: list[str] = []
    changed_modules: Counter[str] = Counter()
    changed_symbols: list[str] = []
    page_candidates: list[str] = []
    changed_areas: list[str] = []
    risk_signals: list[dict[str, Any]] = []

    for line in diff_text.splitlines():
        text = str(line or "")
        file_match = re.match(r"^\+\+\+\s+b/(.+)$", text.strip())
        if file_match:
            file_path = file_match.group(1).strip()
            if file_path and file_path not in changed_files:
                changed_files.append(file_path)
                module_name = file_path.split("/", 1)[0]
                if module_name:
                    changed_modules[module_name] += 1
                page_candidates.extend(_page_candidates(file_path))
                changed_areas.extend(_detect_changed_areas("", file_path))
            continue
        symbol_match = re.match(r"^\+\s*(def|class)\s+([A-Za-z0-9_]+)", text)
        if symbol_match:
            changed_symbols.append(symbol_match.group(2))
            page_candidates.extend(_page_candidates(symbol_match.group(2)))
        if text.startswith("+") or text.startswith("-"):
            changed_areas.extend(_detect_changed_areas(text, ""))

    if path_hint and path_hint not in changed_files:
        changed_files.append(path_hint)
        module_name = path_hint.split("/", 1)[0]
        if module_name:
            changed_modules[module_name] += 1
        page_candidates.extend(_page_candidates(path_hint))
        changed_areas.extend(_detect_changed_areas("", path_hint))

    dedup_areas = list(dict.fromkeys(area for area in changed_areas if area))
    if "permission" in dedup_areas:
        risk_signals.append({"code": "permission_change", "severity": "high", "detail": "auth/permission related diff detected"})
    if "ui_selector" in dedup_areas:
        risk_signals.append({"code": "ui_selector_change", "severity": "medium", "detail": "selector/ui wording change detected"})
    if "api_contract" in dedup_areas:
        risk_signals.append({"code": "api_contract_change", "severity": "high", "detail": "api contract related diff detected"})
    if "business_rule" in dedup_areas:
        risk_signals.append({"code": "business_rule_change", "severity": "medium", "detail": "business rule diff detected"})

    return {
        "source": "git_diff",
        "changed_file_count": len(changed_files),
        "changed_files": changed_files[:20],
        "changed_modules": [item for item, _count in changed_modules.most_common(10)],
        "changed_symbols": changed_symbols[:20],
        "changed_areas": dedup_areas[:10],
        "risk_signals": risk_signals[:10],
        "page_candidates": list(dict.fromkeys(page_candidates))[:5],
        "design_input_fragments": changed_files[:8] + changed_symbols[:8],
    }
