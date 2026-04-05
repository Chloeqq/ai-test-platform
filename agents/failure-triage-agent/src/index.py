# mypy: ignore-errors

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent import FailureTriageAgent


def main() -> int:
    parser = argparse.ArgumentParser(description="Run failure triage classification.")
    parser.add_argument("--input", required=True, help="JSON payload path")
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    report = payload.get("report") if isinstance(payload.get("report"), dict) else {}
    failure_analysis = payload.get("failure_analysis") if isinstance(payload.get("failure_analysis"), dict) else {}
    execution_record = payload.get("execution_record") if isinstance(payload.get("execution_record"), dict) else {}
    evidence_manifest = payload.get("evidence_manifest") if isinstance(payload.get("evidence_manifest"), dict) else {}

    if not failure_analysis and report:
        nested = report.get("failure_analysis")
        if isinstance(nested, dict):
            failure_analysis = nested
    if not execution_record and report:
        nested = report.get("execution_record")
        if isinstance(nested, dict):
            execution_record = nested
    if not evidence_manifest and report:
        nested = report.get("evidence")
        if isinstance(nested, dict):
            evidence_manifest = nested

    triage = FailureTriageAgent().triage(
        failure_analysis=failure_analysis,
        execution_record=execution_record,
        evidence_manifest=evidence_manifest,
        report=report,
    )
    print(json.dumps(triage, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
