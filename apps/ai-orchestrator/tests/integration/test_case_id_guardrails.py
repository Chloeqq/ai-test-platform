from __future__ import annotations

from pathlib import Path
import sys

from shared_backend.case_ids import match_case_id

src_root = Path(__file__).resolve().parents[2] / "src"
if str(src_root) not in sys.path:
    sys.path.insert(0, str(src_root))


def test_allocate_case_id_rejects_legacy_smoke_preferred(tmp_path: Path) -> None:
    from services.agent_execution_support import AgentExecutionSupport

    support = AgentExecutionSupport(
        agent_root=tmp_path / "agents" / "test-design-agent",
        script_generation_root=tmp_path / "agents" / "script-generation-agent",
        execution_planner_root=tmp_path / "agents" / "execution-planner-agent",
        generated_scripts_root=tmp_path / "reports" / "generated-scripts",
    )
    support._assets_cases_root = tmp_path / "assets" / "test-cases"
    support._assets_cases_root.mkdir(parents=True, exist_ok=True)

    allocated = support._allocate_case_id(
        page="returnapply",
        module="query",
        preferred="SMOKE-RETURNAPPLY-020005",
    )

    assert match_case_id(allocated)
    assert not allocated.startswith("smoke-")
    assert allocated.startswith("atp-")
