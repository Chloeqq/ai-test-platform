"""EvieAi 需求聚合及不可变版本模型。"""

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
    Text,
    UniqueConstraint,
    column,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.constants.evie_ai import RequirementStatus, RequirementVersionStatus
from app.core.database import Base


class Requirement(Base):
    """需求聚合根；正文只存在于 RequirementVersion。"""

    __tablename__ = "requirements"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_requirements"),
        UniqueConstraint("requirement_id", name="uq_requirements_requirement_id"),
        UniqueConstraint(
            "project_code",
            "requirement_code",
            name="uq_requirements_project_code_requirement_code",
        ),
        CheckConstraint(
            column("status").in_(RequirementStatus.values()),
            name="ck_requirements_status",
        ),
        CheckConstraint("row_version >= 1", name="ck_requirements_row_version_positive"),
        Index("ix_requirements_project_code", "project_code"),
        Index(
            "ix_requirements_project_code_external_requirement_key",
            "project_code",
            "external_requirement_key",
        ),
        Index("ix_requirements_status", "status"),
        Index("ix_requirements_deleted_at", "deleted_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    requirement_id: Mapped[str] = mapped_column(String(64), nullable=False)
    project_code: Mapped[str] = mapped_column(String(20), nullable=False)
    requirement_code: Mapped[str] = mapped_column(String(120), nullable=False)
    external_requirement_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
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


class RequirementVersion(Base):
    """需求正文的不可变版本。"""

    __tablename__ = "requirement_versions"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_requirement_versions"),
        UniqueConstraint(
            "requirement_version_id",
            name="uq_requirement_versions_requirement_version_id",
        ),
        UniqueConstraint(
            "requirement_pk",
            "version_no",
            name="uq_requirement_versions_requirement_pk_version_no",
        ),
        ForeignKeyConstraint(
            ["requirement_pk"],
            ["requirements.id"],
            name="fk_requirement_versions_requirement_pk_requirements",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "version_no >= 1",
            name="ck_requirement_versions_version_no_positive",
        ),
        CheckConstraint(
            column("version_status").in_(RequirementVersionStatus.values()),
            name="ck_requirement_versions_version_status",
        ),
        Index("ix_requirement_versions_requirement_pk", "requirement_pk"),
        Index("ix_requirement_versions_content_checksum", "content_checksum"),
        Index("ix_requirement_versions_version_status", "version_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    requirement_version_id: Mapped[str] = mapped_column(String(64), nullable=False)
    requirement_pk: Mapped[int] = mapped_column(Integer, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    version_status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
