# ruff: noqa: E402
from __future__ import annotations

import hashlib
import sys
from pathlib import Path


WEB_UI_ROOT = Path(__file__).resolve().parents[2]
if str(WEB_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_UI_ROOT))
APPS_ROOT = Path(__file__).resolve().parents[3]
if str(APPS_ROOT) not in sys.path:
    sys.path.insert(0, str(APPS_ROOT))

from app.core.security import hash_password, verify_password


def test_verify_password_supports_bcrypt_hash() -> None:
    hashed = hash_password("admin123")

    assert verify_password("admin123", hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_verify_password_supports_legacy_sha256_digest() -> None:
    legacy_hash = hashlib.sha256("admin123".encode("utf-8")).hexdigest()

    assert verify_password("admin123", legacy_hash) is True
    assert verify_password("wrong-password", legacy_hash) is False
