# mypy: ignore-errors

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from shared_backend.case_ids import build_case_id, next_case_sequence, normalize_case_id


class AgentExecutionSupport:
    def __init__(
        self,
        *,
        agent_root: Path,
        script_generation_root: Path,
        execution_planner_root: Path,
        generated_scripts_root: Path,
        test_point_steps_authoritative: bool,
    ) -> None:
        self._agent_root = agent_root
        self._script_generation_root = script_generation_root
        self._execution_planner_root = execution_planner_root
        self._generated_scripts_root = generated_scripts_root
        self._test_point_steps_authoritative = test_point_steps_authoritative
        self._repo_root = agent_root.parents[3]
        self._assets_cases_root = self._repo_root / "assets" / "test-cases"

    def _allocate_case_id(self, *, page: str, module: str, preferred: str = "") -> str:
        normalized_preferred = normalize_case_id(preferred, fallback="").strip() if str(preferred).strip() else ""
        if normalized_preferred.count("-") >= 2 and normalized_preferred.rsplit("-", 1)[-1].isdigit():
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

    def generate_script_bundle(
        self,
        *,
        case: dict[str, Any],
        framework: str,
        language: str,
    ) -> dict[str, Any]:
        payload = {
            "framework": framework,
            "language": language,
            "case": case,
        }
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(json.dumps(payload, ensure_ascii=False))
            completed = subprocess.run(
                [sys.executable, "-m", "src.index", "--input", str(temp_path)],
                cwd=str(self._script_generation_root),
                text=True,
                capture_output=True,
                check=False,
            )
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "script generation failed")
            parsed = json.loads(completed.stdout.strip() or "{}")
            if not isinstance(parsed, dict):
                raise RuntimeError("script generation returned non-object payload")
            script_code = str(parsed.get("script_code", "")).strip()
            filename = str(parsed.get("filename", "")).strip()
            if script_code and filename:
                self._generated_scripts_root.mkdir(parents=True, exist_ok=True)
                output_path = self._generated_scripts_root / filename
                output_path.write_text(script_code + "\n", encoding="utf-8")
                parsed["script_path"] = str(output_path)
            return parsed
        except Exception as exc:
            return {
                "version": "GeneratedScriptV1",
                "framework": framework,
                "language": language,
                "case_id": str(case.get("id", "")).strip(),
                "page": str((case.get("execution") or {}).get("page", "")).strip(),
                "filename": "",
                "entrypoint": "",
                "script_code": "",
                "script_path": "",
                "metadata": {"error": str(exc)},
            }

    def build_execution_plan(
        self,
        *,
        case: dict[str, Any],
        execution_requested: bool,
        source: str,
        execution_config: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            "case": case,
            "execution_requested": execution_requested,
            "source": source,
            "execution_config": execution_config,
        }
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(json.dumps(payload, ensure_ascii=False))
            completed = subprocess.run(
                [sys.executable, "-m", "src.index", "--input", str(temp_path)],
                cwd=str(self._execution_planner_root),
                text=True,
                capture_output=True,
                check=False,
            )
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "execution planner failed")
            parsed = json.loads(completed.stdout.strip() or "{}")
            if not isinstance(parsed, dict):
                raise RuntimeError("execution planner returned non-object payload")
            return parsed
        except Exception as exc:
            return {
                "version": "ExecutionPlanV1",
                "run_mode": "generate_and_run" if execution_requested else "generate_only",
                "source": source,
                "priority": str(case.get("priority", "P1")).strip() or "P1",
                "environment": "test",
                "parallelism": 1,
                "retry_policy": {"enabled": bool(execution_requested), "max_retries": 1, "backoff_seconds": 5},
                "stages": [],
                "scheduling_hints": {"queue": "normal", "expected_total_seconds": 60, "resource_profile": "default"},
                "metadata": {"error": str(exc)},
            }

    def generate_case(self, requirement: str, page: str) -> dict[str, Any]:
        if str(self._agent_root) not in sys.path:
            sys.path.insert(0, str(self._agent_root))

        from src.agent import TestDesignAgent  # type: ignore[import-not-found]
        from src.tools.yaml_writer import save_yaml  # type: ignore[import-not-found]  # noqa: F401

        agent = TestDesignAgent()
        normalized_page = str(page).strip() or "product"
        try:
            generated = agent.generate(requirement=requirement, page=normalized_page)
            if isinstance(generated, dict) and generated:
                return generated
        except Exception as exc:
            return self.build_design_fallback_case(
                requirement=requirement,
                page=normalized_page,
                reason=str(exc),
            )
        return self.build_design_fallback_case(
            requirement=requirement,
            page=normalized_page,
            reason="test-design-agent returned empty payload",
        )

    def build_design_fallback_case(self, *, requirement: str, page: str, reason: str, runner: str = "playwright") -> dict[str, Any]:
        normalized_page = str(page).strip().lower() or "product"
        case_id = self._allocate_case_id(page=normalized_page, module=normalized_page)
        menu_target = f"{normalized_page}_menu"
        title_target = f"{normalized_page}_list_title"
        safe_requirement = str(requirement or "").strip() or f"{normalized_page} 页面核心流程验证"
        return {
            "version": "v4",
            "id": case_id,
            "title": f"{normalized_page}页面-核心流程-回退生成-执行基础冒烟-关键元素可见",
            "module": normalized_page,
            "priority": "P1",
            "tags": ["ai-generated", "smoke", normalized_page, "fallback"],
            "owner": "qa-team",
            "status": "automated",
            "source": "fb",
            "ai_status": "generated",
            "change_source": "ai",
            "description": f"由于测试设计代理生成失败，平台已回退生成基础冒烟用例。失败原因：{reason[:200]}",
            "requirement": [safe_requirement],
            "data": {},
            "execution": {
                "runner": str(runner or "playwright").strip() or "playwright",
                "page": normalized_page,
                "variables": {},
                "steps": [
                    {"action": "login"},
                    {"action": "click", "target": menu_target},
                    {"action": "wait_for", "target": title_target},
                    {"action": "assert_visible", "target": title_target},
                ],
            },
        }

    @staticmethod
    def build_design_generation(case: dict[str, Any]) -> dict[str, Any]:
        tags = [str(item).strip().lower() for item in (case.get("tags") or []) if str(item).strip()]
        description = str(case.get("description", "")).strip()
        lowered_description = description.lower()
        fallback_used = (
            ("fallback" in tags)
            or ("fallback case generated because test-design-agent failed" in lowered_description)
            or ("回退生成基础冒烟用例" in description)
            or ("测试设计代理生成失败" in description)
        )
        fallback_reason = ""
        marker = "failed:"
        if fallback_used and marker in lowered_description:
            original_parts = description.split("failed:", 1)
            if len(original_parts) > 1:
                fallback_reason = original_parts[1].strip()
        if fallback_used and "失败原因：" in description:
            original_parts = description.split("失败原因：", 1)
            if len(original_parts) > 1:
                fallback_reason = original_parts[1].strip()
        if fallback_used and not fallback_reason:
            fallback_reason = "test-design-agent returned fallback case"
        return {
            "generator": "test-design-agent",
            "fallback_used": fallback_used,
            "fallback_reason": fallback_reason,
            "ai_status": "generated",
            "change_source": "ai",
        }

    def render_case_steps_from_test_points(self, *, case: dict[str, Any], test_points: dict[str, Any]) -> dict[str, Any]:
        rendered = dict(case)
        execution = rendered.get("execution") if isinstance(rendered.get("execution"), dict) else {}
        existing_steps = execution.get("steps") if isinstance(execution.get("steps"), list) else []
        if existing_steps and not self._test_point_steps_authoritative:
            return rendered

        points = test_points.get("points") if isinstance(test_points.get("points"), list) else []
        steps: list[dict[str, Any]] = []
        for point in points:
            if not isinstance(point, dict):
                continue
            action = str(point.get("action", "")).strip()
            if not action:
                continue
            step: dict[str, Any] = {"action": action}
            target = str(point.get("target", "")).strip()
            if target:
                step["target"] = target
            if "value" in point and point.get("value") is not None:
                step["value"] = point.get("value")
            traceability = (
                point.get("metadata", {}).get("traceability")
                if isinstance(point.get("metadata"), dict) and isinstance(point.get("metadata", {}).get("traceability"), dict)
                else {}
            )
            step["source_point_key"] = str(point.get("key", "")).strip()
            if traceability:
                step["traceability"] = {
                    "intent_ids": [str(item).strip() for item in (traceability.get("intent_ids") or []) if str(item).strip()],
                    "source_ids": [str(item).strip() for item in (traceability.get("source_ids") or []) if str(item).strip()],
                    "origin": str(traceability.get("origin", "")).strip() or "requirement_intent",
                }
            if steps and steps[-1] == step:
                continue
            steps.append(step)
        if steps:
            execution = dict(execution)
            execution["steps"] = steps
            rendered["execution"] = execution
        return rendered
