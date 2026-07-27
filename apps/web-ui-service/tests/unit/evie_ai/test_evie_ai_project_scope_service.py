from __future__ import annotations

from unittest.mock import Mock, call

import pytest

from app.errors.evie_ai import EvieAiDomainError, EvieAiErrorCode, EvieAiErrorStage
from app.models import test_project as test_project_model
from app.repositories.test_project_repository import TestProjectRepository
from app.services.evie_ai.project_scope_service import ProjectScopeService


def _project(*, project_code: str = "atp", status: str = "active") -> test_project_model.TestProject:
    return test_project_model.TestProject(
        project_code=project_code,
        project_name="EvieAi test project",
        status=status,
    )


def _repository(project: test_project_model.TestProject | None) -> Mock:
    repository = Mock(spec=TestProjectRepository)
    repository.get_by_code.return_value = project
    return repository


def test_project_scope_service_returns_normalized_active_scope() -> None:
    repository = _repository(_project())

    scope = ProjectScopeService(repository).execute(" ATP ")

    assert scope.project_code == "atp"
    assert scope.is_active is True
    assert repository.mock_calls == [call.get_by_code("atp")]


@pytest.mark.parametrize(
    "project_code",
    [None, 42, "", " ", "x", "@", "atp!", "atp-1", "a" * 21],
)
def test_project_scope_service_rejects_missing_or_invalid_code_without_query(
    project_code: object,
) -> None:
    repository = _repository(_project())

    with pytest.raises(EvieAiDomainError) as exc_info:
        ProjectScopeService(repository).execute(project_code)  # type: ignore[arg-type]

    assert exc_info.value.code is EvieAiErrorCode.REQUEST_VALIDATION_ERROR
    assert exc_info.value.stage is EvieAiErrorStage.REQUEST_VALIDATION
    assert exc_info.value.retryable is False
    repository.get_by_code.assert_not_called()


def test_project_scope_service_rejects_unknown_project() -> None:
    repository = _repository(None)

    with pytest.raises(EvieAiDomainError) as exc_info:
        ProjectScopeService(repository).execute("missing")

    assert exc_info.value.code is EvieAiErrorCode.PROJECT_NOT_FOUND
    assert exc_info.value.stage is EvieAiErrorStage.REQUEST_VALIDATION
    assert exc_info.value.retryable is False
    assert repository.mock_calls == [call.get_by_code("missing")]


def test_project_scope_service_rejects_inactive_project() -> None:
    repository = _repository(_project(status="inactive"))

    with pytest.raises(EvieAiDomainError) as exc_info:
        ProjectScopeService(repository).execute("atp")

    assert exc_info.value.code is EvieAiErrorCode.PROJECT_INACTIVE
    assert exc_info.value.stage is EvieAiErrorStage.REQUEST_VALIDATION
    assert exc_info.value.retryable is False
    assert repository.mock_calls == [call.get_by_code("atp")]
