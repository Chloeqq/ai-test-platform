from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TestCase(Base):
    __tablename__ = "test_cases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    product_line: Mapped[str] = mapped_column(String(120), index=True)
    module: Mapped[str] = mapped_column(String(120), index=True)
    priority: Mapped[str] = mapped_column(String(20), default="P2", index=True)
    test_type: Mapped[str] = mapped_column(String(50), default="ui", index=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    markers: Mapped[list[str]] = mapped_column(JSON, default=list)
    creator: Mapped[str] = mapped_column(String(120), default="system", index=True)
    pytest_path: Mapped[str] = mapped_column(String(500), default="", index=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    script_code: Mapped[str] = mapped_column(Text, default="")
    data_config: Mapped[dict] = mapped_column(JSON, default=dict)
    last_execution_result: Mapped[str] = mapped_column(String(40), default="unknown", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class TestCaseDefect(Base):
    __tablename__ = "test_case_defects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id", ondelete="CASCADE"), index=True)
    defect_key: Mapped[str] = mapped_column(String(120), index=True)
    defect_url: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TestCaseExecution(Base):
    __tablename__ = "test_case_executions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    report_url: Mapped[str] = mapped_column(Text, default="")
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class TestCaseVersion(Base):
    __tablename__ = "test_case_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id", ondelete="CASCADE"), index=True)
    version_no: Mapped[int] = mapped_column(Integer, index=True)
    script_code: Mapped[str] = mapped_column(Text, default="")
    changed_by: Mapped[str] = mapped_column(String(120), default="system")
    change_summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
