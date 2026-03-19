import json
from pathlib import Path
from typing import Any

from apply_patch import apply_patch_plan
from patch_generator import generate_patch_plan
from rollback import rollback_patch


class SelfHealingExecutor:
    def __init__(
        self,
        *,
        ai_generated_root: Path | None = None,
        page_objects_root: Path | None = None,
        rollback_root: Path | None = None,
    ):
        self.ai_generated_root = ai_generated_root
        self.page_objects_root = page_objects_root
        self.rollback_root = rollback_root

    def preview(self, case_path: Path, suggestion_path: Path) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if self.ai_generated_root is not None:
            kwargs["ai_generated_root"] = self.ai_generated_root
        if self.page_objects_root is not None:
            kwargs["page_objects_root"] = self.page_objects_root
        return generate_patch_plan(case_path, suggestion_path, **kwargs)

    def save_preview(self, plan: dict[str, Any], output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return output_path

    def apply(self, plan_path: Path) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if self.rollback_root is not None:
            kwargs["rollback_root"] = self.rollback_root
        if self.ai_generated_root is not None:
            kwargs["ai_generated_root"] = self.ai_generated_root
        return apply_patch_plan(plan_path, **kwargs)

    def rollback(self, receipt_path: Path) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if self.ai_generated_root is not None:
            kwargs["ai_generated_root"] = self.ai_generated_root
        return rollback_patch(receipt_path, **kwargs)

