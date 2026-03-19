import argparse
import json
from pathlib import Path

from self_healing_orchestrator import SelfHealingOrchestrator
from self_healing_executor import SelfHealingExecutor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Preview, apply, and rollback YAML self-healing fixes.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preview_parser = subparsers.add_parser("preview", help="Generate a diff preview from suggestion.json.")
    preview_parser.add_argument("--case", required=True, help="Path to the ai-generated YAML case.")
    preview_parser.add_argument("--suggestion", required=True, help="Path to suggestion.json.")
    preview_parser.add_argument("--output", help="Optional path to save the patch plan JSON.")

    apply_parser = subparsers.add_parser("apply", help="Apply a previewed patch plan after manual confirmation.")
    apply_parser.add_argument("--plan", required=True, help="Path to patch plan JSON.")
    apply_parser.add_argument("--confirm", required=True, help="Must be APPLY to confirm writing the YAML file.")

    rollback_parser = subparsers.add_parser("rollback", help="Rollback a previously applied patch.")
    rollback_parser.add_argument("--receipt", required=True, help="Path to receipt.json.")
    rollback_parser.add_argument("--confirm", required=True, help="Must be ROLLBACK to confirm restoring the backup.")

    auto_heal_parser = subparsers.add_parser("auto-heal", help="Run one self-healing cycle for an ai-generated YAML case.")
    auto_heal_parser.add_argument("--case", required=True, help="Path to the ai-generated YAML case.")
    auto_heal_parser.add_argument("--artifacts", required=True, help="Artifact directory containing suggestion.json.")
    auto_heal_parser.add_argument(
        "--previous-attempts",
        type=int,
        default=0,
        help="Existing self-healing attempt count. Maximum supported attempts is 1.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    executor = SelfHealingExecutor()

    if args.command == "preview":
        plan = executor.preview(Path(args.case), Path(args.suggestion))
        if args.output:
            executor.save_preview(plan, Path(args.output))
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    if args.command == "apply":
        if args.confirm != "APPLY":
            raise SystemExit("Refusing to apply without --confirm APPLY")
        receipt = executor.apply(Path(args.plan))
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        return 0

    if args.command == "rollback":
        if args.confirm != "ROLLBACK":
            raise SystemExit("Refusing to rollback without --confirm ROLLBACK")
        result = executor.rollback(Path(args.receipt))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "auto-heal":
        orchestrator = SelfHealingOrchestrator(executor=executor)
        result = orchestrator.run_from_artifacts(
            Path(args.artifacts),
            Path(args.case),
            previous_attempts=args.previous_attempts,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    raise SystemExit(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
