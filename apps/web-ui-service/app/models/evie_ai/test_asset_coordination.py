"""EvieAi 幂等协调和有效内容占用模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
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

from app.constants.evie_ai import TestAssetOperationType
from app.core.database import Base


class TestAssetIdempotencyRecord(Base):
    """可过期、可按 generation 重新占用的技术幂等记录。"""

    __tablename__ = "test_asset_idempotency_records"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_test_asset_idempotency_records"),
        UniqueConstraint(
            "project_code",
            "operation_type",
            "actor_or_client_id",
            "idempotency_key",
            name="uq_test_asset_idempotency_scope_key",
        ),
        CheckConstraint(
            column("operation_type").in_(TestAssetOperationType.values()),
            name="ck_test_asset_idempotency_operation_type",
        ),
        CheckConstraint("generation >= 1", name="ck_test_asset_idempotency_generation"),
        CheckConstraint(
            "result_http_status IS NULL OR "
            "(result_http_status >= 100 AND result_http_status <= 599)",
            name="ck_test_asset_idempotency_http_status",
        ),
        Index("ix_test_asset_idempotency_expires_at", "expires_at"),
        Index("ix_test_asset_idempotency_completed_at", "completed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_code: Mapped[str] = mapped_column(String(20), nullable=False)
    operation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_or_client_id: Mapped[str] = mapped_column(String(120), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    result_http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    test_asset_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    test_asset_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    test_asset_review_record_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    created: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    reused_existing: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    changed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    row_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deleted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TestAssetContentClaim(Base):
    """有效资产当前内容指纹的唯一占用。"""

    __tablename__ = "test_asset_content_claims"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_test_asset_content_claims"),
        UniqueConstraint(
            "project_code",
            "content_fingerprint",
            name="uq_test_asset_content_claims_project_fingerprint",
        ),
        UniqueConstraint(
            "test_asset_pk",
            name="uq_test_asset_content_claims_test_asset_pk",
        ),
        ForeignKeyConstraint(
            ["test_asset_pk"],
            ["test_assets.id"],
            name="fk_test_asset_content_claims_asset_pk_test_assets",
            ondelete="RESTRICT",
        ),
        Index("ix_test_asset_content_claims_fingerprint", "content_fingerprint"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_asset_pk: Mapped[int] = mapped_column(Integer, nullable=False)
    project_code: Mapped[str] = mapped_column(String(20), nullable=False)
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
