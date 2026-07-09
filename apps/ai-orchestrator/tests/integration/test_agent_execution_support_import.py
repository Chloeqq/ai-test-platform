from __future__ import annotations

from pathlib import Path
import sys

import pytest


pytestmark = [pytest.mark.integration]


def test_agent_execution_support_loads_test_design_agent_module(monkeypatch: pytest.MonkeyPatch) -> None:
    src_root = Path(__file__).resolve().parents[2] / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))

    from services.agent_execution_support import AgentExecutionSupport

    repo_root = Path(__file__).resolve().parents[4]
    support = AgentExecutionSupport(
        agent_root=repo_root / "agents" / "test-design-agent",
        script_generation_root=repo_root / "agents" / "script-generation-agent",
        execution_planner_root=repo_root / "agents" / "execution-planner-agent",
        generated_scripts_root=repo_root / "reports" / "executions" / "generated-scripts",
        repo_root=repo_root,
    )

    monkeypatch.setenv("TEST_DESIGN_MODE", "deterministic")

    module = support._load_test_design_agent_module()
    assert hasattr(module, "TestDesignAgent")
    assert hasattr(module, "TestDesignAgentError")

    monkeypatch.setattr(
        module.TestDesignAgent,
        "_safe_list_page_elements",
        staticmethod(lambda _page: ["login_username", "login_password", "login_button"]),
    )

    result = support.generate_case("验证登录成功", "login")
    assert result["id"]
    assert result["execution"]["page"] == "login"
    assert result["execution"]["steps"]
