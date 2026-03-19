import argparse
import json
from pathlib import Path

import yaml

from runner.asset_toolkit import (
    add_page_element,
    build_test_case,
    create_page_object,
    describe_scaffold_template,
    list_page_elements,
    list_scaffold_templates,
    scaffold_page_assets,
    save_page_object,
    save_test_case,
    sync_test_case_steps,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage YAML test cases and page objects for web-playwright-python")
    subparsers = parser.add_subparsers(dest="command", required=True)

    page_init = subparsers.add_parser("init-page-object", help="Create a new page object YAML file")
    page_init.add_argument("--page", required=True)
    page_init.add_argument("--description", default="")
    page_init.add_argument("--output-dir")

    add_element = subparsers.add_parser("add-page-element", help="Add or update an element in a page object")
    add_element.add_argument("--page", required=True)
    add_element.add_argument("--name", required=True)
    add_element.add_argument("--locator-type", required=True, choices=["placeholder", "text", "css", "role"])
    add_element.add_argument("--locator-value", required=True)
    add_element.add_argument("--role")
    add_element.add_argument("--description")
    add_element.add_argument("--output-dir")

    list_elements = subparsers.add_parser("list-page-elements", help="List available element names for a page")
    list_elements.add_argument("--page", required=True)
    list_elements.add_argument("--output-dir")

    case_init = subparsers.add_parser("init-test-case", help="Generate a YAML test case from a page object")
    case_init.add_argument("--kind", required=True, choices=["smoke", "regression", "ai-generated"])
    case_init.add_argument("--page", required=True)
    case_init.add_argument("--id", required=True)
    case_init.add_argument("--title", required=True)
    case_init.add_argument("--description", required=True)
    case_init.add_argument("--requirement", required=True)
    case_init.add_argument("--priority", default="P1")
    case_init.add_argument("--module")
    case_init.add_argument("--tag", action="append", default=[])
    case_init.add_argument("--menu-target")
    case_init.add_argument("--assert-target")
    case_init.add_argument("--output-dir")
    case_init.add_argument("--page-objects-dir")

    case_sync = subparsers.add_parser("sync-test-case", help="Rewrite an existing YAML test case with standard steps inferred from its page object")
    case_sync.add_argument("--file", required=True)
    case_sync.add_argument("--menu-target")
    case_sync.add_argument("--assert-target")
    case_sync.add_argument("--page-objects-dir")
    case_sync.add_argument("--output")

    scaffold = subparsers.add_parser("scaffold-assets", help="Create a page object and smoke case scaffold together")
    scaffold.add_argument("--page", required=True)
    scaffold.add_argument("--title", required=True)
    scaffold.add_argument("--requirement", required=True)
    scaffold.add_argument("--description", default="")
    scaffold.add_argument("--priority", default="P1")
    scaffold.add_argument("--menu-label")
    scaffold.add_argument("--assert-label")
    scaffold.add_argument("--template")
    scaffold.add_argument("--elements-file")
    scaffold.add_argument("--page-objects-dir")
    scaffold.add_argument("--test-cases-dir")

    template_list = subparsers.add_parser("list-scaffold-templates", help="List built-in scaffold templates")
    template_list.add_argument("--templates-dir")
    template_list.add_argument("--verbose", action="store_true")

    template_describe = subparsers.add_parser("describe-scaffold-template", help="Show scaffold template details")
    template_describe.add_argument("--template", required=True)
    template_describe.add_argument("--templates-dir")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init-page-object":
        page_object = create_page_object(args.page, description=args.description)
        path = save_page_object(
            page_object,
            output_dir=Path(args.output_dir) if args.output_dir else None,
        )
        print(path)
        return

    if args.command == "add-page-element":
        path = add_page_element(
            page=args.page,
            element_name=args.name,
            locator_type=args.locator_type,
            locator_value=args.locator_value,
            role=args.role,
            description=args.description,
            output_dir=Path(args.output_dir) if args.output_dir else None,
        )
        print(path)
        return

    if args.command == "list-page-elements":
        elements = list_page_elements(
            page=args.page,
            output_dir=Path(args.output_dir) if args.output_dir else None,
        )
        for element in elements:
            print(element)
        return

    if args.command == "init-test-case":
        test_case = build_test_case(
            kind=args.kind,
            page=args.page,
            case_id=args.id,
            title=args.title,
            description=args.description,
            requirement=args.requirement,
            priority=args.priority,
            module=args.module,
            tags=args.tag,
            menu_target=args.menu_target,
            assert_target=args.assert_target,
            page_objects_dir=Path(args.page_objects_dir) if args.page_objects_dir else None,
        )
        path = save_test_case(
            test_case,
            kind=args.kind,
            output_dir=Path(args.output_dir) if args.output_dir else None,
        )
        print(path)
        return

    if args.command == "sync-test-case":
        path = sync_test_case_steps(
            test_case_path=Path(args.file),
            menu_target=args.menu_target,
            assert_target=args.assert_target,
            page_objects_dir=Path(args.page_objects_dir) if args.page_objects_dir else None,
            output_path=Path(args.output) if args.output else None,
        )
        print(path)
        return

    if args.command == "scaffold-assets":
        result = scaffold_page_assets(
            page=args.page,
            title=args.title,
            requirement=args.requirement,
            description=args.description,
            priority=args.priority,
            menu_label=args.menu_label,
            assert_label=args.assert_label,
            template=args.template,
            elements=_load_elements_file(args.elements_file),
            page_objects_dir=Path(args.page_objects_dir) if args.page_objects_dir else None,
            test_cases_dir=Path(args.test_cases_dir) if args.test_cases_dir else None,
        )
        print(result["page_object_path"])
        print(result["test_case_path"])
        return

    if args.command == "list-scaffold-templates":
        templates_dir = Path(args.templates_dir) if args.templates_dir else None
        templates = list_scaffold_templates(templates_dir=templates_dir)
        for template in templates:
            if args.verbose:
                details = describe_scaffold_template(template, templates_dir=templates_dir)
                summary = details["summary"] or "-"
                print(f"{template}\t{details['page_type'] or '-'}\t{summary}")
            else:
                print(template)
        return

    if args.command == "describe-scaffold-template":
        details = describe_scaffold_template(
            args.template,
            templates_dir=Path(args.templates_dir) if args.templates_dir else None,
        )
        print(yaml.safe_dump(details, allow_unicode=True, sort_keys=False).rstrip())
        return


def _load_elements_file(path: str | None) -> list[dict] | None:
    if not path:
        return None

    with open(path, "r", encoding="utf-8") as f:
        if path.endswith(".json"):
            data = json.load(f)
        else:
            data = yaml.safe_load(f)

    if data is None:
        return []
    if not isinstance(data, list):
        raise ValueError("elements file must contain a list")
    return data


if __name__ == "__main__":
    main()
