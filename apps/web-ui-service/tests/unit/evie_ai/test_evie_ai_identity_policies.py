from __future__ import annotations

import pytest
from app.errors.evie_ai import EvieAiDomainError, EvieAiErrorCode
from app.policies.evie_ai.actor_identity_policy import normalize_user_actor
from app.policies.evie_ai.asset_code_policy import asset_code_for_new_asset
from app.policies.evie_ai.user_identity_policy import is_valid_user_public_id

USER_ID = "usr_0123456789abcdef0123456789abcdef"
ASSET_ID = "ta_0123456789abcdef0123456789abcdef"


def test_user_public_id_and_actor_use_approved_stable_identity() -> None:
    assert is_valid_user_public_id(USER_ID)
    assert normalize_user_actor(USER_ID) == f"user:{USER_ID}"


@pytest.mark.parametrize(
    "invalid_value",
    [None, "", "usr_short", "USR_0123456789abcdef0123456789abcdef", "123"],
)
def test_invalid_user_public_identity_fails_closed(
    invalid_value: str | None,
) -> None:
    assert not is_valid_user_public_id(invalid_value)
    with pytest.raises(EvieAiDomainError) as exc_info:
        normalize_user_actor(invalid_value)

    assert exc_info.value.code is EvieAiErrorCode.DATA_INTEGRITY_ERROR


def test_asset_code_for_new_asset_is_its_public_id() -> None:
    assert asset_code_for_new_asset(ASSET_ID) == ASSET_ID


def test_asset_code_policy_rejects_non_asset_identity() -> None:
    with pytest.raises(EvieAiDomainError):
        asset_code_for_new_asset(USER_ID)
