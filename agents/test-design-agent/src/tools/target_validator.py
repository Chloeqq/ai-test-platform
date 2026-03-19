from .page_object_loader import list_page_elements


def validate_targets(test_case: dict) -> None:
    execution = test_case.get("execution", {})
    page = execution.get("page")
    steps = execution.get("steps", [])

    if not page:
        raise ValueError("execution.page is required")

    valid_elements = set(list_page_elements(page))

    for step in steps:
        target = step.get("target")

        if not target:
            continue

        if target not in valid_elements:
            raise ValueError(
                f"Invalid target '{target}' for page '{page}'. "
                f"Available elements: {sorted(valid_elements)}"
            )