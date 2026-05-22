# mypy: ignore-errors
"""Agent 执行支撑：加载 test-design-agent 并生成用例与设计元数据。"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any
import types

from shared_backend.case_ids import build_case_id, match_case_id, next_case_sequence, normalize_case_id


class AgentExecutionSupport:
    """封装测试设计 Agent 的动态加载与 case_id 分配。"""

    def __init__(
        self,
        *,
        agent_root: Path,
        script_generation_root: Path,
        execution_planner_root: Path,
        generated_scripts_root: Path,
        repo_root: Path | None = None,
    ) -> None:
        self._agent_root = agent_root
        self._script_generation_root = script_generation_root
        self._execution_planner_root = execution_planner_root
        self._generated_scripts_root = generated_scripts_root
        self._repo_root = repo_root if isinstance(repo_root, Path) else self._resolve_repo_root(agent_root)
        self._assets_cases_root = self._repo_root / "assets" / "test-cases"
        self._test_design_agent_module: Any | None = None

    @staticmethod
    def _resolve_repo_root(agent_root: Path) -> Path:
        root = agent_root if isinstance(agent_root, Path) else Path(str(agent_root))
        candidates = [root, *list(root.parents)]
        for candidate in candidates:
            if (candidate / "apps").exists() and (candidate / "assets").exists():
                return candidate
        return candidates[-1] if candidates else root

    def _allocate_case_id(self, *, page: str, module: str, preferred: str = "") -> str:
        normalized_preferred = normalize_case_id(preferred, fallback="").strip() if str(preferred).strip() else ""
        # Only reuse preferred id when it already conforms to shared_backend case_id format.
        if normalized_preferred and match_case_id(normalized_preferred):
            return normalized_preferred
        existing_case_ids: list[str] = []
        if self._assets_cases_root.exists():
            for path in self._assets_cases_root.rglob("*.yaml"):
                existing_case_ids.append(path.stem)
        sequence = next_case_sequence(
            existing_case_ids=existing_case_ids,
            page=page,
            module=module,
            case_type="FN",
            source="AI",
        )
        return build_case_id(page=page, module=module, case_type="FN", source="AI", sequence=sequence)

    def generate_case(self, requirement: str, page: str) -> dict[str, Any]:
        """调用 TestDesignAgent 根据自然语言需求生成 YAML 用例结构。"""
        agent_module = self._load_test_design_agent_module()
        TestDesignAgent = getattr(agent_module, "TestDesignAgent", None)
        TestDesignAgentError = getattr(agent_module, "TestDesignAgentError", None)
        if TestDesignAgent is None or TestDesignAgentError is None:
            raise RuntimeError("test-design-agent module is missing required exports")

        agent = TestDesignAgent()
        normalized_page = str(page).strip() or "product"
        try:
            generated = agent.generate(requirement=requirement, page=normalized_page)
            if isinstance(generated, dict) and generated:
                return generated
            raise RuntimeError("test-design-agent returned empty payload")
        except TestDesignAgentError as exc:
            raise RuntimeError(json.dumps(exc.to_dict(), ensure_ascii=False)) from exc
        except Exception as exc:
            raise RuntimeError(f"test-design-agent generate failed: {str(exc)[:240]}") from exc

    def _load_test_design_agent_module(self) -> Any:
        cached = self._test_design_agent_module
        if cached is not None:
            return cached

        agent_src_dir = self._agent_root / "src"
        agent_module_path = agent_src_dir / "agent.py"
        if not agent_module_path.exists():
            raise FileNotFoundError(f"test-design-agent module not found: {agent_module_path}")

        package_root_name = "_ai_test_platform_test_design_agent"
        package_src_name = f"{package_root_name}.src"
        if package_root_name not in sys.modules:
            root_pkg = types.ModuleType(package_root_name)
            root_pkg.__path__ = [str(self._agent_root)]  # type: ignore[attr-defined]
            root_pkg.__package__ = package_root_name
            sys.modules[package_root_name] = root_pkg
        if package_src_name not in sys.modules:
            src_pkg = types.ModuleType(package_src_name)
            src_pkg.__path__ = [str(agent_src_dir)]  # type: ignore[attr-defined]
            src_pkg.__package__ = package_src_name
            sys.modules[package_src_name] = src_pkg

        module_name = f"{package_src_name}.agent"
        spec = importlib.util.spec_from_file_location(module_name, str(agent_module_path))
        if spec is None or spec.loader is None:
            raise ImportError(f"unable to load test-design-agent module: {agent_module_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        self._test_design_agent_module = module
        return module

    @staticmethod
    def build_design_generation(case: dict[str, Any]) -> dict[str, Any]:
        return {
            "generator": "test-design-agent",
            "ai_status": "generated",
            "change_source": "ai",
        }
