from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.constants.evie_ai import TestAssetSourceType as SourceType
from app.models.evie_ai import TestAssetRequirementSource as RequirementSourceModel
from app.repositories.evie_ai import (
    RepositoryDataIntegrityError,
    RequirementRepository,
    SourceOwnershipError,
)
from app.repositories.evie_ai import (
    TestAssetRepository as AssetRepository,
)
from app.repositories.evie_ai import (
    TestAssetSourceRepository as SourceRepository,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .repository_test_support import (
    make_asset,
    make_requirement,
    make_requirement_version,
    make_source,
)


def test_manual_source_round_trip_has_no_requirement_subtype(
    evie_ai_session: Session,
) -> None:
    asset = AssetRepository(evie_ai_session).add(make_asset())
    repository = SourceRepository(evie_ai_session)
    source = repository.add_manual_source(make_source(asset.id))

    assert (
        repository.get_by_identity(
            test_asset_pk=asset.id,
            source_identity_hash=source.source_identity_hash,
        )
        is source
    )
    assert repository.exists_identity(
        test_asset_pk=asset.id,
        source_identity_hash=source.source_identity_hash,
    )
    records = repository.list_by_asset(asset.id)
    assert len(records) == 1
    assert records[0].source is source
    assert records[0].requirement_source is None


def test_requirement_source_validates_version_and_project_scope(
    evie_ai_session: Session,
) -> None:
    requirements = RequirementRepository(evie_ai_session)
    requirement = requirements.add(make_requirement())
    version = requirements.add_version(make_requirement_version(requirement.id))
    asset = AssetRepository(evie_ai_session).add(make_asset())
    repository = SourceRepository(evie_ai_session)

    source = repository.add_requirement_source(
        make_source(
            asset.id,
            source_type=SourceType.REQUIREMENT.value,
        ),
        requirement_pk=requirement.id,
        requirement_version_pk=version.id,
    )

    record = repository.list_by_asset(asset.id)[0]
    assert record.source is source
    assert record.requirement is requirement
    assert record.requirement_version is version
    assert record.requirement_source is not None


def test_requirement_source_rejects_cross_project_binding(
    evie_ai_session: Session,
) -> None:
    requirements = RequirementRepository(evie_ai_session)
    requirement = requirements.add(make_requirement(project_code="project-b"))
    version = requirements.add_version(make_requirement_version(requirement.id))
    asset = AssetRepository(evie_ai_session).add(make_asset())

    with pytest.raises(SourceOwnershipError):
        SourceRepository(evie_ai_session).add_requirement_source(
            make_source(
                asset.id,
                source_type=SourceType.REQUIREMENT.value,
            ),
            requirement_pk=requirement.id,
            requirement_version_pk=version.id,
        )


def test_source_identity_uniqueness_is_enforced_by_database(
    evie_ai_session: Session,
) -> None:
    asset = AssetRepository(evie_ai_session).add(make_asset())
    repository = SourceRepository(evie_ai_session)
    repository.add_manual_source(make_source(asset.id))

    with pytest.raises(IntegrityError):
        repository.add_manual_source(make_source(asset.id))


def test_source_identity_query_requires_explicit_deleted_visibility(
    evie_ai_session: Session,
) -> None:
    asset = AssetRepository(evie_ai_session).add(make_asset())
    repository = SourceRepository(evie_ai_session)
    source = repository.add_manual_source(make_source(asset.id))
    asset.deleted_at = datetime.now(UTC)
    evie_ai_session.flush()

    assert (
        repository.get_by_identity(
            test_asset_pk=asset.id,
            source_identity_hash=source.source_identity_hash,
        )
        is None
    )
    assert (
        repository.get_by_identity(
            test_asset_pk=asset.id,
            source_identity_hash=source.source_identity_hash,
            include_deleted=True,
        )
        is source
    )


def test_requirement_source_without_subtype_fails_closed(
    evie_ai_session: Session,
) -> None:
    asset = AssetRepository(evie_ai_session).add(make_asset())
    source = make_source(
        asset.id,
        source_type=SourceType.REQUIREMENT.value,
    )
    evie_ai_session.add(source)
    evie_ai_session.flush()

    with pytest.raises(RepositoryDataIntegrityError) as exc_info:
        SourceRepository(evie_ai_session).list_by_asset(asset.id)

    assert exc_info.value.error_code == "EVIE_DATA_INTEGRITY_ERROR"


def test_manual_source_with_requirement_subtype_fails_closed(
    evie_ai_session: Session,
) -> None:
    requirements = RequirementRepository(evie_ai_session)
    requirement = requirements.add(make_requirement())
    version = requirements.add_version(make_requirement_version(requirement.id))
    asset = AssetRepository(evie_ai_session).add(make_asset())
    source = SourceRepository(evie_ai_session).add_manual_source(make_source(asset.id))
    evie_ai_session.add(
        RequirementSourceModel(
            test_asset_source_pk=source.id,
            requirement_pk=requirement.id,
            requirement_version_pk=version.id,
        )
    )
    evie_ai_session.flush()

    with pytest.raises(RepositoryDataIntegrityError):
        SourceRepository(evie_ai_session).list_by_asset(asset.id)
