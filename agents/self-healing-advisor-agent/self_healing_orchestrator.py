import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from patch_generator import AI_GENERATED_ROOT, is_path_within, load_yaml
from rerun_runner import RerunRunner
from self_healing_executor import SelfHealingExecutor


DEFAULT_RESULT_FILE = "self_healing_result.json"
DEFAULT_PLAN_FILE = "self_healing_patch_plan.json"
RerunCallback = Callable[[Path], Any]


class SelfHealingOrchestrator:
    def __init__(
        self,
        *,
        executor: SelfHealingExecutor | None = None,
        rerun_runner: RerunRunner | None = None,
        ai_generated_root: Path = AI_GENERATED_ROOT,
        min_confidence: float = 0.7,
        max_attempts: int = 1,
    ):
        self.executor = executor or SelfHealingExecutor(ai_generated_root=ai_generated_root)
        self.rerun_runner = rerun_runner or RerunRunner()
        self.ai_generated_root = ai_generated_root
        self.min_confidence = min_confidence
        self.max_attempts = max_attempts

    def run_from_artifacts(
        self,
        artifact_dir: Path,
        case_path: Path,
        *,
        previous_attempts: int = 0,
        rerun_case: RerunCallback | None = None,
    ) -> dict[str, Any]:
        artifact_dir = artifact_dir.resolve()
        artifact_dir.mkdir(parents=True, exist_ok=True)
        suggestion_path = artifact_dir / "suggestion.json"
        if not suggestion_path.exists():
            raise FileNotFoundError(f"suggestion.json not found under: {artifact_dir}")

        result = self.run_once(
            case_path=case_path,
            suggestion_path=suggestion_path,
            previous_attempts=previous_attempts,
            rerun_case=rerun_case,
            plan_output_path=artifact_dir / DEFAULT_PLAN_FILE,
        )
        result["artifact_dir"] = str(artifact_dir)
        result_path = artifact_dir / DEFAULT_RESULT_FILE
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result["result_path"] = str(result_path)
        return result

    def run_once(
        self,
        *,
        case_path: Path,
        suggestion_path: Path,
        previous_attempts: int = 0,
        rerun_case: RerunCallback | None = None,
        plan_output_path: Path | None = None,
    ) -> dict[str, Any]:
        case_path = case_path.resolve()
        suggestion_path = suggestion_path.resolve()

        if previous_attempts >= self.max_attempts:
            return self._rejected_result(
                case_path=case_path,
                suggestion_path=suggestion_path,
                reason=f"Maximum self-healing attempts reached ({self.max_attempts}).",
            )

        if not is_path_within(case_path, self.ai_generated_root):
            return self._rejected_result(
                case_path=case_path,
                suggestion_path=suggestion_path,
                reason="Only ai-generated YAML cases can be auto-healed.",
            )

        suggestion_data = json.loads(suggestion_path.read_text(encoding="utf-8"))
        if not isinstance(suggestion_data, dict):
            raise ValueError("suggestion.json must contain an object.")

        confidence = self._parse_confidence(suggestion_data)
        if confidence <= self.min_confidence:
            return self._rejected_result(
                case_path=case_path,
                suggestion_path=suggestion_path,
                reason=f"Confidence must be greater than {self.min_confidence:.1f}.",
                confidence=confidence,
            )

        plan = self.executor.preview(case_path, suggestion_path)
        if plan_output_path is not None:
            self.executor.save_preview(plan, plan_output_path)
        if not plan.get("allowed_to_apply"):
            return self._rejected_result(
                case_path=case_path,
                suggestion_path=suggestion_path,
                reason=str(plan.get("reason", "Patch preview was rejected.")),
                confidence=confidence,
                plan=plan,
                plan_path=str(plan_output_path.resolve()) if plan_output_path is not None else "",
            )

        plan_path = plan_output_path
        if plan_path is None:
            plan_path = suggestion_path.parent / DEFAULT_PLAN_FILE
            self.executor.save_preview(plan, plan_path)

        receipt = self.executor.apply(plan_path)
        rerun_result = self._run_rerun(case_path, rerun_case, previous_attempts=previous_attempts)
        if self._rerun_succeeded(rerun_result):
            return {
                "status": "success",
                "reason": "Patch applied and rerun succeeded.",
                "attempts_used": 1,
                "max_attempts": self.max_attempts,
                "case_path": str(case_path),
                "suggestion_path": str(suggestion_path),
                "confidence": confidence,
                "plan": plan,
                "plan_path": str(plan_path.resolve()),
                "receipt": receipt,
                "rerun_result": self._serialize_rerun_result(rerun_result),
                "rolled_back": False,
                "healed": True,
            }

        rollback_result = self.executor.rollback(Path(receipt["receipt_path"]))
        return {
            "status": "rollback",
            "reason": "Patch applied but rerun failed; rollback completed.",
            "attempts_used": 1,
            "max_attempts": self.max_attempts,
            "case_path": str(case_path),
            "suggestion_path": str(suggestion_path),
            "confidence": confidence,
            "plan": plan,
            "plan_path": str(plan_path.resolve()),
            "receipt": receipt,
            "rerun_result": self._serialize_rerun_result(rerun_result),
            "rollback_result": rollback_result,
            "rolled_back": True,
            "healed": False,
        }

    def _run_rerun(self, case_path: Path, rerun_case: RerunCallback | None, *, previous_attempts: int) -> Any:
        if rerun_case is not None:
            return rerun_case(case_path)

        case_data = load_yaml(case_path)
        case_id = str(case_data.get("id", "")).strip()
        return self.rerun_runner.run(case_path=case_path, case_id=case_id, previous_attempts=previous_attempts)

    def _rejected_result(
        self,
        *,
        case_path: Path,
        suggestion_path: Path,
        reason: str,
        confidence: float = 0.0,
        plan: dict[str, Any] | None = None,
        plan_path: str = "",
    ) -> dict[str, Any]:
        return {
            "status": "rejected",
            "reason": reason,
            "attempts_used": 0,
            "max_attempts": self.max_attempts,
            "case_path": str(case_path),
            "suggestion_path": str(suggestion_path),
            "confidence": confidence,
            "plan": plan or {},
            "plan_path": plan_path,
            "boundary": (plan or {}).get("boundary", {}),
            "rolled_back": False,
            "healed": False,
        }

    @staticmethod
    def _parse_confidence(suggestion_data: dict[str, Any]) -> float:
        try:
            return float(suggestion_data.get("confidence", 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _rerun_succeeded(result: Any) -> bool:
        if isinstance(result, bool):
            return result
        if isinstance(result, dict):
            if "success" in result:
                return bool(result["success"])
            if "returncode" in result:
                return int(result["returncode"]) == 0
            return False
        return int(getattr(result, "returncode", 1)) == 0

    @staticmethod
    def _serialize_rerun_result(result: Any) -> Any:
        if isinstance(result, (str, int, float, bool, list, dict)) or result is None:
            return result
        if hasattr(result, "returncode"):
            return {
                "returncode": int(getattr(result, "returncode", 1)),
                "stdout": str(getattr(result, "stdout", "")),
                "stderr": str(getattr(result, "stderr", "")),
            }
        return {"repr": repr(result)}
