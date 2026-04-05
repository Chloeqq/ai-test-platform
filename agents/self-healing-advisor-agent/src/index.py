# mypy: ignore-errors

import argparse
import json
import sys
from pathlib import Path

try:
    from .agent import SelfHealingAdvisorAgent
except ImportError:  # pragma: no cover - direct module execution fallback
    from agent import SelfHealingAdvisorAgent


def _load_payload(input_path: str | None) -> dict:
    if input_path:
        return json.loads(Path(input_path).read_text(encoding="utf-8"))

    raw = sys.stdin.read().strip()
    if not raw:
        raise ValueError("No input payload provided. Use --input or pipe JSON via stdin.")
    return json.loads(raw)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate self-healing advice without modifying YAML.")
    parser.add_argument("--input", help="Path to a JSON payload file")
    parser.add_argument("--model", help="Override model name")
    args = parser.parse_args()

    payload = _load_payload(args.input)
    agent = SelfHealingAdvisorAgent(model=args.model)
    result = agent.advise(payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
