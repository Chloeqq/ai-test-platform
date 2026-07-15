from __future__ import annotations

import pytest
from app.constants.evie_ai import (
    RequirementStatus,
    RequirementVersionStatus,
)
from app.constants.evie_ai import (
    TestAssetAuditEventType as AssetAuditEventType,
)
from app.constants.evie_ai import (
    TestAssetConversionStatus as AssetConversionStatus,
)
from app.constants.evie_ai import (
    TestAssetOperationType as AssetOperationType,
)
from app.constants.evie_ai import (
    TestAssetReviewAction as AssetReviewAction,
)
from app.constants.evie_ai import (
    TestAssetReviewStatus as AssetReviewStatus,
)
from app.constants.evie_ai import (
    TestAssetSourceType as AssetSourceType,
)
from app.core.id_gen import (
    generate_requirement_id,
    generate_requirement_version_id,
    generate_test_asset_id,
    generate_test_asset_version_id,
)
from app.models.evie_ai import (
    Requirement,
    RequirementVersion,
)
from app.models.evie_ai import (
    TestAsset as AssetModel,
)
from app.models.evie_ai import (
    TestAssetAuditEvent as AssetAuditEventModel,
)
from app.models.evie_ai import (
    TestAssetContentClaim as AssetContentClaimModel,
)
from app.models.evie_ai import (
    TestAssetIdempotencyRecord as AssetIdempotencyRecordModel,
)
from app.models.evie_ai import (
    TestAssetRequirementSource as AssetRequirementSourceModel,
)
from app.models.evie_ai import (
    TestAssetReviewRecord as AssetReviewRecordModel,
)
from app.models.evie_ai import (
    TestAssetSource as AssetSourceModel,
)
from app.models.evie_ai import (
    TestAssetVersion as AssetVersionModel,
)
from app.models.user import User
from sqlalchemy import (
    CheckConstraint,
    Engine,
    ForeignKeyConstraint,
    Index,
    PrimaryKeyConstraint,
    UniqueConstraint,
    inspect,
    text,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

EVIE_AI_TABLE_NAMES = {
    "requirements",
    "requirement_versions",
    "test_assets",
    "test_asset_versions",
    "test_asset_sources",
    "test_asset_requirement_sources",
    "test_asset_idempotency_records",
    "test_asset_content_claims",
    "test_asset_review_records",
    "test_asset_audit_events",
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
}


def _requirement(*, requirement_id: str | None = None) -> Requirement:
    return Requirement(
        requirement_id=requirement_id or generate_requirement_id(),
        project_code="project-a",
        requirement_code="REQ-001",
        external_requirement_key=None,
        status=RequirementStatus.DRAFT.value,
        created_by="tester",
        updated_by="tester",
    )


def _requirement_version(requirement_pk: int, *, version_no: int = 1) -> RequirementVersion:
    return RequirementVersion(
        requirement_version_id=generate_requirement_version_id(),
        requirement_pk=requirement_pk,
        version_no=version_no,
        title="登录需求",
        content="用户可以登录系统",
        content_checksum="1" * 64,
        version_status=RequirementVersionStatus.DRAFT.value,
        created_by="tester",
    )


def _test_asset() -> AssetModel:
    return AssetModel(
        test_asset_id=generate_test_asset_id(),
        project_code="project-a",
        asset_code="ASSET-001",
        review_status=AssetReviewStatus.PENDING.value,
        conversion_status=AssetConversionStatus.NOT_STARTED.value,
        created_by="tester",
        updated_by="tester",
    )


def _test_asset_version(test_asset_pk: int, *, version_no: int = 1) -> AssetVersionModel:
    return AssetVersionModel(
        test_asset_version_id=generate_test_asset_version_id(),
        test_asset_pk=test_asset_pk,
        version_no=version_no,
        title="有效用户登录",
        precondition="账号有效",
        natural_steps=["打开登录页", "输入账号密码", "点击登录"],
        expected_result="进入首页",
        priority="P1",
        content_checksum="2" * 64,
        created_by="tester",
    )


def test_evie_ai_sqlite_fixture_enables_foreign_keys(evie_ai_engine: Engine) -> None:
    with evie_ai_engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1


def test_evie_ai_tables_are_registered_and_created(evie_ai_engine: Engine) -> None:
    assert EVIE_AI_TABLE_NAMES.issubset(set(inspect(evie_ai_engine).get_table_names()))


def test_public_id_columns_are_uniquely_constrained() -> None:
    expected = {
        Requirement.__table__: "requirement_id",
        RequirementVersion.__table__: "requirement_version_id",
        AssetModel.__table__: "test_asset_id",
        AssetVersionModel.__table__: "test_asset_version_id",
        AssetSourceModel.__table__: "test_asset_source_id",
    }

    for table, public_id_column in expected.items():
        unique_columns = {
            tuple(constraint.columns.keys())
            for constraint in table.constraints
            if isinstance(constraint, UniqueConstraint)
        }
        assert (public_id_column,) in unique_columns


def test_requirement_public_id_unique_constraint_is_enforced(
    evie_ai_session: Session,
) -> None:
    public_id = generate_requirement_id()
    first = _requirement(requirement_id=public_id)
    second = _requirement(requirement_id=public_id)
    second.requirement_code = "REQ-002"
    evie_ai_session.add_all([first, second])

    try:
        evie_ai_session.flush()
    except IntegrityError:
        evie_ai_session.rollback()
    else:
        raise AssertionError("duplicate requirement_id must be rejected")


def test_required_version_foreign_key_is_enforced(evie_ai_session: Session) -> None:
    evie_ai_session.add(_requirement_version(999_999))

    try:
        evie_ai_session.flush()
    except IntegrityError:
        evie_ai_session.rollback()
    else:
        raise AssertionError("unknown requirement_pk must be rejected")


def test_required_test_asset_version_foreign_key_is_enforced(
    evie_ai_session: Session,
) -> None:
    evie_ai_session.add(_test_asset_version(999_999))

    try:
        evie_ai_session.flush()
    except IntegrityError:
        evie_ai_session.rollback()
    else:
        raise AssertionError("unknown test_asset_pk must be rejected")


def test_all_evie_ai_constraints_and_indexes_are_explicitly_named() -> None:
    tables = (
        Requirement.__table__,
        RequirementVersion.__table__,
        AssetModel.__table__,
        AssetVersionModel.__table__,
        AssetSourceModel.__table__,
        AssetRequirementSourceModel.__table__,
        AssetIdempotencyRecordModel.__table__,
        AssetContentClaimModel.__table__,
        AssetReviewRecordModel.__table__,
        AssetAuditEventModel.__table__,
    )
    named_constraint_types = (
        PrimaryKeyConstraint,
        UniqueConstraint,
        ForeignKeyConstraint,
        CheckConstraint,
    )

    for table in tables:
        for constraint in table.constraints:
            if isinstance(constraint, named_constraint_types):
                assert constraint.name, f"unnamed constraint on {table.name}"
        for index in table.indexes:
            assert isinstance(index, Index)
            assert index.name, f"unnamed index on {table.name}"


def test_current_version_pk_is_nullable_without_database_foreign_key() -> None:
    assert Requirement.__table__.c.current_version_pk.nullable is True
    assert AssetModel.__table__.c.current_version_pk.nullable is True
    assert Requirement.__table__.c.current_version_pk.foreign_keys == set()
    assert AssetModel.__table__.c.current_version_pk.foreign_keys == set()


def test_version_tables_are_immutable_by_shape() -> None:
    for model in (
        RequirementVersion,
        AssetVersionModel,
        AssetReviewRecordModel,
        AssetAuditEventModel,
    ):
        columns = set(model.__table__.c.keys())
        assert "updated_at" not in columns
        assert "updated_by" not in columns


def test_test_asset_models_contain_no_machine_execution_fields() -> None:
    for model in (AssetModel, AssetVersionModel):
        assert FORBIDDEN_ASSET_FIELDS.isdisjoint(model.__table__.c.keys())


def test_json_list_default_is_not_shared_between_versions(evie_ai_session: Session) -> None:
    asset = _test_asset()
    evie_ai_session.add(asset)
    evie_ai_session.flush()

    first = _test_asset_version(asset.id, version_no=1)
    second = _test_asset_version(asset.id, version_no=2)
    evie_ai_session.add_all([first, second])
    evie_ai_session.flush()

    first.tags.append("login")

    assert first.tags == ["login"]
    assert second.tags == []
    assert first.tags is not second.tags


def test_parent_delete_is_restricted_when_versions_exist(evie_ai_session: Session) -> None:
    requirement = _requirement()
    evie_ai_session.add(requirement)
    evie_ai_session.flush()
    evie_ai_session.add(_requirement_version(requirement.id))
    evie_ai_session.flush()

    evie_ai_session.delete(requirement)
    try:
        evie_ai_session.flush()
    except IntegrityError:
        evie_ai_session.rollback()
    else:
        raise AssertionError("requirement with versions must not be physically deleted")


def test_phase1_source_models_separate_common_and_requirement_fields() -> None:
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


def test_phase1_uniqueness_contracts_are_present() -> None:
    def unique_column_sets(model: type[object]) -> set[tuple[str, ...]]:
        return {
            tuple(constraint.columns.keys())
            for constraint in model.__table__.constraints
            if isinstance(constraint, UniqueConstraint)
        }

    assert ("test_asset_pk", "source_identity_hash") in unique_column_sets(
        AssetSourceModel
    )
    assert ("test_asset_source_pk",) in unique_column_sets(
        AssetRequirementSourceModel
    )
    assert (
        "project_code",
        "operation_type",
        "actor_or_client_id",
        "idempotency_key",
    ) in unique_column_sets(AssetIdempotencyRecordModel)
    assert ("project_code", "content_fingerprint") in unique_column_sets(
        AssetContentClaimModel
    )
    assert ("test_asset_pk",) in unique_column_sets(AssetContentClaimModel)


def test_review_and_audit_store_idempotency_snapshots_without_strong_fk() -> None:
    snapshot_fields = {
        "operation_type",
        "idempotency_scope_hash",
        "idempotency_key_hash",
        "idempotency_generation",
    }
    for model in (AssetReviewRecordModel, AssetAuditEventModel):
        assert snapshot_fields.issubset(model.__table__.c.keys())
        assert "idempotency_record_pk" not in model.__table__.c
        assert "idempotency_key" not in model.__table__.c


def test_user_public_id_is_required_and_uniquely_constrained() -> None:
    column = User.__table__.c.user_public_id
    assert column.nullable is False
    unique_names = {
        constraint.name
        for constraint in User.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
        and tuple(constraint.columns.keys()) == ("user_public_id",)
    }
    assert unique_names == {"uq_users_user_public_id"}


def test_phase1_state_checks_use_central_contract_values() -> None:
    assert AssetSourceType.values() == ("requirement", "manual")
    assert AssetOperationType.REVIEW_ASSET.value == "review_asset"
    assert AssetReviewAction.REOPEN.value == "reopen"
    assert AssetAuditEventType.ASSET_CREATED.value == "asset_created"


def test_user_public_id_has_no_implicit_generator_default() -> None:
    column = User.__table__.c.user_public_id
    assert column.default is None
    assert column.server_default is None


def test_test_asset_version_has_only_approved_content_fields() -> None:
    approved_content_fields = {
        "title",
        "precondition",
        "natural_steps",
        "expected_result",
        "priority",
        "tags",
    }
    technical_fields = {
        "id",
        "test_asset_version_id",
        "test_asset_pk",
        "version_no",
        "content_checksum",
        "created_at",
        "created_by",
    }
    assert set(AssetVersionModel.__table__.c.keys()) == (
        approved_content_fields | technical_fields
    )


def test_governance_records_do_not_duplicate_natural_language_content() -> None:
    natural_language_fields = {
        "title",
        "precondition",
        "natural_steps",
        "expected_result",
        "priority",
        "tags",
    }
    for model in (AssetReviewRecordModel, AssetAuditEventModel):
        assert natural_language_fields.isdisjoint(model.__table__.c.keys())


def test_all_evie_ai_schema_identifiers_fit_postgresql_limit() -> None:
    for table in (
        Requirement.__table__,
        RequirementVersion.__table__,
        AssetModel.__table__,
        AssetVersionModel.__table__,
        AssetSourceModel.__table__,
        AssetRequirementSourceModel.__table__,
        AssetIdempotencyRecordModel.__table__,
        AssetContentClaimModel.__table__,
        AssetReviewRecordModel.__table__,
        AssetAuditEventModel.__table__,
    ):
        for schema_object in (*table.constraints, *table.indexes):
            assert schema_object.name is not None
            assert len(schema_object.name.encode("utf-8")) <= 63


def test_content_claim_database_uniqueness_is_enforced(
    evie_ai_session: Session,
) -> None:
    first_asset = _test_asset()
    second_asset = _test_asset()
    second_asset.asset_code = "ASSET-002"
    evie_ai_session.add_all([first_asset, second_asset])
    evie_ai_session.flush()
    evie_ai_session.add(
        AssetContentClaimModel(
            test_asset_pk=first_asset.id,
            project_code="project-a",
            content_fingerprint="a" * 64,
        )
    )
    evie_ai_session.flush()
    evie_ai_session.add(
        AssetContentClaimModel(
            test_asset_pk=second_asset.id,
            project_code="project-a",
            content_fingerprint="a" * 64,
        )
    )
    with pytest.raises(IntegrityError):
        evie_ai_session.flush()
