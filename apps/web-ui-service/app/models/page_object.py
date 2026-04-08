from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PageObject(Base):
    __tablename__ = "page_objects"
    __table_args__ = (
        UniqueConstraint("project_code", "client", "page_code", name="uq_page_objects_identity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_code: Mapped[str] = mapped_column(String(20), default="atp", index=True)
    client: Mapped[str] = mapped_column(String(10), default="web", index=True)
    page_code: Mapped[str] = mapped_column(String(40), index=True)
    page_name: Mapped[str] = mapped_column(String(120), default="")
    page_url: Mapped[str] = mapped_column(String(256), default="")
    precondition_state: Mapped[str] = mapped_column(Text, default="")
    module_id: Mapped[int] = mapped_column(Integer, default=0, index=True)
    element_count: Mapped[int] = mapped_column(Integer, default=0)
    health_status: Mapped[int] = mapped_column(Integer, default=1, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    created_by: Mapped[str] = mapped_column(String(60), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )


class PageElement(Base):
    __tablename__ = "page_elements"
    __table_args__ = (
        UniqueConstraint("page_object_id", "element_code", name="uq_page_elements_identity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    page_object_id: Mapped[int] = mapped_column(ForeignKey("page_objects.id", ondelete="CASCADE"), index=True)
    element_code: Mapped[str] = mapped_column(String(80), index=True)
    element_name: Mapped[str] = mapped_column(String(120), default="")
    locator_type: Mapped[str] = mapped_column(String(30), default="css")
    locator_value: Mapped[str] = mapped_column(Text, default="")
    backup_locator: Mapped[str] = mapped_column(String(512), default="")
    health_status: Mapped[int] = mapped_column(Integer, default=1, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, index=True)
    role: Mapped[str] = mapped_column(String(60), default="")
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    owner: Mapped[str] = mapped_column(String(60), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )


class PageElementVersion(Base):
    __tablename__ = "page_element_versions"
    __table_args__ = (
        UniqueConstraint("page_element_id", "version_no", name="uq_page_element_versions_identity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    page_element_id: Mapped[int] = mapped_column(ForeignKey("page_elements.id", ondelete="CASCADE"), index=True)
    version_no: Mapped[int] = mapped_column(index=True)
    locator_type: Mapped[str] = mapped_column(String(30), default="css")
    locator_value: Mapped[str] = mapped_column(Text, default="")
    role: Mapped[str] = mapped_column(String(60), default="")
    status: Mapped[str] = mapped_column(String(20), default="active")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    changed_by: Mapped[str] = mapped_column(String(60), default="system")
    change_summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class PageObjectRef(Base):
    __tablename__ = "page_object_refs"
    __table_args__ = (
        UniqueConstraint("page_element_id", "reference_type", "reference_key", name="uq_page_object_refs_identity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    page_element_id: Mapped[int] = mapped_column(ForeignKey("page_elements.id", ondelete="CASCADE"), index=True)
    reference_type: Mapped[str] = mapped_column(String(30), default="test_case", index=True)
    reference_key: Mapped[str] = mapped_column(String(120), index=True)
    source: Mapped[str] = mapped_column(String(40), default="manual")
    created_by: Mapped[str] = mapped_column(String(60), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class PageElementHealthCheck(Base):
    __tablename__ = "page_element_health_checks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    page_element_id: Mapped[int] = mapped_column(ForeignKey("page_elements.id", ondelete="CASCADE"), index=True)
    check_status: Mapped[str] = mapped_column(String(20), default="unknown", index=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    checked_by: Mapped[str] = mapped_column(String(60), default="system")
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class PageObjectRecorderSession(Base):
    __tablename__ = "page_object_recorder_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    project_code: Mapped[str] = mapped_column(String(20), default="atp", index=True)
    client: Mapped[str] = mapped_column(String(10), default="web", index=True)
    page_code: Mapped[str] = mapped_column(String(40), index=True)
    page_name: Mapped[str] = mapped_column(String(120), default="")
    url: Mapped[str] = mapped_column(String(512), default="")
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    process_pid: Mapped[int | None] = mapped_column(nullable=True, index=True)
    script_path: Mapped[str] = mapped_column(String(1024), default="")
    started_by: Mapped[str] = mapped_column(String(60), default="system")
    error_message: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
