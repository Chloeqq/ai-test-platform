"""类型别名存根 — 依赖注入/回调协议的类型标注用。

所有别名仅在 TYPE_CHECKING 下声明，运行时不存在。
使用 `from __future__ import annotations` 的文件中，注解被延迟为字符串，
这些类型名永远不需要在运行时求值。
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # ── 回调协议 ────────────────────────────────────────────
    AllocateCaseId = Callable[..., str]  # type: ignore[valid-type]
    AppendHistory = Callable[..., None]  # type: ignore[valid-type]
    BuildCoverageSummary = Callable[..., dict[str, Any]]  # type: ignore[valid-type]
    BuildExecutionGate = Callable[..., dict[str, Any]]  # type: ignore[valid-type]
    BuildExecutionGateAuditSnapshot = Callable[..., dict[str, Any]]  # type: ignore[valid-type]
    BuildExecutionPlanForRisk = Callable[..., dict[str, Any]]  # type: ignore[valid-type]
    BuildPageSemanticSummary = Callable[..., dict[str, Any]]  # type: ignore[valid-type]
    BuildReviewAuditSummary = Callable[..., dict[str, Any]]  # type: ignore[valid-type]
    BuildRiskReport = Callable[..., dict[str, Any]]  # type: ignore[valid-type]
    BuildRiskReportSummary = Callable[..., dict[str, Any]]  # type: ignore[valid-type]
    BuildRuntimeExecutionRecord = Callable[..., dict[str, Any]]  # type: ignore[valid-type]
    BuildSelectionSummary = Callable[..., dict[str, Any]]  # type: ignore[valid-type]
    BuildSemanticSummaryFn = Callable[..., dict[str, Any]]  # type: ignore[valid-type]
    BuildTechniqueSummaryFn = Callable[..., dict[str, Any]]  # type: ignore[valid-type]
    BuildTestPointAssetTechniqueSummary = Callable[..., dict[str, Any]]  # type: ignore[valid-type]
    BuildTraceabilitySummary = Callable[..., dict[str, Any]]  # type: ignore[valid-type]
    ClampConfidence = Callable[..., float]  # type: ignore[valid-type]
    CollectCaseItems = Callable[..., list[dict[str, Any]]]  # type: ignore[valid-type]
    CountTestPointTypesFn = Callable[..., dict[str, int]]  # type: ignore[valid-type]
    DerivePoints = Callable[..., list[dict[str, Any]]]  # type: ignore[valid-type]
    EnsureProjectWritable = Callable[..., None]  # type: ignore[valid-type]
    ExtractQualityGate = Callable[..., dict[str, Any]]  # type: ignore[valid-type]
    FindRunItem = Callable[..., dict[str, Any] | None]  # type: ignore[valid-type]
    IsQualityGateBlocked = Callable[..., bool]  # type: ignore[valid-type]
    LatestRunSnapshotForCase = Callable[..., dict[str, Any] | None]  # type: ignore[valid-type]
    LoadTestPointAsset = Callable[..., dict[str, Any] | None]  # type: ignore[valid-type]
    MergeReferenceItemsFn = Callable[..., list[dict[str, Any]]]  # type: ignore[valid-type]
    NormalizePageSlug = Callable[..., str]  # type: ignore[valid-type]
    NormalizeTestPointPlanPayload = Callable[..., dict[str, Any]]  # type: ignore[valid-type]
    NowIso = Callable[[], str]  # type: ignore[valid-type]
    NowIsoFn = Callable[[], str]  # type: ignore[valid-type]
    PaginateCaseItems = Callable[..., dict[str, Any]]  # type: ignore[valid-type]
    ReadCaseYaml = Callable[..., dict[str, Any]]  # type: ignore[valid-type]
    ReadJsonList = Callable[..., list[dict[str, Any]]]  # type: ignore[valid-type]
    ResolveCaseYamlPath = Callable[[str, str], Path]  # type: ignore[valid-type]
    RunOrchestratorGenerate = Callable[..., dict[str, Any]]  # type: ignore[valid-type]
    RunOrchestratorRisk = Callable[..., dict[str, Any]]  # type: ignore[valid-type]
    RuntimeViewWithExecutionRecordPreferred = Callable[..., dict[str, Any]]  # type: ignore[valid-type]
    SaveCaseState = Callable[..., None]  # type: ignore[valid-type]
    ValidationReport = Any  # type: ignore[valid-type]
    WriteCaseYaml = Callable[..., Path]  # type: ignore[valid-type]
