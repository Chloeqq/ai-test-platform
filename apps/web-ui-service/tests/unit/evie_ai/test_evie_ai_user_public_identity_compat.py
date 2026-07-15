from __future__ import annotations

from typing import Any

import pytest
from app.models.user import User
from app.routers import auth
from app.schemas.user import UserCreate
from pydantic import ValidationError

PUBLIC_USER_ID = "usr_0123456789abcdef0123456789abcdef"


class _RepositoryStub:
    def __init__(self, _db: object) -> None:
        pass

    def get_by_username(self, _username: str) -> None:
        return None


class _SessionStub:
    def __init__(self) -> None:
        self.added: User | None = None
        self.committed = False

    def add(self, value: User) -> None:
        self.added = value

    def commit(self) -> None:
        self.committed = True
        assert self.added is not None
        self.added.id = 42

    def refresh(self, _value: User) -> None:
        return None


def test_user_create_rejects_client_supplied_public_identity() -> None:
    with pytest.raises(ValidationError) as exc_info:
        UserCreate(
            username="tester",
            password="secret1",
            user_public_id=PUBLIC_USER_ID,
        )
    assert exc_info.value.errors()[0]["type"] == "extra_forbidden"


def test_registration_allocates_public_identity_from_shared_generator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _SessionStub()
    monkeypatch.setattr(auth, "UserRepository", _RepositoryStub)
    monkeypatch.setattr(auth, "hash_password", lambda _password: "hashed")
    monkeypatch.setattr(auth, "generate_user_public_id", lambda: PUBLIC_USER_ID)

    response = auth.register(
        UserCreate(username="tester", password="secret1"),
        db=db,  # type: ignore[arg-type]
    )

    assert db.committed is True
    assert db.added is not None
    assert db.added.user_public_id == PUBLIC_USER_ID
    assert response.user_public_id == PUBLIC_USER_ID
    assert "id" not in type(response).model_fields


def test_token_subject_remains_internal_user_id_for_compatibility(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def _create_access_token(**kwargs: Any) -> str:
        captured.update(kwargs)
        return "encoded-token"

    monkeypatch.setattr(auth, "create_access_token", _create_access_token)
    user = User(
        id=42,
        user_public_id=PUBLIC_USER_ID,
        username="tester",
        hashed_password="hashed",
        role="viewer",
        is_active=True,
    )

    token = auth._build_token_response(user)

    assert captured["subject"] == "42"
    assert token.user.user_public_id == PUBLIC_USER_ID
    assert "id" not in type(token.user).model_fields
