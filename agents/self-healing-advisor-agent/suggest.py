import argparse
import json
import os
from pathlib import Path
from typing import Any

from prompt import SYSTEM_PROMPT, USER_TEMPLATE

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    def load_dotenv(*_args, **_kwargs):
        return False


ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ROOT_ENV)


class SelfHealingAdvisor:
    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("OPENAI_MODEL", "qwen3.5-plus")
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL")
        self.client = self._build_client()

    def suggest(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized_payload = self._normalize_input(payload)
        if self.client is None:
            return self._suggest_with_rules(normalized_payload)
        try:
            return self._suggest_with_model(normalized_payload)
        except Exception:
            return self._suggest_with_rules(normalized_payload)

    def _build_client(self):
        if not self.api_key or not self.base_url:
            return None
        try:
            from openai import OpenAI
        except Exception:
            return None
        return OpenAI(api_key=self.api_key, base_url=self.base_url)

    def _suggest_with_model(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_TEMPLATE.format(payload=json.dumps(payload, ensure_ascii=False, indent=2))},
            ],
        )
        content = self._extract_text_response(response)
        parsed = json.loads(content)
        return self._normalize_output(parsed, payload["available_targets"])

    def _suggest_with_rules(self, payload: dict[str, Any]) -> dict[str, Any]:
        available_targets = payload["available_targets"]
        failure_reason = str(payload.get("failure_reason", "")).lower()
        failure_analysis = payload.get("failure_analysis", {}) if isinstance(payload.get("failure_analysis"), dict) else {}
        likely_cause = str(failure_analysis.get("likely_cause", "")).lower()
        category = str(failure_analysis.get("failure_category", "")).lower()
        combined = "\n".join([failure_reason, likely_cause, category]).strip()

        advice_type = "no_change"
        target = ""
        suggestion = "证据不足，先人工检查现有 page-object 和断言，再决定是否调整。"
        confidence = 0.4
        fix_candidates: list[str] = []

        if any(token in combined for token in ["locator", "selector", "not found", "target"]):
            advice_type = "locator_update"
            target = self._pick_target(available_targets, ["button", "input", "menu", "title", "table", "list"])
            suggestion = "优先检查当前失败步骤引用的现有 target 是否仍然匹配 UI，并在现有 page-object target 中选择更合适的候选。"
            confidence = 0.78
            fix_candidates = self._candidate_targets(available_targets, ["menu", "title", "table", "list", "input", "button"])
        elif any(token in combined for token in ["assert", "expected", "actual", "visible"]):
            advice_type = "assertion_update"
            target = self._pick_target(available_targets, ["title", "table", "list"])
            suggestion = "优先核对断言目标是否仍然代表页面稳定结果，必要时仅在现有 target 中替换断言对象。"
            confidence = 0.74
            fix_candidates = self._candidate_targets(available_targets, ["title", "table", "list"])
        elif any(token in combined for token in ["timeout", "waiting", "wait_for"]):
            advice_type = "wait_strategy"
            target = self._pick_target(available_targets, ["title", "table", "list", "button"])
            suggestion = "优先检查现有等待目标是否合理，并考虑在现有 target 基础上调整等待策略，而不是新增 target。"
            confidence = 0.72
            fix_candidates = self._candidate_targets(available_targets, ["title", "table", "list", "button"])
        elif any(token in combined for token in ["data", "input", "fixture", "invalid"]):
            advice_type = "data_adjustment"
            suggestion = "优先核对当前测试数据和步骤输入是否满足页面前置条件，不建议先调整 page-object。"
            confidence = 0.68
        elif any(token in combined for token in ["environment", "browser", "base_url", "network", "auth", "login"]):
            advice_type = "environment_check"
            target = self._pick_target(available_targets, ["menu", "button", "input"])
            suggestion = "优先排查环境、登录态和基础依赖，再决定是否需要调整现有 target 的使用方式。"
            confidence = 0.65
            fix_candidates = self._candidate_targets(available_targets, ["menu", "button", "input"])

        summary = f"建议类型为 {advice_type}，当前阶段仅输出人工修复建议，不自动修改 YAML。"
        return self._normalize_output(
            {
                "summary": summary,
                "advice_type": advice_type,
                "target": target,
                "suggestion": suggestion,
                "confidence": confidence,
                "fix_candidates": fix_candidates,
            },
            available_targets,
        )

    @staticmethod
    def _normalize_input(payload: dict[str, Any]) -> dict[str, Any]:
        available_targets = payload.get("available_targets")
        if not isinstance(available_targets, list):
            available_targets = []
        normalized_targets = [str(item).strip() for item in available_targets if str(item).strip()]
        return {
            "page": str(payload.get("page", "")).strip(),
            "failure_reason": str(payload.get("failure_reason", "")).strip(),
            "failure_analysis": payload.get("failure_analysis", {}),
            "available_targets": normalized_targets,
        }

    @staticmethod
    def _candidate_targets(available_targets: list[str], keywords: list[str]) -> list[str]:
        matches = []
        for target in available_targets:
            target_lower = target.lower()
            if any(keyword in target_lower for keyword in keywords):
                matches.append(target)
        return matches[:3]

    @classmethod
    def _pick_target(cls, available_targets: list[str], keywords: list[str]) -> str:
        candidates = cls._candidate_targets(available_targets, keywords)
        return candidates[0] if candidates else ""

    @staticmethod
    def _extract_text_response(response: Any) -> str:
        if hasattr(response, "output_text") and response.output_text:
            return response.output_text.strip()
        raise ValueError("Model response did not contain output_text")

    @staticmethod
    def _normalize_output(payload: dict[str, Any], available_targets: list[str]) -> dict[str, Any]:
        advice_type = str(payload.get("advice_type", "no_change")).strip()
        if advice_type not in {
            "locator_update",
            "assertion_update",
            "wait_strategy",
            "data_adjustment",
            "environment_check",
            "no_change",
        }:
            advice_type = "no_change"

        target = str(payload.get("target", "")).strip()
        if target and target not in available_targets:
            target = ""

        fix_candidates = payload.get("fix_candidates")
        if not isinstance(fix_candidates, list):
            fix_candidates = []
        fix_candidates = [str(item).strip() for item in fix_candidates if str(item).strip() in available_targets]

        suggestion = str(payload.get("suggestion", "")).strip()
        if "自动修改" in suggestion:
            suggestion = suggestion.replace("自动修改", "人工修改")

        try:
            confidence = float(payload.get("confidence", 0.4))
        except (TypeError, ValueError):
            confidence = 0.4
        confidence = max(0.0, min(1.0, confidence))

        summary = str(payload.get("summary", "")).strip() or "当前阶段仅输出人工修复建议。"

        if confidence < 0.5:
            return {
                "summary": "置信度不足，当前不输出修复建议。",
                "advice_type": "no_change",
                "target": "",
                "suggestion": "",
                "confidence": confidence,
                "fix_candidates": [],
            }

        return {
            "summary": summary,
            "advice_type": advice_type,
            "target": target,
            "suggestion": suggestion or "请人工检查现有 target 和步骤配置。",
            "confidence": confidence,
            "fix_candidates": fix_candidates,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate self-healing suggestions without modifying YAML.")
    parser.add_argument("--input", required=True, help="Path to JSON payload file.")
    args = parser.parse_args()

    input_path = Path(args.input)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    result = SelfHealingAdvisor().suggest(payload)
    json.dump(result, fp=os.sys.stdout, ensure_ascii=False, indent=2)
    os.sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
