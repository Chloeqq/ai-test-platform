import argparse
import json
from datetime_compat import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

from apply_patch import ROLLBACK_ROOT
from patch_generator import AI_GENERATED_ROOT, is_path_within, sha256_text


def rollback_patch(
    receipt_path: Path,
    *,
    ai_generated_root: Path = AI_GENERATED_ROOT,
) -> dict[str, Any]:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    case_path = Path(receipt["case_path"]).resolve()
    backup_path = Path(receipt["backup_path"]).resolve()

    if not is_path_within(case_path, ai_generated_root):
        raise ValueError("Refusing to rollback non ai-generated YAML.")
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    current_content = case_path.read_text(encoding="utf-8")
    expected_updated_sha = str(receipt.get("updated_sha256", "")).strip()
    if expected_updated_sha and sha256_text(current_content) != expected_updated_sha:
        raise ValueError("Current YAML no longer matches the applied version; refusing rollback.")

    backup_content = backup_path.read_text(encoding="utf-8")
    case_path.write_text(backup_content, encoding="utf-8")

    result = {
        "rollback_id": str(receipt.get("rollback_id", "")).strip(),
        "case_path": str(case_path),
        "backup_path": str(backup_path),
        "receipt_path": str(receipt_path.resolve()),
        "rolled_back_at": datetime.now(UTC).isoformat(),
        "restored_sha256": sha256_text(backup_content),
    }
    result_path = receipt_path.parent / "rollback-result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result["result_path"] = str(result_path)
    return result


def find_latest_receipt(rollback_root: Path = ROLLBACK_ROOT) -> Path:
    if not rollback_root.exists():
        raise FileNotFoundError(f"Rollback root not found: {rollback_root}")

    candidates = sorted(rollback_root.glob("*/receipt.json"))
    if not candidates:
        raise FileNotFoundError(f"No receipt.json found under: {rollback_root}")
    return candidates[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Rollback a manually applied YAML patch from a receipt file.")
    parser.add_argument("--receipt", help="Path to receipt.json. If omitted, uses the latest receipt in artifacts/yaml-rollbacks.")
    parser.add_argument("--confirm", required=True, help="Must be ROLLBACK to confirm restoring the backup.")
    args = parser.parse_args()

    if args.confirm != "ROLLBACK":
        raise SystemExit("Refusing to rollback without --confirm ROLLBACK")

    receipt_path = Path(args.receipt).resolve() if args.receipt else find_latest_receipt()
    result = rollback_patch(receipt_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
