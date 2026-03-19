from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from .agent import DataGenerationAgent
    from .cleanup_manager import mark_cleaned
    from .registry import list_pending_cleanup_entries, summarize_cleanup_retention, summarize_registry_entries
    from .templates import summarize_template_library, summarize_template_migration
    from .utils.formatter import model_dump_json
    from .utils.parser import load_generation_request
except ImportError:  # pragma: no cover
    from agent import DataGenerationAgent  # type: ignore
    from cleanup_manager import mark_cleaned  # type: ignore
    from registry import list_pending_cleanup_entries, summarize_cleanup_retention, summarize_registry_entries  # type: ignore
    from templates import summarize_template_library, summarize_template_migration  # type: ignore
    from utils.formatter import model_dump_json  # type: ignore
    from utils.parser import load_generation_request  # type: ignore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic data generation agent")
    parser.add_argument("--input", dest="input_path", default="", help="JSON file path; defaults to stdin")
    parser.add_argument("--registry-path", dest="registry_path", default="", help="Registry JSON path")
    parser.add_argument("--mark-cleaned", dest="mark_cleaned_request_id", default="", help="Mark request as cleaned")
    parser.add_argument("--registry-summary", dest="show_registry_summary", action="store_true", help="Print registry summary")
    parser.add_argument("--template-summary", dest="show_template_summary", action="store_true", help="Print template catalog summary")
    parser.add_argument("--template-migration-summary", dest="show_template_migration_summary", action="store_true", help="Print template version migration summary")
    parser.add_argument("--pending-cleanups", dest="show_pending_cleanups", action="store_true", help="Print pending cleanup entries")
    parser.add_argument("--cleanup-retention-summary", dest="show_cleanup_retention_summary", action="store_true", help="Print cleanup retention and archive summary")
    args = parser.parse_args(argv)

    registry_path = args.registry_path or "reports/data-generation/registry.json"

    if args.show_template_summary:
        print(model_dump_json(summarize_template_library()))
        return 0

    if args.show_template_migration_summary:
        print(model_dump_json(summarize_template_migration()))
        return 0

    if args.show_registry_summary:
        print(model_dump_json(summarize_registry_entries(Path(registry_path))))
        return 0

    if args.show_pending_cleanups:
        print(model_dump_json(list_pending_cleanup_entries(Path(registry_path))))
        return 0

    if args.show_cleanup_retention_summary:
        print(model_dump_json(summarize_cleanup_retention(Path(registry_path))))
        return 0

    if args.mark_cleaned_request_id:
        result = mark_cleaned(registry_path=registry_path, request_id=args.mark_cleaned_request_id)
        if not result:
            raise SystemExit(f"request_id not found in registry: {args.mark_cleaned_request_id}")
        print(model_dump_json(result))
        return 0

    payload = load_generation_request(args.input_path or sys.stdin.read())
    response = DataGenerationAgent(registry_path=args.registry_path or None).generate(payload)
    print(model_dump_json(response))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
