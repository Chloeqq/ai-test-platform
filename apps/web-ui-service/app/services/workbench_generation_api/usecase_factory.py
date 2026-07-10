from __future__ import annotations

from sqlalchemy.orm import Session

from .context import build_workbench_context
from .generate_case_service import GenerateCaseService
from .precheck_selected_intents_service import PrecheckSelectedIntentsService
from .save_test_point_assets_service import SaveTestPointAssetsService


def build_generate_case_usecase(db: Session) -> GenerateCaseService:
    return GenerateCaseService(context=build_workbench_context(db))


def build_precheck_selected_intents_usecase(db: Session) -> PrecheckSelectedIntentsService:
    return PrecheckSelectedIntentsService(context=build_workbench_context(db))


def build_save_test_point_assets_usecase(db: Session) -> SaveTestPointAssetsService:
    return SaveTestPointAssetsService(context=build_workbench_context(db))
