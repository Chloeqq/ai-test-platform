# mypy: ignore-errors

from pathlib import Path
from typing import Any
import yaml

from runner.schema_validator import validate_testcase_schema


def load_yaml_file(file_path: Path) -> Any:
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_yaml_files(dir_path: Path) -> list[Any]:
    cases = []

    # 如果目录不存在，返回空列表
    if not dir_path.exists():
        print(f"⚠️ Directory not found: {dir_path}")
        return cases

    for file_path in dir_path.iterdir():

        if file_path.suffix not in [".yaml", ".yml"]:
            continue

        parsed = load_yaml_file(file_path)

        # ⭐ 关键修复：跳过空 YAML
        if parsed is None:
            print(f"⚠️ Skip empty YAML: {file_path}")
            continue

        # ⭐ 再做 schema 校验
        try:
            validate_testcase_schema(parsed)
        except Exception as e:
            print(f"❌ Schema validation failed for {file_path}: {e}")
            raise

        cases.append(parsed)

    return cases
