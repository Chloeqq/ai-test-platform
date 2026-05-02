from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

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


class PageObjectRecorderSession(Base):
    __tablename__ = "page_object_recorder_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    project_code: Mapped[str] = mapped_column(String(20), default="mall", index=True)
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


class PageObjectCandidateGroup(Base):
    __tablename__ = "page_object_candidate_groups"
    __table_args__ = (
        UniqueConstraint(
            "project_code",
            "client",
            "page_code",
            "group_key",
            name="uq_page_object_candidate_groups_identity",
        ),
        Index(
            "ix_page_object_candidate_groups_page_status",
            "project_code",
            "client",
            "page_code",
            "promotion_status",
        ),
        Index(
            "ix_page_object_candidate_groups_page_quality",
            "project_code",
            "client",
            "page_code",
            "quality_tier",
        ),
        Index("ix_page_object_candidate_groups_matched_element", "matched_existing_element_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_code: Mapped[str] = mapped_column(String(20), default="mall", index=True)
    client: Mapped[str] = mapped_column(String(10), default="web", index=True)
    page_code: Mapped[str] = mapped_column(String(40), index=True)
    group_key: Mapped[str] = mapped_column(String(160), index=True)
    proposed_element_code: Mapped[str] = mapped_column(String(80), default="")
    proposed_element_name: Mapped[str] = mapped_column(String(120), default="")
    business_type_guess: Mapped[str] = mapped_column(String(40), default="")
    business_domain_guess: Mapped[str] = mapped_column(String(40), default="")
    quality_tier: Mapped[str] = mapped_column(String(20), default="", index=True)
    max_score: Mapped[int] = mapped_column(Integer, default=0)
    avg_score: Mapped[int] = mapped_column(Integer, default=0)
    session_count: Mapped[int] = mapped_column(Integer, default=0)
    candidate_count: Mapped[int] = mapped_column(Integer, default=0)
    recommended_action: Mapped[str] = mapped_column(String(20), default="review")
    promotion_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    route_scope: Mapped[str] = mapped_column(String(256), default="")
    top_locator_source: Mapped[str] = mapped_column(String(20), default="")
    top_locator_type: Mapped[str] = mapped_column(String(30), default="")
    top_locator_value: Mapped[str] = mapped_column(Text, default="")
    top_role: Mapped[str] = mapped_column(String(60), default="")
    risk_tags_json: Mapped[list[Any]] = mapped_column(JSON, default=list)
    sample_texts_json: Mapped[list[Any]] = mapped_column(JSON, default=list)
    matched_existing_element_code: Mapped[str] = mapped_column(String(80), default="", index=True)
    reviewed_by: Mapped[str] = mapped_column(String(60), default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    review_note: Mapped[str] = mapped_column(Text, default="")
    latest_session_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )


class PageObjectCandidateElement(Base):
    __tablename__ = "page_object_candidate_elements"
    __table_args__ = (
        UniqueConstraint("session_id", "candidate_key", name="uq_page_object_candidate_elements_identity"),
        Index(
            "ix_page_object_candidate_elements_page_status",
            "project_code",
            "client",
            "page_code",
            "candidate_status",
        ),
        Index("ix_page_object_candidate_elements_group_key", "group_key"),
        Index("ix_page_object_candidate_elements_session_id", "session_id"),
        Index("ix_page_object_candidate_elements_quality_score", "quality_score"),
        Index("ix_page_object_candidate_elements_recommended_action", "recommended_action"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_code: Mapped[str] = mapped_column(String(20), default="mall", index=True)
    client: Mapped[str] = mapped_column(String(10), default="web", index=True)
    page_code: Mapped[str] = mapped_column(String(40), index=True)
    session_id: Mapped[str] = mapped_column(String(64))
    candidate_key: Mapped[str] = mapped_column(String(120), index=True)
    group_key: Mapped[str] = mapped_column(String(160))
    raw_locator_type: Mapped[str] = mapped_column(String(30), default="")
    raw_locator_value: Mapped[str] = mapped_column(Text, default="")
    raw_role: Mapped[str] = mapped_column(String(60), default="")
    raw_text: Mapped[str] = mapped_column(Text, default="")
    dom_signature: Mapped[str] = mapped_column(String(160), default="")
    route: Mapped[str] = mapped_column(String(256), default="")
    step_hit_count: Mapped[int] = mapped_column(Integer, default=0)
    quality_score: Mapped[int] = mapped_column(Integer, default=0)
    quality_tier: Mapped[str] = mapped_column(String(20), default="")
    risk_tags_json: Mapped[list[Any]] = mapped_column(JSON, default=list)
    recommended_action: Mapped[str] = mapped_column(String(20), default="review")
    candidate_status: Mapped[str] = mapped_column(String(20), default="pending")
    ingest_block_reason: Mapped[str] = mapped_column(Text, default="")
    proposed_element_code: Mapped[str] = mapped_column(String(80), default="")
    proposed_element_name: Mapped[str] = mapped_column(String(120), default="")
    business_type_guess: Mapped[str] = mapped_column(String(40), default="")
    probe_status: Mapped[str] = mapped_column(String(20), default="unknown")
    probe_match_count: Mapped[int] = mapped_column(Integer, default=0)
    probe_visible: Mapped[bool] = mapped_column(Boolean, default=False)
    probe_interactable: Mapped[bool] = mapped_column(Boolean, default=False)
    merged_to_element_code: Mapped[str] = mapped_column(String(80), default="")
    promoted_element_code: Mapped[str] = mapped_column(String(80), default="")
    reviewed_by: Mapped[str] = mapped_column(String(60), default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    review_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )


class PageElementLocator(Base):
    __tablename__ = "page_element_locators"
    __table_args__ = (
        UniqueConstraint(
            "page_element_id",
            "locator_type",
            "locator_value",
            "role",
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
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
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
    before_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    after_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    operator: Mapped[str] = mapped_column(String(60), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
