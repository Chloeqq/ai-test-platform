"""EvieAi Requirement 聚合持久化访问。"""

from __future__ import annotations

from sqlalchemy import select, update

from app.models.evie_ai import Requirement, RequirementVersion
from app.repositories.base import BaseRepository
from app.repositories.evie_ai.errors import (
    CurrentVersionOwnershipError,
    OptimisticConcurrencyError,
)


class RequirementRepository(BaseRepository):
    """Requirement 与不可变版本的最小数据访问层。"""

    def add(self, requirement: Requirement) -> Requirement:
        self.db.add(requirement)
        self.db.flush()
        return requirement

    def add_version(self, version: RequirementVersion) -> RequirementVersion:
        self.db.add(version)
        self.db.flush()
        return version

    def get_by_pk(self, requirement_pk: int) -> Requirement | None:
        return self.db.execute(
            select(Requirement).where(
                Requirement.id == requirement_pk,
                Requirement.deleted_at.is_(None),
            )
        ).scalar_one_or_none()

    def get_by_requirement_id(self, requirement_id: str) -> Requirement | None:
        return self.db.execute(
            select(Requirement).where(
                Requirement.requirement_id == requirement_id,
                Requirement.deleted_at.is_(None),
            )
        ).scalar_one_or_none()

    def resolve_source_version(
        self,
        *,
        project_code: str,
        requirement_id: str,
        requirement_version_id: str,
    ) -> tuple[Requirement, RequirementVersion] | None:
        """按公开 ID 解析同项目、未删除的 Requirement 来源。"""
        return self.db.execute(
            select(Requirement, RequirementVersion)
            .join(
                RequirementVersion,
                RequirementVersion.requirement_pk == Requirement.id,
            )
            .where(
                Requirement.project_code == project_code,
                Requirement.requirement_id == requirement_id,
                Requirement.deleted_at.is_(None),
                RequirementVersion.requirement_version_id
                == requirement_version_id,
            )
        ).one_or_none()

    def get_current_version(
        self,
        requirement_pk: int,
    ) -> RequirementVersion | None:
        return self.db.execute(
            select(RequirementVersion)
            .join(
                Requirement,
                Requirement.current_version_pk == RequirementVersion.id,
            )
            .where(
                Requirement.id == requirement_pk,
                Requirement.deleted_at.is_(None),
                RequirementVersion.requirement_pk == requirement_pk,
            )
        ).scalar_one_or_none()

    def list_versions(self, requirement_pk: int) -> list[RequirementVersion]:
        return list(
            self.db.execute(
                select(RequirementVersion)
                .join(Requirement, Requirement.id == RequirementVersion.requirement_pk)
                .where(
                    RequirementVersion.requirement_pk == requirement_pk,
                    Requirement.deleted_at.is_(None),
                )
                .order_by(RequirementVersion.version_no.desc())
            )
            .scalars()
            .all()
        )

    def set_current_version(
        self,
        requirement: Requirement,
        version: RequirementVersion,
        *,
        expected_row_version: int,
        updated_by: str,
        trace_id: str | None = None,
    ) -> Requirement:
        if (
            requirement.id is None
            or version.id is None
            or version.requirement_pk != requirement.id
        ):
            raise CurrentVersionOwnershipError(
                aggregate_type="requirement",
                aggregate_id=requirement.requirement_id,
                trace_id=trace_id,
            )

        result = self.db.execute(
            update(Requirement)
            .where(
                Requirement.id == requirement.id,
                Requirement.row_version == expected_row_version,
                Requirement.deleted_at.is_(None),
            )
            .values(
                current_version_pk=version.id,
                row_version=Requirement.row_version + 1,
                updated_by=updated_by,
            )
            .execution_options(synchronize_session="fetch")
        )
        if result.rowcount != 1:
            raise OptimisticConcurrencyError(
                aggregate_type="requirement",
                aggregate_id=requirement.requirement_id,
                trace_id=trace_id,
            )
        self.db.flush()
        self.db.refresh(requirement)
        return requirement
