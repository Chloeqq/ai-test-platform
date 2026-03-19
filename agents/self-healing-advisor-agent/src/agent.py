import json
import os
from pathlib import Path
from typing import Any

try:
    from .prompt import SYSTEM_PROMPT, USER_TEMPLATE
    from .schema import SelfHealingAdvice
except ImportError:  # pragma: no cover - direct module execution fallback
    from prompt import SYSTEM_PROMPT, USER_TEMPLATE
    from schema import SelfHealingAdvice

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    def load_dotenv(*_args, **_kwargs):
        return False


ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV)


class SelfHealingAdvisorAgent:
    ALLOWED_SUGGESTION_TYPES = {
        "locator_update",
        "assertion_update",
        "wait_strategy",
        "data_adjustment",
        "environment_check",
        "no_change",
    }

    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("OPENAI_MODEL", "qwen3.5-plus")
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL")
        self.client = self._build_client()

    def advise(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.client is None:
            return self._advise_with_rules(payload)
        try:
            return self._advise_with_model(payload)
        except Exception:
            return self._advise_with_rules(payload)

    def _build_client(self):
        if not self.api_key or not self.base_url:
            return None
        try:
            from openai import OpenAI
        except Exception:
            return None
        return OpenAI(api_key=self.api_key, base_url=self.base_url)

    def _advise_with_model(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_TEMPLATE.format(payload=json.dumps(payload, ensure_ascii=False, indent=2))},
            ],
        )
        content = self._extract_text_response(response)
        parsed = json.loads(content)
        return self._normalize_output(parsed)

    def _advise_with_rules(self, payload: dict[str, Any]) -> dict[str, Any]:
        failure_analysis = payload.get("failure_analysis", {}) if isinstance(payload.get("failure_analysis"), dict) else {}
        category = str(failure_analysis.get("failure_category", "unknown")).strip().lower()
        failure_reason = str(payload.get("failure_reason", "")).strip()
        page_name = str(payload.get("page", "")).strip()
        target_names = payload.get("available_targets", [])
        if not isinstance(target_names, list):
            target_names = []

        suggestion_type = "no_change"
        suggested_changes = ["Do not modify files automatically. Review the failure details first."]
        rationale = "Not enough information to recommend a safe manual fix."
        confidence = 0.4

        if category == "locator":
            suggestion_type = "locator_update"
            suggested_changes = [
                f"Review the failing target against current page-object names for page '{page_name}'.",
                "Prefer reusing an existing stable target before introducing a new locator.",
            ]
            if target_names:
                suggested_changes.append(f"Available targets: {', '.join(target_names)}")
            rationale = "The failure analysis suggests the current locator or target name no longer matches the UI."
            confidence = 0.78
        elif category == "assertion":
            suggestion_type = "assertion_update"
            suggested_changes = [
                "Check whether the assertion target is still the correct stable element.",
                "If the page state changed intentionally, update the assertion target or expected content manually.",
            ]
            rationale = f"The failure was categorized as an assertion issue. {failure_reason}".strip()
            confidence = 0.74
        elif category == "timeout":
            suggestion_type = "wait_strategy"
            suggested_changes = [
                "Check whether the current wait target is the correct stable page marker.",
                "If needed, add or swap to a more stable existing target for wait_for/assert_visible.",
            ]
            rationale = "The failure indicates the page or target did not become ready in time."
            confidence = 0.73
        elif category in {"authentication", "environment", "network"}:
            suggestion_type = "environment_check"
            suggested_changes = [
                "Check environment variables, account state, and service availability before changing YAML.",
                "Avoid changing stable smoke YAML until environment issues are ruled out.",
            ]
            rationale = "The failure is more likely caused by environment or system state than by YAML structure."
            confidence = 0.72
        elif category == "data":
            suggestion_type = "data_adjustment"
            suggested_changes = [
                "Review the generated input data and variable substitutions.",
                "Adjust only the scenario data manually; do not rename stable targets.",
            ]
            rationale = "The failure appears tied to scenario input or precondition data."
            confidence = 0.68

        return self._normalize_output(
            {
                "summary": f"Suggested manual remediation path for failure category '{category}'.",
                "suggestion_type": suggestion_type,
                "suggested_changes": suggested_changes,
                "rationale": rationale,
                "confidence": confidence,
                "safe_to_apply_manually": True,
            }
        )

    @staticmethod
    def _extract_text_response(response: Any) -> str:
        if hasattr(response, "output_text") and response.output_text:
            return response.output_text.strip()
        raise ValueError("Model response did not contain output_text")

    def _normalize_output(self, payload: dict[str, Any]) -> dict[str, Any]:
        suggestion_type = str(payload.get("suggestion_type", "no_change")).strip().lower()
        if suggestion_type not in self.ALLOWED_SUGGESTION_TYPES:
            suggestion_type = "no_change"

        suggested_changes = payload.get("suggested_changes", [])
        if not isinstance(suggested_changes, list):
            suggested_changes = []

        try:
            confidence = float(payload.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))

        result = SelfHealingAdvice(
            summary=str(payload.get("summary", "No self-healing advice generated.")).strip(),
            suggestion_type=suggestion_type,
            suggested_changes=[str(item).strip() for item in suggested_changes if str(item).strip()],
            rationale=str(payload.get("rationale", "No rationale provided.")).strip(),
            confidence=confidence,
            safe_to_apply_manually=bool(payload.get("safe_to_apply_manually", True)),
        )
        return result.model_dump()
