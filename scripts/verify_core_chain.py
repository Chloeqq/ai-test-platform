#!/usr/bin/env python3
"""核心链路冒烟验证——纯 import 检查，不依赖 DB/LLM/浏览器。"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "web-ui-service"))
# 不加 apps/ai-orchestrator/src → 避免 app.py 和 app/ 包冲突
# orchestrator 的 import 单独处理

passed = 0
failed = 0


def check(name: str, mod_name: str, attr: str | None = None) -> None:
    global passed, failed
    try:
        mod = importlib.import_module(mod_name)
        if attr:
            getattr(mod, attr)
        print(f"  ✅ {name}")
        passed += 1
    except Exception as exc:
        print(f"  ❌ {name}: {type(exc).__name__}: {exc}")
        failed += 1


print("\n🔗 生成链路")
GEN = "app.services.workbench_generation_compiler.runtime.generate_pipeline"
check("facade", "app.api.workbench.facade")
check("generate_pipeline", GEN, "run_generate_pipeline")
for step, fn in [
    ("Step 1: parse", "_call_orchestrator_and_parse"),
    ("Step 2: normalize", "_normalize_and_scope_test_points"),
    ("Step 3: validate", "_validate_and_compile_steps"),
    ("Step 4: allocate", "_allocate_and_format_case_id"),
    ("Step 5: persist", "_persist_and_build_response"),
    ("exception handler", "_handle_generation_exception"),
]:
    check(step, GEN, fn)

print("\n⚡ 执行链路")
RTS = "app.services.workbench_runtime_service"
for fn in ["execute_run", "start_run", "build_run_command"]:
    check(fn, RTS, fn)

print("\n🤖 Orchestrator")
sys.path.insert(0, str(ROOT / "apps" / "ai-orchestrator" / "src"))
check("orchestrator_service", "orchestrator_service", "OrchestratorService")
check("FastAPI app", "main", "app")
sys.path.pop(0)

print("\n📦 Repository 层")
for mod, cls in [
    ("app.repositories.test_case_repository", "TestCaseRepository"),
    ("app.repositories.page_object_repository", "PageObjectRepository"),
    ("app.repositories.recorder_repository", "RecorderRepository"),
    ("app.repositories.test_project_repository", "TestProjectRepository"),
    ("app.repositories.test_data_pool_repository", "TestDataPoolRepository"),
]:
    check(cls, mod, cls)

print("\n🧰 shared_backend")
for mod in ["type_utils", "db", "execution_compiler", "element_binding", "case_ids"]:
    check(mod, f"shared_backend.{mod}")

print("\n🛡️ DSL V1.1")
check("compiler", "shared_backend.execution_compiler", "compile_execution_steps")
check("ExecutionCompilerError", "shared_backend.execution_compiler", "ExecutionCompilerError")

print("\n📋 审核 + 治理链")
check("review_service", "app.services.workbench_review_service")
check("governance(overview)", "app.services.workbench_governance_service", "build_dashboard_overview")
check("governance(flaky)", "app.services.workbench_governance_service", "build_flaky_top5")

print(f"\n{'='*40}\n  {passed} passed, {failed} failed\n{'='*40}")
sys.exit(1 if failed > 0 else 0)
