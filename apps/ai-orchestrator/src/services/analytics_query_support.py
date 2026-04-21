from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable


class AnalyticsQuerySupport:
    def __init__(
        self,
        *,
        now: Callable[[], str],
        iter_recent_reports: Callable[..., list[dict[str, Any]]],
        load_self_healing_suggestion_preview: Callable[[dict[str, Any]], dict[str, Any]],
        load_report_summary_preview: Callable[[Path], dict[str, Any]],
        get_report_root: Callable[[], Path],
        get_runner_root: Callable[[], Path],
        get_requirement_parse_telemetry_log: Callable[[], Path],
    ) -> None:
        self._now = now
        self._iter_recent_reports = iter_recent_reports
        self._load_self_healing_suggestion_preview = load_self_healing_suggestion_preview
        self._load_report_summary_preview = load_report_summary_preview
        self._get_report_root = get_report_root
        self._get_runner_root = get_runner_root
        self._get_requirement_parse_telemetry_log = get_requirement_parse_telemetry_log

    def get_requirement_parse_telemetry_summary(
        self,
        *,
        limit: int = 500,
        prompt_version: str = "",
        model: str = "",
        mode: str = "",
        stage: str = "",
    ) -> dict[str, Any]:
        normalized_limit = max(1, min(int(limit), 5000))
        normalized_prompt_version = str(prompt_version).strip()
        normalized_model = str(model).strip()
        normalized_mode = str(mode).strip().lower()
        normalized_stage = str(stage).strip().lower()

        events = self.iter_requirement_parse_telemetry_events(limit=normalized_limit)
        filtered: list[dict[str, Any]] = []
        for event in events:
            parser_runtime = event.get("parser_runtime")
            runtime = parser_runtime if isinstance(parser_runtime, dict) else {}
            event_stage = str(event.get("stage", "")).strip().lower()
            event_prompt_version = str(runtime.get("prompt_version", "")).strip()
            event_model = str(runtime.get("model", "")).strip()
            event_mode = str(runtime.get("mode", "")).strip().lower()
            if normalized_stage and event_stage != normalized_stage:
                continue
            if normalized_prompt_version and event_prompt_version != normalized_prompt_version:
                continue
            if normalized_model and event_model != normalized_model:
                continue
            if normalized_mode and event_mode != normalized_mode:
                continue
            filtered.append(event)

        allow_count = 0
        blocked_count = 0
        llm_attempted_count = 0
        llm_succeeded_count = 0
        groups: dict[str, dict[str, Any]] = {}

        for event in filtered:
            parser_runtime = event.get("parser_runtime")
            runtime = parser_runtime if isinstance(parser_runtime, dict) else {}
            llm_trace = event.get("llm_trace")
            llm = llm_trace if isinstance(llm_trace, dict) else {}
            decision = str(event.get("quality_gate_decision", "")).strip().lower() or "allow"
            blocked = decision == "block" or str(event.get("outcome", "")).strip().lower() == "block"

            if blocked:
                blocked_count += 1
            else:
                allow_count += 1
            if bool(llm.get("attempted", False)):
                llm_attempted_count += 1
            if bool(llm.get("succeeded", False)):
                llm_succeeded_count += 1

            group_prompt = str(runtime.get("prompt_version", "")).strip() or "unknown"
            group_model = str(runtime.get("model", "")).strip() or "unknown"
            group_mode = str(runtime.get("mode", "")).strip().lower() or "rule_based"
            group_key = f"{group_prompt}|{group_model}|{group_mode}"
            group = groups.setdefault(
                group_key,
                {
                    "prompt_version": group_prompt,
                    "model": group_model,
                    "mode": group_mode,
                    "total": 0,
                    "allow_count": 0,
                    "blocked_count": 0,
                    "llm_attempted_count": 0,
                    "llm_succeeded_count": 0,
                },
            )
            group["total"] += 1
            if blocked:
                group["blocked_count"] += 1
            else:
                group["allow_count"] += 1
            if bool(llm.get("attempted", False)):
                group["llm_attempted_count"] += 1
            if bool(llm.get("succeeded", False)):
                group["llm_succeeded_count"] += 1

        group_items = sorted(groups.values(), key=lambda item: int(item.get("total", 0)), reverse=True)
        for item in group_items:
            total = max(1, int(item.get("total", 0)))
            item["allow_rate"] = round(int(item.get("allow_count", 0)) / total, 3)

        total_filtered = len(filtered)
        return {
            "version": "RequirementParseTelemetrySummaryV1",
            "generated_at": self._now(),
            "filters": {
                "limit": normalized_limit,
                "prompt_version": normalized_prompt_version,
                "model": normalized_model,
                "mode": normalized_mode,
                "stage": normalized_stage,
            },
            "total_events": total_filtered,
            "allow_count": allow_count,
            "blocked_count": blocked_count,
            "allow_rate": round(allow_count / max(1, total_filtered), 3),
            "llm_attempted_count": llm_attempted_count,
            "llm_succeeded_count": llm_succeeded_count,
            "groups": group_items[:100],
        }

    def iter_requirement_parse_telemetry_events(self, *, limit: int) -> list[dict[str, Any]]:
        telemetry_log = self._get_requirement_parse_telemetry_log()
        if not telemetry_log.exists():
            return []
        events: list[dict[str, Any]] = []
        try:
            with telemetry_log.open("r", encoding="utf-8") as handle:
                for line in handle:
                    text = str(line).strip()
                    if not text:
                        continue
                    try:
                        payload = json.loads(text)
                    except Exception:
                        continue
                    if isinstance(payload, dict):
                        events.append(payload)
        except Exception:
            return []
        if len(events) > limit:
            return events[-limit:]
        return events

    def record_requirement_parse_telemetry(
        self,
        *,
        requirement_spec: dict[str, Any],
        stage: str,
        source: str,
        outcome: str,
    ) -> None:
        spec = requirement_spec if isinstance(requirement_spec, dict) else {}
        parser_runtime = spec.get("parser_runtime")
        runtime = parser_runtime if isinstance(parser_runtime, dict) else {}
        quality_gate = spec.get("quality_gate")
        gate = quality_gate if isinstance(quality_gate, dict) else {}
        blockers_raw = gate.get("blockers")
        blockers = blockers_raw if isinstance(blockers_raw, list) else []
        blocker_codes = [
            str(item.get("code", "")).strip()
            for item in blockers
            if isinstance(item, dict) and str(item.get("code", "")).strip()
        ][:20]
        llm_trace = runtime.get("llm_trace")
        llm = llm_trace if isinstance(llm_trace, dict) else {}
        ai_trace = runtime.get("ai_trace")
        trace = ai_trace if isinstance(ai_trace, dict) else {}
        try:
            parse_confidence = round(float(spec.get("parse_confidence", 0.0) or 0.0), 2)
        except Exception:
            parse_confidence = 0.0

        event = {
            "event_type": "requirement_parse_telemetry",
            "timestamp": self._now(),
            "stage": str(stage).strip().lower(),
            "source": str(source).strip().lower() or "manual",
            "outcome": str(outcome).strip().lower() or "allow",
            "page": str(spec.get("page", "")).strip(),
            "source_type": str(spec.get("source_type", "")).strip() or "text",
            "priority": str(spec.get("priority", "")).strip() or "P1",
            "parse_confidence": parse_confidence,
            "quality_gate_decision": str(gate.get("decision", "")).strip().lower() or "allow",
            "quality_gate_blocker_count": len(blocker_codes),
            "quality_gate_blocker_codes": blocker_codes,
            "trace_id": str(trace.get("trace_id", "")).strip(),
            "parser_runtime": {
                "mode": str(runtime.get("mode", "")).strip() or "rule_based",
                "model": str(runtime.get("model", "")).strip() or "rule-engine",
                "prompt_version": str(runtime.get("prompt_version", "")).strip() or "unknown",
                "instructions_version": str(runtime.get("instructions_version", "")).strip() or "unknown",
                "parse_duration_ms": int(runtime.get("parse_duration_ms", 0) or 0),
            },
            "llm_trace": {
                "attempted": bool(llm.get("attempted", False)),
                "succeeded": bool(llm.get("succeeded", False)),
                "reason_code": str(llm.get("reason_code", "")).strip(),
                "latency_ms": int(llm.get("latency_ms", 0) or 0),
                "total_tokens": llm.get("total_tokens"),
                "overlay_key_count": int(llm.get("overlay_key_count", 0) or 0),
            },
        }
        try:
            telemetry_log = self._get_requirement_parse_telemetry_log()
            telemetry_log.parent.mkdir(parents=True, exist_ok=True)
            with telemetry_log.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception:
            return

    def get_latest_report(self) -> dict[str, Any]:
        report_root = self._get_report_root()
        report_files = sorted(
            report_root.glob("*.report.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if not report_files:
            raise ValueError("No execution reports found")
        return self.get_report(report_files[0].stem.removesuffix(".report"))

    def get_report(self, case_id: str) -> dict[str, Any]:
        normalized_case_id = case_id.strip()
        if not normalized_case_id:
            raise ValueError("case_id must not be empty")

        report_root = self._get_report_root()
        runner_root = self._get_runner_root()
        json_path = report_root / f"{normalized_case_id}.report.json"
        markdown_path = report_root / f"{normalized_case_id}.report.md"
        if not json_path.exists():
            raise ValueError(f"Execution report not found for case_id: {normalized_case_id}")

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        payload.setdefault("self_healing_suggestion_preview", self._load_self_healing_suggestion_preview(payload))
        report_summary_path = runner_root / "artifacts" / "report_summary.txt"
        return {
            "report": payload,
            "execution_record": payload.get("execution_record", {}),
            "report_json_path": str(json_path),
            "report_markdown_path": str(markdown_path),
            "report_summary_path": str(report_summary_path),
            "report_summary_preview": self._load_report_summary_preview(report_summary_path),
        }

    def get_failure_clusters(
        self,
        *,
        limit: int = 200,
        max_clusters: int = 20,
        queue: str = "",
        failure_class: str = "",
        severity: str = "",
    ) -> dict[str, Any]:
        normalized_limit = max(1, min(int(limit), 2000))
        normalized_max_clusters = max(1, min(int(max_clusters), 200))
        normalized_queue = str(queue).strip().lower()
        normalized_failure_class = str(failure_class).strip().lower()
        normalized_severity = str(severity).strip().upper()
        reports = self._iter_recent_reports(limit=normalized_limit)

        clusters: dict[str, dict[str, Any]] = {}
        total_failed_reports = 0
        queue_distribution: dict[str, int] = {}
        class_distribution: dict[str, int] = {}
        severity_distribution: dict[str, int] = {}

        for report in reports:
            status = str(report.get("status", "")).strip().lower()
            if status not in {"failed", "broken", "coverage_gap"}:
                continue
            total_failed_reports += 1

            triage = report.get("failure_triage", {})
            if not isinstance(triage, dict):
                triage = {}
            failure_analysis = report.get("failure_analysis", {})
            if not isinstance(failure_analysis, dict):
                failure_analysis = {}

            case_id = str(report.get("case_id", "")).strip()
            page = str(report.get("page", "")).strip()
            started_at = str(report.get("started_at", "")).strip()
            risk_level = str((report.get("risk_report", {}) or {}).get("risk_level", "")).strip().lower()
            current_queue = str(triage.get("queue", "")).strip() or "manual-triage"
            current_severity = str(triage.get("severity", "")).strip().upper() or "S4"
            current_failure_class = str(triage.get("failure_class", "")).strip().lower() or str(failure_analysis.get("failure_category", "unknown")).strip().lower() or "unknown"
            owner_team = str(triage.get("owner_team", "")).strip() or "qa-triage"
            bucket_key = str(triage.get("bucket_key", "")).strip().lower()
            cluster_id = str(triage.get("cluster_id", "")).strip()

            if not cluster_id:
                cluster_seed = bucket_key or f"{current_failure_class}|{page or 'unknown-page'}"
                cluster_id = f"cluster-{hashlib.sha1(cluster_seed.encode('utf-8')).hexdigest()[:12]}"

            row = clusters.setdefault(
                cluster_id,
                {
                    "cluster_id": cluster_id,
                    "failure_class": current_failure_class,
                    "page": page,
                    "queue": current_queue,
                    "owner_team": owner_team,
                    "severity": current_severity,
                    "bucket_key": bucket_key,
                    "occurrence_count": 0,
                    "first_seen_at": started_at,
                    "last_seen_at": started_at,
                    "latest_case_id": case_id,
                    "requires_manual_review_count": 0,
                    "risk_level_count": {"critical": 0, "high": 0, "medium": 0, "low": 0, "unknown": 0},
                    "sample_cases": [],
                },
            )

            row["occurrence_count"] += 1
            if bool(triage.get("requires_manual_review", False)):
                row["requires_manual_review_count"] += 1

            current_first = str(row.get("first_seen_at", "")).strip()
            current_last = str(row.get("last_seen_at", "")).strip()
            if started_at:
                if not current_first or started_at < current_first:
                    row["first_seen_at"] = started_at
                if not current_last or started_at > current_last:
                    row["last_seen_at"] = started_at
                    row["latest_case_id"] = case_id or row.get("latest_case_id", "")

            if risk_level not in {"critical", "high", "medium", "low"}:
                risk_level = "unknown"
            row["risk_level_count"][risk_level] = int(row["risk_level_count"].get(risk_level, 0)) + 1

            row["sample_cases"].append(
                {
                    "case_id": case_id,
                    "status": status,
                    "page": page,
                    "started_at": started_at,
                    "risk_level": risk_level,
                    "severity": current_severity,
                    "queue": current_queue,
                }
            )

            queue_distribution[current_queue] = queue_distribution.get(current_queue, 0) + 1
            class_distribution[current_failure_class] = class_distribution.get(current_failure_class, 0) + 1
            severity_distribution[current_severity] = severity_distribution.get(current_severity, 0) + 1

        rows: list[dict[str, Any]] = []
        for row in clusters.values():
            sample_cases = sorted(
                row["sample_cases"],
                key=lambda item: str(item.get("started_at", "")),
                reverse=True,
            )[:5]
            risk_level_count = row["risk_level_count"]
            top_risk_level = max(
                ["critical", "high", "medium", "low", "unknown"],
                key=lambda level: int(risk_level_count.get(level, 0)),
            )
            occurrence_count = int(row["occurrence_count"])
            requires_manual_review_count = int(row["requires_manual_review_count"])
            manual_review_ratio = round(requires_manual_review_count / occurrence_count, 2) if occurrence_count > 0 else 0.0

            rows.append(
                {
                    "cluster_id": row["cluster_id"],
                    "failure_class": row["failure_class"],
                    "page": row["page"],
                    "queue": row["queue"],
                    "owner_team": row["owner_team"],
                    "severity": row["severity"],
                    "bucket_key": row["bucket_key"],
                    "occurrence_count": occurrence_count,
                    "first_seen_at": row["first_seen_at"],
                    "last_seen_at": row["last_seen_at"],
                    "latest_case_id": row["latest_case_id"],
                    "requires_manual_review_count": requires_manual_review_count,
                    "manual_review_ratio": manual_review_ratio,
                    "top_risk_level": top_risk_level,
                    "risk_level_count": risk_level_count,
                    "sample_cases": sample_cases,
                }
            )

        if normalized_queue:
            rows = [item for item in rows if str(item.get("queue", "")).strip().lower() == normalized_queue]
        if normalized_failure_class:
            rows = [
                item
                for item in rows
                if str(item.get("failure_class", "")).strip().lower() == normalized_failure_class
            ]
        if normalized_severity:
            rows = [item for item in rows if str(item.get("severity", "")).strip().upper() == normalized_severity]

        severity_rank = {"S0": 5, "S1": 4, "S2": 3, "S3": 2, "S4": 1}
        risk_rank = {"critical": 5, "high": 4, "medium": 3, "low": 2, "unknown": 1}
        rows.sort(
            key=lambda item: (
                severity_rank.get(str(item.get("severity", "S4")).upper(), 0),
                risk_rank.get(str(item.get("top_risk_level", "unknown")).lower(), 0),
                int(item.get("occurrence_count", 0)),
                str(item.get("last_seen_at", "")),
            ),
            reverse=True,
        )
        rows = rows[:normalized_max_clusters]

        return {
            "generated_at": self._now(),
            "total_failed_reports": total_failed_reports,
            "total_clusters": len(rows),
            "clusters": rows,
            "queue_distribution": [{"queue": key, "count": value} for key, value in sorted(queue_distribution.items(), key=lambda item: item[1], reverse=True)],
            "class_distribution": [{"failure_class": key, "count": value} for key, value in sorted(class_distribution.items(), key=lambda item: item[1], reverse=True)],
            "severity_distribution": [{"severity": key, "count": value} for key, value in sorted(severity_distribution.items(), key=lambda item: item[1], reverse=True)],
            "filters": {
                "queue": normalized_queue,
                "failure_class": normalized_failure_class,
                "severity": normalized_severity,
            },
        }

    def get_failure_cluster(self, *, cluster_id: str, limit: int = 200) -> dict[str, Any]:
        normalized_cluster_id = str(cluster_id).strip()
        if not normalized_cluster_id:
            raise ValueError("cluster_id must not be empty")
        cluster_payload = self.get_failure_clusters(limit=limit, max_clusters=200)
        for cluster in cluster_payload.get("clusters", []):
            if str(cluster.get("cluster_id", "")).strip() == normalized_cluster_id:
                return {
                    "generated_at": cluster_payload.get("generated_at", self._now()),
                    "cluster": cluster,
                }
        raise ValueError(f"Failure cluster not found: {normalized_cluster_id}")
