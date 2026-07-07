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
    invalid_files: list[str] = []

    # 如果目录不存在，返回空列表
    if not dir_path.exists():
        print(f"⚠️ Directory not found: {dir_path}")
        return cases

    # 排序保证批量执行顺序可复现。
    for file_path in sorted(dir_path.iterdir()):

        if file_path.suffix not in [".yaml", ".yml"]:
            continue

        try:
            parsed = load_validated_yaml_file(file_path)
        except Exception as exc:
            # 批量目录扫描：单条坏用例（空文件 / schema 不合规等）跳过并记录，
            # 不让一条脏数据阻断整批收集。单条入口 load_validated_yaml_file 仍 raise，
            # 保持显式单跑的严格性（与 test_case_loader 身份门禁同一哲学）。
            if "Test case file is empty" in str(exc):
                print(f"⚠️ Skip empty YAML: {file_path}")
            else:
                invalid_files.append(f"{file_path.name}: {exc}")
            continue

        cases.append(parsed)

    if invalid_files:
        print(f"⚠️ Skipped {len(invalid_files)} invalid YAML case(s) during batch load:")
        for item in invalid_files:
            print(f"   - {item}")

    return cases
