from __future__ import annotations

from typing import Any

import pytest
from app.models.user import User
from app.routers import auth
from app.schemas.user import UserCreate
from app.services.evie_ai.request_actor_context import RequestActorContext
from app.services.evie_ai.user_public_identity_service import UserPublicIdentityService
from fastapi import FastAPI
from fastapi.testclient import TestClient
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


def _registration_client(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[TestClient, _SessionStub]:
    db = _SessionStub()
    monkeypatch.setattr(auth, "UserRepository", _RepositoryStub)
    monkeypatch.setattr(auth, "hash_password", lambda _password: "hashed")
    monkeypatch.setattr(auth, "generate_user_public_id", lambda: PUBLIC_USER_ID)

    app = FastAPI()
    app.include_router(auth.router)

    def _override_db():
        yield db

    app.dependency_overrides[auth.get_db] = _override_db
    return TestClient(app), db


def test_user_create_ignores_unrelated_extra_fields() -> None:
    payload = UserCreate(
        username="tester",
        password="secret1",
        unrelated_legacy_field="ignored",
    )

    assert payload.username == "tester"
    assert "unrelated_legacy_field" not in payload.model_dump()


@pytest.mark.parametrize(
    "identity_overrides",
    [
        {"user_public_id": PUBLIC_USER_ID},
        {"actor_or_client_id": f"user:{PUBLIC_USER_ID}"},
        {
            "user_public_id": PUBLIC_USER_ID,
            "actor_or_client_id": f"user:{PUBLIC_USER_ID}",
        },
    ],
)
def test_user_create_rejects_identity_overrides(
    identity_overrides: dict[str, str],
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        UserCreate(
            username="tester",
            password="secret1",
            **identity_overrides,
        )

    message = exc_info.value.errors()[0]["msg"]
    assert "identity override fields are not allowed" in message
    for field_name in identity_overrides:
        assert field_name in message


def test_registration_api_ignores_unrelated_extra_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, db = _registration_client(monkeypatch)

    response = client.post(
        "/api/auth/register",
        json={
            "username": "tester",
            "password": "secret1",
            "unrelated_legacy_field": "ignored",
        },
    )

    assert response.status_code == 201
    assert db.committed is True
    assert response.json()["user_public_id"] == PUBLIC_USER_ID
    assert "id" not in response.json()


@pytest.mark.parametrize(
    "identity_overrides",
    [
        {"user_public_id": PUBLIC_USER_ID},
        {"actor_or_client_id": f"user:{PUBLIC_USER_ID}"},
        {
            "user_public_id": PUBLIC_USER_ID,
            "actor_or_client_id": f"user:{PUBLIC_USER_ID}",
        },
    ],
)
def test_registration_api_rejects_identity_overrides(
    monkeypatch: pytest.MonkeyPatch,
    identity_overrides: dict[str, str],
) -> None:
    client, db = _registration_client(monkeypatch)

    response = client.post(
        "/api/auth/register",
        json={
            "username": "tester",
            "password": "secret1",
            **identity_overrides,
        },
    )

    assert response.status_code == 422
    assert db.committed is False
    assert "identity override fields are not allowed" in response.text


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
    response_json = response.model_dump(mode="json")
    assert response_json["user_public_id"].startswith("usr_")
    assert "id" not in response_json


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


def test_authenticated_user_builds_stable_principal_and_actor_without_internal_id() -> None:
    user = User(
        id=42,
        user_public_id=PUBLIC_USER_ID,
        username="tester",
        hashed_password="hashed",
        role="developer",
        is_active=True,
    )

    principal = UserPublicIdentityService().execute(user)

    assert RequestActorContext().execute(principal) == f"user:{PUBLIC_USER_ID}"
    assert not hasattr(principal, "id")
