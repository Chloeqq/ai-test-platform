import logging
import time
import uuid
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.core.redis_client import ping_redis
from app.core.security import hash_password
from app.models import User
from app.routers.auth import router as auth_router
from app.routers.dashboard import router as dashboard_router
from app.routers.health import router as health_router
from app.routers.legacy_console import router as legacy_console_router
from app.routers.legacy_workbench import router as legacy_workbench_router
from app.routers.test_cases import router as test_cases_router
from app.routers.workbench_assets import router as workbench_assets_router
from app.routers.workbench_gate import router as workbench_gate_router
from app.routers.workbench_generation import router as workbench_generation_router
from app.routers.workbench_reporting import router as workbench_reporting_router
from app.routers.workbench_reviews import router as workbench_reviews_router
from app.routers.workbench_runs import router as workbench_runs_router
from app.routers.ui import router as ui_router
from apps.shared_backend.observability import configure_logging, set_request_id

settings = get_settings()
configure_logging(service_name="web-ui-service")
access_logger = logging.getLogger("web.access")
STATIC_DIR = Path(__file__).resolve().parent / "static"
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="FastAPI backend skeleton with SQLite and JWT authentication.",
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
ALLURE_DIR = Path(__file__).resolve().parents[3] / "runners" / "web-playwright-python" / "allure-report"
ALLURE_SNAPSHOTS_DIR = Path(__file__).resolve().parents[3] / "runners" / "web-playwright-python" / "allure-report-snapshots"
if ALLURE_DIR.exists():
    app.mount("/allure", StaticFiles(directory=str(ALLURE_DIR)), name="allure")
ALLURE_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/allure-snapshots", StaticFiles(directory=str(ALLURE_SNAPSHOTS_DIR)), name="allure-snapshots")
app.include_router(ui_router)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(legacy_console_router)
app.include_router(workbench_assets_router)
app.include_router(workbench_gate_router)
app.include_router(workbench_generation_router)
app.include_router(workbench_reporting_router)
app.include_router(workbench_reviews_router)
app.include_router(workbench_runs_router)
app.include_router(legacy_workbench_router)
app.include_router(test_cases_router)


@app.middleware("http")
async def _disable_allure_cache(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = str(request.headers.get("x-request-id", "")).strip() or str(uuid.uuid4())
    start = time.perf_counter()
    set_request_id(request_id)
    response: Response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Request-Id"] = request_id
    access_logger.info(
        "http_request method=%s path=%s status=%s duration_ms=%.2f client=%s",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        request.client.host if request.client else "-",
    )
    if request.url.path.startswith("/allure"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


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
    if settings.database_auto_create_tables:
        Base.metadata.create_all(bind=engine)
    _ensure_default_admin()


@app.get("/health/ready")
def readiness() -> dict[str, object]:
    db_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    redis_ok = ping_redis()

    orchestrator_ok = False
    orchestrator_url = settings.orchestrator_url.rstrip("/")
    if orchestrator_url:
        try:
            with urlopen(f"{orchestrator_url}/health", timeout=2) as response:  # nosec B310
                orchestrator_ok = int(response.status) < 500
        except (URLError, TimeoutError, ValueError):
            orchestrator_ok = False

    status = "ok" if db_ok else "degraded"
    return {
        "status": status,
        "service": settings.app_name,
        "app_env": settings.app_env,
        "database": {
            "ok": db_ok,
            "dialect": engine.dialect.name,
        },
        "redis": {
            "enabled": settings.redis_enabled,
            "ok": redis_ok if settings.redis_enabled else None,
        },
        "orchestrator": {
            "url": orchestrator_url,
            "ok": orchestrator_ok,
        },
    }
