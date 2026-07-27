from __future__ import annotations

import ast
from pathlib import Path

from app.models.evie_ai import (
    Requirement,
    RequirementVersion,
)
from app.models.evie_ai import (
    TestAsset as AssetModel,
)
from app.models.evie_ai import (
    TestAssetRequirementSource as AssetRequirementSourceModel,
)
from app.models.evie_ai import (
    TestAssetSource as AssetSourceModel,
)
from app.models.evie_ai import (
    TestAssetVersion as AssetVersionModel,
)
from app.schemas.evie_ai import (
    ManualTestAssetSourceCreate,
    ManualTestAssetSourceRead,
    RequirementTestAssetSourceCreate,
    RequirementTestAssetSourceRead,
)
from app.schemas.evie_ai import (
    TestAssetCreate as AssetCreate,
)
from app.schemas.evie_ai import (
    TestAssetRead as AssetRead,
)
from app.schemas.evie_ai import (
    TestAssetVersionCreate as AssetVersionCreate,
)
from app.schemas.evie_ai import (
    TestAssetVersionRead as AssetVersionRead,
)
from sqlalchemy import ForeignKeyConstraint, UniqueConstraint

SERVICE_ROOT = Path(__file__).resolve().parents[3]
EVIE_AI_MODULE_ROOTS = (
    SERVICE_ROOT / "app" / "errors" / "evie_ai.py",
    SERVICE_ROOT / "app" / "models" / "evie_ai",
    SERVICE_ROOT / "app" / "schemas" / "evie_ai",
    SERVICE_ROOT / "app" / "repositories" / "evie_ai",
    SERVICE_ROOT / "app" / "policies" / "evie_ai",
    SERVICE_ROOT / "app" / "services" / "evie_ai",
)
SLICE5_SERVICE_PATHS = tuple(
    SERVICE_ROOT / "app" / "services" / "evie_ai" / filename
    for filename in (
        "project_access_authorizer.py",
        "project_scope_service.py",
        "request_actor_context.py",
        "request_channel_context.py",
        "request_trace_context.py",
        "user_public_identity_service.py",
    )
)
INTAKE_SERVICE_PATH = (
    SERVICE_ROOT
    / "app"
    / "services"
    / "evie_ai"
    / "test_asset_intake_service.py"
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
        paths = (root,) if root.is_file() else root.rglob("*.py")
        for path in paths:
            for reference in _import_references(path):
                for token in FORBIDDEN_IMPORT_TOKENS:
                    if token in reference:
                        violations.append((str(path.relative_to(SERVICE_ROOT)), reference))

    assert violations == []


def test_evie_ai_policies_do_not_depend_on_stateful_application_layers() -> None:
    policy_root = SERVICE_ROOT / "app" / "policies" / "evie_ai"
    forbidden_layers = {
        "app.models",
        "app.repositories",
        "app.routers",
        "app.services",
        "sqlalchemy",
    }
    violations: list[tuple[str, str]] = []

    for path in policy_root.rglob("*.py"):
        for reference in _import_references(path):
            if any(
                reference == layer or reference.startswith(f"{layer}.")
                for layer in forbidden_layers
            ):
                violations.append((str(path.relative_to(SERVICE_ROOT)), reference))

    assert violations == []


def test_test_asset_schemas_have_only_natural_language_domain_fields() -> None:
    schemas = (
        AssetCreate,
        AssetVersionCreate,
        ManualTestAssetSourceCreate,
        RequirementTestAssetSourceCreate,
        AssetRead,
        AssetVersionRead,
        ManualTestAssetSourceRead,
        RequirementTestAssetSourceRead,
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


def test_phase1_source_schema_separates_common_and_requirement_facts() -> None:
    assert set(AssetSourceModel.__table__.c.keys()) == {
        "id",
        "test_asset_source_id",
        "test_asset_pk",
        "source_type",
        "source_identity_hash",
        "created_at",
        "created_by",
    }
    assert set(AssetRequirementSourceModel.__table__.c.keys()) == {
        "id",
        "test_asset_source_pk",
        "requirement_pk",
        "requirement_version_pk",
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


def test_required_foreign_keys_are_explicit_and_named() -> None:
    expected = {
        RequirementVersion.__table__: {
            "fk_requirement_versions_requirement_pk_requirements"
        },
        AssetVersionModel.__table__: {
            "fk_test_asset_versions_test_asset_pk_test_assets"
        },
        AssetSourceModel.__table__: {
            "fk_test_asset_sources_test_asset_pk_test_assets",
        },
        AssetRequirementSourceModel.__table__: {
            "fk_test_asset_req_sources_source_pk_sources",
            "fk_test_asset_req_sources_requirement_pk_requirements",
            "fk_test_asset_req_sources_req_version_pk_req_versions",
        },
    }
    for table, expected_names in expected.items():
        actual_names = {
            constraint.name
            for constraint in table.constraints
            if isinstance(constraint, ForeignKeyConstraint)
        }
        assert actual_names == expected_names


def test_slice5_security_services_have_no_default_project_or_business_chain_dependencies() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in SLICE5_SERVICE_PATHS
    ).lower()

    forbidden_tokens = {
        "ensure_project_seed",
        "ensure_project_writable",
        "get_project_status",
        "default_project_code",
        "testassetintakeservice",
        "execution_compiler",
        "candidate",
        "runner",
        "/api/evie-ai/test-assets",
    }

    assert all(token not in source for token in forbidden_tokens)
    assert '"mall"' not in source


def test_intake_service_preserves_natural_language_asset_boundaries() -> None:
    source = INTAKE_SERVICE_PATH.read_text(encoding="utf-8").lower()
    forbidden_tokens = {
        "candidate",
        "preview",
        "selected_candidates",
        "execution_compiler",
        "runner",
        "testcase",
        "script_code",
        "structured_steps",
        "default_project_code",
        "/api/evie-ai/test-assets",
        "fastapi",
        "httpexception",
    }

    assert all(token not in source for token in forbidden_tokens)
    assert '"mall"' not in source


def test_intake_service_is_the_only_public_intake_class() -> None:
    definitions: list[tuple[str, str]] = []
    application_root = SERVICE_ROOT / "app"

    for path in application_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if (
                isinstance(node, ast.ClassDef)
                and "IntakeService" in node.name
            ):
                definitions.append(
                    (str(path.relative_to(SERVICE_ROOT)), node.name)
                )

    assert definitions == [
        (
            "app/services/evie_ai/test_asset_intake_service.py",
            "TestAssetIntakeService",
        )
    ]
