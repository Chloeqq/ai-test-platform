"""Authority policy for new TestAsset asset codes."""

from __future__ import annotations

import re

from app.core.id_gen import TEST_ASSET_ID_PATTERN
from app.errors.evie_ai import EvieAiDomainError, EvieAiErrorCode, EvieAiErrorStage


def asset_code_for_new_asset(test_asset_id: str) -> str:
    if re.fullmatch(TEST_ASSET_ID_PATTERN, test_asset_id) is None:
        raise EvieAiDomainError(
            EvieAiErrorCode.DATA_INTEGRITY_ERROR,
            stage=EvieAiErrorStage.IDENTITY,
            message="A valid TestAsset public identity is required.",
            retryable=False,
        )
    return test_asset_id
