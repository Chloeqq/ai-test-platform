from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.config import get_settings
import app.main as main


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_non_dev_settings_do_not_default_to_weak_bootstrap_values(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("ADMIN_ROLE", raising=False)
    monkeypatch.delenv("DATABASE_AUTO_CREATE_TABLES", raising=False)

    settings = get_settings()

    assert settings.jwt_secret_key == ""
    assert settings.default_admin_username == ""
    assert settings.default_admin_password == ""
    assert settings.default_admin_role == ""
    assert settings.database_auto_create_tables is False


def test_dev_settings_keep_explicit_bootstrap_switch(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("ADMIN_ROLE", raising=False)
    monkeypatch.delenv("DATABASE_AUTO_CREATE_TABLES", raising=False)

    settings = get_settings()

    assert settings.jwt_secret_key == ""
    assert settings.default_admin_username == ""
    assert settings.default_admin_password == ""
    assert settings.default_admin_role == ""
    assert settings.database_auto_create_tables is False


def test_explicit_bootstrap_values_are_respected(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("JWT_SECRET_KEY", "explicit-secret")
    monkeypatch.setenv("ADMIN_USERNAME", "bootstrap-admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "bootstrap-password")
    monkeypatch.setenv("ADMIN_ROLE", "admin")
    monkeypatch.setenv("DATABASE_AUTO_CREATE_TABLES", "true")

    settings = get_settings()

    assert settings.jwt_secret_key == "explicit-secret"
    assert settings.default_admin_username == "bootstrap-admin"
    assert settings.default_admin_password == "bootstrap-password"
    assert settings.default_admin_role == "admin"
    assert settings.database_auto_create_tables is True


def test_non_dev_bootstrap_config_must_be_explicit(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "settings",
        SimpleNamespace(
            app_env="production",
            jwt_secret_key="",
            default_admin_username="",
            default_admin_password="",
            default_admin_role="",
            database_auto_create_tables=True,
            page_surface_login_url="http://localhost:5174/#/login",
        ),
    )

    with pytest.raises(RuntimeError, match="unsafe bootstrap configuration"):
        main._assert_safe_startup_config()
