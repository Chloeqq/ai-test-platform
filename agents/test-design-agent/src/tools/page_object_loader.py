from pathlib import Path
import yaml


PAGE_OBJECT_ROOT = Path(__file__).resolve().parents[4] / "assets" / "page-objects" / "web"


def _validate_page_object(page_object: dict, expected_page: str) -> None:
    if not isinstance(page_object, dict):
        raise ValueError("Page object content must be a YAML object")

    if page_object.get("page") != expected_page:
        raise ValueError(
            f"Page object page mismatch: expected '{expected_page}', got '{page_object.get('page')}'"
        )

    elements = page_object.get("elements")
    if not isinstance(elements, dict):
        raise ValueError(f"Page object '{expected_page}' must contain an elements mapping")

    for element_name, element in elements.items():
        if not isinstance(element, dict):
            raise ValueError(f"Element '{element_name}' in page '{expected_page}' must be an object")

        locator_type = element.get("locator_type")
        locator_value = element.get("locator_value")

        if locator_type not in {"placeholder", "text", "css", "role"}:
            raise ValueError(
                f"Element '{element_name}' in page '{expected_page}' has unsupported locator_type '{locator_type}'"
            )

        if not locator_value:
            raise ValueError(
                f"Element '{element_name}' in page '{expected_page}' must define locator_value"
            )

        if locator_type == "role" and not element.get("role"):
            raise ValueError(
                f"Element '{element_name}' in page '{expected_page}' must define role when locator_type=role"
            )


def load_page_object(page_name: str) -> dict:
    file_path = PAGE_OBJECT_ROOT / f"{page_name}.page-object.yaml"

    if not file_path.exists():
        raise FileNotFoundError(f"Page object not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        page_object = yaml.safe_load(f)

    _validate_page_object(page_object, page_name)
    return page_object


def list_page_elements(page_name: str) -> list[str]:
    page_object = load_page_object(page_name)
    elements = page_object.get("elements", {})
    return list(elements.keys())
