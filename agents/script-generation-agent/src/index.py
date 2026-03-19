from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent import ScriptGenerationAgent


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate executable script from test case.")
    parser.add_argument("--input", required=True, help="JSON file containing case/framework/language")
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    case = payload.get("case") if isinstance(payload.get("case"), dict) else {}
    framework = str(payload.get("framework", "playwright")).strip() or "playwright"
    language = str(payload.get("language", "python")).strip() or "python"

    result = ScriptGenerationAgent().generate(
        case=case,
        framework=framework,
        language=language,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
