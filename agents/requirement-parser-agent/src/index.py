# mypy: ignore-errors

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .agent import RequirementParserAgent


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse requirement text into RequirementSpecV1.")
    parser.add_argument("--requirement", default="", help="Raw requirement text")
    parser.add_argument("--page", default="", help="Target page slug")
    parser.add_argument("--input", default="", help="Optional JSON input file containing requirement/openapi_spec")
    args = parser.parse_args()

    payload: dict = {}
    if args.input:
        input_path = Path(args.input)
        payload = json.loads(input_path.read_text(encoding="utf-8"))

    requirement = str(payload.get("requirement", "")).strip() or args.requirement
    page = str(payload.get("page", "")).strip() or args.page
    openapi_spec = payload.get("openapi_spec")
    source_type = str(payload.get("source_type", "text")).strip() or "text"
    input_sources = payload.get("input_sources")
    prd_text = str(payload.get("prd_text", "")).strip()
    prd_url = str(payload.get("prd_url", "")).strip()
    user_story = str(payload.get("user_story", "")).strip()
    git_diff = str(payload.get("git_diff", "")).strip()
    git_diff_path = str(payload.get("git_diff_path", "")).strip()
    openapi_url = str(payload.get("openapi_url", "")).strip()
    defect_ticket = str(payload.get("defect_ticket", "")).strip()
    runtime_logs = str(payload.get("runtime_logs", "")).strip()

    try:
        result = RequirementParserAgent().parse(
            requirement=requirement,
            page=page,
            source_type=source_type,
            openapi_spec=openapi_spec if isinstance(openapi_spec, dict) else None,
            input_sources=input_sources if isinstance(input_sources, list) else None,
            prd_text=prd_text,
            prd_url=prd_url,
            user_story=user_story,
            git_diff=git_diff,
            git_diff_path=git_diff_path,
            openapi_url=openapi_url,
            defect_ticket=defect_ticket,
            runtime_logs=runtime_logs,
        )
    except Exception as exc:
        # Keep forced-llm behavior strict, but return a compact structured error
        # instead of a full traceback, so upstream can surface actionable details.
        error_payload = {
            "error": {
                "code": "requirement_parser_runtime_error",
                "type": exc.__class__.__name__,
                "message": str(exc),
            }
        }
        print(json.dumps(error_payload, ensure_ascii=False), file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
