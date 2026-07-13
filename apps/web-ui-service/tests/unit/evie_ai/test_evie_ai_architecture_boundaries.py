from __future__ import annotations

import ast
from pathlib import Path

from sqlalchemy import ForeignKeyConstraint, UniqueConstraint

from app.models.evie_ai import (
    Requirement,
    RequirementVersion,
    TestAsset as AssetModel,
    TestAssetSource as AssetSourceModel,
    TestAssetVersion as AssetVersionModel,
)
from app.schemas.evie_ai import (
    TestAssetCreate as AssetCreate,
    TestAssetRead as AssetRead,
    TestAssetSourceCreate as AssetSourceCreate,
    TestAssetSourceRead as AssetSourceRead,
    TestAssetVersionCreate as AssetVersionCreate,
    TestAssetVersionRead as AssetVersionRead,
)


SERVICE_ROOT = Path(__file__).resolve().parents[3]
EVIE_AI_MODULE_ROOTS = (
    SERVICE_ROOT / "app" / "models" / "evie_ai",
    SERVICE_ROOT / "app" / "schemas" / "evie_ai",
    SERVICE_ROOT / "app" / "repositories" / "evie_ai",
)
FORBIDDEN_IMPORT_TOKENS = {
    "behavior_registry",
    "candidate",
    "contractvalidator",
    "execution_compiler",
    "intent_mapping",
    "point_builder",
    "preview",
    "quality_gate",
    "resolve_explicit_step",
    "runner",
    "selected_candidates",
    "structurer",
    "testpointasset",
    "test_point_asset",
    "test_point",
}
FORBIDDEN_ASSET_FIELDS = {
    "action",
    "target",
    "value",
    "locator",
    "selector",
    "structured_steps",
    "steps_hint",
    "compiler_ir",
    "dsl",
    "script_code",
    "runner_steps",
    "selected_candidates",
    "duplicate_status",
    "intent_id",
}


def _import_references(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    references: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            references.update(alias.name.lower() for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                references.add(node.module.lower())
            references.update(alias.name.lower() for alias in node.names)
    return references


def test_evie_ai_modules_do_not_import_frozen_generation_or_execution_chain() -> None:
    violations: list[tuple[str, str]] = []

    for root in EVIE_AI_MODULE_ROOTS:
        for path in root.rglob("*.py"):
            for reference in _import_references(path):
                for token in FORBIDDEN_IMPORT_TOKENS:
                    if token in reference:
                        violations.append((str(path.relative_to(SERVICE_ROOT)), reference))

    assert violations == []


def test_test_asset_schemas_have_only_natural_language_domain_fields() -> None:
    schemas = (
        AssetCreate,
        AssetVersionCreate,
        AssetSourceCreate,
        AssetRead,
        AssetVersionRead,
        AssetSourceRead,
    )
    for schema in schemas:
        assert FORBIDDEN_ASSET_FIELDS.isdisjoint(schema.model_fields)


def test_evie_ai_orm_maintains_single_sources_of_truth() -> None:
    assert {"title", "content"}.isdisjoint(Requirement.__table__.c.keys())
    assert {
        "title",
        "precondition",
        "natural_steps",
        "expected_result",
        "priority",
        "tags",
    }.isdisjoint(AssetModel.__table__.c.keys())
    assert FORBIDDEN_ASSET_FIELDS.isdisjoint(AssetVersionModel.__table__.c.keys())
    assert FORBIDDEN_ASSET_FIELDS.isdisjoint(RequirementVersion.__table__.c.keys())


def test_version_tables_are_immutable_and_current_versions_have_no_database_fk() -> None:
    for model in (RequirementVersion, AssetVersionModel):
        assert "updated_at" not in model.__table__.c
        assert "updated_by" not in model.__table__.c
    assert Requirement.__table__.c.current_version_pk.foreign_keys == set()
    assert AssetModel.__table__.c.current_version_pk.foreign_keys == set()


def test_phase0_source_schema_supports_only_requirement_provenance() -> None:
    assert set(AssetSourceModel.__table__.c.keys()) == {
        "id",
        "test_asset_source_id",
        "test_asset_pk",
        "requirement_pk",
        "requirement_version_pk",
        "source_identity_hash",
        "created_at",
        "created_by",
    }


def test_content_checksums_are_indexed_but_not_unique() -> None:
    for model in (RequirementVersion, AssetVersionModel):
        unique_columns = {
            tuple(constraint.columns.keys())
            for constraint in model.__table__.constraints
            if isinstance(constraint, UniqueConstraint)
        }
        indexed_columns = {
            tuple(index.columns.keys()) for index in model.__table__.indexes
        }
        assert ("content_checksum",) not in unique_columns
        assert ("content_checksum",) in indexed_columns


def test_required_phase0_foreign_keys_are_explicit_and_named() -> None:
    expected = {
        RequirementVersion.__table__: {
            "fk_requirement_versions_requirement_pk_requirements"
        },
        AssetVersionModel.__table__: {
            "fk_test_asset_versions_test_asset_pk_test_assets"
        },
        AssetSourceModel.__table__: {
            "fk_test_asset_sources_test_asset_pk_test_assets",
            "fk_test_asset_sources_requirement_pk_requirements",
            "fk_test_asset_sources_requirement_version_pk_requirement_versions",
        },
    }
    for table, expected_names in expected.items():
        actual_names = {
            constraint.name
            for constraint in table.constraints
            if isinstance(constraint, ForeignKeyConstraint)
        }
        assert actual_names == expected_names
