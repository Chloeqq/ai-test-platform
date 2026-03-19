import argparse
import difflib
import hashlib
import json
from datetime_compat import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
AI_GENERATED_ROOT = REPO_ROOT / "assets" / "test-cases" / "ai-generated"
PAGE_OBJECTS_ROOT = REPO_ROOT / "assets" / "page-objects" / "web"
AUTO_HEAL_BOUNDARY_VERSION = "SelfHealingBoundaryV1"
ALLOWED_AUTO_HEAL_ADVICE_TYPES = {"locator_update", "wait_strategy"}
PREVIEW_ONLY_ADVICE_TYPES = {
    "assertion_update",
    "data_adjustment",
    "environment_check",
    "no_change",
}


def sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML file must contain an object: {path}")
    return data


def dump_yaml_text(data: dict[str, Any]) -> str:
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


def build_unified_diff(original_text: str, updated_text: str, *, original_path: Path) -> str:
    diff = difflib.unified_diff(
        original_text.splitlines(),
        updated_text.splitlines(),
        fromfile=str(original_path),
        tofile=str(original_path),
        lineterm="",
    )
    return "\n".join(diff) + ("\n" if original_text != updated_text else "")


def is_path_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def load_available_targets(page_name: str, page_objects_root: Path = PAGE_OBJECTS_ROOT) -> list[str]:
    page_object_path = page_objects_root / f"{page_name}.page-object.yaml"
    if not page_object_path.exists():
        return []
    page_object = load_yaml(page_object_path)
    elements = page_object.get("elements", {})
    if not isinstance(elements, dict):
        return []
    return [str(name).strip() for name in elements.keys() if str(name).strip()]


def build_auto_heal_boundary_summary(*, advice_type: str) -> dict[str, Any]:
    normalized_advice_type = str(advice_type or "").strip()
    allowed = normalized_advice_type in ALLOWED_AUTO_HEAL_ADVICE_TYPES
    reason = (
        f"Advice type '{normalized_advice_type}' is within deterministic auto-healing boundary."
        if allowed
        else (
            f"Advice type '{normalized_advice_type}' is outside deterministic auto-healing boundary. "
            "Only locator_update and wait_strategy can be auto-applied."
        )
    )
    return {
        "version": AUTO_HEAL_BOUNDARY_VERSION,
        "mode": "deterministic-guardrail",
        "allowed": allowed,
        "advice_type": normalized_advice_type,
        "allowed_advice_types": sorted(ALLOWED_AUTO_HEAL_ADVICE_TYPES),
        "preview_only_advice_types": sorted(PREVIEW_ONLY_ADVICE_TYPES),
        "forbidden_mutations": [
            "business_assertion_change",
            "business_flow_change",
            "page_object_writeback",
            "login_step_mutation",
        ],
        "allowed_mutations": [
            "replace_existing_target_reference",
            "swap_wait_target_to_existing_page_object_target",
        ],
        "reason": reason,
    }


def _primary_assertion_target(steps: list[dict[str, Any]]) -> str:
    for action_name in ("assert_visible", "wait_for"):
        for step in steps:
            if step.get("action") == action_name and step.get("target"):
                return str(step["target"]).strip()
    return ""


def _primary_target(steps: list[dict[str, Any]]) -> str:
    preferred = _primary_assertion_target(steps)
    if preferred:
        return preferred
    for step in steps:
        if step.get("action") != "login" and step.get("target"):
            return str(step["target"]).strip()
    return ""


def infer_operations(case_data: dict[str, Any], suggestion_data: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    execution = case_data.get("execution", {})
    steps = execution.get("steps", [])
    if not isinstance(steps, list):
        return [], "execution.steps must be a list."

    advice_type = str(suggestion_data.get("advice_type", "")).strip()
    new_target = str(suggestion_data.get("target", "")).strip()
    if not new_target:
        return [], "suggestion target is empty."

    operations: list[dict[str, Any]] = []
    reason = ""

    if advice_type == "assertion_update":
        current_target = _primary_assertion_target(steps)
        if not current_target:
            return [], "No assertion target found to update."
        for index, step in enumerate(steps):
            if step.get("action") in {"wait_for", "assert_visible"} and str(step.get("target", "")).strip() == current_target:
                operations.append(
                    {
                        "step_index": index,
                        "action": step.get("action"),
                        "from_target": current_target,
                        "to_target": new_target,
                    }
                )
        reason = f"Replace assertion target '{current_target}' with '{new_target}'."
    elif advice_type == "wait_strategy":
        current_target = _primary_assertion_target(steps)
        if not current_target:
            return [], "No wait target found to update."
        for index, step in enumerate(steps):
            if step.get("action") == "wait_for" and str(step.get("target", "")).strip() == current_target:
                operations.append(
                    {
                        "step_index": index,
                        "action": step.get("action"),
                        "from_target": current_target,
                        "to_target": new_target,
                    }
                )
        reason = f"Replace wait target '{current_target}' with '{new_target}'."
    elif advice_type == "locator_update":
        current_target = _primary_target(steps)
        if not current_target:
            return [], "No target-bearing step found to update."
        for index, step in enumerate(steps):
            if step.get("action") != "login" and str(step.get("target", "")).strip() == current_target:
                operations.append(
                    {
                        "step_index": index,
                        "action": step.get("action"),
                        "from_target": current_target,
                        "to_target": new_target,
                    }
                )
        reason = f"Replace primary locator target '{current_target}' with '{new_target}'."
    else:
        return [], f"Advice type '{advice_type}' is preview-only and not applicable to YAML patching."

    if not operations:
        return [], "No matching steps found for the suggestion."
    return operations, reason


def apply_operations_to_case(case_data: dict[str, Any], operations: list[dict[str, Any]]) -> dict[str, Any]:
    updated = json.loads(json.dumps(case_data))
    steps = updated["execution"]["steps"]
    for operation in operations:
        step = steps[operation["step_index"]]
        if step.get("action") == "login":
            raise ValueError("Refusing to modify login steps.")
        step["target"] = operation["to_target"]
    return updated


def generate_patch_plan(
    case_path: Path,
    suggestion_path: Path,
    *,
    ai_generated_root: Path = AI_GENERATED_ROOT,
    page_objects_root: Path = PAGE_OBJECTS_ROOT,
) -> dict[str, Any]:
    case_path = case_path.resolve()
    suggestion_path = suggestion_path.resolve()

    if not case_path.exists():
        raise FileNotFoundError(f"Case file not found: {case_path}")
    if not suggestion_path.exists():
        raise FileNotFoundError(f"Suggestion file not found: {suggestion_path}")

    case_data = load_yaml(case_path)
    suggestion_data = json.loads(suggestion_path.read_text(encoding="utf-8"))
    if not isinstance(suggestion_data, dict):
        raise ValueError("suggestion.json must contain an object.")

    original_text = case_path.read_text(encoding="utf-8")
    case_id = str(case_data.get("id", "")).strip()
    page_name = str(case_data.get("execution", {}).get("page", "")).strip()
    available_targets = load_available_targets(page_name, page_objects_root=page_objects_root)
    advice_type = str(suggestion_data.get("advice_type", "no_change")).strip()
    boundary_summary = build_auto_heal_boundary_summary(advice_type=advice_type)

    allowed = True
    reason = "Preview ready."
    confidence = float(suggestion_data.get("confidence", 0.0) or 0.0)
    new_target = str(suggestion_data.get("target", "")).strip()

    if not is_path_within(case_path, ai_generated_root):
        allowed = False
        reason = "Only ai-generated YAML cases can be auto-healed."
    elif not boundary_summary["allowed"]:
        allowed = False
        reason = str(boundary_summary["reason"])
    elif confidence < 0.5:
        allowed = False
        reason = "Confidence is below 0.5; patch generation is not allowed."
    elif not new_target:
        allowed = False
        reason = "Suggestion target is empty."
    elif new_target not in available_targets:
        allowed = False
        reason = "Suggested target does not exist in the current page-object."

    operations: list[dict[str, Any]] = []
    updated_case = case_data
    if allowed:
        operations, reason = infer_operations(case_data, suggestion_data)
        if operations:
            updated_case = apply_operations_to_case(case_data, operations)
        else:
            allowed = False

    updated_text = dump_yaml_text(updated_case)
    diff_text = build_unified_diff(original_text, updated_text, original_path=case_path)
    changed = original_text != updated_text

    return {
        "status": "preview_ready" if allowed and changed else "rejected",
        "allowed_to_apply": bool(allowed and changed),
        "reason": reason if changed or not allowed else "No changes detected.",
        "case_id": case_id,
        "page": page_name,
        "case_path": str(case_path),
        "suggestion_path": str(suggestion_path),
        "advice_type": advice_type,
        "target": new_target,
        "confidence": confidence,
        "boundary": boundary_summary,
        "available_targets": available_targets,
        "operations": operations,
        "original_sha256": sha256_text(original_text),
        "updated_sha256": sha256_text(updated_text),
        "original_content": original_text,
        "updated_content": updated_text,
        "diff": diff_text,
        "generated_at": datetime.now(UTC).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a previewable YAML patch plan from suggestion.json.")
    parser.add_argument("--case", required=True, help="Path to YAML case file.")
    parser.add_argument("--suggestion", required=True, help="Path to suggestion.json.")
    parser.add_argument("--output", help="Optional output path for the patch plan JSON.")
    args = parser.parse_args()

    plan = generate_patch_plan(Path(args.case), Path(args.suggestion))
    output_text = json.dumps(plan, ensure_ascii=False, indent=2) + "\n"

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_text, encoding="utf-8")
    else:
        print(output_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
