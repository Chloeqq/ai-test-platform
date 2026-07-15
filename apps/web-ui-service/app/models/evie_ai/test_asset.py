"""EvieAi 自然语言测试资产聚合和不可变版本模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    column,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.constants.evie_ai import TestAssetConversionStatus, TestAssetReviewStatus
from app.core.database import Base


class TestAsset(Base):
    """自然语言测试资产聚合根；正文只存在于 TestAssetVersion。"""

    __tablename__ = "test_assets"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_test_assets"),
        UniqueConstraint("test_asset_id", name="uq_test_assets_test_asset_id"),
        UniqueConstraint(
            "project_code",
            "asset_code",
            name="uq_test_assets_project_code_asset_code",
        ),
        CheckConstraint(
            column("review_status").in_(TestAssetReviewStatus.values()),
            name="ck_test_assets_review_status",
        ),
        CheckConstraint(
            column("conversion_status").in_(TestAssetConversionStatus.values()),
            name="ck_test_assets_conversion_status",
        ),
        CheckConstraint("row_version >= 1", name="ck_test_assets_row_version_positive"),
        Index("ix_test_assets_project_code", "project_code"),
        Index("ix_test_assets_review_status", "review_status"),
        Index("ix_test_assets_conversion_status", "conversion_status"),
        Index("ix_test_assets_deleted_at", "deleted_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_asset_id: Mapped[str] = mapped_column(String(64), nullable=False)
    project_code: Mapped[str] = mapped_column(String(20), nullable=False)
    asset_code: Mapped[str] = mapped_column(String(120), nullable=False)
    review_status: Mapped[str] = mapped_column(String(20), nullable=False)
    conversion_status: Mapped[str] = mapped_column(String(20), nullable=False)
    current_version_pk: Mapped[int | None] = mapped_column(Integer, nullable=True)
    row_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(120), nullable=False)


class TestAssetVersion(Base):
    """自然语言测试资产内容的不可变版本。"""

    __tablename__ = "test_asset_versions"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_test_asset_versions"),
        UniqueConstraint(
            "test_asset_version_id",
            name="uq_test_asset_versions_test_asset_version_id",
        ),
        UniqueConstraint(
            "test_asset_pk",
            "version_no",
            name="uq_test_asset_versions_test_asset_pk_version_no",
        ),
        ForeignKeyConstraint(
            ["test_asset_pk"],
            ["test_assets.id"],
            name="fk_test_asset_versions_test_asset_pk_test_assets",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "version_no >= 1",
            name="ck_test_asset_versions_version_no_positive",
        ),
        Index("ix_test_asset_versions_test_asset_pk", "test_asset_pk"),
        Index("ix_test_asset_versions_content_checksum", "content_checksum"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_asset_version_id: Mapped[str] = mapped_column(String(64), nullable=False)
    test_asset_pk: Mapped[int] = mapped_column(Integer, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    precondition: Mapped[str | None] = mapped_column(Text, nullable=True)
    natural_steps: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    expected_result: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    content_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
