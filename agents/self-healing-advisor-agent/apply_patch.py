import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from patch_generator import AI_GENERATED_ROOT, REPO_ROOT, is_path_within, sha256_text


ROLLBACK_ROOT = REPO_ROOT / "artifacts" / "yaml-rollbacks"


def apply_patch_plan(
    plan_path: Path,
    *,
    rollback_root: Path = ROLLBACK_ROOT,
    ai_generated_root: Path = AI_GENERATED_ROOT,
) -> dict[str, Any]:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    case_path = Path(plan["case_path"]).resolve()

    if not plan.get("allowed_to_apply"):
        raise ValueError("Patch plan is not allowed to apply.")
    if not is_path_within(case_path, ai_generated_root):
        raise ValueError("Refusing to modify non ai-generated YAML.")

    current_content = case_path.read_text(encoding="utf-8")
    if sha256_text(current_content) != plan.get("original_sha256"):
        raise ValueError("Current YAML does not match the previewed version; regenerate the patch plan.")

    rollback_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{case_path.stem}"
    rollback_dir = rollback_root / rollback_id
    rollback_dir.mkdir(parents=True, exist_ok=True)
    backup_path = rollback_dir / case_path.name
    shutil.copy2(case_path, backup_path)

    updated_content = str(plan.get("updated_content", ""))
    case_path.write_text(updated_content, encoding="utf-8")

    receipt = {
        "rollback_id": rollback_id,
        "case_path": str(case_path),
        "backup_path": str(backup_path),
        "plan_path": str(plan_path.resolve()),
        "applied_at": datetime.now(UTC).isoformat(),
        "original_sha256": plan.get("original_sha256", ""),
        "updated_sha256": sha256_text(updated_content),
    }
    receipt_path = rollback_dir / "receipt.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    receipt["receipt_path"] = str(receipt_path)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply a previewed YAML patch only after manual confirmation.")
    parser.add_argument("--plan", required=True, help="Path to patch plan JSON.")
    parser.add_argument("--confirm", required=True, help="Must be APPLY to confirm writing the YAML file.")
    args = parser.parse_args()

    if args.confirm != "APPLY":
        raise SystemExit("Refusing to apply without --confirm APPLY")

    receipt = apply_patch_plan(Path(args.plan))
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
