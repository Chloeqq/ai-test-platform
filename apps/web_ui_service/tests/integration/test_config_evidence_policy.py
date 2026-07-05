from __future__ import annotations

import sys
from pathlib import Path

import pytest


WEB_UI_ROOT = Path(__file__).resolve().parents[2]
if str(WEB_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_UI_ROOT))
existing_app = sys.modules.get("app")
if existing_app is not None and not getattr(existing_app, "__path__", None):
    sys.modules.pop("app", None)

from app.core.config import Settings  # noqa: E402


pytestmark = [pytest.mark.integration]


def test_evidence_policy_strict_disables_compat_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVIDENCE_MANIFEST_POLICY", "strict")
    monkeypatch.delenv("EVIDENCE_MANIFEST_COMPAT_SCAN_ENABLED", raising=False)
    settings = Settings()
    assert settings.evidence_manifest_policy == "strict"
    assert settings.evidence_manifest_compat_scan_enabled is False


def test_evidence_policy_compat_enables_compat_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVIDENCE_MANIFEST_POLICY", "compat")
    monkeypatch.delenv("EVIDENCE_MANIFEST_COMPAT_SCAN_ENABLED", raising=False)
    settings = Settings()
    assert settings.evidence_manifest_policy == "compat"
    assert settings.evidence_manifest_compat_scan_enabled is True


def test_evidence_policy_auto_uses_strict_env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("EVIDENCE_MANIFEST_POLICY", "auto")
    monkeypatch.delenv("EVIDENCE_MANIFEST_COMPAT_SCAN_ENABLED", raising=False)
    settings = Settings()
    assert settings.evidence_manifest_policy == "auto"
    assert settings.evidence_manifest_compat_scan_enabled is False


def test_evidence_policy_auto_uses_compat_for_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("EVIDENCE_MANIFEST_POLICY", "auto")
    monkeypatch.delenv("EVIDENCE_MANIFEST_COMPAT_SCAN_ENABLED", raising=False)
    settings = Settings()
    assert settings.evidence_manifest_policy == "auto"
    assert settings.evidence_manifest_compat_scan_enabled is True


def test_evidence_compat_scan_env_override_has_highest_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("EVIDENCE_MANIFEST_POLICY", "strict")
    monkeypatch.setenv("EVIDENCE_MANIFEST_COMPAT_SCAN_ENABLED", "true")
    settings = Settings()
    assert settings.evidence_manifest_policy == "strict"
    assert settings.evidence_manifest_compat_scan_enabled is True


def test_invalid_evidence_policy_falls_back_to_auto(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("EVIDENCE_MANIFEST_POLICY", "unexpected")
    monkeypatch.delenv("EVIDENCE_MANIFEST_COMPAT_SCAN_ENABLED", raising=False)
    settings = Settings()
    assert settings.evidence_manifest_policy == "auto"
    assert settings.evidence_manifest_compat_scan_enabled is False


def test_page_surface_allowed_hosts_include_base_url_and_local_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("BASE_URL", "http://localhost:5173/login#/login")
    monkeypatch.delenv("PAGE_SURFACE_ALLOWED_HOSTS", raising=False)
    settings = Settings()

    assert "localhost" in settings.page_surface_allowed_hosts
    assert "127.0.0.1" in settings.page_surface_allowed_hosts


def test_page_surface_allowed_hosts_respects_explicit_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("BASE_URL", "https://qa.example.com/login")
    monkeypatch.setenv("PAGE_SURFACE_ALLOWED_HOSTS", "internal.example.com,*.corp.example.com")
    settings = Settings()

    assert "qa.example.com" in settings.page_surface_allowed_hosts
    assert "internal.example.com" in settings.page_surface_allowed_hosts
    assert "*.corp.example.com" in settings.page_surface_allowed_hosts
