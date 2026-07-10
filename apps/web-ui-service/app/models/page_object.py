from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PageObject(Base):
    __tablename__ = "page_objects"
    __table_args__ = (
        UniqueConstraint("project_code", "client", "page_code", name="uq_page_objects_identity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_code: Mapped[str] = mapped_column(String(20), default="mall", index=True)
    client: Mapped[str] = mapped_column(String(10), default="web", index=True)
    page_code: Mapped[str] = mapped_column(String(40), index=True)
    elements: Mapped[list[PageElement]] = relationship(back_populates="page_object", lazy="select")
    page_name: Mapped[str] = mapped_column(String(120), default="")
    page_url: Mapped[str] = mapped_column(String(256), default="")
    precondition_state: Mapped[str] = mapped_column(Text, default="")
    route_pattern: Mapped[str] = mapped_column(String(256), default="")
    anchor_config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    governance_status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    testability_score: Mapped[int] = mapped_column(Integer, default=0)
    key_element_count: Mapped[int] = mapped_column(Integer, default=0)
    approved_element_count: Mapped[int] = mapped_column(Integer, default=0)
    candidate_pending_count: Mapped[int] = mapped_column(Integer, default=0)
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
        Index("ix_page_elements_page_object_review_status", "page_object_id", "review_status"),
        Index("ix_page_elements_page_object_business_type", "page_object_id", "business_type"),
        Index("ix_page_elements_page_object_stability_level", "page_object_id", "stability_level"),
        Index("ix_page_elements_page_object_locator_source", "page_object_id", "locator_source"),
        Index("ix_page_elements_page_object_testid_value", "page_object_id", "testid_value"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    page_object_id: Mapped[int] = mapped_column(ForeignKey("page_objects.id", ondelete="CASCADE"), index=True)
    page_object: Mapped[PageObject] = relationship(back_populates="elements")
    element_code: Mapped[str] = mapped_column(String(80), index=True)
    element_name: Mapped[str] = mapped_column(String(120), default="")
    locator_type: Mapped[str] = mapped_column(String(30), default="css")
    locator_value: Mapped[str] = mapped_column(Text, default="")
    backup_locator: Mapped[str] = mapped_column(String(512), default="")
    business_type: Mapped[str] = mapped_column(String(40), default="")
    business_domain: Mapped[str] = mapped_column(String(40), default="")
    aliases_json: Mapped[list[Any]] = mapped_column(JSON, default=list)
    semantic_tags_json: Mapped[list[Any]] = mapped_column(JSON, default=list)
    locator_source: Mapped[str] = mapped_column(String(20), default="")
    match_strategy: Mapped[str] = mapped_column(String(20), default="exact")
    stability_level: Mapped[str] = mapped_column(String(20), default="low")
    review_status: Mapped[str] = mapped_column(String(20), default="pending")
    origin_candidate_key: Mapped[str] = mapped_column(String(120), default="")
    route_scope: Mapped[str] = mapped_column(String(256), default="")
    anchor_required: Mapped[bool] = mapped_column(Boolean, default=False)
    is_key_element: Mapped[bool] = mapped_column(Boolean, default=False)
    testid_value: Mapped[str] = mapped_column(String(120), default="")
    qa_value: Mapped[str] = mapped_column(String(120), default="")
    governance_note: Mapped[str] = mapped_column(Text, default="")
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



# PageElementLocator / PageObjectGovernanceLog 回归（原被误移到 recorder_models）
# — 它们是页面对象核心模型，不是录制功能专用


class PageElementLocator(Base):
    __tablename__ = "page_element_locators"
    __table_args__ = (
        UniqueConstraint(
            "page_element_id", "locator_type", "locator_value", "role",
            name="uq_page_element_locators_identity",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    page_element_id: Mapped[int] = mapped_column(ForeignKey("page_elements.id", ondelete="CASCADE"), index=True)
    locator_type: Mapped[str] = mapped_column(String(30), default="")
    locator_value: Mapped[str] = mapped_column(String(512), default="")
    role: Mapped[str] = mapped_column(String(60), default="")
    locator_source: Mapped[str] = mapped_column(String(20), default="")
    priority: Mapped[int] = mapped_column(Integer, default=100)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    health_status: Mapped[str] = mapped_column(String(20), default="unknown", index=True)
    verification_status: Mapped[str] = mapped_column(String(20), default="unknown", index=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_by: Mapped[str] = mapped_column(String(60), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True,
    )


class PageObjectGovernanceLog(Base):
    __tablename__ = "page_object_governance_logs"
    __table_args__ = (
        Index("ix_page_object_governance_logs_page", "project_code", "client", "page_code"),
        Index("ix_page_object_governance_logs_entity", "entity_type", "entity_key"),
        Index("ix_page_object_governance_logs_action", "action"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_code: Mapped[str] = mapped_column(String(20), default="mall", index=True)
    client: Mapped[str] = mapped_column(String(10), default="web", index=True)
    page_code: Mapped[str] = mapped_column(String(40), index=True)
    entity_type: Mapped[str] = mapped_column(String(40), default="")
    entity_key: Mapped[str] = mapped_column(String(160), default="")
    action: Mapped[str] = mapped_column(String(40), default="")
    operator: Mapped[str] = mapped_column(String(60), default="system", index=True)
    before_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    after_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
