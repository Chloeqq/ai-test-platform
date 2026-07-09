"""AI 测试质量评估中心 — 数据模型。

四张表 + 级联关系：
  quality_eval_datasets  ──< quality_eval_items  ──< quality_eval_results
  quality_eval_datasets  ──< quality_eval_runs   ──< quality_eval_results

删除 dataset 时自动级联删除 items → results 和 runs → results。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    pass  # 所有 relationship 引用在 with future.annotations 下延迟求值


class QualityEvalDataset(Base):
    __tablename__ = "quality_eval_datasets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    project_code: Mapped[str] = mapped_column(String(20), default="atp", index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    task_type: Mapped[str] = mapped_column(
        String(50),
        default="test_case_generation",
        comment="test_case_generation | script_generation | assertion_generation | data_generation",
    )
    eval_dimensions: Mapped[list[str]] = mapped_column(JSON, default=list)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ── 级联关系 ──
    items: Mapped[list["QualityEvalItem"]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
        lazy="select",
    )
    runs: Mapped[list["QualityEvalRun"]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
        lazy="select",
    )


class QualityEvalItem(Base):
    __tablename__ = "quality_eval_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    dataset_id: Mapped[str] = mapped_column(String(64), ForeignKey("quality_eval_datasets.dataset_id"), index=True)

    requirement_text: Mapped[str] = mapped_column(Text)
    context_json: Mapped[dict] = mapped_column(JSON, default=dict)

    expected_coverage: Mapped[list[str]] = mapped_column(JSON, default=list)
    expected_assertions: Mapped[list[dict]] = mapped_column(JSON, default=list)
    expected_page_codes: Mapped[list[str]] = mapped_column(JSON, default=list)

    perturbed_requirement: Mapped[str] = mapped_column(Text, default="")
    known_issues: Mapped[list[str]] = mapped_column(JSON, default=list)

    category: Mapped[str] = mapped_column(String(50), default="")
    meta_data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # ── 级联关系 ──
    dataset: Mapped["QualityEvalDataset"] = relationship(back_populates="items")
    results: Mapped[list["QualityEvalResult"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        lazy="select",
    )


class QualityEvalRun(Base):
    __tablename__ = "quality_eval_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    dataset_id: Mapped[str] = mapped_column(String(64), ForeignKey("quality_eval_datasets.dataset_id"), index=True)
    project_code: Mapped[str] = mapped_column(String(20), default="atp", index=True)

    agent_version: Mapped[str] = mapped_column(String(50), default="")
    llm_model: Mapped[str] = mapped_column(String(100), default="")
    prompt_version: Mapped[str] = mapped_column(String(50), default="")
    gate_rule_version: Mapped[str] = mapped_column(String(50), default="")

    task_type: Mapped[str] = mapped_column(String(50), default="test_case_generation")
    eval_dimensions: Mapped[list[str]] = mapped_column(JSON, default=list)

    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    completed_items: Mapped[int] = mapped_column(Integer, default=0)

    overall_score: Mapped[float] = mapped_column(Float, default=0.0)
    coverage_score: Mapped[float] = mapped_column(Float, default=0.0)
    assertion_score: Mapped[float] = mapped_column(Float, default=0.0)
    executability_score: Mapped[float] = mapped_column(Float, default=0.0)
    consistency_score: Mapped[float] = mapped_column(Float, default=0.0)
    robustness_score: Mapped[float] = mapped_column(Float, default=0.0)
    hallucination_risk: Mapped[float] = mapped_column(Float, default=0.0)

    summary_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── 级联关系 ──
    dataset: Mapped["QualityEvalDataset"] = relationship(back_populates="runs")
    results: Mapped[list["QualityEvalResult"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="select",
    )


class QualityEvalResult(Base):
    __tablename__ = "quality_eval_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    result_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("quality_eval_runs.run_id"), index=True)
    item_id: Mapped[str] = mapped_column(String(64), ForeignKey("quality_eval_items.item_id"), index=True)

    generated_case_json: Mapped[dict] = mapped_column(JSON, default=dict)
    generated_script: Mapped[str] = mapped_column(Text, default="")

    coverage_score: Mapped[float] = mapped_column(Float, default=0.0)
    coverage_detail: Mapped[dict] = mapped_column(JSON, default=dict)
    assertion_score: Mapped[float] = mapped_column(Float, default=0.0)
    assertion_detail: Mapped[dict] = mapped_column(JSON, default=dict)
    executability_score: Mapped[float] = mapped_column(Float, default=0.0)
    executability_detail: Mapped[dict] = mapped_column(JSON, default=dict)

    consistency_runs: Mapped[list[dict]] = mapped_column(JSON, default=list)
    consistency_score: Mapped[float] = mapped_column(Float, default=0.0)

    perturbed_output: Mapped[dict] = mapped_column(JSON, default=dict)
    robustness_score: Mapped[float] = mapped_column(Float, default=0.0)

    hallucination_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    hallucination_score: Mapped[float] = mapped_column(Float, default=0.0)

    weighted_score: Mapped[float] = mapped_column(Float, default=0.0)

    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # ── 双向关系（只读取，不设 cascade，由 Item/Run 侧管理级联） ──
    run: Mapped["QualityEvalRun"] = relationship(back_populates="results")
    item: Mapped["QualityEvalItem"] = relationship(back_populates="results")