from __future__ import annotations

from typing import Any

from .candidate_normalizer import CandidateNormalizer
from .feature_flags import FeatureFlags


class ScenarioEngine:
    def __init__(self, flags: FeatureFlags) -> None:
        self._flags = flags

    def _scenario_alias(self, scenario: str) -> str:
        if scenario == "normal":
            return "functional"
        if scenario == "abnormal":
            return "negative"
        return "boundary"

    def normalize_combination_mode(self, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized in {"pairwise", "full", "intent_based"}:
            return normalized
        return "intent_based"

    def normalize_coverage_profile(self, value: str) -> list[str]:
        raw = str(value or "").strip().lower()
        if not raw:
            raw = "normal+abnormal+boundary"
        tokens = [part.strip() for part in raw.replace(",", "+").replace("/", "+").split("+") if part.strip()]
        mapped: list[str] = []
        for token in tokens:
            if token in {"normal", "functional", "positive", "happy", "smoke"}:
                key = "normal"
            elif token in {"abnormal", "negative", "exception", "error", "invalid"}:
                key = "abnormal"
            elif token in {"boundary", "edge", "limit"}:
                key = "boundary"
            else:
                continue
            if key not in mapped:
                mapped.append(key)
        if not mapped:
            mapped = ["normal", "abnormal", "boundary"]
        return mapped

    def scenario_from_intent(self, intent: dict[str, Any]) -> str:
        if not self._flags.scene_auto_classify_enabled():
            explicit_scene = str(intent.get("scene_type") or "").strip().lower()
            if explicit_scene in {"positive", "normal", "functional"}:
                return "normal"
            if explicit_scene in {"boundary", "edge", "limit"}:
                return "boundary"
            if explicit_scene in {"negative", "abnormal", "business_exception", "interaction_exception", "format", "non_empty"}:
                return "abnormal"
            intent_type_only = str(intent.get("intent_type") or "").strip().lower()
            if intent_type_only in {"boundary"}:
                return "boundary"
            if intent_type_only in {"negative", "security", "performance", "regression", "api"}:
                return "abnormal"
            return "normal"

        intent_type = str(intent.get("intent_type") or "").strip().lower()
        title = str(intent.get("title") or "").strip()
        summary = str(intent.get("summary") or "").strip()
        combined = f"{title} {summary} {intent_type}".lower()
        if any(keyword in combined for keyword in ["正确", "成功", "正常", "登录成功", "正向", "functional"]):
            return "normal"
        if any(keyword in combined for keyword in ["boundary", "edge", "limit", "边界", "临界", "上限", "下限", "最大", "最小"]):
            return "boundary"
        if any(
            keyword in combined
            for keyword in ["negative", "abnormal", "error", "invalid", "exception", "异常", "错误", "失败", "无效", "非法"]
        ):
            return "abnormal"
        return "normal"

    def _decorate_candidate_for_scenario(self, candidate: dict[str, Any], scenario: str, serial: int) -> dict[str, Any]:
        label_map = {"normal": "正常", "abnormal": "异常", "boundary": "边界"}
        decorated = dict(candidate)
        title = str(decorated.get("title") or "").strip()
        summary = str(decorated.get("summary") or "").strip()
        scenario_label = label_map.get(scenario, scenario)
        if title and scenario_label not in title:
            decorated["title"] = f"{title}（{scenario_label}）"
        elif not title:
            decorated["title"] = f"候选场景 {serial:02d}（{scenario_label}）"
        if summary and f"场景维度：{scenario}" not in summary:
            decorated["summary"] = f"{summary}\n场景维度：{scenario}"
        elif not summary:
            decorated["summary"] = f"场景维度：{scenario}"
        tags = decorated.get("tags")
        normalized_tags: list[str] = []
        if isinstance(tags, list):
            for item in tags:
                value = str(item or "").strip()
                if value and value not in normalized_tags:
                    normalized_tags.append(value)
        if scenario not in normalized_tags:
            normalized_tags.append(scenario)
        decorated["tags"] = normalized_tags
        decorated["intent_type"] = self._scenario_alias(scenario)
        return decorated

    def build_candidate_matrix(
        self,
        *,
        preview_payload: dict[str, Any],
        max_cases: int,
        combination_mode: str,
        coverage_profile: list[str],
        candidate_normalizer: CandidateNormalizer,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        normalized_mode = self.normalize_combination_mode(combination_mode)
        base_candidates = candidate_normalizer.extract_case_candidates_from_preview(preview_payload, max_cases=max_cases)
        item = preview_payload.get("item") if isinstance(preview_payload, dict) else {}
        item = item if isinstance(item, dict) else {}
        requirement_spec = item.get("requirement_spec") if isinstance(item.get("requirement_spec"), dict) else {}
        intents = (
            item.get("test_intents")
            if isinstance(item.get("test_intents"), list)
            else requirement_spec.get("test_intents") if isinstance(requirement_spec.get("test_intents"), list) else []
        )
        detected_input_scenarios: list[str] = []
        for raw_intent in intents:
            if not isinstance(raw_intent, dict):
                continue
            scenario = self.scenario_from_intent(raw_intent)
            if scenario not in detected_input_scenarios:
                detected_input_scenarios.append(scenario)
        if not base_candidates:
            base_candidates = [
                {
                    "title": "基础候选场景",
                    "summary": "系统在缺少结构化测试点时生成的基础候选。",
                    "intent_type": "functional",
                    "priority": "P1",
                    "tags": ["ai-generated"],
                }
            ]

        candidates: list[dict[str, Any]] = []
        if normalized_mode == "full":
            serial = 0
            for candidate in base_candidates:
                for scenario in coverage_profile:
                    serial += 1
                    candidates.append(self._decorate_candidate_for_scenario(candidate, scenario, serial))
                    if len(candidates) >= max_cases:
                        break
                if len(candidates) >= max_cases:
                    break
        elif normalized_mode == "pairwise":
            expected_size = max(len(base_candidates), len(coverage_profile))
            planned_size = min(expected_size, max_cases)
            for index in range(planned_size):
                scenario = coverage_profile[index % len(coverage_profile)]
                base = base_candidates[index % len(base_candidates)]
                candidates.append(self._decorate_candidate_for_scenario(base, scenario, index + 1))
        else:
            candidates = base_candidates[:max_cases]

        normalized_candidates = candidate_normalizer.normalize_candidates(candidates)[:max_cases]
        covered_scenarios: list[str] = []
        for candidate in normalized_candidates:
            scenario = self.scenario_from_intent(candidate)
            if scenario not in covered_scenarios:
                covered_scenarios.append(scenario)
        missing_required = [item for item in coverage_profile if item not in covered_scenarios]
        expected_full_combinations = len(base_candidates) * len(coverage_profile)
        effective_expected_count = len(normalized_candidates)
        truncated_full = normalized_mode == "full" and expected_full_combinations > len(normalized_candidates)
        if normalized_mode == "full":
            effective_expected_count = expected_full_combinations
        elif normalized_mode == "pairwise":
            effective_expected_count = max(len(base_candidates), len(coverage_profile))
        required_count = len(coverage_profile) or 1
        ratio = (required_count - len(missing_required)) / required_count
        status_value = "full"
        if missing_required or truncated_full:
            status_value = "gap"

        matrix_summary = {
            "combination_mode": normalized_mode,
            "coverage_profile": coverage_profile,
            "required_scenarios": coverage_profile,
            "detected_input_scenarios": detected_input_scenarios,
            "covered_scenarios": covered_scenarios,
            "missing_scenarios": missing_required,
            "status": status_value,
            "coverage_ratio": round(ratio, 4),
            "expected_case_count": int(effective_expected_count),
            "generated_case_count": len(normalized_candidates),
            "truncated_by_max_cases": bool(expected_full_combinations > max_cases and normalized_mode == "full"),
            "expected_full_combinations": int(expected_full_combinations),
        }
        return normalized_candidates, matrix_summary
