from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TestDataPool(Base):
    __tablename__ = "test_data_pools"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    pool_name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    created_by: Mapped[str] = mapped_column(String(120), default="system")
    updated_by: Mapped[str] = mapped_column(String(120), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class TestDataPoolItem(Base):
    __tablename__ = "test_data_pool_items"
    __table_args__ = (
        UniqueConstraint("pool_id", "item_key", name="uq_test_data_pool_item_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    pool_id: Mapped[int] = mapped_column(ForeignKey("test_data_pools.id", ondelete="CASCADE"), index=True)
    item_key: Mapped[str] = mapped_column(String(160), index=True)
    item_value: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    created_by: Mapped[str] = mapped_column(String(120), default="system")
    updated_by: Mapped[str] = mapped_column(String(120), default="system")
    tags: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class TestDataPoolAuditLog(Base):
    __tablename__ = "test_data_pool_audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    pool_name: Mapped[str] = mapped_column(String(120), index=True)
    item_key: Mapped[str] = mapped_column(String(160), default="", index=True)
    operation: Mapped[str] = mapped_column(String(40), index=True)
    changed_by: Mapped[str] = mapped_column(String(120), default="system")
    note: Mapped[str] = mapped_column(Text, default="")
    before_value: Mapped[str] = mapped_column(Text, default="")
    after_value: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
