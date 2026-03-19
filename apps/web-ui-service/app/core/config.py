import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "dev.db"


class Settings(BaseModel):
    app_name: str = "AI Test Platform FastAPI"
    app_env: str = Field(default_factory=lambda: os.getenv("APP_ENV", "dev"))
    database_url: str = Field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            f"sqlite:///{DEFAULT_DB_PATH}",
        )
    )
    jwt_secret_key: str = Field(default_factory=lambda: os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-change-me"))
    jwt_algorithm: str = Field(default_factory=lambda: os.getenv("JWT_ALGORITHM", "HS256"))
    jwt_expire_minutes: int = Field(default_factory=lambda: int(os.getenv("JWT_EXPIRE_MINUTES", "120")))
    default_admin_username: str = Field(default_factory=lambda: os.getenv("ADMIN_USERNAME", "admin"))
    default_admin_password: str = Field(default_factory=lambda: os.getenv("ADMIN_PASSWORD", "admin123"))
    default_admin_role: str = Field(default_factory=lambda: os.getenv("ADMIN_ROLE", "admin"))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
