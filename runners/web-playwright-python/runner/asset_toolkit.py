from pathlib import Path
from copy import deepcopy
from typing import Any

import yaml

from runner.page_object_validator import validate_page_object_schema
from runner.paths import AI_GENERATED_CASES_ROOT, ASSET_TEMPLATES_ROOT, PAGE_OBJECTS_ROOT, SMOKE_TEST_CASES_ROOT, TEST_CASES_ROOT
from runner.schema_validator import validate_testcase_schema
from runner.yaml_loader import load_yaml_file


def dump_yaml(data: dict, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
    return output_path


def create_page_object(page: str, description: str = "") -> dict:
    page_object = {
        "page": page,
        "elements": {},
    }
    if description:
        page_object["description"] = description
    validate_page_object_schema(page_object, expected_page=page)
    return page_object


def save_page_object(page_object: dict, output_dir: Path | None = None) -> Path:
    page = page_object["page"]
    validate_page_object_schema(page_object, expected_page=page)
    target_dir = output_dir or PAGE_OBJECTS_ROOT
    return dump_yaml(page_object, target_dir / f"{page}.page-object.yaml")


def load_page_object_for_edit(page: str, output_dir: Path | None = None) -> dict:
    target_dir = output_dir or PAGE_OBJECTS_ROOT
    path = target_dir / f"{page}.page-object.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Page object not found: {path}")
    page_object = load_yaml_file(path)
    if page_object is None:
        raise ValueError(f"Page object is empty: {path}")
    validate_page_object_schema(page_object, expected_page=page)
    return page_object


def add_page_element(
    page: str,
    element_name: str,
    locator_type: str,
    locator_value: str,
    role: str | None = None,
    description: str | None = None,
    output_dir: Path | None = None,
) -> Path:
    page_object = load_page_object_for_edit(page, output_dir=output_dir)

    element = {
        "locator_type": locator_type,
        "locator_value": locator_value,
    }
    if role:
        element["role"] = role
    if description:
        element["description"] = description

    page_object["elements"][element_name] = element
    return save_page_object(page_object, output_dir=output_dir)


def list_page_elements(page: str, output_dir: Path | None = None) -> list[str]:
    page_object = load_page_object_for_edit(page, output_dir=output_dir)
    return list(page_object.get("elements", {}).keys())


def infer_smoke_targets(page_object: dict) -> tuple[str | None, str | None]:
    elements = page_object.get("elements", {})
    menu_target = next((name for name in elements if name.endswith("_menu")), None)
    assert_target = next(
        (
            name
            for name in elements
            if name not in {menu_target}
            and ("title" in name or "table" in name or "list" in name or "home" in name)
        ),
        None,
    )

    if not assert_target:
        assert_target = next((name for name in elements if name != menu_target), None)

    return menu_target, assert_target


def resolve_test_case_dir(kind: str, output_dir: Path | None = None) -> Path:
    if output_dir:
        return output_dir

    if kind == "smoke":
        return SMOKE_TEST_CASES_ROOT
    if kind == "ai-generated":
        return AI_GENERATED_CASES_ROOT
    if kind == "regression":
        return TEST_CASES_ROOT / "regression"

    raise ValueError(f"Unsupported test case kind: {kind}")


def load_test_case_for_edit(test_case_path: Path) -> dict:
    if not test_case_path.exists():
        raise FileNotFoundError(f"Test case not found: {test_case_path}")

    test_case = load_yaml_file(test_case_path)
    if test_case is None:
        raise ValueError(f"Test case is empty: {test_case_path}")

    validate_testcase_schema(test_case)
    return test_case


def build_standard_steps(
    page: str,
    page_objects_dir: Path | None = None,
    menu_target: str | None = None,
    assert_target: str | None = None,
) -> list[dict]:
    page_object = load_page_object_for_edit(page, output_dir=page_objects_dir)
    inferred_menu, inferred_assert = infer_smoke_targets(page_object)

    final_menu_target = menu_target if menu_target is not None else inferred_menu
    final_assert_target = assert_target if assert_target is not None else inferred_assert

    steps = [{"action": "login"}]
    if page != "login":
        if not final_menu_target:
            raise ValueError(f"Could not infer menu target for page '{page}'. Pass --menu-target explicitly.")
        steps.append({"action": "click", "target": final_menu_target})

    if not final_assert_target:
        raise ValueError(f"Could not infer assert target for page '{page}'. Pass --assert-target explicitly.")

    steps.append({"action": "wait_for", "target": final_assert_target})
    steps.append({"action": "assert_visible", "target": final_assert_target})
    return steps


def build_test_case(
    kind: str,
    page: str,
    case_id: str,
    title: str,
    description: str,
    requirement: str,
    priority: str = "P1",
    module: str | None = None,
    tags: list[str] | None = None,
    menu_target: str | None = None,
    assert_target: str | None = None,
    page_objects_dir: Path | None = None,
) -> dict:
    steps = build_standard_steps(
        page=page,
        page_objects_dir=page_objects_dir,
        menu_target=menu_target,
        assert_target=assert_target,
    )

    final_tags = tags[:] if tags else [kind, page]
    if kind not in final_tags:
        final_tags.insert(0, kind)
    if page not in final_tags:
        final_tags.append(page)

    test_case = {
        "version": "v4",
        "id": case_id,
        "title": title,
        "module": module or ("auth" if page == "login" else page),
        "priority": priority,
        "tags": final_tags,
        "owner": "qa-team",
        "status": "automated",
        "description": description,
        "requirement": [requirement],
        "data": {},
        "execution": {
            "runner": "playwright",
            "page": page,
            "variables": {},
            "steps": steps,
        },
    }
    validate_testcase_schema(test_case)
    return test_case


def save_test_case(test_case: dict, kind: str, output_dir: Path | None = None) -> Path:
    validate_testcase_schema(test_case)
    target_dir = resolve_test_case_dir(kind, output_dir=output_dir)
    return dump_yaml(test_case, target_dir / f"{test_case['id']}.yaml")


def list_scaffold_templates(templates_dir: Path | None = None) -> list[str]:
    target_dir = templates_dir or ASSET_TEMPLATES_ROOT / "scaffold-elements"
    if not target_dir.exists():
        return []

    return sorted(path.stem for path in target_dir.glob("*.yaml"))


def load_scaffold_template_metadata(template_name: str, templates_dir: Path | None = None) -> dict[str, Any]:
    if not template_name.strip():
        raise ValueError("template must not be empty")

    target_dir = templates_dir or ASSET_TEMPLATES_ROOT / "scaffold-metadata"
    template_path = target_dir / f"{template_name}.yaml"
    if not template_path.exists():
        return {}

    data = load_yaml_file(template_path)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"Scaffold template metadata must contain an object: {template_path}")
    return data


def load_scaffold_template(template_name: str, templates_dir: Path | None = None) -> list[dict[str, Any]]:
    if not template_name.strip():
        raise ValueError("template must not be empty")

    target_dir = templates_dir or ASSET_TEMPLATES_ROOT / "scaffold-elements"
    template_path = target_dir / f"{template_name}.yaml"
    if not template_path.exists():
        raise ValueError(f"Unknown scaffold template: {template_name}")

    data = load_yaml_file(template_path)
    if data is None:
        return []
    if not isinstance(data, list):
        raise ValueError(f"Scaffold template must contain a list: {template_path}")
    return data


def describe_scaffold_template(template_name: str, templates_dir: Path | None = None) -> dict[str, Any]:
    metadata = load_scaffold_template_metadata(template_name, templates_dir=templates_dir)
    elements = load_scaffold_template(template_name, templates_dir=templates_dir)
    return {
        "name": template_name,
        "summary": metadata.get("summary", ""),
        "page_type": metadata.get("page_type", ""),
        "recommended_title": metadata.get("recommended_title", ""),
        "recommended_requirement": metadata.get("recommended_requirement", ""),
        "elements_count": len(elements),
        "elements": elements,
    }


def scaffold_page_assets(
    page: str,
    title: str,
    requirement: str,
    description: str = "",
    priority: str = "P1",
    menu_label: str | None = None,
    assert_label: str | None = None,
    template: str | None = None,
    elements: list[dict[str, Any]] | None = None,
    page_objects_dir: Path | None = None,
    test_cases_dir: Path | None = None,
    templates_dir: Path | None = None,
) -> dict:
    if not page.strip():
        raise ValueError("page must not be empty")
    if not title.strip():
        raise ValueError("title must not be empty")
    if not requirement.strip():
        raise ValueError("requirement must not be empty")

    page_object = create_page_object(page=page, description=description)
    smoke_targets = {
        "menu": None,
        "assert": None,
    }

    page_object["elements"][f"{page}_menu"] = {
        "locator_type": "role",
        "role": "menuitem",
        "locator_value": menu_label or title,
        "description": f"{title}菜单",
    }
    page_object["elements"][f"{page}_title"] = {
        "locator_type": "text",
        "locator_value": assert_label or title,
        "description": f"{title}标题",
    }

    merged_elements: list[dict[str, Any]] = []
    if template:
        merged_elements.extend(load_scaffold_template(template, templates_dir=templates_dir))
    if elements:
        merged_elements.extend(elements)

    for element in merged_elements:
        apply_scaffold_element(page_object, element, smoke_targets)

    page_object_path = save_page_object(page_object, output_dir=page_objects_dir)
    test_case = build_test_case(
        kind="smoke",
        page=page,
        case_id=f"TC-{page.upper()}-001",
        title=title,
        description=description or f"验证{title}可以正常打开",
        requirement=requirement,
        priority=priority,
        page_objects_dir=page_objects_dir,
        menu_target=smoke_targets["menu"],
        assert_target=smoke_targets["assert"],
    )
    test_case_path = save_test_case(
        test_case,
        kind="smoke",
        output_dir=test_cases_dir or (TEST_CASES_ROOT / "smoke"),
    )

    return {
        "page_object": page_object,
        "page_object_path": str(page_object_path),
        "test_case": test_case,
        "test_case_path": str(test_case_path),
    }


def apply_scaffold_element(
    page_object: dict,
    element: dict[str, Any],
    smoke_targets: dict[str, str | None],
) -> None:
    if not isinstance(element, dict):
        raise ValueError("elements entries must be objects")

    name = str(element.get("name", "")).strip()
    locator_type = str(element.get("locator_type", "")).strip()
    locator_value = str(element.get("locator_value", "")).strip()
    role = element.get("role")
    description = element.get("description")
    smoke_role = str(element.get("smoke_role", "")).strip()

    if not name:
        raise ValueError("elements[].name must not be empty")
    if not locator_type:
        raise ValueError("elements[].locator_type must not be empty")
    if locator_type not in {"placeholder", "text", "css", "role"}:
        raise ValueError("elements[].locator_type is not supported")
    if not locator_value:
        raise ValueError("elements[].locator_value must not be empty")
    if locator_type == "role" and not str(role or "").strip():
        raise ValueError("elements[].role must not be empty for role locators")
    if smoke_role and smoke_role not in {"menu", "assert"}:
        raise ValueError("elements[].smoke_role is not supported")
    if smoke_role and smoke_targets[smoke_role]:
        raise ValueError(f"elements[].smoke_role '{smoke_role}' is duplicated")

    normalized_element = {
        "locator_type": locator_type,
        "locator_value": locator_value,
    }
    if role:
        normalized_element["role"] = str(role).strip()
    if description:
        normalized_element["description"] = str(description)

    page_object["elements"][name] = normalized_element
    if smoke_role:
        smoke_targets[smoke_role] = name


def prepare_generated_test_case(test_case: dict) -> dict:
    normalized = deepcopy(test_case)
    page = normalized["execution"]["page"]

    tags = list(normalized.get("tags", []))
    if "ai-generated" not in tags:
        tags.insert(0, "ai-generated")
    if page not in tags:
        tags.append(page)

    normalized["tags"] = tags
    normalized.setdefault("owner", "qa-team")
    normalized.setdefault("status", "automated")

    validate_testcase_schema(normalized)
    return normalized


def sync_test_case_steps(
    test_case_path: Path,
    menu_target: str | None = None,
    assert_target: str | None = None,
    page_objects_dir: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    test_case = deepcopy(load_test_case_for_edit(test_case_path))
    page = test_case["execution"]["page"]
    test_case["execution"]["steps"] = build_standard_steps(
        page=page,
        page_objects_dir=page_objects_dir,
        menu_target=menu_target,
        assert_target=assert_target,
    )
    validate_testcase_schema(test_case)
    destination = output_path or test_case_path
    return dump_yaml(test_case, destination)
