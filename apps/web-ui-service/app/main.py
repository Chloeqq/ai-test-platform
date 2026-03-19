from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models import User
from app.routers.auth import router as auth_router
from app.routers.dashboard import router as dashboard_router
from app.routers.health import router as health_router
from app.routers.legacy_console import router as legacy_console_router
from app.routers.legacy_workbench import router as legacy_workbench_router
from app.routers.test_cases import router as test_cases_router
from app.routers.ui import router as ui_router

settings = get_settings()
STATIC_DIR = Path(__file__).resolve().parent / "static"
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="FastAPI backend skeleton with SQLite and JWT authentication.",
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
ALLURE_DIR = Path(__file__).resolve().parents[3] / "runners" / "web-playwright-python" / "allure-report"
if ALLURE_DIR.exists():
    app.mount("/allure", StaticFiles(directory=str(ALLURE_DIR)), name="allure")
app.include_router(ui_router)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(legacy_console_router)
app.include_router(legacy_workbench_router)
app.include_router(test_cases_router)


def _ensure_default_admin() -> None:
    with SessionLocal() as db:
        _create_default_admin_if_needed(db)


def _create_default_admin_if_needed(db: Session) -> None:
    existing = db.execute(select(User).where(User.username == settings.default_admin_username)).scalar_one_or_none()
    if existing:
        return
    user = User(
        username=settings.default_admin_username,
        hashed_password=hash_password(settings.default_admin_password),
        role=settings.default_admin_role,
        is_active=True,
    )
    db.add(user)
    db.commit()


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_default_admin()
