import argparse
import json
from collections import Counter
from pathlib import Path


def parse_analysis_file(path: Path, *, suggestion_path: Path | None = None) -> dict[str, str]:
    parsed = {
        "case": path.parent.name,
        "summary": "",
        "failure_category": "",
        "likely_cause": "",
        "risk_level": "",
        "recommended_action": "",
        "confidence": "",
        "evidence_used": "",
        "path": str(path),
        "suggestion_path": str(suggestion_path.resolve()) if suggestion_path else "",
    }
    key_map = {
        "Summary": "summary",
        "Failure Category": "failure_category",
        "Likely Cause": "likely_cause",
        "Risk Level": "risk_level",
        "Recommended Action": "recommended_action",
        "Confidence": "confidence",
        "Evidence Used": "evidence_used",
    }
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if ": " not in raw_line:
            continue
        prefix, value = raw_line.split(": ", 1)
        mapped_key = key_map.get(prefix.strip())
        if mapped_key:
            parsed[mapped_key] = value.strip()
    return parsed


def _load_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _resolve_manifest_entries(entries: object, *, root: Path) -> list[Path]:
    if not isinstance(entries, list):
        return []
    resolved = []
    for raw_entry in entries:
        raw_text = str(raw_entry).strip()
        if not raw_text:
            continue
        candidate = Path(raw_text)
        if not candidate.is_absolute():
            candidate = root / candidate
        if candidate.exists() and candidate.is_file():
            resolved.append(candidate.resolve())
    return resolved


def _iter_manifest_paths(artifacts_dir: Path) -> list[Path]:
    paths = set(artifacts_dir.rglob("evidence_manifest.json"))
    paths.update(artifacts_dir.rglob("manifest.json"))
    return sorted(paths)


def _load_records_from_manifest(manifest_path: Path) -> list[dict[str, str]]:
    manifest = _load_json(manifest_path)
    if not manifest:
        return []
    if manifest_path.name == "evidence_manifest.json":
        if str(manifest.get("schema_version", "")).strip() != "evidence-manifest.v1":
            return []

    root = manifest_path.parent
    analysis_paths = _resolve_manifest_entries(manifest.get("analysis_files"), root=root)
    if not analysis_paths:
        return []
    suggestion_paths = _resolve_manifest_entries(manifest.get("suggestion_files"), root=root)
    records = []
    for index, analysis_path in enumerate(analysis_paths):
        suggestion_path = None
        if suggestion_paths:
            suggestion_path = suggestion_paths[index] if index < len(suggestion_paths) else suggestion_paths[0]
        records.append(parse_analysis_file(analysis_path, suggestion_path=suggestion_path))
    return records


def load_analysis_records(artifacts_dir: Path) -> list[dict[str, str]]:
    records = []
    consumed_analysis_paths: set[Path] = set()
    for manifest_path in _iter_manifest_paths(artifacts_dir):
        for record in _load_records_from_manifest(manifest_path):
            record_path = Path(record["path"]).resolve()
            if record_path in consumed_analysis_paths:
                continue
            consumed_analysis_paths.add(record_path)
            records.append(record)
    for path in sorted(artifacts_dir.rglob("analysis.txt")):
        if not path.is_file():
            continue
        resolved = path.resolve()
        if resolved in consumed_analysis_paths:
            continue
        records.append(parse_analysis_file(path))
    return records


def load_suggestion_summary(record: dict[str, str]) -> dict[str, object]:
    analysis_path = Path(record["path"])
    suggestion_path_raw = str(record.get("suggestion_path", "")).strip()
    suggestion_path = Path(suggestion_path_raw) if suggestion_path_raw else analysis_path.parent / "suggestion.json"
    default_summary = {
        "has_suggestion_file": False,
        "actionable": False,
        "advice_type": "",
        "target": "",
        "confidence": 0.0,
    }
    if not suggestion_path.exists():
        return default_summary

    try:
        payload = json.loads(suggestion_path.read_text(encoding="utf-8"))
    except Exception:
        return {**default_summary, "has_suggestion_file": True}

    advice_type = str(payload.get("advice_type", "")).strip()
    target = str(payload.get("target", "")).strip()
    try:
        confidence = float(payload.get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    actionable = advice_type not in {"", "no_change"} and confidence >= 0.5 and bool(target)
    return {
        "has_suggestion_file": True,
        "actionable": actionable,
        "advice_type": advice_type,
        "target": target,
        "confidence": confidence,
    }


def classify_failure_domain(record: dict[str, str]) -> str:
    category = (record.get("failure_category") or "").strip().lower()
    if category in {"environment", "network", "authentication"}:
        return "environment"
    return "business"


def render_summary(records: list[dict[str, str]], artifacts_dir: Path) -> str:
    lines = [
        "AI Failure Analysis Report Summary",
        "",
        f"Artifacts Directory: {artifacts_dir}",
        f"Total Analysis Files: {len(records)}",
        "",
    ]
    if not records:
        lines.append("No analysis.txt files were found.")
        lines.append("")
        return "\n".join(lines)

    category_counter = Counter(record["failure_category"] or "unknown" for record in records)
    risk_counter = Counter(record["risk_level"] or "unknown" for record in records)
    domain_counter = Counter(classify_failure_domain(record) for record in records)
    actionable_suggestion_count = 0

    for record in records:
        suggestion_summary = load_suggestion_summary(record)
        record["suggestion_actionable"] = "yes" if suggestion_summary["actionable"] else "no"
        record["suggestion_advice_type"] = str(suggestion_summary["advice_type"])
        record["suggestion_target"] = str(suggestion_summary["target"])
        record["suggestion_confidence"] = str(suggestion_summary["confidence"])
        if suggestion_summary["actionable"]:
            actionable_suggestion_count += 1

    lines.extend(
        [
            "Management Summary:",
            f"- Total Failed Cases: {len(records)}",
            f"- Environment Failures: {domain_counter.get('environment', 0)}",
            f"- Business Failures: {domain_counter.get('business', 0)}",
            f"- High Risk Failures: {risk_counter.get('high', 0)}",
            f"- Cases With Actionable Self-Healing Advice: {actionable_suggestion_count}",
            "",
            "Failure Categories:",
            *[f"- {name}: {count}" for name, count in sorted(category_counter.items())],
            "",
            "Risk Levels:",
            *[f"- {name}: {count}" for name, count in sorted(risk_counter.items())],
            "",
            "Per-Case Details:",
        ]
    )

    for index, record in enumerate(records, start=1):
        lines.extend(
            [
                f"{index}. Case: {record['case']}",
                f"   Summary: {record['summary'] or '-'}",
                f"   Failure Category: {record['failure_category'] or '-'}",
                f"   Likely Cause: {record['likely_cause'] or '-'}",
                f"   Risk Level: {record['risk_level'] or '-'}",
                f"   Recommended Action: {record['recommended_action'] or '-'}",
                f"   Confidence: {record['confidence'] or '-'}",
                f"   Evidence Used: {record['evidence_used'] or '-'}",
                f"   Actionable Suggestion: {record['suggestion_actionable'] or '-'}",
                f"   Suggestion Advice Type: {record['suggestion_advice_type'] or '-'}",
                f"   Suggestion Target: {record['suggestion_target'] or '-'}",
                f"   Suggestion Confidence: {record['suggestion_confidence'] or '-'}",
                f"   Source File: {record['path']}",
                "",
            ]
        )

    return "\n".join(lines)


def build_report_summary(artifacts_dir: Path, output_path: Path) -> Path:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    records = load_analysis_records(artifacts_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_summary(records, artifacts_dir), encoding="utf-8")
    return output_path


def parse_args() -> argparse.Namespace:
    runner_root = Path(__file__).resolve().parents[1]
    default_artifacts_dir = runner_root / "artifacts"
    default_output_path = default_artifacts_dir / "report_summary.txt"

    parser = argparse.ArgumentParser(
        description="Summarize failure analysis artifacts into a single text report.",
    )
    parser.add_argument(
        "--artifacts-dir",
        default=str(default_artifacts_dir),
        help="Directory containing per-case artifact folders with analysis.txt files.",
    )
    parser.add_argument(
        "--output",
        default=str(default_output_path),
        help="Output path for the generated report_summary.txt file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifacts_dir = Path(args.artifacts_dir).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    build_report_summary(artifacts_dir, output_path)
    print(f"Generated summary: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
