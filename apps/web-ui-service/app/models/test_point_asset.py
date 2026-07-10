"""测试点资产（bundle 粒度）—— DB 事实源。

一个资产 = 一份 requirement 的测试点 bundle(asset_id 唯一),整份内容存
`raw_payload`(无损),另抽若干可查询列(项目/页面/状态/优先级/计数等)。
与 test_cases.script_code 同构:DB 为权威,web-ui/state 文件仅为可重建缓存。
点粒度的 test_points 表保留作派生覆盖率索引(可后置)。
"""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TestPointAsset(Base):
    __tablename__ = "test_point_assets"
    __table_args__ = (
        UniqueConstraint("project_code", "asset_id", name="uq_test_point_assets_identity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_code: Mapped[str] = mapped_column(String(20), default="mall", index=True)
    asset_id: Mapped[str] = mapped_column(String(120), index=True)
    page_code: Mapped[str] = mapped_column(String(40), default="common", index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    priority: Mapped[str] = mapped_column(String(20), default="P1", index=True)
    source_type: Mapped[str] = mapped_column(String(40), default="", index=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    point_count: Mapped[int] = mapped_column(Integer, default=0)
    intent_count: Mapped[int] = mapped_column(Integer, default=0)
    requires_review: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )
