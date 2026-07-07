from datetime import datetime

from sqlalchemy import DateTime, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TestPoint(Base):
    __tablename__ = "test_points"
    __table_args__ = (
        UniqueConstraint("project_code", "page_code", "point_id", name="uq_test_points_identity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_code: Mapped[str] = mapped_column(String(20), default="atp", index=True)
    page_code: Mapped[str] = mapped_column(String(40), default="common", index=True)
    point_id: Mapped[str] = mapped_column(String(80), index=True)
    point_name: Mapped[str] = mapped_column(String(255), default="")
    scene_type: Mapped[str] = mapped_column(String(40), default="", index=True)
    priority: Mapped[str] = mapped_column(String(20), default="P1", index=True)
    test_data_type: Mapped[str] = mapped_column(String(40), default="")
    involved_elements: Mapped[list[str]] = mapped_column(JSON, default=list)
    expect_result: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(40), default="manual", index=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )
