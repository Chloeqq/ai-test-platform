from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent import TestDesignAgent


def main():
    parser = argparse.ArgumentParser(description="Generate test cases or enterprise design bundles.")
    parser.add_argument("--input", default="", help="Optional JSON input file")
    parser.add_argument("--bundle", action="store_true", help="Emit enterprise design bundle instead of raw test case")
    parser.add_argument("--requirement", default="", help="Raw requirement text")
    parser.add_argument("--page", default="", help="Target page slug")
    args = parser.parse_args()

    payload: dict = {}
    if args.input:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))

    requirement = str(payload.get("requirement", "")).strip() or str(args.requirement or "").strip()
    page = str(payload.get("page", "")).strip() or str(args.page or "").strip()
    requirement_spec = payload.get("requirement_spec") if isinstance(payload.get("requirement_spec"), dict) else {}
    case = payload.get("case") if isinstance(payload.get("case"), dict) else None

    if not page:
        raise ValueError("page is required. pass --page or input.page")

    if not requirement:
        spec_design_input = str(requirement_spec.get("design_input", "")).strip() if requirement_spec else ""
        spec_raw_requirement = str(requirement_spec.get("raw_requirement", "")).strip() if requirement_spec else ""
        if not spec_design_input and not spec_raw_requirement and case is None:
            raise ValueError("requirement is required. pass --requirement or input.requirement")

    agent = TestDesignAgent()
    if args.bundle or requirement_spec or case is not None:
        result = agent.design_bundle(
            requirement=requirement,
            page=page,
            requirement_spec=requirement_spec,
            case=case,
        )
    else:
        result = agent.generate(requirement, page=page)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
