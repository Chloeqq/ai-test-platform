from __future__ import annotations

from sqlalchemy.orm import Session

from .auto_run_service import AutoRunService
from .context import build_workbench_context
from .full_chain_service import FullChainPipeline, FullChainService
from .generate_case_service import GenerateCaseService
from .save_test_point_assets_service import SaveTestPointAssetsService
from .precheck_selected_intents_service import PrecheckSelectedIntentsService


def build_generate_case_usecase(db: Session) -> GenerateCaseService:
    return GenerateCaseService(context=build_workbench_context(db))


def build_full_chain_usecase(db: Session) -> FullChainService:
    context = build_workbench_context(db)
    pipeline = FullChainPipeline(context=context)
    return FullChainService(pipeline=pipeline)


def build_auto_run_usecase(db: Session) -> AutoRunService:
    return AutoRunService(context=build_workbench_context(db))


def build_precheck_selected_intents_usecase(db: Session) -> PrecheckSelectedIntentsService:
    return PrecheckSelectedIntentsService(context=build_workbench_context(db))


def build_save_test_point_assets_usecase(db: Session) -> SaveTestPointAssetsService:
    return SaveTestPointAssetsService(context=build_workbench_context(db))
