# mypy: ignore-errors
"""多源需求支撑：OpenAPI、Git diff、Jira 等输入的归一化与页面对象推断。"""

from __future__ import annotations

from typing import Any, Callable


LoadRuntimeModule = Callable[..., Any]
InferPageFromText = Callable[..., str]
BuildSourceId = Callable[..., str]
SlugToken = Callable[..., str]
DedupStrings = Callable[[list[Any]], list[str]]


class MultisourceSupport:
    """合并多源上下文，生成 source_inputs、覆盖矩阵与变更影响摘要。"""

    def __init__(
        self,
        *,
        load_runtime_module: LoadRuntimeModule,
        infer_page_from_text: InferPageFromText,
        build_source_id: BuildSourceId,
        slug_token: SlugToken,
        dedup_strings: DedupStrings,
        logger: Any,
        tools_root: Any,
    ) -> None:
        self._load_runtime_module = load_runtime_module
        self._infer_page_from_text = infer_page_from_text
        self._build_source_id = build_source_id
        self._slug_token = slug_token
        self._dedup_strings = dedup_strings
        self._logger = logger
        self._tools_root = tools_root

    def build_fallback_multisource_context(
        self,
        *,
        input_sources: list[dict[str, Any]] | None = None,
        openapi_spec: dict[str, Any] | None = None,
        openapi_url: str = "",
        git_diff: str = "",
        git_diff_path: str = "",
        defect_ticket: str = "",
    ) -> dict[str, Any]:
        """在无 LLM 解析结果时，从各原始输入构建多源上下文字典。"""
        source_inputs: list[dict[str, Any]] = []
        page_candidates: list[str] = []
        page_candidate_signals: list[dict[str, Any]] = []
        parameter_constraints: list[dict[str, Any]] = []
        changed_files: list[str] = []
        changed_modules: list[str] = []
        changed_areas: list[str] = []
        business_rules: list[dict[str, Any]] = []
        design_input_fragments: list[str] = []
        risk_signals: list[dict[str, Any]] = []

        for item in input_sources if isinstance(input_sources, list) else []:
            if not isinstance(item, dict):
                continue
            source_type = str(item.get("source_type", "")).strip() or "input_source"
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            source_inputs.append(
                {
                    "source_type": source_type,
                    "summary": content[:120],
                    "reference_ids": [],
                }
            )
            inferred_page = self._infer_page_from_text(requirement=content)
            if inferred_page and inferred_page != "product":
                page_candidates.append(inferred_page)
                page_candidate_signals.append(
                    {
                        "page": inferred_page,
                        "source_type": source_type,
                        "reason": "input source keyword matched page intent",
                        "score": 32,
                    }
                )

        if isinstance(openapi_spec, dict) and openapi_spec:
            try:
                module = self._load_runtime_module(
                    cache_key="ai_orchestrator_openapi_parser_tool",
                    module_path=self._tools_root / "openapi-parser.tool.py",
                )
                parsed = module.parse_openapi_spec(openapi_spec, openapi_url=openapi_url)
                page_candidates.extend(parsed.get("page_candidates") if isinstance(parsed.get("page_candidates"), list) else [])
                for index, candidate in enumerate(parsed.get("page_candidates") if isinstance(parsed.get("page_candidates"), list) else []):
                    text = str(candidate).strip()
                    if not text:
                        continue
                    page_candidate_signals.append(
                        {
                            "page": text,
                            "source_type": "openapi",
                            "reason": "OpenAPI endpoint/resource match",
                            "score": 90 - index * 5,
                        }
                    )
                parameter_constraints.extend(
                    [item for item in (parsed.get("parameter_constraints") or []) if isinstance(item, dict)]
                )
                changed_areas.extend([str(item).strip() for item in (parsed.get("changed_areas") or []) if str(item).strip()])
                risk_signals.extend([item for item in (parsed.get("risk_signals") or []) if isinstance(item, dict)])
                design_input_fragments.extend(
                    [str(item).strip() for item in (parsed.get("design_input_fragments") or []) if str(item).strip()]
                )
                source_inputs.append(
                    {
                        "source_type": "openapi",
                        "summary": f"OpenAPI endpoints={int(parsed.get('endpoint_count', 0) or 0)} title={str(parsed.get('api_title', '')).strip() or '-'}",
                        "reference_ids": [str(item.get("path", "")).strip() for item in (parsed.get("endpoints") or [])[:3] if isinstance(item, dict)],
                    }
                )
            except Exception as exc:
                self._logger.warning("openapi parser tool unavailable in fallback path: %s", exc)

        if git_diff.strip() or git_diff_path.strip():
            try:
                module = self._load_runtime_module(
                    cache_key="ai_orchestrator_git_diff_tool",
                    module_path=self._tools_root / "git-diff.tool.py",
                )
                parsed = module.analyze_git_diff(git_diff, git_diff_path=git_diff_path)
                page_candidates.extend(parsed.get("page_candidates") if isinstance(parsed.get("page_candidates"), list) else [])
                for index, candidate in enumerate(parsed.get("page_candidates") if isinstance(parsed.get("page_candidates"), list) else []):
                    text = str(candidate).strip()
                    if not text:
                        continue
                    page_candidate_signals.append(
                        {
                            "page": text,
                            "source_type": "git_diff",
                            "reason": "Git diff path/symbol match",
                            "score": 72 - index * 4,
                        }
                    )
                changed_files.extend([str(item).strip() for item in (parsed.get("changed_files") or []) if str(item).strip()])
                changed_modules.extend([str(item).strip() for item in (parsed.get("changed_modules") or []) if str(item).strip()])
                changed_areas.extend([str(item).strip() for item in (parsed.get("changed_areas") or []) if str(item).strip()])
                risk_signals.extend([item for item in (parsed.get("risk_signals") or []) if isinstance(item, dict)])
                design_input_fragments.extend(
                    [str(item).strip() for item in (parsed.get("design_input_fragments") or []) if str(item).strip()]
                )
                source_inputs.append(
                    {
                        "source_type": "git_diff",
                        "summary": f"changed_files={int(parsed.get('changed_file_count', 0) or 0)}",
                        "reference_ids": changed_files[:3],
                    }
                )
            except Exception as exc:
                self._logger.warning("git diff tool unavailable in fallback path: %s", exc)

        if defect_ticket.strip():
            try:
                module = self._load_runtime_module(
                    cache_key="ai_orchestrator_jira_reader_tool",
                    module_path=self._tools_root / "jira-reader.tool.py",
                )
                parsed = module.parse_defect_ticket(defect_ticket)
                page_candidates.extend(parsed.get("page_candidates") if isinstance(parsed.get("page_candidates"), list) else [])
                for index, candidate in enumerate(parsed.get("page_candidates") if isinstance(parsed.get("page_candidates"), list) else []):
                    text = str(candidate).strip()
                    if not text:
                        continue
                    page_candidate_signals.append(
                        {
                            "page": text,
                            "source_type": "defect_ticket",
                            "reason": "Defect ticket symptom/component match",
                            "score": 64 - index * 4,
                        }
                    )
                business_rules.extend(
                    [item for item in (parsed.get("business_rule_hints") or []) if isinstance(item, dict)]
                )
                if int(parsed.get("regression_priority_boost", 0) or 0) > 0:
                    risk_signals.append(
                        {
                            "code": "defect_priority_boost",
                            "severity": "medium" if int(parsed.get("regression_priority_boost", 0) or 0) <= 1 else "high",
                            "detail": f"regression_priority_boost={int(parsed.get('regression_priority_boost', 0) or 0)}",
                        }
                    )
                design_input_fragments.extend(
                    [str(item).strip() for item in (parsed.get("design_input_fragments") or []) if str(item).strip()]
                )
                source_inputs.append(
                    {
                        "source_type": "defect_ticket",
                        "summary": (
                            f"{str(parsed.get('ticket_key', '')).strip() or 'ticket'} severity={str(parsed.get('severity', '')).strip() or '-'}"
                        ),
                        "reference_ids": [str(parsed.get("ticket_key", "")).strip()] if str(parsed.get("ticket_key", "")).strip() else [],
                    }
                )
            except Exception as exc:
                self._logger.warning("jira reader tool unavailable in fallback path: %s", exc)

        return {
            "source_inputs": source_inputs[:20],
            "page_candidates": [item for item in dict.fromkeys(str(item).strip() for item in page_candidates if str(item).strip())][:5],
            "page_candidate_signals": [item for item in page_candidate_signals if isinstance(item, dict)][:20],
            "parameter_constraints": parameter_constraints[:20],
            "changed_files": [item for item in dict.fromkeys(changed_files) if item][:20],
            "changed_modules": [item for item in dict.fromkeys(changed_modules) if item][:20],
            "changed_areas": [item for item in dict.fromkeys(changed_areas) if item][:20],
            "business_rules": business_rules[:10],
            "risk_signals": risk_signals[:12],
            "design_input_fragments": [item for item in dict.fromkeys(design_input_fragments) if item][:20],
        }

    def normalize_multisource_source_inputs(
        self,
        source_inputs: list[dict[str, Any]] | None,
    ) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
        normalized: list[dict[str, Any]] = []
        source_ids_by_type: dict[str, list[str]] = {}
        seen_keys: set[tuple[str, str, tuple[str, ...]]] = set()
        for index, item in enumerate(source_inputs if isinstance(source_inputs, list) else [], start=1):
            if not isinstance(item, dict):
                continue
            source_type = str(item.get("source_type", "")).strip() or "input_source"
            summary = str(item.get("summary", "")).strip() or str(item.get("content", "")).strip()
            reference_ids = [
                str(value).strip()
                for value in (item.get("reference_ids") or [])
                if str(value).strip()
            ]
            source_id = str(item.get("source_id", "")).strip() or self._build_source_id(
                source_type=source_type,
                hint=reference_ids[0] if reference_ids else (summary[:48] or f"{source_type}-{index:02d}"),
                index=index,
            )
            dedup_key = (source_type, summary, tuple(reference_ids))
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)
            normalized_item = {
                "source_id": source_id,
                "source_type": source_type,
                "summary": summary[:180],
                "reference_ids": reference_ids[:10],
                "metadata": item.get("metadata") if isinstance(item.get("metadata"), dict) else {},
            }
            normalized.append(normalized_item)
            source_ids_by_type.setdefault(source_type, []).append(source_id)
        return normalized, source_ids_by_type

    def rank_page_candidates(
        self,
        *,
        fallback_context: dict[str, Any],
        source_inputs: list[dict[str, Any]],
        current_page: str = "",
    ) -> list[dict[str, Any]]:
        priority = {
            "openapi": 5,
            "git_diff": 4,
            "defect_ticket": 3,
            "prd": 2,
            "user_story": 2,
            "input_source": 1,
        }
        source_ids_by_type: dict[str, list[str]] = {}
        for item in source_inputs:
            if not isinstance(item, dict):
                continue
            source_type = str(item.get("source_type", "")).strip()
            source_id = str(item.get("source_id", "")).strip()
            if source_type and source_id:
                source_ids_by_type.setdefault(source_type, []).append(source_id)

        raw_signals = fallback_context.get("page_candidate_signals") if isinstance(fallback_context.get("page_candidate_signals"), list) else []
        if not raw_signals:
            raw_signals = [
                {"page": item, "source_type": "input_source", "reason": "generic candidate", "score": 24 - index * 2}
                for index, item in enumerate(fallback_context.get("page_candidates", []) if isinstance(fallback_context.get("page_candidates"), list) else [])
            ]

        aggregates: dict[str, dict[str, Any]] = {}
        for index, signal in enumerate(raw_signals):
            if not isinstance(signal, dict):
                continue
            page = str(signal.get("page", "")).strip()
            source_type = str(signal.get("source_type", "")).strip() or "input_source"
            if not page:
                continue
            priority_score = priority.get(source_type, 1) * 10
            entry = aggregates.setdefault(
                page,
                {
                    "page": page,
                    "score": 0,
                    "vote_count": 0,
                    "source_types": [],
                    "source_ids": [],
                    "reasons": [],
                    "source_priority_score": 0,
                    "source_priority_rules": [],
                },
            )
            raw_score = int(signal.get("score", 0) or 0)
            score = max(raw_score, priority_score - index)
            if current_page and page == current_page:
                score += 8
            entry["score"] += score
            entry["vote_count"] += 1
            entry["source_priority_score"] += priority_score
            if source_type not in entry["source_types"]:
                entry["source_types"].append(source_type)
                entry["source_priority_rules"].append(
                    {
                        "source_type": source_type,
                        "priority_weight": priority.get(source_type, 1),
                        "reason": f"{source_type} source priority={priority.get(source_type, 1)}",
                    }
                )
            for source_id in source_ids_by_type.get(source_type, []):
                if source_id not in entry["source_ids"]:
                    entry["source_ids"].append(source_id)
            reason = str(signal.get("reason", "")).strip()
            if reason and reason not in entry["reasons"]:
                entry["reasons"].append(reason)

        ranked = list(aggregates.values())
        max_score = max((int(item.get("score", 0) or 0) for item in ranked), default=0)
        for item in ranked:
            item["confidence"] = round(
                min(1.0, (int(item.get("score", 0) or 0) / max(1, max_score))) if max_score > 0 else 0.0,
                3,
            )
        ranked.sort(key=lambda item: (-int(item.get("score", 0) or 0), -int(item.get("vote_count", 0) or 0), str(item.get("page", ""))))
        return ranked

    def resolve_source_ids(
        self,
        *,
        raw_source_ids: list[Any] | None,
        source_ids_by_type: dict[str, list[str]],
        fallback_types: list[str] | None = None,
        fallback_to_all: bool = False,
    ) -> list[str]:
        resolved: list[str] = []
        for item in raw_source_ids if isinstance(raw_source_ids, list) else []:
            value = str(item or "").strip()
            if not value:
                continue
            if "." in value:
                resolved.append(value)
                continue
            if value in source_ids_by_type:
                resolved.extend(source_ids_by_type.get(value, []))
            else:
                resolved.append(value)
        if not resolved and fallback_types:
            for source_type in fallback_types:
                resolved.extend(source_ids_by_type.get(source_type, []))
        if not resolved and fallback_to_all:
            for rows in source_ids_by_type.values():
                resolved.extend(rows)
        return self._dedup_strings(resolved)

    def normalize_business_rules(
        self,
        *,
        business_rules: list[dict[str, Any]] | None,
        source_ids_by_type: dict[str, list[str]],
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(business_rules if isinstance(business_rules, list) else [], start=1):
            if not isinstance(item, dict):
                continue
            rule_type = str(item.get("rule_type", "")).strip() or str(item.get("name", "")).strip() or "rule"
            rule_text = (
                str(item.get("rule_text", "")).strip()
                or str(item.get("text", "")).strip()
                or str(item.get("description", "")).strip()
            )
            if not rule_text:
                continue
            source_ids = self.resolve_source_ids(
                raw_source_ids=item.get("source_ids"),
                source_ids_by_type=source_ids_by_type,
                fallback_types=["defect_ticket", "prd", "openapi"],
                fallback_to_all=True,
            )
            normalized.append(
                {
                    "rule_id": str(item.get("rule_id", "")).strip() or f"rule.{self._slug_token(rule_type)}.{index:02d}",
                    "rule_type": rule_type,
                    "rule_text": rule_text[:240],
                    "severity": str(item.get("severity", "")).strip() or "medium",
                    "source_ids": source_ids,
                    "description": str(item.get("description", "")).strip() or rule_text[:240],
                    "metadata": item.get("metadata") if isinstance(item.get("metadata"), dict) else {},
                }
            )
        return normalized

    def normalize_test_intents_for_multisource(
        self,
        *,
        intents: list[dict[str, Any]] | None,
        source_ids_by_type: dict[str, list[str]],
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(intents if isinstance(intents, list) else [], start=1):
            if not isinstance(item, dict):
                continue
            intent_type = str(item.get("intent_type", "")).strip().lower() or "functional"
            fallback_types: list[str] = []
            if intent_type == "api":
                fallback_types = ["openapi"]
            elif intent_type == "regression":
                fallback_types = ["git_diff", "defect_ticket"]
            source_ids = self.resolve_source_ids(
                raw_source_ids=item.get("source_ids"),
                source_ids_by_type=source_ids_by_type,
                fallback_types=fallback_types,
                fallback_to_all=True,
            )
            normalized.append(
                {
                    **item,
                    "intent_id": str(item.get("intent_id", "")).strip() or f"intent-{index:02d}",
                    "intent_type": intent_type,
                    "title": str(item.get("title", "")).strip() or f"intent-{index:02d}",
                    "priority": str(item.get("priority", "")).strip() or "P1",
                    "source_ids": source_ids,
                    "dependencies": self._dedup_strings(item.get("dependencies") if isinstance(item.get("dependencies"), list) else []),
                    "steps_hint": [str(value).strip() for value in (item.get("steps_hint") or []) if str(value).strip()],
                }
            )
        return normalized

    def normalize_coverage_matrix_for_multisource(
        self,
        *,
        coverage_matrix: list[dict[str, Any]] | None,
        test_intents: list[dict[str, Any]],
        source_ids_by_type: dict[str, list[str]],
        requirement_text: str,
    ) -> list[dict[str, Any]]:
        intent_map = {
            str(item.get("intent_id", "")).strip(): item
            for item in test_intents
            if isinstance(item, dict) and str(item.get("intent_id", "")).strip()
        }
        normalized_rows: list[dict[str, Any]] = []
        rows = coverage_matrix if isinstance(coverage_matrix, list) and coverage_matrix else [{}]
        total_source_input_count = sum(len(values) for values in source_ids_by_type.values())
        for index, row in enumerate(rows, start=1):
            item = row if isinstance(row, dict) else {}
            intent_ids = self._dedup_strings(item.get("intent_ids") if isinstance(item.get("intent_ids"), list) else list(intent_map.keys()))
            linked_source_ids: list[str] = []
            for intent_id in intent_ids:
                intent = intent_map.get(intent_id, {})
                linked_source_ids.extend(intent.get("source_ids") if isinstance(intent.get("source_ids"), list) else [])
            linked_source_ids = self.resolve_source_ids(
                raw_source_ids=item.get("source_ids"),
                source_ids_by_type=source_ids_by_type,
                fallback_to_all=not linked_source_ids,
            ) or self._dedup_strings(linked_source_ids)
            traceability_status = str(item.get("traceability_status", "")).strip().lower()
            if not traceability_status:
                if intent_ids and linked_source_ids:
                    traceability_status = "partial" if total_source_input_count > 1 and len(linked_source_ids) < total_source_input_count else "covered"
                elif intent_ids or linked_source_ids:
                    traceability_status = "partial"
                else:
                    traceability_status = "gap"
            primary_source_id = linked_source_ids[0] if linked_source_ids else ""
            primary_source_type = primary_source_id.split(".", 1)[0] if primary_source_id else ""
            normalized_rows.append(
                {
                    "requirement_id": str(item.get("requirement_id", "")).strip() or f"REQ-{index:03d}",
                    "requirement_text": str(item.get("requirement_text", "")).strip() or requirement_text[:200],
                    "intent_ids": intent_ids,
                    "source_ids": linked_source_ids,
                    "source_id": primary_source_id,
                    "source_type": str(item.get("source_type", "")).strip() or primary_source_type or ("multi_source" if len(linked_source_ids) > 1 else "manual"),
                    "coverage_ratio": float(item.get("coverage_ratio", 1.0 if traceability_status == "covered" else (0.5 if traceability_status == "partial" else 0.0)) or 0.0),
                    "traceability_status": traceability_status,
                    "explanation": str(item.get("explanation", "")).strip() or ("linked to source inputs" if traceability_status == "covered" else "missing source or intent links"),
                }
            )
        return normalized_rows

    def normalize_change_impact_for_multisource(
        self,
        *,
        change_impact: dict[str, Any] | None,
        fallback_context: dict[str, Any],
        test_intents: list[dict[str, Any]],
        source_ids_by_type: dict[str, list[str]],
    ) -> dict[str, Any]:
        raw = change_impact if isinstance(change_impact, dict) else {}
        changed_files = self._dedup_strings((raw.get("changed_files") if isinstance(raw.get("changed_files"), list) else []) + fallback_context.get("changed_files", []))
        changed_modules = self._dedup_strings((raw.get("changed_modules") if isinstance(raw.get("changed_modules"), list) else []) + fallback_context.get("changed_modules", []))
        changed_areas = self._dedup_strings((raw.get("changed_areas") if isinstance(raw.get("changed_areas"), list) else []) + fallback_context.get("changed_areas", []))
        affected_intent_ids = self._dedup_strings(raw.get("affected_intent_ids") if isinstance(raw.get("affected_intent_ids"), list) else [])
        if not affected_intent_ids and changed_files:
            affected_intent_ids = [
                str(item.get("intent_id", "")).strip()
                for item in test_intents
                if isinstance(item, dict)
                and str(item.get("intent_type", "")).strip().lower() in {"regression", "api", "functional"}
                and str(item.get("intent_id", "")).strip()
            ][:10]
        impacted_source_ids = self.resolve_source_ids(
            raw_source_ids=raw.get("impacted_source_ids"),
            source_ids_by_type=source_ids_by_type,
            fallback_types=["git_diff", "defect_ticket", "openapi"],
            fallback_to_all=False,
        )
        risk_signals_raw = raw.get("risk_signals") if isinstance(raw.get("risk_signals"), list) else []
        risk_signals = [item for item in risk_signals_raw if isinstance(item, dict)]
        risk_signals.extend(item for item in fallback_context.get("risk_signals", []) if isinstance(item, dict))
        dedup_signals: list[dict[str, Any]] = []
        seen_codes: set[str] = set()
        for signal in risk_signals:
            code = str(signal.get("code", "")).strip()
            if not code or code in seen_codes:
                continue
            seen_codes.add(code)
            dedup_signals.append(signal)
        impact_score = raw.get("impact_score")
        try:
            impact_score_value = int(impact_score or 0)
        except Exception:
            impact_score_value = 0
        derived_score = min(100, len(changed_files) * 10 + len(changed_areas) * 12 + len(dedup_signals) * 10 + len(affected_intent_ids) * 4)
        impact_score_value = max(impact_score_value, derived_score)
        factors: list[dict[str, Any]] = []
        for area in changed_areas:
            weight = 14 if area in {"api_contract", "permission"} else 10
            factors.append({"factor": area, "weight": weight, "reason": f"changed_area={area}"})
        for signal in dedup_signals:
            code = str(signal.get("code", "")).strip()
            if not code:
                continue
            severity = str(signal.get("severity", "")).strip().lower()
            weight = 16 if severity == "high" else (11 if severity == "medium" else 7)
            factors.append({"factor": code, "weight": weight, "reason": str(signal.get("detail", "")).strip() or code})
        if changed_files:
            factors.append({"factor": "changed_files", "weight": min(len(changed_files) * 4, 16), "reason": f"changed_files={len(changed_files)}"})
        if affected_intent_ids:
            factors.append({"factor": "affected_intents", "weight": min(len(affected_intent_ids) * 3, 15), "reason": f"affected_intents={len(affected_intent_ids)}"})
        factors.sort(key=lambda item: (-int(item.get("weight", 0) or 0), str(item.get("factor", ""))))
        recommended_regression_scope: list[str] = []
        if "api_contract" in changed_areas:
            recommended_regression_scope.append("api_contract_regression")
        if "permission" in changed_areas:
            recommended_regression_scope.append("permission_smoke")
        if "ui_selector" in changed_areas:
            recommended_regression_scope.append("ui_selector_smoke")
        if "business_rule" in changed_areas or "assertion" in changed_areas:
            recommended_regression_scope.append("business_rule_regression")
        why_manual_review = ""
        if any(area in {"permission", "api_contract"} for area in changed_areas):
            why_manual_review = "变更涉及权限或 API 契约，建议人工复核关键主链。"
        elif len(dedup_signals) >= 3:
            why_manual_review = "变更信号较多，建议人工复核回归范围。"
        why_blocked = ""
        if "permission" in changed_areas:
            why_blocked = "权限范围变更会直接影响主链放行，建议优先阻断校验。"
        elif "api_contract" in changed_areas and len(changed_files) >= 2:
            why_blocked = "接口契约变更范围较广，建议收紧回归放行条件。"
        return {
            "changed_modules": changed_modules,
            "changed_files": changed_files,
            "changed_areas": changed_areas,
            "affected_intent_ids": affected_intent_ids,
            "impacted_source_ids": impacted_source_ids,
            "suggested_regression_scope": self._dedup_strings(raw.get("suggested_regression_scope") if isinstance(raw.get("suggested_regression_scope"), list) else []) or recommended_regression_scope,
            "risk_hint": str(raw.get("risk_hint", "")).strip() or ("multi_source" if dedup_signals else "none"),
            "impact_score": impact_score_value,
            "risk_signals": dedup_signals[:12],
            "factors": factors[:12],
            "top_factor": factors[0] if factors else {},
            "recommended_regression_scope": recommended_regression_scope,
            "why_manual_review": why_manual_review,
            "why_blocked": why_blocked,
            "explanation": str(raw.get("explanation", "")).strip() or f"changed_files={len(changed_files)}, changed_areas={len(changed_areas)}, signals={len(dedup_signals)}, top_factor={str(factors[0].get('factor', '-')) if factors else '-'}",
        }

    def ensure_change_impact_explainability(self, change_impact: dict[str, Any] | None) -> dict[str, Any]:
        raw = dict(change_impact) if isinstance(change_impact, dict) else {}
        if raw.get("top_factor") and raw.get("factors") and raw.get("recommended_regression_scope"):
            return raw
        normalized = self.normalize_change_impact_for_multisource(
            change_impact=raw,
            fallback_context={},
            test_intents=[],
            source_ids_by_type={},
        )
        return {
            **normalized,
            **raw,
            "factors": raw.get("factors") if isinstance(raw.get("factors"), list) and raw.get("factors") else normalized.get("factors", []),
            "top_factor": raw.get("top_factor") if isinstance(raw.get("top_factor"), dict) and raw.get("top_factor") else normalized.get("top_factor", {}),
            "recommended_regression_scope": raw.get("recommended_regression_scope") if isinstance(raw.get("recommended_regression_scope"), list) and raw.get("recommended_regression_scope") else normalized.get("recommended_regression_scope", []),
            "why_manual_review": str(raw.get("why_manual_review", "")).strip() or str(normalized.get("why_manual_review", "")).strip(),
            "why_blocked": str(raw.get("why_blocked", "")).strip() or str(normalized.get("why_blocked", "")).strip(),
            "explanation": str(raw.get("explanation", "")).strip() or str(normalized.get("explanation", "")).strip(),
        }

    def build_page_resolution_summary(
        self,
        *,
        page: str,
        fallback_context: dict[str, Any],
        source_inputs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        ranked_candidates = self.rank_page_candidates(
            fallback_context=fallback_context,
            source_inputs=source_inputs,
            current_page=page,
        )
        candidates = [str(item.get("page", "")).strip() for item in ranked_candidates if str(item.get("page", "")).strip()]
        chosen = ranked_candidates[0] if ranked_candidates else {}
        rejected = ranked_candidates[1:4]
        chosen_source_id = chosen.get("source_ids", [])[0] if isinstance(chosen.get("source_ids"), list) and chosen.get("source_ids") else ""
        chosen_source_type = chosen.get("source_types", [])[0] if isinstance(chosen.get("source_types"), list) and chosen.get("source_types") else ""
        reason = "selected from multi-source candidates" if candidates else "fallback inferred from requirement text"
        if len(candidates) > 1:
            reason = "selected from multi-source conflict candidates"
        chosen_page = page or str(chosen.get("page", "")).strip()
        chosen_reason_parts = []
        if isinstance(chosen, dict):
            chosen_reason_parts.extend(chosen.get("reasons", [])[:3] if isinstance(chosen.get("reasons"), list) else [])
            if chosen.get("source_priority_rules"):
                rule = chosen.get("source_priority_rules")[0]
                if isinstance(rule, dict):
                    chosen_reason_parts.append(str(rule.get("reason", "")).strip())
            if str(chosen.get("confidence", "")).strip():
                chosen_reason_parts.append(f"confidence={chosen.get('confidence')}")
        return {
            "page": page,
            "page_candidates": candidates[:5],
            "candidate_details": ranked_candidates[:5],
            "conflict_detected": len(candidates) > 1,
            "conflict_candidates": [item.get("page") for item in rejected if str(item.get("page", "")).strip()],
            "conflict_candidate_details": [
                {
                    "page": str(item.get("page", "")).strip(),
                    "score": int(item.get("score", 0) or 0),
                    "vote_count": int(item.get("vote_count", 0) or 0),
                    "source_types": item.get("source_types", []) if isinstance(item.get("source_types"), list) else [],
                    "source_ids": item.get("source_ids", []) if isinstance(item.get("source_ids"), list) else [],
                    "confidence": float(item.get("confidence", 0.0) or 0.0),
                    "reasons": item.get("reasons", []) if isinstance(item.get("reasons"), list) else [],
                }
                for item in rejected
                if isinstance(item, dict) and str(item.get("page", "")).strip()
            ],
            "chosen_source_id": chosen_source_id,
            "chosen_source_type": chosen_source_type,
            "chosen_candidate": {
                "page": chosen_page,
                "score": int(chosen.get("score", 0) or 0) if isinstance(chosen, dict) else 0,
                "vote_count": int(chosen.get("vote_count", 0) or 0) if isinstance(chosen, dict) else 0,
                "source_types": chosen.get("source_types", []) if isinstance(chosen, dict) and isinstance(chosen.get("source_types"), list) else [],
                "source_ids": chosen.get("source_ids", []) if isinstance(chosen, dict) and isinstance(chosen.get("source_ids"), list) else [],
                "confidence": float(chosen.get("confidence", 0.0) or 0.0) if isinstance(chosen, dict) else 0.0,
            },
            "resolution_strategy": "source_priority_then_score" if len(candidates) > 1 else "single_candidate_or_fallback",
            "source_priority_rules": [
                {"source_type": "openapi", "priority_weight": 5},
                {"source_type": "git_diff", "priority_weight": 4},
                {"source_type": "defect_ticket", "priority_weight": 3},
                {"source_type": "prd", "priority_weight": 2},
                {"source_type": "user_story", "priority_weight": 2},
                {"source_type": "input_source", "priority_weight": 1},
            ],
            "reason": reason,
            "chosen_reason": "; ".join(item for item in chosen_reason_parts if item),
            "rejected_reasons": [
                {
                    "page": str(item.get("page", "")).strip(),
                    "reason": (
                        f"score={int(item.get('score', 0) or 0)}，低于已选页面 {chosen_page or '-'}；"
                        f"source_types={','.join(item.get('source_types', [])) if isinstance(item.get('source_types'), list) else '-'}"
                    ),
                }
                for item in rejected
                if isinstance(item, dict) and str(item.get("page", "")).strip()
            ],
        }

    def build_test_point_traceability_summary(
        self,
        *,
        requirement_spec: dict[str, Any],
        test_points: dict[str, Any],
    ) -> dict[str, Any]:
        source_inputs = requirement_spec.get("source_inputs") if isinstance(requirement_spec.get("source_inputs"), list) else []
        source_type_distribution: dict[str, int] = {}
        source_ids: list[str] = []
        for item in source_inputs:
            if not isinstance(item, dict):
                continue
            source_type = str(item.get("source_type", "")).strip() or "unknown"
            source_type_distribution[source_type] = source_type_distribution.get(source_type, 0) + 1
            source_id = str(item.get("source_id", "")).strip()
            if source_id:
                source_ids.append(source_id)
        points = test_points.get("points") if isinstance(test_points.get("points"), list) else []
        linked_point_count = sum(1 for item in points if isinstance(item, dict) and isinstance(item.get("source_ids"), list) and bool(item.get("source_ids")))
        coverage = requirement_spec.get("coverage_matrix") if isinstance(requirement_spec.get("coverage_matrix"), list) else []
        gap_count = sum(1 for item in coverage if isinstance(item, dict) and str(item.get("traceability_status", "")).strip().lower() == "gap")
        partial_count = sum(1 for item in coverage if isinstance(item, dict) and str(item.get("traceability_status", "")).strip().lower() == "partial")
        covered_count = sum(1 for item in coverage if isinstance(item, dict) and str(item.get("traceability_status", "")).strip().lower() == "covered")
        referenced_source_ids = self._dedup_strings(
            [
                str(source_id).strip()
                for item in points
                if isinstance(item, dict)
                for source_id in (item.get("source_ids") or [])
                if str(source_id).strip()
            ]
        )
        orphan_point_count = sum(
            1
            for item in points
            if isinstance(item, dict)
            and str(item.get("point_type", "")).strip().lower() != "precondition"
            and not [str(source_id).strip() for source_id in (item.get("source_ids") or []) if str(source_id).strip()]
        )
        orphan_point_keys = [
            str(item.get("key", "")).strip()
            for item in points
            if isinstance(item, dict)
            and str(item.get("point_type", "")).strip().lower() != "precondition"
            and not [str(source_id).strip() for source_id in (item.get("source_ids") or []) if str(source_id).strip()]
            and str(item.get("key", "")).strip()
        ]
        changed_areas = self._dedup_strings(
            requirement_spec.get("change_impact", {}).get("changed_areas", [])
            if isinstance(requirement_spec.get("change_impact"), dict)
            else []
        )
        intent_types = {
            str(item.get("intent_type", "")).strip().lower()
            for item in (requirement_spec.get("test_intents") or [])
            if isinstance(item, dict) and str(item.get("intent_type", "")).strip()
        }
        mapped_changed_areas: set[str] = set()
        if "api" in intent_types:
            mapped_changed_areas.add("api_contract")
        if "regression" in intent_types or "functional" in intent_types:
            mapped_changed_areas.update({"business_rule", "assertion", "ui_selector"})
        if any(
            isinstance(rule, dict) and str(rule.get("rule_type", "")).strip().lower() == "permission"
            for rule in (requirement_spec.get("business_rules") or [])
        ):
            mapped_changed_areas.add("permission")
        unmapped_changed_areas = [area for area in changed_areas if area not in mapped_changed_areas]
        source_covered_count = len([source_id for source_id in source_ids if source_id in referenced_source_ids])
        source_gap_count = max(len(source_ids) - source_covered_count, 0)
        partial_source_ids = [
            source_id
            for source_id in source_ids
            if source_id in referenced_source_ids
            and len(source_ids) > 1
            and source_gap_count > 0
        ]
        uncovered_source_ids = [source_id for source_id in source_ids if source_id not in referenced_source_ids]
        coverage_row_count = len(coverage)
        coverage_score = (covered_count + partial_count * 0.5) / max(1, coverage_row_count)
        source_score = source_covered_count / max(1, len(source_ids)) if source_ids else 1.0
        orphan_penalty = orphan_point_count / max(1, len(points)) if points else 0.0
        area_penalty = len(unmapped_changed_areas) / max(1, len(changed_areas)) if changed_areas else 0.0
        traceability_completeness = max(
            0.0,
            min(
                1.0,
                round(
                    coverage_score * 0.55
                    + source_score * 0.3
                    + (1 - orphan_penalty) * 0.1
                    + (1 - area_penalty) * 0.05,
                    3,
                ),
            ),
        )
        intent_coverage_status = "covered"
        if orphan_point_count > 0:
            intent_coverage_status = "orphan"
        elif gap_count > 0:
            intent_coverage_status = "gap"
        elif partial_count > 0:
            intent_coverage_status = "partial"
        source_coverage_status = "covered" if source_gap_count == 0 else ("partial" if source_covered_count > 0 else "gap")
        return {
            "source_input_count": len(source_inputs),
            "source_type_distribution": dict(sorted(source_type_distribution.items())),
            "intent_count": len(requirement_spec.get("test_intents") if isinstance(requirement_spec.get("test_intents"), list) else []),
            "point_count": len(points),
            "linked_point_count": linked_point_count,
            "coverage_row_count": coverage_row_count,
            "gap_count": gap_count,
            "gap_point_count": gap_count + orphan_point_count,
            "partial_count": partial_count,
            "covered_count": covered_count,
            "orphan_point_count": orphan_point_count,
            "orphan_step_count": orphan_point_count,
            "source_covered_count": source_covered_count,
            "source_gap_count": source_gap_count,
            "partial_source_ids": partial_source_ids,
            "uncovered_source_ids": uncovered_source_ids,
            "source_coverage_status": source_coverage_status,
            "intent_coverage_status": intent_coverage_status,
            "status": "orphan" if orphan_point_count > 0 else intent_coverage_status,
            "unmapped_changed_area_count": len(unmapped_changed_areas),
            "unmapped_changed_areas": unmapped_changed_areas,
            "orphan_point_keys": orphan_point_keys,
            "orphan_step_keys": orphan_point_keys,
            "coverage_breakdown": {
                "covered": covered_count,
                "partial": partial_count,
                "gap": gap_count,
                "orphan": orphan_point_count,
            },
            "source_breakdown": {
                "covered": source_covered_count,
                "partial": len(partial_source_ids),
                "gap": source_gap_count,
                "total": len(source_ids),
            },
            "intent_breakdown": {
                "covered": covered_count,
                "partial": partial_count,
                "gap": gap_count,
                "orphan": orphan_point_count,
                "status": intent_coverage_status,
            },
            "traceability_completeness": traceability_completeness,
        }
