from urllib.error import URLError
from urllib.request import urlopen

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine
from app.core.minio_client import ping_minio
from app.core.redis_client import ping_redis

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def readiness() -> dict[str, object]:
    settings = get_settings()
    db_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    redis_ok = ping_redis()

    minio_ok = ping_minio() if settings.minio_enabled else False

    orchestrator_ok = False
    orchestrator_url = settings.orchestrator_url.rstrip("/")
    if orchestrator_url:
        try:
            with urlopen(f"{orchestrator_url}/health", timeout=2) as response:  # nosec B310
                orchestrator_ok = int(response.status) < 500
        except (URLError, TimeoutError, ValueError):
            pass

    status = "ok" if db_ok else "degraded"
    return {
        "status": status,
        "service": settings.app_name,
        "app_env": settings.app_env,
        "database": {"ok": db_ok, "dialect": engine.dialect.name},
        "redis": {
            "enabled": settings.redis_enabled,
            "ok": redis_ok if settings.redis_enabled else None,
        },
        "minio": {
            "enabled": settings.minio_enabled,
            "ok": minio_ok if settings.minio_enabled else None,
        },
        "orchestrator": {"url": orchestrator_url, "ok": orchestrator_ok},
    }
