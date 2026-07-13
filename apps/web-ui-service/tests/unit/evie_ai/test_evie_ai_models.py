from __future__ import annotations

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

from app.constants.evie_ai import (
    RequirementStatus,
    RequirementVersionStatus,
    TestAssetConversionStatus as AssetConversionStatus,
    TestAssetReviewStatus as AssetReviewStatus,
)
from app.core.id_gen import (
    generate_requirement_id,
    generate_requirement_version_id,
    generate_test_asset_id,
    generate_test_asset_source_id,
    generate_test_asset_version_id,
)
from app.models.evie_ai import (
    Requirement,
    RequirementVersion,
    TestAsset as AssetModel,
    TestAssetSource as AssetSourceModel,
    TestAssetVersion as AssetVersionModel,
)


EVIE_AI_TABLE_NAMES = {
    "requirements",
    "requirement_versions",
    "test_assets",
    "test_asset_versions",
    "test_asset_sources",
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
    for model in (RequirementVersion, AssetVersionModel):
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
