from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WorkbenchRuntimeRun(Base):
    __tablename__ = "workbench_runtime_runs"
    __table_args__ = (UniqueConstraint("run_id", name="uq_workbench_runtime_runs_run_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(120), index=True)
    project: Mapped[str] = mapped_column(String(120), default="default", index=True)
    page: Mapped[str] = mapped_column(String(120), default="", index=True)
    status: Mapped[str] = mapped_column(String(60), default="", index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )


class WorkbenchReviewDecision(Base):
    __tablename__ = "workbench_review_decisions"
    __table_args__ = (
        UniqueConstraint("project", "run_id", "page", "review_type", name="uq_workbench_review_decisions_identity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project: Mapped[str] = mapped_column(String(120), default="default", index=True)
    run_id: Mapped[str] = mapped_column(String(120), default="", index=True)
    page: Mapped[str] = mapped_column(String(120), default="", index=True)
    review_type: Mapped[str] = mapped_column(String(60), default="", index=True)
    status: Mapped[str] = mapped_column(String(60), default="", index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )


class WorkbenchExecutionGateDecision(Base):
    __tablename__ = "workbench_execution_gate_decisions"
    __table_args__ = (
        UniqueConstraint("project", "run_id", "page", name="uq_workbench_execution_gate_decisions_identity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project: Mapped[str] = mapped_column(String(120), default="default", index=True)
    run_id: Mapped[str] = mapped_column(String(120), default="", index=True)
    page: Mapped[str] = mapped_column(String(120), default="", index=True)
    decision: Mapped[str] = mapped_column(String(60), default="", index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )


class WorkbenchHistoryEvent(Base):
    __tablename__ = "workbench_history_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(120), default="", index=True)
    action: Mapped[str] = mapped_column(String(120), default="", index=True)
    page: Mapped[str] = mapped_column(String(120), default="", index=True)
    status: Mapped[str] = mapped_column(String(60), default="", index=True)
    actor_display: Mapped[str] = mapped_column(String(120), default="", index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    detail_summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class WorkbenchDefectLink(Base):
    __tablename__ = "workbench_defect_links"
    __table_args__ = (UniqueConstraint("case_id", "defect_id", name="uq_workbench_defect_links_case_defect"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String(120), default="", index=True)
    defect_id: Mapped[str] = mapped_column(String(120), default="", index=True)
    linked_at: Mapped[str] = mapped_column(String(64), default="", index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )


class WorkbenchFailureSourceCalibration(Base):
    __tablename__ = "workbench_failure_source_calibrations"
    __table_args__ = (UniqueConstraint("sample_id", name="uq_workbench_failure_source_calibrations_sample_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sample_id: Mapped[str] = mapped_column(String(120), default="", index=True)
    run_id: Mapped[str] = mapped_column(String(120), default="", index=True)
    case_id: Mapped[str] = mapped_column(String(120), default="", index=True)
    page: Mapped[str] = mapped_column(String(120), default="", index=True)
    human_decision: Mapped[str] = mapped_column(String(80), default="", index=True)
    predicted_failure_source: Mapped[str] = mapped_column(String(120), default="", index=True)
    confirmed_failure_source: Mapped[str] = mapped_column(String(120), default="", index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )
