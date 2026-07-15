"""EvieAi 不可变审核历史和资产审计事件。"""

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
)
from sqlalchemy.orm import Mapped, mapped_column

from app.constants.evie_ai import (
    TestAssetAuditEventType,
    TestAssetOperationType,
    TestAssetReviewAction,
    TestAssetReviewStatus,
)
from app.core.database import Base


class TestAssetReviewRecord(Base):
    """绑定具体 TestAssetVersion 的不可变审核记录。"""

    __tablename__ = "test_asset_review_records"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_test_asset_review_records"),
        UniqueConstraint(
            "test_asset_review_record_id",
            name="uq_test_asset_review_records_public_id",
        ),
        ForeignKeyConstraint(
            ["test_asset_pk"],
            ["test_assets.id"],
            name="fk_test_asset_reviews_asset_pk_test_assets",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["test_asset_version_pk"],
            ["test_asset_versions.id"],
            name="fk_test_asset_reviews_version_pk_asset_versions",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            column("from_status").in_(TestAssetReviewStatus.values()),
            name="ck_test_asset_reviews_from_status",
        ),
        CheckConstraint(
            column("to_status").in_(TestAssetReviewStatus.values()),
            name="ck_test_asset_reviews_to_status",
        ),
        CheckConstraint(
            column("review_action").in_(TestAssetReviewAction.values()),
            name="ck_test_asset_reviews_action",
        ),
        CheckConstraint(
            column("operation_type").in_(
                (TestAssetOperationType.REVIEW_ASSET.value,)
            ),
            name="ck_test_asset_reviews_operation_type",
        ),
        CheckConstraint(
            "idempotency_generation >= 1",
            name="ck_test_asset_reviews_idempotency_generation",
        ),
        Index("ix_test_asset_reviews_asset_pk", "test_asset_pk"),
        Index("ix_test_asset_reviews_version_pk", "test_asset_version_pk"),
        Index("ix_test_asset_reviews_reviewed_at", "reviewed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_asset_review_record_id: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    test_asset_pk: Mapped[int] = mapped_column(Integer, nullable=False)
    test_asset_version_pk: Mapped[int] = mapped_column(Integer, nullable=False)
    from_status: Mapped[str] = mapped_column(String(20), nullable=False)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    review_action: Mapped[str] = mapped_column(String(20), nullable=False)
    reviewer: Mapped[str] = mapped_column(String(120), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    operation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    idempotency_scope_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TestAssetAuditEvent(Base):
    """TestAsset 生命周期的不可变、脱敏审计事件。"""

    __tablename__ = "test_asset_audit_events"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_test_asset_audit_events"),
        UniqueConstraint(
            "test_asset_audit_event_id",
            name="uq_test_asset_audit_events_public_id",
        ),
        ForeignKeyConstraint(
            ["test_asset_pk"],
            ["test_assets.id"],
            name="fk_test_asset_audit_events_asset_pk_test_assets",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            column("event_type").in_(TestAssetAuditEventType.values()),
            name="ck_test_asset_audit_events_event_type",
        ),
        CheckConstraint(
            column("operation_type").in_(TestAssetOperationType.values()),
            name="ck_test_asset_audit_events_operation_type",
        ),
        CheckConstraint(
            "idempotency_generation >= 1",
            name="ck_test_asset_audit_idempotency_generation",
        ),
        Index("ix_test_asset_audit_events_asset_pk", "test_asset_pk"),
        Index("ix_test_asset_audit_events_event_type", "event_type"),
        Index("ix_test_asset_audit_events_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_asset_audit_event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    test_asset_pk: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    operation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    idempotency_scope_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    related_test_asset_version_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    related_test_asset_source_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    related_review_record_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    before_state_summary: Mapped[dict[str, object] | None] = mapped_column(
        JSON, nullable=True
    )
    after_state_summary: Mapped[dict[str, object] | None] = mapped_column(
        JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
