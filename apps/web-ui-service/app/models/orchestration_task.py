from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OrchestrationTask(Base):
    __tablename__ = "orchestration_tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_name: Mapped[str] = mapped_column(String(255), index=True)
    input_source_type: Mapped[str] = mapped_column(String(80), index=True)
    input_source_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    agent_config: Mapped[dict] = mapped_column(JSON, default=dict)
    asset_binding: Mapped[dict] = mapped_column(JSON, default=dict)
    execution_config: Mapped[dict] = mapped_column(JSON, default=dict)
    preview_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(40), default="queued", index=True)
    created_by: Mapped[str] = mapped_column(String(120), default="admin", index=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
