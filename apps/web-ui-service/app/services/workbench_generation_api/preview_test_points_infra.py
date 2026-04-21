from __future__ import annotations

# DEPRECATED: PreviewTestPointsCompiler is no longer used by the preview usecase.
# The preview endpoint now delegates to build_preview_response / run_preview_pipeline
# (the single canonical preview path).
# This module is kept for backward compatibility only.

from shared_backend import PreviewTestPointsCompiler

from .orchestrator_client_factory import build_orchestrator_client


def build_compiler() -> PreviewTestPointsCompiler:
    """Deprecated: use build_preview_usecase() instead."""
    return PreviewTestPointsCompiler(orchestrator_client=build_orchestrator_client())
