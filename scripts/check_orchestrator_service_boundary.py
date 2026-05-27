from __future__ import annotations

from pathlib import Path
import sys


MAX_ORCHESTRATOR_LINES = 2000
REPO_ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR_SERVICE_FILE = REPO_ROOT / "apps" / "ai-orchestrator" / "src" / "orchestrator_service.py"
REQUIRED_IMPORTS = (
    "from services.multisource_support import MultisourceSupport",
    "from services.execution_report_support import ExecutionReportSupport",
    "from services.analytics_query_support import AnalyticsQuerySupport",
    "from services.failure_healing_support import FailureHealingSupport",
    "from services.requirement_testpoint_support import RequirementTestPointSupport",
    "from services.requirement_parse_support import RequirementParseSupport",
    "from services.agent_execution_support import AgentExecutionSupport",
    "from services.orchestration_flow_support import OrchestrationFlowSupport",
)
FORBIDDEN_SNIPPETS = (
    "from tools.report_summary import build_report_summary",
)


def check_orchestrator_service_boundary(target: Path = ORCHESTRATOR_SERVICE_FILE) -> list[str]:
    issues: list[str] = []
    text = target.read_text(encoding="utf-8")
    line_count = len(text.splitlines())
    if line_count > MAX_ORCHESTRATOR_LINES:
        issues.append(
            f"orchestrator_service.py has {line_count} lines, exceeds boundary limit {MAX_ORCHESTRATOR_LINES}."
        )
    for marker in REQUIRED_IMPORTS:
        if marker not in text:
            issues.append(f"orchestrator_service.py is missing required support import: {marker}")
    for marker in FORBIDDEN_SNIPPETS:
        if marker in text:
            issues.append(f"orchestrator_service.py must delegate report-summary logic via support modules: {marker}")
    return issues


def main() -> int:
    issues = check_orchestrator_service_boundary()
    if not issues:
        print("orchestrator_service boundary check passed")
        return 0
    for issue in issues:
        print(issue)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
