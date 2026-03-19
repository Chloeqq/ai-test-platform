import json
from pathlib import Path

import jsonschema


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "yaml_testcase.schema.json"


def validate_testcase_schema(test_case: dict):

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = json.load(f)

    jsonschema.validate(
        instance=test_case,
        schema=schema
    )