from __future__ import annotations

import importlib.util
from pathlib import Path


def test_orchestrator_service_boundary_guard() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    script_path = repo_root / "scripts" / "check_orchestrator_service_boundary.py"
    spec = importlib.util.spec_from_file_location("check_orchestrator_service_boundary", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    issues = module.check_orchestrator_service_boundary()

    assert issues == []
