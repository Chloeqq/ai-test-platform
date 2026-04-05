from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


class FailureHealingSupport:
    def __init__(
        self,
        *,
        now: Callable[[], str],
        iter_recent_reports: Callable[..., list[dict[str, Any]]],
        run_failure_analysis_agent: Callable[[dict[str, Any]], dict[str, Any]],
        run_self_healing_advisor_agent: Callable[[dict[str, Any]], dict[str, Any]],
        load_available_targets: Callable[[str], list[str]],
        risk_evaluation_root: Path,
        failure_triage_root: Path,
    ) -> None:
        self._now = now
        self._iter_recent_reports = iter_recent_reports
        self._run_failure_analysis_agent = run_failure_analysis_agent
        self._run_self_healing_advisor_agent = run_self_healing_advisor_agent
        self._load_available_targets = load_available_targets
        self._risk_evaluation_root = risk_evaluation_root
        self._failure_triage_root = failure_triage_root

    def evaluate_risk_report(
        self,
        *,
        requirement_spec: dict[str, Any],
        execution_plan: dict[str, Any],
        execution_record: dict[str, Any],
        failure_analysis: dict[str, Any],
        failure_triage: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            "requirement_spec": requirement_spec,
            "execution_plan": execution_plan,
            "execution_record": execution_record,
            "failure_analysis": failure_analysis,
            "failure_triage": failure_triage,
        }
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(json.dumps(payload, ensure_ascii=False))
            completed = subprocess.run(
                [sys.executable, "-m", "src.index", "--input", str(temp_path)],
                cwd=str(self._risk_evaluation_root),
                text=True,
                capture_output=True,
                check=False,
            )
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "risk evaluation failed")
            parsed = json.loads(completed.stdout.strip() or "{}")
            if not isinstance(parsed, dict):
                raise RuntimeError("risk evaluation returned non-object payload")
            return parsed
        except Exception as exc:
            status = str(execution_record.get("status", "generated")).lower()
            fallback_decision = "allow" if status in {"passed", "generated"} else "manual_review"
            return {
                "version": "RiskReportV1",
                "risk_score": 55 if fallback_decision == "manual_review" else 30,
                "risk_level": "medium" if fallback_decision == "manual_review" else "low",
                "gate_decision": fallback_decision,
                "recommendation": "风险评估代理暂不可用，建议人工复核。",
                "factors": [{"factor": "agent_unavailable", "score": 20, "reason": str(exc)}],
                "metadata": {"fallback": True},
            }

    def triage_failure(
        self,
        *,
        failure_analysis: dict[str, Any],
        execution_record: dict[str, Any],
        evidence_manifest: dict[str, Any],
        report: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "failure_analysis": failure_analysis,
            "execution_record": execution_record,
            "evidence_manifest": evidence_manifest,
            "report": report or {},
        }
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(json.dumps(payload, ensure_ascii=False))
            completed = subprocess.run(
                [sys.executable, "-m", "src.index", "--input", str(temp_path)],
                cwd=str(self._failure_triage_root),
                text=True,
                capture_output=True,
                check=False,
            )
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "failure triage failed")
            parsed = json.loads(completed.stdout.strip() or "{}")
            if not isinstance(parsed, dict):
                raise RuntimeError("failure triage returned non-object payload")
            return parsed
        except Exception as exc:
            category = str(failure_analysis.get("failure_category", "unknown")).strip().lower() or "unknown"
            risk_level = str(failure_analysis.get("risk_level", "medium")).strip().lower() or "medium"
            status = str(execution_record.get("status", "generated")).strip().lower() or "generated"
            return {
                "version": "FailureTriageV1",
                "triage_label": f"{category}:{risk_level}:{status}",
                "failure_class": category,
                "severity": "S2" if status == "failed" else "S4",
                "owner_team": "qa-triage",
                "queue": "manual-triage",
                "bucket_key": f"{category}|fallback",
                "duplicate_of": "",
                "requires_manual_review": True,
                "confidence": 0.3,
                "signals": {
                    "status": status,
                    "risk_level": risk_level,
                    "evidence_total_files": int(evidence_manifest.get("total_files", 0) or 0),
                },
                "actions": [
                    {
                        "action": "create_ticket:manual-triage",
                        "owner": "qa-triage",
                        "reason": "分诊代理不可用，回退到人工分诊。",
                    }
                ],
                "metadata": {"fallback": True, "error": str(exc)},
            }

    def enrich_failure_triage_with_history(
        self,
        *,
        triage: dict[str, Any],
        case_id: str,
        page: str,
        started_at: str,
    ) -> dict[str, Any]:
        if not isinstance(triage, dict):
            triage = {}
        current_case_id = str(case_id).strip()
        current_page = str(page).strip()
        current_bucket = str(triage.get("bucket_key", "")).strip().lower()
        current_class = str(triage.get("failure_class", "unknown")).strip().lower() or "unknown"
        current_started_at = str(started_at).strip() or self._now()

        similarity_candidates: list[dict[str, Any]] = []
        for report in self._iter_recent_reports(limit=200):
            candidate_case_id = str(report.get("case_id", "")).strip()
            if not candidate_case_id or candidate_case_id == current_case_id:
                continue
            candidate_status = str(report.get("status", "")).strip().lower()
            if candidate_status not in {"failed", "broken", "coverage_gap"}:
                continue

            candidate_triage = report.get("failure_triage", {})
            if not isinstance(candidate_triage, dict):
                continue
            candidate_bucket = str(candidate_triage.get("bucket_key", "")).strip().lower()
            candidate_class = str(candidate_triage.get("failure_class", "unknown")).strip().lower()
            candidate_page = str(report.get("page", "")).strip()
            same_bucket = bool(current_bucket and candidate_bucket and current_bucket == candidate_bucket)
            same_class_page = candidate_class == current_class and candidate_page == current_page and bool(current_page)
            if not same_bucket and not same_class_page:
                continue

            similarity_candidates.append(
                {
                    "case_id": candidate_case_id,
                    "status": candidate_status,
                    "started_at": str(report.get("started_at", "")).strip(),
                    "risk_level": str((report.get("risk_report", {}) or {}).get("risk_level", "")).strip(),
                    "bucket_key": candidate_bucket,
                }
            )

        similarity_candidates.sort(key=lambda item: item.get("started_at", ""))
        similar_cases = similarity_candidates[-10:]
        duplicate_of = str(triage.get("duplicate_of", "")).strip()
        if not duplicate_of and similar_cases:
            duplicate_of = similar_cases[-1]["case_id"]

        cluster_seed = current_bucket or f"{current_class}|{current_page or 'unknown-page'}"
        cluster_id = f"cluster-{hashlib.sha1(cluster_seed.encode('utf-8')).hexdigest()[:12]}"
        occurrence_count = len(similarity_candidates) + 1
        first_seen_at = similarity_candidates[0]["started_at"] if similarity_candidates and similarity_candidates[0].get("started_at") else current_started_at
        last_seen_at = current_started_at

        triage["cluster_id"] = cluster_id
        triage["occurrence_count"] = occurrence_count
        triage["first_seen_at"] = first_seen_at
        triage["last_seen_at"] = last_seen_at
        triage["similar_cases"] = similar_cases
        triage["duplicate_of"] = duplicate_of
        metadata = triage.get("metadata", {})
        triage["metadata"] = metadata if isinstance(metadata, dict) else {}
        return triage

    def analyze_failure(self, report_payload: dict[str, Any], stdout_text: str, stderr_text: str) -> dict[str, Any]:
        if report_payload["status"] != "failed":
            return {
                "summary": "No failure analysis needed because the run did not fail.",
                "failure_category": "unknown",
                "failure_source": "unknown",
                "failure_source_reason": "No failure occurred, so no source classification is required.",
                "failure_source_confidence": 1.0,
                "source_evidence": [],
                "likely_cause": "",
                "risk_level": "low",
                "recommended_action": "No immediate failure action is required.",
                "confidence": 1.0,
                "requires_manual_review": False,
                "evidence_used": [],
            }

        try:
            return self._run_failure_analysis_agent(
                {
                    "report": report_payload,
                    "stdout": stdout_text,
                    "stderr": stderr_text,
                    "error": report_payload["failure_reason"],
                }
            )
        except Exception:
            return {
                "summary": "Failure analysis agent was unavailable; returned heuristic fallback analysis.",
                "failure_category": "unknown",
                "failure_source": "unknown",
                "failure_source_reason": "Failure analysis agent was unavailable, so source classification fell back to unknown.",
                "failure_source_confidence": 0.35,
                "source_evidence": [
                    {
                        "signal": "fallback",
                        "value": "failure_analysis_agent_unavailable",
                        "origin": "report",
                        "supports": "unknown",
                    }
                ],
                "likely_cause": report_payload["failure_reason"] or "Unknown execution failure.",
                "risk_level": "medium",
                "recommended_action": "Review the pytest output and captured evidence manually.",
                "confidence": 0.35,
                "requires_manual_review": True,
                "evidence_used": ["stdout", "stderr"] if stdout_text or stderr_text else ["report"],
            }

    def build_self_healing_advice(self, case: dict[str, Any], report_payload: dict[str, Any]) -> dict[str, Any]:
        available_targets = self._load_available_targets(case.get("execution", {}).get("page", ""))
        payload = {
            "page": case.get("execution", {}).get("page", ""),
            "failure_reason": report_payload.get("failure_reason", ""),
            "failure_analysis": report_payload.get("failure_analysis", {}),
            "available_targets": available_targets,
            "case": case,
        }
        try:
            return self._run_self_healing_advisor_agent(payload)
        except Exception:
            return {
                "summary": "No self-healing advice generated.",
                "suggestion_type": "no_change",
                "suggested_changes": ["Do not modify files automatically. Review the report and failure analysis manually."],
                "rationale": "Self-healing advisor agent was unavailable.",
                "confidence": 0.0,
                "safe_to_apply_manually": True,
            }

    @staticmethod
    def load_self_healing_suggestion_preview(report_payload: dict[str, Any]) -> dict[str, Any]:
        evidence = report_payload.get("evidence", {})
        if not isinstance(evidence, dict):
            return {}

        suggestion_files = evidence.get("suggestion_files") or []
        if not isinstance(suggestion_files, list) or not suggestion_files:
            return {}

        suggestion_path = Path(str(suggestion_files[0]))
        if not suggestion_path.exists():
            return {}

        try:
            payload = json.loads(suggestion_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

        if not isinstance(payload, dict):
            return {}

        return {
            "summary": str(payload.get("summary", "No suggestion summary available.")).strip() or "No suggestion summary available.",
            "advice_type": str(payload.get("advice_type", "no_change")).strip() or "no_change",
            "target": str(payload.get("target", "")).strip(),
            "suggestion": str(payload.get("suggestion", "")).strip(),
            "confidence": payload.get("confidence", 0.0),
            "fix_candidates": payload.get("fix_candidates", []) if isinstance(payload.get("fix_candidates", []), list) else [],
        }

    @staticmethod
    def load_self_healing_execution_preview(report_payload: dict[str, Any]) -> dict[str, Any]:
        evidence = report_payload.get("evidence", {})
        if not isinstance(evidence, dict):
            return {}

        result_files = evidence.get("self_healing_result_files") or []
        if not isinstance(result_files, list) or not result_files:
            return {}

        result_path = Path(str(result_files[0]))
        if not result_path.exists():
            return {}

        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

        if not isinstance(payload, dict):
            return {}

        return {
            "status": str(payload.get("status", "unknown")).strip() or "unknown",
            "reason": str(payload.get("reason", "")).strip(),
            "attempts_used": int(payload.get("attempts_used", 0) or 0),
            "healed": bool(payload.get("healed", False)),
            "rolled_back": bool(payload.get("rolled_back", False)),
            "confidence": payload.get("confidence", 0.0),
            "plan_path": str(payload.get("plan_path", "")).strip(),
            "result_path": str(payload.get("result_path", "")).strip(),
        }

    def preview_self_healing_advice(
        self,
        page: str,
        case: dict[str, Any] | None = None,
        failure_reason: str = "",
        failure_analysis: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_page = page.strip()
        if not normalized_page:
            raise ValueError("page must not be empty")

        normalized_case = case if isinstance(case, dict) else {}
        normalized_failure_analysis = failure_analysis if isinstance(failure_analysis, dict) else {}
        if not normalized_case:
            normalized_case = {
                "execution": {
                    "page": normalized_page,
                    "steps": [],
                }
            }

        payload = {
            "page": normalized_page,
            "failure_reason": str(failure_reason).strip(),
            "failure_analysis": normalized_failure_analysis,
            "available_targets": self._load_available_targets(normalized_page),
            "case": normalized_case,
        }
        return self._run_self_healing_advisor_agent(payload)
