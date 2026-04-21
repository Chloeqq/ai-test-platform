# mypy: ignore-errors

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from shared_backend.case_ids import build_case_id, match_case_id, next_case_sequence, normalize_case_id


class AgentExecutionSupport:
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
        # Dev fallback; Docker sets PYTHONPATH for agent roots.
        if str(self._agent_root) not in sys.path:
            sys.path.insert(0, str(self._agent_root))

        from src.agent import TestDesignAgent, TestDesignAgentError  # type: ignore[import-not-found]
        from src.tools.yaml_writer import save_yaml  # type: ignore[import-not-found]  # noqa: F401

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

    @staticmethod
    def build_design_generation(case: dict[str, Any]) -> dict[str, Any]:
        return {
            "generator": "test-design-agent",
            "ai_status": "generated",
            "change_source": "ai",
        }
