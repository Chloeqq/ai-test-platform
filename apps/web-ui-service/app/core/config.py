import os
from urllib.parse import urlsplit
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "dev.db"
STRICT_EVIDENCE_POLICY_ENVS = {"prod", "production", "staging", "stage", "preprod", "pre", "uat"}
DEVLIKE_APP_ENVS = {"dev", "development", "local", "test", "testing"}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _resolve_evidence_manifest_policy() -> str:
    raw = os.getenv("EVIDENCE_MANIFEST_POLICY")
    value = str(raw or "auto").strip().lower()
    if value in {"strict", "compat", "auto"}:
        return value
    return "auto"


def _default_evidence_manifest_compat_scan_enabled() -> bool:
    policy = _resolve_evidence_manifest_policy()
    if policy == "strict":
        return False
    if policy == "compat":
        return True
    app_env = str(os.getenv("APP_ENV", "dev")).strip().lower()
    if app_env in STRICT_EVIDENCE_POLICY_ENVS:
        return False
    return True


def _parse_csv(raw: str) -> list[str]:
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


def _default_page_surface_allowed_hosts() -> list[str]:
    configured = _parse_csv(os.getenv("PAGE_SURFACE_ALLOWED_HOSTS", ""))
    hosts: list[str] = []
    base_url = _default_base_url()
    if base_url:
        hostname = urlsplit(base_url).hostname
        if hostname:
            hosts.append(hostname.strip().lower())
    app_env = str(os.getenv("APP_ENV", "dev")).strip().lower()
    if app_env not in STRICT_EVIDENCE_POLICY_ENVS:
        hosts.extend(["localhost", "127.0.0.1", "::1"])
    hosts.extend(item.lower() for item in configured)

    deduped: list[str] = []
    seen: set[str] = set()
    for item in hosts:
        if not item or item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _default_execution_gate_decision_roles() -> list[str]:
    configured = _parse_csv(
        os.getenv(
            "EXECUTION_GATE_DECISION_PRIVILEGED_ROLES",
            "admin,qa-lead,release-manager",
        )
    )
    normalized = [str(item).strip().lower() for item in configured if str(item).strip()]
    return normalized or ["admin"]


def _default_execution_gate_dual_approval_roles() -> list[str]:
    configured = _parse_csv(
        os.getenv(
            "EXECUTION_GATE_DUAL_APPROVAL_BYPASS_ROLES",
            "admin",
        )
    )
    normalized = [str(item).strip().lower() for item in configured if str(item).strip()]
    return normalized or ["admin"]


def _current_app_env() -> str:
    return str(os.getenv("APP_ENV", "dev")).strip().lower()


def _default_base_url() -> str:
    raw = str(os.getenv("BASE_URL", "")).strip()
    if raw:
        return raw
    if _current_app_env() in DEVLIKE_APP_ENVS:
        return "http://localhost:5173/login#/login"
    return ""


def _default_jwt_secret_key() -> str:
    return str(os.getenv("JWT_SECRET_KEY", "")).strip()


def _default_admin_username() -> str:
    return str(os.getenv("ADMIN_USERNAME", "")).strip()


def _default_admin_password() -> str:
    return str(os.getenv("ADMIN_PASSWORD", "")).strip()


def _default_admin_role() -> str:
    return str(os.getenv("ADMIN_ROLE", "")).strip()


def _default_database_auto_create_tables() -> bool:
    return _env_bool("DATABASE_AUTO_CREATE_TABLES", False)


class Settings(BaseModel):
    app_name: str = "AI Test Platform FastAPI"
    app_env: str = Field(default_factory=lambda: os.getenv("APP_ENV", "dev"))
    orchestrator_url: str = Field(default_factory=lambda: os.getenv("ORCHESTRATOR_URL", "http://127.0.0.1:8000"))
    database_url: str = Field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            f"sqlite:///{DEFAULT_DB_PATH}",
        )
    )
    database_pool_size: int = Field(default_factory=lambda: int(os.getenv("DATABASE_POOL_SIZE", "10")))
    database_max_overflow: int = Field(default_factory=lambda: int(os.getenv("DATABASE_MAX_OVERFLOW", "20")))
    database_pool_recycle_seconds: int = Field(default_factory=lambda: int(os.getenv("DATABASE_POOL_RECYCLE_SECONDS", "1800")))
    database_auto_create_tables: bool = Field(
        default_factory=_default_database_auto_create_tables
    )
    redis_url: str = Field(default_factory=lambda: os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))
    redis_enabled: bool = Field(default_factory=lambda: _env_bool("REDIS_ENABLED", True))
    redis_prefix: str = Field(default_factory=lambda: os.getenv("REDIS_PREFIX", "aitest"))
    orchestrator_timeout_seconds: int = Field(default_factory=lambda: int(os.getenv("ORCHESTRATOR_TIMEOUT_SECONDS", "300")))
    jwt_secret_key: str = Field(default_factory=_default_jwt_secret_key)
    jwt_algorithm: str = Field(default_factory=lambda: os.getenv("JWT_ALGORITHM", "HS256"))
    jwt_expire_minutes: int = Field(default_factory=lambda: int(os.getenv("JWT_EXPIRE_MINUTES", "120")))
    default_admin_username: str = Field(default_factory=_default_admin_username)
    default_admin_password: str = Field(default_factory=_default_admin_password)
    default_admin_role: str = Field(default_factory=_default_admin_role)
    evidence_manifest_policy: str = Field(default_factory=_resolve_evidence_manifest_policy)
    evidence_manifest_compat_scan_enabled: bool = Field(
        default_factory=lambda: _env_bool(
            "EVIDENCE_MANIFEST_COMPAT_SCAN_ENABLED",
            _default_evidence_manifest_compat_scan_enabled(),
        )
    )
    page_surface_login_url: str = Field(
        default_factory=lambda: os.getenv(
            "PAGE_SURFACE_LOGIN_URL",
            _default_base_url(),
        )
    )
    page_surface_allowed_hosts: list[str] = Field(default_factory=_default_page_surface_allowed_hosts)
    page_surface_allow_private_hosts: bool = Field(
        default_factory=lambda: _env_bool("PAGE_SURFACE_ALLOW_PRIVATE_HOSTS", False)
    )
    execution_gate_block_missing_required_threshold: int = Field(
        default_factory=lambda: int(os.getenv("EXECUTION_GATE_BLOCK_MISSING_REQUIRED_THRESHOLD", "2"))
    )
    execution_gate_block_on_failed_status: bool = Field(
        default_factory=lambda: _env_bool("EXECUTION_GATE_BLOCK_ON_FAILED_STATUS", True)
    )
    execution_gate_block_on_risk_block: bool = Field(
        default_factory=lambda: _env_bool("EXECUTION_GATE_BLOCK_ON_RISK_BLOCK", True)
    )
    execution_gate_warn_on_pending_reviews: bool = Field(
        default_factory=lambda: _env_bool("EXECUTION_GATE_WARN_ON_PENDING_REVIEWS", True)
    )
    execution_gate_warn_on_low_confidence_elements: bool = Field(
        default_factory=lambda: _env_bool("EXECUTION_GATE_WARN_ON_LOW_CONFIDENCE_ELEMENTS", True)
    )
    execution_gate_warn_on_pending_test_points: bool = Field(
        default_factory=lambda: _env_bool("EXECUTION_GATE_WARN_ON_PENDING_TEST_POINTS", True)
    )
    execution_gate_block_missing_dependency_points_threshold: int = Field(
        default_factory=lambda: int(os.getenv("EXECUTION_GATE_BLOCK_MISSING_DEPENDENCY_POINTS_THRESHOLD", "1"))
    )
    execution_gate_warn_on_low_confidence_dependency_points: bool = Field(
        default_factory=lambda: _env_bool("EXECUTION_GATE_WARN_ON_LOW_CONFIDENCE_DEPENDENCY_POINTS", True)
    )
    execution_gate_decision_privileged_roles: list[str] = Field(
        default_factory=_default_execution_gate_decision_roles
    )
    execution_gate_dual_approval_enabled: bool = Field(
        default_factory=lambda: _env_bool("EXECUTION_GATE_DUAL_APPROVAL_ENABLED", False)
    )
    execution_gate_dual_approval_bypass_roles: list[str] = Field(
        default_factory=_default_execution_gate_dual_approval_roles
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
