# mypy: ignore-errors

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent import RiskEvaluationAgent


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate risk report from execution context.")
    parser.add_argument("--input", required=True, help="JSON payload path")
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    requirement_spec = payload.get("requirement_spec") if isinstance(payload.get("requirement_spec"), dict) else {}
    execution_plan = payload.get("execution_plan") if isinstance(payload.get("execution_plan"), dict) else {}
    execution_record = payload.get("execution_record") if isinstance(payload.get("execution_record"), dict) else {}
    failure_analysis = payload.get("failure_analysis") if isinstance(payload.get("failure_analysis"), dict) else {}
    failure_triage = payload.get("failure_triage") if isinstance(payload.get("failure_triage"), dict) else {}

    report = RiskEvaluationAgent().evaluate(
        requirement_spec=requirement_spec,
        execution_plan=execution_plan,
        execution_record=execution_record,
        failure_analysis=failure_analysis,
        failure_triage=failure_triage,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
