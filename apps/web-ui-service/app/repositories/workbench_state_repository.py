"""Repository for Workbench state models.

Covers: WorkbenchRuntimeRun, WorkbenchReviewDecision,
WorkbenchExecutionGateDecision, WorkbenchHistoryEvent,
WorkbenchDefectLink, WorkbenchFailureSourceCalibration.
"""
from __future__ import annotations

from sqlalchemy import delete, select

from app.models.workbench_state import (
    WorkbenchDefectLink,
    WorkbenchExecutionGateDecision,
    WorkbenchFailureSourceCalibration,
    WorkbenchHistoryEvent,
    WorkbenchReviewDecision,
    WorkbenchRuntimeRun,
)
from .base import BaseRepository


class WorkbenchStateRepository(BaseRepository):
    """Repository for the 6 Workbench state models."""

    # ---- WorkbenchRuntimeRun ----

    def get_runtime_run_by_run_id(self, run_id: str) -> WorkbenchRuntimeRun | None:
        return self.db.execute(
            select(WorkbenchRuntimeRun).where(WorkbenchRuntimeRun.run_id == run_id)
        ).scalar_one_or_none()

    def list_all_runtime_runs(self) -> list[WorkbenchRuntimeRun]:
        return list(
            self.db.execute(
                select(WorkbenchRuntimeRun).order_by(
                    WorkbenchRuntimeRun.updated_at.desc(),
                    WorkbenchRuntimeRun.id.desc(),
                )
            ).scalars().all()
        )

    # ---- WorkbenchReviewDecision ----

    def get_review_decision(
        self, project: str, run_id: str, page: str, review_type: str
    ) -> WorkbenchReviewDecision | None:
        return self.db.execute(
            select(WorkbenchReviewDecision).where(
                WorkbenchReviewDecision.project == project,
                WorkbenchReviewDecision.run_id == run_id,
                WorkbenchReviewDecision.page == page,
                WorkbenchReviewDecision.review_type == review_type,
            )
        ).scalar_one_or_none()

    def list_all_review_decisions(self) -> list[WorkbenchReviewDecision]:
        return list(
            self.db.execute(
                select(WorkbenchReviewDecision).order_by(
                    WorkbenchReviewDecision.updated_at.desc(),
                    WorkbenchReviewDecision.id.desc(),
                )
            ).scalars().all()
        )

    # ---- WorkbenchExecutionGateDecision ----

    def get_execution_gate_decision(
        self, project: str, run_id: str, page: str
    ) -> WorkbenchExecutionGateDecision | None:
        return self.db.execute(
            select(WorkbenchExecutionGateDecision).where(
                WorkbenchExecutionGateDecision.project == project,
                WorkbenchExecutionGateDecision.run_id == run_id,
                WorkbenchExecutionGateDecision.page == page,
            )
        ).scalar_one_or_none()

    def list_all_execution_gate_decisions(self) -> list[WorkbenchExecutionGateDecision]:
        return list(
            self.db.execute(
                select(WorkbenchExecutionGateDecision).order_by(
                    WorkbenchExecutionGateDecision.updated_at.desc(),
                    WorkbenchExecutionGateDecision.id.desc(),
                )
            ).scalars().all()
        )

    # ---- WorkbenchDefectLink ----

    def get_defect_link(self, case_id: str, defect_id: str) -> WorkbenchDefectLink | None:
        return self.db.execute(
            select(WorkbenchDefectLink).where(
                WorkbenchDefectLink.case_id == case_id,
                WorkbenchDefectLink.defect_id == defect_id,
            )
        ).scalar_one_or_none()

    def list_all_defect_links(self) -> list[WorkbenchDefectLink]:
        return list(
            self.db.execute(
                select(WorkbenchDefectLink).order_by(
                    WorkbenchDefectLink.updated_at.desc(),
                    WorkbenchDefectLink.id.desc(),
                )
            ).scalars().all()
        )

    # ---- WorkbenchFailureSourceCalibration ----

    def get_calibration_by_sample_id(
        self, sample_id: str
    ) -> WorkbenchFailureSourceCalibration | None:
        return self.db.execute(
            select(WorkbenchFailureSourceCalibration).where(
                WorkbenchFailureSourceCalibration.sample_id == sample_id
            )
        ).scalar_one_or_none()

    def list_all_calibrations(self) -> list[WorkbenchFailureSourceCalibration]:
        return list(
            self.db.execute(
                select(WorkbenchFailureSourceCalibration).order_by(
                    WorkbenchFailureSourceCalibration.updated_at.desc(),
                    WorkbenchFailureSourceCalibration.id.desc(),
                )
            ).scalars().all()
        )

    # ---- WorkbenchHistoryEvent ----

    def list_all_history_events(self) -> list[WorkbenchHistoryEvent]:
        return list(
            self.db.execute(
                select(WorkbenchHistoryEvent).order_by(WorkbenchHistoryEvent.id.desc())
            ).scalars().all()
        )

    # ---- Bulk operations ----

    def delete_all(self, model_class: type) -> None:
        self.db.execute(delete(model_class))
