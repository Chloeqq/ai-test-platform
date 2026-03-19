import os
import sys
from pathlib import Path

import uvicorn

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_APP_DIR = REPO_ROOT / "apps" / "web-ui-service"

if str(SERVICE_APP_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_APP_DIR))

from app.main import app as fastapi_app

app = fastapi_app


def create_app():
    return app


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        app_dir=str(SERVICE_APP_DIR),
        host=os.getenv("WEB_UI_HOST", "127.0.0.1"),
        port=int(os.getenv("WEB_UI_PORT", "8013")),
        reload=os.getenv("WEB_UI_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"},
    )
