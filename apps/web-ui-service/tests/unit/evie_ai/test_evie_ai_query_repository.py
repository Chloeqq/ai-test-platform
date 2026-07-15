from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.constants.evie_ai import TestAssetSourceType as SourceType
from app.repositories.evie_ai import (
    RepositoryDataIntegrityError,
    RequirementRepository,
)
from app.repositories.evie_ai import (
    TestAssetListFilters as AssetListFilters,
)
from app.repositories.evie_ai import (
    TestAssetQueryRepository as AssetQueryRepository,
)
from app.repositories.evie_ai import (
    TestAssetRepository as AssetRepository,
)
from app.repositories.evie_ai import (
    TestAssetReviewRepository as ReviewRepository,
)
from app.repositories.evie_ai import (
    TestAssetSourceRepository as SourceRepository,
)
from sqlalchemy import Engine, event
from sqlalchemy.orm import Session

from .repository_test_support import (
    make_asset,
    make_asset_version,
    make_requirement,
    make_requirement_version,
    make_review,
    make_source,
)


def _persist_asset(
    session: Session,
    *,
    public_suffix: str,
    title: str,
    priority: str = "P1",
    tags: list[str] | None = None,
    deleted_at: datetime | None = None,
):
    assets = AssetRepository(session)
    public_id = "ta_" + public_suffix * 32
    asset = make_asset(test_asset_id=public_id)
    asset.created_at = datetime(2026, 7, 15, 1, tzinfo=UTC)
    asset = assets.add(asset)
    version = assets.add_version(
        make_asset_version(
            asset.id,
            title=title,
            priority=priority,
            tags=tags,
        )
    )
    assets.set_current_version(
        asset,
        version,
        expected_row_version=1,
        updated_by=asset.updated_by,
    )
    SourceRepository(session).add_manual_source(
        make_source(asset.id, source_identity_hash=public_suffix * 64)
    )
    if deleted_at is not None:
        asset.deleted_at = deleted_at
        session.flush()
    return asset, version


def test_asset_list_filters_and_stable_public_id_tiebreaker(
    evie_ai_session: Session,
) -> None:
    first, _ = _persist_asset(
        evie_ai_session,
        public_suffix="a",
        title="Login failure",
        priority="P2",
        tags=["login", "negative"],
    )
    second, _ = _persist_asset(
        evie_ai_session,
        public_suffix="b",
        title="Login success",
        tags=["login", "smoke"],
    )
    _persist_asset(
        evie_ai_session,
        public_suffix="c",
        title="Deleted login",
        deleted_at=datetime.now(UTC),
    )
    repository = AssetQueryRepository(evie_ai_session)

    page = repository.list_assets(
        AssetListFilters(project_code="project-a"),
        page=1,
        page_size=20,
    )
    assert [item.asset for item in page.items] == [second, first]
    assert page.total == 2

    filtered = repository.list_assets(
        AssetListFilters(
            project_code="project-a",
            priority="P1",
            tags=("smoke",),
            keyword="SUCCESS",
            source_type=SourceType.MANUAL.value,
        ),
        page=1,
        page_size=20,
    )
    assert [item.asset for item in filtered.items] == [second]
    assert filtered.items[0].source_types == (SourceType.MANUAL.value,)


def test_asset_list_include_deleted_is_explicit(
    evie_ai_session: Session,
) -> None:
    deleted, _ = _persist_asset(
        evie_ai_session,
        public_suffix="d",
        title="Deleted",
        deleted_at=datetime.now(UTC),
    )
    repository = AssetQueryRepository(evie_ai_session)

    hidden = repository.list_assets(
        AssetListFilters(project_code="project-a"),
        page=1,
        page_size=20,
    )
    visible = repository.list_assets(
        AssetListFilters(project_code="project-a", include_deleted=True),
        page=1,
        page_size=20,
    )
    assert hidden.items == []
    assert [item.asset for item in visible.items] == [deleted]


def test_requirement_filter_and_detail_return_typed_sources_and_latest_review(
    evie_ai_session: Session,
) -> None:
    asset, version = _persist_asset(
        evie_ai_session,
        public_suffix="e",
        title="Requirement asset",
    )
    requirements = RequirementRepository(evie_ai_session)
    requirement = requirements.add(make_requirement())
    requirement_version = requirements.add_version(
        make_requirement_version(requirement.id)
    )
    SourceRepository(evie_ai_session).add_requirement_source(
        make_source(
            asset.id,
            source_type=SourceType.REQUIREMENT.value,
            source_identity_hash="f" * 64,
        ),
        requirement_pk=requirement.id,
        requirement_version_pk=requirement_version.id,
    )
    review = ReviewRepository(evie_ai_session).add(
        make_review(test_asset_pk=asset.id, test_asset_version_pk=version.id)
    )
    repository = AssetQueryRepository(evie_ai_session)

    page = repository.list_assets(
        AssetListFilters(
            project_code="project-a",
            requirement_id=requirement.requirement_id,
        ),
        page=1,
        page_size=20,
    )
    assert [item.asset for item in page.items] == [asset]
    assert page.items[0].latest_review is review
    assert page.items[0].source_types == ("manual", "requirement")

    detail = repository.get_detail(
        project_code="project-a",
        test_asset_id=asset.test_asset_id,
    )
    assert detail is not None
    assert detail.asset is asset
    assert detail.current_version is version
    assert detail.latest_review is review
    assert len(detail.sources) == 2


def test_version_and_review_history_are_independently_paginated(
    evie_ai_session: Session,
) -> None:
    asset, first_version = _persist_asset(
        evie_ai_session,
        public_suffix="1",
        title="Version one",
    )
    assets = AssetRepository(evie_ai_session)
    second_version = assets.add_version(
        make_asset_version(asset.id, version_no=2, title="Version two")
    )
    assets.set_current_version(
        asset,
        second_version,
        expected_row_version=2,
        updated_by=asset.updated_by,
    )
    reviews = ReviewRepository(evie_ai_session)
    older_review = reviews.add(
        make_review(
            test_asset_pk=asset.id,
            test_asset_version_pk=first_version.id,
            reviewed_at=datetime.now(UTC) - timedelta(minutes=1),
        )
    )
    newer_review = reviews.add(
        make_review(
            test_asset_pk=asset.id,
            test_asset_version_pk=second_version.id,
            reviewed_at=datetime.now(UTC),
        )
    )
    repository = AssetQueryRepository(evie_ai_session)

    versions = repository.list_version_history(
        project_code="project-a",
        test_asset_id=asset.test_asset_id,
        include_deleted=False,
        page=1,
        page_size=1,
    )
    review_page = repository.list_review_history(
        project_code="project-a",
        test_asset_id=asset.test_asset_id,
        include_deleted=False,
        page=1,
        page_size=1,
    )
    assert versions is not None and versions.items == [second_version]
    assert versions.total == 2
    assert review_page is not None and review_page.items == [newer_review]
    assert review_page.total == 2
    assert older_review not in review_page.items


def test_list_query_count_is_constant_for_multiple_assets(
    evie_ai_session: Session,
    evie_ai_engine: Engine,
) -> None:
    for suffix in ("2", "3", "4"):
        _persist_asset(
            evie_ai_session,
            public_suffix=suffix,
            title=f"Asset {suffix}",
        )
    evie_ai_session.expire_all()
    selects = 0

    def _count_selects(
        _connection,
        _cursor,
        statement: str,
        _parameters,
        _context,
        _executemany,
    ) -> None:
        nonlocal selects
        if statement.lstrip().upper().startswith("SELECT"):
            selects += 1

    event.listen(evie_ai_engine, "before_cursor_execute", _count_selects)
    try:
        page = AssetQueryRepository(evie_ai_session).list_assets(
            AssetListFilters(project_code="project-a"),
            page=1,
            page_size=20,
        )
    finally:
        event.remove(evie_ai_engine, "before_cursor_execute", _count_selects)

    assert len(page.items) == 3
    assert selects == 3


def test_missing_current_version_fails_closed(
    evie_ai_session: Session,
) -> None:
    AssetRepository(evie_ai_session).add(make_asset())

    with pytest.raises(RepositoryDataIntegrityError):
        AssetQueryRepository(evie_ai_session).list_assets(
            AssetListFilters(project_code="project-a"),
            page=1,
            page_size=20,
        )
