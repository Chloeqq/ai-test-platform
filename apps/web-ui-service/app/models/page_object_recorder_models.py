"""Recorder 模型: 录制器会话、候选元素/分组、定位器、治理日志。提取自 page_object.py。"""
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
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

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
