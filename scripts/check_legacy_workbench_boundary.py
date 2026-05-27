from __future__ import annotations

from pathlib import Path
import sys


MAX_LEGACY_LINES = 2400
REPO_ROOT = Path(__file__).resolve().parents[1]
LEGACY_WORKBENCH_FILE = REPO_ROOT / "apps" / "web-ui-service" / "app" / "routers" / "legacy_workbench.py"
FORBIDDEN_ROUTE_DECORATORS = ("@router.", "@router.get(", "@router.post(", "@router.put(", "@router.delete(")


def check_legacy_workbench_boundary(target: Path = LEGACY_WORKBENCH_FILE) -> list[str]:
    issues: list[str] = []
    text = target.read_text(encoding="utf-8")
    line_count = len(text.splitlines())
    if line_count > MAX_LEGACY_LINES:
        issues.append(
            f"legacy_workbench.py has {line_count} lines, exceeds boundary limit {MAX_LEGACY_LINES}."
        )
    if any(marker in text for marker in FORBIDDEN_ROUTE_DECORATORS):
        issues.append("legacy_workbench.py must not define new FastAPI route decorators.")
    return issues


def main() -> int:
    issues = check_legacy_workbench_boundary()
    if not issues:
        print("legacy_workbench boundary check passed")
        return 0
    for issue in issues:
        print(issue)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
