# mypy: ignore-errors

from pathlib import Path
from typing import Any
import yaml

from runner.schema_validator import validate_testcase_schema


def load_yaml_file(file_path: Path) -> Any:
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_validated_yaml_file(file_path: Path) -> Any:
    """读取单个 YAML 并执行和目录加载一致的 schema 校验。"""
    parsed = load_yaml_file(file_path)
    if parsed is None:
        raise ValueError(f"Test case file is empty: {file_path}")
    try:
        validate_testcase_schema(parsed)
    except Exception as e:
        print(f"❌ Schema validation failed for {file_path}: {e}")
        raise
    return parsed


def load_yaml_files(dir_path: Path) -> list[Any]:
    cases = []

    # 如果目录不存在，返回空列表
    if not dir_path.exists():
        print(f"⚠️ Directory not found: {dir_path}")
        return cases

    for file_path in dir_path.iterdir():

        if file_path.suffix not in [".yaml", ".yml"]:
            continue

        try:
            parsed = load_validated_yaml_file(file_path)
        except ValueError as exc:
            if "Test case file is empty" not in str(exc):
                raise
            print(f"⚠️ Skip empty YAML: {file_path}")
            continue

        cases.append(parsed)

    return cases
