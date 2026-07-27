from __future__ import annotations

from unittest.mock import Mock

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.errors.evie_ai import EvieAiDomainError, EvieAiErrorCode, EvieAiErrorStage
from app.main import (
    _disable_allure_cache,
    _handle_evie_ai_domain_error,
    _handle_http_exception,
    _handle_request_validation_error,
    _handle_unexpected_exception,
)
from app.models import test_project as test_project_model
from app.repositories.test_project_repository import TestProjectRepository
from app.services.evie_ai.project_access_authorizer import ProjectAccessAuthorizer
from app.services.evie_ai.project_scope_service import ProjectScopeService
from app.services.evie_ai.request_actor_context import RequestActorContext
from app.services.evie_ai.request_channel_context import RequestChannelContext
from app.services.evie_ai.user_public_identity_service import TrustedUserPrincipal


class _ProjectScopePayload(BaseModel):
    project_code: str = Field(min_length=2)


def _security_client() -> TestClient:
    repository = Mock(spec=TestProjectRepository)
    repository.get_by_code.return_value = test_project_model.TestProject(
        project_code="atp",
        project_name="EvieAi test project",
        status="active",
    )
    app = FastAPI()
    app.middleware("http")(_disable_allure_cache)
    app.add_exception_handler(EvieAiDomainError, _handle_evie_ai_domain_error)
    app.add_exception_handler(RequestValidationError, _handle_request_validation_error)
    app.add_exception_handler(HTTPException, _handle_http_exception)
    app.add_exception_handler(Exception, _handle_unexpected_exception)

    @app.post("/api/evie-ai/test-security/context")
    async def security_context(payload: _ProjectScopePayload, request: Request) -> dict[str, str]:
        principal = TrustedUserPrincipal(
            user_public_id="usr_0123456789abcdef0123456789abcdef",
            role="admin",
            is_active=True,
        )
        ProjectAccessAuthorizer().execute(principal)
        scope = ProjectScopeService(repository).execute(payload.project_code)
        return {
            "project_code": scope.project_code,
            "actor": RequestActorContext().execute(principal),
            "channel": RequestChannelContext().execute(),
            "request_id": request.state.evie_ai_trace_context.request_id,
        }

    @app.get("/api/evie-ai/test-security/http-401")
    async def evie_ai_http_401() -> None:
        raise HTTPException(status_code=401, detail="token must not be exposed")

    @app.get("/api/evie-ai/test-security/unexpected")
    async def evie_ai_unexpected_error() -> None:
        raise RuntimeError("SQL password=secret must not be exposed")

    @app.post("/api/evie-ai/test-security/replay")
    async def evie_ai_replay_body(request: Request) -> dict[str, int]:
        return {"body_size": len(await request.body())}

    @app.get("/api/evie-ai/test-security/stream")
    async def evie_ai_stream() -> StreamingResponse:
        return StreamingResponse(iter([b"stream-ok"]), media_type="text/plain")

    @app.get("/legacy/http-401")
    async def legacy_http_401() -> None:
        raise HTTPException(status_code=401, detail="legacy unauthorized")

    return TestClient(app, raise_server_exceptions=False)


def test_evie_ai_test_route_builds_security_context_without_client_actor_or_channel() -> None:
    with _security_client() as client:
        response = client.post(
            "/api/evie-ai/test-security/context",
            headers={"X-Request-Id": "request-123"},
            json={"project_code": "ATP"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "project_code": "atp",
        "actor": "user:usr_0123456789abcdef0123456789abcdef",
        "channel": "api",
        "request_id": "request-123",
    }
    assert response.headers["X-Request-Id"] == "request-123"


def test_evie_ai_http_exception_uses_structured_envelope() -> None:
    with _security_client() as client:
        response = client.get("/api/evie-ai/test-security/http-401")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "EVIE_AUTHENTICATION_REQUIRED"
    assert response.json()["error"]["request_id"] == response.headers["X-Request-Id"]
    assert "token must not be exposed" not in response.text


def test_evie_ai_request_validation_hides_input_value() -> None:
    with _security_client() as client:
        response = client.post(
            "/api/evie-ai/test-security/context",
            json={"project_code": ""},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "EVIE_REQUEST_VALIDATION_ERROR"
    assert "input" not in response.text


def test_evie_ai_unexpected_exception_hides_internal_details() -> None:
    with _security_client() as client:
        response = client.get("/api/evie-ai/test-security/unexpected")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "EVIE_DATA_INTEGRITY_ERROR"
    assert "password=secret" not in response.text


def test_evie_ai_middleware_replays_body_and_keeps_streaming_response_intact() -> None:
    with _security_client() as client:
        replay = client.post(
            "/api/evie-ai/test-security/replay",
            content=b"plain natural language body",
            headers={"content-type": "text/plain"},
        )
        stream = client.get("/api/evie-ai/test-security/stream")

    assert replay.status_code == 200
    assert replay.json()["body_size"] == len(b"plain natural language body")
    assert stream.status_code == 200
    assert stream.text == "stream-ok"


def test_non_evie_ai_http_exception_keeps_existing_response_shape() -> None:
    with _security_client() as client:
        response = client.get("/legacy/http-401")

    assert response.status_code == 401
    assert response.json() == {"detail": "legacy unauthorized"}
