from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TestCase(Base):
    __tablename__ = "test_cases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # 反向引用：通过 Repository 查询，此处仅供 ORM 导航（非强制）
    executions: Mapped[list["TestCaseExecution"]] = relationship(back_populates="case", lazy="select")
    steps: Mapped[list["TestCaseStep"]] = relationship(back_populates="case", lazy="select")
    versions: Mapped[list["TestCaseVersion"]] = relationship(back_populates="case", lazy="select")
    defects: Mapped[list["TestCaseDefect"]] = relationship(back_populates="case", lazy="select")
    project_code: Mapped[str] = mapped_column(String(20), default="atp", index=True)
    client: Mapped[str] = mapped_column(String(10), default="web", index=True)
    page_code: Mapped[str] = mapped_column(String(20), default="common", index=True)
    page_name: Mapped[str] = mapped_column(String(100), default="")
    module_code: Mapped[str] = mapped_column(String(20), default="core", index=True)
    module_name: Mapped[str] = mapped_column(String(100), default="")
    case_type: Mapped[str] = mapped_column(String(10), default="fn", index=True)
    source: Mapped[str] = mapped_column(String(10), default="mn", index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    product_line: Mapped[str] = mapped_column(String(120), index=True)
    module: Mapped[str] = mapped_column(String(120), index=True)
    chain_stage: Mapped[str] = mapped_column(String(120), default="", index=True)
    sut_service: Mapped[str] = mapped_column(String(120), default="", index=True)
    related_services: Mapped[list[str]] = mapped_column(JSON, default=list)
    priority: Mapped[str] = mapped_column(String(20), default="P2", index=True)
    test_type: Mapped[str] = mapped_column(String(50), default="ui", index=True)
    scenario_types: Mapped[list[str]] = mapped_column(JSON, default=list)
    trigger_entry: Mapped[str] = mapped_column(String(40), default="")
    fault_injection_type: Mapped[str] = mapped_column(String(80), default="")
    fault_injection_target: Mapped[str] = mapped_column(String(255), default="")
    fault_injection_params: Mapped[str] = mapped_column(Text, default="")
    setup_sql: Mapped[str] = mapped_column(Text, default="")
    precondition_state: Mapped[str] = mapped_column(Text, default="")
    test_steps: Mapped[list[dict]] = mapped_column(JSON, default=list)
    test_steps_text: Mapped[str] = mapped_column(Text, default="")
    concurrency_model: Mapped[str] = mapped_column(String(120), default="")
    retry_policy: Mapped[str] = mapped_column(Text, default="")
    expected_result: Mapped[str] = mapped_column(Text, default="")
    assert_sql: Mapped[str] = mapped_column(Text, default="")
    event_assertion: Mapped[str] = mapped_column(Text, default="")
    metric_assertion: Mapped[str] = mapped_column(Text, default="")
    cleanup_script: Mapped[str] = mapped_column(Text, default="")
    artifact_links: Mapped[list[str]] = mapped_column(JSON, default=list)
    notes: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    markers: Mapped[list[str]] = mapped_column(JSON, default=list)
    creator: Mapped[str] = mapped_column(String(120), default="system", index=True)
    assignee: Mapped[str] = mapped_column(String(120), default="", index=True)
    pytest_path: Mapped[str] = mapped_column(String(500), default="", index=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    automation_status: Mapped[str] = mapped_column(String(20), default="manual", index=True)
    created_source: Mapped[str] = mapped_column(String(40), default="manual", index=True)
    source_ref: Mapped[str] = mapped_column(String(255), default="")
    script_code: Mapped[str] = mapped_column(Text, default="")
    data_config: Mapped[dict] = mapped_column(JSON, default=dict)
    last_execution_result: Mapped[str] = mapped_column(String(40), default="unknown", index=True)
    last_report_url: Mapped[str] = mapped_column(Text, default="")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class TestCaseStep(Base):
    __tablename__ = "test_case_steps"
    __table_args__ = (
        UniqueConstraint("case_id", "step_index", name="uq_test_case_steps_identity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id", ondelete="CASCADE"), index=True)
    case: Mapped["TestCase"] = relationship(back_populates="steps")
    case_business_id: Mapped[str] = mapped_column(String(64), index=True)
    project_code: Mapped[str] = mapped_column(String(20), default="atp", index=True)
    page_code: Mapped[str] = mapped_column(String(40), default="", index=True)
    step_index: Mapped[int] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(80), default="")
    target: Mapped[str] = mapped_column(String(255), default="")
    locator_type: Mapped[str] = mapped_column(String(40), default="")
    locator_value: Mapped[str] = mapped_column(Text, default="")
    step_data: Mapped[str] = mapped_column(Text, default="")
    expected_result: Mapped[str] = mapped_column(Text, default="")
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )


class TestCaseDefect(Base):
    __tablename__ = "test_case_defects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id", ondelete="CASCADE"), index=True)
    case: Mapped["TestCase"] = relationship(back_populates="defects")
    defect_key: Mapped[str] = mapped_column(String(120), index=True)
    defect_url: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TestCaseExecution(Base):
    __tablename__ = "test_case_executions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id", ondelete="CASCADE"), index=True)
    case: Mapped["TestCase"] = relationship(back_populates="executions")
    status: Mapped[str] = mapped_column(String(40), index=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    report_url: Mapped[str] = mapped_column(Text, default="")
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class TestCaseVersion(Base):
    __tablename__ = "test_case_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id", ondelete="CASCADE"), index=True)
    case: Mapped["TestCase"] = relationship(back_populates="versions")
    version_no: Mapped[int] = mapped_column(Integer, index=True)
    script_code: Mapped[str] = mapped_column(Text, default="")
    changed_by: Mapped[str] = mapped_column(String(120), default="system")
    change_summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class TestCaseTreeNode(Base):
    __tablename__ = "test_case_tree_nodes"
    __table_args__ = (
        UniqueConstraint("project_code", "product_line", "module", name="uq_test_case_tree_node"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_code: Mapped[str] = mapped_column(String(20), default="atp", index=True)
    product_line: Mapped[str] = mapped_column(String(120), index=True)
    module: Mapped[str] = mapped_column(String(120), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
