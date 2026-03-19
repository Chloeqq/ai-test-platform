import argparse
import json
import os
import re
import sys
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


class FailureAnalysisAgent:
    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("OPENAI_MODEL", "qwen3.5-plus")
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL")
        self.client = self._build_client()

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.client is None:
            return self._analyze_with_rules(payload)
        try:
            return self._analyze_with_model(payload)
        except Exception:
            return self._analyze_with_rules(payload)

    def _build_client(self):
        if not self.api_key or not self.base_url:
            return None
        try:
            from openai import OpenAI
        except Exception:
            return None
        return OpenAI(api_key=self.api_key, base_url=self.base_url)

    def _analyze_with_model(self, payload: dict[str, Any]) -> dict[str, Any]:
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

    def _analyze_with_rules(self, payload: dict[str, Any]) -> dict[str, Any]:
        report = payload.get("report", {}) if isinstance(payload.get("report"), dict) else {}
        stdout_text = self._combined_text(payload.get("stdout"), report.get("runner_stdout_excerpt"))
        stderr_text = self._combined_text(payload.get("stderr"), report.get("runner_stderr_excerpt"), payload.get("error"))
        current_url = str(payload.get("current_url", "")).strip()
        page_html = str(payload.get("page_html", "")).strip()
        text = f"{stdout_text}\n{stderr_text}\n{current_url}\n{page_html}".lower()
        evidence = report.get("evidence", {}) if isinstance(report.get("evidence"), dict) else {}
        meta_summary = self._read_meta_summary(evidence)
        text = f"{text}\n{meta_summary.lower()}".strip()

        category = "unknown"
        likely_cause = "Unable to determine an exact cause from the available evidence."
        risk_level = "medium"
        recommended_action = "Review the report, stdout/stderr, and captured evidence before retrying."
        confidence = 0.45
        evidence_used = self._infer_evidence_used(
            stdout_text=stdout_text,
            stderr_text=stderr_text,
            evidence=evidence,
            current_url=current_url,
            page_html=page_html,
        )

        if any(token in text for token in ["timeout", "timed out", "waiting for", "wait_for"]):
            category = "timeout"
            likely_cause = "The page or target element did not become ready within the expected time."
            risk_level = "high"
            recommended_action = "Check environment responsiveness, target selectors, and wait strategy."
            confidence = 0.78
        elif any(token in text for token in ["登录", "login", "/login", "username", "password"]):
            category = "authentication"
            likely_cause = "The failure likely happened around login state, credentials, or session establishment."
            risk_level = "high"
            recommended_action = "Verify the login page, account credentials, and session initialization before rerunning."
            confidence = 0.75
        elif any(token in text for token in ["locator", "selector", "assert_visible", "no node found", "not found"]):
            category = "locator"
            likely_cause = "The page object target or selector likely does not match the current UI."
            risk_level = "high"
            recommended_action = "Validate the page object locator and update the target mapping if the UI changed."
            confidence = 0.8
        elif any(token in text for token in ["assert", "expected", "actual", "assertionerror"]):
            category = "assertion"
            likely_cause = "The observed UI state does not match the expected assertion."
            risk_level = "medium"
            recommended_action = "Confirm whether the failure is a product defect or an outdated assertion."
            confidence = 0.72
        elif any(token in text for token in ["401", "403", "unauthorized", "forbidden", "login failed", "authentication"]):
            category = "authentication"
            likely_cause = "Authentication or permission state is preventing the test from completing."
            risk_level = "critical"
            recommended_action = "Verify the test account, login flow, and required permissions."
            confidence = 0.82
        elif any(token in text for token in ["network", "connection", "dns", "socket", "econnrefused", "502", "503", "504"]):
            category = "network"
            likely_cause = "The target service or network path was unstable or unavailable during execution."
            risk_level = "high"
            recommended_action = "Check service availability, gateway logs, and network reachability before retrying."
            confidence = 0.76
        elif any(token in text for token in ["base_url", "environment", "browser", "playwright", "chromium", "page.goto"]):
            category = "environment"
            likely_cause = "The execution environment or runtime dependency was not correctly prepared."
            risk_level = "high"
            recommended_action = "Verify BASE_URL, browser installation, and environment variables."
            confidence = 0.68
        elif any(token in text for token in ["data", "fixture", "template", "invalid input"]):
            category = "data"
            likely_cause = "The test data or generated input likely does not satisfy the scenario preconditions."
            risk_level = "medium"
            recommended_action = "Review the generated data and scenario assumptions before rerunning."
            confidence = 0.66

        if meta_summary:
            likely_cause = f"{likely_cause} Meta context: {meta_summary}".strip()

        status = report.get("status") or ("failed" if stderr_text or stdout_text else "unknown")
        summary = f"Execution status is {status}; the most likely failure category is {category}."

        return self._normalize_output(
            {
                "summary": summary,
                "failure_category": category,
                "likely_cause": likely_cause,
                "risk_level": risk_level,
                "recommended_action": recommended_action,
                "confidence": confidence,
                "evidence_used": evidence_used,
            }
        )

    @staticmethod
    def _combined_text(*parts: Any) -> str:
        values = [str(part).strip() for part in parts if part]
        return "\n".join(value for value in values if value)

    @staticmethod
    def _infer_evidence_used(
        stdout_text: str,
        stderr_text: str,
        evidence: dict[str, Any],
        current_url: str = "",
        page_html: str = "",
    ) -> list[str]:
        items: list[str] = []
        if stdout_text or stderr_text:
            items.append("error")
        if current_url:
            items.append("current_url")
        if page_html:
            items.append("page_html")
        if stdout_text:
            items.append("stdout")
        if stderr_text:
            items.append("stderr")
        if evidence.get("screenshots"):
            items.append("screenshots")
        if evidence.get("html_pages"):
            items.append("html_pages")
        if evidence.get("meta_files"):
            items.append("meta_files")
        if evidence.get("videos"):
            items.append("videos")
        return items or ["report"]

    @staticmethod
    def _read_meta_summary(evidence: dict[str, Any]) -> str:
        meta_files = evidence.get("meta_files") or []
        if not meta_files:
            return ""

        meta_path = Path(str(meta_files[0]))
        if not meta_path.exists():
            return ""

        try:
            content = meta_path.read_text(encoding="utf-8")
        except Exception:
            return ""

        url_match = re.search(r"^URL:\s*(.+)$", content, re.MULTILINE)
        title_match = re.search(r"^Title:\s*(.+)$", content, re.MULTILINE)
        url_text = url_match.group(1).strip() if url_match else ""
        title_text = title_match.group(1).strip() if title_match else ""

        parts = []
        if url_text:
            parts.append(f"url={url_text}")
        if title_text:
            parts.append(f"title={title_text}")
        return ", ".join(parts)

    @staticmethod
    def _extract_text_response(response: Any) -> str:
        if hasattr(response, "output_text") and response.output_text:
            return response.output_text.strip()
        raise ValueError("Model response did not contain output_text")

    @staticmethod
    def _normalize_output(payload: dict[str, Any]) -> dict[str, Any]:
        allowed_categories = {
            "locator",
            "assertion",
            "timeout",
            "environment",
            "authentication",
            "network",
            "data",
            "unknown",
        }
        allowed_risk_levels = {"low", "medium", "high", "critical"}

        category = str(payload.get("failure_category", "unknown")).strip().lower()
        if category not in allowed_categories:
            category = "unknown"

        risk_level = str(payload.get("risk_level", "medium")).strip().lower()
        if risk_level not in allowed_risk_levels:
            risk_level = "medium"

        try:
            confidence = float(payload.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))

        evidence_used = payload.get("evidence_used", [])
        if not isinstance(evidence_used, list):
            evidence_used = []

        return {
            "summary": str(payload.get("summary", "No failure summary generated.")).strip(),
            "failure_category": category,
            "likely_cause": str(payload.get("likely_cause", "Unknown cause.")).strip(),
            "risk_level": risk_level,
            "recommended_action": str(payload.get("recommended_action", "Review the execution report manually.")).strip(),
            "confidence": confidence,
            "evidence_used": [str(item) for item in evidence_used if str(item).strip()],
        }


def _load_payload(input_path: str | None) -> dict[str, Any]:
    if input_path:
        return json.loads(Path(input_path).read_text(encoding="utf-8"))

    raw = sys.stdin.read().strip()
    if not raw:
        raise ValueError("No input payload provided. Use --input or pipe JSON via stdin.")
    return json.loads(raw)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze a failure report and output structured JSON.")
    parser.add_argument("--input", help="Path to a JSON payload file")
    parser.add_argument("--model", help="Override model name")
    args = parser.parse_args()

    payload = _load_payload(args.input)
    agent = FailureAnalysisAgent(model=args.model)
    result = agent.analyze(payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
