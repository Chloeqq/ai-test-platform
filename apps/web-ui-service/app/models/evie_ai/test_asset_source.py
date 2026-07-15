"""EvieAi TestAsset 通用来源与 Requirement 类型化来源。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    column,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.constants.evie_ai import TestAssetSourceType
from app.core.database import Base


class TestAssetSource(Base):
    """绑定 TestAsset 聚合的通用来源身份。"""

    __tablename__ = "test_asset_sources"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_test_asset_sources"),
        UniqueConstraint(
            "test_asset_source_id",
            name="uq_test_asset_sources_test_asset_source_id",
        ),
        UniqueConstraint(
            "test_asset_pk",
            "source_identity_hash",
            name="uq_test_asset_sources_test_asset_pk_source_identity_hash",
        ),
        ForeignKeyConstraint(
            ["test_asset_pk"],
            ["test_assets.id"],
            name="fk_test_asset_sources_test_asset_pk_test_assets",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            column("source_type").in_(TestAssetSourceType.values()),
            name="ck_test_asset_sources_source_type",
        ),
        Index("ix_test_asset_sources_test_asset_pk", "test_asset_pk"),
        Index("ix_test_asset_sources_source_type", "source_type"),
        Index("ix_test_asset_sources_source_identity_hash", "source_identity_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_asset_source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    test_asset_pk: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_identity_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)


class TestAssetRequirementSource(Base):
    """Requirement 来源的强类型外键事实。"""

    __tablename__ = "test_asset_requirement_sources"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_test_asset_requirement_sources"),
        UniqueConstraint(
            "test_asset_source_pk",
            name="uq_test_asset_requirement_sources_source_pk",
        ),
        ForeignKeyConstraint(
            ["test_asset_source_pk"],
            ["test_asset_sources.id"],
            name="fk_test_asset_req_sources_source_pk_sources",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["requirement_pk"],
            ["requirements.id"],
            name="fk_test_asset_req_sources_requirement_pk_requirements",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["requirement_version_pk"],
            ["requirement_versions.id"],
            name="fk_test_asset_req_sources_req_version_pk_req_versions",
            ondelete="RESTRICT",
        ),
        Index("ix_test_asset_req_sources_requirement_pk", "requirement_pk"),
        Index(
            "ix_test_asset_req_sources_requirement_version_pk",
            "requirement_version_pk",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_asset_source_pk: Mapped[int] = mapped_column(Integer, nullable=False)
    requirement_pk: Mapped[int] = mapped_column(Integer, nullable=False)
    requirement_version_pk: Mapped[int] = mapped_column(Integer, nullable=False)
