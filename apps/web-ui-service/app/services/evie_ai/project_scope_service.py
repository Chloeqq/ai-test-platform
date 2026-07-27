"""EvieAi 请求的显式、只读项目作用域校验。"""

from __future__ import annotations

from dataclasses import dataclass

from app.errors.evie_ai import (
    EvieAiDomainError,
    EvieAiErrorCode,
    EvieAiErrorStage,
)
from app.repositories.test_project_repository import TestProjectRepository
from shared_backend.type_utils import normalize_project_code_strict


@dataclass(frozen=True)
class ValidatedProjectScope:
    """项目存在且处于 active 状态的标准化项目作用域。"""

    project_code: str
    is_active: bool


class ProjectScopeService:
    """校验显式项目作用域，不改变项目状态。"""

    def __init__(self, repository: TestProjectRepository) -> None:
        self._repository = repository

    def execute(self, project_code: str) -> ValidatedProjectScope:
        normalized_project_code = self._normalize_project_code(project_code)
        project = self._repository.get_by_code(normalized_project_code)
        if project is None:
            raise EvieAiDomainError(
                EvieAiErrorCode.PROJECT_NOT_FOUND,
                stage=EvieAiErrorStage.REQUEST_VALIDATION,
                message="The requested project scope does not exist.",
                retryable=False,
            )

        is_active = str(project.status or "").strip().lower() == "active"
        if not is_active:
            raise EvieAiDomainError(
                EvieAiErrorCode.PROJECT_INACTIVE,
                stage=EvieAiErrorStage.REQUEST_VALIDATION,
                message="The requested project scope is inactive.",
                retryable=False,
            )

        return ValidatedProjectScope(
            project_code=normalized_project_code,
            is_active=is_active,
        )

    @staticmethod
    def _normalize_project_code(project_code: str) -> str:
        try:
            if not isinstance(project_code, str):
                raise ValueError("project_code must be a string")
            raw_project_code = project_code.strip().lower()
            normalized_project_code = normalize_project_code_strict(
                raw_project_code,
                max_len=20,
            )
            # 作用域校验可去除首尾空白并统一大小写，但不能静默丢弃输入字符。
            if normalized_project_code != raw_project_code:
                raise ValueError("project_code must contain letters or digits only")
            return normalized_project_code
        except ValueError as exc:
            raise EvieAiDomainError(
                EvieAiErrorCode.REQUEST_VALIDATION_ERROR,
                stage=EvieAiErrorStage.REQUEST_VALIDATION,
                message="An explicit valid project code is required.",
                retryable=False,
            ) from exc
