"""AI Prompt 模板模型：支持 DB 自定义覆盖 + 内置默认兜底。"""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    CODE_MAX_LENGTH = 80
    NAME_MAX_LENGTH = 120
    SCENE_TYPE_MAX_LENGTH = 40
    USER_MAX_LENGTH = 120
    DEFAULT_VERSION = 1

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(CODE_MAX_LENGTH), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH))
    scene_type: Mapped[str] = mapped_column(String(SCENE_TYPE_MAX_LENGTH), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    user_prompt_template: Mapped[str] = mapped_column(Text, default="")
    variables: Mapped[dict] = mapped_column(JSON, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, default=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=DEFAULT_VERSION)
    created_by: Mapped[str | None] = mapped_column(String(USER_MAX_LENGTH), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(USER_MAX_LENGTH), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )
