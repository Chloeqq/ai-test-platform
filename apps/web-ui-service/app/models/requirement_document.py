
"""RequirementDocument 模型：需求文档上传解析 + MinIO 存档记录。

事实源：object_key 指向 MinIO 中的原始文件；parsed_text 不落库（体积大），
仅在上传时同步返回，需要时可凭 object_key 重新下载解析。
"""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.constants.requirement_document import ParseStatus
from app.core.database import Base


class RequirementDocument(Base):
    __tablename__ = "requirement_documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_code: Mapped[str] = mapped_column(String(64), index=True)
    filename: Mapped[str] = mapped_column(String(512), default="")
    source_type: Mapped[str] = mapped_column(String(20), default="")  # docx/pdf/md
    object_key: Mapped[str] = mapped_column(String(1024), default="")
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    parse_status: Mapped[str] = mapped_column(
        String(20), default=ParseStatus.PENDING, index=True
    )  # pending/parsed/partial/failed
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_blocks: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
