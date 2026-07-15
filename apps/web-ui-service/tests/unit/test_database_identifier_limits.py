"""Guard PostgreSQL's 63-byte identifier limit for the frozen schema."""
from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[2]
IDENTIFIER_LIMIT_BYTES = 63
MIGRATION_FILES = (
    SERVICE_ROOT / "migrations/versions/20260713_120000_evie_ai_phase0_assets.py",
    SERVICE_ROOT / "migrations/versions/20260713_121000_fix_evie_ai_constraint_names.py",
    SERVICE_ROOT
    / "migrations/versions/20260715_100000_evie_ai_phase1_asset_lifecycle.py",
)
BASELINE_FILE = SERVICE_ROOT / "migrations/baselines/schema_20260713_121000.py"
MANIFEST_FILE = SERVICE_ROOT / "migrations/baselines/schema_manifest_20260713_121000.json"


def _literal_string(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "f"
        and node.args
    ):
        return _literal_string(node.args[0])
    return None


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    if isinstance(node.func, ast.Name):
        return node.func.id
    return None


def _declared_identifiers(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    identifiers: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call_name = _call_name(node)
        if call_name in {"create_table", "create_index", "Column"} and node.args:
            value = _literal_string(node.args[0])
            if value is not None:
                identifiers.add(value)
        if call_name in {
            "PrimaryKeyConstraint",
            "ForeignKeyConstraint",
            "UniqueConstraint",
            "CheckConstraint",
        }:
            for keyword in node.keywords:
                if keyword.arg == "name":
                    value = _literal_string(keyword.value)
                    if value is not None:
                        identifiers.add(value)
    return identifiers


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _manifest_identifiers() -> set[str]:
    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    identifiers = set(manifest["tables"])
    for table in manifest["tables"].values():
        identifiers.update(column["name"] for column in table["columns"])
    return identifiers


def _assert_postgresql_safe(identifiers: set[str]) -> None:
    too_long = sorted(
        identifier
        for identifier in identifiers
        if len(identifier.encode("utf-8")) > IDENTIFIER_LIMIT_BYTES
    )
    assert not too_long, f"PostgreSQL identifier limit exceeded: {too_long}"


def test_new_schema_identifiers_fit_postgresql_limit() -> None:
    identifiers = set().union(*(_declared_identifiers(path) for path in MIGRATION_FILES))
    constraint_fix = _load_module(MIGRATION_FILES[1])
    identifiers.add(constraint_fix._CANONICAL_REQUIREMENT_VERSION_FK)

    _assert_postgresql_safe(identifiers)


def test_frozen_baseline_and_manifest_identifiers_fit_postgresql_limit() -> None:
    identifiers = _declared_identifiers(BASELINE_FILE) | _manifest_identifiers()

    _assert_postgresql_safe(identifiers)
