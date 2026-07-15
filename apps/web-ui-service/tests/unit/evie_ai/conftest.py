from __future__ import annotations

import sqlite3
from collections.abc import Iterator

import pytest
from app.core.database import Base
from app.models.evie_ai import (
    Requirement,
    RequirementVersion,
    TestAsset,
    TestAssetAuditEvent,
    TestAssetContentClaim,
    TestAssetIdempotencyRecord,
    TestAssetRequirementSource,
    TestAssetReviewRecord,
    TestAssetSource,
    TestAssetVersion,
)
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def evie_ai_engine() -> Iterator[Engine]:
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(
        dbapi_connection: sqlite3.Connection,
        _connection_record: object,
    ) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    tables = [
        Requirement.__table__,
        RequirementVersion.__table__,
        TestAsset.__table__,
        TestAssetVersion.__table__,
        TestAssetSource.__table__,
        TestAssetRequirementSource.__table__,
        TestAssetIdempotencyRecord.__table__,
        TestAssetContentClaim.__table__,
        TestAssetReviewRecord.__table__,
        TestAssetAuditEvent.__table__,
    ]
    Base.metadata.create_all(bind=engine, tables=tables)

    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1

    try:
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine, tables=list(reversed(tables)))
        engine.dispose()


@pytest.fixture()
def evie_ai_session(evie_ai_engine: Engine) -> Iterator[Session]:
    session_factory = sessionmaker(
        bind=evie_ai_engine,
        autocommit=False,
        autoflush=False,
        future=True,
    )
    session = session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
