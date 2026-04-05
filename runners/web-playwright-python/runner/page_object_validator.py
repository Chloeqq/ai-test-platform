# mypy: ignore-errors

import json
from pathlib import Path

import jsonschema


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "page_object.schema.json"


def validate_page_object_schema(page_object: dict, expected_page: str | None = None) -> None:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = json.load(f)

    jsonschema.validate(instance=page_object, schema=schema)

    page_name = page_object.get("page")
    if expected_page and page_name != expected_page:
        raise ValueError(
            f"Page object page mismatch: expected '{expected_page}', got '{page_name}'"
        )
