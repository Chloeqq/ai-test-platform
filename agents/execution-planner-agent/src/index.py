# mypy: ignore-errors

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent import ExecutionPlannerAgent


def main() -> int:
    parser = argparse.ArgumentParser(description="Build execution plan for a generated case.")
    parser.add_argument("--input", required=True, help="JSON payload path")
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    case = payload.get("case") if isinstance(payload.get("case"), dict) else {}
    execution_requested = bool(payload.get("execution_requested", False))
    source = str(payload.get("source", "manual")).strip() or "manual"
    execution_config = payload.get("execution_config") if isinstance(payload.get("execution_config"), dict) else {}

    plan = ExecutionPlannerAgent().plan(
        case=case,
        execution_requested=execution_requested,
        source=source,
        execution_config=execution_config,
    )
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
