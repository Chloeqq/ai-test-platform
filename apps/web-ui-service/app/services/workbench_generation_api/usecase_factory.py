from __future__ import annotations

from sqlalchemy.orm import Session

from .auto_run_service import AutoRunService
from .context import build_workbench_context
from .full_chain_service import FullChainPipeline, FullChainService
from .generate_case_service import GenerateCaseService


def build_generate_case_usecase(db: Session) -> GenerateCaseService:
    return GenerateCaseService(context=build_workbench_context(db))


def build_full_chain_usecase(db: Session) -> FullChainService:
    context = build_workbench_context(db)
    pipeline = FullChainPipeline(context=context)
    return FullChainService(pipeline=pipeline)


def build_auto_run_usecase(db: Session) -> AutoRunService:
    return AutoRunService(context=build_workbench_context(db))
