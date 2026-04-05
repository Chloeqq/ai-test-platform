# mypy: ignore-errors

from pathlib import Path
from copy import deepcopy
from typing import Any

import yaml

from runner.page_object_validator import validate_page_object_schema
from runner.paths import AI_GENERATED_CASES_ROOT, ASSET_TEMPLATES_ROOT, PAGE_OBJECTS_ROOT, SMOKE_TEST_CASES_ROOT, TEST_CASES_ROOT
from runner.schema_validator import validate_testcase_schema
from runner.yaml_loader import load_yaml_file

try:
    from shared_backend.case_ids import build_case_id, build_case_metadata, match_case_id, next_case_sequence, normalize_case_id
    from shared_backend.case_rules import CaseRuleViolation, enrich_case_metadata, validate_case_payload
except Exception:  # pragma: no cover - runner keeps fallback usability
    build_case_id = None
    build_case_metadata = None
    match_case_id = None
    next_case_sequence = None
    normalize_case_id = None
    CaseRuleViolation = ValueError
    enrich_case_metadata = None
    validate_case_payload = None


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


def _ensure_structured_title(*, page: str, module: str, title: str) -> str:
    normalized = str(title or "").strip()
    segments = [segment.strip() for segment in normalized.split("-") if segment.strip()]
    if len(segments) >= 4:
        return normalized
    if callable(build_case_metadata):
        metadata = build_case_metadata(page=page, module=module, title=title)
        page_name = str(metadata.get("page_name", page)).strip() or page
        module_name = str(metadata.get("module_name", module)).strip() or module
    else:
        page_name = str(page or "目标页面").strip()
        module_name = str(module or "核心流程").strip()
    outcome = normalized or "关键结果正确"
    return f"{page_name}-{module_name}-基础场景-执行验证-{outcome}"


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


def _allocate_platform_case_id(test_case: dict[str, Any], *, kind: str, output_dir: Path | None = None) -> str:
    if not callable(build_case_id) or not callable(next_case_sequence) or not callable(build_case_metadata):
        return str(test_case.get("id", "")).strip()
    source_dir = resolve_test_case_dir(kind, output_dir=output_dir)
    existing_case_ids = [path.stem for path in source_dir.glob("*.yaml")] if source_dir.exists() else []
    current_id = normalize_case_id(str(test_case.get("id", "")).strip(), fallback="") if callable(normalize_case_id) else str(test_case.get("id", "")).strip()
    current_match = match_case_id(current_id) if callable(match_case_id) and current_id else None

    execution = test_case.get("execution") if isinstance(test_case.get("execution"), dict) else {}
    metadata = build_case_metadata(
        page=str(execution.get("page", "")).strip() or str(test_case.get("page", "")).strip(),
        module=str(test_case.get("module", "")).strip(),
        title=str(test_case.get("title", "")).strip(),
        description=str(test_case.get("description", "")).strip(),
        tags=test_case.get("tags"),
        source_hint=str(test_case.get("source", "")).strip() or ("AI" if kind == "ai-generated" else "MN"),
        legacy=kind != "ai-generated" and str(test_case.get("source", "")).strip().lower() == "imp",
    )
    if current_match:
        same_prefix = all(
            [
                current_match.group("project").lower() == metadata["project"],
                current_match.group("client").lower() == metadata["client"],
                current_match.group("page").lower() == metadata["page_code"],
                current_match.group("module").lower() == metadata["module_code"],
                current_match.group("case_type").lower() == metadata["case_type"],
                current_match.group("source").lower() == metadata["source"],
            ]
        )
        if same_prefix:
            return current_id

    sequence = next_case_sequence(
        existing_case_ids=existing_case_ids,
        page_code=metadata["page_code"],
        module_code=metadata["module_code"],
        project=metadata["project"],
        client=metadata["client"],
        case_type=metadata["case_type"],
        source=metadata["source"],
    )
    return build_case_id(
        project=metadata["project"],
        client=metadata["client"],
        page_code=metadata["page_code"],
        module_code=metadata["module_code"],
        case_type=metadata["case_type"],
        source=metadata["source"],
        sequence=sequence,
    )


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
    final_module = module or ("auth" if page == "login" else page)
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
        "title": _ensure_structured_title(page=page, module=final_module, title=title),
        "module": final_module,
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
    if callable(enrich_case_metadata):
        test_case = enrich_case_metadata(test_case)
    if callable(validate_case_payload):
        errors = validate_case_payload(test_case)
        if errors:
            raise CaseRuleViolation("; ".join(errors))
    validate_testcase_schema(test_case)
    return test_case


def save_test_case(test_case: dict, kind: str, output_dir: Path | None = None) -> Path:
    if kind == "ai-generated":
        test_case = deepcopy(test_case)
        test_case["id"] = _allocate_platform_case_id(test_case, kind=kind, output_dir=output_dir)
    if callable(enrich_case_metadata):
        test_case = enrich_case_metadata(test_case)
    if callable(validate_case_payload):
        errors = validate_case_payload(test_case)
        if errors:
            raise CaseRuleViolation("; ".join(errors))
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
    default_case_id = (
        build_case_id(page=page, module=page, case_type="SM", source="MN", sequence=1)
        if callable(build_case_id)
        else f"ATP-WEB-{page.upper()}-CORE-SM-MN-0001"
    )
    test_case = build_test_case(
        kind="smoke",
        page=page,
        case_id=default_case_id,
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
