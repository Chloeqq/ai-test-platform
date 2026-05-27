"""共享数据库工具——SQLAlchemy session 获取，供 orchestrator 和 web-ui-service 共用。"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def _build_engine():
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        # Fallback to default sqlite path
        from pathlib import Path
        db_path = Path(__file__).resolve().parents[1] / "apps" / "web-ui-service" / "dev.db"
        database_url = f"sqlite:///{db_path}"

    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, future=True, pool_pre_ping=True, connect_args=connect_args)


_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """返回 SQLAlchemy Session 上下文管理器。"""
    SessionLocal = sessionmaker(bind=_get_engine(), autocommit=False, autoflush=False, future=True)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
