"""AI 测试质量评估中心 — Repository 层。"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app.models.quality_eval import (
    QualityEvalDataset,
    QualityEvalItem,
    QualityEvalResult,
    QualityEvalRun,
)
from app.repositories.base import BaseRepository


class QualityEvalRepository(BaseRepository):
    """质量评估数据访问层。"""

    # ── Dataset ──────────────────────────────────────────────

    def list_datasets(self, *, project_code: str = "atp", task_type: str = "") -> list[QualityEvalDataset]:
        stmt = select(QualityEvalDataset).where(QualityEvalDataset.project_code == project_code)
        if task_type:
            stmt = stmt.where(QualityEvalDataset.task_type == task_type)
        stmt = stmt.order_by(QualityEvalDataset.updated_at.desc())
        return list(self.db.execute(stmt).scalars().all())

    def get_dataset(self, dataset_id: str) -> QualityEvalDataset | None:
        return self.db.execute(
            select(QualityEvalDataset).where(QualityEvalDataset.dataset_id == dataset_id)
        ).scalar_one_or_none()

    def save_dataset(self, dataset: QualityEvalDataset) -> QualityEvalDataset:
        self.db.add(dataset)
        self.db.flush()
        return dataset

    def delete_dataset(self, dataset_id: str) -> bool:
        """删除数据集 — ORM cascade 自动级联删除 items/runs → results。"""
        ds = self.get_dataset(dataset_id)
        if ds is None:
            return False
        self.db.delete(ds)
        self.db.flush()
        return True

    def increment_dataset_item_count(self, dataset_id: str, delta: int = 1) -> None:
        ds = self.get_dataset(dataset_id)
        if ds:
            ds.item_count = max(0, ds.item_count + delta)
            ds.updated_at = datetime.now(UTC)
            self.db.flush()

    # ── Items ────────────────────────────────────────────────

    def list_items(self, dataset_id: str) -> list[QualityEvalItem]:
        return list(
            self.db.execute(
                select(QualityEvalItem)
                .where(QualityEvalItem.dataset_id == dataset_id)
                .order_by(QualityEvalItem.created_at.asc())
            ).scalars().all()
        )

    def get_item(self, item_id: str) -> QualityEvalItem | None:
        return self.db.execute(
            select(QualityEvalItem).where(QualityEvalItem.item_id == item_id)
        ).scalar_one_or_none()

    def save_items(self, items: list[QualityEvalItem]) -> list[QualityEvalItem]:
        self.db.add_all(items)
        self.db.flush()
        return items

    # ── Runs ─────────────────────────────────────────────────

    def list_runs(self, *, project_code: str = "atp", dataset_id: str = "") -> list[QualityEvalRun]:
        stmt = select(QualityEvalRun).where(QualityEvalRun.project_code == project_code)
        if dataset_id:
            stmt = stmt.where(QualityEvalRun.dataset_id == dataset_id)
        stmt = stmt.order_by(QualityEvalRun.created_at.desc())
        return list(self.db.execute(stmt).scalars().all())

    def get_run(self, run_id: str) -> QualityEvalRun | None:
        return self.db.execute(
            select(QualityEvalRun).where(QualityEvalRun.run_id == run_id)
        ).scalar_one_or_none()

    def save_run(self, run: QualityEvalRun) -> QualityEvalRun:
        self.db.add(run)
        self.db.flush()
        return run

    def delete_run(self, run_id: str) -> bool:
        run = self.get_run(run_id)
        if run is None:
            return False
        self.db.delete(run)
        self.db.flush()
        return True

    # ── Results ──────────────────────────────────────────────

    def list_results(self, run_id: str) -> list[QualityEvalResult]:
        return list(
            self.db.execute(
                select(QualityEvalResult)
                .where(QualityEvalResult.run_id == run_id)
                .order_by(QualityEvalResult.weighted_score.asc())
            ).scalars().all()
        )

    def save_results(self, results: list[QualityEvalResult]) -> list[QualityEvalResult]:
        self.db.add_all(results)
        self.db.flush()
        return results
